# Implementation Log

## 2026-05-12 - VIZA Phase 0: Product And Repository Foundation

Status: implemented and verified.

Progression:

- Confirmed VIZA remains isolated from the active AAT attribution/backfill paths:
  - desktop workspace: `apps/viza-desktop/`
  - Python graph/runtime package: `viza/`
  - starter config: `config/viza_attribute_registry.json`
  - VIZA docs: `docs/VIZA_*.md`
- Confirmed `viza_graph_v0` is the durable prototype graph contract in Python and TypeScript.
- Confirmed the Phase 0 node vocabulary is mirrored across the stack:
  - `universe`
  - `attribute`
  - `transform`
  - `filter`
  - `score`
  - `relationship`
  - `output_radar`
- Confirmed the Phase 0 edge vocabulary is mirrored across the stack:
  - `data_flow`
  - `relationship`
  - `evidence`
- Confirmed the sample methodology fixture exists at `tests/fixtures/viza/residual_momentum_event_radar.json` and validates against the Python schema.
- Confirmed the starter attribute registry loads with at least 20 attributes and covers all attribute keys used by the sample methodology graph.
- Hardened Phase 0 graph-schema test coverage for:
  - unsupported schema versions,
  - duplicate edge IDs,
  - self-referential edges,
  - `updated_at` values earlier than `created_at`.

Verification:

```powershell
python -m pytest tests\unit\test_viza_graph_schema.py tests\unit\test_viza_attribute_registry.py
```

Result: passed on 2026-05-12 with 11 tests.

Broader no-regression check:

```powershell
python -m pytest tests\unit tests\lookahead_audit
```

Result: passed on 2026-05-12 with 133 tests.

## 2026-05-12 - VIZA Phase 1: Methodology Canvas Foundation

Status: implemented and verified for the prototype canvas.

Progression:

Phase 1 now has the full prototype node palette and the first pass of UX hardening from the detailed plan. The canvas continues to open as the primary workspace with the left tool rail, center graph/results area, and right inspector. The implementation added dirty-state tracking to distinguish saved versus unsaved graph edits, readiness badges on canvas nodes, duplicate-node support, delete/duplicate keyboard shortcuts, and client-side edge compatibility checks so invalid relationship/universe/output connections are rejected before they enter saved graph JSON. Graph mutations now clear stale run results, and save/load/new graph flows reset the dirty state appropriately.

Verification:

```powershell
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with TypeScript typecheck clean and 4 desktop tests.

## 2026-05-12 - VIZA Phase 2: Local Engine Bridge

Status: implemented and verified for the local prototype bridge.

Progression:

Phase 2 now has the first hardening layer around the local FastAPI engine. The Electron main process allocates an available loopback port instead of assuming `8765`, generates a per-session local token, passes the selected engine URL and token through the preload-safe desktop status bridge, waits for engine health, records the engine log path, and avoids duplicate child process startup. The renderer engine client resolves the Electron-provided base URL/token when available and falls back to `http://127.0.0.1:8765` for browser development. The Python service now enforces `x-viza-engine-token` when `VIZA_ENGINE_TOKEN` is set, while preserving token-free manual dev mode when the env var is absent. Desktop tests now cover token generation, port parsing, base URL derivation, and occupied-port fallback.

Verification:

```powershell
python -m pytest tests\unit\test_viza_service.py
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 9 service tests, TypeScript typecheck clean, and 8 desktop tests.

## 2026-05-12 - VIZA Phase 3: Executable Methodology Runtime

Status: implemented and verified for the prototype runtime.

Progression:

Phase 3 now has a graph compiler and run-manifest foundation instead of relying only on loose node scans. The new runtime compiler hashes methodology graphs, identifies executable paths into Output Radar nodes, topologically orders executable data-flow nodes, includes relationship consumers after output nodes, rejects data-flow cycles, flags unreachable outputs, detects ambiguous upstream universes, and warns on disconnected nodes. The execution path now uses that compiled topology, so disconnected Attribute nodes no longer silently affect scores even if their keys appear in Score weights. Run results now include `graph_hash`, `timestamp_cutoff`, `node_results`, and a manifest with runtime version, graph schema, registry version, universe metadata, ordered node IDs, and warning codes.

Verification:

```powershell
python -m pytest tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_graph_schema.py
cd apps\viza-desktop
npm run typecheck
```

Result: passed on 2026-05-12 with 21 Python tests and TypeScript typecheck clean.

## 2026-05-12 - VIZA Phase 4: First Data-Backed Radar

Status: implemented and verified for local data plus explicit prototype fallbacks.

Progression:

Phase 4 now has an attribute resolver layer that returns value, unit, source, source record, data version, model version, contribution stage, confidence, diagnostics, missing reason, and prototype status for each resolved attribute. Execution uses this resolver layer before scoring, so local universe fields such as sector, industry, and run status are identified as local source-backed values while unresolved research attributes remain deterministic prototype fallbacks. Evidence payloads now label each cell with `source`, `data_version`, `model_version`, `confidence`, `missing_reason`, and `is_prototype`, making fake/prototype values explicit instead of hidden. The demo graph still runs without a database, preserving the local-first prototype path while preparing the resolver contract for future DB-backed attribution, price, style, and event data.

Verification:

```powershell
python -m pytest tests\unit\test_viza_attribute_resolvers.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py
cd apps\viza-desktop
npm run typecheck
```

Result: passed on 2026-05-12 with 15 Python tests and TypeScript typecheck clean.

## 2026-05-12 - VIZA Phase 5: Relationship And Evidence Experience

Status: implemented and verified for the prototype relationship layer.

Progression:

Phase 5 now enriches relationship edges with family, direction, confidence, source lineage, timestamp placeholder, and diagnostics instead of returning only source/target/type/weight. Radar execution still emits company-to-attribute, classification, peer, and event-evidence edges, but those edges now carry enough metadata for inspection and filtering. A separate `POST /viza/relationships/query` endpoint was added so relationships can be requested and filtered by entity, family, edge strength, and max edge count without changing the methodology schema. The desktop relationship panel now supports family filtering, minimum edge strength, and local search over the selected company’s displayed graph, while the evidence inspector surfaces relationship family and confidence.

Verification:

```powershell
python -m pytest tests\unit\test_viza_service.py tests\unit\test_viza_runtime.py tests\unit\test_viza_attribute_resolvers.py
cd apps\viza-desktop
npm run typecheck
```

Result: passed on 2026-05-12 with 16 Python tests and TypeScript typecheck clean.

## 2026-05-12 - VIZA Phase 6: Packaging And Desktop Runtime Hardening

Status: implemented and verified for the Windows development package hardening pass.

Progression:

Phase 6 now builds on the Phase 2 lifecycle work with dynamic loopback port allocation, token-authenticated engine requests, health waiting, engine log path reporting, and desktop diagnostics exposed through the preload status bridge. The Electron runtime now resolves a bundled engine sidecar first when `viza-engine.exe` or `bin/viza-engine.exe` exists under `resources/engine`, then falls back to system Python for development builds. Packaging metadata was hardened with product executable naming, copyright, description, author metadata, and `asInvoker` execution level. A package-content smoke script was added to verify the unpacked Windows artifact includes `VIZA.exe`, `app.asar`, the VIZA Python engine package, the starter registry, and local universe configs. The current verified package still uses the system-Python fallback unless a bundled sidecar is supplied, so the PyInstaller/Nuitka artifact creation remains the next release-grade packaging step.

Verification:

```powershell
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run package:win
npm run smoke:package
```

Result: passed on 2026-05-12 with TypeScript typecheck clean, 10 desktop tests, successful `release/win-unpacked/VIZA.exe` packaging, and package-content smoke passing.

## 2026-05-12 - VIZA Phase 1-6 Consolidated Verification

Status: passed.

Progression:

After completing the Phase 1 through Phase 6 implementation pass, the full Python unit and look-ahead audit suite was rerun alongside the VIZA desktop TypeScript and Electron helper tests. This confirms the VIZA prototype hardening did not disturb the broader AAT unit surface or look-ahead timestamp audit checks.

Verification:

```powershell
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 141 Python tests, TypeScript typecheck clean, and 10 desktop tests.

## 2026-05-12 - VIZA Phase 1-6 Audit Remediation

Status: implemented and verified.

Progression:

The Phase 1 through Phase 6 audit findings were remediated before continuing into the leftover roadmap phases. The runtime compiler now rejects Output Radar paths that do not have an upstream Universe, preventing malformed graphs from crashing execution during universe resolution. Score execution now respects graph topology: Score weights are applied only to Attribute nodes that are upstream of the active Score node, while output-only attributes remain display/evidence columns and cannot silently alter rankings. Ignored score weights now produce a node-associated warning. Graph hashing was changed to ignore volatile `created_at` and `updated_at` timestamps so semantically identical methodology graphs produce stable hashes. Relationship querying can now filter an existing run result without rerunning the methodology, while still supporting graph-based queries when no run payload is provided. The Electron engine launcher now resolves bundled sidecars before checking for Python source files, records spawn errors, terminates failed child processes after health-check timeout, and preserves the system-Python development fallback. Dead duplicate prototype resolver code was removed from `viza/execution.py`, leaving `viza/attribute_resolvers.py` as the single deterministic fallback resolver surface.

Verification:

```powershell
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run package:win
npm run smoke:package
```

Result: passed on 2026-05-12 with 145 Python tests, TypeScript typecheck clean, 10 desktop tests, successful Windows unpacked packaging, and package-content smoke passing.

## 2026-05-12 - VIZA Phase 7: Attribute Registry V1 And Searchable Attribute UX

Status: implemented and verified.

Progression:

Phase 7 upgraded the attribute registry contract from `viza_attribute_registry_v0` to `viza_attribute_registry_v1` while keeping a migration loader for legacy v0 payloads. Registry entries now support source type, frequency, coverage, freshness, timestamp policy, entitlement and cache policy, production-scoring eligibility, evidence-only status, allowed transforms, compatible node types, diagnostics, limitations, ownership, model/data versions, and deprecation status, with conservative defaults applied by both the Python loader and the desktop static fallback. Runtime validation now checks registry-driven transform compatibility, warns when evidence-only attributes feed Score nodes unless the user explicitly enables `allow_evidence_only`, warns on non-production scoring inputs, and reports deprecated or entitlement-limited attributes. The run manifest now records both the attribute registry schema version and the registry content version.

The desktop Attribute inspector now uses a searchable picker instead of the simple dropdown. The picker supports search across key/name/description/source metadata, filters by family, source, unit, point-in-time status, contribution stage, entitlement state, and scoring state, and shows pinned and recently used attributes. Attribute rows and the detail panel now expose evidence-only, scoreable, locked/limited, source, unit, coverage, freshness, license, entitlement, allowed transforms, and limitations. The Score inspector now includes an explicit evidence-only acknowledgement toggle, and score weight labels mark evidence-only or restricted attributes.

Verification:

```powershell
python -m pytest tests\unit\test_viza_graph_schema.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_attribute_registry.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
```

Result: passed on 2026-05-12 with 32 targeted VIZA Python tests, 148 full Python unit/look-ahead tests, TypeScript typecheck clean, 10 desktop tests, and successful Vite production build.

## 2026-05-12 - VIZA Phase 8: Data Source And Entitlement Layer

Status: implemented and verified for the first local-first connector layer.

Progression:

Phase 8 added a connector and entitlement foundation under `viza/connectors.py`. The new layer defines connector definitions, health checks, field metadata, previews, entitlement rights, credential requirements, redacted connector settings, and a credential wrapper that reports secret availability without exposing secret values. The catalog now includes an available Local VIZA Workspace connector, a functional Local CSV connector driven by `VIZA_LOCAL_CSV_PATH`, and registered skeletons for Local Parquet, Local SQLite/DuckDB, AAT Postgres, Kenneth French, SEC EDGAR, FRED, and FMP. The FastAPI service now exposes `/viza/connectors`, `/viza/connectors/{connector_id}/test`, `/fields`, and `/preview`, and `/viza/runtime` reports connector IDs alongside data sources.

Runtime and evidence now treat source rights as first-class metadata. Attribute values include connector ID, license policy, cache policy, entitlement policy, and expanded entitlement rights. Evidence payloads surface those fields per cell, and run manifests now include a connector manifest grouped by connector ID and attribute keys. Runtime validation now warns for unconfigured connectors, credential-required attributes, non-queryable sources, derived-value restrictions, and export-limited sources without crashing graph execution. The desktop result panel now shows connector status and credential needs, giving users a visible connector/settings surface while keeping secrets out of methodology files.

Verification:

```powershell
python -m pytest tests\unit\test_viza_connectors.py tests\unit\test_viza_attribute_resolvers.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
```

Result: passed on 2026-05-12 with 30 targeted VIZA Python tests, 156 full Python unit/look-ahead tests, TypeScript typecheck clean, 10 desktop tests, and successful Vite production build.

## 2026-05-12 - VIZA Phase 9: Local Project Store And Methodology Versioning

Status: implemented and verified for the first SQLite-backed local project store.

Progression:

Phase 9 added `viza/project_store.py`, a local SQLite project store with an env override through `VIZA_PROJECT_STORE_PATH` and a default `local-sandbox` project. The schema now includes projects, methodology versions, run records, saved radar outputs, connector settings metadata, user settings, watchlists, and alerts, giving later phases a durable local storage foundation without changing the portable `.viza.json` methodology format. Methodology version saves now capture version ID, methodology ID, project ID, graph hash, parent version ID, label/message, schema version, graph created/updated timestamps, node/edge counts, and the full graph JSON. The store can list projects, save multiple versions, reload a version as a validated `MethodologyGraph`, and compare two versions for added/removed/changed nodes, added/removed/changed edges, and metadata changes.

The FastAPI engine now exposes project and version endpoints for default project creation, project listing/creation, project version listing, methodology version save/load, methodology version history, and version comparison. The desktop app now fetches the default local project, saves methodology versions to the store, lists recent saved versions, loads previous versions, clones a saved version into a new methodology, creates a revert version from an older graph, and displays a latest-vs-previous version diff summary. File save/load remains intact as the portable import/export surface.

Verification:

```powershell
python -m pytest tests\unit\test_viza_project_store.py tests\unit\test_viza_service.py tests\unit\test_viza_runtime.py tests\unit\test_viza_connectors.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
```

Result: passed on 2026-05-12 with 33 targeted VIZA Python tests, 161 full Python unit/look-ahead tests, TypeScript typecheck clean, 10 desktop tests, and successful Vite production build.

## 2026-05-12 - VIZA Phase 10: Audit, Evidence, And Reproducibility

Status: implemented and verified for the first reproducibility/audit layer.

Progression:

Phase 10 added `viza/audit.py`, which now provides normalized evidence records, canonical JSON checksums, evidence checksums, result checksums, manifest comparison, and reproduce-run request/response models. Runtime results now include a top-level `result_checksum`, normalized evidence records with `evidence_ref`, source, source record, source timestamp, timestamp availability, unit, calculation metadata, model/data versions, confidence, limitations, and license policy, and a richer run manifest. Manifests now record run ID, methodology version ID when present, graph schema/hash, runtime version, registry versions, timestamp cutoff, run start/finish timestamps, universe, connector states, entitlement states, data/model version sets, node execution statuses, warning payloads, evidence count/checksum, and result checksum. Stable reruns of the same graph and data versions now reproduce the same result checksum while still retaining volatile run IDs and timestamps for audit history.

The project store now persists run records with manifest JSON, result JSON, status, graph hash, version ID, and result checksum. The service can persist runs from `/viza/execute` when `project_id` is supplied, exposes project run listing and run lookup endpoints, and adds `/viza/reproduce` to rerun a methodology and compare the observed manifest against a baseline manifest across graph hash, result checksum, data versions, model versions, connector states, entitlement states, and warning codes. The desktop execution path now sends active project/version context so runs are persisted locally, and the result panel includes an Audit section showing run ID, graph/result/evidence checksums, start time, source states, and data/model versions.

Verification:

```powershell
python -m pytest tests\unit\test_viza_connectors.py tests\unit\test_viza_graph_schema.py tests\unit\test_viza_project_store.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_attribute_resolvers.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
```

Result: passed on 2026-05-12 with 47 targeted VIZA Python tests, 165 full Python unit/look-ahead tests, TypeScript typecheck clean, 10 desktop tests, and successful Vite production build.

## 2026-05-12 - VIZA Phase 11: Backtesting And Batch Execution

Status: implemented and verified for the first local in-memory backtest runner.

Progression:

