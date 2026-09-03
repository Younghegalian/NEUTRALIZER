from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

from src import config
from src.normalize.build_symbol_master import build_symbol_master_df
from src.normalize.deduplicate_prices import deduplicate_prices_df
from src.utils import (
    coerce_numeric,
    empty_frame,
    normalize_symbol,
    parse_date,
    read_parquet_if_exists,
    write_parquet,
)


NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "adjusted_close"]
OHLC_BOUNDS_TOLERANCE = 1e-8
SOURCE_PRIORITY = {
    "stooq": 1,
    "yahoo_fallback": 2,
    "yahoo_delisted_probe": 3,
    "kaggle_arandkei_delisted": 4,
}


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_path(path: Path) -> str:
    return _sql_string(path.as_posix())


def _read_parquet_expr(paths: list[Path]) -> str:
    path_list = ", ".join(_sql_path(path) for path in paths)
    return f"read_parquet([{path_list}], union_by_name = true)"


def _sql_date(value: object) -> str:
    return "DATE " + _sql_string(pd.Timestamp(value).date().isoformat())


def _date_filter_sql(start_date: object | None, end_date: object | None) -> str:
    conditions = []
    if start_date is not None:
        conditions.append(f"date >= {_sql_date(start_date)}")
    if end_date is not None:
        conditions.append(f"date <= {_sql_date(end_date)}")
    return " AND ".join(conditions) if conditions else "TRUE"


def _bad_condition() -> str:
    tolerance = OHLC_BOUNDS_TOLERANCE
    return f"""
        date IS NULL
        OR symbol IS NULL
        OR close IS NULL
        OR open IS NULL
        OR high IS NULL
        OR low IS NULL
        OR COALESCE(open <= 0, FALSE)
        OR COALESCE(high <= 0, FALSE)
        OR COALESCE(low <= 0, FALSE)
        OR COALESCE(close <= 0, FALSE)
        OR COALESCE(volume < 0, FALSE)
        OR COALESCE(high < low, FALSE)
        OR COALESCE(open > high + {tolerance}, FALSE)
        OR COALESCE(open < low - {tolerance}, FALSE)
        OR COALESCE(close > high + {tolerance}, FALSE)
        OR COALESCE(close < low - {tolerance}, FALSE)
    """


def _bad_reason_expr() -> str:
    tolerance = OHLC_BOUNDS_TOLERANCE
    parts = [
        ("date IS NULL", "date is null"),
        ("symbol IS NULL", "symbol is null"),
        ("close IS NULL", "close is null"),
        ("open IS NULL", "open is null"),
        ("high IS NULL", "high is null"),
        ("low IS NULL", "low is null"),
        ("COALESCE(open <= 0, FALSE)", "open <= 0"),
        ("COALESCE(high <= 0, FALSE)", "high <= 0"),
        ("COALESCE(low <= 0, FALSE)", "low <= 0"),
        ("COALESCE(close <= 0, FALSE)", "close <= 0"),
        ("COALESCE(volume < 0, FALSE)", "volume < 0"),
        ("COALESCE(high < low, FALSE)", "high < low"),
        (f"COALESCE(open > high + {tolerance}, FALSE)", "open > high"),
        (f"COALESCE(open < low - {tolerance}, FALSE)", "open < low"),
        (f"COALESCE(close > high + {tolerance}, FALSE)", "close > high"),
        (f"COALESCE(close < low - {tolerance}, FALSE)", "close < low"),
    ]
    concat_parts = "\n            || ".join(
        f"CASE WHEN {condition} THEN {_sql_string(reason + '; ')} ELSE '' END"
        for condition, reason in parts
    )
    return f"regexp_replace({concat_parts}, '; $', '')"


def _normalize_symbol_sql(column: str) -> str:
    cleaned = f"""
        replace(
            replace(
                regexp_replace(upper(trim(cast({column} as varchar))), '\\.(US|NYSE|NASDAQ|AMEX)$', ''),
                ' ',
                ''
            ),
            '-',
            '.'
        )
    """
    return f"nullif({cleaned}, '')"


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in config.CANONICAL_PRICE_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
    return out[config.CANONICAL_PRICE_COLUMNS]


