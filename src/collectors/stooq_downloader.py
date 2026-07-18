from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

from src import config
from src.utils import (
    coerce_numeric,
    empty_frame,
    first_present,
    normalize_column_name,
    normalize_symbol,
    parse_date,
    write_parquet,
)


STOOQ_DAILY_US_URL = "https://stooq.com/db/h/d_us_txt.zip"

DATE_COLUMNS = ["date", "datetime", "timestamp", "time"]
OPEN_COLUMNS = ["open", "o"]
HIGH_COLUMNS = ["high", "h"]
LOW_COLUMNS = ["low", "l"]
CLOSE_COLUMNS = ["close", "c"]
VOLUME_COLUMNS = ["volume", "vol", "v"]


def _yyyymmdd(value: date | None) -> str | None:
    return value.strftime("%Y%m%d") if value else None


def stooq_vendor_symbol(symbol: str) -> str:
    return f"{symbol.lower()}.us"


def stooq_vendor_symbol_candidates(symbol: str) -> list[str]:
    base = symbol.strip().upper()
    candidates = [stooq_vendor_symbol(base)]
    if "." in base:
        candidates.append(stooq_vendor_symbol(base.replace(".", "-")))
    if "-" in base:
        candidates.append(stooq_vendor_symbol(base.replace("-", ".")))
    return list(dict.fromkeys(candidates))


def download_stooq_archive(
    raw_dir: Path = config.RAW_STOOQ_DIR,
    url: str = STOOQ_DAILY_US_URL,
    force: bool = False,
) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / Path(url).name
    if archive_path.exists():
        print(f"[stooq] Using existing archive {archive_path}")
        return archive_path

    raise FileNotFoundError(
        "Automatic Stooq downloads are disabled for the open-source pipeline. "
        f"If your Stooq terms allow it, place {archive_path.name} or extracted txt/csv files under {raw_dir}."
    )


def extract_stooq_archive(archive_path: Path, raw_dir: Path = config.RAW_STOOQ_DIR) -> Path:
    extract_dir = raw_dir / archive_path.stem
    if extract_dir.exists() and any(extract_dir.rglob("*")):
        return extract_dir

    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as zf:
        zf.extractall(extract_dir)
    return extract_dir


def _read_price_file(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.read_csv(path, sep=None, engine="python")


def normalize_stooq_file(path: Path) -> pd.DataFrame:
    raw = _read_price_file(path)
    if raw.empty:
        return empty_frame(config.CANONICAL_PRICE_COLUMNS)

    raw = raw.copy()
    raw.columns = [normalize_column_name(col) for col in raw.columns]

    date_col = first_present(raw.columns, DATE_COLUMNS)
    open_col = first_present(raw.columns, OPEN_COLUMNS)
    high_col = first_present(raw.columns, HIGH_COLUMNS)
    low_col = first_present(raw.columns, LOW_COLUMNS)
    close_col = first_present(raw.columns, CLOSE_COLUMNS)
    volume_col = first_present(raw.columns, VOLUME_COLUMNS)

    if not all([date_col, open_col, high_col, low_col, close_col]):
        missing = [
            name
            for name, col in [
                ("date", date_col),
                ("open", open_col),
                ("high", high_col),
                ("low", low_col),
                ("close", close_col),
            ]
            if col is None
        ]
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")

    vendor_symbol = path.stem
    symbol = normalize_symbol(vendor_symbol)
    out = pd.DataFrame(
        {
            "date": raw[date_col].map(parse_date),
            "symbol": symbol,
            "vendor_symbol": vendor_symbol,
            "open": coerce_numeric(raw[open_col]),
            "high": coerce_numeric(raw[high_col]),
            "low": coerce_numeric(raw[low_col]),
            "close": coerce_numeric(raw[close_col]),
            "volume": coerce_numeric(raw[volume_col]) if volume_col else pd.NA,
            "adjusted_close": pd.NA,
            "source": "stooq",
            "is_delisted_source": False,
        }
    )
    return out[config.CANONICAL_PRICE_COLUMNS]


def normalize_stooq_directory(
    raw_dir: Path = config.RAW_STOOQ_DIR,
    output_path: Path = config.STOOQ_STAGING_PATH,
) -> pd.DataFrame:
    paths = sorted(list(raw_dir.rglob("*.txt")) + list(raw_dir.rglob("*.csv")))
    frames: list[pd.DataFrame] = []
    for path in paths:
        if path.name.startswith("."):
            continue
        try:
            frames.append(normalize_stooq_file(path))
        except Exception as exc:
            print(f"[stooq] Skipping {path}: {exc}")

    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = empty_frame(config.CANONICAL_PRICE_COLUMNS)

    write_parquet(result, output_path)
    print(f"[stooq] Wrote {len(result):,} rows to {output_path}")
    return result


def collect_stooq(
    raw_dir: Path = config.RAW_STOOQ_DIR,
    output_path: Path = config.STOOQ_STAGING_PATH,
    download: bool = True,
    force_download: bool = False,
    url: str = STOOQ_DAILY_US_URL,
    start_date: date | None = None,
    end_date: date | None = None,
    enable_html_fallback: bool = False,
) -> pd.DataFrame:
    if download:
        try:
            archive_path = download_stooq_archive(raw_dir=raw_dir, url=url, force=force_download)
            extract_stooq_archive(archive_path, raw_dir=raw_dir)
        except Exception as exc:
            if enable_html_fallback:
                print("[stooq] HTML fallback is disabled in the open-source pipeline.")
            print(f"[stooq] Local archive unavailable ({exc}); continuing without Stooq bulk data.")
    return normalize_stooq_directory(raw_dir=raw_dir, output_path=output_path)


if __name__ == "__main__":
    config.ensure_directories()
    collect_stooq()
