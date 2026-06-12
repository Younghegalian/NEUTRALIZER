from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

import pandas as pd

from src import config
from src.collectors.sec_delisting_collector import SEC_COMPANY_TICKERS_EXCHANGE_URL, SEC_HEADERS
from src.utils import empty_frame, normalize_symbol, read_parquet_if_exists, write_parquet


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_SUBMISSIONS_BULK_URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
SEC_COMPANY_METADATA_COLUMNS = [
    "symbol",
    "cik",
    "sec_company_name",
    "sec_exchange",
    "sec_entity_type",
    "sic",
    "sic_description",
    "sic_sector",
    "fiscal_year_end",
    "sec_ticker_source",
    "cik_candidate_count",
    "source",
]


def _empty_metadata() -> pd.DataFrame:
    return empty_frame(SEC_COMPANY_METADATA_COLUMNS)


def _request_json(url: str, sleep_seconds: float = 0.12) -> object:
    import requests

    response = requests.get(url, headers=SEC_HEADERS, timeout=(5, 60))
    response.raise_for_status()
    time.sleep(sleep_seconds)
    return response.json()


def _clean_text(value: object) -> object:
    if value is None or pd.isna(value):
        return pd.NA
    text = str(value).strip()
    return text if text else pd.NA


def _sic_to_sector(sic: object, description: object = None) -> object:
    code = pd.to_numeric(sic, errors="coerce")
    if pd.isna(code):
        return pd.NA
    code = int(code)
    desc = "" if description is None or pd.isna(description) else str(description).lower()

    if 100 <= code <= 999:
        return "Consumer Defensive"
    if 1000 <= code <= 1299:
        return "Basic Materials"
    if 1300 <= code <= 1399:
        return "Energy"
    if 1400 <= code <= 1499:
        return "Basic Materials"
    if 1500 <= code <= 1799:
        return "Industrials"
    if 2000 <= code <= 2199:
        return "Consumer Defensive"
    if 2200 <= code <= 2599:
        return "Consumer Cyclical"
    if 2600 <= code <= 2699:
        return "Basic Materials"
    if 2700 <= code <= 2799:
        return "Communication Services"
    if 2800 <= code <= 2829:
        return "Basic Materials"
    if 2830 <= code <= 2839:
        return "Healthcare"
    if 2840 <= code <= 2899:
        return "Basic Materials"
    if 2900 <= code <= 2999:
        return "Energy"
    if 3000 <= code <= 3499:
        return "Industrials"
    if 3500 <= code <= 3569:
        return "Industrials"
    if 3570 <= code <= 3579:
        return "Technology"
    if 3580 <= code <= 3599:
        return "Industrials"
    if 3600 <= code <= 3699:
        return "Technology"
    if 3700 <= code <= 3719:
        return "Consumer Cyclical"
    if 3720 <= code <= 3799:
        return "Industrials"
    if 3800 <= code <= 3839:
        return "Technology"
    if 3840 <= code <= 3859:
        return "Healthcare"
    if 3860 <= code <= 3899:
        return "Technology"
    if 3900 <= code <= 3999:
        return "Consumer Cyclical"
    if 4000 <= code <= 4799:
        return "Industrials"
    if 4800 <= code <= 4899:
        return "Communication Services"
    if 4900 <= code <= 4999:
        return "Utilities"
    if 5000 <= code <= 5199:
        return "Industrials"
    if 5200 <= code <= 5399:
        return "Consumer Cyclical"
    if 5400 <= code <= 5499:
        return "Consumer Defensive"
    if 5500 <= code <= 5999:
        return "Consumer Cyclical"
    if 6000 <= code <= 6499:
        return "Financial Services"
    if 6500 <= code <= 6599:
        return "Real Estate"
    if 6600 <= code <= 6999:
        return "Financial Services"
    if 7000 <= code <= 7299:
        return "Consumer Cyclical"
    if 7300 <= code <= 7369:
        return "Industrials"
    if 7370 <= code <= 7379:
        return "Technology"
    if 7380 <= code <= 7399:
        return "Industrials"
    if 7800 <= code <= 7899:
        return "Communication Services"
    if 7900 <= code <= 7999:
        return "Consumer Cyclical"
    if 8000 <= code <= 8099:
        return "Healthcare"
    if 8100 <= code <= 8999:
        if "health" in desc or "medical" in desc:
            return "Healthcare"
        if "software" in desc or "computer" in desc or "data" in desc:
            return "Technology"
        return "Industrials"
    return pd.NA


