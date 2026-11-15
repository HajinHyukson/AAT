# Architecture

Last updated: 2026-05-15

## Current State

The repo has an executable expanded MVP backend/engine/dashboard scaffold:

- `engine/` contains typed contracts, deterministic return accounting, French factor attribution, expanded sector/peer/style/macro attribution helpers, event taxonomy, confidence scoring, exposure gates, replay audit helpers, and a deterministic narrative generator.
- `adapters/` contains the adapter protocol and fail-closed licensing configuration checks.
- `api/` contains FastAPI endpoints for health/version, universe state, methodology selection, attribution runs, chart series, on-demand attribution jobs, exposure decisions, and analyst feedback.
- `db/` and `alembic/` contain the canonical schema, expanded attribute metadata tables, cadence-aware attribution runs, methodology metadata, on-demand jobs, `backfill_run` audit records, FaustCalc staging, universe membership, attribution summaries, and migrations.
- `dashboard/` contains the analyst-facing universe table, methodology selector, attribution detail loader, chart, driver table, evidence drawer, CSV export, run history, exposure decisions, narrative display, and feedback controls.
- `tests/` contains focused unit, look-ahead, and dashboard tests for reconciliation, point-in-time filtering, adapter licensing, expanded attribute primitives, API feedback, on-demand jobs, chart math, and proving-run diagnostics.
- `docs/equity_module/v0.1/` contains the registry-loadable `viza.finance.equity_investment v0.1` artifact corpus, schemas, fixtures, reports, and proof package. The additive loader lives under `viza/equity/`; it validates generated equity registries without modifying `viza.core.strategy`.
- The first equity runtime wedge is feature-flagged under `viza/equity/`: SEC public filings/XBRL evidence, optional FMP market snapshots, optional FRED macro context, `quality_value_long_only` compatibility, non-advice previews, source-rights reporting, and package-redaction preview. It is mock-tested and not production-hardened.
- The Windows packaged desktop prototype has a feature-flagged equity preview path: Electron result sidebar -> local FastAPI sidecar -> `viza/equity` runtime wedge -> mocked SEC-first fixture by default -> PIT/rights/validation/package-redaction preview. Packaged resources include the equity registries and mock fixture under `resources/engine/docs/equity_module/v0.1` after rebuild.
- Equity preview persistence is additive and feature-flagged. It writes run audit rows into the existing local project SQLite store, persists normalized observations through the existing observation store, links evidence/validation/source-rights/package-redaction records, and supports replay from stored observations without live connector calls.
- VIZA MVP Candidate 0.1 adds a narrow package-draft bridge from persisted equity preview runs into the existing `.viza` container/export infrastructure. The bridge supports `white_box`, `output_only`, and `marketplace_draft` draft packages, preserves proof/PIT/rights/validation summaries, and keeps marketplace draft non-monetized and redacted.

Latest local verification:

```powershell
python -m pytest tests\unit tests\lookahead_audit
node --test tests\dashboard\attribution-period-bars.test.mjs
cd apps\viza-desktop; npm run typecheck; npm run test:desktop
cd dashboard; npx tsc --noEmit --project tsconfig.json
```

Result on 2026-05-15:

- Python: `350 passed`.
- Dashboard Node test: `2 passed`.
- VIZA desktop TypeScript typecheck: passed.
- VIZA desktop helper tests: `23 passed`.
- Dashboard TypeScript check: passed.
- Windows packaged build and package smoke: passed after rebuilding the updated sidecar and desktop package.
- Node emitted a module-type warning for `dashboard/components/attribution-period-bars.ts`; the test still passed.

## Model Boundary

The current model is complete enough for MVP proving runs and dashboard inspection. It is not yet complete as a production research model.

Production-style contribution rows currently come from deterministic returns and factor/proxy inputs that the MVP allows to reduce residual. EDGAR event rows and return-based style descriptors are evidence-only unless a calibrated production contribution method exists. Event contribution remains blocked until event-study calibration is implemented and validated. Licensed or alternative data sources remain blocked from production unless their source policy is explicitly confirmed.

## Layering

Layer 1 is deterministic accounting. It computes adjusted close-to-close returns from point-in-time visible price bars.

Layer 2 is statistical attribution. The baseline can estimate French five-factor sensitivities and expanded MVP inputs for sector/industry proxies, custom peer baskets, return-based style descriptors, and macro factors.

