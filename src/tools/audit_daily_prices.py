from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from src import config


HARD_CHECK_SQL = """
WITH duplicate_keys AS (
    SELECT date, symbol, COUNT(*) AS row_count
    FROM daily_prices
    GROUP BY date, symbol
    HAVING COUNT(*) > 1
),
global_calendar AS (
    SELECT date, LEAD(date) OVER (ORDER BY date) AS next_date
    FROM (SELECT DISTINCT date FROM daily_prices ORDER BY date)
),
daily_checks AS (
    SELECT
        SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) AS null_date,
        SUM(CASE WHEN symbol IS NULL OR TRIM(symbol) = '' THEN 1 ELSE 0 END) AS null_symbol,
        SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) AS null_open,
        SUM(CASE WHEN high IS NULL THEN 1 ELSE 0 END) AS null_high,
        SUM(CASE WHEN low IS NULL THEN 1 ELSE 0 END) AS null_low,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) AS null_close,
        SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) AS null_volume,
        SUM(CASE WHEN open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 THEN 1 ELSE 0 END) AS nonpositive_ohlc,
        SUM(CASE WHEN volume < 0 THEN 1 ELSE 0 END) AS negative_volume,
        SUM(CASE WHEN high < low THEN 1 ELSE 0 END) AS high_lt_low,
        SUM(CASE WHEN open > high OR open < low OR close > high OR close < low THEN 1 ELSE 0 END) AS ohlc_outside_high_low,
        SUM(CASE WHEN date > CURRENT_DATE THEN 1 ELSE 0 END) AS future_dates,
        SUM(CASE WHEN STRFTIME(date, '%w') IN ('0', '6') THEN 1 ELSE 0 END) AS weekend_rows
    FROM daily_prices
),
integrity_checks AS (
    SELECT
        (SELECT COUNT(*) FROM daily_prices p LEFT JOIN symbol_master s USING(symbol) WHERE s.symbol IS NULL) AS prices_missing_symbol_master,
        (SELECT COUNT(*) FROM symbol_master s LEFT JOIN security_master sm USING(symbol) WHERE sm.symbol IS NULL) AS symbol_master_missing_security_master,
        (SELECT COUNT(*) FROM liquidity_metrics l LEFT JOIN daily_prices p USING(date, symbol) WHERE p.symbol IS NULL) AS liquidity_without_price,
        (SELECT COUNT(*) FROM universe_membership u LEFT JOIN daily_prices p USING(date, symbol) WHERE p.symbol IS NULL) AS universe_without_price,
        (SELECT COUNT(*) FROM backtest_universe_membership u LEFT JOIN daily_prices p USING(date, symbol) WHERE p.symbol IS NULL) AS backtest_universe_without_price,
        (SELECT COUNT(*) FROM terminal_events t LEFT JOIN symbol_master s USING(symbol) WHERE s.symbol IS NULL) AS terminal_events_missing_symbol_master,
        (SELECT COUNT(*) FROM delisting_outcomes o LEFT JOIN symbol_master s USING(symbol) WHERE s.symbol IS NULL) AS delisting_outcomes_missing_symbol_master,
        (
            SELECT COUNT(*)
            FROM delisting_outcomes o
            LEFT JOIN terminal_events t USING(symbol, event_date)
            WHERE t.symbol IS NULL
        ) AS delisting_outcomes_without_terminal_event,
        (SELECT COUNT(*) FROM delisting_outcomes WHERE exit_date IS NULL) AS delisting_outcomes_missing_exit_date,
        (
            SELECT COUNT(*)
            FROM terminal_event_validity v
            LEFT JOIN terminal_events t USING(symbol, event_date)
            WHERE t.symbol IS NULL
        ) AS terminal_event_validity_without_terminal_event,
        (
            SELECT COUNT(*)
            FROM valid_terminal_events
            WHERE is_valid_liquidation_event = FALSE
        ) AS invalid_rows_in_valid_terminal_events,
        (
            SELECT COUNT(*)
            FROM universe_membership u
            JOIN liquidity_metrics l USING(date, symbol)
            JOIN global_calendar c ON c.date = u.date
            LEFT JOIN daily_prices p ON p.symbol = u.symbol AND p.date = c.next_date AND p.open > 0
            WHERE l.has_next_open AND c.next_date IS NOT NULL AND p.symbol IS NULL
        ) AS universe_global_next_open_mismatch,
        (SELECT COUNT(*) FROM universe_membership u JOIN liquidity_metrics l USING(date, symbol) WHERE l.is_price_quality_suspect) AS universe_price_quality_suspect,
        (SELECT COUNT(*) FROM backtest_universe_membership u JOIN liquidity_metrics l USING(date, symbol) WHERE l.is_price_quality_suspect) AS backtest_universe_price_quality_suspect
)
SELECT 'duplicate_keys' AS check_name, COUNT(*)::DOUBLE AS value FROM duplicate_keys
UNION ALL SELECT 'duplicate_affected_rows', COALESCE(SUM(row_count), 0)::DOUBLE FROM duplicate_keys
UNION ALL SELECT 'null_date', null_date FROM daily_checks
UNION ALL SELECT 'null_symbol', null_symbol FROM daily_checks
UNION ALL SELECT 'null_open', null_open FROM daily_checks
UNION ALL SELECT 'null_high', null_high FROM daily_checks
UNION ALL SELECT 'null_low', null_low FROM daily_checks
UNION ALL SELECT 'null_close', null_close FROM daily_checks
UNION ALL SELECT 'null_volume', null_volume FROM daily_checks
UNION ALL SELECT 'nonpositive_ohlc', nonpositive_ohlc FROM daily_checks
UNION ALL SELECT 'negative_volume', negative_volume FROM daily_checks
UNION ALL SELECT 'high_lt_low', high_lt_low FROM daily_checks
UNION ALL SELECT 'ohlc_outside_high_low', ohlc_outside_high_low FROM daily_checks
UNION ALL SELECT 'future_dates', future_dates FROM daily_checks
UNION ALL SELECT 'weekend_rows', weekend_rows FROM daily_checks
UNION ALL SELECT 'prices_missing_symbol_master', prices_missing_symbol_master FROM integrity_checks
UNION ALL SELECT 'symbol_master_missing_security_master', symbol_master_missing_security_master FROM integrity_checks
UNION ALL SELECT 'liquidity_without_price', liquidity_without_price FROM integrity_checks
UNION ALL SELECT 'universe_without_price', universe_without_price FROM integrity_checks
UNION ALL SELECT 'backtest_universe_without_price', backtest_universe_without_price FROM integrity_checks
UNION ALL SELECT 'terminal_events_missing_symbol_master', terminal_events_missing_symbol_master FROM integrity_checks
UNION ALL SELECT 'delisting_outcomes_missing_symbol_master', delisting_outcomes_missing_symbol_master FROM integrity_checks
UNION ALL SELECT 'delisting_outcomes_without_terminal_event', delisting_outcomes_without_terminal_event FROM integrity_checks
UNION ALL SELECT 'delisting_outcomes_missing_exit_date', delisting_outcomes_missing_exit_date FROM integrity_checks
UNION ALL SELECT 'terminal_event_validity_without_terminal_event', terminal_event_validity_without_terminal_event FROM integrity_checks
UNION ALL SELECT 'invalid_rows_in_valid_terminal_events', invalid_rows_in_valid_terminal_events FROM integrity_checks
UNION ALL SELECT 'universe_global_next_open_mismatch', universe_global_next_open_mismatch FROM integrity_checks
UNION ALL SELECT 'universe_price_quality_suspect', universe_price_quality_suspect FROM integrity_checks
UNION ALL SELECT 'backtest_universe_price_quality_suspect', backtest_universe_price_quality_suspect FROM integrity_checks
ORDER BY check_name
"""