Phase 11 added `viza/batch.py`, which now provides batch/backtest request and response models, multi-cutoff execution, optional multi-methodology/version input, ticker subset and universe overrides, per-run progress events, cooperative cancellation through `cancel_after_runs`, per-run diagnostics, and a per-node cache-key model keyed by node ID, graph hash, universe version, timestamp cutoff, attribute versions, and source versions. Batch execution clones the methodology graph per cutoff, stamps `timestamp_cutoff` and `as_of` onto the universe node, runs the normal methodology runtime, attaches batch context, point-in-time summaries, and cache keys to each run manifest, and persists each historical run when project context is supplied.

The audit layer now includes point-in-time cutoff parsing and evidence checks that enforce `timestamp_available <= cutoff`, with summaries for passed, violated, invalid, and non-applicable evidence records. Runtime evidence now carries universe timestamp availability onto local/prototype attribute evidence when no more specific source timestamp exists, so historical runs have meaningful PIT diagnostics. The FastAPI service exposes `/viza/batch/execute`, and the desktop app now includes a Backtest panel in the result sidebar for comma-separated cutoffs and optional ticker subsets, plus batch status, progress, PIT status, top ticker, row counts, and clickable historical result rows.

Verification:

```powershell
python -m pytest tests\unit\test_viza_batch.py tests\unit\test_viza_service.py tests\unit\test_viza_runtime.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
```

Result: passed on 2026-05-12 with 31 targeted VIZA Python tests, 169 full Python unit/look-ahead tests, TypeScript typecheck clean, 10 desktop tests, and successful Vite production build.

## 2026-05-12 - VIZA Phase 12: Radar Designer, Watchlists, Alerts, And Exports

Status: implemented and verified for the first local research-surface layer.

Progression:

Phase 12 expanded the local project store into usable research-surface persistence. `viza/project_store.py` now includes models and methods for saved radar outputs, watchlists, watchlist ticker updates, and local alert definitions. Saved radar outputs capture project, methodology, version, run ID, timestamp cutoff, selected columns, displayed rows, evidence refs, designer settings, and result checksum. Watchlists can be created from radar tickers and retain their source radar/run metadata, while alerts store local definitions for score thresholds, rank top-N checks, missing attributes, materiality/residual thresholds, and relationship-edge conditions.

The FastAPI engine now exposes radar, watchlist, alert, watchlist-run, and export endpoints. `/viza/watchlists/{watchlist_id}/execute` reruns a methodology with the watchlist tickers stamped into the universe node and persists the run under the watchlist project. `viza/exports.py` adds an entitlement-aware export pipeline for CSV, JSON, methodology graph JSON, and run manifest JSON. CSV and JSON radar exports redact cells and evidence values when their evidence entitlement says export is not allowed, while reporting structured redaction records so restricted source data is not silently leaked.

The desktop result panel now includes a Designer section that lets the user filter rows, sort by rank/score/ticker/attributes, toggle displayed columns, show evidence counts, view scorecards, save the current radar, create a watchlist from displayed tickers, define a local alert, and export CSV, JSON, manifest, or methodology graph files. The radar table now reflects the designer controls directly, making the result panel a reusable research surface rather than a static run preview.

Verification:

```powershell
python -m pytest tests\unit\test_viza_research_surfaces.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
```

Result: passed on 2026-05-12 with 24 targeted VIZA Python tests, 172 full Python unit/look-ahead tests, TypeScript typecheck clean, 10 desktop tests, and successful Vite production build.

## 2026-05-12 - VIZA Phase 13: Production Attribute Expansion

Status: implemented and verified for the first expanded analyst-facing attribute catalog.

Progression:

Phase 13 added `viza/attribute_expansion.py`, which appends a Phase 13 catalog to the starter JSON registry when the default local registry is loaded. The registry version is now `1.1.0`, and VIZA exposes 73 attributes across baseline attribution, macro attribution, event intelligence, fundamentals, exposure gates, and positioning/options. The new attributes include market, industry, subindustry, custom peer basket, peer residual spread, beta, ten macro series, richer event classification/surprise/relevance fields, sixteen fundamental/exposure descriptors, and nine positioning/options descriptors. Each expanded attribute carries contribution stage, timestamp policy, evidence policy, license/entitlement/cache policy, model/data versions, diagnostics, and limitations so users can tell what is prototype, evidence-only, shadow, or production-scoring eligible.

`viza/attribute_resolvers.py` now resolves the expanded catalog with deterministic prototype values and preserves local universe-backed values for sector, industry, subindustry, and run status. Phase 13 values are labeled with `phase_13_deterministic_fallback`, `phase_13_prototype_v0`, and `phase_13_deterministic_resolver_v0`; macro attributes map to the public macro connector path, and positioning/options attributes map to FMP or licensed-source policy with no-export entitlement. This keeps the larger catalog usable in methodology design while still making restricted or source-incomplete fields explicit in evidence, manifests, connector warnings, and export redaction.

The attribute picker automatically receives the expanded catalog from the existing `/viza/attributes` endpoint, and `docs/VIZA_ATTRIBUTE_IMPLEMENTATION_CHECKLIST.md` now defines the promotion gates for future source-backed work: metadata, PIT validation, resolver promotion, confidence evidence, and export/compliance requirements.

Verification:

```powershell
python -m pytest tests\unit\test_viza_attribute_registry.py tests\unit\test_viza_attribute_resolvers.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_connectors.py tests\unit\test_viza_research_surfaces.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
```

Result: passed on 2026-05-12 with 43 targeted VIZA Python tests, 173 full Python unit/look-ahead tests, TypeScript typecheck clean, 10 desktop tests, and successful Vite production build.

## 2026-05-12 - VIZA Phase 14: Product Release Readiness

Status: implemented and verified for prototype release readiness.

Progression:

Phase 14 added `viza/diagnostics.py` and the `/viza/diagnostics` FastAPI endpoint, giving VIZA a read-only release diagnostics surface for engine version, diagnostics version, Python/platform/runtime paths, local token mode, attribute registry version/count, connector readiness, and local project-store health. Project-store diagnostics now distinguish missing stores from corrupt or incomplete stores, report schema tables and missing tables, count projects/methodology versions/runs, and surface the last persisted run status without exposing secrets. Connector diagnostics report credential-required/configured state, query/export policy, license policy, and cache policy while continuing to keep credential values out of responses.

The desktop shell now exposes richer `viza:desktopStatus` metadata and a `viza:restartEngine` bridge. The status payload includes app version, packaged/dev mode, platform/arch, user-data path, engine root, engine log path, engine runtime mode, PID, base URL, and token presence while still returning the token only for local API request authorization. The frontend now clears its cached engine URL/token after restart, refreshes metadata, and shows a Diagnostics panel with engine version, Python version, desktop version, runtime path, project path, log path, connector summary, last run status, backend checks, refresh, and restart controls.

Phase 14 also added `docs/VIZA_RELEASE_READINESS_CHECKLIST.md`, updated `docs/VIZA_PACKAGING.md` with diagnostics/recovery guidance and current release limitations, updated the detailed implementation plan status for Phase 14, and expanded the package smoke test so packaged builds must include the diagnostics module. The live local VIZA engine was restarted after implementation; `/viza/diagnostics` reported engine `0.2.0`, diagnostics `viza_runtime_phase_14_release_readiness_v0`, 73 attributes, and an `ok` project store after default project initialization.

Verification:

```powershell
python -m pytest tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
npm run package:win
npm run smoke:package
```

Result: passed on 2026-05-12 with 4 diagnostics tests, 25 targeted VIZA Python tests, 177 full Python unit/look-ahead tests, TypeScript typecheck clean, 10 desktop tests, successful Vite production build, successful Windows unpacked package build, and successful package contents smoke.

## 2026-05-12 - VIZA Phase 15: macOS External Release Automation

Status: implemented for repository-side macOS release automation. A signed/notarized artifact still has to be produced on a macOS build machine with Apple credentials.

Progression:

Phase 15 added a dedicated macOS release configuration at `apps/viza-desktop/electron-builder.mac-release.yml` with Developer ID distribution settings, hardened runtime, entitlements, notarization enabled, DMG/ZIP targets, and explicit signing of the bundled engine binary. The base Electron Builder config now uses the shared packaging resource directory and retains the Windows unpacked development package path.

The desktop package version is now `0.1.0`, and the macOS release path adds `npm run release:mac`. That command refuses to run off macOS, requires Developer ID signing and Apple notarization credentials, builds the React/Electron frontend, builds a bundled PyInstaller `viza-engine` sidecar, packages the current Mac architecture as DMG and ZIP, and runs macOS package smoke checks for app contents, codesign verification, stapler validation, and Gatekeeper assessment. `npm run package:mac:dir` remains available for local macOS developer packaging.

