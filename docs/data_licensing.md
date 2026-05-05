# Data Licensing

## Policy

Adapters declare a `license_tier`:

- `public`
- `free_api`
- `licensed`
- `alt_data`

In production, licensed or alternative-data adapters must have explicit credential environment variables before they can be enabled.

## MVP Sources

Preferred MVP sources:

- SEC EDGAR for filings.
- FRED for macro series.
- Kenneth French data library for style factors.

Price data requires a confirmed source before production use.

## Implemented

- Kenneth French daily five-factor parser. No API key required. The current public file is not a point-in-time vintage feed, so rows are timestamped as available at ingestion time.
- FMP historical price parser and ingestion CLI. Requires `FMP_API_KEY`; current historical responses are timestamped as available at ingestion time.
- SEC EDGAR submissions parser and ingestion CLI. Requires `EDGAR_USER_AGENT`; no API key required.
- FRED CSV macro ingestion for public development macro series. Observations are timestamped as available at ingestion time unless a vintage-aware source is added.
- FMP price ingestion now fails closed in production unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- MVP sector, peer, and exposure mappings are curated development data from `config/mvp_universe.json`; they are not vendor classifications.
