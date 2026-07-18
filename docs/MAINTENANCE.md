# Daily Maintenance

Daily maintenance is designed for a local machine with network access and enough disk space for generated data. Optional provider credentials unlock optional enrichment sources. The canonical operator commands are Python scripts under `scripts/`, so the same workflow works on Windows, macOS, and Linux.

## Requirements

- Python 3.10+
- Python dependencies installed from `requirements.txt`
- Optional Kaggle token when refreshing Kaggle archive data
- Optional FMP key for metadata enrichment
- Network access to SEC and Yahoo
- `FONA_SEC_USER_AGENT` set to a descriptive SEC fair-access user agent before SEC collection

## Fresh Setup

One-command local setup:

```bash
python scripts/bootstrap.py
```

This creates `.venv`, installs dependencies, checks prerequisites, and runs unit tests.

To include optional provider credential prompts:

```bash
python scripts/bootstrap.py --with-secrets
```

If your shell's `python` points to the wrong interpreter, set `FONA_PYTHON` or run the script with the exact interpreter you want:

```bash
FONA_PYTHON=/path/to/python python scripts/daily_maintenance.py --dry-run
```

On PowerShell:

```powershell
$env:FONA_PYTHON="C:\Path\To\python.exe"
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
```

## Local Provider Settings

Interactive setup:

```bash
python scripts/setup_secrets.py
```

This writes local-only credentials and settings when provided:

- Kaggle token to `~/.kaggle/access_token`
- FMP key to `.env.local` as `FMP_API_KEY`
- SEC fair-access user agent to `.env.local` as `FONA_SEC_USER_AGENT`

For non-interactive environments, pass secrets through your secret manager or CI environment instead of shell history where possible.

## Standard Daily Run

```bash
python scripts/daily_maintenance.py
```

The script:

1. Refreshes the current SEC quarter cache.
2. Checks prerequisites.
3. Refreshes active Yahoo daily bars.
4. Refreshes SEC delisting candidates.
5. Probes Yahoo for newly recoverable delisted candidates.
6. Loads Kaggle delisted data if present.
7. Rebuilds normalized price and symbol parquet.
8. Refreshes cached FMP profile metadata up to the configured profile limit.
9. Refreshes cached SEC CIK/SIC metadata up to the configured company limit.
10. Rebuilds `security_master`.
11. Rebuilds curated corporate-action evidence sources.
12. Recomputes price-quality flags, return-quality flags, and liquidity metrics.
13. Rebuilds the non-SIC security classification handoff catalog.
14. Rebuilds universe tables.
15. Rebuilds lifecycle events, terminal events, and the lifecycle-adjusted backtest universe.
16. Rebuilds delisting outcome enrichment from selected SEC Form 25 documents.
17. Rebuilds terminal-event validity and the liquidation-safe terminal subset.
18. Rebuilds curated symbol aliases.
19. Rebuilds `data/pit_market.duckdb`.
20. Audits daily-bar grain, nulls, OHLC validity, date validity, global next-open execution, price/return-quality exclusions, delisting outcome joins, terminal-event validity, and table integrity.
21. Audits annual listing/delisting flow rates and writes `data/research/market_flow_audit.csv`.
22. Runs unit tests.

Preview resolved configuration without doing work:

```bash
python scripts/daily_maintenance.py --dry-run
```

## Common Options

Incrementally enrich sector and industry metadata when FMP quota allows:

```bash
python scripts/daily_maintenance.py --fmp-profile-limit 500
```

Backfill free SEC CIK/SIC classification metadata from the official nightly bulk archive:

```bash
python scripts/daily_maintenance.py --sec-company-use-bulk
```

Fetch live public listing/delisting benchmark inputs during the flow audit:

```bash
python scripts/daily_maintenance.py --fetch-market-flow-benchmarks
```

Use staged SEC enrichment limits:

```bash
python scripts/daily_maintenance.py --sec-company-limit 200
```

The same options can be supplied through environment variables when a scheduler prefers environment-based configuration:

