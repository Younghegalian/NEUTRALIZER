from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.normalize.build_symbol_master import build_symbol_master_df
from src.normalize.deduplicate_prices import deduplicate_prices_df
from src.utils import (
    coerce_numeric,
    empty_frame,
    normalize_symbol,
    parse_date,
    read_parquet_if_exists,
    write_parquet,
)


NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "adjusted_close"]


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in config.CANONICAL_PRICE_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
    return out[config.CANONICAL_PRICE_COLUMNS]


def clean_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return empty_frame(config.CANONICAL_PRICE_COLUMNS)

    out = _ensure_columns(df)
    out["date"] = out["date"].map(parse_date)
    out["symbol"] = out["symbol"].map(normalize_symbol)
    out["vendor_symbol"] = out["vendor_symbol"].astype("string")
    out["source"] = out["source"].astype("string")
    out["is_delisted_source"] = out["is_delisted_source"].fillna(False).astype(bool)
    for column in NUMERIC_COLUMNS:
        out[column] = coerce_numeric(out[column])
    return out


def _row_reasons(row: pd.Series) -> list[str]:
    reasons: list[str] = []

    if pd.isna(row["date"]):
        reasons.append("date is null")
    if pd.isna(row["symbol"]):
        reasons.append("symbol is null")
    if pd.isna(row["close"]):
        reasons.append("close is null")

    for column in ["open", "high", "low", "close"]:
        if pd.isna(row[column]):
            reasons.append(f"{column} is null")
        elif row[column] <= 0:
            reasons.append(f"{column} <= 0")

    if not pd.isna(row["volume"]) and row["volume"] < 0:
        reasons.append("volume < 0")

    if not pd.isna(row["high"]) and not pd.isna(row["low"]) and row["high"] < row["low"]:
        reasons.append("high < low")

    if not pd.isna(row["open"]) and not pd.isna(row["high"]) and row["open"] > row["high"] * 1.5:
        reasons.append("open > high * 1.5")
    if not pd.isna(row["open"]) and not pd.isna(row["low"]) and row["open"] < row["low"] * 0.5:
        reasons.append("open < low * 0.5")
    if not pd.isna(row["close"]) and not pd.isna(row["high"]) and row["close"] > row["high"] * 1.5:
        reasons.append("close > high * 1.5")
    if not pd.isna(row["close"]) and not pd.isna(row["low"]) and row["close"] < row["low"] * 0.5:
        reasons.append("close < low * 0.5")

    return reasons


def split_bad_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        bad = empty_frame(config.CANONICAL_PRICE_COLUMNS + ["bad_reason"])
        return df.copy(), bad

    masks = {
        "date is null": df["date"].isna(),
        "symbol is null": df["symbol"].isna(),
        "close is null": df["close"].isna(),
        "open is null": df["open"].isna(),
        "high is null": df["high"].isna(),
        "low is null": df["low"].isna(),
        "open <= 0": df["open"].le(0),
        "high <= 0": df["high"].le(0),
        "low <= 0": df["low"].le(0),
        "close <= 0": df["close"].le(0),
        "volume < 0": df["volume"].lt(0),
        "high < low": df["high"].lt(df["low"]),
        "open > high * 1.5": df["open"].gt(df["high"] * 1.5),
        "open < low * 0.5": df["open"].lt(df["low"] * 0.5),
        "close > high * 1.5": df["close"].gt(df["high"] * 1.5),
        "close < low * 0.5": df["close"].lt(df["low"] * 0.5),
    }
    bad_mask = pd.Series(False, index=df.index)
    for mask in masks.values():
        bad_mask |= mask.fillna(False)

    bad = df.loc[bad_mask].copy()
    bad["bad_reason"] = ""
    for reason, mask in masks.items():
        affected = bad.index.intersection(mask[mask.fillna(False)].index)
        if len(affected) > 0:
            current = bad.loc[affected, "bad_reason"].astype(str)
            bad.loc[affected, "bad_reason"] = current.where(current.eq(""), current + "; ") + reason

    good = df.loc[~bad_mask].copy()
    return good, bad


def normalize_price_frame(
    frames: list[pd.DataFrame],
    start_date: object | None = None,
    end_date: object | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if frames:
        combined = pd.concat([clean_price_frame(frame) for frame in frames], ignore_index=True)
    else:
        combined = empty_frame(config.CANONICAL_PRICE_COLUMNS)

    if start_date is not None and not combined.empty:
        start_ts = pd.Timestamp(start_date)
        combined = combined[combined["date"] >= start_ts]
    if end_date is not None and not combined.empty:
        end_ts = pd.Timestamp(end_date)
        combined = combined[combined["date"] <= end_ts]

    good, bad = split_bad_rows(combined)
    selected, duplicate_report = deduplicate_prices_df(good)

    if not selected.empty:
        selected["date"] = pd.to_datetime(selected["date"]).dt.normalize()
        selected["volume"] = selected["volume"].round().astype("Int64")
        selected = selected[config.CANONICAL_PRICE_COLUMNS]

    symbol_master = build_symbol_master_df(selected)
    return selected, symbol_master, duplicate_report, bad


def normalize_prices(
    staging_paths: list[Path] | None = None,
    start_date: object | None = None,
    end_date: object | None = None,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    duplicate_report_path: Path = config.DUPLICATE_REPORT_PATH,
    bad_rows_report_path: Path = config.BAD_ROWS_REPORT_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    staging_paths = staging_paths or [
        config.STOOQ_STAGING_PATH,
        config.YAHOO_FALLBACK_STAGING_PATH,
        config.YAHOO_DELISTED_PROBE_STAGING_PATH,
        config.KAGGLE_DELISTED_STAGING_PATH,
    ]
    frames = [read_parquet_if_exists(path, config.CANONICAL_PRICE_COLUMNS) for path in staging_paths]
    daily_prices, symbol_master, duplicate_report, bad_rows = normalize_price_frame(
        frames, start_date=start_date, end_date=end_date
    )

    write_parquet(daily_prices, daily_prices_path)
    write_parquet(symbol_master, symbol_master_path)
    write_parquet(duplicate_report, duplicate_report_path)
    write_parquet(bad_rows, bad_rows_report_path)

    print(f"[normalize] Wrote {len(daily_prices):,} canonical daily price rows to {daily_prices_path}")
    print(f"[normalize] Wrote {len(symbol_master):,} symbol rows to {symbol_master_path}")
    print(f"[normalize] Wrote {len(duplicate_report):,} duplicate groups to {duplicate_report_path}")
    print(f"[normalize] Wrote {len(bad_rows):,} rejected rows to {bad_rows_report_path}")
    return daily_prices, symbol_master


if __name__ == "__main__":
    config.ensure_directories()
    normalize_prices()
