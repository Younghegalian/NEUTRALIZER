# Daily Maintenance

Daily maintenance is designed for a local machine that already has the required credentials and enough disk space.

## Requirements

- Python dependencies installed from `requirements.txt`
- Kaggle token when refreshing Kaggle data
- Optional FMP key for metadata enrichment
- Network access to SEC and Yahoo

On Windows, if `python` resolves to the Microsoft Store alias, set an explicit runtime before running manual commands:

```powershell
$env:FONA_PYTHON="C:\Path\To\python.exe"
```

The daily maintenance script uses `FONA_PYTHON` when set and otherwise tries a local `.venv`, normal PATH Python, and the Codex bundled Python runtime.

Sector and industry enrichment is incremental because FMP API limits apply. Set this before maintenance to allow new profile requests:

```powershell
$env:FONA_FMP_PROFILE_LIMIT="200"
```

Public listing/delisting benchmark checks are optional because they call external websites. Enable them when you want the daily run to compare local annual flows with StockAnalysis listed/delisted counts and World Bank listed-company counts:

```powershell
$env:FONA_FETCH_MARKET_FLOW_BENCHMARKS="1"
```

## Standard Daily Run

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\daily_maintenance.ps1
```

The script:

1. Refreshes the current SEC quarter cache.
2. Checks prerequisites.
3. Refreshes active Yahoo daily bars.
4. Refreshes SEC delisting candidates.
5. Probes Yahoo for newly recoverable delisted candidates.
6. Loads Kaggle delisted data if present.
7. Rebuilds normalized price and symbol parquet.
8. Refreshes cached FMP profile metadata up to `FONA_FMP_PROFILE_LIMIT`.
9. Rebuilds `security_master`.
10. Recomputes liquidity metrics and universe tables.
11. Rebuilds lifecycle events, terminal events, and the lifecycle-adjusted backtest universe.
12. Rebuilds `data/pit_market.duckdb`.
13. Audits daily-bar grain, nulls, OHLC validity, date validity, and table integrity.
14. Audits annual listing/delisting flow rates and writes `data/research/market_flow_audit.csv`.
15. Runs unit tests.

## Faster Manual Runs

Refresh active data only:

```powershell
python -m src.run_pipeline --step collect_yahoo_active --start-date 2010-01-01 --end-date today --yahoo-workers 6 --force-yahoo-refresh
```

Refresh SEC candidates only:

```powershell
python -m src.run_pipeline --step collect_sec_delisted_candidates --sec-start-year 2010 --skip-sec-doc-enrich
```

Probe delisted candidates only:

```powershell
python -m src.run_pipeline --step probe_yahoo_delisted --start-date 2010-01-01 --end-date today --yahoo-workers 6
```

Rebuild local database from existing staging files:

```powershell
python -m src.run_pipeline --step normalize --start-date 2010-01-01 --end-date today
python -m src.run_pipeline --step fmp_profiles --fmp-profile-limit 0
python -m src.run_pipeline --step security_master
python -m src.run_pipeline --step liquidity
python -m src.run_pipeline --step universe
python -m src.run_pipeline --step backtest_universe
python -m src.run_pipeline --step duckdb
```

Audit the current DuckDB daily bars:

```powershell
python -m src.tools.audit_daily_prices
```

Audit annual listing and delisting flow rates:

```powershell
python -m src.tools.audit_market_flows --fetch-benchmarks --output data\research\market_flow_audit.csv
```

The flow audit reports base and lifecycle-adjusted scopes. Use `backtest_stock_major_universe` as the closest backtest-ready public-market comparison scope. The audit separates price/universe behavior from event coverage:

- `new_to_universe` and `db_listing_rate_pct` measure symbols newly entering the local tradable universe.
- `left_universe_completed` measures symbols that disappear from the local universe in completed years.
- `sec_candidate_price_recovered_delisted_symbols` measures SEC Form 25/25-NSE candidate symbols whose daily prices were recovered.
- `benchmark_new_listed`, `benchmark_delisted`, and benchmark rates are public comparison counts, fetched live when possible and backed by checked fallback values.
