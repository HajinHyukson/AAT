# MVP Closure Repo Map

## Files Inspected

- Backend preview/API: `viza/service.py`, `viza/equity/preview.py`, `viza/equity/runtime.py`, `viza/equity/config.py`
- Persistence/store: `viza/equity/persistence.py`, `viza/project_store.py`, `viza/observations.py`, `viza/validation_ledger.py`
- Package/export/redaction: `viza/file_format/container.py`, `viza/file_format/models.py`, `viza/file_format/packaging.py`, `viza/file_format/export.py`, `viza/marketplace.py`
- UI/result sidebar/Exchange: `apps/viza-desktop/src/App.tsx`, `apps/viza-desktop/src/vizaEngineClient.ts`, `apps/viza-desktop/src/vizaGraph.ts`, `apps/viza-desktop/src/features/vizaFiles/*`
- Windows packaging/smoke: `apps/viza-desktop/electron-builder.yml`, `apps/viza-desktop/scripts/smokePackage.mjs`, `apps/viza-desktop/scripts/buildEngineSidecar.mjs`, `apps/viza-desktop/package.json`
- Tests used as patterns: `tests/unit/test_equity_runtime_wedge.py`, `tests/unit/test_equity_runtime_wedge_api.py`, `tests/unit/test_equity_preview_persistence.py`, `tests/unit/test_equity_packaged_preview.py`, `tests/unit/test_viza_file_import_export.py`, `apps/viza-desktop/test/equityPreviewPanel.test.mjs`

## Selected MVP Flow

The MVP is frozen around one complete path:

`quality_value_long_only` + SEC-first public evidence + optional FMP/FRED context + mocked connectors by default.

Excluded from this sprint: additional equity profiles, portfolio optimization, factor backtesting, live trading, order routing, paid marketplace, ALFRED production vintage pipeline, and investment-advice behavior.

## Existing Storage Convention

The existing local project store uses SQLite via `viza.project_store.project_store_path()` and the `VIZA_PROJECT_STORE_PATH` override. The equity persistence layer already writes preview audit tables into that same database and stores normalized observations through `viza/observations.py`. No standalone database is needed.

Selected persistence approach:

- `run_records` plus `equity_preview_runs`
- `observations` plus `equity_preview_run_observations`
- `equity_preview_evidence_bundles`
- `equity_preview_report_records` for validation/source-rights/package-redaction records

## Existing Package Convention

The universal `.viza` writer is `viza/file_format/container.py`. It writes a ZIP-backed VIZA container with a `viza.document.v1` manifest and canonical sections from `viza/file_format/models.py`.

The existing generic graph export path in `viza/file_format/export.py` requires a methodology graph. Persisted equity preview runs are not ordinary graph runs, so the selected package/export path is a narrow equity adapter that still uses the same VIZA container writer and canonical section model:

`persisted equity preview run -> sanitized equity package sections -> write_viza_container() -> optional viza_file_exports record`

## Selected Package/Export Path

Add a package-ready endpoint under the existing equity run surface:

- `POST /viza/equity/runtime-wedge/runs/{run_id}/package-draft`

The endpoint exports or prepares a `.viza` draft from an immutable persisted preview run. It supports `white_box`, `output_only`, and `marketplace_draft` modes. It redacts FMP dev-only observations and preserves PIT, rights, validation, package-redaction, proof checksum, and the non-advice boundary.

## Selected UI Insertion Point

Extend the existing `EquityRuntimePreviewPanel` in the result sidebar. The UI already supports run/save/history/detail/replay; the MVP closure adds a small package draft/export action to the selected run detail surface.

## Windows Packaged Prototype

The Windows package smoke harness is `apps/viza-desktop/scripts/smokePackage.mjs`. It already starts the packaged sidecar, checks `/health`, verifies equity preview flags-off and flags-on behavior, and scans sentinel FMP/FRED secrets from sidecar stderr and preview payload. The MVP closure extends the flags-on smoke path to persist a run, replay it, and export an equity package draft from the persisted run.

## Selected Test Commands

- `python -m pytest tests\unit\test_equity_runtime_wedge.py -q`
- `python -m pytest tests\unit\test_equity_module_loader.py tests\unit\test_equity_module_fixtures.py -q`
- `python -m pytest tests\unit\test_equity_runtime_wedge_api.py -q`
- `python -m pytest tests\unit\test_equity_preview_persistence.py -q`
- `python -m pytest tests\unit\test_equity_mvp_package_export.py -q`
- `python -m pytest tests\unit tests\lookahead_audit`
- `npm run typecheck` in `apps/viza-desktop`
- `npm run test:desktop` in `apps/viza-desktop`
- `node --test tests\dashboard\attribution-period-bars.test.mjs`
- `npx tsc --noEmit --project tsconfig.json` in `dashboard`
- `npm run package:win` in `apps/viza-desktop`
- `npm run smoke:package` in `apps/viza-desktop`
