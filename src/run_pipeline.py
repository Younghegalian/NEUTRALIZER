from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src import config
from src.collectors.fmp_delisted_metadata import collect_fmp_delisted_metadata
from src.collectors.fmp_profile_metadata import collect_fmp_profile_metadata
from src.collectors.kaggle_downloader import download_kaggle_delisted_dataset
from src.collectors.kaggle_delisted_loader import load_kaggle_delisted
from src.collectors.sec_company_metadata import collect_sec_company_metadata
from src.collectors.sec_delisting_collector import (
    build_sec_delisted_candidates,
    collect_sec_delisted_candidates,
    collect_sec_delisting_filings,
    collect_sec_form345_ticker_map,
    enrich_sec_delisting_documents,
)
from src.collectors.stooq_downloader import collect_stooq
from src.collectors.yahoo_fallback_downloader import (
    collect_yahoo_active,
    collect_yahoo_delisted_probe,
    collect_yahoo_fallback,
)
from src.db.build_duckdb import build_duckdb
from src.normalize.build_security_master import build_security_master
from src.normalize.normalize_prices import normalize_prices
from src.tools.check_prereqs import check_prereqs
from src.universe.build_backtest_universe import build_backtest_universe
from src.universe.build_universe import build_universe
from src.universe.compute_liquidity import compute_liquidity
from src.universe.universe_stats import build_universe_stats
from src.utils import parse_cli_date, read_parquet_if_exists


FULL_PIPELINE_STEPS = [
    "download_kaggle_delisted",
    "collect_stooq",
    "collect_yahoo_active",
    "collect_sec_delisted_candidates",
    "probe_yahoo_delisted",
    "load_kaggle_delisted",
    "fmp_metadata",
    "normalize",
    "fmp_profiles",
    "sec_company_metadata",
    "security_master",
    "liquidity",
    "universe",
    "backtest_universe",
    "duckdb",
]


