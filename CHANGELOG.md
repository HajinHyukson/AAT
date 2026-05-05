# Changelog

## 2026-05-04

- Added cadence-aware attribution runs for daily, weekly, and monthly historical attribution.
- Added `backfill_run` audit records for historical population attempts.
- Added `jobs.run_historical_universe_backfill` for three-year universe data and attribution population.
- Added cadence filters and response fields to attribution run API endpoints.
- Surfaced attribution cadence in dashboard run details and run history.
- Added a curated 50-name MVP universe seed and entity resolver fixture cases.
- Added jobs to seed MVP securities, sector/industry mappings, peer baskets, and exposure gates.
- Added public FRED macro ingestion and proxy price-to-factor-return construction for sector/industry factors.
- Wired expanded MVP attribution mode with sector/industry, peer basket, style evidence, macro factors, and EDGAR event evidence.
- Added deterministic attribution narrative generation.
- Added contribution IDs, evidence payloads, contribution stages, and analyst feedback persistence to the API.
- Added dashboard driver grouping, evidence payload display, CSV export, narrative display, and feedback submission.
- Added replay-style look-ahead audit helper and command.
- Added production fail-closed guard for unconfirmed FMP price licensing.
- Added MVP proving backfill orchestration, dry-run support, coverage reporting, and focused tests for API feedback and proving-run diagnostics.

## 2026-05-03

- Added initial backend/engine scaffold.
- Added Pydantic attribution contracts.
- Added deterministic close-to-close return accounting with point-in-time filtering.
- Added minimal factor-baseline attribution and explicit residual reconciliation.
- Added adapter protocol and production licensing gate.
- Added FastAPI health/version endpoints.
- Added initial docs and focused unit tests.
- Added SQLAlchemy schema models and initial Alembic migration for canonical entities.
- Added Kenneth French daily five-factor adapter parser with offline unit coverage.
- Added Docker Compose configuration for local Postgres + TimescaleDB.
- Added DB session helpers, Alembic helper script, and FMP historical price ingestion CLI.
- Added baseline attribution CLI that reads ingested prices and persists attribution runs.
- Added SEC EDGAR submissions parser and ingestion CLI.
- Added API response schema and latest attribution run endpoint.
- Added initial Next.js dashboard driver table against the latest attribution endpoint.
- Added Kenneth French factor ingestion and a simple point-in-time market-factor attribution baseline.
- Added structured EDGAR event features and conservative exposure update decision logic.
- Added exposure update decisions to the dashboard view.
- Added initial look-ahead audit suite with timestamp and leakage probes.
- Added idempotent attribution runs, daily/weekly/monthly batch runner, French five-factor attribution, and historical run API/dashboard support.
