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
        (SELECT COUNT(*) FROM liquidity_metrics l LEFT JOIN daily_prices p USING(date, symbol) WHERE p.symbol IS NULL) AS liquidity_without_price,
        (SELECT COUNT(*) FROM universe_membership u LEFT JOIN daily_prices p USING(date, symbol) WHERE p.symbol IS NULL) AS universe_without_price
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
UNION ALL SELECT 'liquidity_without_price', liquidity_without_price FROM integrity_checks
UNION ALL SELECT 'universe_without_price', universe_without_price FROM integrity_checks
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


def audit_daily_prices(db_path: Path = config.DUCKDB_PATH) -> int:
    if not db_path.exists():
        raise FileNotFoundError(f"Missing DuckDB database: {db_path}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        profile = con.execute(PROFILE_SQL).fetchdf()
        sources = con.execute(SOURCE_SQL).fetchdf()
        hard_checks = con.execute(HARD_CHECK_SQL).fetchdf()

    print("[audit] daily_prices profile")
    print(profile.to_string(index=False))
    print()
    print("[audit] source profile")
    print(sources.to_string(index=False))
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