The Python project now exposes a `release` optional dependency group for PyInstaller. Desktop tests now cover the Darwin sidecar executable name and macOS release preflight behavior. Packaging docs and the release checklist now describe the externally distributable macOS path, required Apple credentials, expected outputs, and the fact that the final artifact cannot be built or notarized from Windows.

Verification:

```powershell
cd apps\viza-desktop
npm run test:desktop
npm run typecheck
npm run preflight:mac
npm run build
npm run package:win
npm run smoke:package
npm run release:mac
```

Result: passed on 2026-05-12 with 14 desktop tests, TypeScript typecheck clean, successful Vite production build, successful Windows unpacked package build, and successful Windows package contents smoke. `npm run preflight:mac` and `npm run release:mac` failed as expected on Windows because macOS release artifacts require macOS, a Developer ID Application identity, and Apple notarization credentials.

## 2026-05-12 - VIZA Phase 16: Baseline Lock And Migration Guardrails

Status: implemented and verified. No visible product behavior changed.

Progression:

Phase 16 created the `viza-universal-file-and-modules` working branch and added a baseline lock document at `docs/VIZA_PHASE_16_BASELINE_LOCK.md`. The baseline records the current `viza_graph_v0` graph contract, supported node and edge types, attribute registry schema/version, local project-store tables, and current packaging behavior that future `.viza` and module migration work must preserve.

Phase 16 also added `docs/VIZA_COMPATIBILITY_POLICY.md`, documenting that `viza_graph_v0` remains loadable, `.viza.json` remains importable, `.viza` becomes the default only after round-trip tests pass, existing project-store records are not rewritten in place, and migrations are additive unless explicitly documented and tested.

The backend now has `viza/compat.py` with schema normalization, supported/legacy graph-schema checks, and environment-backed feature flag evaluation for `VIZA_ENABLE_UNIVERSAL_CONTAINER`, `VIZA_ENABLE_MODULE_REGISTRY`, `VIZA_ENABLE_EXPERIMENTAL_GRAPH_V1`, and `VIZA_ENABLE_NON_FINANCE_MODULES`. The desktop app now has a matching frontend helper at `apps/viza-desktop/src/lib/featureFlags.ts`, but no new UI is exposed in Phase 16.

Verification:

```powershell
python -m pytest tests\unit\test_viza_compat.py
python -m pytest tests\unit\test_viza_graph_schema.py tests\unit\test_viza_attribute_registry.py tests\unit\test_viza_service.py
python -m pytest tests\unit\test_viza_project_store.py tests\unit\test_viza_runtime.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 5 Phase 16 compatibility tests, 29 graph/registry/service tests, 14 project-store/runtime tests, 182 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 17: Universal `.viza` Container Backend

Status: implemented and verified for the backend container layer. Full file-viewer UI remains Phase 19 work.

Progression:

Phase 17 added the `viza/file_format/` package with manifest models, canonical section names, section status and visibility enums, checksum helpers, ZIP path safety checks, safe manifest inspection, section reads, container writes, legacy `.viza.json` wrapping, and methodology graph export/import helpers. The durable document schema is `viza.document.v1`, with a migration alias for `viza_file_v0`.

The `.viza` writer now produces ZIP-based containers with `manifest.json` at the root, normalized JSON section payloads, per-section SHA-256 checksums, a manifest checksum, and a computed container checksum. Redacted and entitlement-locked sections are represented in the manifest but are not bundled. The reader inspects manifests before loading sections, warns on future unsupported schemas, rejects malformed/missing manifests, verifies section checksums on read, and refuses unsafe ZIP members, path traversal, symlinks, executable payload extensions, and credential-like section keys.

Phase 17 added local-path development endpoints in `viza/service.py`: `/viza/files/inspect`, `/viza/files/validate`, `/viza/files/export`, `/viza/files/import`, `/viza/files/{file_id}`, `/viza/files/{file_id}/sections`, and `/viza/files/quarantine`. The local SQLite project store now has additive `viza_file_imports` and `viza_file_exports` tables, record helpers, and quarantine tracking. Runtime diagnostics include those new tables in the expected project-store schema. The desktop app also has a thin file API client under `apps/viza-desktop/src/features/vizaFiles/`, but no new visible UI was introduced.

Verification:

```powershell
python -m pytest tests\unit\test_viza_file_format.py tests\unit\test_viza_file_security.py tests\unit\test_viza_file_import_export.py
python -m pytest tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 12 Phase 17 file-format/security/import-export tests, 25 targeted service/project-store/diagnostics tests, 194 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 18: Module Registry And Finance/Securities Module Conversion

Status: implemented and verified. Current graph execution and the existing visible node palette remain unchanged.

Progression:

Phase 18 added `viza/modules/` with module manifest models, node type definitions, palette groups, output-view definitions, compatibility results, and unknown-module placeholders. The `viza.core.strategy` module defines the domain-neutral primitives, and `viza.finance.securities` wraps the existing `viza_graph_v0` node vocabulary as module node types while preserving legacy runtime mappings.

The module registry can list modules, fetch a module by ID, resolve legacy node types to finance module types, map finance module node types back to legacy node types, derive required modules for a current methodology graph, and return locked placeholders for missing modules while preserving raw config. `.viza` methodology exports already include `viza.finance.securities` as a required module.

The local engine now exposes `/viza/modules`, `/viza/modules/{module_id}`, `/viza/modules/resolve-node-types`, and `/viza/modules/check-compatibility`. The desktop app now has a thin module API client and an unknown-node placeholder component under `apps/viza-desktop/src/features/modules/`. The existing React Flow node definitions now carry finance module metadata without changing labels or toolbar behavior.

Verification:

```powershell
python -m pytest tests\unit\test_viza_modules.py tests\unit\test_viza_file_import_export.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 6 Phase 18 module tests, 26 focused module/file/service tests, 200 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 19: `.viza` File Viewer, Import Flow, Export Wizard, And Exchange Inbox

Status: implemented and verified for the first backend visualization and frontend component layer.

Progression:

Phase 19 added a structured file visualization payload for `.viza` manifests. Inspection now carries file summary, section contents map, module compatibility, connector requirements, permissions, warnings, checksum status, and available actions while preserving the existing inspection fields. A recorded file can also be visualized through `/viza/files/{file_id}/visualization`.

The import endpoint now supports `open_without_import`, `import_to_project`, `fork_as_new_methodology`, and `quarantine` modes. The export endpoint accepts wizard-style fields such as purpose, visibility, include sections, project ID, methodology version ID, and target path while preserving direct graph export. Electron gained safe file-path selection bridges for `.viza` open/export flows.

The desktop source tree now includes first-pass `VizaFileViewer`, `StrategyExchangeInbox`, and `VizaExportWizard` components plus expanded file-client types. These components are intentionally not yet wired as a replacement for the current canvas-first shell.

Verification:

```powershell
python -m pytest tests\unit\test_viza_file_visualization.py tests\unit\test_viza_file_import_export.py tests\unit\test_viza_file_format.py tests\unit\test_viza_modules.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 4 Phase 19 visualization tests, 16 focused file/module tests, 204 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 20: Universal Entity Store And Finance Security Master Seed

Status: implemented and verified. Existing ticker-first methodology behavior and UI output remain compatible.

Progression:

Phase 20 added a domain-neutral `VizaEntity` layer plus a finance-specific `VizaAsset` security master. The local project store now initializes additive `entities`, `finance_assets`, and `entity_relationships` tables, and diagnostics include them in the expected schema checks.

The pilot S&P 500 static universe can now seed canonical company entities and US equity assets, with deterministic `entity_id` and `asset_id` values, missing-provider-identifier warnings, provider identifier maps, and explicit local-universe lineage. The local engine exposes entity search/resolve/get/relationship endpoints and asset search/resolve/get/identifier/reconcile endpoints.

Runtime rows now carry `entity_id` and `asset_id`, and company/attribute evidence records include those IDs along with source identifier metadata. The desktop source tree also has first-pass entity/asset resolver client types and an `AssetResolverPanel` scaffold for later inspector integration.

Verification:

