# Single-Stock Attribution Engine

AAT is an alpha-stage single-stock attribution engine. The current repo is an executable MVP v0 scaffold: it computes deterministic close-to-close returns, applies point-in-time visible factor contributions, and reports an explicit `unexplained_residual`.

## Current State

Implemented:

- Python engine with typed Pydantic contracts, deterministic return accounting, French five-factor attribution, expanded sector/peer/style/macro helpers, event taxonomy, exposure gates, confidence scoring, replay audit helpers, and deterministic narrative generation.
- SQLAlchemy and Alembic schema for companies, securities, price bars, factors, macro series, events, exposures, attribution runs, contribution evidence, peer baskets, sector classifications, event taxonomy/surprises, and analyst feedback.
- Adapters and ingestion jobs for FMP prices, Kenneth French factors, SEC EDGAR submissions, FRED macro series, curated MVP universe mappings, and proxy factor-return construction.
- FastAPI endpoints and a Next.js dashboard for universe state, run history, grouped driver tables, evidence payloads, CSV export, exposure decisions, narrative text, and analyst feedback.
- MVP proving backfill orchestration with dry-run support and coverage reporting.
- Three-year historical universe backfill orchestration for daily, weekly, and monthly expanded attribution runs.

Latest local verification:

```powershell
python -m pytest tests/unit tests/lookahead_audit
```

Result: 50 tests passed on 2026-05-04.

## Run The Proving Backfill

Start local Postgres and migrate:

```powershell
docker compose up -d postgres
.\scripts\run_alembic.ps1 upgrade head
```

Run the MVP proving workflow:

```powershell
python -m jobs.run_mvp_proving_backfill --prefer-compose-port --to 2026-05-04
```

Dry-run without network calls:

```powershell
python -m jobs.run_mvp_proving_backfill --dry-run --skip-alembic --to 2026-05-04
```

## Run The Historical Universe Backfill

Populate the current 50-name universe with three years of development historical data and daily, weekly, and monthly attribution runs:

```powershell
python -m jobs.run_historical_universe_backfill --prefer-compose-port --to 2026-05-04
```

Dry-run the orchestration without network calls or database writes:

```powershell
python -m jobs.run_historical_universe_backfill --dry-run --skip-alembic --to 2026-05-04
```

## Production Boundary

- FMP price data is development-only unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- Event rows and return-based style descriptors remain evidence-only until calibrated production contribution methods exist.
- The model still needs real-data proving, residual reduction analysis, out-of-sample validation, confidence calibration, and final source/license confirmation before it should be treated as production-complete.

## Key Docs

- `PROJECT_STATUS.md`: most recent implementation state and next action.
- `ARCHITECTURE.md`: current system architecture and model boundary.
- `BUILD.md`: current workflow and proving commands.
- `docs/attribution_methodology.md`: attribution rules and contribution stages.
- `docs/TEMP_attribute_implementation_plan.md`: temporary backlog for unfinished attribute expansion work.
