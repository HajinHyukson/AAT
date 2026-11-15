# Equity Preview Persistence Repo Map

## Files Inspected

- `viza/service.py`
- `viza/equity/config.py`
- `viza/equity/preview.py`
- `viza/equity/runtime.py`
- `viza/equity/registry.py`
- `viza/project_store.py`
- `viza/observations.py`
- `viza/validation_ledger.py`
- `viza/file_format/export.py`
- `viza/marketplace.py`
- `apps/viza-desktop/src/App.tsx`
- `apps/viza-desktop/src/vizaEngineClient.ts`
- `apps/viza-desktop/src/vizaGraph.ts`
- `apps/viza-desktop/src/styles.css`
- `tests/unit/test_equity_runtime_wedge.py`
- `tests/unit/test_equity_runtime_wedge_api.py`
- `tests/unit/test_equity_packaged_preview.py`
- `tests/unit/test_viza_observations.py`
- `tests/unit/test_viza_project_store.py`
- `tests/unit/test_viza_validation_ledger.py`
- `apps/viza-desktop/test/equityPreviewPanel.test.mjs`

## Existing Storage Conventions

- Local store path is resolved by `viza.project_store.project_store_path()` using `VIZA_PROJECT_STORE_PATH`, otherwise `~/.viza/viza_projects.sqlite3`.
- The project store initializes a local SQLite database with WAL-compatible local-app usage patterns and tables such as `projects`, `methodology_versions`, `run_records`, `saved_radar_outputs`, `observations`, `validation_records`, and runtime job tables.
- `viza/observations.py` owns the point-in-time observation API and persists records into the existing `observations` table with `source_id`, `observed_at`, `available_at`, `retrieved_at`, `connector_id`, `data_version`, `model_version`, `rights_policy`, and checksum fields.
- `viza/validation_ledger.py` owns generic validation ledger records. Equity preview validation is preview-specific and can be linked through a narrow equity audit record while still preserving run IDs, checksums, PIT, and rights summaries.

## Backend Preview Endpoint

- Existing endpoint file: `viza/service.py`
- Existing preview adapter: `viza/equity/preview.py`
- Existing endpoint paths:
  - `GET /viza/equity/runtime-wedge/status`
  - `POST /viza/equity/runtime-wedge/preview`

## Runtime Wedge

- Runtime wedge file: `viza/equity/runtime.py`
- The preview adapter already calls `run_sec_quality_value_wedge()` and compacts the runtime payload for desktop/API display.
- SEC/FMP/FRED behavior remains controlled by `EquityRuntimeConfig` and uses mocks unless live connector mode is explicitly enabled.

## Project Store Files

- `viza/project_store.py`
- Existing generic `run_records` can store whole result payloads, but the equity preview needs queryable target/status/PIT/rights/package fields and replay ancestry.

## Observation Store Files

- `viza/observations.py`
- The implementation persists normalized SEC/FMP/FRED preview observations through the existing observation store, then links run IDs to observation IDs in an equity preview audit table. This avoids adding an equity-only database while preserving the existing observation contract.

## Validation, Proof, And Package/Redaction Files

- `viza/validation_ledger.py`
- `viza/equity/runtime.py`
- `viza/equity/preview.py`
- `viza/file_format/export.py`
- `viza/marketplace.py`

Equity preview validation, source-rights, PIT, and package-redaction summaries are already present in the preview payload. Persistence stores these preview reports as linked records with checksums in the same local SQLite database.

## UI Preview Files

- `apps/viza-desktop/src/App.tsx`
- `apps/viza-desktop/src/vizaEngineClient.ts`
- `apps/viza-desktop/src/vizaGraph.ts`
- `apps/viza-desktop/src/styles.css`

The selected UI insertion point is the existing `EquityRuntimePreviewPanel` in the result sidebar. The history/replay controls will remain inside that preview panel so no full equity workstation surface is introduced.

## Selected Persistence Approach

Use the existing local SQLite project store path. Add a small equity preview persistence module that creates the following tables in the same database:

- `equity_preview_runs`
- `equity_preview_evidence_bundles`
- `equity_preview_report_records`
- `equity_preview_run_observations`

Also save the compact preview payload to the existing `run_records` table and save normalized SEC/FMP/FRED observations through `viza/observations.py`.

No standalone database is created.

## Selected Replay Endpoint Paths

- `GET /viza/equity/runtime-wedge/runs`
- `GET /viza/equity/runtime-wedge/runs/{run_id}`
- `POST /viza/equity/runtime-wedge/runs/{run_id}/replay`

Replay from stored observations is the default and does not call live SEC/FMP/FRED APIs. Replay with refresh is explicit and requires `VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED=true`.

## Selected UI History Insertion Point

The history/replay surface will be added inside `EquityRuntimePreviewPanel` in `apps/viza-desktop/src/App.tsx`:

- persist run checkbox
- recent persisted runs list
- run detail panel
- replay from stored observations
- replay with refresh disabled unless the status endpoint reports it allowed

## Existing Tests Used As Patterns

- `tests/unit/test_viza_observations.py` for observation store and API persistence patterns.
- `tests/unit/test_viza_project_store.py` for local SQLite store conventions.
- `tests/unit/test_viza_validation_ledger.py` for checksum/proof-style record behavior.
- `tests/unit/test_equity_runtime_wedge_api.py` for feature-flagged equity endpoint tests.
- `apps/viza-desktop/test/equityPreviewPanel.test.mjs` for existing desktop preview panel source checks.