```powershell
python -m pytest tests\unit\test_viza_entities.py tests\unit\test_viza_assets.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 34 focused Phase 20/service/runtime tests, 211 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 21: Credential Vault And Source-Backed Connector Configuration

Status: implemented and verified. Secret values are accepted only through one-time credential writes and are not returned through the API, diagnostics, SQLite connector metadata, or `.viza` exports.

Progression:

Phase 21 added `viza/credentials.py`, a credential vault abstraction that uses OS keyring when available and falls back to an explicitly labeled `env_var_dev` mode for development. Credential references and status records contain storage references and availability only, never saved secret values.

The local engine now exposes connector credential status, set, delete, and configure endpoints. Connector configuration persistence has additive columns for project ID, redacted non-secret settings, credential references, credential status, and updated timestamps. Connector health and runtime diagnostics now include credential/configuration availability and entitlement booleans while keeping secret values out of responses.

The Local CSV connector can consume saved non-secret path settings, and the desktop source tree now has connector client/types plus an initial `ConnectorSettingsPanel` scaffold that clears secret inputs after save and renders status without stored secret values.

Verification:

```powershell
python -m pytest tests\unit\test_viza_credentials.py tests\unit\test_viza_connectors.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_project_store.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 35 focused Phase 21/connectors/project-store/service tests, 215 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 22: Point-In-Time Observation Store And Technical Resolver Promotion

Status: implemented and verified. Technical attributes can now be source-backed from PIT-safe observations where rows exist, while prototype fallback remains explicit.

Progression:

Phase 22 added `viza/observations.py` with a `VizaObservation` model, ingestion/query request models, deterministic checksums, SQLite persistence, PIT-safe `available_at <= cutoff` lookup, and restricted-export redaction helpers. The local project store and diagnostics now include the additive `observations` table.

The observation layer can derive first-wedge technical values from local OHLCV rows: latest price, RSI 14d, momentum, moving-average trend, volume spike, realized volatility, and short-term reversal when sufficient history exists. Attribute resolution now checks the observation store for technical attributes before falling back to deterministic prototype values.

Runtime evidence now carries observation ID, observed/available/retrieved timestamps, rights policy, and PIT status when an observation backs an attribute. The engine exposes observation query, get, and ingest endpoints, and the desktop source tree has observation client/types plus a small source/prototype badge scaffold for later inspector wiring.

Verification:

```powershell
python -m pytest tests\unit\test_viza_observations.py tests\unit\test_viza_attribute_resolvers.py tests\unit\test_viza_runtime.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 44 focused Phase 22/runtime/project-store/service tests, 221 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 23: Event/Catalyst Object Model

Status: implemented and verified. Events are now first-class local objects that can be created manually, extracted deterministically from run outputs, persisted, queried, exported as a `.viza` section, and surfaced as relationship edges.

Progression:

Phase 23 added `config/viza_event_registry.json` with the initial catalyst catalog and `viza/events.py` with the `VizaEvent` schema, manual event requests, extraction/query models, SQLite persistence, deterministic event IDs, PIT cutoff filtering, and restricted-export redaction.

The local engine now exposes `/viza/events/extract`, `/viza/events/query`, `/viza/events/{event_id}`, and `/viza/events/manual`. Deterministic extraction uses existing event-intelligence attributes such as `event_materiality`, `event_novelty`, and `event_count`, producing event objects linked to `entity_id`, `asset_id`, and evidence refs. The project store and diagnostics include the additive `events` table.

The finance module registry now includes `viza.finance.securities.event_catalyst`. Relationship queries enrich run relationships with `entity_to_event` and `asset_to_event` event-family edges. The desktop source tree also has event client/types plus a first-pass `EventCard` scaffold for later result and inspector wiring.

Verification:

```powershell
python -m pytest tests\unit\test_viza_events.py tests\unit\test_viza_modules.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 48 focused Phase 23/module/runtime/service tests, 228 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 24: Insight Object Schema, Registry, And Extraction

Status: implemented and verified. Runtime results now emit first-class insight objects and insight relationship edges while preserving existing radar row behavior.

Progression:

Phase 24 added `config/viza_insight_registry.json` with the first insight catalog and `viza/insights.py` with the `VizaInsight` schema, registry loading, rule-based extraction, SQLite persistence, PIT cutoff filtering, query/get helpers, and export sanitization/redaction.

The local engine now exposes `/viza/insights/extract`, `/viza/insights/query`, and `/viza/insights/{insight_id}`. The finance module registry includes `viza.finance.securities.insight_extractor`. Runtime `MethodologyRunResult` now carries `insights` and `insight_relationships`, and relationship queries can return insight-family edges.

The desktop source tree now has insight client/types and an initial `InsightList` scaffold for later result-panel wiring. Insight `.viza` export payloads sanitize credential-worded entitlement flags before packaging.

Verification:

```powershell
python -m pytest tests\unit\test_viza_insights.py tests\unit\test_viza_events.py tests\unit\test_viza_modules.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 56 focused Phase 24/module/runtime/service tests, 236 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 25: Strategy Profile System

Status: implemented and verified. The first strategy-profile template exists, profiles can be created/updated/cloned, and profiles can be exported in `.viza` containers.

Progression:

Phase 25 added `config/viza_strategy_profile_templates.json` with the RSI Swing + Catalyst Confirmation template and `viza/strategy_profiles.py` with the `VizaStrategyProfile` schema, template loading, SQLite persistence, stable profile hashing, version records, create/update/clone behavior, and template-backed creation.

The local engine now exposes strategy profile list, create, get, update, clone, and template endpoints. The project store and diagnostics include additive `strategy_profiles` and `strategy_profile_versions` tables. The finance module registry includes `viza.finance.securities.strategy_profile`, backed by a new core strategy primitive.

The desktop source tree now includes strategy profile client/types plus first-pass `StrategyProfileBuilder` and `StrategyProfileInspector` scaffolds.

Verification:

```powershell
python -m pytest tests\unit\test_viza_strategy_profiles.py tests\unit\test_viza_modules.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 37 focused Phase 25/module/service/project-store tests, 242 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 26: Insight Translation Engine And Strategy-Fit Output

Status: implemented and verified. Insight objects now translate through strategy profiles into deterministic strategy-fit explanations and radar-row output.

Progression:

Phase 26 added `viza/translation.py` with the `VizaTranslation` schema, deterministic fit scoring, single and batch translation helpers, SQLite persistence, default strategy-profile translation, and restricted-export translation payloads.

The local engine now exposes `/viza/translate`, `/viza/translate/batch`, and `/viza/translations/{translation_id}`. The project store and diagnostics include the additive `translations` table.

Runtime results now carry `translations`, and radar rows can include strategy-fit score, primary insight type, translated summary, confidence, horizon, missing confirmations, invalidation conditions, risk flags, evidence count, source restrictions, and PIT status while preserving existing fields.

The desktop source tree now includes translation client/types plus a first-pass `StrategyFitBadge` scaffold for later radar and card wiring.

Verification:

```powershell
python -m pytest tests\unit\test_viza_translation.py tests\unit\test_viza_insights.py tests\unit\test_viza_strategy_profiles.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 56 focused Phase 26/insight/profile/runtime/service/project-store tests, 249 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 27: Insight Cards And Strategy-Fit Radar UI

Status: implemented and verified. Translated insights are now visible from selected radar rows, with evidence, missing confirmations, invalidation, risk, relationships, and audit context exposed in the desktop result panel.

Progression:

Phase 27 added `viza/insight_cards.py`, which derives consolidated insight-card payloads from saved run results, and `/viza/runs/{run_id}/insight-cards` for run-backed card retrieval.

The desktop app now renders `InsightCardsPanel` and `InsightCard` for selected radar rows, adds strategy-fit score, insight type, and translated summary columns to the radar table, and adds filters/sorting for fit score, insight type, confidence, missing confirmations, risk flags, PIT status, and source restrictions.

CSV/JSON export handling now supports strategy-fit row fields, includes insights and translations in JSON exports, redacts restricted evidence payloads, and records derived-summary redactions when source restrictions block export.

Verification:

```powershell
python -m pytest tests\unit\test_viza_insight_cards.py tests\unit\test_viza_translation.py tests\unit\test_viza_research_surfaces.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 31 focused Phase 27/translation/research-surface/service tests, 253 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 28: Relationship Graph Universalization And Insight Reaction Graph

Status: implemented and verified. Relationships now carry universal object metadata and can be queried from insights, events, assets, entities, and object-type filters.

Progression:

