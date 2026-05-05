# Financial Modeling Prep Adapter

The MVP uses FMP for daily historical prices when a valid `FMP_API_KEY` is present.

## Endpoint

Default endpoint:

`{FMP_BASE_URL}/historical-price-eod/full?symbol={ticker}&from=YYYY-MM-DD&to=YYYY-MM-DD&apikey=...`

FMP's current documented base URL is `https://financialmodelingprep.com/stable`. If `FMP_BASE_URL` is still set to the older `https://financialmodelingprep.com/api`, the client automatically targets the equivalent stable base URL. The parser is kept separate from the HTTP client so tests stay offline.

## Timestamp Policy

- `event_time`: market date at midnight UTC
- `ingestion_time`: adapter run time
- `timestamp_available`: adapter run time

This is conservative because FMP historical files are not point-in-time vintages. Backtests will only see bars ingested before the attribution cutoff.
