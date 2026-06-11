from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, write_parquet


ACTIVE_SOURCES = {"stooq", "yahoo_fallback"}
DELISTED_SOURCES = {"kaggle_arandkei_delisted", "yahoo_delisted_probe"}


def _join_unique(values: pd.Series) -> str:
    return ",".join(sorted({str(value) for value in values.dropna()}))


def build_symbol_master_df(daily_prices: pd.DataFrame) -> pd.DataFrame:
    if daily_prices.empty:
        return empty_frame(config.SYMBOL_MASTER_COLUMNS)

    work = daily_prices.copy()
    grouped = work.groupby("symbol", as_index=False)
    result = grouped.agg(
        vendor_symbol=("vendor_symbol", _join_unique),
        first_date=("date", "min"),
        last_date=("date", "max"),
        source_list=("source", _join_unique),
        observation_count=("date", "count"),
    )

    source_sets = work.groupby("symbol")["source"].agg(lambda s: set(s.dropna()))
    result["has_active_source"] = result["symbol"].map(
        lambda sym: bool(set(source_sets[sym]) & ACTIVE_SOURCES)
    )
    result["has_delisted_source"] = result["symbol"].map(
        lambda sym: bool(set(source_sets[sym]) & DELISTED_SOURCES)
    )
    result = result[config.SYMBOL_MASTER_COLUMNS].sort_values("symbol").reset_index(drop=True)
    return result


def build_symbol_master(
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    output_path: Path = config.SYMBOL_MASTER_PATH,
) -> pd.DataFrame:
    daily_prices = pd.read_parquet(daily_prices_path) if daily_prices_path.exists() else empty_frame(config.CANONICAL_PRICE_COLUMNS)
    result = build_symbol_master_df(daily_prices)
    write_parquet(result, output_path)
    print(f"[symbol_master] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    build_symbol_master()
