# Build Workflow

## Current State First

The repo has an executable expanded MVP scaffold. The current model can run:

- Deterministic adjusted close-to-close return accounting.
- French five-factor baseline attribution.
- Expanded MVP attribution with sector/industry proxy factors, custom peer baskets, return-based style evidence, FRED macro factors, and EDGAR event evidence.
- Explicit `unexplained_residual` reconciliation.
- Point-in-time filtering by `timestamp_available <= attribution_cutoff`.
- Driver-table dashboard with grouped drivers, evidence payloads, CSV export, run history, exposure decisions, narrative text, and analyst feedback persistence.
- MVP proving backfill orchestration with dry-run support and coverage reporting.
- Historical universe backfill orchestration for three years of daily, weekly, and monthly expanded attribution runs.

Latest local verification:

```powershell
python -m pytest tests/unit tests/lookahead_audit
```

Result: 50 tests passed on 2026-05-04.

The next operational step is running the historical universe backfill with real local credentials, then validating coverage and dashboard output.

```powershell
python -m jobs.run_historical_universe_backfill --prefer-compose-port --to 2026-05-04
```

## MVP Order

1. Schema and migrations.
2. Free/public adapters.
3. Deterministic return accounting.
4. Factor baseline attribution.
5. Look-ahead audit suite.
6. Driver-table dashboard.
7. Event NLP.
8. Exposure update logic.

## Current Build Slice

The MVP now has executable slices through step 8:

- Schema and migrations
- FMP, EDGAR, and Kenneth French ingestion
- Deterministic return accounting
- French five-factor baseline attribution
- Initial look-ahead audit suite with timestamp-schema and leakage probes
- Driver-table dashboard
- Structured EDGAR event features
- Conservative exposure update decisions
- Expanded attribute metadata and contribution evidence payloads
- Sector/industry, peer, style-evidence, macro, and EDGAR event-evidence attribution paths
- Analyst feedback persistence, dashboard evidence drawer, driver grouping, and CSV export
- Expanded MVP proving backfill orchestration
- Historical universe backfill orchestration with `backfill_run` audit records

## MVP Proving Run

Use this command after local Postgres is migrated and `.env` has `FMP_API_KEY`:

```powershell
python -m jobs.run_mvp_proving_backfill --prefer-compose-port --to YYYY-MM-DD
```

Dry-run the orchestration without network calls:

```powershell
python -m jobs.run_mvp_proving_backfill --dry-run --skip-alembic --to YYYY-MM-DD
```

The proving run seeds the 50-name universe, backfills MVP and proxy prices, ingests French and FRED factors, builds sector/industry proxy factor returns, refreshes EDGAR event features, runs expanded attribution, runs replay look-ahead audit, and prints coverage diagnostics.

## Three-Year Historical Backfill

Use this command after local Postgres is migrated and `.env` has `FMP_API_KEY` and `EDGAR_USER_AGENT`:

```powershell
python -m jobs.run_historical_universe_backfill --prefer-compose-port --to YYYY-MM-DD
```

Dry-run the orchestration:

```powershell
python -m jobs.run_historical_universe_backfill --dry-run --skip-alembic --to YYYY-MM-DD
```

The historical backfill seeds the universe, backfills price/factor/macro inputs with a regression-lookback buffer, builds proxy factor returns, ingests available recent EDGAR evidence, generates daily/weekly/monthly expanded attribution runs, runs replay look-ahead audit, and persists a `backfill_run` coverage summary.

## Remaining v0 Hardening And Validation

- Run the historical universe backfill against local Postgres with real credentials and verify daily, weekly, and monthly expanded attribution coverage in the dashboard/API.
- Confirm the production price-data source and license position. FMP remains development-only unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- Add residual reduction analysis by phase and out-of-sample validation for expanded factor additions.
- Add collinearity diagnostics, confidence calibration diagnostics, per-driver missing-data reports, and source availability reports.
- Keep event rows evidence-only until event-study calibration exists.
- Keep options, borrow cost, dealer gamma, and licensed analyst/estimates data out of production until data rights and timestamp policy are confirmed.

## Stop Points

Stop for manual input when work requires:

- API keys or vendor credentials.
- Licensed market/news/estimates data.
- Product scope choices that change MVP behavior.
- Running infrastructure services that are not already available locally.
