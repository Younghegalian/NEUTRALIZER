# Architecture

FONA builds a local daily-bar research database in deterministic stages.

The delisting universe is SEC-led. SEC filings identify delisting events and issuer CIKs, SEC Form 3/4/5 data helps map those issuers back to tickers, and then price-bar collectors recover whatever OHLCV history is available for those tickers.

```text
SEC delisting discovery
  -> SEC candidate tickers
  -> price-bar collectors
  -> staging parquet
  -> canonical daily_prices
  -> symbol_master
  -> SEC CIK/SIC metadata
  -> security_master
  -> corporate_action_evidence
  -> price_quality_flags / return_quality_flags / liquidity_metrics
  -> security_classification_catalog
  -> universe_membership
  -> security_events / terminal_events
  -> delisting_outcomes
  -> backtest_universe_membership
  -> terminal_event_validity / valid_terminal_events
  -> symbol_aliases
  -> universe_stats
  -> pit_market.duckdb
```

## Collectors

| Collector | Output | Notes |
| --- | --- | --- |
| `sec_delisting_collector.py` | SEC staging parquet files | Form 25/25-NSE candidates plus Form 3/4/5 ticker map. |
| `build_delisting_outcomes.py` | `data/staging/sec_delisting_outcome_documents.parquet`, `data/research/delisting_outcomes.parquet` | Selected SEC Form 25 document parsing for effective dates, exit classification, and cash consideration. |
| `build_terminal_event_validity.py` | `data/research/terminal_event_validity.parquet`, `data/research/valid_terminal_events.parquet` | Splits raw terminal hints from liquidation-safe terminal events. |
| `build_symbol_aliases.py` | `data/research/symbol_aliases.parquet` | Curated ticker-change windows for resolving known alias periods. |
| `build_corporate_action_evidence.py` | `data/research/corporate_action_evidence.parquet` | Curated SEC, Nasdaq Trader, and issuer IR source URLs for high-impact return events. |
| `build_return_quality_flags.py` | `data/research/return_quality_flags.parquet` | Extreme close-to-close returns classified as split/scale exclusions, event risk, or manual review. |
| `yahoo_delisted_probe` | `data/staging/yahoo_delisted_probe_daily_prices.parquet` | Recovered daily bars for SEC delisting candidates; accepts only USD `EQUITY` and `ETF` Yahoo metadata. |
| `yahoo_fallback_downloader.py` | `data/staging/yahoo_fallback_daily_prices.parquet` | Active current-symbol daily bars plus forced ETF label seeds. |
| `kaggle_delisted_loader.py` | `data/staging/kaggle_delisted_daily_prices.parquet` | Arandkei archive loader. |
| `fmp_delisted_metadata.py` | `data/staging/fmp_delisted_metadata.parquet` | Optional metadata enrichment. |
| `fmp_profile_metadata.py` | `data/staging/fmp_profile_metadata.parquet` | Optional cached sector and industry enrichment. |
| `sec_company_metadata.py` | `data/staging/sec_company_metadata.parquet` | SEC submissions CIK/SIC metadata, optionally from the nightly SEC bulk archive. |
| `stooq_downloader.py` | `data/staging/stooq_daily_prices.parquet` | Bulk archive attempted; pipeline continues when unavailable. |

## Canonical Merge

`src/normalize/normalize_prices.py` loads staging price files, rejects bad rows, deduplicates overlapping rows, and writes:

- `data/normalized/daily_prices.parquet`
- `data/normalized/symbol_master.parquet`
- `data/normalized/security_master.parquet`
- `data/normalized/security_classification_catalog.parquet`
- `data/normalized/duplicate_report.parquet`
- `data/normalized/bad_rows_report.parquet`

Source priority:

1. `stooq`
2. `yahoo_fallback`
3. `yahoo_delisted_probe`
4. `kaggle_arandkei_delisted`

Price validation rejects rows with null OHLC, non-positive OHLC, negative volume, `high < low`, or `open`/`close` outside the `[low, high]` range.

## Price Quality Layer

`src/universe/compute_liquidity.py` preserves raw `daily_prices` but flags rows that are unsafe for tradable universe construction:

- OHLC above 100,000, usually split-adjusted scale artifacts rather than executable raw prices. `BRK.A` is explicitly allowed as a legitimate high-price class-share exception.
- Extreme `close / adjusted_close` ratios outside `[0.001, 1000]`.
- Zero-volume rows with close above 10,000.
- Extreme close-to-close returns above 1,000% or below -95% are written to `return_quality_flags`.
- `corporate_action_evidence` supplies clickable evidence for curated reverse splits, preferred/reference-price guards, news spikes, and trading suspensions.
- Reverse-split and reference-price scale rows become `exclude_from_backtest_return = true`; sourced news spikes remain in raw prices and are tagged as `event_risk`.

