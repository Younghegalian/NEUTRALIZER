# Contributing

Thanks for helping improve FONA.

## Ground Rules

- Do not commit generated market data, raw vendor/API responses, DuckDB files, parquet outputs, logs, or secrets.
- Keep data-provider credentials local. Use `.env.local`, environment variables, or provider-native credential files.
- Keep changes scoped. Prefer small pull requests with focused tests.
- Treat public/free data providers as best-effort inputs, not authoritative lifecycle truth.

## Local Setup

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests
```

Optional provider setup:

```bash
python scripts/setup_secrets.py
```

Kaggle and FMP credentials are optional. They enable additional data enrichment but are not required to run the unit tests.

## Before Opening A Pull Request

Run:

```bash
python -m unittest discover -s tests
python -m src.tools.check_prereqs
```

If you changed generated data logic and have local data available, also run:

```bash
python -m src.tools.audit_daily_prices
python -m src.tools.audit_market_flows --output data/research/market_flow_audit.csv
```

Only commit source, tests, docs, and small reference files. The `data/` tree is intentionally local-output-only except for `.gitkeep` placeholders.
