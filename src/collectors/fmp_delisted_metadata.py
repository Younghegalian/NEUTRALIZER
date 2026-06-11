from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd

from src import config
from src.secrets import load_local_env
from src.utils import empty_frame, normalize_symbol, parse_date, write_parquet


FMP_ENDPOINT = "https://financialmodelingprep.com/stable/delisted-companies"
FMP_COLUMNS = ["symbol", "companyName", "exchange", "ipoDate", "delistedDate", "source"]


def _empty_metadata() -> pd.DataFrame:
    return empty_frame(FMP_COLUMNS)


def collect_fmp_delisted_metadata(
    raw_dir: Path = config.RAW_FMP_DIR,
    output_path: Path = config.FMP_DELISTED_METADATA_PATH,
    api_key: str | None = None,
    limit: int = 100,
    max_pages: int | None = None,
    sleep_seconds: float = 0.25,
) -> pd.DataFrame:
    load_local_env()
    api_key = api_key or os.getenv("FMP_API_KEY")
    if not api_key:
        result = _empty_metadata()
        write_parquet(result, output_path)
        print("[fmp] FMP_API_KEY not set; wrote empty metadata parquet and skipped.")
        return result

    import requests

    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    page = 0

    while True:
        if max_pages is not None and page >= max_pages:
            print(f"[fmp] Reached max_pages={max_pages}; stopping metadata collection.")
            break

        params = {"page": page, "limit": limit, "apikey": api_key}
        try:
            response = requests.get(FMP_ENDPOINT, params=params, timeout=60)
        except requests.RequestException as exc:
            print(f"[fmp] Request failed on page {page}; keeping partial metadata: {exc}")
            break

        if response.status_code in {401, 402, 403, 429}:
            print(f"[fmp] API limit/auth response {response.status_code} on page {page}; keeping partial metadata.")
            break
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            print(f"[fmp] HTTP error on page {page}; keeping partial metadata: {exc}")
            break

        payload = response.json()
        if not isinstance(payload, list) or not payload:
            break

        raw_path = raw_dir / f"delisted_companies_page_{page}.json"
        raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        for item in payload:
            rows.append(
                {
                    "symbol": normalize_symbol(item.get("symbol")),
                    "companyName": item.get("companyName"),
                    "exchange": item.get("exchange"),
                    "ipoDate": parse_date(item.get("ipoDate")),
                    "delistedDate": parse_date(item.get("delistedDate")),
                    "source": "fmp",
                }
            )

        if len(payload) < limit:
            break
        page += 1
        time.sleep(sleep_seconds)

    result = pd.DataFrame(rows, columns=FMP_COLUMNS) if rows else _empty_metadata()
    write_parquet(result, output_path)
    print(f"[fmp] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    collect_fmp_delisted_metadata()
