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
  -> security_master
  -> liquidity_metrics
  -> universe_membership
  -> universe_stats
  -> pit_market.duckdb
```

## Collectors

| Collector | Output | Notes |
| --- | --- | --- |
| `sec_delisting_collector.py` | SEC staging parquet files | Form 25/25-NSE candidates plus Form 3/4/5 ticker map. |
| `yahoo_delisted_probe` | `data/staging/yahoo_delisted_probe_daily_prices.parquet` | Recovered daily bars for SEC delisting candidates; accepts only USD `EQUITY` and `ETF` Yahoo metadata. |
| `yahoo_fallback_downloader.py` | `data/staging/yahoo_fallback_daily_prices.parquet` | Active current-symbol daily bars. |
| `kaggle_delisted_loader.py` | `data/staging/kaggle_delisted_daily_prices.parquet` | Arandkei archive loader. |
| `fmp_delisted_metadata.py` | `data/staging/fmp_delisted_metadata.parquet` | Optional metadata enrichment. |
| `fmp_profile_metadata.py` | `data/staging/fmp_profile_metadata.parquet` | Optional cached sector and industry enrichment. |
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

## Security Master

`src/normalize/build_security_master.py` builds asset classification separately from price coverage.

Primary fields:

- `asset_type`: `stock`, `etf`, `fund`, or `unknown`
- `is_etf`
- `instrument_type`
- `security_name`
- `exchange`
- `currency`
- `sector`
- `industry`

Stock/ETF classification comes from Yahoo metadata and Nasdaq Trader listing metadata. Sector and industry come from the optional FMP profile cache.

## Universe

The universe is a daily table, not a fixed symbol list.

Eligibility:

```text
close >= 1.00
adv20 >= 1,000,000
traded_days_20 >= 15
has_next_open == true
```

`traded_days_20` counts only rows with positive volume.

Universe name:

```text
US_DAILY_SURVIVORSHIP_REDUCED_V1
```
