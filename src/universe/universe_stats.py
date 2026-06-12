from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, write_parquet


def build_universe_stats_df(
    universe_membership: pd.DataFrame,
    liquidity_metrics: pd.DataFrame,
    daily_prices: pd.DataFrame,
) -> pd.DataFrame:
    if universe_membership.empty:
        return empty_frame(config.UNIVERSE_STATS_COLUMNS)

    membership = universe_membership.copy()
    liquidity = liquidity_metrics.copy()
    prices = daily_prices.copy()

    for frame in [membership, liquidity, prices]:
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")

    merged = membership.merge(liquidity, on=["date", "symbol"], how="left")
    if "is_delisted_source" in prices.columns:
        source_flags = prices[["date", "symbol", "is_delisted_source"]].copy()
        merged = merged.merge(source_flags, on=["date", "symbol"], how="left")
    else:
        merged["is_delisted_source"] = False

    merged["is_delisted_source"] = merged["is_delisted_source"].fillna(False).astype(bool)
    if "quality_adv20" not in merged.columns:
        merged["quality_adv20"] = merged["adv20"]
    if "quality_dollar_volume" not in merged.columns:
        merged["quality_dollar_volume"] = merged["dollar_volume"]
    result = (
        merged.groupby(["date", "universe_name"], as_index=False)
        .agg(
            symbol_count=("symbol", "nunique"),
            median_close=("close", "median"),
            median_adv20=("quality_adv20", "median"),
            total_dollar_volume=("quality_dollar_volume", "sum"),
            delisted_source_count=("is_delisted_source", "sum"),
        )
        .sort_values(["date", "universe_name"])
        .reset_index(drop=True)
    )
    result["date"] = result["date"].dt.normalize()
    result["delisted_source_count"] = result["delisted_source_count"].astype("Int64")
    result["symbol_count"] = result["symbol_count"].astype("Int64")
    return result[config.UNIVERSE_STATS_COLUMNS]


def build_universe_stats(
    universe_membership_path: Path = config.UNIVERSE_MEMBERSHIP_PATH,
    liquidity_metrics_path: Path = config.LIQUIDITY_METRICS_PATH,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    output_path: Path = config.UNIVERSE_STATS_PATH,
) -> pd.DataFrame:
    membership = (
        pd.read_parquet(universe_membership_path)
        if universe_membership_path.exists()
        else empty_frame(config.UNIVERSE_COLUMNS)
    )
    liquidity = (
        pd.read_parquet(liquidity_metrics_path)
        if liquidity_metrics_path.exists()
        else empty_frame(config.LIQUIDITY_COLUMNS)
    )
    prices = (
        pd.read_parquet(daily_prices_path)
        if daily_prices_path.exists()
        else empty_frame(config.CANONICAL_PRICE_COLUMNS)
    )
    result = build_universe_stats_df(membership, liquidity, prices)
    write_parquet(result, output_path)
    print(f"[universe_stats] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    build_universe_stats()