def _read_symbols_file(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_step(args: argparse.Namespace, step: str) -> None:
    start_date = parse_cli_date(args.start_date)
    end_date = parse_cli_date(args.end_date)

    if step == "collect_stooq":
        collect_stooq(
            download=not args.no_stooq_download,
            force_download=args.force_stooq_download,
            start_date=start_date,
            end_date=end_date,
            enable_html_fallback=args.enable_stooq_html_fallback,
        )
    elif step == "download_kaggle_delisted":
        if args.skip_kaggle_download:
            print("[kaggle_download] Skipped by --skip-kaggle-download.")
        else:
            download_kaggle_delisted_dataset(force=args.force_kaggle_download)
    elif step == "load_kaggle_delisted":
        load_kaggle_delisted()
    elif step == "fmp_metadata":
        collect_fmp_delisted_metadata()
    elif step == "fmp_profiles":
        collect_fmp_profile_metadata(limit=args.fmp_profile_limit)
    elif step == "sec_company_metadata":
        collect_sec_company_metadata(
            limit=args.sec_company_limit,
            use_bulk=args.sec_company_use_bulk,
            force_bulk_download=args.force_sec_company_bulk_download,
        )
    elif step == "collect_yahoo":
        symbols = _read_symbols_file(args.yahoo_symbols_file)
        if not symbols:
            print("[yahoo_fallback] No symbols file supplied; skipping Yahoo fallback collection.")
            return
        if start_date is None or end_date is None:
            raise ValueError("Yahoo fallback requires --start-date and --end-date.")
        collect_yahoo_fallback(symbols=symbols, start_date=start_date, end_date=end_date)
    elif step == "collect_yahoo_active":
        if start_date is None or end_date is None:
            raise ValueError("Yahoo active collection requires --start-date and --end-date.")
        collect_yahoo_active(
            start_date=start_date,
            end_date=end_date,
            max_workers=args.yahoo_workers,
            limit=args.yahoo_limit,
            force=args.force_yahoo_refresh,
        )
    elif step == "collect_sec_delisting_filings":
        collect_sec_delisting_filings(start_year=args.sec_start_year, end_year=args.sec_end_year)
    elif step == "enrich_sec_delisting_documents":
        enrich_sec_delisting_documents(limit=args.sec_doc_limit)
    elif step == "collect_sec_form345":
        collect_sec_form345_ticker_map(start_year=args.sec_start_year, end_year=args.sec_end_year)
    elif step == "build_sec_delisted_candidates":
        build_sec_delisted_candidates()
    elif step == "collect_sec_delisted_candidates":
        collect_sec_delisted_candidates(
            start_year=args.sec_start_year,
            end_year=args.sec_end_year,
            enrich_docs=not args.skip_sec_doc_enrich,
        )
    elif step == "probe_yahoo_delisted":
        if start_date is None or end_date is None:
            raise ValueError("Yahoo delisted probe requires --start-date and --end-date.")
        collect_yahoo_delisted_probe(
            start_date=start_date,
            end_date=end_date,
            max_workers=args.yahoo_workers,
            limit=args.yahoo_limit,
            force=args.force_yahoo_refresh,
        )
    elif step == "normalize":
        normalize_prices(start_date=start_date, end_date=end_date)
    elif step == "security_master":
        build_security_master()
    elif step == "liquidity":
        compute_liquidity()
    elif step == "universe":
        build_universe()
        build_universe_stats()
    elif step == "backtest_universe":
        build_backtest_universe()
    elif step == "duckdb":
        build_duckdb()
    elif step == "check":
        check_prereqs()
    else:
        raise ValueError(f"Unknown step: {step}")


def _safe_min_max(series: pd.Series) -> tuple[str, str]:
    if series.empty:
        return "n/a", "n/a"
    values = pd.to_datetime(series, errors="coerce").dropna()
    if values.empty:
        return "n/a", "n/a"
    return str(values.min().date()), str(values.max().date())


def print_summary() -> None:
    daily_prices = read_parquet_if_exists(config.DAILY_PRICES_PATH, config.CANONICAL_PRICE_COLUMNS)
    symbol_master = read_parquet_if_exists(config.SYMBOL_MASTER_PATH, config.SYMBOL_MASTER_COLUMNS)
    universe_membership = read_parquet_if_exists(config.UNIVERSE_MEMBERSHIP_PATH, config.UNIVERSE_COLUMNS)
    backtest_universe = read_parquet_if_exists(
        config.BACKTEST_UNIVERSE_MEMBERSHIP_PATH,
        config.BACKTEST_UNIVERSE_COLUMNS,
    )
    universe_stats = read_parquet_if_exists(config.UNIVERSE_STATS_PATH, config.UNIVERSE_STATS_COLUMNS)

    date_start, date_end = _safe_min_max(daily_prices["date"]) if "date" in daily_prices else ("n/a", "n/a")
    universe_start, universe_end = (
        _safe_min_max(universe_membership["date"])
        if "date" in universe_membership
        else ("n/a", "n/a")
    )

    if not symbol_master.empty:
        symbols_total = len(symbol_master)
        active_symbols = int(symbol_master["has_active_source"].fillna(False).sum())
        delisted_symbols = int(symbol_master["has_delisted_source"].fillna(False).sum())
    else:
        symbols_total = active_symbols = delisted_symbols = 0

    if not universe_stats.empty and "symbol_count" in universe_stats:
        median_universe_count = universe_stats["symbol_count"].median()
        median_universe_count_text = "n/a" if pd.isna(median_universe_count) else f"{median_universe_count:.0f}"
    else:
        median_universe_count_text = "n/a"

    print()
    print("FONA market DB build complete.")
    print()
    print(f"Date range: {date_start} to {date_end}")
    print(f"Symbols total: {symbols_total:,}")
    print(f"Active-source symbols: {active_symbols:,}")
    print(f"Delisted-source symbols: {delisted_symbols:,}")
    print(f"Daily price rows: {len(daily_prices):,}")
    print(f"Universe name: {config.UNIVERSE_NAME}")
    print(f"Universe start: {universe_start}")
    print(f"Universe end: {universe_end}")
    print(f"Median universe count: {median_universe_count_text}")
    print(f"Backtest universe name: {config.BACKTEST_UNIVERSE_NAME}")
    print(f"Backtest universe rows: {len(backtest_universe):,}")
    print(f"DuckDB path: {config.DUCKDB_PATH}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the FONA local market database.")
    parser.add_argument("--start-date", default="2010-01-01", help="Inclusive start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", default="today", help="Inclusive end date, YYYY-MM-DD or today.")
    parser.add_argument(
        "--step",
        choices=[
            *FULL_PIPELINE_STEPS,
            "collect_yahoo",
            "collect_sec_delisting_filings",
            "enrich_sec_delisting_documents",
            "collect_sec_form345",
            "build_sec_delisted_candidates",
            "check",
        ],
        help="Run one pipeline step instead of the full pipeline.",
    )
    parser.add_argument(
        "--no-stooq-download",
        action="store_true",
        help="Normalize existing Stooq raw files without downloading the Stooq archive.",
    )
    parser.add_argument(
        "--force-stooq-download",
        action="store_true",
        help="Download the Stooq archive even if a local copy already exists.",
    )
    parser.add_argument(
        "--enable-stooq-html-fallback",
        action="store_true",
        help="Use Stooq HTML screen scraping if the bulk archive is unavailable. This is slow and incomplete.",
    )
    parser.add_argument(
        "--skip-kaggle-download",
        action="store_true",
        help="Skip automatic Kaggle delisted archive download during a full pipeline run.",
    )
    parser.add_argument(
        "--force-kaggle-download",
        action="store_true",
        help="Force re-download of the Kaggle delisted archive.",
    )
    parser.add_argument(
        "--yahoo-symbols-file",
        type=Path,
        help="Optional newline-delimited symbols file for Yahoo fallback collection.",
    )
    parser.add_argument("--yahoo-workers", type=int, default=12, help="Parallel workers for Yahoo active collection.")
    parser.add_argument("--yahoo-limit", type=int, help="Optional cap for Yahoo active symbols, useful for testing.")
    parser.add_argument(
        "--force-yahoo-refresh",
        action="store_true",
        help="Re-download Yahoo JSON even when a cached raw file already exists.",
    )
    parser.add_argument("--sec-start-year", type=int, default=2010, help="First SEC index year to collect.")
    parser.add_argument("--sec-end-year", type=int, help="Last SEC index year to collect.")
    parser.add_argument("--sec-doc-limit", type=int, help="Optional cap for SEC document enrichment.")
    parser.add_argument(
        "--fmp-profile-limit",
        type=int,
        default=0,
        help="Maximum new FMP profile requests for sector/industry enrichment; cached profiles are always parsed.",
    )
    parser.add_argument(
        "--sec-company-limit",
        type=int,
        default=0,
        help=(
            "Maximum new SEC submissions requests for CIK/SIC enrichment; "
            "cached submissions are always parsed. Use -1 for uncapped."
        ),
    )
    parser.add_argument(
        "--sec-company-use-bulk",
        action="store_true",
        help="Use the SEC nightly submissions.zip bulk archive for CIK/SIC enrichment.",
    )
    parser.add_argument(
        "--force-sec-company-bulk-download",
        action="store_true",
        help="Re-download the SEC submissions.zip bulk archive even when cached.",
    )
    parser.add_argument(
        "--skip-sec-doc-enrich",
        action="store_true",
        help="Build SEC candidates without fetching individual Form 25 documents.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    config.ensure_directories()
    parser = build_parser()
    args = parser.parse_args(argv)

    steps = [args.step] if args.step else FULL_PIPELINE_STEPS
    for step in steps:
        print(f"[pipeline] Running step: {step}")
        run_step(args, step)

    if args.step != "check":
        print_summary()


if __name__ == "__main__":
    main()
