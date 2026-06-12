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
CORPORATE_ACTION_EVIDENCE_PATH = RESEARCH_DIR / "corporate_action_evidence.parquet"
RETURN_QUALITY_FLAGS_PATH = RESEARCH_DIR / "return_quality_flags.parquet"
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

CURATED_CORPORATE_ACTION_EVIDENCE = [
    {
        "symbol": "COSM",
        "event_date": "2022-12-16",
        "event_type": "reverse_split",
        "action_ratio": 25,
        "reference_price": None,
        "source_name": "SEC EX-99.1 Cosmos reverse split",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1474167/000147793222009368/cosm_ex991.htm",
        "source_authority": "sec",
        "confidence": "high",
        "notes": "Cosmos announced a 1-for-25 reverse stock split effective at the open on 2022-12-16.",
    },
    {
        "symbol": "TTOO",
        "event_date": "2022-10-13",
        "event_type": "reverse_split",
        "action_ratio": 50,
        "reference_price": None,
        "source_name": "T2 Biosystems investor relations reverse split",
        "source_url": (
            "https://t2biosystems.gcs-web.com/news-releases/news-release-details/"
            "t2-biosystems-announces-reverse-stock-split-effective-today"
        ),
        "source_authority": "issuer_ir",
        "confidence": "high",
        "notes": "TTOO common stock began trading split-adjusted on 2022-10-13 after a 1-for-50 reverse split.",
    },
    {
        "symbol": "LICN",
        "event_date": "2025-03-03",
        "event_type": "reverse_split",
        "action_ratio": 200,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2025-99",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2025-99",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "LICN effected a 1-for-200 reverse split with name and par value changes.",
    },
    {
        "symbol": "BINI",
        "event_date": "2025-08-04",
        "event_type": "reverse_split",
        "action_ratio": 250,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2025-410",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2025-410",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "BINI effected a 1-for-250 reverse split effective 2025-08-04.",
    },
    {
        "symbol": "BINI",
        "event_date": "2025-09-22",
        "event_type": "reverse_split",
        "action_ratio": 250,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2025-516",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2025-516",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "BINI effected another 1-for-250 reverse split effective 2025-09-22.",
    },
    {
        "symbol": "AIXI",
        "event_date": "2026-05-11",
        "event_type": "reverse_split",
        "action_ratio": 20,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2026-312",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-312",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "AIXI effected a 1-for-20 ADS reverse split and ADS ratio change.",
    },
    {
        "symbol": "ASBP",
        "event_date": "2026-05-11",
        "event_type": "reverse_split",
        "action_ratio": 30,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2026-313",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-313",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "ASBP effected a 1-for-30 reverse split effective 2026-05-11.",
    },
    {
        "symbol": "ELPW",
        "event_date": "2025-12-26",
        "event_type": "reverse_split",
        "action_ratio": 16,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2025-705",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2025-705",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "ELPW effected a 1-for-16 reverse split and par value change effective 2025-12-26.",
    },
    {
        "symbol": "ELPW",
        "event_date": "2026-03-12",
        "event_type": "reverse_split",
        "action_ratio": 80,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2026-150",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-150",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "ELPW effected a 1-for-80 reverse split and par value change effective 2026-03-12.",
    },
    {
        "symbol": "INHD",
        "event_date": "2026-05-04",
        "event_type": "reverse_split",
        "action_ratio": 20,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2026-292",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-292",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "INHD effected a 1-for-20 reverse split effective 2026-05-04.",
    },
    {
        "symbol": "NIVF",
        "event_date": "2025-02-11",
        "event_type": "reverse_split",
        "action_ratio": 20,
        "reference_price": None,
        "source_name": "Nasdaq Trader ECA2025-56",
        "source_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2025-56",
        "source_authority": "nasdaq_trader",
        "confidence": "high",
        "notes": "NIVF effected a 1-for-20 reverse split effective 2025-02-11.",
    },
    {
        "symbol": "SCE.PN",
        "event_date": "2024-05-13",
        "event_type": "price_reference",
        "action_ratio": None,
        "reference_price": 25,
        "source_name": "SEC FWP SCE Trust VIII liquidation amount",
        "source_url": "https://www.sec.gov/Archives/edgar/data/92103/000119312524133191/d797073dfwp.htm",
        "source_authority": "sec",
        "confidence": "high",
        "notes": "SCE Trust VIII references a $25 liquidation amount per trust preference security.",
    },
    {
        "symbol": "TPST",
        "event_date": "2023-10-11",
        "event_type": "news_spike",
        "action_ratio": None,
        "reference_price": None,
        "source_name": "SEC 8-K Tempest October 2023 data release",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1544227/000119312523253882/d547808d8k.htm",
        "source_authority": "sec",
        "confidence": "medium",
        "notes": "TPST filed an 8-K around the clinical data and rights-plan news that coincided with the extreme price move.",
    },
    {
        "symbol": "QMMM",
        "event_date": "2025-09-09",
        "event_type": "news_spike",
        "action_ratio": None,
        "reference_price": None,
        "source_name": "SEC EX-99.1 QMMM crypto and blockchain AI expansion",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1971542/000164117225026950/ex99-1.htm",
        "source_authority": "sec",
        "confidence": "medium",
        "notes": "QMMM announced a crypto/blockchain AI expansion on the day of the extreme price move.",
    },
    {
        "symbol": "QMMM",
        "event_date": "2025-09-29",
        "event_type": "trading_suspension",
        "action_ratio": None,
        "reference_price": None,
        "source_name": "SEC trading suspension 34-104113",
        "source_url": "https://www.sec.gov/enforcement-litigation/trading-suspensions/34-104113-ts",
        "source_authority": "sec",
        "confidence": "high",
        "notes": "SEC temporarily suspended QMMM trading after citing potential manipulation concerns.",
    },
    {
        "symbol": "INHD",
        "event_date": "2026-06-08",
        "event_type": "news_spike",
        "action_ratio": None,
        "reference_price": None,
        "source_name": "SEC 8-K INHD AI used-phone sales agent agreement",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1961847/000149315226028058/form8-k.htm",
        "source_authority": "sec",
        "confidence": "medium",
        "notes": "INHD reported a $3.0 million AI development-services agreement on the day of the extreme price move.",
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
CORPORATE_ACTION_EVIDENCE_COLUMNS = [
    "symbol",
    "event_date",
    "event_type",
    "action_ratio",
    "reference_price",
    "source_name",
    "source_url",
    "source_authority",
    "confidence",
    "notes",
]
RETURN_QUALITY_FLAG_COLUMNS = [
    "date",
    "symbol",
    "source",
    "prev_date",
    "prev_close",
    "close",
    "raw_return",
    "prev_adjusted_close",
    "adjusted_close",
    "adjusted_return",
    "prev_volume",
    "volume",
    "flag_reason",
    "severity",
    "event_type",
    "evidence_event_date",
    "evidence_source_name",
    "evidence_url",
    "exclude_from_backtest_return",
    "notes",
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
