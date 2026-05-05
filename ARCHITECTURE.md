# Architecture

Last updated: 2026-05-04

## Current State

The repo now has an executable expanded MVP backend/engine scaffold:

- `engine/` contains typed contracts, deterministic return accounting, French factor attribution, expanded sector/peer/style/macro attribution helpers, event taxonomy, confidence scoring, exposure gates, replay audit helpers, and a deterministic narrative generator.
- `adapters/` contains the adapter protocol and fail-closed licensing configuration checks.
- `api/` contains FastAPI endpoints for health/version, universe state, attribution runs, contribution evidence, exposure decisions, and analyst feedback.
- `db/` and `alembic/` contain the canonical schema, expanded attribute metadata tables, cadence-aware attribution runs, `backfill_run` audit records, and migrations.
- `dashboard/` contains the analyst-facing driver table, evidence drawer, CSV export, run history, exposure decisions, narrative display, and feedback controls.
- `tests/` contains focused unit and look-ahead tests for reconciliation, point-in-time filtering, adapter licensing, expanded attribute primitives, API feedback, and proving-run diagnostics.

Latest local verification:

```powershell
python -m pytest tests/unit tests/lookahead_audit
```

Result: 50 tests passed on 2026-05-04.

## Model Boundary

The current model is complete enough for MVP proving runs and dashboard inspection. It is not yet complete as a production research model.

Production contribution rows currently come from deterministic returns and calibrated factor-style inputs. EDGAR event rows and return-based style descriptors are evidence-only unless a calibrated production factor return exists. Event contribution remains blocked until event-study calibration is implemented and validated. Licensed or alternative data sources remain blocked from production unless their source policy is explicitly confirmed.

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
- `backfill_run`
- `attribution_run`
- `attribution_contribution`

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

Attribution runs are idempotent by `(security_id, window_start, window_end, model_version, factor_basket_version, cadence)`. Re-running the same window and cadence updates the existing run and replaces contribution rows instead of appending duplicates.

Batch attribution can generate daily, weekly, and monthly windows from actual trading dates in `price_bar`.

Expanded MVP attribution can be run with `--use-expanded-mvp`; the daily 50-name workflow is available through `jobs/run_mvp_daily_batch.py`.

Three-year universe population is available through `jobs/run_historical_universe_backfill.py`. It writes daily, weekly, and monthly expanded attribution runs and stores aggregate coverage in `backfill_run`.

## Dashboard And Feedback

The dashboard displays deterministic narrative text, grouped driver rows, evidence payloads, CSV export, run history, exposure decisions, and analyst feedback controls. Feedback persists through the FastAPI `POST /analyst-feedback` endpoint.

## Non-Negotiable Invariants

- Every model-visible record has `event_time`, `ingestion_time`, and `timestamp_available`.
- Attribution filters by `timestamp_available <= attribution_cutoff`.
- `unexplained_residual` is always explicit.
- Contributions reconcile to observed return within one basis point.
