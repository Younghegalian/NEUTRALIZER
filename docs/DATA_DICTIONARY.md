# Data Dictionary

## `daily_prices`

| Column | Type | Description |
| --- | --- | --- |
| `date` | DATE | Trading date. |
| `symbol` | TEXT | Internal normalized symbol. |
| `vendor_symbol` | TEXT | Source/vendor symbol. |
| `open` | DOUBLE | Raw daily open. |
| `high` | DOUBLE | Raw daily high. |
| `low` | DOUBLE | Raw daily low. |
| `close` | DOUBLE | Raw daily close. |
| `volume` | BIGINT | Daily share volume. |
| `adjusted_close` | DOUBLE | Adjusted close when provided by source. |
| `source` | TEXT | Data source. |
| `is_delisted_source` | BOOLEAN | True for delisted-focused sources. |

## `symbol_master`

| Column | Description |
| --- | --- |
| `symbol` | Internal symbol. |
| `vendor_symbol` | Vendor symbols seen for the security. |
| `first_date` | First price date. |
| `last_date` | Last price date. |
| `source_list` | Comma-separated sources. |
| `has_active_source` | Has active-source coverage. |
| `has_delisted_source` | Has delisted-source coverage. |
| `observation_count` | Canonical daily rows. |

## `security_master`

| Column | Description |
| --- | --- |
| `symbol` | Internal symbol. |
| `asset_type` | `stock`, `etf`, `fund`, or `unknown`. |
| `is_etf` | ETF flag from FMP, Nasdaq Trader, or Yahoo metadata. |
| `instrument_type` | Yahoo instrument type when available. |
| `security_name` | Best available company/fund name. |
| `exchange` | Best available exchange label. |
| `currency` | Best available quote currency. |
| `cik` | SEC Central Index Key when mapped. |
| `sic` | SEC Standard Industrial Classification code when mapped. |
| `sic_description` | SEC SIC description when mapped. |
| `sector` | FMP profile sector, falling back to SEC SIC-derived sector when cached. |
| `industry` | FMP profile industry, falling back to SEC SIC description when cached. |
| `classification_source` | Source used for asset classification/name. |
| `sector_source` | Source used for sector/industry enrichment. |

## `liquidity_metrics`

| Column | Description |
| --- | --- |
| `dollar_volume` | `close * volume`. |
| `adv20` | Symbol-specific rolling 20-day mean dollar volume. |
| `traded_days_20` | Positive-volume days in rolling 20-day window. |
| `next_open` | Next available open for the same symbol. |
| `has_next_open` | True when `next_open` is available. |

## `universe_membership`

| Column | Description |
| --- | --- |
| `date` | Universe date. |
| `universe_name` | Universe identifier. |
| `symbol` | Included symbol. |
| `reason` | Eligibility rule summary. |

## `security_events`

| Column | Description |
| --- | --- |
| `symbol` | Internal symbol. |
| `event_type` | `listing` or `delisting`. |
| `event_date` | Event date. For SEC delistings this is a Form 25/25-NSE filing-date proxy. |
| `source` | Event source, such as `price_first_date`, `fmp_delisted_date`, or `sec_form25_date_filed`. |
| `source_event_id` | Source-specific identifier or aggregation note. |
| `source_symbol` | Raw or source-normalized symbol used to match the event. |
| `confidence` | `high`, `medium`, `proxy`, or `coverage_start`. |
| `notes` | Event caveat. |

## `terminal_events`

| Column | Description |
| --- | --- |
| `symbol` | Internal symbol. |
| `event_date` | Selected delisting event date. |
| `terminal_date` | Last available price date on or before `event_date`. |
| `terminal_price` | Last available close on or before `event_date`; never zero-filled. |
| `previous_close` | Previous available close before `terminal_date`. |
| `terminal_return` | `terminal_price / previous_close - 1` when available. |
| `has_terminal_price` | True when a terminal price was found. |
| `price_source` | Source of the terminal price row. |
| `event_source` | Source of the selected delisting event. |
| `event_confidence` | Confidence of the selected delisting event. |
| `terminal_policy` | Exit-price policy used to build the row. |
| `notes` | Terminal-price caveat. |

## `backtest_universe_membership`

| Column | Description |
| --- | --- |
| `date` | Universe date. |
| `universe_name` | `US_DAILY_LIFECYCLE_ADJUSTED_V2`. |
| `symbol` | Included symbol. |
| `reason` | Base eligibility rule plus lifecycle adjustment when applicable. |

## `universe_stats`

Daily sanity table with symbol counts, median close, median ADV20, total dollar volume, and delisted-source count.
