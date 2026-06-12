<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/fona-black.png">
    <source media="(prefers-color-scheme: light)" srcset="assets/brand/fona-white.png">
    <img alt="FONA" src="assets/brand/fona-white.png" width="720">
  </picture>
</p>

<h1 align="center">FONA</h1>

<p align="center">
  <strong>Finance Open Network Archive.</strong><br>
  Local-first PIT market data infrastructure for survivorship-reduced U.S. equity backtesting.
</p>

<p align="center">
  <img alt="DuckDB" src="https://img.shields.io/badge/storage-DuckDB-FFF000?style=flat-square">
  <img alt="Daily bars" src="https://img.shields.io/badge/daily_bars-23.96M-243BFF?style=flat-square">
  <img alt="Symbols" src="https://img.shields.io/badge/symbols-11.8K-111111?style=flat-square">
  <img alt="SEC led" src="https://img.shields.io/badge/delisting_spine-SEC-1F6FEB?style=flat-square">
  <img alt="Tests" src="https://img.shields.io/badge/tests-11_passing-2EA043?style=flat-square">
</p>

FONA, the Finance Open Network Archive, builds a local market-data layer for backtests that need more than today's surviving tickers. It combines SEC-led delisting discovery, recoverable historical daily bars, security classification, liquidity metrics, and a date-by-date tradable universe into one auditable DuckDB database.

This repository contains the pipeline, tests, documentation, and brand assets. Generated market data, raw vendor/API responses, DuckDB files, and secrets stay local and are intentionally ignored by Git.

## What You Get

| Capability | Delivered artifact |
| --- | --- |
| PIT-style daily OHLCV | `daily_prices` with `date + symbol` grain |
| Active and delisted coverage | Active Yahoo bars plus SEC-candidate Yahoo recovery and Kaggle delisted archive |
| Security classification | `security_master` with stock/ETF/fund classification, exchange, name, sector, and industry fields |
| Backtest universe | `universe_membership` rebuilt daily from price, volume, ADV20, and next-open eligibility |
| Liquidity features | `liquidity_metrics` with dollar volume, ADV20, positive-volume traded days, and next open |
| Quality gates | Unit tests, hard daily-bar audit, and annual listing/delisting flow audit |

## Data Product Snapshot

Latest local build:

| Metric | Value |
| --- | ---: |
| Final database | `data/pit_market.duckdb` |
| Price date range | 2010-01-01 to 2026-06-11 |
| Daily price rows | 23,965,894 |
| Priced symbols | 11,803 |
| Active-source symbols | 10,021 |
| Delisted-source symbols | 1,782 |
| Trading dates | 4,249 |
| Universe date range | 2010-01-25 to 2026-06-09 |
| Universe memberships | 13,740,815 |
| Median daily universe size | 3,053 |

Security classification:

| Classification | Symbols |
| --- | ---: |
| Stock | 6,923 |
| ETF | 4,861 |
| Unknown | 18 |
| Fund | 1 |
| Sector/industry enriched | 184 |

SEC-led delisting discovery:

| Area | Value |
| --- | ---: |
| SEC Form 25/25-NSE filings | 28,144 |
| SEC delisting CIKs | 8,731 |
| SEC candidate tickers | 10,962 |
| Yahoo delisted raw cache inspected | 4,441 |
| Yahoo equity/ETF/USD cache accepted | 1,813 |
| Yahoo non-equity/non-USD/empty cache rejected | 2,628 |

## Inside The DuckDB

| Table | Rows | Grain | What is inside |
| --- | ---: | --- | --- |
| `daily_prices` | 23,965,894 | `date, symbol` | Canonical OHLCV bars, adjusted close, source, delisted-source flag |
| `symbol_master` | 11,803 | `symbol` | First/last price date, source list, active/delisted coverage flags |
| `security_master` | 11,803 | `symbol` | Asset type, ETF flag, instrument type, name, exchange, currency, sector, industry |
| `liquidity_metrics` | 23,965,894 | `date, symbol` | Dollar volume, ADV20, positive-volume traded days, next open |
| `universe_membership` | 13,740,815 | `date, universe, symbol` | Tradable universe membership by date |
| `universe_stats` | 4,231 | `date, universe` | Daily sanity metrics for universe size, median close, ADV, and volume |

Price-bar source coverage:

| Source | Rows | Symbols | Range |
| --- | ---: | ---: | --- |
| `yahoo_fallback` | 20,282,646 | 10,021 | 2010-01-04 to 2026-06-10 |
| `yahoo_delisted_probe` | 3,649,850 | 1,767 | 2010-01-04 to 2026-06-11 |
| `kaggle_arandkei_delisted` | 33,398 | 15 | 2010-01-01 to 2026-02-23 |

## Sample Records

`daily_prices`:

| date | symbol | open | high | low | close | volume | source | delisted |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 2026-06-10 | BINI | 0.08 | 0.09 | 0.06 | 0.08 | 17,400 | `yahoo_delisted_probe` | true |
| 2026-06-10 | DIDIY | 3.48 | 3.60 | 3.48 | 3.58 | 15,635,100 | `yahoo_delisted_probe` | true |
| 2026-06-10 | SPY | 733.39 | 738.38 | 725.33 | 725.43 | 59,800,600 | `yahoo_fallback` | false |
| 2026-06-09 | AAPL | 300.28 | 300.75 | 287.78 | 290.55 | 70,108,800 | `yahoo_fallback` | false |
| 2026-06-08 | BINI | 0.06 | 0.07 | 0.05 | 0.06 | 26,600 | `yahoo_delisted_probe` | true |

`security_master`:

