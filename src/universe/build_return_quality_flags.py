from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.universe.build_corporate_action_evidence import build_corporate_action_evidence_df
from src.utils import empty_frame, write_parquet


EXTREME_POSITIVE_RETURN = 10.0
EXTREME_NEGATIVE_RETURN = -0.95
REVERSE_SPLIT_MATCH_WINDOW_DAYS = 10
SUSPENSION_LOOKAHEAD_DAYS = 30
COMMON_SPLIT_RATIOS = (10, 16, 20, 25, 30, 40, 50, 60, 80, 100, 200, 250)


def _prepare_returns(daily_prices: pd.DataFrame) -> pd.DataFrame:
    work = daily_prices.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "adjusted_close"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")

    work = work.dropna(subset=["date", "symbol", "close"]).sort_values(["symbol", "date"]).reset_index(drop=True)
    grouped = work.groupby("symbol", sort=False)
    work["prev_date"] = grouped["date"].shift(1)
    work["prev_close"] = grouped["close"].shift(1)
    work["prev_adjusted_close"] = grouped["adjusted_close"].shift(1)
    work["prev_volume"] = grouped["volume"].shift(1)
    work["raw_return"] = work["close"] / work["prev_close"].where(work["prev_close"].gt(0)) - 1
    work["adjusted_return"] = (
        work["adjusted_close"] / work["prev_adjusted_close"].where(work["prev_adjusted_close"].gt(0)) - 1
    )
    return work


def _nearest_evidence(row: pd.Series, evidence_by_symbol: dict[str, pd.DataFrame]) -> pd.Series | None:
    evidence = evidence_by_symbol.get(str(row["symbol"]))
    if evidence is None or evidence.empty:
        return None

    same_day = evidence[evidence["event_date"].eq(row["date"])]
    if not same_day.empty:
        priority = {"reverse_split": 0, "price_reference": 1, "news_spike": 2, "trading_suspension": 3}
        ranked = same_day.assign(priority=same_day["event_type"].map(priority).fillna(99))
        return ranked.sort_values(["priority", "event_date"]).iloc[0]

    reverse_splits = evidence[evidence["event_type"].eq("reverse_split")].copy()
    if not reverse_splits.empty:
        reverse_splits["date_delta_days"] = (reverse_splits["event_date"] - row["date"]).abs().dt.days
        nearby = reverse_splits[reverse_splits["date_delta_days"].le(REVERSE_SPLIT_MATCH_WINDOW_DAYS)]
        if not nearby.empty:
            return nearby.sort_values(["date_delta_days", "event_date"]).iloc[0]

    references = evidence[evidence["event_type"].eq("price_reference")]
    if not references.empty:
        return references.sort_values("event_date").iloc[-1]

    suspensions = evidence[evidence["event_type"].eq("trading_suspension")].copy()
    if not suspensions.empty:
        suspensions["date_delta_days"] = (suspensions["event_date"] - row["date"]).dt.days
        nearby = suspensions[
            suspensions["date_delta_days"].between(0, SUSPENSION_LOOKAHEAD_DAYS, inclusive="both")
        ]
        if not nearby.empty:
            return nearby.sort_values(["date_delta_days", "event_date"]).iloc[0]

    return None


def _is_split_like(raw_multiplier: float) -> bool:
    if pd.isna(raw_multiplier) or raw_multiplier <= 0:
        return False
    for ratio in COMMON_SPLIT_RATIOS:
        if 0.75 * ratio <= raw_multiplier <= 1.25 * ratio:
            return True
        inverse = 1 / ratio
        if 0.75 * inverse <= raw_multiplier <= 1.25 * inverse:
            return True
    return False