def clean_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return empty_frame(config.CANONICAL_PRICE_COLUMNS)

    out = _ensure_columns(df)
    out["date"] = out["date"].map(parse_date)
    out["symbol"] = out["symbol"].map(normalize_symbol)
    out["vendor_symbol"] = out["vendor_symbol"].astype("string")
    out["source"] = out["source"].astype("string")
    out["is_delisted_source"] = out["is_delisted_source"].fillna(False).astype(bool)
    for column in NUMERIC_COLUMNS:
        out[column] = coerce_numeric(out[column])
    return out


def _row_reasons(row: pd.Series) -> list[str]:
    reasons: list[str] = []

    if pd.isna(row["date"]):
        reasons.append("date is null")
    if pd.isna(row["symbol"]):
        reasons.append("symbol is null")
    if pd.isna(row["close"]):
        reasons.append("close is null")

    for column in ["open", "high", "low", "close"]:
        if pd.isna(row[column]):
            reasons.append(f"{column} is null")
        elif row[column] <= 0:
            reasons.append(f"{column} <= 0")

    if not pd.isna(row["volume"]) and row["volume"] < 0:
        reasons.append("volume < 0")

    if not pd.isna(row["high"]) and not pd.isna(row["low"]) and row["high"] < row["low"]:
        reasons.append("high < low")

    if not pd.isna(row["open"]) and not pd.isna(row["high"]) and row["open"] > row["high"] + OHLC_BOUNDS_TOLERANCE:
        reasons.append("open > high")
    if not pd.isna(row["open"]) and not pd.isna(row["low"]) and row["open"] < row["low"] - OHLC_BOUNDS_TOLERANCE:
        reasons.append("open < low")
    if not pd.isna(row["close"]) and not pd.isna(row["high"]) and row["close"] > row["high"] + OHLC_BOUNDS_TOLERANCE:
        reasons.append("close > high")
    if not pd.isna(row["close"]) and not pd.isna(row["low"]) and row["close"] < row["low"] - OHLC_BOUNDS_TOLERANCE:
        reasons.append("close < low")

    return reasons


def split_bad_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        bad = empty_frame(config.CANONICAL_PRICE_COLUMNS + ["bad_reason"])
        return df.copy(), bad

    masks = {
        "date is null": df["date"].isna(),
        "symbol is null": df["symbol"].isna(),
        "close is null": df["close"].isna(),
        "open is null": df["open"].isna(),
        "high is null": df["high"].isna(),
        "low is null": df["low"].isna(),
        "open <= 0": df["open"].le(0),
        "high <= 0": df["high"].le(0),
        "low <= 0": df["low"].le(0),
        "close <= 0": df["close"].le(0),
        "volume < 0": df["volume"].lt(0),
        "high < low": df["high"].lt(df["low"]),
        "open > high": df["open"].gt(df["high"] + OHLC_BOUNDS_TOLERANCE),
        "open < low": df["open"].lt(df["low"] - OHLC_BOUNDS_TOLERANCE),
        "close > high": df["close"].gt(df["high"] + OHLC_BOUNDS_TOLERANCE),
        "close < low": df["close"].lt(df["low"] - OHLC_BOUNDS_TOLERANCE),
    }
    bad_mask = pd.Series(False, index=df.index)
    for mask in masks.values():
        bad_mask |= mask.fillna(False)

    bad = df.loc[bad_mask].copy()
    bad["bad_reason"] = ""
    for reason, mask in masks.items():
        affected = bad.index.intersection(mask[mask.fillna(False)].index)
        if len(affected) > 0:
            current = bad.loc[affected, "bad_reason"].astype(str)
            bad.loc[affected, "bad_reason"] = current.where(current.eq(""), current + "; ") + reason

    good = df.loc[~bad_mask].copy()
    return good, bad