Flagged rows are written to `data/research/price_quality_flags.parquet`. `liquidity_metrics` keeps raw `dollar_volume` and `adv20`, and also computes quality-filtered `quality_dollar_volume`, `quality_adv20`, and `quality_traded_days_20`.

Rows with `return_quality_flags.exclude_from_backtest_return = true` are treated as `is_price_quality_suspect` for liquidity and universe construction. The raw bars remain in `daily_prices` for auditability.

`next_open` is computed against the global FONA trading calendar. A row is executable only when the same symbol has a positive open on the very next global trading date, and that next row is not price-quality-suspect.

## Security Master

`src/normalize/build_security_master.py` builds asset classification separately from price coverage.

Primary fields:

- `asset_type`: `stock`, `etf`, `fund`, or `unknown`
- `is_etf`
- `instrument_type`
- `security_name`
- `exchange`
- `currency`
- `cik`
- `sic`
- `sic_description`
- `sector`
- `industry`

Stock/ETF classification comes from Yahoo metadata and Nasdaq Trader listing metadata. Sector and industry prefer SEC submissions SIC metadata and fall back to the optional FMP profile cache when SEC SIC metadata is unavailable. SEC SIC-derived sectors are coarse research buckets, not official GICS classifications.

## Security Classification Catalog

`src/normalize/build_classification_catalog.py` builds a small handoff catalog for labels that a live engine's default SEC SIC labeler cannot reproduce.

It does not duplicate all SEC SIC labels from `security_master`. It includes:

- Non-ETF rows whose `security_master` sector came from a non-SIC source such as the cached FMP fallback.
- ETF rows with no sector source that pass the durable/liquid starter policy: recent price coverage, at least 5 years of price history, `quality_adv20 >= 25,000,000`, and at least 15 quality traded days in the latest 20-day window.

The catalog writes `data/normalized/security_classification_catalog.parquet` and is embedded in `pit_market.duckdb` as `security_classification_catalog`. Strategy bundles and live engines can use its `policy_version` and `catalog_hash` to verify that FONA-only labels were delivered alongside the strategy.

## Universe

The base universe is a daily table, not a fixed symbol list.

Eligibility:

```text
close >= 1.00
quality_adv20 >= 1,000,000
quality_traded_days_20 >= 15
has_next_open == true
is_price_quality_suspect == false
```

`traded_days_20` counts only rows with positive volume.

Universe name:

```text
US_DAILY_SURVIVORSHIP_REDUCED_V1
```

## Lifecycle-Adjusted Backtest Universe

`src/universe/build_backtest_universe.py` builds a second universe for strategy simulation:

```text
US_DAILY_LIFECYCLE_ADJUSTED_V2
```

Outputs:

- `security_events`: listing and delisting lifecycle events.
- `terminal_events`: final exit reference price for each selected delisting event.
- `delisting_outcomes`: enriched exit/outcome record for each selected delisting event.
- `terminal_event_validity`: safety audit for each raw terminal event.
- `valid_terminal_events`: terminal-event subset safe for forced-liquidation use.
- `symbol_aliases`: curated ticker-change aliases for known symbol-history mismatches.
- `backtest_universe_membership`: base universe membership with dates after selected delisting events removed.

Policy:

- `daily_prices` is never zero-filled for delistings.
- FMP `delistedDate` is treated as the highest-confidence delisting event.
- SEC Form 25/25-NSE `date_filed` is used as a proxy only when a higher-confidence event is unavailable.
- Delisting events are applied only to symbols with delisted-source price coverage to reduce ticker-reuse false positives.
- Terminal price is the last available close on or before the selected event date.
- `delisting_outcomes` parses the matched Form 25 document when available. It stores the extracted effective date, best-effort exit classification, observed exit price on or before the effective/event date, and SEC cash consideration per share when the text contains it.
- SEC cash consideration becomes `exit_value` only when it appears to be full cash consideration, not a mixed cash/stock component, and it is on a comparable scale with observed prices when prices are available.
- `terminal_events` remains a raw provenance table. Backtest engines that need hard liquidation events should use `valid_terminal_events`.
- A terminal event is not liquidation-safe when the same symbol still has base-universe membership after the terminal/event date, when terminal price is missing, or when lifecycle-adjusted membership appears after the selected event.
- The current curated alias map records the Fiserv `FI` ticker window against FONA's continuous `FISV` price history.
