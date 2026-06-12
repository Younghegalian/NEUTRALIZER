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
  -> price_quality_flags / liquidity_metrics
  -> universe_membership
  -> security_events / terminal_events
  -> delisting_outcomes
  -> backtest_universe_membership
  -> universe_stats
  -> pit_market.duckdb
```

## Collectors

| Collector | Output | Notes |
| --- | --- | --- |
| `sec_delisting_collector.py` | SEC staging parquet files | Form 25/25-NSE candidates plus Form 3/4/5 ticker map. |
| `build_delisting_outcomes.py` | `data/staging/sec_delisting_outcome_documents.parquet`, `data/research/delisting_outcomes.parquet` | Selected SEC Form 25 document parsing for effective dates, exit classification, and cash consideration. |
| `yahoo_delisted_probe` | `data/staging/yahoo_delisted_probe_daily_prices.parquet` | Recovered daily bars for SEC delisting candidates; accepts only USD `EQUITY` and `ETF` Yahoo metadata. |
| `yahoo_fallback_downloader.py` | `data/staging/yahoo_fallback_daily_prices.parquet` | Active current-symbol daily bars. |
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

Flagged rows are written to `data/research/price_quality_flags.parquet`. `liquidity_metrics` keeps raw `dollar_volume` and `adv20`, and also computes quality-filtered `quality_dollar_volume`, `quality_adv20`, and `quality_traded_days_20`.

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

Stock/ETF classification comes from Yahoo metadata and Nasdaq Trader listing metadata. Sector and industry prefer the optional FMP profile cache and fall back to SEC submissions SIC metadata when available. SEC SIC-derived sectors are coarse research buckets, not official GICS classifications.

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
- `backtest_universe_membership`: base universe membership with dates after selected delisting events removed.

Policy:

- `daily_prices` is never zero-filled for delistings.
- FMP `delistedDate` is treated as the highest-confidence delisting event.
- SEC Form 25/25-NSE `date_filed` is used as a proxy only when a higher-confidence event is unavailable.
- Delisting events are applied only to symbols with delisted-source price coverage to reduce ticker-reuse false positives.
- Terminal price is the last available close on or before the selected event date.
- `delisting_outcomes` parses the matched Form 25 document when available. It stores the extracted effective date, best-effort exit classification, observed exit price on or before the effective/event date, and SEC cash consideration per share when the text contains it.
- SEC cash consideration becomes `exit_value` only when it appears to be full cash consideration, not a mixed cash/stock component, and it is on a comparable scale with observed prices when prices are available.
