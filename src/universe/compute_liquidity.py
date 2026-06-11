from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, write_parquet


def compute_liquidity_metrics_df(daily_prices: pd.DataFrame) -> pd.DataFrame:
    if daily_prices.empty:
        return empty_frame(config.LIQUIDITY_COLUMNS)

    work = daily_prices.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    for column in ["open", "close", "volume"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")

    work = work.sort_values(["symbol", "date"]).reset_index(drop=True)
    work["dollar_volume"] = work["close"] * work["volume"]
    grouped = work.groupby("symbol", group_keys=False)
    work["adv20"] = grouped["dollar_volume"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    work["traded_days_20"] = grouped["volume"].transform(
        lambda s: s.gt(0).rolling(20, min_periods=1).sum()
    )
    work["next_open"] = grouped["open"].shift(-1)
    work["has_next_open"] = work["next_open"].notna()

    result = work[
        [
            "date",
            "symbol",
            "close",
            "volume",
            "dollar_volume",
            "adv20",
            "traded_days_20",
            "next_open",
            "has_next_open",
        ]
    ].copy()
    result["date"] = result["date"].dt.normalize()
    result["volume"] = result["volume"].round().astype("Int64")
    result["traded_days_20"] = result["traded_days_20"].round().astype("Int64")
    return result[config.LIQUIDITY_COLUMNS]


def compute_liquidity(
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    output_path: Path = config.LIQUIDITY_METRICS_PATH,
) -> pd.DataFrame:
    daily_prices = pd.read_parquet(daily_prices_path) if daily_prices_path.exists() else empty_frame(config.CANONICAL_PRICE_COLUMNS)
    result = compute_liquidity_metrics_df(daily_prices)
    write_parquet(result, output_path)
    print(f"[liquidity] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    compute_liquidity()