Layer 3 is event intelligence. EDGAR metadata is converted into structured event features and event taxonomy rows. Event rows are evidence-only until event-study calibration exists.

Layer 4 is constrained explanation. The MVP uses a deterministic narrative template generated only from structured attribution outputs.

## Contracts

Public engine boundaries use Pydantic models from `engine/contracts.py`. The important models are:

- `PriceBar`
- `FactorContributionInput`
- `AttributionContribution`
- `AttributionResult`
- `TimeWindow`
- expanded attribute metadata and evidence contracts such as contribution stage, factor observations, security factor exposures, sector classifications, peer baskets, event taxonomy, and event surprise.

All time-sensitive records inherit timestamp fields through `TimestampedRecord`.

## Database

The initial schema implements the canonical project entities plus `security_ticker_history`:

- `company`
- `security`
- `security_ticker_history`
- `price_bar`
- `factor_return`
- `macro_series`
- `factor_definition`
- `factor_observation`
- `security_factor_exposure`
- `sector_classification_history`
- `peer_basket`
- `peer_basket_member`
- `event`
- `event_taxonomy`
- `event_surprise`
- `company_exposure`
- `analyst_feedback`
- `attribution_methodology`
- `backfill_run`
- `attribution_run`
- `attribution_contribution`
- `model_universe_member`
- `attribution_backfill_task`
- `security_attribution_summary`
- `attribution_on_demand_job`
- FaustCalc staging and audit tables

The migration enables TimescaleDB and converts `price_bar`, `factor_return`, and `macro_series` into hypertables.

## Ingestion

Implemented local ingestion paths:

- FMP historical daily prices into `price_bar`
- Kenneth French daily factors into `factor_return`
- SEC EDGAR recent submissions into `event`
- FRED public macro observations into `macro_series`
- curated MVP universe, sector/industry classifications, peer baskets, and exposure gates
- sector/industry proxy price bars can be converted into `factor_return` rows

FMP and French historical files are timestamped as available at ingestion time because they are not point-in-time vintage feeds.

## Attribution Runs

Attribution runs are idempotent by `(security_id, window_start, window_end, cadence, methodology)`. Re-running the same window, cadence, and methodology updates the existing run and replaces contribution rows instead of appending duplicates.

Batch attribution can generate daily, weekly, and monthly windows from actual trading dates in `price_bar`.

Expanded MVP attribution can be run with `--use-expanded-mvp`; the daily 50-name workflow is available through `jobs/run_mvp_daily_batch.py`.

Three-year universe population is available through `jobs/run_historical_universe_backfill.py`. It writes daily, weekly, and monthly expanded attribution runs and stores aggregate coverage in `backfill_run`.

The active methodology names are:

- `legacy`
- `residual_safety_v1`
- `hierarchical_market_first_v1`

On-demand dashboard requests enqueue `attribution_on_demand_job` rows. `jobs/run_on_demand_attribution_worker.py` claims queued jobs with advisory locks, fills missing windows, and refreshes summaries for the requested ticker.

## Dashboard And Feedback

The dashboard displays universe summaries, methodology selection, deterministic narrative text, chart ranges, grouped driver rows, evidence payloads, CSV export, run history, exposure decisions, and analyst feedback controls. Feedback persists through the FastAPI `POST /analyst-feedback` endpoint.

## Non-Negotiable Invariants

- Every model-visible record has `event_time`, `ingestion_time`, and `timestamp_available`.
- Attribution filters by `timestamp_available <= attribution_cutoff`.
- `unexplained_residual` is always explicit.
- Contributions reconcile to observed return within one basis point.

## Equity Module Boundary

`viza.core.strategy` remains domain-neutral. `viza.finance.securities` provides the finance/security substrate. `viza.aat.attribute_analysis` is optional and subordinate. `viza.finance.equity_investment` is the additive equity decision layer: entity/node/edge/attribute/event/insight registries, strategy profiles, output views, validation rules, PIT/source-rights controls, package redaction policy, a default-off SEC/FMP/FRED runtime preview wedge, and a default-off packaged Windows desktop MVP workflow. The v0.1 state is registry-loadable, fixture-tested, feature-flag runtime-wired, persisted/replayable, package-draft export capable, and not production-hardened.
