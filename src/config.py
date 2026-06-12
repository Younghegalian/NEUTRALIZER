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
SEC_DELISTING_OUTCOME_DOCS_PATH = STAGING_DIR / "sec_delisting_outcome_documents.parquet"
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
DELISTING_OUTCOMES_PATH = RESEARCH_DIR / "delisting_outcomes.parquet"
TERMINAL_EVENT_VALIDITY_PATH = RESEARCH_DIR / "terminal_event_validity.parquet"
VALID_TERMINAL_EVENTS_PATH = RESEARCH_DIR / "valid_terminal_events.parquet"
SYMBOL_ALIASES_PATH = RESEARCH_DIR / "symbol_aliases.parquet"
BACKTEST_UNIVERSE_MEMBERSHIP_PATH = RESEARCH_DIR / "backtest_universe_membership.parquet"
PRICE_QUALITY_FLAGS_PATH = RESEARCH_DIR / "price_quality_flags.parquet"

DUCKDB_PATH = DATA_DIR / "pit_market.duckdb"
UNIVERSE_NAME = "US_DAILY_SURVIVORSHIP_REDUCED_V1"
BACKTEST_UNIVERSE_NAME = "US_DAILY_LIFECYCLE_ADJUSTED_V2"

BACKTEST_LABEL_ETF_SEED_SYMBOLS = [
    "AGG",
    "BND",
    "HYG",
    "IEF",
    "LQD",
    "SHY",
    "SOXX",
    "SPLG",
    "TIP",
    "TLT",
]

CURATED_SYMBOL_ALIASES = [
    {
        "canonical_symbol": "FISV",
        "alias_symbol": "FI",
        "start_date": "2023-06-07",
        "end_date": "2025-11-10",
        "action_type": "ticker_change",
        "source": "fiserv_ir_and_nasdaq_trader",
        "notes": (
            "Fiserv traded as FI after its 2023 NYSE transfer and returned to FISV "
            "with its 2025 Nasdaq transfer. Yahoo currently exposes the continuous "
            "history under FISV."
        ),
    },
]

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
    "quality_dollar_volume",
    "adv20",
    "quality_adv20",
    "traded_days_20",
    "quality_traded_days_20",
    "next_open",
    "has_next_open",
    "is_price_quality_suspect",
]
PRICE_QUALITY_FLAG_COLUMNS = [
    "date",
    "symbol",
    "source",
    "flag_reason",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adjusted_close",
    "close_adjusted_ratio",
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
SEC_DELISTING_OUTCOME_DOC_COLUMNS = [
    "symbol",
    "event_date",
    "cik",
    "company_name",
    "form_type",
    "date_filed",
    "filename",
    "candidate_symbol",
    "ticker_source",
    "candidate_symbol_count_for_filing",
    "security_description",
    "signature_date",
    "effective_date",
    "symbols_in_doc",
    "text_available",
    "outcome_type",
    "outcome_confidence",
    "outcome_source",
    "evidence",
    "cash_consideration_per_share",
    "cash_consideration_source",
    "cash_consideration_is_partial",
]
DELISTING_OUTCOMES_COLUMNS = [
    "symbol",
    "event_date",
    "effective_date",
    "exit_date",
    "exit_date_source",
    "exit_price_date",
    "exit_price",
    "previous_close",
    "exit_return",
    "has_exit_price",
    "cash_consideration_per_share",
    "cash_consideration_is_partial",
    "cash_consideration_price_ratio",
    "exit_value",
    "exit_value_return",
    "exit_value_source",
    "has_exit_value",
    "price_source",
    "event_source",
    "event_confidence",
    "outcome_type",
    "outcome_confidence",
    "outcome_source",
    "sec_filename",
    "sec_form_type",
    "sec_company_name",
    "sec_ticker_source",
    "candidate_symbol_count",
    "policy",
    "evidence",
    "notes",
]
TERMINAL_EVENT_VALIDITY_COLUMNS = [
    "symbol",
    "event_date",
    "terminal_date",
    "has_terminal_price",
    "event_source",
    "event_confidence",
    "outcome_type",
    "has_exit_value",
    "price_rows_after_terminal_date",
    "price_rows_after_event_date",
    "universe_rows_after_terminal_date",
    "universe_rows_after_event_date",
    "backtest_rows_after_event_date",
    "has_price_after_terminal_date",
    "has_universe_after_terminal_date",
    "has_universe_after_event_date",
    "is_valid_liquidation_event",
    "invalidation_reason",
    "notes",
]
VALID_TERMINAL_EVENTS_COLUMNS = TERMINAL_EVENTS_COLUMNS + [
    "outcome_type",
    "has_exit_value",
    "is_valid_liquidation_event",
    "validity_notes",
]
SYMBOL_ALIAS_COLUMNS = [
    "canonical_symbol",
    "alias_symbol",
    "start_date",
    "end_date",
    "action_type",
    "source",
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