| Environment variable | Equivalent CLI option |
| --- | --- |
| `FONA_START_DATE` | `--start-date` |
| `FONA_SEC_USER_AGENT` | SEC request `User-Agent` header |
| `FONA_YAHOO_WORKERS` | `--yahoo-workers` |
| `FONA_FMP_PROFILE_LIMIT` | `--fmp-profile-limit` |
| `FONA_SEC_COMPANY_LIMIT` | `--sec-company-limit` |
| `FONA_SEC_COMPANY_USE_BULK=1` | `--sec-company-use-bulk` |
| `FONA_FORCE_SEC_COMPANY_BULK_DOWNLOAD=1` | `--force-sec-company-bulk-download` |
| `FONA_FETCH_MARKET_FLOW_BENCHMARKS=1` | `--fetch-market-flow-benchmarks` |

## Faster Manual Runs

Refresh active data only:

```bash
python -m src.run_pipeline --step collect_yahoo_active --start-date 2010-01-01 --end-date today --yahoo-workers 6 --force-yahoo-refresh
```

Refresh SEC candidates only:

```bash
python -m src.run_pipeline --step collect_sec_delisted_candidates --sec-start-year 2010 --skip-sec-doc-enrich
```

Probe delisted candidates only:

```bash
python -m src.run_pipeline --step probe_yahoo_delisted --start-date 2010-01-01 --end-date today --yahoo-workers 6
```

Rebuild local database from existing staging files:

```bash
python -m src.run_pipeline --step normalize --start-date 2010-01-01 --end-date today
python -m src.run_pipeline --step fmp_profiles --fmp-profile-limit 0
python -m src.run_pipeline --step sec_company_metadata --sec-company-limit 0
python -m src.run_pipeline --step security_master
python -m src.run_pipeline --step corporate_action_evidence
python -m src.run_pipeline --step liquidity
python -m src.run_pipeline --step classification_catalog
python -m src.run_pipeline --step universe
python -m src.run_pipeline --step backtest_universe
python -m src.run_pipeline --step delisting_outcomes
python -m src.run_pipeline --step terminal_event_validity
python -m src.run_pipeline --step symbol_aliases
python -m src.run_pipeline --step duckdb
```

Rebuild delisting outcomes from cached SEC documents only:

```bash
python -m src.run_pipeline --step delisting_outcomes --skip-delisting-outcome-doc-fetch
```

Audit the current DuckDB daily bars:

```bash
python -m src.tools.audit_daily_prices
```

Audit annual listing and delisting flow rates:

```bash
python -m src.tools.audit_market_flows --fetch-benchmarks --output data/research/market_flow_audit.csv
```

The flow audit reports base and lifecycle-adjusted scopes. Use `backtest_stock_major_universe` as the closest backtest-ready public-market comparison scope. The audit separates price/universe behavior from event coverage:

- `new_to_universe` and `db_listing_rate_pct` measure symbols newly entering the local tradable universe.
- `left_universe_completed` measures symbols that disappear from the local universe in completed years.
- `sec_candidate_price_recovered_delisted_symbols` measures SEC Form 25/25-NSE candidate symbols whose daily prices were recovered.
- `benchmark_new_listed`, `benchmark_delisted`, and benchmark rates are public comparison counts, fetched live when possible and backed by checked fallback values.

## Resetting Local Data State

There is no separate hidden data fingerprint ledger. The effective local fingerprint is the generated DuckDB/parquet outputs plus raw source caches under `data/`.

Preview a reset:

```bash
python scripts/reset_local_data.py
```

Remove derived artifacts while keeping raw API/vendor caches:

```bash
python scripts/reset_local_data.py --generated-only --force
```

Blank the whole local data cache, including raw Yahoo/FMP/SEC/Kaggle files:

```bash
python scripts/reset_local_data.py --all-local-data --force
```

## Windows PowerShell Wrappers

Windows users can still use the existing wrappers if they prefer PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\setup_secrets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\daily_maintenance.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\reset_local_data.ps1
```

The Python scripts are the cross-platform source of truth for new operator documentation.
