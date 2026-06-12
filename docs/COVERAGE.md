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

## Annual Flow Audit

Annual listing and delisting fit is measured with:

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
| Local universe entry rate | 9.72% |
| Local universe exit rate | 0.60% |
| Local delisted-source universe exit rate | 0.38% |

Interpretation: SEC-led price recovery captures a meaningful share of annual delisting events, but local universe exits are still too low to claim CRSP-grade survivorship-bias-free coverage. Treat the database as survivorship-reduced unless a paid lifecycle identifier source such as CRSP, Norgate, Sharadar, Refinitiv, or Polygon delisted history is added.

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
- Kaggle and FMP coverage depends on available plan/data limits.
- Yahoo adjusted historical prices and vendor volume can still distort dollar-volume estimates for heavily split-adjusted securities.
- Sector and industry coverage depends on cached FMP profile requests and will grow incrementally under API limits.

## Audit Files

- `data/research/yahoo_delisted_probe_coverage.parquet`
- `data/research/yahoo_delisted_probe_metadata_audit.parquet`
- `data/research/market_flow_audit.csv`
- `data/normalized/duplicate_report.parquet`
- `data/normalized/bad_rows_report.parquet`
