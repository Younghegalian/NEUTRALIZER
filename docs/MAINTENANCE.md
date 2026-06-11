# Daily Maintenance

Daily maintenance is designed for a local machine that already has the required credentials and enough disk space.

## Requirements

- Python dependencies installed from `requirements.txt`
- Kaggle token when refreshing Kaggle data
- Optional FMP key for metadata enrichment
- Network access to SEC and Yahoo

On Windows, if `python` resolves to the Microsoft Store alias, set an explicit runtime before running manual commands:

```powershell
$env:NEUTRALIZER_PYTHON="C:\Path\To\python.exe"
```

The daily maintenance script uses `NEUTRALIZER_PYTHON` when set and otherwise tries a local `.venv`, normal PATH Python, and the Codex bundled Python runtime.

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
7. Rebuilds normalized parquet.
8. Recomputes liquidity metrics and universe tables.
9. Rebuilds `data/pit_market.duckdb`.
10. Runs unit tests.

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
python -m src.run_pipeline --step liquidity
python -m src.run_pipeline --step universe
python -m src.run_pipeline --step duckdb
```
