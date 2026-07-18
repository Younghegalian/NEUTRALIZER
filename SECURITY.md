# Security Policy

## Supported Scope

Security reports for the FONA codebase, scripts, and documentation are in scope.

Generated market data, upstream data-provider quality, provider availability, and local trading decisions made with derived outputs are out of scope for security support.

## Reporting

Please report suspected vulnerabilities privately through the repository owner's preferred GitHub security contact if available. If private reporting is not enabled, open a minimal issue that describes the affected area without exposing secrets, credentials, tokens, or exploit-ready payloads.

## Secrets

Never commit:

- `.env.local`
- Kaggle tokens or `kaggle.json`
- FMP API keys
- DuckDB/parquet outputs containing local market data
- Raw vendor/API responses

If a secret is committed, rotate it at the provider immediately and remove it from Git history before making the repository public.
