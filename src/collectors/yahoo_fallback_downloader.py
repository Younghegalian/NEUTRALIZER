from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from src import config
from src.collectors.active_symbols import active_symbol_list
from src.utils import empty_frame, normalize_symbol, write_parquet


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
YAHOO_ALLOWED_INSTRUMENT_TYPES = {"EQUITY", "ETF"}
YAHOO_ALLOWED_CURRENCIES = {"USD"}


def _unix_day(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp())


def yahoo_query_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def _parse_chart_payload(
    query_symbol: str,
    payload: dict,
    internal_symbol: str | None = None,
    source: str = "yahoo_fallback",
    is_delisted_source: bool = False,
) -> pd.DataFrame:
    chart = payload.get("chart", {})
    results = chart.get("result") or []
    if not results:
        return empty_frame(config.CANONICAL_PRICE_COLUMNS)

    result = results[0]
    meta = result.get("meta", {})
    instrument_type = str(meta.get("instrumentType") or "").upper()
    currency = str(meta.get("currency") or "").upper()
    if instrument_type not in YAHOO_ALLOWED_INSTRUMENT_TYPES or currency not in YAHOO_ALLOWED_CURRENCIES:
        return empty_frame(config.CANONICAL_PRICE_COLUMNS)

    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjclose = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")

    dates = [pd.to_datetime(ts, unit="s", utc=True).tz_convert(None).normalize() for ts in timestamps]
    n = len(dates)
    adjusted_close = adjclose if adjclose is not None else [pd.NA] * n
    vendor_symbol = query_symbol.upper()

    out = pd.DataFrame(
        {
            "date": dates,
            "symbol": normalize_symbol(internal_symbol or query_symbol),
            "vendor_symbol": vendor_symbol,
            "open": quote.get("open", [pd.NA] * n),
            "high": quote.get("high", [pd.NA] * n),
            "low": quote.get("low", [pd.NA] * n),
            "close": quote.get("close", [pd.NA] * n),
            "volume": quote.get("volume", [pd.NA] * n),
            "adjusted_close": adjusted_close,
            "source": source,
            "is_delisted_source": is_delisted_source,
        }
    )
    return out[config.CANONICAL_PRICE_COLUMNS]


def _download_one_yahoo(
    raw_symbol: str,
    start_date: date,
    end_date: date,
    raw_dir: Path,
    source: str = "yahoo_fallback",
    is_delisted_source: bool = False,
    force: bool = False,
) -> pd.DataFrame:
    import requests

    internal_symbol = normalize_symbol(raw_symbol)
    if not internal_symbol:
        return empty_frame(config.CANONICAL_PRICE_COLUMNS)

    query_symbol = yahoo_query_symbol(internal_symbol)
    raw_path = raw_dir / f"{query_symbol}.json"
    if raw_path.exists() and raw_path.stat().st_size > 0 and not force:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        url = YAHOO_CHART_URL.format(symbol=query_symbol)
        params = {
            "period1": _unix_day(start_date),
            "period2": _unix_day(end_date),
            "interval": "1d",
            "includeAdjustedClose": "true",
            "events": "div,splits",
        }
        response = None
        for attempt in range(4):
            response = requests.get(url, params=params, headers=YAHOO_HEADERS, timeout=(5, 30))
            if response.status_code != 429:
                break
            time.sleep(2 * (attempt + 1))
        assert response is not None
        if response.status_code in {404, 410}:
            return empty_frame(config.CANONICAL_PRICE_COLUMNS)
        response.raise_for_status()
        payload = response.json()
        raw_path.write_text(json.dumps(payload), encoding="utf-8")

    return _parse_chart_payload(
        query_symbol,
        payload,
        internal_symbol=internal_symbol,
        source=source,
        is_delisted_source=is_delisted_source,
    )


def collect_yahoo_fallback(
    symbols: Iterable[str],
    start_date: date,
    end_date: date,
    raw_dir: Path = config.RAW_YAHOO_DIR,
    output_path: Path = config.YAHOO_FALLBACK_STAGING_PATH,
    sleep_seconds: float = 0.5,
    force: bool = False,
) -> pd.DataFrame:
    raw_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []

    for raw_symbol in symbols:
        symbol = normalize_symbol(raw_symbol)
        if not symbol:
            continue

        frames.append(_download_one_yahoo(symbol, start_date, end_date, raw_dir, force=force))
        time.sleep(sleep_seconds)

    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = empty_frame(config.CANONICAL_PRICE_COLUMNS)

    write_parquet(result, output_path)
    print(f"[yahoo_fallback] Wrote {len(result):,} rows to {output_path}")
    return result


def collect_yahoo_active(
    start_date: date,
    end_date: date,
    raw_dir: Path = config.RAW_YAHOO_DIR,
    output_path: Path = config.YAHOO_FALLBACK_STAGING_PATH,
    max_workers: int = 12,
    limit: int | None = None,
    force: bool = False,
) -> pd.DataFrame:
    raw_dir.mkdir(parents=True, exist_ok=True)
    symbols = active_symbol_list(include_etfs=True, liquid_equity_like=True)
    if limit is not None:
        symbols = symbols[:limit]

    print(f"[yahoo_active] Collecting {len(symbols):,} active symbols from Yahoo chart API")
    frames: list[pd.DataFrame] = []
    failures = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_download_one_yahoo, symbol, start_date, end_date, raw_dir, force=force): symbol
            for symbol in symbols
        }
        for idx, future in enumerate(as_completed(futures), start=1):
            symbol = futures[future]
            try:
                frame = future.result()
                if frame.empty:
                    failures += 1
                else:
                    frames.append(frame)
            except Exception as exc:
                failures += 1
                if failures <= 25 or failures % 250 == 0:
                    print(f"[yahoo_active] {symbol} failed: {exc}")

            if idx % 250 == 0 or idx == len(symbols):
                elapsed = max(time.time() - started, 1)
                rows = sum(len(frame) for frame in frames)
                print(
                    f"[yahoo_active] {idx:,}/{len(symbols):,} done "
                    f"({len(frames):,} symbols ok, {failures:,} missing/failed, {rows:,} rows, {idx / elapsed:.2f} symbols/sec)"
                )

    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = empty_frame(config.CANONICAL_PRICE_COLUMNS)

    write_parquet(result, output_path)
    print(f"[yahoo_active] Wrote {len(result):,} rows to {output_path}")
    return result


