from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, write_parquet


MAX_TRADABLE_CLOSE = 100_000
MAX_CLOSE_ADJUSTED_RATIO = 1_000
MIN_CLOSE_ADJUSTED_RATIO = 0.001
ZERO_VOLUME_HIGH_PRICE = 10_000
LEGITIMATE_HIGH_PRICE_SYMBOLS = {"BRK.A"}


def _price_quality_reason_frame(work: pd.DataFrame) -> pd.DataFrame:
    ratio = work["close"] / work["adjusted_close"].where(work["adjusted_close"].gt(0))
    ohlc_max = work[["open", "high", "low", "close"]].max(axis=1)
    reasons = pd.Series("", index=work.index, dtype="string")

    masks = {
        f"extreme_ohlc_gt_{MAX_TRADABLE_CLOSE}": ohlc_max.gt(MAX_TRADABLE_CLOSE)
        & ~work["symbol"].isin(LEGITIMATE_HIGH_PRICE_SYMBOLS),
        "extreme_close_adjusted_ratio": ratio.gt(MAX_CLOSE_ADJUSTED_RATIO) | ratio.lt(MIN_CLOSE_ADJUSTED_RATIO),
        f"zero_volume_close_gt_{ZERO_VOLUME_HIGH_PRICE}": work["volume"].fillna(0).eq(0)
        & work["close"].gt(ZERO_VOLUME_HIGH_PRICE),
    }
    for reason, mask in masks.items():
        mask = mask.fillna(False)
        current = reasons.loc[mask]
        reasons.loc[mask] = current.where(current.eq(""), current + "; ") + reason

    flags = work.loc[reasons.ne("")].copy()
    if flags.empty:
        return empty_frame(config.PRICE_QUALITY_FLAG_COLUMNS)

    flags["flag_reason"] = reasons.loc[flags.index]
    flags["close_adjusted_ratio"] = ratio.loc[flags.index]
    return flags[config.PRICE_QUALITY_FLAG_COLUMNS].reset_index(drop=True)


def build_price_quality_flags_df(daily_prices: pd.DataFrame) -> pd.DataFrame:
    if daily_prices.empty:
        return empty_frame(config.PRICE_QUALITY_FLAG_COLUMNS)

    work = daily_prices.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "adjusted_close"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return _price_quality_reason_frame(work)


def compute_liquidity_metrics_df(daily_prices: pd.DataFrame) -> pd.DataFrame:
    if daily_prices.empty:
        return empty_frame(config.LIQUIDITY_COLUMNS)

    work = daily_prices.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume", "adjusted_close"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    flags = build_price_quality_flags_df(work)
    if flags.empty:
        flagged_keys = pd.MultiIndex.from_arrays([[], []], names=["date", "symbol"])
    else:
        flagged_keys = pd.MultiIndex.from_frame(flags[["date", "symbol"]])

    work = work.sort_values(["symbol", "date"]).reset_index(drop=True)
    row_keys = pd.MultiIndex.from_frame(work[["date", "symbol"]])
    work["is_price_quality_suspect"] = row_keys.isin(flagged_keys)
    work["dollar_volume"] = work["close"] * work["volume"]
    not_suspect = work["is_price_quality_suspect"].eq(False)
    work["quality_dollar_volume"] = work["dollar_volume"].where(not_suspect, 0)
    grouped = work.groupby("symbol", group_keys=False)
    work["adv20"] = grouped["dollar_volume"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    work["quality_adv20"] = grouped["quality_dollar_volume"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    work["traded_days_20"] = grouped["volume"].transform(
        lambda s: s.gt(0).rolling(20, min_periods=1).sum()
    )
    work["quality_traded_days_20"] = (
        work["volume"].gt(0)
        & not_suspect
    ).groupby(work["symbol"]).transform(lambda s: s.rolling(20, min_periods=1).sum())
    calendar = work[["date"]].drop_duplicates().sort_values("date").reset_index(drop=True)
    calendar["next_date"] = calendar["date"].shift(-1)
    work = work.merge(calendar, on="date", how="left")
    next_rows = work[["symbol", "date", "open", "is_price_quality_suspect"]].rename(
        columns={
            "date": "next_date",
            "open": "next_open",
            "is_price_quality_suspect": "next_is_price_quality_suspect",
        }
    )
    work = work.merge(next_rows, on=["symbol", "next_date"], how="left")
    work["next_is_price_quality_suspect"] = work["next_is_price_quality_suspect"].fillna(False)
    work["has_next_open"] = (
        work["next_open"].notna()
        & work["next_open"].gt(0)
        & work["next_is_price_quality_suspect"].eq(False)
    )

    result = work[
        [
            "date",
            "symbol",
            "close",
            "volume",
            "dollar_volume",
            "quality_dollar_volume",
            "adv20",
            "quality_adv20",
            "traded_days_20",
            "quality_traded_days_20",
            "next_open",
            "has_next_open",
            "is_price_quality_suspect",
        ]
    ].copy()
    result["date"] = result["date"].dt.normalize()
    result["volume"] = result["volume"].round().astype("Int64")
    result["traded_days_20"] = result["traded_days_20"].round().astype("Int64")
    result["quality_traded_days_20"] = result["quality_traded_days_20"].round().astype("Int64")
    result["is_price_quality_suspect"] = result["is_price_quality_suspect"].astype(bool)
    return result[config.LIQUIDITY_COLUMNS]


def compute_liquidity(
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    output_path: Path = config.LIQUIDITY_METRICS_PATH,
    price_quality_flags_path: Path = config.PRICE_QUALITY_FLAGS_PATH,
) -> pd.DataFrame:
    daily_prices = pd.read_parquet(daily_prices_path) if daily_prices_path.exists() else empty_frame(config.CANONICAL_PRICE_COLUMNS)
    result = compute_liquidity_metrics_df(daily_prices)
    quality_flags = build_price_quality_flags_df(daily_prices)
    write_parquet(result, output_path)
    write_parquet(quality_flags, price_quality_flags_path)
    print(f"[liquidity] Wrote {len(result):,} rows to {output_path}")
    print(f"[liquidity] Wrote {len(quality_flags):,} price quality flags to {price_quality_flags_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    compute_liquidity()
