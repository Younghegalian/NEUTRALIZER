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
| Yahoo delisted probe attempts | 9,133 |
| Yahoo delisted probe successes | 2,413 |
| Yahoo delisted probe no-data | 6,674 |
| Yahoo delisted probe errors | 46 |
| Final delisted-source symbols | 2,391 |
| Delisted-source universe memberships | 1,294,263 |

## Known Gaps

- SEC Form 25/25-NSE filings do not always include ticker symbols.
- Form 3/4/5 historical ticker mapping is incomplete for issuers without insider filings.
- Yahoo may remove delisted symbols, return no data, or expose OTC successor symbols.
- Ticker reuse can contaminate historical joins when metadata is weak.
- Kaggle and FMP coverage depends on available plan/data limits.

## Audit Files

- `data/research/yahoo_delisted_probe_coverage.parquet`
- `data/normalized/duplicate_report.parquet`
- `data/normalized/bad_rows_report.parquet`
