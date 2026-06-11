# Architecture

NEUTRALIZER builds a local daily-bar research database in deterministic stages.

```text
source collectors
  -> staging parquet
  -> canonical daily_prices
  -> symbol_master
  -> liquidity_metrics
  -> universe_membership
  -> universe_stats
  -> pit_market.duckdb
```

## Collectors

| Collector | Output | Notes |
| --- | --- | --- |
| `stooq_downloader.py` | `data/staging/stooq_daily_prices.parquet` | Bulk archive attempted; pipeline continues when unavailable. |
| `yahoo_fallback_downloader.py` | `data/staging/yahoo_fallback_daily_prices.parquet` | Active current-symbol daily bars. |
| `sec_delisting_collector.py` | SEC staging parquet files | Form 25/25-NSE candidates plus Form 3/4/5 ticker map. |
| `yahoo_delisted_probe` | `data/staging/yahoo_delisted_probe_daily_prices.parquet` | Recovered daily bars for SEC delisting candidates. |
| `kaggle_delisted_loader.py` | `data/staging/kaggle_delisted_daily_prices.parquet` | Arandkei archive loader. |
| `fmp_delisted_metadata.py` | `data/staging/fmp_delisted_metadata.parquet` | Optional metadata enrichment. |

## Canonical Merge

`src/normalize/normalize_prices.py` loads staging price files, rejects bad rows, deduplicates overlapping rows, and writes:

- `data/normalized/daily_prices.parquet`
- `data/normalized/symbol_master.parquet`
- `data/normalized/duplicate_report.parquet`
- `data/normalized/bad_rows_report.parquet`

Source priority:

1. `stooq`
2. `yahoo_fallback`
3. `yahoo_delisted_probe`
4. `kaggle_arandkei_delisted`

## Universe

The universe is a daily table, not a fixed symbol list.

Eligibility:

```text
close >= 1.00
adv20 >= 1,000,000
traded_days_20 >= 15
has_next_open == true
```

Universe name:

```text
US_DAILY_SURVIVORSHIP_REDUCED_V1
```

