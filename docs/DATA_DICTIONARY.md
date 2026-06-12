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
| `dollar_volume` | Raw `close * volume`. |
| `quality_dollar_volume` | `dollar_volume`, set to zero for price-quality-suspect rows. |
| `adv20` | Symbol-specific rolling 20-day mean raw dollar volume. |
| `quality_adv20` | Symbol-specific rolling 20-day mean quality-filtered dollar volume used by the universe builder. |
| `traded_days_20` | Positive-volume days in rolling 20-day window. |
| `quality_traded_days_20` | Positive-volume non-suspect days in rolling 20-day window used by the universe builder. |
| `next_open` | Open on the next global FONA trading-calendar date for the same symbol. Missing if the symbol has no bar on that next date. |
| `has_next_open` | True when a positive `next_open` exists on the next global trading-calendar date and that next row is not price-quality-suspect. |
| `is_price_quality_suspect` | True for rows flagged as unsafe for tradable universe construction. |

## `price_quality_flags`

| Column | Description |
| --- | --- |
| `date` | Flagged trading date. |
| `symbol` | Flagged symbol. |
| `source` | Price source. |
| `flag_reason` | Semicolon-separated quality reasons. |
| `open`, `high`, `low`, `close`, `volume`, `adjusted_close` | Flagged raw price row values. |
| `close_adjusted_ratio` | `close / adjusted_close` when adjusted close is positive. |

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

## `delisting_outcomes`

| Column | Description |
| --- | --- |
| `symbol` | Internal symbol. |
| `event_date` | Selected delisting event date from `terminal_events`. |
| `effective_date` | SEC Form 25 effective date when extractable. |
| `exit_date` | `effective_date` when available, otherwise `event_date`. |
| `exit_date_source` | Whether the exit date came from SEC Form 25 effective-date text or the selected delisting event. |
| `exit_price_date` | Last available price date on or before `exit_date`. |
| `exit_price` | Last available close on or before `exit_date`; never zero-filled. |
| `previous_close` | Previous available close before `exit_price_date`. |
| `exit_return` | `exit_price / previous_close - 1` when available. |
| `has_exit_price` | True when an observed exit price was found. |
| `cash_consideration_per_share` | SEC Form 25 cash consideration per share when extractable. |
| `cash_consideration_is_partial` | True when the cash amount appears to be only one component of mixed cash/stock consideration. |
| `cash_consideration_price_ratio` | Cash consideration divided by comparable observed price when available. |
| `exit_value` | Preferred terminal value: clean SEC cash consideration when usable, otherwise observed `exit_price`. |
| `exit_value_return` | `exit_value / previous_close - 1` when available. |
| `exit_value_source` | `sec_cash_consideration` or `observed_exit_price`. |
| `has_exit_value` | True when either a usable observed exit price or usable cash consideration exists. |
| `price_source` | Source of the observed exit price row. |
| `event_source` | Source of the selected delisting event. |
| `event_confidence` | Confidence of the selected delisting event. |
| `outcome_type` | Best-effort Form 25 text classification, such as `listing_standards_failure`, `merger_or_acquisition`, `bankruptcy_or_liquidation`, `exchange_transfer_or_market_change`, or `unknown`. |
| `outcome_confidence` | Rule confidence for `outcome_type`. |
| `outcome_source` | Source used for outcome classification. |
| `sec_filename` | SEC archive filename for the matched Form 25/25-NSE filing. |
| `sec_form_type` | SEC form type. |
| `sec_company_name` | Company name from the SEC index. |
| `sec_ticker_source` | Source used to map the SEC filing to the local ticker. |
| `candidate_symbol_count` | Number of candidate symbols mapped to the filing. |
| `policy` | Exit-value policy used to build the row. |
| `evidence` | Short text snippet supporting outcome classification. |
| `notes` | Exit-value caveat. |

## `terminal_event_validity`

| Column | Description |
| --- | --- |
| `symbol` | Internal symbol. |
| `event_date` | Selected delisting event date. |
| `terminal_date` | Terminal price date from `terminal_events`. |
| `has_terminal_price` | True when terminal price exists. |
| `event_source` | Source of selected event. |
| `event_confidence` | Confidence of selected event. |
| `outcome_type` | Outcome type from `delisting_outcomes` when available. |
| `has_exit_value` | True when `delisting_outcomes.exit_value` exists. |
| `price_rows_after_terminal_date` | Count of raw price rows after `terminal_date`. |
| `price_rows_after_event_date` | Count of raw price rows after `event_date`. |
| `universe_rows_after_terminal_date` | Count of base universe rows after `terminal_date`. |
| `universe_rows_after_event_date` | Count of base universe rows after `event_date`. |
| `backtest_rows_after_event_date` | Count of lifecycle-adjusted universe rows after `event_date`; expected zero. |
| `has_price_after_terminal_date` | True when later raw prices exist. |
| `has_universe_after_terminal_date` | True when later base-universe membership exists. |
| `has_universe_after_event_date` | True when later base-universe membership exists after `event_date`. |
| `is_valid_liquidation_event` | True when the row is safe for forced-liquidation use under current FONA rules. |
| `invalidation_reason` | Semicolon-separated reasons why the row was not considered liquidation-safe. |
| `notes` | Validity caveat. |

## `valid_terminal_events`

Same core columns as `terminal_events`, plus:

| Column | Description |
| --- | --- |
| `outcome_type` | Outcome type from `delisting_outcomes` when available. |
| `has_exit_value` | True when `delisting_outcomes.exit_value` exists. |
| `is_valid_liquidation_event` | Always true for this table. |
| `validity_notes` | Validity caveat copied from `terminal_event_validity`. |

## `symbol_aliases`

| Column | Description |
| --- | --- |
| `canonical_symbol` | Symbol used by FONA price history. |
| `alias_symbol` | Alternate ticker observed in a date range. |
| `start_date` | First date the alias applies. |
| `end_date` | Last date the alias applies when known. |
| `action_type` | Action type, such as `ticker_change`. |
| `source` | Source note for the curated alias. |
| `notes` | Human-readable caveat. |

## `backtest_universe_membership`

| Column | Description |
| --- | --- |
| `date` | Universe date. |
| `universe_name` | `US_DAILY_LIFECYCLE_ADJUSTED_V2`. |
| `symbol` | Included symbol. |
| `reason` | Base eligibility rule plus lifecycle adjustment when applicable. |

## `universe_stats`

Daily sanity table with symbol counts, median close, median ADV20, total dollar volume, and delisted-source count.