def _current_sec_ticker_map() -> pd.DataFrame:
    payload = _request_json(SEC_COMPANY_TICKERS_EXCHANGE_URL)
    df = pd.DataFrame(payload["data"], columns=payload["fields"])
    df = df.rename(
        columns={
            "ticker": "symbol",
            "name": "mapped_company_name",
            "exchange": "mapped_exchange",
        }
    )
    df["cik"] = pd.to_numeric(df["cik"], errors="coerce").astype("Int64")
    df["symbol"] = df["symbol"].map(normalize_symbol)
    df["sec_ticker_source"] = "sec_company_tickers_exchange"
    return df[["symbol", "cik", "mapped_company_name", "mapped_exchange", "sec_ticker_source"]].dropna(
        subset=["symbol", "cik"]
    )


def _form345_ticker_map() -> pd.DataFrame:
    form345 = read_parquet_if_exists(config.SEC_FORM345_TICKER_MAP_PATH, ["cik", "symbol"])
    if form345.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "cik",
                "mapped_company_name",
                "mapped_exchange",
                "last_ticker_date",
                "sec_ticker_source",
            ]
        )
    form345["cik"] = pd.to_numeric(form345["cik"], errors="coerce").astype("Int64")
    form345["symbol"] = form345["symbol"].map(normalize_symbol)
    form345 = form345.rename(columns={"issuer_name": "mapped_company_name", "last_form345_date": "last_ticker_date"})
    form345["mapped_exchange"] = pd.NA
    form345["sec_ticker_source"] = "sec_form345"
    for column in ["mapped_company_name", "last_ticker_date"]:
        if column not in form345.columns:
            form345[column] = pd.NA
    return form345[
        ["symbol", "cik", "mapped_company_name", "mapped_exchange", "last_ticker_date", "sec_ticker_source"]
    ].dropna(subset=["symbol", "cik"])


def _delisted_candidate_ticker_map() -> pd.DataFrame:
    candidates = read_parquet_if_exists(config.SEC_DELISTED_CANDIDATES_PATH, ["cik", "candidate_symbol"])
    if candidates.empty or "candidate_symbol" not in candidates.columns:
        return pd.DataFrame(
            columns=[
                "symbol",
                "cik",
                "mapped_company_name",
                "mapped_exchange",
                "last_ticker_date",
                "sec_ticker_source",
            ]
        )
    candidates["cik"] = pd.to_numeric(candidates["cik"], errors="coerce").astype("Int64")
    candidates["symbol"] = candidates["candidate_symbol"].map(normalize_symbol)
    candidates = candidates.rename(
        columns={
            "company_name": "mapped_company_name",
            "exchange": "mapped_exchange",
            "date_filed": "last_ticker_date",
            "ticker_source": "sec_ticker_source",
        }
    )
    if "sec_ticker_source" not in candidates.columns:
        candidates["sec_ticker_source"] = "sec_delisted_candidates"
    else:
        candidates["sec_ticker_source"] = candidates["sec_ticker_source"].fillna("sec_delisted_candidates")
    for column in ["mapped_company_name", "mapped_exchange", "last_ticker_date"]:
        if column not in candidates.columns:
            candidates[column] = pd.NA
    return candidates[
        ["symbol", "cik", "mapped_company_name", "mapped_exchange", "last_ticker_date", "sec_ticker_source"]
    ].dropna(subset=["symbol", "cik"])


