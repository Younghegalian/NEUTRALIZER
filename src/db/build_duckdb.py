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
    liquidity_metrics_path: Path = config.LIQUIDITY_METRICS_PATH,
    universe_membership_path: Path = config.UNIVERSE_MEMBERSHIP_PATH,
    universe_stats_path: Path = config.UNIVERSE_STATS_PATH,
) -> Path:
    import duckdb

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for table in [
            "daily_prices",
            "symbol_master",
            "liquidity_metrics",
            "universe_membership",
            "universe_stats",
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
            CREATE TABLE liquidity_metrics (
                date DATE,
                symbol TEXT,
                close DOUBLE,
                volume BIGINT,
                dollar_volume DOUBLE,
                adv20 DOUBLE,
                traded_days_20 INTEGER,
                next_open DOUBLE,
                has_next_open BOOLEAN
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
            "liquidity_metrics",
            liquidity_metrics_path,
            """
            SELECT
                CAST(date AS DATE),
                CAST(symbol AS TEXT),
                CAST(close AS DOUBLE),
                CAST(volume AS BIGINT),
                CAST(dollar_volume AS DOUBLE),
                CAST(adv20 AS DOUBLE),
                CAST(traded_days_20 AS INTEGER),
                CAST(next_open AS DOUBLE),
                CAST(has_next_open AS BOOLEAN)
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

        con.execute("CREATE INDEX IF NOT EXISTS idx_prices_date_symbol ON daily_prices(date, symbol)")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_universe_date_name ON universe_membership(date, universe_name)"
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_liquidity_date_symbol ON liquidity_metrics(date, symbol)")
    finally:
        con.close()

    print(f"[duckdb] Built database at {db_path}")
    return db_path


if __name__ == "__main__":
    config.ensure_directories()
    build_duckdb()

