# Packaged Equity Preview Repo Map

## Applicability Decision

```json
{
  "applicable_to_packaged_prototype": true,
  "reason": "The packaged prototype has an Electron React/TypeScript UI, a local Python FastAPI sidecar, packaged engine/config paths, token-aware desktop bridge calls, a result-sidebar insertion point, and Windows packaged smoke harnesses. The existing checked packaged artifact is stale relative to the source tree and does not yet include the equity runtime wedge or equity docs resources, so the package must be rebuilt after the source/resource changes.",
  "required_packaged_changes": [
    "Add a feature-flagged FastAPI preview endpoint in the local sidecar.",
    "Add desktop bridge calls for the preview endpoint.",
    "Add a feature-flagged result-sidebar equity preview panel.",
    "Include equity module docs/registry/fixture resources under resources/engine/docs/equity_module/v0.1 in the packaged app.",
    "Extend packaged smoke coverage for flags-off and mocked flags-on preview behavior."
  ],
  "blockers": []
}
```

## Files Inspected

- `viza/service.py`
- `viza/equity/config.py`
- `viza/equity/connectors.py`
- `viza/equity/runtime.py`
- `viza/equity/registry.py`
- `viza/modules/registry.py`
- `docs/equity_module/v0.1/reports/sec_fmp_fred_runtime_wedge_report.md`
- `docs/equity_module/v0.1/proofs/sec_fmp_fred_wedge_proof.json`
- `docs/equity_module/v0.1/fixtures/first_wedge_sec_quality_value/sec_fmp_fred_runtime_wedge_fixture.json`
- `apps/viza-desktop/src/App.tsx`
- `apps/viza-desktop/src/vizaEngineClient.ts`
- `apps/viza-desktop/src/vizaGraph.ts`
- `apps/viza-desktop/src/styles.css`
- `apps/viza-desktop/src/vizaWorkflowEngine.ts`
- `apps/viza-desktop/electron/main.cjs`
- `apps/viza-desktop/electron/preload.cjs`
- `apps/viza-desktop/electron/engineLifecycle.cjs`
- `apps/viza-desktop/electron/desktopPaths.cjs`
- `apps/viza-desktop/electron-builder.yml`
- `apps/viza-desktop/package.json`
- `apps/viza-desktop/scripts/buildEngineSidecar.mjs`
- `apps/viza-desktop/scripts/smokePackage.mjs`
- `apps/viza-desktop/scripts/smokeMacPackage.mjs`
- `tests/unit/test_equity_runtime_wedge.py`

## Packaged Sidecar Paths Inspected

- `apps/viza-desktop/release/win-unpacked/VIZA.exe`
- `apps/viza-desktop/release/win-unpacked/resources/app.asar`
- `apps/viza-desktop/release/win-unpacked/resources/engine/viza-engine.exe`
- `apps/viza-desktop/release/win-unpacked/resources/engine/config`
- `apps/viza-desktop/release/win-unpacked/resources/engine/viza`

Initial inspection found the checked packaged artifact was pre-equity-wedge: `resources/engine/viza/equity` and `resources/engine/docs/equity_module/v0.1` were absent. The Windows package was rebuilt after adding the explicit equity docs resource mapping; the rebuilt `release/win-unpacked` artifact now includes `resources/engine/viza/equity` and `resources/engine/docs/equity_module/v0.1`.

## Feature Flag And Config Paths Inspected

- Development defaults are documented in `env.example`.
- Runtime flag loading is in `viza/equity/config.py`.
- Packaged sidecar environment is assembled in `apps/viza-desktop/electron/engineLifecycle.cjs`.
- Packaged smoke starts the engine with `VIZA_CONFIG_DIR`, `VIZA_ENGINE_ROOT`, `VIZA_ENGINE_HOST`, `VIZA_ENGINE_PORT`, `VIZA_ENGINE_TOKEN`, and `VIZA_PROJECT_STORE_PATH` in `apps/viza-desktop/scripts/smokePackage.mjs`.
- Packaged config resources are copied by `apps/viza-desktop/electron-builder.yml` from `config` to `resources/engine/config`.

## Backend Route And Runtime Files Inspected

- FastAPI app and endpoint definitions live in `viza/service.py`.
- Local token auth is enforced by `validate_local_engine_token` in `viza/service.py` using `x-viza-engine-token` when `VIZA_ENGINE_TOKEN` is set.
- Equity wedge runtime logic lives in `viza/equity/runtime.py`.
- Equity runtime config and feature flags live in `viza/equity/config.py`.
- Equity module/registry loading lives in `viza/equity/registry.py`, `viza/modules/equity_investment.py`, and `viza/modules/registry.py`.

## Desktop Bridge Files Inspected

- Engine URL/token bootstrap is exposed through `window.vizaDesktop.desktopStatus()` in `apps/viza-desktop/electron/preload.cjs`.
- Engine lifecycle and packaged path behavior are in `apps/viza-desktop/electron/engineLifecycle.cjs` and `apps/viza-desktop/electron/desktopPaths.cjs`.
- Browser-to-sidecar requests are centralized in `apps/viza-desktop/src/vizaEngineClient.ts`.

## UI Files Inspected

- Main desktop UI shell is `apps/viza-desktop/src/App.tsx`.
- Shared desktop data types live in `apps/viza-desktop/src/vizaGraph.ts`.
- Desktop styles live in `apps/viza-desktop/src/styles.css`.
- Existing result sidebar panels include diagnostics, `.viza` Exchange, runtime jobs, project versions, batch controls, and radar designer.

## Packaging Scripts Inspected

- `apps/viza-desktop/scripts/buildEngineSidecar.mjs`
- `apps/viza-desktop/electron-builder.yml`
- `apps/viza-desktop/package.json`

`buildEngineSidecar.mjs` builds a PyInstaller onefile sidecar. `electron-builder.yml` currently copies `../../viza` and `../../config` into the packaged engine resources. Equity docs/registry/fixture resources need an explicit `docs/equity_module/v0.1` extra resource entry.

## Smoke-Test Files Inspected

- `apps/viza-desktop/scripts/smokePackage.mjs`
- `apps/viza-desktop/scripts/smokeMacPackage.mjs`
- `apps/viza-desktop/test/engineLifecycle.test.mjs`
- `apps/viza-desktop/test/preload.test.mjs`
- `apps/viza-desktop/test/workflowEngine.test.mjs`

## Final Chosen Endpoint Path

- `GET /viza/equity/runtime-wedge/status`
- `POST /viza/equity/runtime-wedge/preview`

The status endpoint can be called by the desktop UI to decide whether the preview panel should appear. The preview endpoint is disabled when either `VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED` or `VIZA_EQUITY_SEC_WEDGE_ENABLED` is false.

## Final Chosen UI Insertion Point

The preview surface will be added to the existing result sidebar in `apps/viza-desktop/src/App.tsx`, near the diagnostics/developer panels. This is the smallest stable packaged-desktop surface and avoids presenting the wedge as a full equity workstation.

## Packaged Integration Notes

- Feature flags remain default-off.
- Mock fixture mode remains the default for desktop preview calls.
- Live connector mode remains blocked unless `VIZA_EQUITY_LIVE_INTEGRATION_TESTS=true`.
- SEC requires no API key.
- FMP and FRED keys must be read only by runtime config and must never be serialized to responses, reports, proofs, screenshots, package resources, or logs.
- The existing packaged artifact must be rebuilt before the new endpoint and UI can be verified in `release/win-unpacked`.
- Rebuild completed on 2026-05-14. `npm run smoke:package` passed against the rebuilt Windows artifact.