def _row_decision(row: pd.Series, evidence_row: pd.Series | None) -> dict[str, object]:
    reasons: list[str] = []
    notes: list[str] = []
    raw_return = row["raw_return"]
    raw_multiplier = raw_return + 1 if pd.notna(raw_return) else float("nan")

    if pd.notna(raw_return) and raw_return > EXTREME_POSITIVE_RETURN:
        reasons.append("extreme_positive_return_gt_1000pct")
    if pd.notna(raw_return) and raw_return < EXTREME_NEGATIVE_RETURN:
        reasons.append("extreme_negative_return_lt_minus95pct")
    if row["prev_close"] <= 0.25 and pd.notna(raw_return) and raw_return > EXTREME_POSITIVE_RETURN:
        reasons.append("penny_base_jump")
    if (row["prev_volume"] == 0 or row["volume"] == 0) and reasons:
        reasons.append("zero_volume_side")
    if str(row["source"]) == "yahoo_delisted_probe":
        reasons.append("delisted_probe_extreme_return")
    if _is_split_like(raw_multiplier):
        reasons.append("split_like_return_ratio")

    event_type = ""
    evidence_event_date = pd.NaT
    evidence_source_name = ""
    evidence_url = ""
    severity = "review"
    exclude = False

    if evidence_row is not None:
        event_type = str(evidence_row["event_type"])
        evidence_event_date = evidence_row["event_date"]
        evidence_source_name = str(evidence_row["source_name"])
        evidence_url = str(evidence_row["source_url"])

        if event_type == "reverse_split":
            if evidence_event_date == row["date"]:
                reasons.append("matched_reverse_split_evidence")
            else:
                reasons.append("nearby_reverse_split_evidence_date_mismatch")
                notes.append("price jump date does not equal the sourced reverse-split effective date")
            severity = "exclude_candidate"
            exclude = True
        elif event_type == "price_reference":
            reasons.append("reference_price_scale_error_candidate")
            severity = "exclude_candidate"
            exclude = True
        elif event_type == "news_spike":
            reasons.append("matched_news_event_evidence")
            severity = "event_risk"
            exclude = False
        elif event_type == "trading_suspension":
            reasons.append("nearby_trading_suspension_evidence")
            severity = "event_risk"
            exclude = False

    if not exclude and "split_like_return_ratio" in reasons and "matched_news_event_evidence" not in reasons:
        severity = "exclude_candidate"
        exclude = True

    if not exclude and row["symbol"].endswith((".P", ".PA", ".PB", ".PC", ".PN")) and abs(raw_multiplier) > 50:
        reasons.append("preferred_symbol_scale_error_candidate")
        severity = "exclude_candidate"
        exclude = True

    if not reasons:
        reasons.append("extreme_return")

    return {
        "flag_reason": "; ".join(dict.fromkeys(reasons)),
        "severity": severity,
        "event_type": event_type,
        "evidence_event_date": evidence_event_date,
        "evidence_source_name": evidence_source_name,
        "evidence_url": evidence_url,
        "exclude_from_backtest_return": exclude,
        "notes": "; ".join(dict.fromkeys(notes)),
    }


def build_return_quality_flags_df(
    daily_prices: pd.DataFrame,
    corporate_action_evidence: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if daily_prices.empty:
        return empty_frame(config.RETURN_QUALITY_FLAG_COLUMNS)

    evidence = (
        corporate_action_evidence.copy()
        if corporate_action_evidence is not None
        else build_corporate_action_evidence_df()
    )
    if evidence.empty:
        evidence_by_symbol: dict[str, pd.DataFrame] = {}
    else:
        evidence["event_date"] = pd.to_datetime(evidence["event_date"], errors="coerce").dt.normalize()
        evidence_by_symbol = {symbol: rows.copy() for symbol, rows in evidence.groupby("symbol")}

    returns = _prepare_returns(daily_prices)
    extreme = returns[
        returns["prev_close"].gt(0)
        & (
            returns["raw_return"].gt(EXTREME_POSITIVE_RETURN)
            | returns["raw_return"].lt(EXTREME_NEGATIVE_RETURN)
        )
    ].copy()
    if extreme.empty:
        return empty_frame(config.RETURN_QUALITY_FLAG_COLUMNS)

    decisions = [
        _row_decision(row, _nearest_evidence(row, evidence_by_symbol))
        for _, row in extreme.iterrows()
    ]
    decision_frame = pd.DataFrame(decisions, index=extreme.index)
    result = pd.concat([extreme, decision_frame], axis=1)
    result["date"] = result["date"].dt.normalize()
    result["prev_date"] = pd.to_datetime(result["prev_date"], errors="coerce").dt.normalize()
    result["evidence_event_date"] = pd.to_datetime(result["evidence_event_date"], errors="coerce").dt.normalize()
    result["prev_volume"] = result["prev_volume"].round().astype("Int64")
    result["volume"] = result["volume"].round().astype("Int64")
    result["exclude_from_backtest_return"] = result["exclude_from_backtest_return"].astype(bool)
    result = result[config.RETURN_QUALITY_FLAG_COLUMNS].sort_values(["date", "symbol"]).reset_index(drop=True)
    return result


def build_return_quality_flags(
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    corporate_action_evidence_path: Path = config.CORPORATE_ACTION_EVIDENCE_PATH,
    output_path: Path = config.RETURN_QUALITY_FLAGS_PATH,
) -> pd.DataFrame:
    daily_prices = (
        pd.read_parquet(daily_prices_path)
        if daily_prices_path.exists()
        else empty_frame(config.CANONICAL_PRICE_COLUMNS)
    )
    evidence = (
        pd.read_parquet(corporate_action_evidence_path)
        if corporate_action_evidence_path.exists()
        else build_corporate_action_evidence_df()
    )
    result = build_return_quality_flags_df(daily_prices, evidence)
    write_parquet(result, output_path)
    print(f"[return_quality_flags] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    build_return_quality_flags()
