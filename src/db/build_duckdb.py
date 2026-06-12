from __future__ import annotations

from pathlib import Path

from src import config


def _quote_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _insert_from_parquet(con, table: str, path: Path, select_sql: str) -> None:
    if not path.exists():
        print(f"[duckdb] Missing {path}; created empty {table}.")
        return
    parquet_path = _quote_path(path)
    con.execute(f"INSERT INTO {table} {select_sql.format(path=parquet_path)}")


def build_duckdb(
    db_path: Path = config.DUCKDB_PATH,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    security_master_path: Path = config.SECURITY_MASTER_PATH,
    liquidity_metrics_path: Path = config.LIQUIDITY_METRICS_PATH,
    universe_membership_path: Path = config.UNIVERSE_MEMBERSHIP_PATH,
    universe_stats_path: Path = config.UNIVERSE_STATS_PATH,
    security_events_path: Path = config.SECURITY_EVENTS_PATH,
    terminal_events_path: Path = config.TERMINAL_EVENTS_PATH,
    delisting_outcomes_path: Path = config.DELISTING_OUTCOMES_PATH,
    backtest_universe_membership_path: Path = config.BACKTEST_UNIVERSE_MEMBERSHIP_PATH,
    price_quality_flags_path: Path = config.PRICE_QUALITY_FLAGS_PATH,
) -> Path:
    import duckdb

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for table in [
            "daily_prices",
            "symbol_master",
            "security_master",
            "liquidity_metrics",
            "universe_membership",
            "universe_stats",
            "security_events",
            "terminal_events",
            "delisting_outcomes",
            "backtest_universe_membership",
            "price_quality_flags",
        ]:
            con.execute(f"DROP TABLE IF EXISTS {table}")

        con.execute(
            """
            CREATE TABLE daily_prices (
                date DATE,
                symbol TEXT,
                vendor_symbol TEXT,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                adjusted_close DOUBLE,
                source TEXT,
                is_delisted_source BOOLEAN
            )
            """
        )
        con.execute(
            """
            CREATE TABLE symbol_master (
                symbol TEXT,
                vendor_symbol TEXT,
                first_date DATE,
                last_date DATE,
                source_list TEXT,
                has_active_source BOOLEAN,
                has_delisted_source BOOLEAN,
                observation_count BIGINT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE security_master (
                symbol TEXT,
                asset_type TEXT,
                is_etf BOOLEAN,
                instrument_type TEXT,
                security_name TEXT,
                exchange TEXT,
                currency TEXT,
                cik BIGINT,
                sic INTEGER,
                sic_description TEXT,
                sector TEXT,
                industry TEXT,
                classification_source TEXT,
                sector_source TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE liquidity_metrics (
                date DATE,
                symbol TEXT,
                close DOUBLE,
                volume BIGINT,
                dollar_volume DOUBLE,
                quality_dollar_volume DOUBLE,
                adv20 DOUBLE,
                quality_adv20 DOUBLE,
                traded_days_20 INTEGER,
                quality_traded_days_20 INTEGER,
                next_open DOUBLE,
                has_next_open BOOLEAN,
                is_price_quality_suspect BOOLEAN
            )
            """
        )
        con.execute(
            """
            CREATE TABLE universe_membership (
                date DATE,
                universe_name TEXT,
                symbol TEXT,
                reason TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE universe_stats (
                date DATE,
                universe_name TEXT,
                symbol_count BIGINT,
                median_close DOUBLE,
                median_adv20 DOUBLE,
                total_dollar_volume DOUBLE,
                delisted_source_count BIGINT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE security_events (
                symbol TEXT,
                event_type TEXT,
                event_date DATE,
                source TEXT,
                source_event_id TEXT,
                source_symbol TEXT,
                confidence TEXT,
                notes TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE terminal_events (
                symbol TEXT,
                event_date DATE,
                terminal_date DATE,
                terminal_price DOUBLE,
                previous_close DOUBLE,
                terminal_return DOUBLE,
                has_terminal_price BOOLEAN,
                price_source TEXT,
                event_source TEXT,
                event_confidence TEXT,
                terminal_policy TEXT,
                notes TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE delisting_outcomes (
                symbol TEXT,
                event_date DATE,
                effective_date DATE,
                exit_date DATE,
                exit_date_source TEXT,
                exit_price_date DATE,
                exit_price DOUBLE,
                previous_close DOUBLE,
                exit_return DOUBLE,
                has_exit_price BOOLEAN,
                cash_consideration_per_share DOUBLE,
                cash_consideration_is_partial BOOLEAN,
                cash_consideration_price_ratio DOUBLE,
                exit_value DOUBLE,
                exit_value_return DOUBLE,
                exit_value_source TEXT,
                has_exit_value BOOLEAN,
                price_source TEXT,
                event_source TEXT,
                event_confidence TEXT,
                outcome_type TEXT,
                outcome_confidence TEXT,
                outcome_source TEXT,
                sec_filename TEXT,
                sec_form_type TEXT,
                sec_company_name TEXT,
                sec_ticker_source TEXT,
                candidate_symbol_count BIGINT,
                policy TEXT,
                evidence TEXT,
                notes TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE backtest_universe_membership (
                date DATE,
                universe_name TEXT,
                symbol TEXT,
                reason TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE price_quality_flags (
                date DATE,
                symbol TEXT,
                source TEXT,
                flag_reason TEXT,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                adjusted_close DOUBLE,
                close_adjusted_ratio DOUBLE
            )
            """
        )

        _insert_from_parquet(
            con,
            "daily_prices",
            daily_prices_path,
            """
            SELECT
                CAST(date AS DATE),
                CAST(symbol AS TEXT),
                CAST(vendor_symbol AS TEXT),
                CAST(open AS DOUBLE),
                CAST(high AS DOUBLE),
                CAST(low AS DOUBLE),
                CAST(close AS DOUBLE),
                CAST(volume AS BIGINT),
                CAST(adjusted_close AS DOUBLE),
                CAST(source AS TEXT),
                CAST(is_delisted_source AS BOOLEAN)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "symbol_master",
            symbol_master_path,
            """
            SELECT
                CAST(symbol AS TEXT),
                CAST(vendor_symbol AS TEXT),
                CAST(first_date AS DATE),
                CAST(last_date AS DATE),
                CAST(source_list AS TEXT),
                CAST(has_active_source AS BOOLEAN),
                CAST(has_delisted_source AS BOOLEAN),
                CAST(observation_count AS BIGINT)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "security_master",
            security_master_path,
            """
            SELECT
                CAST(symbol AS TEXT),
                CAST(asset_type AS TEXT),
                CAST(is_etf AS BOOLEAN),
                CAST(instrument_type AS TEXT),
                CAST(security_name AS TEXT),
                CAST(exchange AS TEXT),
                CAST(currency AS TEXT),
                CAST(cik AS BIGINT),
                CAST(sic AS INTEGER),
                CAST(sic_description AS TEXT),
                CAST(sector AS TEXT),
                CAST(industry AS TEXT),
                CAST(classification_source AS TEXT),
                CAST(sector_source AS TEXT)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "liquidity_metrics",
            liquidity_metrics_path,
            """
            SELECT
                CAST(date AS DATE),
                CAST(symbol AS TEXT),
                CAST(close AS DOUBLE),
                CAST(volume AS BIGINT),
                CAST(dollar_volume AS DOUBLE),
                CAST(quality_dollar_volume AS DOUBLE),
                CAST(adv20 AS DOUBLE),
                CAST(quality_adv20 AS DOUBLE),
                CAST(traded_days_20 AS INTEGER),
                CAST(quality_traded_days_20 AS INTEGER),
                CAST(next_open AS DOUBLE),
                CAST(has_next_open AS BOOLEAN),
                CAST(is_price_quality_suspect AS BOOLEAN)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "universe_membership",
            universe_membership_path,
            """
            SELECT
                CAST(date AS DATE),
                CAST(universe_name AS TEXT),
                CAST(symbol AS TEXT),
                CAST(reason AS TEXT)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "universe_stats",
            universe_stats_path,
            """
            SELECT
                CAST(date AS DATE),
                CAST(universe_name AS TEXT),
                CAST(symbol_count AS BIGINT),
                CAST(median_close AS DOUBLE),
                CAST(median_adv20 AS DOUBLE),
                CAST(total_dollar_volume AS DOUBLE),
                CAST(delisted_source_count AS BIGINT)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "security_events",
            security_events_path,
            """
            SELECT
                CAST(symbol AS TEXT),
                CAST(event_type AS TEXT),
                CAST(event_date AS DATE),
                CAST(source AS TEXT),
                CAST(source_event_id AS TEXT),
                CAST(source_symbol AS TEXT),
                CAST(confidence AS TEXT),
                CAST(notes AS TEXT)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "terminal_events",
            terminal_events_path,
            """
            SELECT
                CAST(symbol AS TEXT),
                CAST(event_date AS DATE),
                CAST(terminal_date AS DATE),
                CAST(terminal_price AS DOUBLE),
                CAST(previous_close AS DOUBLE),
                CAST(terminal_return AS DOUBLE),
                CAST(has_terminal_price AS BOOLEAN),
                CAST(price_source AS TEXT),
                CAST(event_source AS TEXT),
                CAST(event_confidence AS TEXT),
                CAST(terminal_policy AS TEXT),
                CAST(notes AS TEXT)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "delisting_outcomes",
            delisting_outcomes_path,
            """
            SELECT
                CAST(symbol AS TEXT),
                CAST(event_date AS DATE),
                CAST(effective_date AS DATE),
                CAST(exit_date AS DATE),
                CAST(exit_date_source AS TEXT),
                CAST(exit_price_date AS DATE),
                CAST(exit_price AS DOUBLE),
                CAST(previous_close AS DOUBLE),
                CAST(exit_return AS DOUBLE),
                CAST(has_exit_price AS BOOLEAN),
                CAST(cash_consideration_per_share AS DOUBLE),
                CAST(cash_consideration_is_partial AS BOOLEAN),
                CAST(cash_consideration_price_ratio AS DOUBLE),
                CAST(exit_value AS DOUBLE),
                CAST(exit_value_return AS DOUBLE),
                CAST(exit_value_source AS TEXT),
                CAST(has_exit_value AS BOOLEAN),
                CAST(price_source AS TEXT),
                CAST(event_source AS TEXT),
                CAST(event_confidence AS TEXT),
                CAST(outcome_type AS TEXT),
                CAST(outcome_confidence AS TEXT),
                CAST(outcome_source AS TEXT),
                CAST(sec_filename AS TEXT),
                CAST(sec_form_type AS TEXT),
                CAST(sec_company_name AS TEXT),
                CAST(sec_ticker_source AS TEXT),
                CAST(candidate_symbol_count AS BIGINT),
                CAST(policy AS TEXT),
                CAST(evidence AS TEXT),
                CAST(notes AS TEXT)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "backtest_universe_membership",
            backtest_universe_membership_path,
            """
            SELECT
                CAST(date AS DATE),
                CAST(universe_name AS TEXT),
                CAST(symbol AS TEXT),
                CAST(reason AS TEXT)
            FROM read_parquet('{path}')
            """,
        )
        _insert_from_parquet(
            con,
            "price_quality_flags",
            price_quality_flags_path,
            """
            SELECT
                CAST(date AS DATE),
                CAST(symbol AS TEXT),
                CAST(source AS TEXT),
                CAST(flag_reason AS TEXT),
                CAST(open AS DOUBLE),
                CAST(high AS DOUBLE),
                CAST(low AS DOUBLE),
                CAST(close AS DOUBLE),
                CAST(volume AS BIGINT),
                CAST(adjusted_close AS DOUBLE),
                CAST(close_adjusted_ratio AS DOUBLE)
            FROM read_parquet('{path}')
            """,
        )

        con.execute("CREATE INDEX IF NOT EXISTS idx_prices_date_symbol ON daily_prices(date, symbol)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_security_symbol ON security_master(symbol)")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_universe_date_name ON universe_membership(date, universe_name)"
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_liquidity_date_symbol ON liquidity_metrics(date, symbol)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_security_events_symbol ON security_events(symbol, event_type)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_terminal_events_symbol ON terminal_events(symbol, event_date)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_delisting_outcomes_symbol ON delisting_outcomes(symbol, event_date)")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_backtest_universe_date_name "
            "ON backtest_universe_membership(date, universe_name)"
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_price_quality_flags_symbol ON price_quality_flags(symbol, date)")
    finally:
        con.close()

    print(f"[duckdb] Built database at {db_path}")
    return db_path


if __name__ == "__main__":
    config.ensure_directories()
    build_duckdb()
