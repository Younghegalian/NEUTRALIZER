from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd
import requests

from src import config


STOCKANALYSIS_BASE_URL = "https://stockanalysis.com/actions"
WORLD_BANK_LISTED_URL = (
    "https://api.worldbank.org/v2/country/USA/indicator/"
    "CM.MKT.LDOM.NO?format=json&per_page=100"
)

WORLD_BANK_LISTED_DOMESTIC_US_FALLBACK = {
    2010: 4279,
    2011: 4171,
    2012: 4102,
    2013: 4180,
    2014: 4369,
    2015: 4381,
    2016: 4331,
    2017: 4336,
    2018: 4013,
    2019: 3910,
    2020: 4104,
    2021: 4774,
    2022: 4642,
    2023: 4317,
    2024: 4010,
    2025: 3908,
}

STOCKANALYSIS_LISTED_FALLBACK = {
    2010: 239,
    2011: 180,
    2012: 228,
    2013: 308,
    2014: 395,
    2015: 295,
    2016: 221,
    2017: 309,
    2018: 368,
    2019: 317,
    2020: 513,
    2021: 928,
    2022: 237,
    2023: 223,
    2024: 265,
    2025: 333,
    2026: 141,
}

STOCKANALYSIS_DELISTED_FALLBACK = {
    2010: 291,
    2011: 273,
    2012: 278,
    2013: 244,
    2014: 234,
    2015: 308,
    2016: 335,
    2017: 321,
    2018: 289,
    2019: 278,
    2020: 252,
    2021: 364,
    2022: 374,
    2023: 486,
    2024: 411,
    2025: 376,
    2026: 172,
}


@dataclass(frozen=True)
class Scope:
    name: str
    where_sql: str


SCOPES = [
    Scope("all_universe", "TRUE"),
    Scope("stock_universe", "sec.asset_type = 'stock'"),
    Scope(
        "stock_major_universe",
        "sec.asset_type = 'stock' AND COALESCE(sec.exchange, '') NOT ILIKE '%OTC%'",
    ),
]


def _year_range(start_year: int, end_year: int) -> list[int]:
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")
    return list(range(start_year, end_year + 1))


def _stockanalysis_fallback(year: int, action: str) -> int | None:
    if action == "listed":
        return STOCKANALYSIS_LISTED_FALLBACK.get(year)
    if action == "delisted":
        return STOCKANALYSIS_DELISTED_FALLBACK.get(year)
    return None


def _fetch_stockanalysis_action_count(year: int, action: str) -> int | None:
    url = f"{STOCKANALYSIS_BASE_URL}/{action}/{year}/"
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "FONA/1.0"})
        response.raise_for_status()
        match = re.search(r"Showing\s+\d+\s+of\s+([0-9,]+)", response.text)
        if match:
            return int(match.group(1).replace(",", ""))
    except requests.RequestException as exc:
        print(f"[audit] benchmark fetch warning: {url} ({exc})")
    return _stockanalysis_fallback(year, action)


