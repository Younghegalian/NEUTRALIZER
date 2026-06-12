from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, write_parquet


UNIVERSE_REASON = "close>=1; quality_adv20>=1000000; quality_traded_days_20>=15; has_next_open; not_price_quality_suspect"


def build_universe_df(
    liquidity_metrics: pd.DataFrame,
    universe_name: str = config.UNIVERSE_NAME,
) -> pd.DataFrame:
    if liquidity_metrics.empty:
        return empty_frame(config.UNIVERSE_COLUMNS)

    work = liquidity_metrics.copy()
    if "quality_adv20" not in work.columns:
        work["quality_adv20"] = work["adv20"]
    if "quality_traded_days_20" not in work.columns:
        work["quality_traded_days_20"] = work["traded_days_20"]
    if "is_price_quality_suspect" not in work.columns:
        work["is_price_quality_suspect"] = False

    for column in ["close", "quality_adv20", "quality_traded_days_20"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")

    eligible = (
        (work["close"] >= 1.00)
        & (work["quality_adv20"] >= 1_000_000)
        & (work["quality_traded_days_20"] >= 15)
        & (work["has_next_open"].fillna(False).astype(bool))
        & (work["is_price_quality_suspect"].fillna(False).astype(bool).eq(False))
    )
    result = work.loc[eligible, ["date", "symbol"]].copy()
    result["universe_name"] = universe_name
    result["reason"] = UNIVERSE_REASON
    result = result[config.UNIVERSE_COLUMNS].sort_values(["date", "symbol"]).reset_index(drop=True)
    return result


def build_universe(
    liquidity_metrics_path: Path = config.LIQUIDITY_METRICS_PATH,
    output_path: Path = config.UNIVERSE_MEMBERSHIP_PATH,
    universe_name: str = config.UNIVERSE_NAME,
) -> pd.DataFrame:
    liquidity_metrics = (
        pd.read_parquet(liquidity_metrics_path)
        if liquidity_metrics_path.exists()
        else empty_frame(config.LIQUIDITY_COLUMNS)
    )
    result = build_universe_df(liquidity_metrics, universe_name=universe_name)
    write_parquet(result, output_path)
    print(f"[universe] Wrote {len(result):,} memberships to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    build_universe()
