# Setup

## Local Python

Use Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Environment

Copy `env.example` to `.env` and fill real credentials. Do not commit `.env`.

For the first scaffold, tests do not require external credentials.

## Verification

```powershell
pytest
```

## Local Postgres + TimescaleDB

Start the local database:

```powershell
docker compose up -d postgres
.\scripts\run_alembic.ps1 upgrade head
```

The Compose service reads `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` from `.env`.
It binds the container to host port `POSTGRES_HOST_PORT`, defaulting to `55432` to avoid collisions with an existing local Postgres on `5432`.

## FMP Price Ingestion

```powershell
python -m jobs.ingest_fmp_prices AAPL --from 2026-01-02 --to 2026-01-31 --company-name "Apple Inc." --exchange NASDAQ --prefer-compose-port
```

Run a baseline attribution from ingested prices:

```powershell
python -m jobs.run_attribution AAPL --from 2026-01-02 --to 2026-01-09 --prefer-compose-port
```

With the French five-factor baseline:

```powershell
python -m jobs.ingest_french_factors --from 2024-01-01 --to 2024-03-31 --prefer-compose-port
python -m jobs.run_attribution AAPL --from 2024-03-27 --to 2024-03-28 --use-french-factors --lookback-days 60 --prefer-compose-port
python -m jobs.run_batch_attribution AAPL --from 2024-03-25 --to 2024-03-29 --cadence daily --use-french-factors --lookback-days 60 --prefer-compose-port
```

## EDGAR Filing Ingestion

```powershell
python -m jobs.ingest_edgar_submissions 0000320193 --ticker AAPL --limit 25 --prefer-compose-port
python -m jobs.generate_event_features --prefer-compose-port
python -m jobs.evaluate_exposure_updates --ticker AAPL --lookback-days 30 --prefer-compose-port
```

## API

```powershell
python -m uvicorn api.main:app --reload
```

Latest attribution run:

```text
http://localhost:8000/attribution-runs/latest?ticker=AAPL&prefer_compose_port=true
```

## Dashboard

```powershell
cd dashboard
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:3000?ticker=AAPL
```

Specific historical run:

```text
http://127.0.0.1:3000?ticker=AAPL&runId=<attribution_run_id>
```
