# Coverage Notes

FONA is survivorship-reduced, not survivorship-bias-free.

Coverage is split into two different questions:

- SEC-led discovery coverage: how many delisting events, CIKs, and candidate tickers were found.
- Price-bar recovery coverage: how many of those candidates could actually produce daily OHLCV rows from Yahoo, Kaggle, or other price sources.

## Latest Local Coverage

| Metric | Value |
| --- | ---: |
| SEC Form 25/25-NSE filings | 28,144 |
| SEC delisting CIKs | 8,731 |
| SEC candidate tickers | 10,962 |
| Yahoo delisted raw cache inspected | 4,441 |
| Yahoo equity/ETF/USD cache accepted | 1,813 |
| Yahoo cache rejected by instrument/currency/empty parse | 2,628 |
| Final delisted-source symbols | 1,782 |
| Delisted-source universe memberships | 975,928 |

## Backtest Lifecycle Coverage

FONA keeps raw prices untouched and applies delisting policy in separate backtest tables:

- `security_events`: lifecycle events from price coverage, FMP metadata, and SEC Form 25/25-NSE filings.
- `terminal_events`: last available close on or before selected delisting events; no artificial zero-price fill.
- `backtest_universe_membership`: `US_DAILY_LIFECYCLE_ADJUSTED_V2`, excluding dates after selected delisting events.

Latest lifecycle build:

| Metric | Value |
| --- | ---: |
| Security lifecycle events | 13,635 |
| Selected terminal delisting events | 1,778 |
| Terminal events with price | 1,013 |
| Zero terminal prices | 0 |
| Lifecycle-adjusted universe memberships | 13,162,013 |
| Base universe rows removed by lifecycle policy | 578,802 |
| Membership rows after selected delisting event | 0 |

Delisting events are applied only to symbols with delisted-source price coverage. This reduces ticker-reuse false positives, but it also means unpriced delisting candidates remain coverage gaps rather than simulated zero-price rows.

## Annual Flow Audit

Annual listing and delisting fit is measured with:

```powershell
python -m src.tools.audit_market_flows --fetch-benchmarks --output data\research\market_flow_audit.csv
```

Latest `backtest_stock_major_universe` completed-year medians:

| Metric | Value |
| --- | ---: |
| Public benchmark listing rate | 6.93% |
| Public benchmark delisting rate | 7.16% |
| Local SEC price-recovered delisting rate | 5.16% |
| Local delisted-event capture vs benchmark | 71.68% |
| Lifecycle-adjusted universe entry rate | 9.09% |
| Lifecycle-adjusted universe exit rate | 1.21% |
| Lifecycle-adjusted delisted-source universe exit rate | 0.88% |

Interpretation: SEC-led price recovery captures a meaningful share of annual delisting events and the lifecycle-adjusted universe now removes all dates after selected delisting events. Local universe exits are still lower than CRSP-grade lifecycle coverage because many public delisting candidates remain unpriced or never pass the liquidity universe. Treat the database as survivorship-reduced unless a paid lifecycle identifier source such as CRSP, Norgate, Sharadar, Refinitiv, or Polygon delisted history is added.

## Latest Classification Coverage

| Metric | Value |
| --- | ---: |
| Security master symbols | 11,803 |
| Stock-classified symbols | 6,923 |
| ETF-classified symbols | 4,861 |
| Unknown/fund symbols | 19 |
| Sector/industry-enriched symbols | 184 |

## Latest Local Validation

| Check | Result |
| --- | ---: |
| Duplicate `(date, symbol)` keys | 0 |
| Null required OHLCV fields | 0 |
| Non-positive OHLC rows | 0 |
| Negative volume rows | 0 |
| `high < low` rows | 0 |
| `open`/`close` outside `[low, high]` rows | 0 |
| Future-dated rows | 0 |
| Weekend rows | 0 |

## Known Gaps

- SEC Form 25/25-NSE filings do not always include ticker symbols.
- Form 3/4/5 historical ticker mapping is incomplete for issuers without insider filings.
- Yahoo may remove delisted symbols, return no data, or expose OTC successor symbols.
- Ticker reuse can contaminate historical joins when metadata is weak.
- SEC Form 25/25-NSE filing dates are proxies when no FMP `delistedDate` is available.
- Terminal event prices are last available closes, not CRSP-style delisting returns.
- Kaggle and FMP coverage depends on available plan/data limits.
- Yahoo adjusted historical prices and vendor volume can still distort dollar-volume estimates for heavily split-adjusted securities.
- Sector and industry coverage depends on cached FMP profile requests and will grow incrementally under API limits.

## Audit Files

- `data/research/yahoo_delisted_probe_coverage.parquet`
- `data/research/yahoo_delisted_probe_metadata_audit.parquet`
- `data/research/market_flow_audit.csv`
- `data/research/security_events.parquet`
- `data/research/terminal_events.parquet`
- `data/research/backtest_universe_membership.parquet`
- `data/normalized/duplicate_report.parquet`
- `data/normalized/bad_rows_report.parquet`