def normalize_price_frame(
    frames: list[pd.DataFrame],
    start_date: object | None = None,
    end_date: object | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if frames:
        combined = pd.concat([clean_price_frame(frame) for frame in frames], ignore_index=True)
    else:
        combined = empty_frame(config.CANONICAL_PRICE_COLUMNS)

    if start_date is not None and not combined.empty:
        start_ts = pd.Timestamp(start_date)
        combined = combined[combined["date"] >= start_ts]
    if end_date is not None and not combined.empty:
        end_ts = pd.Timestamp(end_date)
        combined = combined[combined["date"] <= end_ts]

    good, bad = split_bad_rows(combined)
    selected, duplicate_report = deduplicate_prices_df(good)

    if not selected.empty:
        selected["date"] = pd.to_datetime(selected["date"]).dt.normalize()
        selected["volume"] = selected["volume"].round().astype("Int64")
        selected = selected[config.CANONICAL_PRICE_COLUMNS]

    symbol_master = build_symbol_master_df(selected)
    return selected, symbol_master, duplicate_report, bad


def _normalize_prices_pandas(
    staging_paths: list[Path] | None = None,
    start_date: object | None = None,
    end_date: object | None = None,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    duplicate_report_path: Path = config.DUPLICATE_REPORT_PATH,
    bad_rows_report_path: Path = config.BAD_ROWS_REPORT_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    staging_paths = staging_paths or [
        config.STOOQ_STAGING_PATH,
        config.YAHOO_FALLBACK_STAGING_PATH,
        config.YAHOO_DELISTED_PROBE_STAGING_PATH,
        config.KAGGLE_DELISTED_STAGING_PATH,
    ]
    frames = [read_parquet_if_exists(path, config.CANONICAL_PRICE_COLUMNS) for path in staging_paths]
    daily_prices, symbol_master, duplicate_report, bad_rows = normalize_price_frame(
        frames, start_date=start_date, end_date=end_date
    )

    write_parquet(daily_prices, daily_prices_path)
    write_parquet(symbol_master, symbol_master_path)
    write_parquet(duplicate_report, duplicate_report_path)
    write_parquet(bad_rows, bad_rows_report_path)

    print(f"[normalize] Wrote {len(daily_prices):,} canonical daily price rows to {daily_prices_path}")
    print(f"[normalize] Wrote {len(symbol_master):,} symbol rows to {symbol_master_path}")
    print(f"[normalize] Wrote {len(duplicate_report):,} duplicate groups to {duplicate_report_path}")
    print(f"[normalize] Wrote {len(bad_rows):,} rejected rows to {bad_rows_report_path}")
    return daily_prices, symbol_master


def _write_empty_outputs(
    daily_prices_path: Path,
    symbol_master_path: Path,
    duplicate_report_path: Path,
    bad_rows_report_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_prices = empty_frame(config.CANONICAL_PRICE_COLUMNS)
    symbol_master = empty_frame(config.SYMBOL_MASTER_COLUMNS)
    duplicate_report = pd.DataFrame(columns=["date", "symbol", "sources_found", "selected_source"])
    bad_rows = empty_frame(config.CANONICAL_PRICE_COLUMNS + ["bad_reason"])

    write_parquet(daily_prices, daily_prices_path)
    write_parquet(symbol_master, symbol_master_path)
    write_parquet(duplicate_report, duplicate_report_path)
    write_parquet(bad_rows, bad_rows_report_path)

    print(f"[normalize] Wrote 0 canonical daily price rows to {daily_prices_path}")
    print(f"[normalize] Wrote 0 symbol rows to {symbol_master_path}")
    print(f"[normalize] Wrote 0 duplicate groups to {duplicate_report_path}")
    print(f"[normalize] Wrote 0 rejected rows to {bad_rows_report_path}")
    return daily_prices, symbol_master


def _normalize_prices_duckdb(
    staging_paths: list[Path] | None = None,
    start_date: object | None = None,
    end_date: object | None = None,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    duplicate_report_path: Path = config.DUPLICATE_REPORT_PATH,
    bad_rows_report_path: Path = config.BAD_ROWS_REPORT_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    staging_paths = staging_paths or [
        config.STOOQ_STAGING_PATH,
        config.YAHOO_FALLBACK_STAGING_PATH,
        config.YAHOO_DELISTED_PROBE_STAGING_PATH,
        config.KAGGLE_DELISTED_STAGING_PATH,
    ]
    existing_paths = [path for path in staging_paths if path.exists()]
    if not existing_paths:
        return _write_empty_outputs(
            daily_prices_path=daily_prices_path,
            symbol_master_path=symbol_master_path,
            duplicate_report_path=duplicate_report_path,
            bad_rows_report_path=bad_rows_report_path,
        )

    for path in [daily_prices_path, symbol_master_path, duplicate_report_path, bad_rows_report_path]:
        path.parent.mkdir(parents=True, exist_ok=True)

    temp_parent = config.DATA_DIR / "duckdb_tmp" / "normalize"
    temp_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="run-", dir=temp_parent))

    bad_condition = _bad_condition()
    bad_reason_expr = _bad_reason_expr()
    price_columns = ", ".join(config.CANONICAL_PRICE_COLUMNS)

    con = duckdb.connect((temp_dir / "normalize.duckdb").as_posix())
    con.execute(f"SET temp_directory = {_sql_path(temp_dir)}")

    cleaned_sources: list[tuple[int, Path, str]] = []
    bad_paths: list[Path] = []
    date_filter = _date_filter_sql(start_date, end_date)
    con.execute("CREATE TABLE duplicate_source_events(date DATE, symbol VARCHAR, source VARCHAR)")

    for index, path in enumerate(existing_paths):
        duplicate_rows = con.execute(
            f"""
            SELECT count(*) - count(DISTINCT (date, symbol))
            FROM read_parquet({_sql_path(path)})
            """
        ).fetchone()[0]
        needs_source_dedupe = duplicate_rows > 0
        row_order_sql = "row_number() OVER ()" if needs_source_dedupe else "0"
        good_path = temp_dir / f"good_{index}.parquet"
        bad_path = temp_dir / f"bad_{index}.parquet"

        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW source_clean AS
            SELECT
                CASE
                    WHEN date IS NULL THEN NULL
                    WHEN regexp_matches(trim(cast(date AS varchar)), '^[0-9]{{8}}$')
                        THEN try_strptime(trim(cast(date AS varchar)), '%Y%m%d')::DATE
                    ELSE try_cast(date AS DATE)
                END AS date,
                {_normalize_symbol_sql("symbol")} AS symbol,
                cast(vendor_symbol AS varchar) AS vendor_symbol,
                try_cast(open AS DOUBLE) AS open,
                try_cast(high AS DOUBLE) AS high,
                try_cast(low AS DOUBLE) AS low,
                try_cast(close AS DOUBLE) AS close,
                try_cast(volume AS DOUBLE) AS volume,
                try_cast(adjusted_close AS DOUBLE) AS adjusted_close,
                cast(source AS varchar) AS source,
                coalesce(try_cast(is_delisted_source AS BOOLEAN), FALSE) AS is_delisted_source,
                {row_order_sql} AS _row_order
            FROM read_parquet({_sql_path(path)})
            """
        )
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW source_filtered AS
            SELECT *
            FROM source_clean
            WHERE {date_filter}
            """
        )
        con.execute(
            f"""
            COPY (
                SELECT {price_columns}, {bad_reason_expr} AS bad_reason
                FROM source_filtered
                WHERE {bad_condition}
            ) TO {_sql_path(bad_path)} (FORMAT PARQUET)
            """
        )
        if needs_source_dedupe:
            con.execute(
                f"""
                INSERT INTO duplicate_source_events
                SELECT date, symbol, source
                FROM (
                    SELECT date, symbol, source, count(*) AS row_count
                    FROM source_filtered
                    WHERE NOT ({bad_condition})
                    GROUP BY date, symbol, source
                    HAVING count(*) > 1
                )
                """
            )
        if needs_source_dedupe:
            good_sql = f"""
                SELECT {price_columns}
                FROM (
                    SELECT
                        date,
                        symbol,
                        vendor_symbol,
                        open,
                        high,
                        low,
                        close,
                        CAST(round(volume) AS BIGINT) AS volume,
                        adjusted_close,
                        source,
                        is_delisted_source,
                        row_number() OVER (PARTITION BY date, symbol ORDER BY _row_order) AS rn
                    FROM source_filtered
                    WHERE NOT ({bad_condition})
                )
                WHERE rn = 1
            """
        else:
            good_sql = f"""
                SELECT
                    date,
                    symbol,
                    vendor_symbol,
                    open,
                    high,
                    low,
                    close,
                    CAST(round(volume) AS BIGINT) AS volume,
                    adjusted_close,
                    source,
                    is_delisted_source
                FROM source_filtered
                WHERE NOT ({bad_condition})
            """
        con.execute(f"COPY ({good_sql}) TO {_sql_path(good_path)} (FORMAT PARQUET)")
        good_count = con.execute(f"SELECT count(*) FROM read_parquet({_sql_path(good_path)})").fetchone()[0]
        if good_count:
            source = con.execute(
                f"SELECT source FROM read_parquet({_sql_path(good_path)}) WHERE source IS NOT NULL LIMIT 1"
            ).fetchone()
            source_name = source[0] if source else ""
            priority = SOURCE_PRIORITY.get(source_name, 99)
            cleaned_sources.append((priority, good_path, source_name))
        bad_paths.append(bad_path)
        print(
            f"[normalize] Prepared {path.name}: {good_count:,} good rows, {duplicate_rows:,} raw duplicate rows",
            flush=True,
        )

    con.execute("CREATE TABLE selected_keys(date DATE, symbol VARCHAR)")
    con.execute("CREATE TABLE selected_sources(date DATE, symbol VARCHAR, selected_source VARCHAR)")
    selected_parts: list[Path] = []
    for index, (_priority, good_path, _source_name) in enumerate(sorted(cleaned_sources, key=lambda item: item[0])):
        part_path = temp_dir / f"selected_{index}.parquet"
        con.execute(
            f"""
            INSERT INTO duplicate_source_events
            SELECT g.date, g.symbol, s.selected_source
            FROM read_parquet({_sql_path(good_path)}) g
            JOIN selected_sources s USING (date, symbol)
            """
        )
        con.execute(
            f"""
            INSERT INTO duplicate_source_events
            SELECT g.date, g.symbol, g.source
            FROM read_parquet({_sql_path(good_path)}) g
            JOIN selected_sources s USING (date, symbol)
            """
        )
        con.execute(
            f"""
            COPY (
                SELECT g.*
                FROM read_parquet({_sql_path(good_path)}) g
                LEFT JOIN selected_keys k USING (date, symbol)
                WHERE k.symbol IS NULL
            ) TO {_sql_path(part_path)} (FORMAT PARQUET)
            """
        )
        part_count = con.execute(f"SELECT count(*) FROM read_parquet({_sql_path(part_path)})").fetchone()[0]
        if part_count:
            con.execute(
                f"""
                INSERT INTO selected_keys
                SELECT date, symbol
                FROM read_parquet({_sql_path(part_path)})
                """
            )
            con.execute(
                f"""
                INSERT INTO selected_sources
                SELECT date, symbol, source AS selected_source
                FROM read_parquet({_sql_path(part_path)})
                """
            )
            selected_parts.append(part_path)
        print(f"[normalize] Selected {part_count:,} rows from {good_path.name}", flush=True)

    if selected_parts:
        con.execute(
            f"""
            COPY (
                SELECT {price_columns}
                FROM {_read_parquet_expr(selected_parts)}
            ) TO {_sql_path(daily_prices_path)} (FORMAT PARQUET)
            """
        )
    else:
        write_parquet(empty_frame(config.CANONICAL_PRICE_COLUMNS), daily_prices_path)

    if bad_paths:
        con.execute(
            f"""
            COPY (
                SELECT {", ".join(config.CANONICAL_PRICE_COLUMNS + ["bad_reason"])}
                FROM {_read_parquet_expr(bad_paths)}
            ) TO {_sql_path(bad_rows_report_path)} (FORMAT PARQUET)
            """
        )
    else:
        write_parquet(empty_frame(config.CANONICAL_PRICE_COLUMNS + ["bad_reason"]), bad_rows_report_path)

    duplicate_event_count = con.execute("SELECT count(*) FROM duplicate_source_events").fetchone()[0]
    if duplicate_event_count:
        con.execute(
            f"""
            COPY (
                WITH duplicate_sources AS (
                    SELECT
                        date,
                        symbol,
                        string_agg(source, ',' ORDER BY source) AS sources_found
                    FROM (
                        SELECT DISTINCT date, symbol, source
                        FROM duplicate_source_events
                        WHERE source IS NOT NULL
                    )
                    GROUP BY date, symbol
                )
                SELECT
                    ds.date,
                    ds.symbol,
                    coalesce(ds.sources_found, '') AS sources_found,
                    s.selected_source
                FROM duplicate_sources ds
                LEFT JOIN selected_sources s USING (date, symbol)
                ORDER BY ds.date, ds.symbol
            ) TO {_sql_path(duplicate_report_path)} (FORMAT PARQUET)
            """
        )
    else:
        write_parquet(
            pd.DataFrame(columns=["date", "symbol", "sources_found", "selected_source"]),
            duplicate_report_path,
        )

    con.execute(
        f"""
        CREATE TEMP VIEW daily_prices AS
        SELECT *
        FROM read_parquet({_sql_path(daily_prices_path)})
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE symbol_vendor_symbols AS
        SELECT
            symbol,
            string_agg(vendor_symbol, ',' ORDER BY vendor_symbol) AS vendor_symbol
        FROM (
            SELECT DISTINCT symbol, vendor_symbol
            FROM daily_prices
            WHERE vendor_symbol IS NOT NULL
        )
        GROUP BY symbol
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE symbol_sources AS
        SELECT
            symbol,
            string_agg(source, ',' ORDER BY source) AS source_list
        FROM (
            SELECT DISTINCT symbol, source
            FROM daily_prices
            WHERE source IS NOT NULL
        )
        GROUP BY symbol
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE symbol_master AS
        SELECT
            s.symbol,
            coalesce(v.vendor_symbol, '') AS vendor_symbol,
            s.first_date,
            s.last_date,
            coalesce(src.source_list, '') AS source_list,
            CAST(s.has_active_source AS BOOLEAN) AS has_active_source,
            CAST(s.has_delisted_source AS BOOLEAN) AS has_delisted_source,
            s.observation_count
        FROM (
            SELECT
                symbol,
                min(date) AS first_date,
                max(date) AS last_date,
                max(CASE WHEN source IN ('stooq', 'yahoo_fallback') THEN 1 ELSE 0 END) AS has_active_source,
                max(CASE WHEN source IN ('kaggle_arandkei_delisted', 'yahoo_delisted_probe') THEN 1 ELSE 0 END)
                    AS has_delisted_source,
                count(*) AS observation_count
            FROM daily_prices
            GROUP BY symbol
        ) s
        LEFT JOIN symbol_vendor_symbols v USING (symbol)
        LEFT JOIN symbol_sources src USING (symbol)
        ORDER BY s.symbol
        """
    )

    con.execute(f"COPY symbol_master TO {_sql_path(symbol_master_path)} (FORMAT PARQUET)")

    daily_count = con.execute(f"SELECT count(*) FROM read_parquet({_sql_path(daily_prices_path)})").fetchone()[0]
    symbol_count = con.execute("SELECT count(*) FROM symbol_master").fetchone()[0]
    duplicate_count = con.execute(
        f"SELECT count(*) FROM read_parquet({_sql_path(duplicate_report_path)})"
    ).fetchone()[0]
    bad_count = con.execute(f"SELECT count(*) FROM read_parquet({_sql_path(bad_rows_report_path)})").fetchone()[0]
    print(f"[normalize] Wrote {daily_count:,} canonical daily price rows to {daily_prices_path} (duckdb)")
    print(f"[normalize] Wrote {symbol_count:,} symbol rows to {symbol_master_path} (duckdb)")
    print(f"[normalize] Wrote {duplicate_count:,} duplicate groups to {duplicate_report_path} (duckdb)")
    print(f"[normalize] Wrote {bad_count:,} rejected rows to {bad_rows_report_path} (duckdb)")

    con.close()
    shutil.rmtree(temp_dir, ignore_errors=True)
    try:
        temp_dir.parent.rmdir()
    except OSError:
        pass

    daily_prices = pd.DataFrame(columns=config.CANONICAL_PRICE_COLUMNS)
    symbol_master = pd.DataFrame(columns=config.SYMBOL_MASTER_COLUMNS)
    return daily_prices, symbol_master


def normalize_prices(
    staging_paths: list[Path] | None = None,
    start_date: object | None = None,
    end_date: object | None = None,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    duplicate_report_path: Path = config.DUPLICATE_REPORT_PATH,
    bad_rows_report_path: Path = config.BAD_ROWS_REPORT_PATH,
    engine: str = "duckdb",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if engine == "pandas":
        return _normalize_prices_pandas(
            staging_paths=staging_paths,
            start_date=start_date,
            end_date=end_date,
            daily_prices_path=daily_prices_path,
            symbol_master_path=symbol_master_path,
            duplicate_report_path=duplicate_report_path,
            bad_rows_report_path=bad_rows_report_path,
        )
    if engine != "duckdb":
        raise ValueError(f"Unknown normalize engine: {engine}")
    return _normalize_prices_duckdb(
        staging_paths=staging_paths,
        start_date=start_date,
        end_date=end_date,
        daily_prices_path=daily_prices_path,
        symbol_master_path=symbol_master_path,
        duplicate_report_path=duplicate_report_path,
        bad_rows_report_path=bad_rows_report_path,
    )


if __name__ == "__main__":
    config.ensure_directories()
    normalize_prices()
