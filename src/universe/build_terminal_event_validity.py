from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, normalize_symbol, read_parquet_if_exists, write_parquet


def _prepare_terminal_events(terminal_events: pd.DataFrame) -> pd.DataFrame:
    if terminal_events.empty:
        return empty_frame(config.TERMINAL_EVENTS_COLUMNS)
    result = terminal_events.copy()
    result["symbol"] = result["symbol"].map(normalize_symbol)
    result["event_date"] = pd.to_datetime(result["event_date"], errors="coerce").dt.normalize()
    result["terminal_date"] = pd.to_datetime(result["terminal_date"], errors="coerce").dt.normalize()
    result["has_terminal_price"] = result["has_terminal_price"].fillna(False).astype(bool)
    return result.dropna(subset=["symbol", "event_date"])


def _count_after(frame: pd.DataFrame, date_column: str, terminal_events: pd.DataFrame, out_column: str) -> pd.DataFrame:
    if frame.empty or terminal_events.empty:
        return pd.DataFrame(columns=["symbol", "event_date", out_column])

    work = frame[["symbol", date_column]].copy()
    work["symbol"] = work["symbol"].map(normalize_symbol)
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce").dt.normalize()
    work = work.dropna(subset=["symbol", date_column])
    if work.empty:
        return pd.DataFrame(columns=["symbol", "event_date", out_column])

    merged = terminal_events[["symbol", "event_date", "terminal_date"]].merge(work, on="symbol", how="left")
    counts = (
        merged[merged[date_column] > merged["terminal_date"]]
        .groupby(["symbol", "event_date"], as_index=False)
        .size()
        .rename(columns={"size": out_column})
    )
    return counts


def _count_after_event(frame: pd.DataFrame, date_column: str, terminal_events: pd.DataFrame, out_column: str) -> pd.DataFrame:
    if frame.empty or terminal_events.empty:
        return pd.DataFrame(columns=["symbol", "event_date", out_column])

    work = frame[["symbol", date_column]].copy()
    work["symbol"] = work["symbol"].map(normalize_symbol)
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce").dt.normalize()
    work = work.dropna(subset=["symbol", date_column])
    if work.empty:
        return pd.DataFrame(columns=["symbol", "event_date", out_column])

    merged = terminal_events[["symbol", "event_date"]].merge(work, on="symbol", how="left")
    counts = (
        merged[merged[date_column] > merged["event_date"]]
        .groupby(["symbol", "event_date"], as_index=False)
        .size()
        .rename(columns={"size": out_column})
    )
    return counts


