from __future__ import annotations

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


DATE_COLUMNS = ["date", "datetime", "timestamp", "time"]
SYMBOL_COLUMNS = ["symbol", "ticker", "asset", "name"]
OPEN_COLUMNS = ["open", "o"]
HIGH_COLUMNS = ["high", "h"]
LOW_COLUMNS = ["low", "l"]
CLOSE_COLUMNS = ["close", "c", "adj_close", "adjusted_close"]
VOLUME_COLUMNS = ["volume", "vol", "v"]
ADJUSTED_CLOSE_COLUMNS = ["adjusted_close", "adj_close", "adjclose"]


def infer_symbol_from_filename(path: Path) -> str:
    stem = path.name
    while stem.lower().endswith(".csv"):
        stem = stem[:-4]
    return stem.split("_", 1)[0]


def _valid_symbol_value(value: object) -> bool:
    symbol = normalize_symbol(value)
    if not symbol:
        return False
    return not symbol.isdigit()


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin1")


def _canonicalize_raw_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [normalize_column_name(col) for col in out.columns]
    return out


def normalize_kaggle_file(path: Path) -> pd.DataFrame:
    raw = _canonicalize_raw_columns(_read_csv(path))
    if raw.empty:
        return empty_frame(config.CANONICAL_PRICE_COLUMNS)

    date_col = first_present(raw.columns, DATE_COLUMNS)
    open_col = first_present(raw.columns, OPEN_COLUMNS)
    high_col = first_present(raw.columns, HIGH_COLUMNS)
    low_col = first_present(raw.columns, LOW_COLUMNS)
    close_col = first_present(raw.columns, CLOSE_COLUMNS)
    volume_col = first_present(raw.columns, VOLUME_COLUMNS)
    adjusted_close_col = first_present(raw.columns, ADJUSTED_CLOSE_COLUMNS)
    symbol_col = first_present(raw.columns, SYMBOL_COLUMNS)

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

    vendor_symbol = infer_symbol_from_filename(path)
    if symbol_col is not None:
        vendor_symbols = raw[symbol_col].where(raw[symbol_col].map(_valid_symbol_value), vendor_symbol)
    else:
        vendor_symbols = pd.Series([vendor_symbol] * len(raw), index=raw.index)

    out = pd.DataFrame(
        {
            "date": raw[date_col].map(parse_date),
            "symbol": vendor_symbols.map(normalize_symbol),
            "vendor_symbol": vendor_symbols.astype(str),
            "open": coerce_numeric(raw[open_col]),
            "high": coerce_numeric(raw[high_col]),
            "low": coerce_numeric(raw[low_col]),
            "close": coerce_numeric(raw[close_col]),
            "volume": coerce_numeric(raw[volume_col]) if volume_col else pd.NA,
            "adjusted_close": coerce_numeric(raw[adjusted_close_col]) if adjusted_close_col else pd.NA,
            "source": "kaggle_arandkei_delisted",
            "is_delisted_source": True,
        }
    )
    return out[config.CANONICAL_PRICE_COLUMNS]


def load_kaggle_delisted(
    raw_dir: Path = config.RAW_KAGGLE_DELISTED_DIR,
    output_path: Path = config.KAGGLE_DELISTED_STAGING_PATH,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    csv_paths = sorted(raw_dir.rglob("*.csv"))

    for path in csv_paths:
        try:
            frames.append(normalize_kaggle_file(path))
        except Exception as exc:
            print(f"[kaggle_delisted] Skipping {path}: {exc}")

    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = empty_frame(config.CANONICAL_PRICE_COLUMNS)

    write_parquet(result, output_path)
    print(f"[kaggle_delisted] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    load_kaggle_delisted()