def _symbol_cik_map(symbol_master_path: Path) -> pd.DataFrame:
    symbol_master = read_parquet_if_exists(
        symbol_master_path,
        ["symbol", "has_active_source", "has_delisted_source"],
    )
    if not symbol_master.empty:
        symbol_master["symbol"] = symbol_master["symbol"].map(normalize_symbol)
        symbol_master = symbol_master[symbol_master["symbol"].notna()].drop_duplicates("symbol")

    frames = [_current_sec_ticker_map(), _form345_ticker_map(), _delisted_candidate_ticker_map()]
    mappings = pd.concat(frames, ignore_index=True, sort=False)
    mappings["symbol"] = mappings["symbol"].map(normalize_symbol)
    mappings = mappings.dropna(subset=["symbol", "cik"]).drop_duplicates(["symbol", "cik", "sec_ticker_source"])
    if not symbol_master.empty:
        mappings = mappings.merge(
            symbol_master[["symbol", "has_active_source", "has_delisted_source"]],
            on="symbol",
            how="inner",
        )
    else:
        mappings["has_active_source"] = False
        mappings["has_delisted_source"] = False
    mappings["cik_candidate_count"] = mappings.groupby("symbol")["cik"].transform("nunique")
    return mappings


def _submission_metadata(cik: int, payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {
            "cik": cik,
            "sec_company_name": pd.NA,
            "sec_entity_type": pd.NA,
            "sic": pd.NA,
            "sic_description": pd.NA,
            "sic_sector": pd.NA,
            "fiscal_year_end": pd.NA,
        }
    sic = pd.to_numeric(payload.get("sic"), errors="coerce")
    sic_value = pd.NA if pd.isna(sic) else int(sic)
    description = _clean_text(payload.get("sicDescription"))
    return {
        "cik": cik,
        "sec_company_name": _clean_text(payload.get("name")),
        "sec_entity_type": _clean_text(payload.get("entityType")),
        "sic": sic_value,
        "sic_description": description,
        "sic_sector": _sic_to_sector(sic_value, description),
        "fiscal_year_end": _clean_text(payload.get("fiscalYearEnd")),
    }


def _load_or_fetch_submission(
    cik: int,
    raw_dir: Path,
    can_fetch: bool,
    sleep_seconds: float,
) -> tuple[dict[str, object] | None, bool]:
    raw_path = raw_dir / f"CIK{cik:010d}.json"
    if raw_path.exists() and raw_path.stat().st_size > 0:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        return _submission_metadata(cik, payload), False
    if not can_fetch:
        return None, False
    payload = _request_json(SEC_SUBMISSIONS_URL.format(cik=cik), sleep_seconds=sleep_seconds)
    raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return _submission_metadata(cik, payload), True


def _download_bulk_submissions(raw_dir: Path, force: bool = False) -> Path:
    import requests

    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "submissions.zip"
    if zip_path.exists() and zip_path.stat().st_size > 0 and not force:
        return zip_path

    tmp_path = raw_dir / "submissions.zip.tmp"
    response = requests.get(SEC_SUBMISSIONS_BULK_URL, headers=SEC_HEADERS, stream=True, timeout=(5, 300))
    response.raise_for_status()
    total = int(response.headers.get("Content-Length") or 0)
    downloaded = 0
    next_report = 100 * 1024 * 1024
    with tmp_path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            fh.write(chunk)
            downloaded += len(chunk)
            if downloaded >= next_report:
                if total:
                    print(f"[sec_company] Downloaded SEC submissions bulk {downloaded / total:.1%}.")
                else:
                    print(f"[sec_company] Downloaded SEC submissions bulk {downloaded / 1024 / 1024:.0f} MB.")
                next_report += 100 * 1024 * 1024
    tmp_path.replace(zip_path)
    print(f"[sec_company] Downloaded SEC submissions bulk archive to {zip_path}")
    return zip_path


def _load_bulk_metadata(cik_values: list[int], raw_dir: Path, force_download: bool = False) -> list[dict[str, object]]:
    zip_path = _download_bulk_submissions(raw_dir, force=force_download)
    rows: list[dict[str, object]] = []
    missing = 0
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        for idx, cik in enumerate(cik_values, start=1):
            member = f"CIK{cik:010d}.json"
            if member not in names:
                missing += 1
                continue
            with zf.open(member) as fh:
                payload = json.loads(fh.read().decode("utf-8"))
            rows.append(_submission_metadata(cik, payload))
            if idx % 1000 == 0 or idx == len(cik_values):
                print(f"[sec_company] Parsed {len(rows):,}/{len(cik_values):,} CIKs from SEC bulk archive.")
    if missing:
        print(f"[sec_company] SEC bulk archive missing {missing:,} requested CIKs.")
    return rows


def _resolve_one_row_per_symbol(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_metadata()

    source_priority = {
        "sec_company_tickers_exchange": 0,
        "sec_form25_text": 1,
        "sec_delisted_candidates": 2,
        "sec_form345": 3,
    }
    df = df.copy()
    df["source_priority"] = df["sec_ticker_source"].map(source_priority).fillna(5)
    delisted_only = df["has_delisted_source"].fillna(False) & ~df["has_active_source"].fillna(False)
    df.loc[delisted_only & df["sec_ticker_source"].eq("sec_company_tickers_exchange"), "source_priority"] += 10
    df["missing_sic_priority"] = df["sic"].isna().astype(int)
    df["last_ticker_date"] = pd.to_datetime(df.get("last_ticker_date"), errors="coerce")
    df = df.sort_values(
        ["symbol", "missing_sic_priority", "source_priority", "last_ticker_date"],
        ascending=[True, True, True, False],
    )
    df = df.drop_duplicates("symbol", keep="first")
    df["sec_company_name"] = df.apply(
        lambda row: row.get("sec_company_name")
        if not pd.isna(row.get("sec_company_name"))
        else row.get("mapped_company_name"),
        axis=1,
    )
    df["sec_exchange"] = df["mapped_exchange"]
    df["source"] = "sec_submissions_sic"
    return df[SEC_COMPANY_METADATA_COLUMNS].sort_values("symbol").reset_index(drop=True)


def collect_sec_company_metadata(
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    raw_dir: Path = config.RAW_SEC_DIR / "submissions",
    output_path: Path = config.SEC_COMPANY_METADATA_PATH,
    limit: int | None = 0,
    sleep_seconds: float = 0.12,
    use_bulk: bool = False,
    force_bulk_download: bool = False,
) -> pd.DataFrame:
    """Collect SEC CIK/SIC metadata.

    limit is the maximum number of new SEC submissions requests. Cached submissions are always parsed.
    Set limit to a negative value for an uncapped catch-up run.
    """

    raw_dir.mkdir(parents=True, exist_ok=True)
    mappings = _symbol_cik_map(symbol_master_path)
    if mappings.empty:
        result = _empty_metadata()
        write_parquet(result, output_path)
        print(f"[sec_company] Wrote 0 rows to {output_path}")
        return result

    cik_values = sorted({int(cik) for cik in mappings["cik"].dropna().tolist()})
    fetched = 0
    failed = 0
    if use_bulk:
        rows = _load_bulk_metadata(cik_values, raw_dir=raw_dir, force_download=force_bulk_download)
    else:
        parsed = 0
        uncapped = limit is not None and limit < 0
        rows = []
        for idx, cik in enumerate(cik_values, start=1):
            can_fetch = uncapped or limit is None or fetched < limit
            try:
                row, did_fetch = _load_or_fetch_submission(
                    cik=cik,
                    raw_dir=raw_dir,
                    can_fetch=can_fetch,
                    sleep_seconds=sleep_seconds,
                )
            except Exception as exc:
                failed += 1
                if failed <= 10:
                    print(f"[sec_company] CIK {cik} request failed: {exc}")
                continue
            if row is None:
                continue
            rows.append(row)
            parsed += 1
            if did_fetch:
                fetched += 1
            if idx % 250 == 0 or idx == len(cik_values):
                print(f"[sec_company] Parsed {parsed:,}/{len(cik_values):,} CIKs ({fetched:,} new requests).")

    if not rows:
        result = _empty_metadata()
    else:
        metadata = pd.DataFrame(rows).drop_duplicates("cik")
        enriched = mappings.merge(metadata, on="cik", how="inner")
        result = _resolve_one_row_per_symbol(enriched)

    write_parquet(result, output_path)
    print(
        f"[sec_company] Wrote {len(result):,} symbol metadata rows to {output_path} "
        f"({fetched:,} new requests, {failed:,} failed)."
    )
    return result


if __name__ == "__main__":
    config.ensure_directories()
    collect_sec_company_metadata()
