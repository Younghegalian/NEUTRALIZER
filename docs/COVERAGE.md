# Coverage Notes

NEUTRALIZER is survivorship-reduced, not survivorship-bias-free.

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

## Audit Files

- `data/research/yahoo_delisted_probe_coverage.parquet`
- `data/research/yahoo_delisted_probe_metadata_audit.parquet`
- `data/normalized/duplicate_report.parquet`
- `data/normalized/bad_rows_report.parquet`
