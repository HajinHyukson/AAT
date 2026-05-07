# AAT Single-Stock Attribution Engine

AAT is an alpha-stage single-stock attribution engine. It computes deterministic close-to-close returns, applies point-in-time visible factor contributions, and reports an explicit unexplained residual.

The project is currently centered around two backfill tracks:

- A live FaustCalc-expanded full-history attribution backfill on the server database.
- A local S&P 500 pilot backfill for methodology development and residual-share safety work.

## Where The Project Is Now

AAT is between an MVP scaffold and a complete attribution platform.

The current version can ingest market and event data, preserve large source snapshots, build named security universes, run point-in-time attribution windows, store contribution rows, and power a dashboard/API. It is good enough for proving the architecture and running research-scale backfills.

The full version is intended to be a production-grade attribution system with licensed point-in-time data, calibrated factor and event contribution methods, out-of-sample validation, confidence calibration, stable residual diagnostics, and operational monitoring around every data and model layer.

Current state by major capability:

| Capability | Current Version | Complete Version Target |
|---|---|---|
| Data ingestion | FMP/FaustCalc/French/FRED/EDGAR adapters and import jobs exist. FaustCalc prices and filings are staged and partially promoted. | Licensed production data sources, point-in-time vintages, corporate-action validation, and source-priority governance. |
| Entity model | `company`, `security`, ticker history, sector classification, peer baskets, and universe membership are implemented. | Robust issuer/security/share-class handling, corporate actions, identifiers, delistings, restatements, and audit workflows. |
| Attribution engine | French five-factor, sector, peer, macro, style descriptors, event evidence, residual safety, and pilot hierarchical methodology exist. | Calibrated production methodology with residualized or regularized factors, event impact models, validation gates, and stable reporting rules. |
| Backfill execution | Large FaustCalc backfill is resumable, checkpointed, and can use advisory-lock-aware distributed workers. Local S&P pilot backfill supports resume-by-skipping completed windows. | Scheduler-managed jobs, monitoring, retries, resource controls, post-run validation, and reproducible run manifests. |
| Dashboard/API | Universe, attribution, evidence, summary, feedback, and export paths exist. Expanded universe summary depends on backfill completion. | Fast paginated production dashboards with quality flags, coverage explanations, model comparisons, and operational health surfaces. |
| Validation/governance | Unit tests, look-ahead audit tests, guardrail docs, and source/license warnings exist. | Formal model validation, source entitlement checks, confidence calibration, out-of-sample promotion gates, and release controls. |

## AAT Layers

AAT is easier to reason about as a stack. The active backfills are moving data through this stack from lower layers into attribution outputs and dashboard summaries.

### 1. Source And Adapter Layer

This layer pulls or receives raw source data. Current sources include FMP-style prices, the FaustCalc feature-store snapshot, Kenneth French factor files, FRED macro series, SEC EDGAR submissions, proxy ETF prices, and the static S&P 500 pilot universe config.

Its job is to know how to talk to each source and convert responses into typed Python records. It should not decide final model truth. In the complete version, this layer also needs source entitlements, data-vintage handling, retry policy, corporate-action checks, and clear source-priority rules.

### 2. Staging And Snapshot Preservation Layer

This layer preserves imported source data without prematurely collapsing it into AAT's canonical model. FaustCalc uses `faustcalc_` staging tables for assets, companies, prices, fundamentals, price features, theme scores, filing analysis, peer analysis, and SEC filing catalogs.

The purpose is auditability. If a source row is messy, duplicated, or not promotion-ready, AAT can keep it in staging while rejecting or delaying canonical promotion. The current FaustCalc import already follows this pattern. The full version should extend the same discipline to every large vendor or public data source.

### 3. Canonical Market And Event Layer

This layer contains AAT's normalized tables: `company`, `security`, `security_ticker_history`, `price_bar`, `factor_return`, `macro_series`, `event`, and `event_feature`.

Attribution jobs read from this layer, not directly from source snapshots. FaustCalc has already promoted roughly 11.3 million representable price bars into `price_bar`, and SEC filing imports promoted canonical event rows/features. The complete version needs stronger corporate-action validation, vintage-aware macro/factor rows, and source/license governance.

### 4. Universe And Identity Layer

This layer decides what securities are runnable for a workflow. AAT does not assume every security in `security` belongs in every runtime universe.

Current named universes include:

- `faustcalc_active_us_equities` on the server: active USD stock securities from FaustCalc with canonical price coverage.
- `pilot_sp500_static` locally: static S&P 500 pilot rows from `config/pilot_sp500_universe.json`.

The full version should support multiple named universes, universe versions, inclusion/exclusion reasons, delisted names, liquidity filters, analyst watchlists, and benchmark-specific cohorts.

### 5. Mapping, Classification, And Exposure Layer

This layer adds economic context: sector/subindustry, peer baskets, proxy mappings, macro exposure gates, and curated company exposures.

