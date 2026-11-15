# Equity MVP Closure Report

## Summary

This sprint closes the VIZA MVP candidate around one complete workflow:

`quality_value_long_only` + SEC-first public evidence + optional FMP/FRED context + preview + persistence + replay + package-redaction preview + `.viza` draft export.

The implementation intentionally does not add new equity profiles, factor backtesting, portfolio optimization, live trading, order routing, paid marketplace behavior, personal investment advice, or ALFRED production vintage infrastructure.

## MVP Scope

Selected MVP flow:

- Run the feature-flagged SEC-first equity runtime wedge through the packaged desktop preview.
- Save a preview run into the existing local project SQLite store.
- Link the saved run to normalized observations, evidence, validation, source-rights, PIT, package-redaction, and proof data.
- Replay from stored observations without live SEC/FMP/FRED calls.
- Prepare a local `.viza` draft package from the persisted run in `white_box`, `output_only`, or `marketplace_draft` mode.

## Storage Approach

Persistence continues to use the existing VIZA project store and observation store. No standalone equity database was created.

Stores used:

- `run_records` plus `equity_preview_runs`
- `observations` plus `equity_preview_run_observations`
- `equity_preview_evidence_bundles`
- `equity_preview_report_records` for validation, source-rights, and package-redaction records
- `viza_file_exports` when a package draft is associated with a project

## API

Existing preview and replay endpoints remain:

- `POST /viza/equity/runtime-wedge/preview`
- `GET /viza/equity/runtime-wedge/runs`
- `GET /viza/equity/runtime-wedge/runs/{run_id}`
- `POST /viza/equity/runtime-wedge/runs/{run_id}/replay`

MVP package endpoint added:

- `POST /viza/equity/runtime-wedge/runs/{run_id}/package-draft`

The package endpoint is feature-flagged behind the equity runtime, SEC wedge, and preview-persistence flags. It exports from an immutable persisted preview run and does not refresh live connector data.

## Package Draft Behavior

The package adapter uses the existing `.viza` container writer and canonical VIZA sections.

Mode behavior:

- `white_box`: includes the workflow graph, SEC source refs, public derived fundamentals, validation proof, rights report, PIT summary, and audit hashes.
- `output_only`: includes output summary, proof summary, PIT/rights/validation state, and redacts the workflow graph.
- `marketplace_draft`: remains non-monetized and not publish-ready; it redacts FMP dev-only data and restricted/unclear rights while preserving source-rights summaries and the non-advice boundary.

The adapter writes local `.viza` draft artifacts and can record the export through the existing `viza_file_exports` store when a `project_id` is supplied.

## Desktop UI

The existing `EquityRuntimePreviewPanel` remains the MVP surface. It now supports:

- Save run toggle
- Recent equity preview runs
- Run detail
- Replay from stored observations
- Replay with refresh control, disabled unless enabled by sidecar status
- Package preview / export draft action
- Proof checksum display

The UI continues to call the local sidecar bridge only. It renders PIT, rights, validation, redaction, source-rights, and non-advice state. It avoids personalized advice language.

## Packaged Windows Prototype

The Windows package was rebuilt with the updated sidecar and desktop UI. The packaged smoke harness verifies:

- Package contents are present.
- Packaged sidecar starts.
- `/health` succeeds.
- Equity preview is disabled with flags off.
- Mocked equity preview runs with flags on.
- Persisted run history, detail, stored-observation replay, and package-draft export work in packaged mode.
- Sentinel FMP/FRED secret values are absent from API payloads, sidecar stderr, and package artifacts.

## PIT Behavior

SEC-derived observations persist with `source_id`, `observed_at`, `available_at`, `retrieved_at`, `PIT_safe`, and `lookahead_risk`. FRED macro observations remain latest-only / not true PIT-safe for historical backtests unless ALFRED-style vintage cutoff enforcement is implemented and tested. Replay from stored observations does not make live API calls.

## Rights And Redaction

SEC public evidence persists as public-official metadata and derived observations, avoiding unnecessary bulk raw filing reproduction. FMP observations remain `dev_only_unconfirmed`, export-blocked, and marketplace-redacted unless production rights are explicitly confirmed. Marketplace draft packages redact restricted, unclear, private, or unconfirmed-license data.

## Verification

The full local regression suite passed after the MVP package-draft changes:

- Python unit/lookahead suite: `350 passed`.
- Desktop typecheck: passed.
- Desktop helper tests: `23 passed`.
- Dashboard TypeScript check: passed.
- Dashboard Node chart test: `2 passed` with the existing module-type warning.
- Windows package build: passed.
- Windows package smoke: passed.

MVP proof checksum:

- `696F5346788E772E999D4D887F00FAECD3BEFE73C384D789E5AD67A4313FFCFB`

Secret scan:

- Actual `.env` secret values checked: 2 across 539 files, 0 matches.
- Fake sentinel values checked across generated/package outputs: 4 across 312 files, 0 matches.
- `.env` remains gitignored.

## Limitations

- Not production-hardened.
- Mocked preview remains the default test path.
- Live SEC/FMP/FRED tests remain opt-in only.
- FMP production rights require legal/source-rights review.
- FRED true PIT backtesting requires ALFRED-style vintage cutoff enforcement.
- Full ticker alias resolution through a security master remains future work unless already available.
- `quality_value_long_only` remains the only fully wired equity profile.
- No personalized investment advice.
- No order routing.
- No monetized marketplace.