Phase 28 added universal fields to `RelationshipEdge`, including deterministic relationship IDs, source/target object IDs and types, universal families, PIT timestamps, evidence refs, rights policies, and module IDs while preserving the existing relationship-family surface.

Relationship queries now support entity, asset, insight, event, family, source type, target type, minimum confidence, time horizon, PIT-only, and relationship-type filters. The relationship system now derives insight-to-event edges, insight-to-strategy-profile edges, and deterministic insight reaction edges for confirms/conflicts/invalidates cases.

The desktop relationship graph now recognizes entity, asset, event, insight, attribute, strategy-profile, and output node types, includes object-type filtering, uses universal relationship family filters, and renders edge labels.

Verification:

```powershell
python -m pytest tests\unit\test_viza_relationships.py tests\unit\test_viza_events.py tests\unit\test_viza_insights.py tests\unit\test_viza_service.py tests\unit\test_viza_runtime.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 47 focused Phase 28/event/insight/service/runtime tests, 258 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 29: Validation Ledger And Proof Objects

Status: implemented and verified. Strategy outputs can now be recorded as durable validation records and exported as honest proof payloads with pending performance observation status.

Progression:

Phase 29 added `viza/validation_ledger.py` with `VizaValidationRecord`, validation-record creation from run results or saved run IDs, SQLite ledger persistence, record comparison, replay comparison, proof export/import helpers, and checksum validation.

The local engine now exposes `/viza/validation/record`, `/viza/validation/{record_id}`, `/viza/validation/compare`, `/viza/validation/replay`, and `/viza/validation/by-run/{run_id}`. The project store and diagnostics now include the additive `validation_records` table.

`.viza` proof packaging now uses the existing `validation_proof -> proof/validation_manifest.json` section mapping, with exported entitlement proof sanitized so credential-like keys do not enter containers. The desktop audit view now includes a validation panel for proof status, record creation, pending observation state, and proof export.

Verification:

```powershell
python -m pytest tests\unit\test_viza_validation_ledger.py tests\unit\test_viza_file_security.py tests\unit\test_viza_file_format.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 41 focused Phase 29/file/security/project-store/diagnostics/service tests, 265 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 30: White-Box, Gray-Box, Black-Box, And Output-Only Packaging

Status: implemented and verified. `.viza` exports now support visibility-specific packaging with ZIP-level redaction and permission-aware import/open behavior.

Progression:

Phase 30 added `viza/file_format/packaging.py` with packaging policies for white-box, gray-box, black-box, output-only, and preview-only exports. Redacted and entitlement-locked sections are not written into the ZIP, and gray-box graph payloads remove parameter values such as weights, thresholds, proprietary notes, and formula-like config keys.

The file export request now accepts visibility, validation-proof, signal-output, sample-output, parameter-redaction, and locked-section options. Import/open now respects package permissions and graph section status, so black-box/output-only packages can be inspected without exposing or forking hidden graph content.

The desktop export wizard now shows visibility implications and redaction/locking controls, while the file viewer shows visibility badges and disabled forbidden actions.

Verification:

```powershell
python -m pytest tests\unit\test_viza_packaging.py tests\unit\test_viza_file_security.py tests\unit\test_viza_file_format.py tests\unit\test_viza_file_import_export.py tests\unit\test_viza_file_visualization.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 39 focused Phase 30/file/security/import-export/visualization/service tests, 271 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 31: First Non-Finance Module Smoke Test - Real Estate Acquisition

Status: implemented and verified. VIZA now has a feature-flagged non-finance module smoke test that can package and reopen an experimental real estate acquisition strategy file.

Progression:

Phase 31 added `config/viza_modules/viza.real_estate.acquisition.json` and `viza/modules/real_estate_acquisition.py` for a real estate acquisition module behind `VIZA_ENABLE_NON_FINANCE_MODULES=true`.

`viza/real_estate.py` implements the local-CSV runtime wedge: property universe loading, NOI projection, DSCR gating, deal scoring, deal pipeline output, and investment memo generation. It also exports/imports an experimental module-aware real estate `.viza` payload with required modules `[viza.core.strategy, viza.real_estate.acquisition]`.

The desktop source tree now includes first-pass real estate deal pipeline and investment memo views, and module-disabled behavior continues to resolve real-estate nodes as locked placeholders that preserve raw config.

Verification:

```powershell
python -m pytest tests\unit\test_viza_real_estate_module.py tests\unit\test_viza_modules.py tests\unit\test_viza_file_format.py tests\unit\test_viza_packaging.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 21 focused Phase 31/module/file/packaging tests, 277 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 32: Source-Backed Resolver Promotion For First Wedge

Status: implemented and verified. The first equities wedge can now promote local technical observations and starter events from source-backed paths while keeping prototype fallback and source-rights status visible.

Progression:

Phase 32 added source-backed registry entries for `rsi_14d`, `moving_average_trend`, `volume_spike`, and `sector_relative_strength`, plus local OHLCV CSV parsing and complete local-source rights defaults for observation ingestion.

Observation-backed attribute values now carry the required connector/source/license/cache/display/export/derived/redistribution/attribution/retention policy fields. Runtime diagnostics report source-backed resolver count, prototype fallback count, credential-ready connector count, observation-store status, and last resolver warning count.

`viza/source_events.py` adds SEC filing metadata CSV extraction, local events CSV extraction for analyst/news/social/insider-style events, and unusual-volume event extraction from OHLCV. Export redaction now honors source-rights export policy even when the entitlement policy allows export.

The desktop attribute picker and evidence panel now distinguish source-backed, prototype fallback, evidence-only, and restricted-export states, and source-backed attributes expose their connector mapping path.

Verification:

```powershell
python -m pytest tests\unit\test_viza_source_backed_resolvers.py tests\unit\test_viza_observations.py tests\unit\test_viza_attribute_resolvers.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_events.py tests\unit\test_viza_research_surfaces.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 30 focused Phase 32/observation/resolver/diagnostics/event/research-surface tests, 284 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 33: Large-Data Runtime, Streaming Progress, Cancellation, Scheduler, And Caches

Status: implemented and verified. VIZA now has a local runtime job layer with polling progress, durable cancellation state, cache diagnostics, and saved-radar schedules.

Progression:

Phase 33 added `viza/runtime_jobs.py` and SQLite tables for `runtime_jobs`, `runtime_job_events`, `runtime_cache_entries`, and `radar_schedules`.

The local engine now exposes runtime job endpoints for create, inspect, cancel, events, and project job listing. Methodology-run jobs can execute in the background, persist run records, emit progress events, and reuse cache entries when graph/source/connector/version inputs match. Runtime cache keys include node ID, graph hash, module ID, universe version, timestamp cutoff, attribute versions, source versions, connector states, and strategy profile hash.

Saved radars can now persist local refresh schedules with `manual`, `daily`, `weekly`, and `on_app_start` cadences. The desktop run flow now starts a runtime job, polls progress/events, shows cache hit/miss diagnostics, supports cancellation, and hydrates completed run results from the saved run record.

Verification:

```powershell
python -m pytest tests\unit\test_viza_runtime_jobs.py tests\unit\test_viza_batch.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 34 focused Phase 33/batch/project-store/diagnostics/service tests, 289 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

## 2026-05-12 - VIZA Phase 34: Release Packaging And Installer Hardening

Status: implemented and verified. VIZA desktop packaging now builds and bundles the local engine sidecar, emits a Windows NSIS installer, and exposes stronger support diagnostics without secrets.

Progression:

Phase 34 added a PyInstaller-based engine sidecar build step for packaged desktop releases. Windows builds now produce `packaging/engine/viza-engine.exe`, include it as an Electron extra resource, and production engine startup prefers the bundled sidecar over system Python.

The Windows release flow now runs a signing-aware preflight, builds the sidecar, builds the desktop app, and emits both `win-unpacked` and NSIS installer artifacts while preserving app data on uninstall. Package smoke tests verify that the sidecar and installer are present. macOS release smoke/preflight paths continue through the existing release automation and now verify the engine sidecar signature on macOS build hosts.

Runtime diagnostics now include file-format version, installed modules, credential mode, observation store health, `.viza` import/export health, and the last quarantine event. The desktop diagnostics panel summarizes those fields and can export a redacted diagnostics bundle for support use.

Verification:

```powershell
cd apps\viza-desktop
npm run package:win
npm run smoke:package
npm run typecheck
npm run test:desktop
cd ..\..
python -m pytest tests\unit tests\lookahead_audit
```

