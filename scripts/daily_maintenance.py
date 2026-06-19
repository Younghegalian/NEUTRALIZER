from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from _operator_common import PROJECT_ROOT, env_flag, resolve_python, run_python_module


def _current_sec_quarter_paths(today: date) -> list[Path]:
    quarter = ((today.month - 1) // 3) + 1
    return [
        PROJECT_ROOT / "data" / "raw" / "sec" / "full-index" / f"{today.year}q{quarter}_master.idx",
        PROJECT_ROOT / "data" / "raw" / "sec" / "form345" / f"{today.year}q{quarter}_form345.zip",
    ]


def _remove_current_sec_cache() -> None:
    for path in _current_sec_quarter_paths(date.today()):
        if path.exists():
            path.unlink()
            print(f"Refreshed cache by removing {path}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the cross-platform FONA daily maintenance workflow.")
    parser.add_argument("--start-date", default=None, help="Pipeline start date, YYYY-MM-DD. Default: FONA_START_DATE or 2010-01-01.")
    parser.add_argument("--end-date", default="today", help="Pipeline end date. Default: today.")
    parser.add_argument("--yahoo-workers", default=None, help="Yahoo worker count. Default: FONA_YAHOO_WORKERS or 6.")
    parser.add_argument("--fmp-profile-limit", default=None, help="New FMP profile request cap. Default: FONA_FMP_PROFILE_LIMIT or 0.")
    parser.add_argument("--sec-company-limit", default=None, help="New SEC submissions request cap. Default: FONA_SEC_COMPANY_LIMIT or 0.")
    parser.add_argument(
        "--sec-company-use-bulk",
        action=argparse.BooleanOptionalAction,
        default=env_flag("FONA_SEC_COMPANY_USE_BULK"),
        help="Use the SEC nightly submissions.zip bulk archive.",
    )
    parser.add_argument(
        "--force-sec-company-bulk-download",
        action=argparse.BooleanOptionalAction,
        default=env_flag("FONA_FORCE_SEC_COMPANY_BULK_DOWNLOAD"),
        help="Re-download the SEC submissions.zip bulk archive.",
    )
    parser.add_argument(
        "--fetch-market-flow-benchmarks",
        action=argparse.BooleanOptionalAction,
        default=env_flag("FONA_FETCH_MARKET_FLOW_BENCHMARKS"),
        help="Fetch live public listing/delisting benchmark inputs for the flow audit.",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip the final unittest run.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved configuration without running pipeline steps.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python = resolve_python()
    start_date = args.start_date or os.environ.get("FONA_START_DATE", "2010-01-01")
    yahoo_workers = args.yahoo_workers or os.environ.get("FONA_YAHOO_WORKERS", "6")
    fmp_profile_limit = args.fmp_profile_limit or os.environ.get("FONA_FMP_PROFILE_LIMIT", "0")
    sec_company_limit = args.sec_company_limit or os.environ.get("FONA_SEC_COMPANY_LIMIT", "0")

    print("FONA daily maintenance", flush=True)
    print(f"Project: {PROJECT_ROOT}", flush=True)
    print(f"Python: {python}", flush=True)
    print(f"Date range: {start_date} to {args.end_date}", flush=True)
    print(f"Yahoo workers: {yahoo_workers}", flush=True)
    print(f"FMP profile limit: {fmp_profile_limit}", flush=True)
    print(f"SEC company limit: {sec_company_limit}", flush=True)
    print(f"SEC company bulk: {args.sec_company_use_bulk}", flush=True)
    print(f"Market-flow benchmark fetch: {args.fetch_market_flow_benchmarks}", flush=True)

    if args.dry_run:
        print("Dry run complete.", flush=True)
        return 0

    _remove_current_sec_cache()

    run_python_module(python, "src.run_pipeline", "--step", "check")
    run_python_module(
        python,
        "src.run_pipeline",
        "--step",
        "collect_yahoo_active",
        "--start-date",
        start_date,
        "--end-date",
        args.end_date,
        "--yahoo-workers",
        yahoo_workers,
        "--force-yahoo-refresh",
    )
    run_python_module(
        python,
        "src.run_pipeline",
        "--step",
        "collect_sec_delisted_candidates",
        "--sec-start-year",
        "2010",
        "--skip-sec-doc-enrich",
    )
    run_python_module(
        python,
        "src.run_pipeline",
        "--step",
        "probe_yahoo_delisted",
        "--start-date",
        start_date,
        "--end-date",
        args.end_date,
        "--yahoo-workers",
        yahoo_workers,
    )
    run_python_module(python, "src.run_pipeline", "--step", "load_kaggle_delisted", "--start-date", start_date, "--end-date", args.end_date)
    run_python_module(python, "src.run_pipeline", "--step", "fmp_metadata", "--start-date", start_date, "--end-date", args.end_date)
    run_python_module(python, "src.run_pipeline", "--step", "normalize", "--start-date", start_date, "--end-date", args.end_date)
    run_python_module(python, "src.run_pipeline", "--step", "fmp_profiles", "--fmp-profile-limit", fmp_profile_limit)

    sec_company_args: list[object] = ["--step", "sec_company_metadata", "--sec-company-limit", sec_company_limit]
    if args.sec_company_use_bulk:
        sec_company_args.append("--sec-company-use-bulk")
    if args.force_sec_company_bulk_download:
        sec_company_args.append("--force-sec-company-bulk-download")
    run_python_module(python, "src.run_pipeline", *sec_company_args)

    for step in [
        "security_master",
        "corporate_action_evidence",
        "liquidity",
        "universe",
        "backtest_universe",
        "delisting_outcomes",
        "terminal_event_validity",
        "symbol_aliases",
        "duckdb",
    ]:
        run_python_module(python, "src.run_pipeline", "--step", step)

    run_python_module(python, "src.tools.audit_daily_prices")

    market_flow_args: list[object] = ["--output", str(Path("data") / "research" / "market_flow_audit.csv")]
    if args.fetch_market_flow_benchmarks:
        market_flow_args.append("--fetch-benchmarks")
    run_python_module(python, "src.tools.audit_market_flows", *market_flow_args)

    if not args.skip_tests:
        run_python_module(python, "unittest", "discover", "-s", "tests")

    print("FONA daily maintenance complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
