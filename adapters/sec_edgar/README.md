# SEC EDGAR Adapter

Source: SEC EDGAR public APIs.

The submissions endpoint is:

`https://data.sec.gov/submissions/CIK##########.json`

The adapter requires `EDGAR_USER_AGENT` in `.env`. The SEC asks automated tools to identify themselves in request headers.

## Timestamp Policy

For filing metadata:

- `event_time`: accepted timestamp when present, otherwise filing date at midnight UTC
- `ingestion_time`: adapter run time
- `timestamp_available`: accepted timestamp when present, otherwise ingestion time

The accepted timestamp is the earliest structured timestamp exposed by the submissions API. If it is missing, the conservative fallback is ingestion time.