def build_terminal_event_validity_df(
    terminal_events: pd.DataFrame,
    daily_prices: pd.DataFrame,
    universe_membership: pd.DataFrame,
    backtest_universe_membership: pd.DataFrame,
    delisting_outcomes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = _prepare_terminal_events(terminal_events)
    if events.empty:
        return (
            empty_frame(config.TERMINAL_EVENT_VALIDITY_COLUMNS),
            empty_frame(config.VALID_TERMINAL_EVENTS_COLUMNS),
        )

    outcomes = delisting_outcomes.copy() if not delisting_outcomes.empty else pd.DataFrame()
    if not outcomes.empty:
        outcomes["symbol"] = outcomes["symbol"].map(normalize_symbol)
        outcomes["event_date"] = pd.to_datetime(outcomes["event_date"], errors="coerce").dt.normalize()
        outcomes = outcomes[["symbol", "event_date", "outcome_type", "has_exit_value"]].drop_duplicates(
            ["symbol", "event_date"]
        )
    else:
        outcomes = pd.DataFrame(columns=["symbol", "event_date", "outcome_type", "has_exit_value"])

    validity = events[["symbol", "event_date", "terminal_date", "has_terminal_price", "event_source", "event_confidence"]].copy()
    validity = validity.merge(outcomes, on=["symbol", "event_date"], how="left")
    validity["outcome_type"] = validity["outcome_type"].fillna("unknown")
    validity["has_exit_value"] = validity["has_exit_value"].fillna(False).astype(bool)

    count_frames = [
        _count_after(daily_prices, "date", events, "price_rows_after_terminal_date"),
        _count_after_event(daily_prices, "date", events, "price_rows_after_event_date"),
        _count_after(universe_membership, "date", events, "universe_rows_after_terminal_date"),
        _count_after_event(universe_membership, "date", events, "universe_rows_after_event_date"),
        _count_after_event(backtest_universe_membership, "date", events, "backtest_rows_after_event_date"),
    ]
    for frame in count_frames:
        validity = validity.merge(frame, on=["symbol", "event_date"], how="left")

    count_columns = [
        "price_rows_after_terminal_date",
        "price_rows_after_event_date",
        "universe_rows_after_terminal_date",
        "universe_rows_after_event_date",
        "backtest_rows_after_event_date",
    ]
    for column in count_columns:
        validity[column] = validity[column].fillna(0).astype("int64")

    validity["has_price_after_terminal_date"] = validity["price_rows_after_terminal_date"].gt(0)
    validity["has_universe_after_terminal_date"] = validity["universe_rows_after_terminal_date"].gt(0)
    validity["has_universe_after_event_date"] = validity["universe_rows_after_event_date"].gt(0)
    validity["is_valid_liquidation_event"] = (
        validity["has_terminal_price"]
        & validity["terminal_date"].notna()
        & validity["has_universe_after_terminal_date"].eq(False)
        & validity["has_universe_after_event_date"].eq(False)
        & validity["backtest_rows_after_event_date"].eq(0)
    )

    reasons = pd.Series("", index=validity.index, dtype="string")
    reason_masks = {
        "missing_terminal_price": validity["has_terminal_price"].eq(False) | validity["terminal_date"].isna(),
        "base_universe_after_terminal_date": validity["has_universe_after_terminal_date"],
        "base_universe_after_event_date": validity["has_universe_after_event_date"],
        "backtest_universe_after_event_date": validity["backtest_rows_after_event_date"].gt(0),
    }
    for reason, mask in reason_masks.items():
        current = reasons.loc[mask]
        reasons.loc[mask] = current.where(current.eq(""), current + "; ") + reason

    validity["invalidation_reason"] = reasons.fillna("")
    validity["notes"] = validity["is_valid_liquidation_event"].map(
        {
            True: "Safe terminal-event subset for forced liquidation under current FONA universe rules.",
            False: "Raw terminal event retained for audit; do not use for hard liquidation without review.",
        }
    )

    validity = validity[config.TERMINAL_EVENT_VALIDITY_COLUMNS].sort_values(["event_date", "symbol"]).reset_index(drop=True)

    valid_events = events.merge(
        validity[["symbol", "event_date", "outcome_type", "has_exit_value", "is_valid_liquidation_event", "notes"]],
        on=["symbol", "event_date"],
        how="inner",
        suffixes=("", "_validity"),
    )
    valid_events = valid_events[valid_events["is_valid_liquidation_event"]].copy()
    valid_events = valid_events.rename(columns={"notes_validity": "validity_notes"})
    valid_events = valid_events[config.VALID_TERMINAL_EVENTS_COLUMNS].sort_values(["event_date", "symbol"]).reset_index(drop=True)

    return validity, valid_events


def build_terminal_event_validity(
    terminal_events_path: Path = config.TERMINAL_EVENTS_PATH,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    universe_membership_path: Path = config.UNIVERSE_MEMBERSHIP_PATH,
    backtest_universe_membership_path: Path = config.BACKTEST_UNIVERSE_MEMBERSHIP_PATH,
    delisting_outcomes_path: Path = config.DELISTING_OUTCOMES_PATH,
    validity_path: Path = config.TERMINAL_EVENT_VALIDITY_PATH,
    valid_terminal_events_path: Path = config.VALID_TERMINAL_EVENTS_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    terminal_events = read_parquet_if_exists(terminal_events_path, config.TERMINAL_EVENTS_COLUMNS)
    daily_prices = read_parquet_if_exists(daily_prices_path, config.CANONICAL_PRICE_COLUMNS)
    universe_membership = read_parquet_if_exists(universe_membership_path, config.UNIVERSE_COLUMNS)
    backtest_universe = read_parquet_if_exists(backtest_universe_membership_path, config.BACKTEST_UNIVERSE_COLUMNS)
    delisting_outcomes = read_parquet_if_exists(delisting_outcomes_path, config.DELISTING_OUTCOMES_COLUMNS)

    validity, valid_events = build_terminal_event_validity_df(
        terminal_events=terminal_events,
        daily_prices=daily_prices,
        universe_membership=universe_membership,
        backtest_universe_membership=backtest_universe,
        delisting_outcomes=delisting_outcomes,
    )
    write_parquet(validity, validity_path)
    write_parquet(valid_events, valid_terminal_events_path)
    print(f"[terminal_event_validity] Wrote {len(validity):,} rows to {validity_path}")
    print(f"[terminal_event_validity] Wrote {len(valid_events):,} valid terminal events to {valid_terminal_events_path}")
    return validity, valid_events


if __name__ == "__main__":
    config.ensure_directories()
    build_terminal_event_validity()