PROFILE_SQL = """
SELECT
    COUNT(*) AS rows,
    COUNT(DISTINCT symbol) AS symbols,
    MIN(date) AS min_date,
    MAX(date) AS max_date,
    COUNT(DISTINCT date) AS trading_dates,
    COUNT(DISTINCT source) AS sources
FROM daily_prices
"""


SOURCE_SQL = """
SELECT
    source,
    is_delisted_source,
    COUNT(*) AS rows,
    COUNT(DISTINCT symbol) AS symbols,
    MIN(date) AS min_date,
    MAX(date) AS max_date,
    SUM(CASE WHEN volume = 0 THEN 1 ELSE 0 END) AS zero_volume_rows
FROM daily_prices
GROUP BY source, is_delisted_source
ORDER BY rows DESC
"""


QUALITY_SQL = """
SELECT
    COUNT(*) AS flagged_rows,
    COUNT(DISTINCT symbol) AS flagged_symbols,
    COUNT(*) FILTER (WHERE flag_reason LIKE '%extreme_ohlc%') AS extreme_ohlc_rows,
    COUNT(*) FILTER (WHERE flag_reason LIKE '%extreme_close_adjusted_ratio%') AS extreme_ratio_rows,
    COUNT(*) FILTER (WHERE flag_reason LIKE '%zero_volume_close%') AS zero_volume_high_price_rows
FROM price_quality_flags
"""