| symbol | asset_type | is_etf | instrument_type | security_name | exchange | sector | industry |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL | stock | false | EQUITY | Apple Inc. | NASDAQ | Technology | Consumer Electronics |
| BINI | stock | false | EQUITY | Bollinger Innovations, Inc. | OTC Markets OTCPK |  |  |
| DIDIY | stock | false | EQUITY | DiDi Global Inc. | OTC Markets OTCPK |  |  |
| SPY | etf | true | ETF | State Street SPDR S&P 500 ETF Trust | NYSEArca |  |  |
| UVXY | etf | true | ETF | ProShares Ultra VIX Short-Term Futures ETF | Cboe US |  |  |

## Query Contract

Python helpers:

```python
from src.db.query_examples import (
    get_price_panel,
    get_prices,
    get_security_master,
    get_universe,
)

symbols = get_universe("2020-01-02")
prices = get_prices("2020-01-02", symbols[:100])
panel = get_price_panel("2020-01-02", "2020-03-31")
metadata = get_security_master(symbols[:100])
```

Direct DuckDB:

```sql
SELECT
    p.date,
    p.symbol,
    sm.asset_type,
    sm.sector,
    p.close,
    l.adv20,
    l.next_open
FROM universe_membership u
JOIN daily_prices p USING (date, symbol)
JOIN liquidity_metrics l USING (date, symbol)
LEFT JOIN security_master sm USING (symbol)
WHERE u.date = DATE '2020-01-02'
  AND u.universe_name = 'US_DAILY_SURVIVORSHIP_REDUCED_V1'
ORDER BY p.symbol;
```

## Source Model

FONA uses SEC as the primary delisting discovery spine. SEC identifies delisting events and issuer CIKs; price collectors then recover the available OHLCV history for mapped tickers.

| Layer | Source | Role |
| --- | --- | --- |
| Delisting discovery | SEC Form 25/25-NSE filings | Finds delisting events and issuer CIKs |
| Ticker mapping | SEC Form 3/4/5 structured data | Maps CIKs to historical tickers where available |
| Delisted OHLCV recovery | Yahoo chart API probe | Pulls daily bars for recoverable SEC candidate tickers |
| Active OHLCV baseline | Yahoo chart API | Pulls current listed-symbol daily bars |
| Supplemental delisted OHLCV | Kaggle Arandkei archive | Adds delisted historical bars available in the archive |
| Metadata enrichment | FMP delisted and profile endpoints | Adds delisting metadata, sector, and industry when plan limits allow |
| Supplemental OHLCV | Stooq bulk archive | Attempted when available; pipeline continues without it |

Yahoo chart responses are accepted only when metadata identifies a USD `EQUITY` or `ETF`; non-equity, non-USD, and placeholder `YHD` matches are rejected before normalization.

## Quality Controls

The daily audit fails if any hard data-quality rule breaks:

| Check | Expected |
| --- | ---: |
| Duplicate `(date, symbol)` keys | 0 |
| Null required OHLCV fields | 0 |
| Non-positive OHLC rows | 0 |
| Negative volume rows | 0 |
| `high < low` rows | 0 |
| `open`/`close` outside `[low, high]` rows | 0 |
| Future-dated rows | 0 |
| Weekend rows | 0 |
| Missing joins to symbol/security/liquidity/universe tables | 0 |

Latest validation:

```text
Ran 11 tests
OK

[audit] OK
```

Annual market-flow validation:

```powershell
python -m src.tools.audit_market_flows --fetch-benchmarks --output data\research\market_flow_audit.csv
```

Latest `stock_major_universe` completed-year medians:

| Metric | Value |
| --- | ---: |
| Public benchmark listing rate | 6.93% |
| Public benchmark delisting rate | 7.16% |
| Local SEC price-recovered delisting rate | 5.16% |
| Local delisted-event capture vs benchmark | 71.68% |

## Quick Start

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Set local secrets:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_secrets.ps1
```

Run a full rebuild:

```powershell
python -m src.run_pipeline --start-date 2010-01-01 --end-date today
```

Run daily maintenance:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\daily_maintenance.ps1
```

Incrementally enrich sector and industry metadata when FMP quota allows:

```powershell
$env:FONA_FMP_PROFILE_LIMIT="500"
powershell -ExecutionPolicy Bypass -File .\scripts\daily_maintenance.ps1
```

## Repository Layout

```text
assets/brand/               FONA brand assets
docs/                       Architecture, data dictionary, maintenance notes
scripts/                    Operator scripts
src/collectors/             Source collectors
src/normalize/              Canonical prices, symbol master, and security master
src/universe/               Liquidity metrics and daily universe
src/db/                     DuckDB build and query helpers
src/tools/                  Audits and prerequisite checks
tests/                      Unit tests
data/                       Local-only generated data, ignored by Git
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data Dictionary](docs/DATA_DICTIONARY.md)
- [Daily Maintenance](docs/MAINTENANCE.md)
- [Coverage Notes](docs/COVERAGE.md)

## Boundaries

FONA is a research-grade local data product, not a CRSP, Norgate, Bloomberg, or Refinitiv replacement.

Known limitations:

- Not every historical delisted U.S. security is recoverable from public/free sources.
- Ticker reuse can still require manual investigation when metadata is weak.
- Yahoo adjusted historical prices and vendor volume can distort dollar-volume estimates for heavily split-adjusted securities.
- Sector and industry coverage grows incrementally under FMP plan limits.
- This is daily equity/ETF infrastructure, not intraday, options, fundamentals, or live trading infrastructure.

## Data Policy

Do not commit generated market data, raw vendor/API responses, database files, or secrets.

Ignored local artifacts include:

- `.env.local`
- `data/pit_market.duckdb`
- `data/raw/**`
- `data/staging/**`
- `data/normalized/**`
- `data/research/**`