def _fetch_world_bank_listed_counts(years: Iterable[int]) -> dict[int, int]:
    wanted = set(years)
    try:
        response = requests.get(
            WORLD_BANK_LISTED_URL,
            timeout=30,
            headers={"User-Agent": "FONA/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and len(payload) >= 2:
            counts: dict[int, int] = {}
            for row in payload[1]:
                value = row.get("value")
                if value is None:
                    continue
                year = int(row["date"])
                if year in wanted:
                    counts[year] = int(value)
            if counts:
                return counts
    except requests.RequestException as exc:
        print(f"[audit] benchmark fetch warning: {WORLD_BANK_LISTED_URL} ({exc})")

    return {year: count for year, count in WORLD_BANK_LISTED_DOMESTIC_US_FALLBACK.items() if year in wanted}


def fetch_public_benchmarks(start_year: int, end_year: int) -> pd.DataFrame:
    years = _year_range(start_year, end_year)
    listed_counts = _fetch_world_bank_listed_counts(years)
    rows = []
    for year in years:
        listed_actions = _fetch_stockanalysis_action_count(year, "listed")
        delisted_actions = _fetch_stockanalysis_action_count(year, "delisted")
        listed_company_count = listed_counts.get(year)
        rows.append(
            {
                "year": year,
                "benchmark_listed_company_count": listed_company_count,
                "benchmark_new_listed": listed_actions,
                "benchmark_delisted": delisted_actions,
                "benchmark_listing_rate_pct": _pct(listed_actions, listed_company_count),
                "benchmark_delisting_rate_pct": _pct(delisted_actions, listed_company_count),
            }
        )
    return pd.DataFrame(rows)


def _pct(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(float(numerator) * 100.0 / float(denominator), 2)


def _quote_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _scope_sql(scope: Scope) -> str:
    return f"""
    WITH scoped_universe AS (
        SELECT
            um.date,
            um.symbol,
            sec.asset_type,
            sec.exchange,
            sm.has_delisted_source
        FROM universe_membership um
        JOIN symbol_master sm USING(symbol)
        LEFT JOIN security_master sec USING(symbol)
        WHERE um.universe_name = '{config.UNIVERSE_NAME}'
          AND {scope.where_sql}
    ),
    daily_counts AS (
        SELECT
            YEAR(date)::INTEGER AS year,
            date,
            COUNT(DISTINCT symbol) AS daily_symbols,
            COUNT(DISTINCT CASE WHEN has_delisted_source THEN symbol END) AS daily_delisted_source_symbols
        FROM scoped_universe
        GROUP BY 1, 2
    ),
    first_daily_counts AS (
        SELECT year, daily_symbols AS first_day_symbols
        FROM (
            SELECT
                year,
                daily_symbols,
                ROW_NUMBER() OVER (PARTITION BY year ORDER BY date) AS rn
            FROM daily_counts
        )
        WHERE rn = 1
    ),
    last_daily_counts AS (
        SELECT year, daily_symbols AS last_day_symbols
        FROM (
            SELECT
                year,
                daily_symbols,
                ROW_NUMBER() OVER (PARTITION BY year ORDER BY date DESC) AS rn
            FROM daily_counts
        )
        WHERE rn = 1
    ),
    annual_counts AS (
        SELECT
            year,
            ROUND(AVG(daily_symbols), 2) AS avg_daily_symbols,
            MAX(daily_symbols) AS max_daily_symbols,
            ROUND(AVG(daily_delisted_source_symbols), 2) AS avg_daily_delisted_source_symbols
        FROM daily_counts
        GROUP BY 1
    ),
    symbol_life AS (
        SELECT
            symbol,
            MIN(YEAR(date))::INTEGER AS first_year,
            MAX(YEAR(date))::INTEGER AS last_year,
            BOOL_OR(has_delisted_source) AS has_delisted_source
        FROM scoped_universe
        GROUP BY 1
    ),
    observed_years AS (
        SELECT MIN(year) AS min_year, MAX(year) AS max_year
        FROM annual_counts
    ),
    annual_life AS (
        SELECT
            y.year,
            COUNT(DISTINCT CASE WHEN l.first_year = y.year THEN l.symbol END) AS new_to_universe,
            COUNT(DISTINCT CASE WHEN l.first_year = y.year AND l.has_delisted_source THEN l.symbol END) AS new_delisted_source_symbols,
            COUNT(DISTINCT CASE WHEN l.last_year = y.year AND y.year < oy.max_year THEN l.symbol END) AS left_universe_completed,
            COUNT(DISTINCT CASE WHEN l.last_year = y.year AND y.year < oy.max_year AND l.has_delisted_source THEN l.symbol END) AS left_universe_delisted_source_completed
        FROM annual_counts y
        CROSS JOIN observed_years oy
        CROSS JOIN symbol_life l
        GROUP BY y.year
    )
    SELECT
        '{scope.name}' AS scope,
        ac.year,
        f.first_day_symbols,
        l.last_day_symbols,
        ac.avg_daily_symbols,
        ac.max_daily_symbols,
        ac.avg_daily_delisted_source_symbols,
        al.new_to_universe,
        al.new_delisted_source_symbols,
        al.left_universe_completed,
        al.left_universe_delisted_source_completed,
        ROUND(100.0 * al.new_to_universe / NULLIF(f.first_day_symbols, 0), 2) AS db_listing_rate_pct,
        ROUND(100.0 * al.left_universe_completed / NULLIF(f.first_day_symbols, 0), 2) AS db_exit_rate_pct,
        ROUND(100.0 * al.left_universe_delisted_source_completed / NULLIF(f.first_day_symbols, 0), 2) AS db_delisted_source_exit_rate_pct
    FROM annual_counts ac
    JOIN first_daily_counts f USING(year)
    JOIN last_daily_counts l USING(year)
    JOIN annual_life al USING(year)
    ORDER BY ac.year
    """


def compute_db_flows(db_path: Path = config.DUCKDB_PATH) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(f"Missing DuckDB database: {db_path}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        frames = [con.execute(_scope_sql(scope)).fetchdf() for scope in SCOPES]
    return pd.concat(frames, ignore_index=True)


def compute_sec_candidate_counts(db_path: Path = config.DUCKDB_PATH) -> pd.DataFrame:
    if not config.SEC_DELISTED_CANDIDATES_PATH.exists():
        return pd.DataFrame(columns=["year", "sec_candidate_filings", "sec_candidate_ciks", "sec_candidate_symbols"])

    parquet_path = _quote_path(config.SEC_DELISTED_CANDIDATES_PATH)
    query = f"""
    WITH sec_candidates AS (
        SELECT
            YEAR(date_filed)::INTEGER AS year,
            cik,
            NULLIF(TRIM(UPPER(candidate_symbol)), '') AS raw_candidate_symbol,
            REGEXP_REPLACE(NULLIF(TRIM(UPPER(candidate_symbol)), ''), '[^A-Z0-9]', '', 'g') AS compact_candidate_symbol
        FROM read_parquet('{parquet_path}')
    ),
    symbol_aliases AS (
        SELECT
            symbol,
            has_delisted_source,
            REGEXP_REPLACE(UPPER(symbol), '[^A-Z0-9]', '', 'g') AS compact_symbol
        FROM symbol_master
    ),
    matched AS (
        SELECT
            c.year,
            c.cik,
            c.raw_candidate_symbol,
            s.symbol,
            s.has_delisted_source
        FROM sec_candidates c
        LEFT JOIN symbol_aliases s
          ON c.compact_candidate_symbol = s.compact_symbol
        WHERE c.raw_candidate_symbol IS NOT NULL
    ),
    candidate_annual AS (
        SELECT
            year,
            COUNT(*) AS sec_candidate_rows,
            COUNT(DISTINCT cik) AS sec_candidate_ciks,
            COUNT(DISTINCT raw_candidate_symbol) AS sec_candidate_symbols
        FROM sec_candidates
        GROUP BY 1
    ),
    matched_annual AS (
        SELECT
            year,
            COUNT(DISTINCT symbol) FILTER (WHERE symbol IS NOT NULL) AS sec_candidate_any_price_symbols,
            COUNT(DISTINCT symbol) FILTER (WHERE has_delisted_source) AS sec_candidate_price_recovered_delisted_symbols
        FROM matched
        GROUP BY 1
    )
    SELECT
        c.year,
        c.sec_candidate_rows,
        c.sec_candidate_ciks,
        c.sec_candidate_symbols,
        COALESCE(m.sec_candidate_any_price_symbols, 0) AS sec_candidate_any_price_symbols,
        COALESCE(m.sec_candidate_price_recovered_delisted_symbols, 0) AS sec_candidate_price_recovered_delisted_symbols,
        ROUND(
            100.0 * COALESCE(m.sec_candidate_price_recovered_delisted_symbols, 0)
            / NULLIF(c.sec_candidate_symbols, 0),
            2
        ) AS sec_candidate_price_recovery_pct
    FROM candidate_annual c
    LEFT JOIN matched_annual m USING(year)
    ORDER BY c.year
    """
    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute(query).fetchdf()


def compute_fmp_metadata_counts() -> pd.DataFrame:
    if not config.FMP_DELISTED_METADATA_PATH.exists():
        return pd.DataFrame(columns=["year", "fmp_delisted_metadata_symbols"])

    parquet_path = _quote_path(config.FMP_DELISTED_METADATA_PATH)
    query = f"""
    SELECT
        YEAR(delistedDate)::INTEGER AS year,
        COUNT(DISTINCT symbol) AS fmp_delisted_metadata_symbols
    FROM read_parquet('{parquet_path}')
    WHERE delistedDate IS NOT NULL
    GROUP BY 1
    ORDER BY 1
    """
    with duckdb.connect(database=":memory:") as con:
        return con.execute(query).fetchdf()


def build_market_flow_audit(
    db_path: Path = config.DUCKDB_PATH,
    fetch_benchmarks: bool = False,
) -> pd.DataFrame:
    flows = compute_db_flows(db_path)
    sec_counts = compute_sec_candidate_counts(db_path)
    fmp_counts = compute_fmp_metadata_counts()

    result = flows.merge(sec_counts, on="year", how="left")
    result = result.merge(fmp_counts, on="year", how="left")

    if fetch_benchmarks and not result.empty:
        start_year = int(result["year"].min())
        end_year = int(result["year"].max())
        benchmarks = fetch_public_benchmarks(start_year, end_year)
        result = result.merge(benchmarks, on="year", how="left")

        result["delisted_capture_vs_benchmark_pct"] = (
            result["sec_candidate_price_recovered_delisted_symbols"]
            .astype("float64")
            .mul(100.0)
            .div(result["benchmark_delisted"].replace({0: pd.NA}))
            .round(2)
        )
        result["db_recovered_delisting_rate_pct"] = (
            result["sec_candidate_price_recovered_delisted_symbols"]
            .astype("float64")
            .mul(100.0)
            .div(result["benchmark_listed_company_count"].replace({0: pd.NA}))
            .round(2)
        )
        result["new_listing_capture_vs_benchmark_pct"] = (
            result["new_to_universe"]
            .astype("float64")
            .mul(100.0)
            .div(result["benchmark_new_listed"].replace({0: pd.NA}))
            .round(2)
        )

    return result


def write_outputs(frame: pd.DataFrame, output: Path | None, json_output: Path | None) -> None:
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)
        print(f"[audit] wrote CSV: {output}")
    if json_output is not None:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        records = json.loads(frame.to_json(orient="records", date_format="iso"))
        json_output.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"[audit] wrote JSON: {json_output}")


def audit_market_flows(
    db_path: Path = config.DUCKDB_PATH,
    fetch_benchmarks: bool = False,
    output: Path | None = None,
    json_output: Path | None = None,
    print_scope: str = "stock_major_universe",
) -> int:
    frame = build_market_flow_audit(db_path=db_path, fetch_benchmarks=fetch_benchmarks)
    write_outputs(frame, output, json_output)

    print("[audit] market flow profile")
    if print_scope:
        printable = frame[frame["scope"] == print_scope].copy()
    else:
        printable = frame.copy()
    print(printable.to_string(index=False))

    completed = frame[frame["year"] < frame["year"].max()]
    major_completed = completed[completed["scope"] == "stock_major_universe"]
    if major_completed.empty:
        return 0

    median_exit_rate = major_completed["db_exit_rate_pct"].median()
    median_delisted_exit_rate = major_completed["db_delisted_source_exit_rate_pct"].median()
    print()
    print(
        "[audit] stock_major_universe completed-year medians: "
        f"exit_rate={median_exit_rate:.2f}%, "
        f"delisted_source_exit_rate={median_delisted_exit_rate:.2f}%"
    )

    if fetch_benchmarks and "benchmark_delisting_rate_pct" in major_completed:
        comparison = major_completed.dropna(subset=["benchmark_delisting_rate_pct"])
        if not comparison.empty:
            benchmark_median = comparison["benchmark_delisting_rate_pct"].median()
            capture_median = comparison["delisted_capture_vs_benchmark_pct"].median()
            print(
                "[audit] public benchmark medians: "
                f"delisting_rate={benchmark_median:.2f}%, "
                f"captured_delisted_events={capture_median:.2f}%"
            )

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit annual listing and delisting flow rates for the local PIT market DB."
    )
    parser.add_argument("--db-path", type=Path, default=config.DUCKDB_PATH)
    parser.add_argument(
        "--fetch-benchmarks",
        action="store_true",
        help="Fetch StockAnalysis listed/delisted counts and World Bank listed-company counts.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional CSV output path.")
    parser.add_argument("--json-output", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument(
        "--print-scope",
        default="stock_major_universe",
        choices=[scope.name for scope in SCOPES] + ["all"],
        help="Scope to print in the console. Use 'all' to print every scope.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print_scope = "" if args.print_scope == "all" else args.print_scope
    raise SystemExit(
        audit_market_flows(
            db_path=args.db_path,
            fetch_benchmarks=args.fetch_benchmarks,
            output=args.output,
            json_output=args.json_output,
            print_scope=print_scope,
        )
    )


if __name__ == "__main__":
    main()
