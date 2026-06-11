from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd

from src import config
from src.secrets import load_local_env
from src.utils import empty_frame, normalize_symbol, write_parquet


FMP_PROFILE_ENDPOINT = "https://financialmodelingprep.com/stable/profile"
FMP_PROFILE_COLUMNS = [
    "symbol",
    "companyName",
    "exchange",
    "currency",
    "sector",
    "industry",
    "isEtf",
    "isFund",
    "isAdr",
    "isActivelyTrading",
    "source",
]


def _empty_profiles() -> pd.DataFrame:
    return empty_frame(FMP_PROFILE_COLUMNS)


def _profile_from_payload(payload: object) -> dict | None:
    if not isinstance(payload, list) or not payload:
        return None
    item = payload[0]
    if not isinstance(item, dict):
        return None
    return {
        "symbol": normalize_symbol(item.get("symbol")),
        "companyName": item.get("companyName"),
        "exchange": item.get("exchange") or item.get("exchangeFullName"),
        "currency": item.get("currency"),
        "sector": item.get("sector"),
        "industry": item.get("industry"),
        "isEtf": item.get("isEtf"),
        "isFund": item.get("isFund"),
        "isAdr": item.get("isAdr"),
        "isActivelyTrading": item.get("isActivelyTrading"),
        "source": "fmp_profile",
    }


def _symbols_from_master(path: Path) -> list[str]:
    if not path.exists():
        return []
    symbols = pd.read_parquet(path, columns=["symbol"])["symbol"].dropna().map(normalize_symbol)
    return sorted({symbol for symbol in symbols if symbol})


def collect_fmp_profile_metadata(
    symbols: list[str] | None = None,
    symbols_path: Path = config.SYMBOL_MASTER_PATH,
    raw_dir: Path = config.RAW_FMP_DIR / "profiles",
    output_path: Path = config.FMP_PROFILE_METADATA_PATH,
    api_key: str | None = None,
    limit: int = 0,
    sleep_seconds: float = 0.25,
) -> pd.DataFrame:
    """Collect cached FMP profile metadata.

    limit is the maximum number of new API requests. Cached profiles are always parsed.
    """

    load_local_env()
    api_key = api_key or os.getenv("FMP_API_KEY")
    requested_symbols = symbols or _symbols_from_master(symbols_path)
    requested_symbols = sorted({symbol for symbol in map(normalize_symbol, requested_symbols) if symbol})

    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    new_requests = 0
    failures = 0

    for symbol in requested_symbols:
        raw_path = raw_dir / f"{symbol.replace('.', '-')}.json"
        payload = None
        if raw_path.exists() and raw_path.stat().st_size > 0:
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
        elif api_key and new_requests < limit:
            import requests

            try:
                response = requests.get(
                    FMP_PROFILE_ENDPOINT,
                    params={"symbol": symbol.replace(".", "-"), "apikey": api_key},
                    timeout=30,
                )
            except requests.RequestException as exc:
                failures += 1
                if failures <= 10:
                    print(f"[fmp_profile] {symbol} request failed: {exc}")
                continue

            if response.status_code in {401, 402, 403, 429}:
                print(f"[fmp_profile] API limit/auth response {response.status_code}; stopping new requests.")
                break
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                failures += 1
                if failures <= 10:
                    print(f"[fmp_profile] {symbol} HTTP error: {exc}")
                continue

            payload = response.json()
            raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            new_requests += 1
            time.sleep(sleep_seconds)

        if payload is None:
            continue

        row = _profile_from_payload(payload)
        if row and row["symbol"]:
            rows.append(row)

    result = pd.DataFrame(rows, columns=FMP_PROFILE_COLUMNS) if rows else _empty_profiles()
    result = result.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
    write_parquet(result, output_path)
    print(
        f"[fmp_profile] Wrote {len(result):,} cached profile rows to {output_path} "
        f"({new_requests:,} new requests)."
    )
    return result


if __name__ == "__main__":
    config.ensure_directories()
    collect_fmp_profile_metadata()
