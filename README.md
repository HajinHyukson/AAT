# AAT Single-Stock Attribution Engine

AAT is an alpha-stage single-stock attribution engine. It computes deterministic close-to-close returns, applies point-in-time visible factor contributions, and reports an explicit unexplained residual.

The project is currently centered around two backfill tracks:

- A live FaustCalc-expanded full-history attribution backfill on the server database.
- A local S&P 500 pilot backfill for methodology development and residual-share safety work.

## Backfill Warning

The FaustCalc server backfill is treated as a live production-like data job until it finishes and a post-backfill backup is created.

While that job is active, do not deploy or run changes on the server that require:

- Alembic migrations.
- Schema or constraint changes.
- Destructive DB commands.
- Rebuilding backfill tasks.
- Changing FaustCalc import, promotion, or loading order.
- Changing persisted attribution/backfill semantics for already-created tasks.

Safe work during the live backfill is mostly frontend, read-only API, documentation, tests, and local-only pilot DB work. See [docs/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md](docs/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md).

## FaustCalc Server Backfill

The server database is the source of truth for the expanded FaustCalc universe. The active run id is:

```text
a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c
```

Check status from the server Ubuntu repo:

```bash
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --status-only
```

Check status remotely from this development machine:

```powershell
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution"
python -m jobs.run_faustcalc_attribution_backfill --status-only
```

Resume on the server:

```bash
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --workers 1 --progress-every 10 --worker-id server-1
```

Optional remote worker from this development machine:

```powershell
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution"
python -m jobs.run_faustcalc_attribution_backfill --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --workers 1 --progress-every 10 --worker-id dev-1
```

Distributed workers are supported only when every worker is running the advisory-lock-aware code. Start conservatively and monitor Postgres, disk, and CPU pressure.

After the FaustCalc backfill completes:

```bash
python -m jobs.refresh_attribution_summaries --prefer-compose-port
```

Then verify the expanded universe API:

```bash
curl "http://localhost:8000/universe?limit=50&prefer_compose_port=true"
```

Detailed FaustCalc data and backfill notes live in [docs/FAUSTCALC_DATA_IMPLEMENTATION_REPORT.md](docs/FAUSTCALC_DATA_IMPLEMENTATION_REPORT.md).

## Local S&P 500 Pilot Backfill

Use the local pilot DB for methodology work while the server backfill runs. The pilot DB is named:

```text
aat_pilot_sp500
```

Initialize the pilot DB:

```powershell
python -m jobs.init_pilot_sp500_db
```

Populate pilot prices, factors, proxy ETFs, and generated mappings:

```powershell
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@localhost:55432/aat_pilot_sp500"
python -m jobs.populate_pilot_sp500_data --from 2023-01-01 --to 2026-05-06
```

Check pilot progress:

```powershell
python -m jobs.check_pilot_sp500_progress --from 2023-01-01 --to 2026-05-06
```

Resume the monthly residual-safety pilot attribution run:

```powershell
python -m jobs.run_pilot_sp500_attribution --from 2023-01-01 --to 2026-05-06 --cadences monthly --methodology residual_safety_v1
```

The pilot runner skips already-existing windows by default. To intentionally recompute existing windows, add:

```powershell
--rerun-existing
```

Recommended pilot order:

```powershell
python -m jobs.run_pilot_sp500_attribution --from 2023-01-01 --to 2026-05-06 --cadences monthly --methodology residual_safety_v1
python -m jobs.run_pilot_sp500_attribution --from 2023-01-01 --to 2026-05-06 --cadences weekly --methodology residual_safety_v1
python -m jobs.run_pilot_sp500_attribution --from 2023-01-01 --to 2026-05-06 --cadences daily --methodology residual_safety_v1
```

Then run the research methodology:

```powershell
python -m jobs.run_pilot_sp500_attribution --from 2023-01-01 --to 2026-05-06 --cadences monthly --methodology hierarchical_market_first_v1
```

Evaluate pilot methodology outputs:

```powershell
python -m jobs.evaluate_pilot_methodologies
```

## Current Implementation

Implemented:

- Python engine with typed Pydantic contracts, deterministic return accounting, French five-factor attribution, expanded sector/peer/style/macro helpers, event taxonomy, exposure gates, confidence scoring, replay audit helpers, and deterministic narrative generation.
- SQLAlchemy and Alembic schema for companies, securities, price bars, factors, macro series, events, exposures, attribution runs, contribution evidence, peer baskets, sector classifications, event taxonomy/surprises, analyst feedback, backfill tasks, universe membership, and attribution summaries.
- Adapters and ingestion jobs for FMP prices, Kenneth French factors, SEC EDGAR submissions, FRED macro series, curated MVP universe mappings, FaustCalc imports, S&P 500 pilot population, and proxy factor-return construction.
- FastAPI endpoints and a Next.js dashboard for universe state, run history, grouped driver tables, evidence payloads, CSV export, exposure decisions, narrative text, and analyst feedback.
- Resumable FaustCalc full-history attribution backfill with DB-backed progress, window checkpointing, advisory locks, and optional distributed workers.
- Local S&P 500 pilot methodology workflow with residual-share safety and hierarchical market-first research attribution.

Latest local verification:

```powershell
python -m pytest tests\unit tests\lookahead_audit
```

Recent result: `105 passed`.

## Legacy Proving Backfills

Start local Postgres and migrate:

```powershell
docker compose up -d postgres
.\scripts\run_alembic.ps1 upgrade head
```

Run the MVP proving workflow:

```powershell
python -m jobs.run_mvp_proving_backfill --prefer-compose-port --to 2026-05-06
```

Run the historical 50-name universe workflow:

```powershell
python -m jobs.run_historical_universe_backfill --prefer-compose-port --to 2026-05-06
```

Dry-run without network calls:

```powershell
python -m jobs.run_mvp_proving_backfill --dry-run --skip-alembic --to 2026-05-06
python -m jobs.run_historical_universe_backfill --dry-run --skip-alembic --to 2026-05-06
```

## Production Boundary

- FMP price data is development-only unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- FaustCalc/FMP-derived snapshot data remains development/proving data unless source rights are confirmed.
- Event rows and return-based style descriptors remain evidence-only until calibrated production contribution methods exist.
- FRED and French factor data are not fully vintage-aware in the current ingestion path.
- Confidence labels are qualitative data/model-quality flags, not calibrated probabilities.
- The model still needs real-data proving, residual reduction analysis, out-of-sample validation, confidence calibration, and final source/license confirmation before it should be treated as production-complete.

## Key Docs

- [PROJECT_STATUS.md](PROJECT_STATUS.md): most recent implementation state and next action.
- [docs/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md](docs/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md): rules while the server FaustCalc backfill is active.
- [docs/FAUSTCALC_DATA_IMPLEMENTATION_REPORT.md](docs/FAUSTCALC_DATA_IMPLEMENTATION_REPORT.md): FaustCalc data contents, migration state, and server backfill status.
- [docs/AAT_FUNCTIONAL_REPORT.md](docs/AAT_FUNCTIONAL_REPORT.md): full system behavior and methodology boundaries.
- [docs/RESIDUAL_SHARE_METHODOLOGY_ISSUE.md](docs/RESIDUAL_SHARE_METHODOLOGY_ISSUE.md): residual-share problem and methodology fixes.
- [ARCHITECTURE.md](ARCHITECTURE.md): system architecture and model boundary.
- [BUILD.md](BUILD.md): build workflow and proving commands.
- [docs/attribution_methodology.md](docs/attribution_methodology.md): attribution rules and contribution stages.