DELISTING_OUTCOME_SQL = """
SELECT
    COUNT(*) AS outcomes,
    SUM(CASE WHEN has_exit_price THEN 1 ELSE 0 END) AS with_exit_price,
    SUM(CASE WHEN has_exit_value THEN 1 ELSE 0 END) AS with_exit_value,
    COUNT(*) FILTER (WHERE cash_consideration_per_share IS NOT NULL) AS with_cash_consideration,
    COUNT(*) FILTER (WHERE effective_date IS NOT NULL) AS with_effective_date,
    COUNT(DISTINCT outcome_type) AS outcome_types,
    COUNT(*) FILTER (WHERE outcome_type = 'unknown') AS unknown_outcomes
FROM delisting_outcomes
"""


TERMINAL_VALIDITY_SQL = """
SELECT
    COUNT(*) AS terminal_events_checked,
    SUM(CASE WHEN is_valid_liquidation_event THEN 1 ELSE 0 END) AS valid_liquidation_events,
    SUM(CASE WHEN has_universe_after_terminal_date THEN 1 ELSE 0 END) AS universe_after_terminal_events,
    SUM(CASE WHEN has_price_after_terminal_date THEN 1 ELSE 0 END) AS price_after_terminal_events
FROM terminal_event_validity
"""


def audit_daily_prices(db_path: Path = config.DUCKDB_PATH) -> int:
    if not db_path.exists():
        raise FileNotFoundError(f"Missing DuckDB database: {db_path}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        profile = con.execute(PROFILE_SQL).fetchdf()
        sources = con.execute(SOURCE_SQL).fetchdf()
        quality = con.execute(QUALITY_SQL).fetchdf()
        delisting_outcomes = con.execute(DELISTING_OUTCOME_SQL).fetchdf()
        terminal_validity = con.execute(TERMINAL_VALIDITY_SQL).fetchdf()
        hard_checks = con.execute(HARD_CHECK_SQL).fetchdf()

    print("[audit] daily_prices profile")
    print(profile.to_string(index=False))
    print()
    print("[audit] source profile")
    print(sources.to_string(index=False))
    print()
    print("[audit] price quality flags")
    print(quality.to_string(index=False))
    print()
    print("[audit] delisting outcomes")
    print(delisting_outcomes.to_string(index=False))
    print()
    print("[audit] terminal event validity")
    print(terminal_validity.to_string(index=False))
    print()
    print("[audit] hard checks")
    print(hard_checks.to_string(index=False))

    failed = hard_checks[hard_checks["value"].fillna(0) != 0]
    if not failed.empty:
        print()
        print("[audit] FAILED")
        return 1

    print()
    print("[audit] OK")
    return 0


def main() -> None:
    raise SystemExit(audit_daily_prices())


if __name__ == "__main__":
    main()