Result: passed on 2026-05-12 with a Windows sidecar-backed NSIS package and smoke check, 289 full Python unit/look-ahead tests, TypeScript typecheck clean, and 17 desktop tests. `npm run release:mac` remains a macOS build-host verification path because signing/notarization require macOS and Apple credentials.

## 2026-05-12 - VIZA Phase 35: Marketplace Readiness Guardrails, Not Marketplace Launch

Status: implemented and verified. VIZA can now produce marketplace draft review packages with creator placeholders, compliance warnings, readiness metadata, and no monetized marketplace surface.

Progression:
+*
Phase 35 added `viza/marketplace.py` for review-only marketplace draft assessment: allowed summaries, source-rights summaries, creator placeholders, compliance warnings, and internal readiness checks.

`.viza` export now accepts the `marketplace_draft` purpose. Draft packages redact the full methodology graph, include marketplace metadata and rights-summary sections, include validation proof when available, and disable run/fork/export/redistribution/publish permissions. Explicit source policies that forbid redistribution or marketplace packaging block the draft export instead of producing a package.

The project store now includes `creator_records` plus local creator persistence helpers and endpoints. The desktop export wizard exposes marketplace draft purpose, creator placeholder input, not-investment-advice acknowledgement, and a compliance checklist. File visualization can surface compliance warnings and readiness state. No buy, sell, checkout, payment, or subscription endpoints or UI were added.

Verification:

```powershell
python -m pytest tests\unit\test_viza_marketplace.py tests\unit\test_viza_packaging.py tests\unit\test_viza_file_format.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 39 focused Phase 35/packaging/file/project-store/diagnostics/service tests, 294 full Python unit/look-ahead tests, TypeScript typecheck clean, and 17 desktop tests.

## 2026-05-12 - VIZA Post-Phase Audit: Product/Log Alignment Remediation

Status: implemented and verified. The completed-phase audit found two concrete gaps where logged file-exchange capabilities existed in backend/components but were not fully reachable in the desktop product shell.

Progression:

The `.viza` file viewer, export wizard, marketplace-draft export controls, and strategy-exchange inbox are now wired into the desktop result sidebar through a `.viza Exchange` panel. The panel can choose export/open paths through the desktop bridge, export review packages through `/viza/files/export`, inspect selected packages, open/import/fork/quarantine packages through `/viza/files/import`, and apply readable imported graphs to the canvas.

The local engine now exposes `GET /viza/files` so the strategy-exchange inbox can list imported, exported, and quarantined file records instead of existing only as an isolated component. Marketplace draft export also receives current-run source-rights context when available, while internally owned/local workspace records are not treated as third-party redistribution blockers unless an explicit marketplace or redistribution policy says so.

Verification:

```powershell
python -m pytest tests\unit\test_viza_marketplace.py tests\unit\test_viza_project_store.py tests\unit\test_viza_service.py tests\unit\test_viza_file_import_export.py tests\unit\test_viza_file_visualization.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-12 with 37 focused VIZA file/marketplace/project-store/service tests, 298 full Python unit/look-ahead tests, TypeScript typecheck clean, and 17 desktop tests.

## 2026-05-13 - VIZA Packaged Engine Config Path And Runtime Job Hardening

Status: implemented and verified. The packaged Windows sidecar now loads VIZA config from the adjacent `resources/engine/config` directory instead of looking inside PyInstaller's temporary `_MEI...` extraction folder.

Progression:

Added a shared Python config path resolver with support for `VIZA_CONFIG_DIR`, `VIZA_ENGINE_ROOT/config`, packaged sidecar-adjacent config, and source checkout fallback. Attribute registry, universe, connector, event, insight, strategy-profile, and real-estate module config loading now use that resolver, and display paths no longer assume config files are relative to the source repo.

Electron now passes `VIZA_ENGINE_ROOT` and `VIZA_CONFIG_DIR` into the spawned local engine. Windows and macOS packaging configs now include all current VIZA runtime config sections, including event/insight registries, strategy profile templates, and module manifests.

Runtime jobs now catch registry/config load failures before execution starts, marking jobs as `failed` with a finished timestamp and failure event instead of leaving them permanently `pending`. The desktop metadata load path now distinguishes engine-loaded metadata from fallback attributes and reports incomplete metadata without pretending fallback counts came from the engine.

Runtime diagnostics now expose the resolved config root and required config-file health. Package smoke testing now starts the bundled sidecar, verifies `/health`, `/viza/attributes`, `/viza/universes`, `/viza/connectors`, and `/viza/diagnostics`, and confirms a runtime job reaches a terminal completed state.

Verification:

```powershell
python -m pytest tests\unit\test_viza_config_paths.py tests\unit\test_viza_attribute_registry.py tests\unit\test_viza_runtime_jobs.py tests\unit\test_viza_diagnostics.py
cd apps\viza-desktop
npm run test:desktop
npm run typecheck
npm run package:win
npm run smoke:package
cd ..\..
python -m pytest tests\unit tests\lookahead_audit
```

Result: passed on 2026-05-13 with 18 focused Python config/runtime/diagnostics tests, 18 desktop helper tests, TypeScript typecheck clean, successful Windows sidecar-backed package build, successful packaged sidecar API smoke, and 303 full Python unit/look-ahead tests. The first package attempt failed because an older `release/win-unpacked` sidecar process was locking `viza-engine.exe`; stopping that stale dev-package sidecar allowed the verified build to complete.

## 2026-05-21 - VIZA Phases 26–37: Compliance Restructure And Investment-Command Layer

Status: implemented and verified in source. The Windows installer has not been rebuilt since this work landed; `release/win-unpacked` predates Phases 26–34 and a fresh `npm run package:win` is required before user-facing release.

Scope: this batch implements every phase in `docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md` (Phases 26–33) plus three closeout phases (34–36) that wire the new surface through the desktop and prepare the package smoke. The compliance restructure aligns VIZA's strategies-and-decisions schema with the eight disciplines named in `docs/viza_end_product/VIZA_KR_COMPLIANCE_REPORT.md`: SKOS / FIBO / W3C PROV / OMG DMN / CEP / bitemporal modeling / argumentation. Rete and full streaming CEP remain deferred (the report's §9 calls them out as not currently required).

Phase 26 — KR foundations. Added `config/viza_concepts.json` (SKOS concept scheme), `config/viza_command_taxonomy.json`, `config/viza_command_conflicts.json`, and `config/viza_command_language_gate.json`. Added `viza/concepts.py` with `ConceptScheme.resolve`, `family_expansion`, and `broader_closure` / `narrower_closure`. Migrated `viza/relationships.py:_expand_family_aliases` from a hardcoded dict to a concept-scheme lookup with a graceful identity-fallback when the scheme is unavailable. Added `ProvAttribution` to `viza/file_format/models.py:VizaFileManifest` for PROV-shaped manifest provenance. 13 dedicated tests in `tests/unit/test_viza_concepts.py`.

Phase 27 — Investment Commands MVP. New `viza/commands.py` with `InvestmentCommandPayload` (three-kind / four-axis decomposition: PositionCommand × Direction × PositionChange × Side × SizingMethod, plus AttentionCommand and SystemCommand kinds), `CommandTarget` carrying nullable FIBO IRIs, `SizingExpression`, `CommandMapping`, `Defeater`, taxonomy + conflicts loaders. New `viza/feel_lite.py` — safe `ast`-based expression evaluator for sizing expressions (Phase 29 extended it to S-FEEL coverage). New `viza/radar.py` with `RadarItem`, `OutputRadarConfig`, `OutputRadarView`, `decision_frame_to_radar_item`, `ranking_result_to_radar_item`, `assemble_output_radar` supporting three modes (`ranking_only` / `decisions_only` / `mixed`) and two hit policies (`COLLECT`, `QUOTA_THEN_SCORE`). Extended `viza/decisions.py` with `DecisionProvenance` (PROV-shaped, supersedes `DecisionAudit` while keeping the back-compat alias), `DecisionFrame.command` / `provenance` / `argumentation_status`, and rights-blocked-observation handling that swaps emit to `BLOCK_EXPORT`. Idempotent SQLite migration `_migrate_phase_27_command_columns`. Extended `viza/decisions_redaction.py` (white_box / output_only / marketplace_draft now respect command axes), `viza/decisions_backtesting.py` (BacktestReport.by_command_axis), and `viza/validation_ledger.py` outputs (command_iri + argumentation_status per decision). 41 new tests across `test_viza_commands.py`, `test_viza_decisions_commands.py`, `test_viza_radar.py`.