def collect_yahoo_delisted_probe(
    start_date: date,
    end_date: date,
    candidates_path: Path = config.SEC_DELISTED_CANDIDATES_PATH,
    raw_dir: Path = config.RAW_YAHOO_DIR / "delisted_probe",
    output_path: Path = config.YAHOO_DELISTED_PROBE_STAGING_PATH,
    coverage_path: Path = config.YAHOO_DELISTED_COVERAGE_PATH,
    max_workers: int = 6,
    limit: int | None = None,
    exclude_active_symbols: bool = True,
    force: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not candidates_path.exists():
        raise FileNotFoundError(f"Missing SEC candidates: {candidates_path}")

    raw_dir.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_parquet(candidates_path)
    candidates = candidates[candidates["candidate_symbol"].notna()].copy()
    candidates["candidate_symbol"] = candidates["candidate_symbol"].map(normalize_symbol)
    candidates = candidates[candidates["candidate_symbol"].notna()]

    if exclude_active_symbols and config.SYMBOL_MASTER_PATH.exists():
        symbol_master = pd.read_parquet(config.SYMBOL_MASTER_PATH, columns=["symbol", "has_active_source"])
        active_symbols = set(symbol_master.loc[symbol_master["has_active_source"].fillna(False), "symbol"])
        before = candidates["candidate_symbol"].nunique()
        candidates = candidates[~candidates["candidate_symbol"].isin(active_symbols)]
        after = candidates["candidate_symbol"].nunique()
        print(f"[yahoo_delisted_probe] Excluded {before - after:,} symbols already covered by active source")

    summary = (
        candidates.sort_values(["candidate_symbol", "date_filed"])
        .groupby("candidate_symbol", as_index=False)
        .agg(
            cik=("cik", "first"),
            company_name=("company_name", "first"),
            first_delisting_filing=("date_filed", "min"),
            last_delisting_filing=("date_filed", "max"),
            filing_count=("filename", "nunique"),
            ticker_sources=("ticker_source", lambda s: ",".join(sorted({str(x) for x in s.dropna()}))),
        )
        .sort_values("candidate_symbol")
    )
    if limit is not None:
        summary = summary.head(limit)

    print(f"[yahoo_delisted_probe] Probing {len(summary):,} SEC candidate symbols")
    frames: list[pd.DataFrame] = []
    coverage_rows: list[dict] = []
    started = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _download_one_yahoo,
                row.candidate_symbol,
                start_date,
                end_date,
                raw_dir,
                "yahoo_delisted_probe",
                True,
                force,
            ): row
            for row in summary.itertuples(index=False)
        }
        for idx, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            try:
                frame = future.result()
                if frame.empty:
                    status = "no_data"
                    min_date = max_date = None
                    row_count = 0
                else:
                    status = "ok"
                    frames.append(frame)
                    min_date = pd.to_datetime(frame["date"]).min()
                    max_date = pd.to_datetime(frame["date"]).max()
                    row_count = len(frame)
                coverage_rows.append(
                    {
                        "symbol": row.candidate_symbol,
                        "cik": row.cik,
                        "company_name": row.company_name,
                        "first_delisting_filing": row.first_delisting_filing,
                        "last_delisting_filing": row.last_delisting_filing,
                        "filing_count": row.filing_count,
                        "ticker_sources": row.ticker_sources,
                        "status": status,
                        "row_count": row_count,
                        "first_price_date": min_date,
                        "last_price_date": max_date,
                        "error": None,
                    }
                )
            except Exception as exc:
                coverage_rows.append(
                    {
                        "symbol": row.candidate_symbol,
                        "cik": row.cik,
                        "company_name": row.company_name,
                        "first_delisting_filing": row.first_delisting_filing,
                        "last_delisting_filing": row.last_delisting_filing,
                        "filing_count": row.filing_count,
                        "ticker_sources": row.ticker_sources,
                        "status": "error",
                        "row_count": 0,
                        "first_price_date": None,
                        "last_price_date": None,
                        "error": str(exc)[:500],
                    }
                )

            if idx % 250 == 0 or idx == len(summary):
                elapsed = max(time.time() - started, 1)
                ok = sum(1 for r in coverage_rows if r["status"] == "ok")
                rows = sum(r["row_count"] for r in coverage_rows)
                print(
                    f"[yahoo_delisted_probe] {idx:,}/{len(summary):,} done "
                    f"({ok:,} ok, {rows:,} rows, {idx / elapsed:.2f} symbols/sec)"
                )

    prices = pd.concat(frames, ignore_index=True) if frames else empty_frame(config.CANONICAL_PRICE_COLUMNS)
    coverage = pd.DataFrame(coverage_rows)
    write_parquet(prices, output_path)
    write_parquet(coverage, coverage_path)
    print(f"[yahoo_delisted_probe] Wrote {len(prices):,} rows to {output_path}")
    print(f"[yahoo_delisted_probe] Wrote coverage report to {coverage_path}")
    return prices, coverage
