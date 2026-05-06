# Project Status

Last updated: 2026-05-05

## Current Snapshot

The project is an executable MVP v0 scaffold with expanded attribution plumbing, not yet a production-complete attribution model.

Detailed FaustCalc migration, data-content, server DB, and backfill progress notes now live in `docs/FAUSTCALC_DATA_IMPLEMENTATION_REPORT.md`.

Live-backfill development restrictions are documented in `docs/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md`. Until the server FaustCalc backfill completes, avoid schema migrations, DB-loading changes, and backfill-contract changes unless the job is stopped, backed up, and resumed deliberately.

Current implemented surface:

- Deterministic adjusted close-to-close return accounting.
- French five-factor baseline attribution.
- Expanded MVP mode for sector/industry proxy factors, custom peer baskets, return-based style evidence, FRED macro factors, and EDGAR event evidence.
- Explicit `unexplained_residual` on every attribution result.
- Point-in-time filtering through `timestamp_available <= attribution_cutoff`.
- FastAPI endpoints and a Next.js dashboard with driver grouping, evidence payloads, CSV export, narrative display, run history, exposure decisions, and analyst feedback persistence.
- Replay-style look-ahead audit helper, MVP proving backfill orchestration, and three-year historical universe backfill orchestration.

Latest local verification:

```powershell
python -m pytest tests/unit tests/lookahead_audit
```

Result: 84 tests passed on 2026-05-05.

Current production boundary:

- FMP price data is development-only unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- Event rows and return-based style descriptors remain evidence-only unless a calibrated production factor return exists.
- The model still needs real-data proving, residual reduction analysis, out-of-sample validation, confidence calibration, and production source/license confirmation.

## Milestone

Current target: MVP v0 scaffold.

## Completed This Cycle

- Converted the bootstrap docs into an executable Python scaffold.
- Added typed contracts for price bars, factor inputs, contributions, and attribution results.
- Added deterministic return accounting.
- Added baseline factor attribution with residual reconciliation.
- Added adapter licensing checks.
- Added API health endpoint.
- Added initial tests.
- Added canonical database models and initial Alembic migration.
- Added initial Kenneth French factor adapter parser.
- Added Docker Compose configuration for local Postgres + TimescaleDB.
- Added FMP historical price parser and ingestion CLI.
- Added baseline attribution CLI for ingested price bars.
- Added SEC EDGAR submissions parser and ingestion CLI.
- Added latest attribution run API endpoint.
- Added initial Next.js dashboard driver table.
- Added French factor ingestion and market-factor baseline support in attribution runs.
- Added structured EDGAR event features and conservative exposure update decisions.
- Surfaced exposure update decisions in the dashboard.
- Added initial look-ahead audit suite under `tests/lookahead_audit`.
- Added idempotent attribution runs and daily/weekly/monthly batch attribution.
- Added French five-factor baseline attribution.
- Added historical attribution run API endpoints and dashboard run history.
- Added expanded attribute metadata, sector/peer/style/macro/event scaffolding, and contribution evidence payloads.
- Added curated 50-name MVP universe seed, sector/industry mappings, peer baskets, exposure gates, and entity resolver cases.
- Added FRED macro ingestion, proxy factor-return construction, expanded MVP attribution mode, and daily MVP batch runner.
- Added deterministic narrative generation, analyst feedback API persistence, dashboard evidence drawer, driver grouping, and CSV export.
- Added replay-style look-ahead audit helper and command.
- Added MVP proving backfill orchestration with dry-run support, price/factor/macro/event/backtest workflow, coverage reporting, and success threshold handling.
- Added cadence-aware attribution runs, `backfill_run` audit records, and historical universe backfill orchestration for daily, weekly, and monthly expanded attribution runs.
- Added FaustCalc staging models/migrations, feature-store and SEC filing import CLIs, SEC cleanup/dedupe logic, and FaustCalc migration tests.
- Applied FaustCalc staging migration to the local compose database and imported the SEC filing snapshot: 2,009 deduped filings staged, 576 canonical events promoted, and 576 event features generated.
- Imported the FaustCalc feature-store snapshot into staging and promoted 11,265,327 representable price rows into canonical `price_bar`; 2,520 staged price rows remain audit-only because they are outside canonical `price_bar` precision/range.
- Confirmed attribution jobs run against the FaustCalc-augmented compose database; price loading now dedupes overlapping same-day sources by latest point-in-time-visible bar before return calculation.
- Added FaustCalc active-US-equity universe membership, attribution backfill task progress, and frontend attribution summary tables plus supporting indexes.
- Built the local `faustcalc_active_us_equities` universe from the compose database: 12,657 eligible active USD stock securities with FaustCalc price coverage.
- Seeded generated FaustCalc sector/industry classifications, peer baskets, and macro exposure gates without overwriting curated MVP mappings.
- Optimized `/universe` to query precomputed summaries with SQL pagination; local API response for `limit=50` is now under 1 second against 12,657 names.
- Added resumable FaustCalc full-history attribution backfill orchestration and preloaded price/factor/macro series reuse for large attribution runs.
- Added DB-backed progress output to the FaustCalc attribution backfill command, including completed task count out of the total task count.
- Optimized the FaustCalc attribution backfill for local execution: reusable peer basket context avoids repeated peer price loads, tasks now checkpoint every window chunk, `--task-order expected-windows` runs the smallest positive-window tasks first, and `--status-only` prints tracker state without running work.
- Fixed DB session pooling so repeated checkpoint sessions reuse a small shared SQLAlchemy pool instead of exhausting the local Postgres client limit.
- Added distributed FaustCalc backfill coordination with Postgres advisory task locks, opt-in `--workers`, worker IDs, lock-miss progress reporting, and concurrency-safe attribution run upserts.

## Where We Left Off

Local TimescaleDB runs on host port `55432` to avoid the existing Windows Postgres on `5432`. Use:

```powershell
docker compose up -d postgres
.\scripts\run_alembic.ps1 upgrade head
```

Next build step is running the FaustCalc universe attribution backfill in controlled batches and refreshing summaries afterward:

```powershell
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --batch-size 200
python -m jobs.refresh_attribution_summaries --prefer-compose-port
```

The current local FaustCalc backfill run can be resumed with:

```powershell
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --progress-every 10
```

Check progress without running work:

```powershell
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --status-only
```

Manual input likely needed soon:

- Confirm the MVP production price-data source and license status. FMP remains development-only unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- Fill real values in `.env` for `FMP_API_KEY` and `EDGAR_USER_AGENT`. FRED CSV ingestion does not require a key.
