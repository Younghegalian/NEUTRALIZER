from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
STAGING_DIR = DATA_DIR / "staging"
NORMALIZED_DIR = DATA_DIR / "normalized"
RESEARCH_DIR = DATA_DIR / "research"

RAW_STOOQ_DIR = RAW_DIR / "stooq"
RAW_KAGGLE_DELISTED_DIR = RAW_DIR / "kaggle_delisted"
RAW_FMP_DIR = RAW_DIR / "fmp"
RAW_YAHOO_DIR = RAW_DIR / "yahoo"
RAW_SEC_DIR = RAW_DIR / "sec"

STOOQ_STAGING_PATH = STAGING_DIR / "stooq_daily_prices.parquet"
KAGGLE_DELISTED_STAGING_PATH = STAGING_DIR / "kaggle_delisted_daily_prices.parquet"
FMP_DELISTED_METADATA_PATH = STAGING_DIR / "fmp_delisted_metadata.parquet"
FMP_PROFILE_METADATA_PATH = STAGING_DIR / "fmp_profile_metadata.parquet"
YAHOO_FALLBACK_STAGING_PATH = STAGING_DIR / "yahoo_fallback_daily_prices.parquet"
SEC_DELISTING_FILINGS_PATH = STAGING_DIR / "sec_delisting_filings.parquet"
SEC_FORM345_TICKER_MAP_PATH = STAGING_DIR / "sec_form345_ticker_map.parquet"
SEC_DELISTED_CANDIDATES_PATH = STAGING_DIR / "sec_delisted_candidates.parquet"
SEC_COMPANY_METADATA_PATH = STAGING_DIR / "sec_company_metadata.parquet"
YAHOO_DELISTED_PROBE_STAGING_PATH = STAGING_DIR / "yahoo_delisted_probe_daily_prices.parquet"
YAHOO_DELISTED_COVERAGE_PATH = RESEARCH_DIR / "yahoo_delisted_probe_coverage.parquet"

DAILY_PRICES_PATH = NORMALIZED_DIR / "daily_prices.parquet"
SYMBOL_MASTER_PATH = NORMALIZED_DIR / "symbol_master.parquet"
SECURITY_MASTER_PATH = NORMALIZED_DIR / "security_master.parquet"
DUPLICATE_REPORT_PATH = NORMALIZED_DIR / "duplicate_report.parquet"
BAD_ROWS_REPORT_PATH = NORMALIZED_DIR / "bad_rows_report.parquet"

LIQUIDITY_METRICS_PATH = RESEARCH_DIR / "liquidity_metrics.parquet"
UNIVERSE_MEMBERSHIP_PATH = RESEARCH_DIR / "universe_membership.parquet"
UNIVERSE_STATS_PATH = RESEARCH_DIR / "universe_stats.parquet"
SECURITY_EVENTS_PATH = RESEARCH_DIR / "security_events.parquet"
TERMINAL_EVENTS_PATH = RESEARCH_DIR / "terminal_events.parquet"
BACKTEST_UNIVERSE_MEMBERSHIP_PATH = RESEARCH_DIR / "backtest_universe_membership.parquet"

DUCKDB_PATH = DATA_DIR / "pit_market.duckdb"
UNIVERSE_NAME = "US_DAILY_SURVIVORSHIP_REDUCED_V1"
BACKTEST_UNIVERSE_NAME = "US_DAILY_LIFECYCLE_ADJUSTED_V2"

CANONICAL_PRICE_COLUMNS = [
    "date",
    "symbol",
    "vendor_symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adjusted_close",
    "source",
    "is_delisted_source",
]

SYMBOL_MASTER_COLUMNS = [
    "symbol",
    "vendor_symbol",
    "first_date",
    "last_date",
    "source_list",
    "has_active_source",
    "has_delisted_source",
    "observation_count",
]

SECURITY_MASTER_COLUMNS = [
    "symbol",
    "asset_type",
    "is_etf",
    "instrument_type",
    "security_name",
    "exchange",
    "currency",
    "cik",
    "sic",
    "sic_description",
    "sector",
    "industry",
    "classification_source",
    "sector_source",
]

LIQUIDITY_COLUMNS = [
    "date",
    "symbol",
    "close",
    "volume",
    "dollar_volume",
    "adv20",
    "traded_days_20",
    "next_open",
    "has_next_open",
]

UNIVERSE_COLUMNS = ["date", "universe_name", "symbol", "reason"]
SECURITY_EVENTS_COLUMNS = [
    "symbol",
    "event_type",
    "event_date",
    "source",
    "source_event_id",
    "source_symbol",
    "confidence",
    "notes",
]
TERMINAL_EVENTS_COLUMNS = [
    "symbol",
    "event_date",
    "terminal_date",
    "terminal_price",
    "previous_close",
    "terminal_return",
    "has_terminal_price",
    "price_source",
    "event_source",
    "event_confidence",
    "terminal_policy",
    "notes",
]
BACKTEST_UNIVERSE_COLUMNS = ["date", "universe_name", "symbol", "reason"]
UNIVERSE_STATS_COLUMNS = [
    "date",
    "universe_name",
    "symbol_count",
    "median_close",
    "median_adv20",
    "total_dollar_volume",
    "delisted_source_count",
]


@dataclass(frozen=True)
class DateRange:
    start_date: date | None = None
    end_date: date | None = None


def ensure_directories() -> None:
    for path in [
        RAW_STOOQ_DIR,
        RAW_KAGGLE_DELISTED_DIR,
        RAW_FMP_DIR,
        RAW_YAHOO_DIR,
        RAW_SEC_DIR,
        STAGING_DIR,
        NORMALIZED_DIR,
        RESEARCH_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