Current curated MVP mappings are preserved as higher-confidence rows. FaustCalc and S&P pilot jobs generate deterministic mappings to fill gaps without overwriting curated mappings. The complete version should add analyst review, confidence levels, model promotion gates, and multiple mapping versions for research versus production.

### 6. Factor, Event, And Evidence Layer

This layer builds the explanatory inputs used by attribution: French factors, sector and industry proxy factors, peer basket returns, macro factor transforms, return-style descriptors, EDGAR filing evidence, and event taxonomy/surprise features.

The current version treats events and style descriptors mostly as evidence-only. They help explain context, but they do not yet reduce residual as calibrated causal contribution rows. The complete version should include validated event-impact models and explicit event contribution promotion rules.

### 7. Attribution Methodology Layer

This layer turns returns and evidence into contribution rows. It computes observed return, factor contributions, event/evidence rows, and the accounting residual.

Current methodologies include:

- `legacy`: the existing expanded additive stack.
- `residual_safety_v1`: legacy attribution plus safer residual-share diagnostics and display behavior.
- `hierarchical_market_first_v1`: local pilot research methodology that residualizes lower layers after market/French factors.

The current residual is an accounting residual, not yet a fully clean idiosyncratic residual. The complete version should use residualized or regularized multivariate factor models, beta stability gates, contribution leverage diagnostics, calibrated confidence, and out-of-sample validation.

### 8. Backfill Orchestration Layer

This layer decides which windows to run, tracks progress, resumes interrupted work, and prevents duplicate outputs.

The FaustCalc backfill creates one task per security/cadence, checkpoints within long tasks, and stores progress in `attribution_backfill_task`. It uses Postgres advisory locks so multiple workers can join the same run safely when they run compatible code.

The S&P pilot runner is lighter: it checks existing attribution rows and skips already-completed windows by default. It is meant for local methodology iteration, not server-scale production scheduling.

The complete version should add job scheduling, worker health monitoring, retry dashboards, resource controls, alerting, and post-run validation reports.

### 9. Summary, API, And Dashboard Layer

This layer turns raw attribution rows into something fast and usable. The `security_attribution_summary` table stores latest run status, latest price, top driver, contribution count, sector/industry, and coverage flags for `/universe`.

The server expanded dashboard will not look complete until the FaustCalc backfill finishes and `jobs.refresh_attribution_summaries` is run. The full version should show coverage gaps, freshness, methodology version, residual stability, and model-quality diagnostics directly in the UI.

### 10. Validation And Governance Layer

This layer protects the system from look-ahead bias, unstable methodology, source misuse, and unsafe operational changes.

Current validation includes unit tests, look-ahead audit tests, live-backfill guardrail docs, source/license warnings, and residual-share methodology notes. The full version needs formal model validation, out-of-sample promotion tests, source entitlement review, production runbooks, release gates, and backup/restore discipline.

## What The Backfills Are Doing

The active backfills are not just "running calculations." They are proving whether all layers can work together over many securities, windows, and data-quality conditions.

### FaustCalc Server Backfill

The FaustCalc backfill runs on the server database against the `faustcalc_active_us_equities` universe. The current universe contains about 12.6k eligible active USD stock securities with FaustCalc price coverage. For each security and each cadence, AAT builds valid historical windows and runs expanded attribution wherever the inputs exist.

At a high level, each task does this:

1. Claim a `security + cadence` task using DB-backed task state and advisory locks.
2. Load visible point-in-time price history, factor returns, macro data, and peer context.
3. Build valid daily, weekly, or monthly attribution windows.
4. Skip windows that do not have enough price/factor history.
5. Compute observed return and contribution rows.
6. Persist `attribution_run` and `attribution_contribution` rows using idempotent upserts.
7. Checkpoint `ran_windows`, `skipped_windows`, and `last_window_end`.
8. Mark the task completed, skipped, or failed.

The job is large because it is roughly millions of windows across tens of thousands of `security + cadence` tasks. It is designed to be stopped and resumed. The server DB should remain running, and the code used by all workers should remain compatible with already-created tasks.

### Local S&P 500 Pilot Backfill

The local pilot is intentionally separate from the server. It uses the `aat_pilot_sp500` database and the `pilot_sp500_static` universe so methodology changes can be developed without disturbing the FaustCalc backfill.

The pilot currently has:

- Static S&P 500 universe rows, including share classes.
- FMP price coverage for the S&P names and proxy ETFs.
- Kenneth French factors.
- Proxy factor returns.
- Deterministic peer baskets.
- Residual-safety and hierarchical research methodology paths.

FRED macro may fail locally because the FRED endpoint can time out or reset connections. That is not a blocker for the pilot attribution run; it only means macro contribution rows may be absent or degraded until macro rows are loaded.

The pilot runner now skips existing windows by default, so rerunning a command picks up from where it left off unless `--rerun-existing` is passed.

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
