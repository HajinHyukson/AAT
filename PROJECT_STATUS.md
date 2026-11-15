# Project Status

Last updated: 2026-05-20

## Current Snapshot

AAT is an executable alpha/MVP scaffold with real ingestion, attribution, persistence, API, dashboard, and backfill plumbing. It is not yet a production-complete attribution model.

The current source of truth is split deliberately:

- `README.md`: operator-facing overview and commands.
- `ARCHITECTURE.md`: implementation map and system boundaries.
- `docs/attribution_methodology.md`: current contribution methodology and model limits.
- `docs/FAUSTCALC_DATA_IMPLEMENTATION_REPORT.md`: FaustCalc data contents and live backfill state.
- `docs/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md`: development restrictions while the server backfill is active.

Current implemented surface:

- Deterministic adjusted close-to-close return accounting.
- French five-factor baseline attribution.
- Expanded MVP attribution for sector/industry proxy factors, peer baskets, macro factors, return-style evidence, and EDGAR event evidence.
- Methodology registry for `legacy`, `residual_safety_v1`, and `hierarchical_market_first_v1`.
- Explicit `unexplained_residual` on every attribution result.
- Residual-share safety diagnostics that suppress unstable share percentages for small observed moves.
- Point-in-time filtering through `timestamp_available <= attribution_cutoff`.
- FastAPI endpoints for universe summaries, attribution runs, chart series, methodology selection, on-demand attribution jobs, exposure decisions, and analyst feedback.
- Next.js dashboard with universe search/filtering, methodology selection, attribution detail loading, chart range updates, run history, driver table, evidence payloads, CSV export, exposure review, and feedback controls.
- Replay-style look-ahead audit helper and tests.
- MVP proving, historical universe, S&P 500 pilot, FaustCalc full-history, and on-demand attribution orchestration.
- `viza.finance.equity_investment v0.1` registry artifacts are generated and loadable under `docs/equity_module/v0.1/`, with an additive `viza/equity` loader/validator, SEC quality-value first wedge, three profile pilots, and package/redaction fixtures.
- `viza.finance.equity_investment v0.1` now has a feature-flagged SEC public first-wedge runtime path with optional FMP market snapshot support, optional FRED macro context, `quality_value_long_only` compatibility checks, non-advice output previews, validation reporting, source-rights reporting, and package-redaction preview behavior.
- The VIZA Windows packaged desktop prototype now has a feature-flagged equity preview surface in the Electron result sidebar. It calls the local packaged FastAPI sidecar endpoint, uses mocked SEC-first preview fixtures by default, and displays target identity, SEC evidence, PIT state, rights state, validation state, source-rights state, package-redaction preview, and the non-advice boundary.
- Equity preview runs can now be persisted, inspected, and replayed when `VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED=true`. Persisted runs use the existing local project SQLite store plus normalized observation records, preserve PIT/rights/validation/package-redaction state, and support replay from stored observations without live connector calls. Refresh replay is explicit and gated by `VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED=true`.
- VIZA MVP Candidate 0.1 is wired around the single SEC-first `quality_value_long_only` equity workflow: packaged desktop preview, save run, history/detail inspection, stored-observation replay, package-redaction preview, and `.viza` draft package preparation through the existing VIZA container/export infrastructure.
- The VIZA quant sandbox (spec phases 1-2: data foundation and execution) is implemented in `viza_sandbox/`: read-only canonical price source, point-in-time panels, isolated runner, quantile backtest with a disclosed D+1 execution convention, per-user-token HTTP API, and an operator CLI. Docker isolation is not yet verified against a daemon and FaustCalc split adjustment is unverified until `check-split-adjustment` is run on the server. See `docs/superpowers/specs/2026-11-15-viza-quant-sandbox-design.md`, `docs/superpowers/plans/2026-11-15-viza-quant-sandbox-phase-1-2.md` and `docs/viza_end_product/VIZA_SANDBOX_OPERATIONS.md`.

Latest local verification:

```powershell
python -m pytest tests\unit tests\lookahead_audit
node --test tests\dashboard\attribution-period-bars.test.mjs
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
cd ..\..\dashboard
npx tsc --noEmit --project tsconfig.json
```

Result on 2026-05-15:

- Python: `350 passed`.
- Dashboard Node test: `2 passed`.
- VIZA desktop TypeScript typecheck: passed.
- VIZA desktop helper tests: `23 passed`.
- Dashboard TypeScript check: passed.
- Windows packaged build/smoke: passed after rebuilding the updated sidecar and desktop package.
- Node emitted a module-type warning for `dashboard/components/attribution-period-bars.ts`; the test still passed.

Current production boundary:

- FMP price data is development-only unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- FaustCalc/FMP-derived snapshot data remains development/proving data unless source rights are confirmed.
- FRED and Kenneth French rows are not true point-in-time vintages in the current ingestion path; they are timestamped at ingestion time.
- EDGAR event rows and return-based style descriptors are evidence-only unless a calibrated production contribution method exists.
- Confidence labels are qualitative data/model-quality labels, not calibrated probabilities.
- The model still needs residual reduction analysis, out-of-sample validation, confidence calibration, source/license confirmation, and production runbooks.
- The equity module v0.1 artifacts are registry-seedable/loadable and fixture-tested only. Production hardening still requires legal/source-rights review, connector entitlement review, runtime handler integration, production validation, and a separate production review.
- The equity runtime wedge, packaged desktop MVP workflow, preview persistence/replay history, and package-draft export are feature-flagged and mock-tested, not production-hardened. FMP output remains dev-only/export-blocked unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`; FRED output remains latest-only/not backtest-safe unless ALFRED-style vintage cutoff enforcement is implemented and tested.

## Milestone

Current target: finish and validate the MVP v0 scaffold while keeping the live FaustCalc backfill safe.

## Completed This Cycle

- Converted the bootstrap docs into an executable Python scaffold.
- Added typed contracts for price bars, factor inputs, contributions, attribution results, factor observations, exposures, event taxonomy, event surprise, and contribution stages.
- Added deterministic return accounting and baseline residual reconciliation.
- Added adapter licensing checks and FMP production fail-closed policy.
- Added canonical SQLAlchemy models and Alembic migrations for identity, prices, factors, macro, events, exposures, attribution, feedback, backfills, universes, summaries, on-demand jobs, and FaustCalc staging.
- Added FMP, Kenneth French, FRED, SEC EDGAR, FaustCalc feature-store, and FaustCalc SEC filing ingestion paths.
- Added curated 50-name MVP universe and static S&P 500 pilot universe workflows.
- Added French five-factor, sector/industry proxy, peer basket, macro, style evidence, event evidence, residual-safety, and hierarchical market-first attribution paths.
- Added deterministic narrative generation and conservative exposure-update review decisions.
- Added idempotent daily, weekly, and monthly attribution run persistence.
- Added FastAPI endpoints for attribution, universe, charting, methodologies, feedback, exposure decisions, and on-demand jobs.
- Added Next.js dashboard support for universe access, methodology selection, attribution detail loading, charts, driver evidence, CSV export, run history, exposure review, and analyst feedback.
- Added replay/look-ahead tests and dashboard chart-period tests.
- Added FaustCalc staging, universe construction, generated mappings, resumable backfill tasks, checkpointing, status reporting, advisory locks, and optional distributed workers.
- Added on-demand attribution worker support for web-triggered missing-window attribution.
- Added KOSPI pilot Phase 1 (see `docs/ACQUIN_KOSPI_ADAPTER_DESIGN.md`): `acquin_*` staging tables and migration `20260609_0012`, read-only Acquin Railway snapshot import, placeholder-entity universe seeding, price promotion into `price_bar` (KRW) behind a continuity guard and the Acquin vintage policy, `kospi_market` proxy factor returns, evidence-only investor-flow inputs, a configurable market factor name in attribution runs, and `jobs.run_pilot_kospi_attribution` on the local `aat_pilot_kospi` database.

## Current Operational State

Local TimescaleDB normally runs on host port `55432`:

```powershell
docker compose up -d postgres
.\scripts\run_alembic.ps1 upgrade head
```

The server FaustCalc backfill remains active and should be treated as a live production-like data job until it completes and a post-backfill backup is created.

Latest read-only status check from this development machine on 2026-05-12:

```text
backfill_run_id=a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c
tasks_completed=5912/37971
tasks_finished=6067/37971
pending=31903
running=1
skipped_tasks=153
failed=2
windows_ran=99294/7156478
windows_skipped=0
current_ticker=SRRE
current_cadence=monthly
current_windows=0/27
```

The two failed tasks are monthly windows for `FSBN` and `TXGE`; both failed because extreme source-price/model outputs overflowed the current numeric precision. Treat these as data/model-quality defects to triage after preserving backfill progress.

Current approved status check:

```powershell
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution"
python -m jobs.run_faustcalc_attribution_backfill --status-only
```

Current approved server-local resume command:

```bash
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --workers 1 --progress-every 10 --worker-id server-1
```

KOSPI pilot (local-only, requires `ACQUIN_DB_URL` in `.env`):

```powershell
python -m jobs.init_pilot_kospi_db
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@localhost:55432/aat_pilot_kospi"
python -m jobs.import_acquin_snapshot
python -m jobs.promote_acquin_data
python -m jobs.run_pilot_kospi_attribution --from 2026-01-02 --cadences daily weekly
```

The KOSPI pilot refreshes itself daily: the Windows scheduled task `AAT Pilot KOSPI Daily`
runs `jobs.run_pilot_kospi_daily` at 17:30 KST (import -> promote -> attribution for new
windows -> summary refresh). The dashboard is Vercel-deployable against the pilot DB with
`AAT_DEFAULT_UNIVERSE_NAME=pilot_kospi_static`, `AAT_DEFAULT_UNIVERSE_VERSION=latest`, and
`NEXT_PUBLIC_PRICE_CURRENCY=KRW`; see `docs/VERCEL_CLOUDFLARE_TUNNEL_DEPLOYMENT.md`.

## Next Work

1. Continue the FaustCalc backfill without schema, loader, or persisted-attribution contract changes.
2. Triage the two failed monthly tasks after recording the current status and deciding whether to skip, cap, or repair the bad-source windows.
3. Refresh `security_attribution_summary` after backfill completion.
4. Validate `/universe`, chart, run-history, and detail-panel response times after summaries are refreshed.
5. Spot-check representative tickers such as `AAPL`, `MSFT`, a thin-name winner, and a failed/edge-case ticker.
6. Create a post-backfill server DB dump.
7. Run residual-reduction and out-of-sample methodology evaluation before promoting any expanded factor or event methodology as production-grade.
8. For `viza.finance.equity_investment v0.1`, next prepare an MVP user test, demo script, and installer handoff while preserving the current non-production-hardened boundary.
9. Phases A, B, C.1, C.2, and **D** of `docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md` are landed and green — the decisions feature is **feature-complete**. Phase D landed 2026-05-20: backtesting evaluator (`viza/decisions_backtesting.py` + new HTTP endpoint + 7 tests), DecisionsPanel wired into App.tsx, SQLite migration helper closes the last open C.2 WARN, and `docs/VIZA_DECISIONS_STRUCTURAL_AUDIT.md` documents the 7-point structural audit with file:line references for every enforcement site. Release-readiness checklist updated with the Decisions section. Verification on 2026-05-20: 498 Python tests pass; 42 desktop tests pass; typecheck clean; 0 regressions. Public-release sign-off awaits marketing/help surfaces being authored (out of this repo). All historic phase detail follows.

9b. Phases A, B, C.1, and C.2 of `docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md` were the precursors landed earlier the same day — the decisions feature is now feature-complete through Phase C. Phase C.2 (live-mode opt-in flow + live-mode code path) landed 2026-05-20 under the CEO directive to treat legal constraints as resolved. Defense-in-depth controls remain in place: (a) global engine env flag `VIZA_LIVE_MODE_ENABLED=true` required to activate live mode in any process; (b) per-profile versioned opt-in (`LiveModeOptIn`) with disclosure version `v1`; (c) strict per-rule `effective_from <= cutoff_timestamp` gate; (d) SQLite CHECK still rejects modes outside `(sandbox_replay, live)`. Verification: 488 Python tests pass (Phase C.1 baseline 482 + 6 new for live mode enforcement); 40 desktop tests pass (Phase B baseline 31 + 9 new for live-mode UI surface). Next-up items: App.tsx wiring of `DecisionsPanel` is still a small follow-up (component is built and tested standalone but not yet visible in the running app shell); Phase D (backtesting evaluator, marketing copy review, final structural-point audit, release-readiness sign-off) is now the remaining workstream on the plan. **Phase C is split**: C.1 (cooldown/dead-band, decision package-redaction, second module) shipped today with 482 unit+lookahead tests passing (Phase B baseline 468 + 14 new). **Phase C.2 (live-mode opt-in dialog + live-mode code path) is held for the legal memo** briefed in `docs/VIZA_DECISIONS_LEGAL_BRIEF.md` — the live-mode block is encoded at the type/runtime/DB layer and stays in place until the memo confirms the simulator frame survives a live run. Estimated coding time post-memo: ~5–10 minutes. Phase C.1 detail: `CooldownPolicy` sub-model on `DecisionRule` (additive); `PriorEmission` carrier + `_cooldown_suppresses` enforcement in `compile_decisions`; new `viza/decisions_redaction.py` with `white_box`/`output_only`/`marketplace_draft` modes + cross-mode block on `export_allowed=False`; new real-estate template proving module-agnostic abstraction. Remaining follow-ups: App.tsx wiring of `DecisionsPanel`, legal memo from counsel, Phase C.2 live-mode unlock once memo confirms. **Phase A**: `viza/decisions.py` (DecisionFrame, executor, store, replay), additive `DecisionRule` schema on `VizaStrategyProfile`, `output_radar_mode` helper, pilot rule on the RSI swing template, and `tests/lookahead_audit/test_decisions_pit.py` gate. **Phase B**: validation-ledger integration (`validation_record_for_decisions`, `emit_and_persist_decisions`), FastAPI endpoints (`GET /viza/runs/{run_id}/decisions`, `POST /viza/runs/{run_id}/decisions/replay`), end-to-end replay-from-stores integration test, and the decisions UI feature surface at `apps/viza-desktop/src/features/decisions/` (types, client, card, panel) with 8 desktop tests asserting non-advice language and sandbox framing. Plus `docs/VIZA_DECISIONS_LEGAL_BRIEF.md` for the lighter US + Korea legal pass (counsel engagement is scheduling-bound, ~2 weeks calendar). Verification: 468 unit + lookahead tests pass (Phase A 464 + Phase B 4); desktop typecheck clean; 31 desktop tests pass (23 baseline + 8 new). Remaining: App.tsx wiring of `DecisionsPanel` into the desktop layout (small follow-up; component is tested standalone), legal memo from counsel, and `viza-code-reviewer` sign-off on the full Phase B diff. Phase C picks up next: live-mode opt-in dialog, cooldown/debounce/dead-band, decision-aware package-redaction modes, and a second module's decision rule.

Manual input likely needed soon:

- Confirm the production price-data source and license status. FMP remains development-only unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- Decide how to handle extreme price/source anomalies that generate impossible returns or coefficient explosions.
- Fill real values in `.env` for `FMP_API_KEY` and `EDGAR_USER_AGENT` when running local ingestion workflows. FRED CSV ingestion does not require a key.
- Review open `acquin_validation_issue` continuity suspects (e.g. `204210`, `140910`) before trusting their KOSPI pilot attribution output.
