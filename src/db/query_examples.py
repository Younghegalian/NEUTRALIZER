from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config


def _connect(db_path: Path = config.DUCKDB_PATH):
    import duckdb

    return duckdb.connect(str(db_path), read_only=True)


def get_universe(
    date: str,
    universe_name: str = config.UNIVERSE_NAME,
    db_path: Path = config.DUCKDB_PATH,
) -> list[str]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT symbol
            FROM universe_membership
            WHERE date = CAST(? AS DATE)
              AND universe_name = ?
            ORDER BY symbol
            """,
            [date, universe_name],
        ).fetchall()
    finally:
        con.close()
    return [row[0] for row in rows]


def get_backtest_universe(
    date: str,
    db_path: Path = config.DUCKDB_PATH,
) -> list[str]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT symbol
            FROM backtest_universe_membership
            WHERE date = CAST(? AS DATE)
              AND universe_name = ?
            ORDER BY symbol
            """,
            [date, config.BACKTEST_UNIVERSE_NAME],
        ).fetchall()
    finally:
        con.close()
    return [row[0] for row in rows]


def get_prices(
    date: str,
    symbols: list[str],
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=config.CANONICAL_PRICE_COLUMNS)

    placeholders = ",".join(["?"] * len(symbols))
    params = [date, *symbols]
    con = _connect(db_path)
    try:
        return con.execute(
            f"""
            SELECT *
            FROM daily_prices
            WHERE date = CAST(? AS DATE)
              AND symbol IN ({placeholders})
            ORDER BY symbol
            """,
            params,
        ).fetchdf()
    finally:
        con.close()


def get_security_master(
    symbols: list[str] | None = None,
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    con = _connect(db_path)
    try:
        if not symbols:
            return con.execute("SELECT * FROM security_master ORDER BY symbol").fetchdf()
        placeholders = ",".join(["?"] * len(symbols))
        return con.execute(
            f"""
            SELECT *
            FROM security_master
            WHERE symbol IN ({placeholders})
            ORDER BY symbol
            """,
            symbols,
        ).fetchdf()
    finally:
        con.close()


def get_security_classification_catalog(
    symbols: list[str] | None = None,
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    con = _connect(db_path)
    try:
        if not symbols:
            return con.execute("SELECT * FROM security_classification_catalog ORDER BY symbol").fetchdf()
        placeholders = ",".join(["?"] * len(symbols))
        return con.execute(
            f"""
            SELECT *
            FROM security_classification_catalog
            WHERE symbol IN ({placeholders})
            ORDER BY symbol
            """,
            symbols,
        ).fetchdf()
    finally:
        con.close()


def get_delisting_outcomes(
    symbols: list[str] | None = None,
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    con = _connect(db_path)
    try:
        if not symbols:
            return con.execute("SELECT * FROM delisting_outcomes ORDER BY event_date, symbol").fetchdf()
        placeholders = ",".join(["?"] * len(symbols))
        return con.execute(
            f"""
            SELECT *
            FROM delisting_outcomes
            WHERE symbol IN ({placeholders})
            ORDER BY event_date, symbol
            """,
            symbols,
        ).fetchdf()
    finally:
        con.close()


def get_valid_terminal_events(
    symbols: list[str] | None = None,
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    con = _connect(db_path)
    try:
        if not symbols:
            return con.execute("SELECT * FROM valid_terminal_events ORDER BY event_date, symbol").fetchdf()
        placeholders = ",".join(["?"] * len(symbols))
        return con.execute(
            f"""
            SELECT *
            FROM valid_terminal_events
            WHERE symbol IN ({placeholders})
            ORDER BY event_date, symbol
            """,
            symbols,
        ).fetchdf()
    finally:
        con.close()


def get_symbol_aliases(
    alias_symbols: list[str] | None = None,
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    con = _connect(db_path)
    try:
        if not alias_symbols:
            return con.execute("SELECT * FROM symbol_aliases ORDER BY alias_symbol, start_date").fetchdf()
        placeholders = ",".join(["?"] * len(alias_symbols))
        return con.execute(
            f"""
            SELECT *
            FROM symbol_aliases
            WHERE alias_symbol IN ({placeholders})
            ORDER BY alias_symbol, start_date
            """,
            alias_symbols,
        ).fetchdf()
    finally:
        con.close()


def get_corporate_action_evidence(
    symbols: list[str] | None = None,
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    con = _connect(db_path)
    try:
        if not symbols:
            return con.execute(
                "SELECT * FROM corporate_action_evidence ORDER BY event_date, symbol, event_type"
            ).fetchdf()
        placeholders = ",".join(["?"] * len(symbols))
        return con.execute(
            f"""
            SELECT *
            FROM corporate_action_evidence
            WHERE symbol IN ({placeholders})
            ORDER BY event_date, symbol, event_type
            """,
            symbols,
        ).fetchdf()
    finally:
        con.close()


def get_return_quality_flags(
    symbols: list[str] | None = None,
    only_exclusions: bool = False,
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    con = _connect(db_path)
    try:
        predicates = []
        params: list[object] = []
        if symbols:
            placeholders = ",".join(["?"] * len(symbols))
            predicates.append(f"symbol IN ({placeholders})")
            params.extend(symbols)
        if only_exclusions:
            predicates.append("exclude_from_backtest_return")

        where_sql = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        return con.execute(
            f"""
            SELECT *
            FROM return_quality_flags
            {where_sql}
            ORDER BY date, symbol
            """,
            params,
        ).fetchdf()
    finally:
        con.close()


def get_price_panel(
    start_date: str,
    end_date: str,
    universe_name: str = config.UNIVERSE_NAME,
    db_path: Path = config.DUCKDB_PATH,
) -> pd.DataFrame:
    con = _connect(db_path)
    try:
        return con.execute(
            """
            SELECT p.*
            FROM daily_prices p
            JOIN universe_membership u
              ON p.date = u.date
             AND p.symbol = u.symbol
            WHERE p.date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
              AND u.universe_name = ?
            ORDER BY p.date, p.symbol
            """,
            [start_date, end_date, universe_name],
        ).fetchdf()
    finally:
        con.close()