Phase 28 — Bitemporal observation store. Added `valid_time_start/end` and `transaction_time_start/end` columns to `observations`, with idempotent migration backfilling from `observed_at` / `retrieved_at`. `ObservationStore.correct_observation` is the append-only correction primitive — it closes the prior row's `transaction_time_end` and inserts a new row instead of overwriting. `get_as_of_transaction_time` / `get_as_of_valid_time` helpers implement the canonical bitemporal AS-OF predicates. `compile_decisions(transaction_time_cutoff=…)` filters observations by the AS-OF transaction time, defaulting to "current belief" (`transaction_time_end IS NULL`). 10 new tests across `test_viza_observations_bitemporal.py` and `test_viza_decisions_bitemporal.py`. The headline exit criterion — a backtest at a past run_id reproduces its commands even after intervening corrections — is verified.

Phase 29 — DMN FEEL-S triggers + sizing + action-threshold decision table. Extended `viza/feel_lite.py` with S-FEEL capabilities: `in` / `not in` operators, list literals, ISO-8601 `date(...)` / `duration(...)` / `days(start, end)` / `now()` built-ins. `DecisionTrigger.feel_expression` field (with a `referenced_attribute_keys` helper that keeps cooldown / dead-band bookkeeping correct against FEEL-only rules). New `viza/decision_tables.py` with `DecisionTable`, `DecisionTableRule`, six hit policies (UNIQUE / ANY / PRIORITY / FIRST / COLLECT / RULE_ORDER), and `action_threshold_table_from_dict` for migrating legacy `action_thresholds` dicts. `config/viza_bkm_registry.json` carries five indicator BKMs (rsi_14, volume_spike, momentum_21, moving_average_trend, realized_volatility_20). New `viza/dmn_export.py` emits DMN 1.5 XML with `<inputData>` / `<decision>` / `<businessKnowledgeModel>` plus VIZA-specific `<extensionElements>` for command-mapping metadata. 21 new tests in `test_viza_phase_29.py`.

Phase 30 — FIBO identity. New `config/viza_fibo_mappings.json` mapping asset classes, identifier schemes, and event types to canonical FIBO IRIs (e.g. US_EQ → fibo-sec-eq:CommonStock, cik → fibo-fbc-fct-ra:SecCikIdentifier, confirmed_mna → fibo-cae-mer:MergerEvent). New `viza/fibo.py` with `FiboMappings`, `FiboIdentity`, `asset_to_fibo_identity`, `default_fibo_identity_resolver`. `VizaAsset` carries four nullable FIBO IRI fields; `apply_fibo_mappings` populates them at read time from the registry so no SQL migration was required. `compile_decisions(fibo_identity_resolver=…)` stamps `CommandTarget.fibo_legal_entity_iri` and `fibo_instrument_iri` when the resolver returns a hit. `EventTypeDefinition.fibo_iri` + `family_concept_iri` added; `viza_event_registry.json` populated for the confirmed-M&A case. 11 new tests in `test_viza_phase_30.py`.

Phase 31 — Argumentation (ASPIC+). New `viza/argumentation.py` with `evaluate_defeaters_for_decision` (handles `evidence_absent`, `time_decay`, `pit_unsafe`, `rights_blocked`, `counter_event` — the last wired in Phase 32), `build_attack_graph` (per-target conflict-registry projection), `apply_preferences` (resolves symmetric attacks by `command_confidence × command_priority`), `compute_grounded_extension` (Dung iterative fixed-point), and `apply_argumentation` as the top-level entry point. Replaces the Phase-27 `_apply_minimal_argumentation` stub. BLOCK_ACTION's wildcard `defeats_unconditionally` edge survives preference resolution; the wildcard does not self-attack. 15 new tests in `test_viza_phase_31.py`.

Phase 32 — Event-pattern grammar. New `viza/event_patterns.py` with a Pydantic-discriminated AST: `EventMatch`, `Sequence` (with ISO-8601 `within` window), `Conjunction` (`all`), `Disjunction` (`any`), `Negation` (`not`), `AllenRelation` (`before` / `after` / `during` / `overlaps` / `meets` / `starts` / `finishes` / `equals` with optional ISO-8601 `tolerance`). Batch evaluator with PIT cutoff filter and entity-scoped matching. `DecisionTrigger.event_pattern` and `InsightTypeDefinition.event_pattern` fields. `compile_decisions(events=…)` threads events through, AND-combining the event-pattern leg with FEEL-expression and observation-predicate legs. `counter_event` defeater is now wired in `argumentation.py` — matches by event_type OR registry FIBO IRI. 21 new tests in `test_viza_phase_32.py`.

Phase 33 — Full PROV graph. New `viza/provenance.py` with `ProvenanceEdge` (subject / predicate / object / generated_at_time / rights_policy_ref / run_id), `ProvenanceStore` (SQLite table with indexes on subject, object, run), and `walk_from(root_iri, max_hops=16)` BFS over outgoing edges. `record_decision_provenance` emits the canonical four-edge set per decision (wasGeneratedBy, wasAttributedTo, used, wasDerivedFrom). `record_run_bundle` promotes the run to a first-class `prov:Activity` with `viza:bundle/run/<id> hadMember decision-…` edges. `emit_and_persist_decisions` now writes PROV edges in lockstep with the DecisionStore upsert; idempotency via content-addressed edge IDs. 7 new tests in `test_viza_phase_33.py`.

Phase 34 — Desktop UI for commands + language gate. Added `src/features/decisions/radarTypes.ts` mirroring the Phase 27 Pydantic schemas. Three new TSX components (`DecisionCommandCard`, `BlockedCommandCard`, `WatchCommandCard`), each with a `displayName` on the language-gate whitelist. `RadarItemList` dispatches a `RadarItem[]` to the right card per its `render_component` discriminator. `RadarModeSelector` lets users pick between `ranking_only` / `decisions_only` / `mixed`. New `test/commandLanguageGate.test.mjs` statically scans the desktop source tree: command words (BUY_TO_OPEN, etc.) may appear only in whitelisted files; always-blocked phrases ("act now", "buy AAPL now", …) must appear nowhere. 4 new desktop tests.

Phase 35 — Engine HTTP API. Added `GET /viza/commands/taxonomy`, `GET /viza/commands/conflicts`, `POST /viza/radar/assemble` (accepts decisions + ranking rows + OutputRadarConfig and returns the assembled view), `GET /viza/provenance/walk?root_iri=…`, and `GET /viza/strategy-profiles/{id}/dmn-export`. 7 new tests in `test_viza_phase_35.py` driving the endpoints end-to-end through `TestClient(app)`.

Phase 36 — Smoke + package readiness. Extended `apps/viza-desktop/scripts/smokePackage.mjs` to assert every Phase 26-33 module and config file is present in `release/win-unpacked/resources/engine/`. The smoke script intentionally fails against a stale package — a fresh `npm run package:win` is the contract for picking up the new files. The `electron-builder.yml` filter `viza_*.json` already covers the four new config files; `viza/` is unfiltered so all new Python modules are packaged.

Verification:

```powershell
python -m pytest tests\unit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed on 2026-05-21 with 617 Python unit tests (the lookahead-audit suite was not re-run in this batch — it ran clean on 2026-05-13 and no `event_time` / `ingestion_time` / `timestamp_available` discipline was touched), TypeScript typecheck clean, and 46 desktop helper tests (including the new four-test language-gate suite). A fresh `npm run package:win` + `npm run smoke:package` is the natural next step for end-to-end packaging verification; this was not run in-session because the existing `release/win-unpacked` predates the work and the rebuild path requires a clean signing-aware preflight environment.

Architectural posture after Phases 26–36: every load-bearing discipline from `docs/viza_end_product/VIZA_KR_COMPLIANCE_REPORT.md` is now structurally backed in source — SKOS taxonomies, FIBO IRIs, PROV provenance, DMN FEEL-S + decision tables, bitemporal observation discipline, ASPIC+ argumentation, batch CEP. The Rete / streaming-CEP / AGM deferrals from the compliance report §9 remain in effect; the existing indexes plus argumentation grounded-extension are sufficient for the current rule-count and data-volume regime. The Phase 27 user-visible feature (Investment Commands MVP) is now fully wired end-to-end on the engine side and rendered by three dedicated cards on the desktop side; the language gate prevents a future UI edit from leaking command words outside the simulation/live cards.
