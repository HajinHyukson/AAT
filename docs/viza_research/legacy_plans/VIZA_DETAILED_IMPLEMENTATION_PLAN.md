# VIZA Detailed Implementation Plan

Last updated: 2026-05-12

## Purpose

This document expands `docs/VIZA_PROTOTYPE_PLAN.md` into implementation-sized pieces. It is meant to be detailed enough that an engineer can pick up a phase, understand the expected behavior, identify the relevant subsystems, and know what tests prove the work is complete.

The implementation target is the product direction in `docs/VIZA_PRODUCT_SPEC.md`:

```text
Blank Canvas -> Methodology Graph -> Engine Run -> Radar Output -> Relationship View -> Save/Load
```

The current prototype has already proven much of the first loop. The remaining work is to turn that loop from a convincing prototype into a robust local-first research product.

## Current Baseline

As of 2026-05-12, the repo contains:

- Electron desktop workspace under `apps/viza-desktop/`.
- React/TypeScript canvas using React Flow.
- Python VIZA package under `viza/`.
- Starter attribute registry at `config/viza_attribute_registry.json`.
- Local universe definitions at `config/mvp_universe.json` and `config/pilot_sp500_universe.json`.
- Sample methodology fixture at `tests/fixtures/viza/residual_momentum_event_radar.json`.
- Local FastAPI engine in `viza/service.py`.
- Prototype execution in `viza/execution.py`.
- Windows unpacked development build at `apps/viza-desktop/release/win-unpacked/VIZA.exe`.

The prototype can:

- Open to a blank methodology canvas.
- Add Universe, Attribute, Transform, Filter, Score, Output Radar, and Relationship nodes.
- Connect nodes visually.
- Configure nodes in a right inspector.
- Save and load `viza_graph_v0` JSON files.
- Call a local Python service.
- Return ranked radar rows.
- Render a company-centered relationship view.
- Show warnings and evidence references.
- Package a Windows development build.

The most important current limitations are:

- Most research attributes are deterministic prototype values, not real AAT-backed values.
- Graph execution does not yet compile the edge topology into a true execution plan.
- The packaged app still depends on system Python.
- Engine autostart uses a fixed local port.
- There is no connector, entitlement, credential, project-store, scheduler, backtest, or production-grade audit layer yet.

## Significant Implementation Pieces

VIZA should be built as a set of coordinated workstreams. Phases below group these workstreams into useful delivery slices, but the workstreams themselves should stay conceptually separate.

| Piece | Responsibility | Main Code Areas |
|---|---|---|
| Desktop shell | App window, packaging, engine lifecycle, native dialogs, local paths, credentials later. | `apps/viza-desktop/electron/`, `electron-builder.yml` |
| Canvas UI | Node palette, graph editing, inspector, user workflow, result panels. | `apps/viza-desktop/src/` |
| Graph contract | Durable methodology JSON, node/edge types, schema validation, migrations. | `viza/graph_schema.py`, `src/vizaGraph.ts` |
| Attribute registry | Searchable attribute catalog, metadata, source policies, transform compatibility. | `viza/attribute_registry.py`, `config/viza_attribute_registry.json`, UI registry state |
| Execution runtime | Graph validation, execution plan compilation, node execution, warnings, manifests. | `viza/execution.py`, future `viza/runtime/` |
| Data access | Local universes, AAT database, public data, paid APIs, caching, lineage. | `viza/universes.py`, `adapters/`, `db/`, future connector layer |
| Relationship engine | Relationship edge generation, graph queries, evidence, path search, clusters. | `viza/execution.py` now, future `viza/relationships/` |
| Radar/output system | Ranked tables, output columns, filters, saved radars, watchlists, exports. | Result panel UI, future project store |
| Audit/reproducibility | Run manifests, data versions, graph versions, timestamp cutoff, evidence trail. | `viza/execution.py`, DB/project store, tests |
| Testing/release | Unit tests, desktop tests, packaged smoke tests, look-ahead tests, release checklist. | `tests/`, `apps/viza-desktop/test/`, future Playwright/Electron smoke |

## Phase 0: Product And Repository Foundation

Status: implemented for the prototype, but keep this phase as the baseline contract for all future work.

### Goal

Create the VIZA workspace and contracts without disrupting the existing AAT attribution/backfill system.

### Scope

- Keep VIZA desktop code isolated under `apps/viza-desktop/`.
- Keep VIZA Python bridge/runtime code isolated under `viza/`.
- Keep starter config under `config/`.
- Keep VIZA docs under `docs/`.
- Reuse existing AAT engine modules only through explicit integration points.
- Avoid schema, loader, and backfill changes unless a later phase explicitly requires them.

### Implementation Details

- Define `viza_graph_v0` as the durable prototype graph format.
- Mirror graph schema in Python and TypeScript.
- Define node type enum:
  - `universe`
  - `attribute`
  - `transform`
  - `filter`
  - `score`
  - `relationship`
  - `output_radar`
- Define edge type enum:
  - `data_flow`
  - `relationship`
  - `evidence`
- Define minimal node fields:
  - `id`
  - `type`
  - `position`
  - `label`
  - `config`
- Define minimal edge fields:
  - `id`
  - `source`
  - `target`
  - `type`
  - `config`
- Add schema validation:
  - reject unsupported schema versions,
  - reject duplicate node IDs,
  - reject duplicate edge IDs,
  - reject edges pointing at missing nodes,
  - reject self-referential edges,
  - reject `updated_at < created_at`.
- Add a sample graph fixture that exercises the intended demo story.
- Add a starter attribute registry with enough metadata for the first UI and execution loop.

### Deliverables

- `apps/viza-desktop/README.md`.
- `viza/graph_schema.py`.
- `viza/attribute_registry.py`.
- `config/viza_attribute_registry.json`.
- `tests/fixtures/viza/residual_momentum_event_radar.json`.
- Unit tests for graph and registry validation.

### Acceptance Criteria

- Sample methodology graph validates in Python.
- Registry loads with at least 20 starter attributes.
- Sample graph attribute keys exist in the registry.
- No active AAT backfill path changes.
- Existing AAT tests remain green.

### Verification

```powershell
python -m pytest tests\unit\test_viza_graph_schema.py tests\unit\test_viza_attribute_registry.py
```

## Phase 1: Methodology Canvas Foundation

Status: implemented for the prototype; next work is UX hardening and graph semantics.

### Goal

Make the first screen feel like VIZA: a blank research-methodology canvas where the user builds logic through nodes and edges.

### Scope

- Render an empty canvas as the first screen.
- Provide a left tool rail with node creation actions.
- Provide a right inspector for selected node configuration.
- Support visual graph editing and local methodology file round-trips.
- Keep output tables and relationship views secondary to the graph-building experience.

### Implementation Details

#### Canvas Shell

- Use React Flow as the node/edge canvas.
- Fit the canvas to the available workspace.
- Provide zoom, pan, minimap, and controls.
- Use stable node dimensions so labels and status indicators do not shift layout.
- Keep the app layout as:
  - left tool rail,
  - center canvas and results,
  - right inspector.

#### Node Creation

- Add toolbar buttons for every prototype node type.
- Create each node with:
  - generated ID based on type,
  - type-specific default config,
  - readable label,
  - deterministic initial position offset from existing nodes.
- Clear previous run result after graph mutation.

#### Edge Creation

- Support dragging from source handle to target handle.
- Infer edge type from source and target node types:
  - output-to-relationship becomes `relationship`,
  - most other connections become `data_flow`.
- Give relationship edges a distinct visual style.
- Preserve edge type in saved graph JSON.

#### Inspector

- Universe inspector:
  - universe selector,
  - universe version,
  - ticker subset.
- Attribute inspector:
  - attribute selector,
  - lookback days,
  - missing-data behavior.
- Transform inspector:
  - transform type,
  - direction.
- Filter inspector:
  - attribute key,
  - operator,
  - value.
- Score inspector:
  - scoring method,
  - weights per discovered attribute node,
  - missing-data scoring behavior.
- Output Radar inspector:
  - top N,
  - sort direction,
  - output columns.
- Relationship inspector:
  - relationship families.

#### Save/Load

- In Electron:
  - use native save/open dialogs through preload bridge,
  - default save path to `Documents/VIZA Methodologies`,
  - save formatted JSON with newline.
- In browser dev mode:
  - use file download/upload fallback.
- On load:
  - parse and validate basic JSON shape in the UI,
  - convert graph nodes to React Flow nodes,
  - convert graph edges to React Flow edges,
  - restore methodology ID, name, timestamps, nodes, and edges.

### Next UX Hardening

- Add real drag/drop from toolbar instead of click-to-add only.
- Add node duplication and delete keyboard shortcuts.
- Add multi-select.
- Add grouping and annotations.
- Add visual status badges for:
  - not configured,
  - ready,
  - running,
  - completed,
  - warning,
  - failed.
- Add edge compatibility preview before the connection is committed.
- Add invalid-edge messages without waiting for execution.
- Add graph templates:
  - Residual Momentum Event Radar,
  - Sector Relative Momentum,
  - Event Materiality Watchlist.
- Add graph dirty-state tracking.

### Deliverables

- Canvas route/page as the default app view.
- Node palette for prototype nodes.
- Node components with handles.
- Inspector components for every prototype node.
- Save/load bridge and browser fallback.
- Round-trip conversion functions between UI graph and persisted graph.

### Acceptance Criteria

- User can open a blank canvas.
- User can add every prototype node type.
- User can connect nodes.
- User can configure nodes.
- User can save graph JSON.
- User can load graph JSON and recover nodes/edges/configs.
- Loaded graph can be run without manual repair.

### Verification

```powershell
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Future verification:

- Add Playwright/Electron test that builds, saves, reloads, and reruns a graph.

## Phase 2: Local Engine Bridge

Status: implemented for prototype; next work is lifecycle and security hardening.

### Goal

Connect the desktop canvas to executable Python logic through a local service or IPC layer.

### Scope

- Provide local engine endpoints.
- Allow the UI to fetch metadata.
- Allow the UI to execute methodology graphs.
- Return structured warnings instead of crashing on user-authored graph problems.
- Keep this service independent from the old AAT web dashboard.

### Implementation Details

#### FastAPI Service

Current endpoints:

- `GET /health`
  - returns service health.
- `GET /viza/runtime`
  - returns runtime mode,
  - declares whether database is required,
  - lists data sources used by the prototype.
- `GET /viza/attributes`
  - returns the full attribute registry.
- `GET /viza/universes`
  - returns local universe summaries.
- `POST /viza/execute`
  - accepts `viza_graph_v0`,
  - validates graph shape,
  - executes graph,
  - returns result payload.

#### UI Client

- Centralize engine URL configuration.
- Fetch attributes and universes when the app starts.
- Show engine state:
  - checking,
  - online,
  - offline.
- On run:
  - serialize the current canvas to graph JSON,
  - post to `/viza/execute`,
  - display status, row count, relationship count, warnings, evidence.

#### Electron Lifecycle

- Development mode:
  - app can call manually started `npm run dev:engine`,
  - Electron dev shell can autostart the Python service.
- Packaged mode:
  - engine root resolves from `process.resourcesPath/engine`,
  - Python path includes packaged engine first,
  - service starts without old web dashboard.

### Required Hardening

- Replace fixed port behavior with dynamic port allocation.
- Pass the selected engine base URL from Electron main process to renderer.
- Add health wait with clear timeout messaging.
- Detect when port is in use by another VIZA instance.
- Avoid starting duplicate engine processes.
- Add a per-session local token:
  - generated by Electron main process,
  - passed to engine as env var,
  - sent by renderer in request header,
  - rejected by engine when missing or wrong.
- Tighten CORS to expected local origins in dev and local token in production.
- Surface engine logs or log location in a diagnostics panel.
- Ensure app shutdown terminates the child engine process.

### Deliverables

- `viza/service.py` endpoints.
- `apps/viza-desktop/src/vizaEngineClient.ts`.
- Electron engine startup in `electron/main.cjs`.
- Desktop path helpers in `electron/desktopPaths.cjs`.
- Desktop status IPC endpoint.

### Acceptance Criteria

- UI fetches attributes and universes from the local engine.
- UI can execute a methodology graph.
- Engine failure is visible as an app state, not a blank or frozen screen.
- Packaged app can start the local service without manually starting the old dashboard.
- Port conflict is handled deterministically.

### Verification

```powershell
python -m pytest tests\unit\test_viza_service.py
cd apps\viza-desktop
npm run test:desktop
```

Future verification:

- Add packaged engine autostart test on a random port.
- Add port conflict test.
- Add invalid local token test.

## Phase 3: Executable Methodology Runtime

Status: prototype implementation exists; product runtime still needs a real graph compiler.

### Goal

Turn user-authored methodology graphs into deterministic execution plans.

### Current Prototype Behavior

The current runtime:

- validates required node types,
- resolves a universe,
- reads requested attribute keys,
- materializes local/prototype values,
- applies one transform policy,
- applies filters,
- computes scores,
- builds radar rows,
- builds relationship edges,
- returns warnings and evidence.

This is enough for the prototype loop but not enough for final VIZA, because execution does not yet truly follow the graph topology.

### Required Runtime Architecture

#### Graph Compiler

Add a compiler that converts `MethodologyGraph` into an execution plan.

Compiler responsibilities:

- Identify connected components.
- Find executable paths from Universe nodes to Output nodes.
- Reject cycles in data-flow edges.
- Type-check source and target ports.
- Enforce that required inputs exist.
- Respect edge topology and node ordering.
- Detect disconnected nodes and return warnings.
- Detect unreachable output nodes.
- Detect ambiguous multiple upstream universes.
- Detect unsupported node configs.
- Emit ordered node execution steps.

#### Node Execution Contract

Every node executor should return:

- `node_id`
- `node_type`
- `status`
- `output_ref`
- `warnings`
- `evidence_refs`
- `diagnostics`
- `started_at`
- `finished_at`

Statuses:

- `pending`
- `running`
- `completed`
- `completed_with_warnings`
- `skipped`
- `failed`

#### Runtime Context

The execution context should include:

- `run_id`
- `methodology_id`
- graph hash,
- methodology version,
- timestamp cutoff,
- selected universe,
- connector state,
- registry version,
- execution mode,
- cache policy,
- request user/settings context.

#### Intermediate Data Model

Use a table-like in-memory representation for the prototype:

- rows keyed by security/ticker/entity ID,
- columns keyed by attribute key or transform output key,
- metadata per column,
- warnings per row and per column,
- evidence refs per cell.

Later, back this with DuckDB or Arrow/Polars for larger universes.

### Node Execution Details

#### Universe Node

Inputs:

- none for prototype,
- later may accept upstream filters or data source nodes.

Config:

- `universe_name`
- `universe_version`
- `ticker_subset`
- `as_of`
- `timestamp_cutoff`

Execution:

- load universe definition,
- apply version and cutoff,
- apply ticker subset,
- return entity set.

Warnings:

- unknown universe,
- version not found,
- empty universe,
- subset tickers missing,
- stale universe,
- unavailable due to entitlement.

#### Attribute Node

Inputs:

- universe/entity set.

Config:

- `attribute_key`
- `lookback_days`
- `missing_data`
- optional source override,
- optional timestamp cutoff override.

Execution:

- look up registry definition,
- resolve data source,
- fetch values for each entity,
- attach source and evidence metadata,
- preserve missing values with reason codes.

Warnings:

- unknown attribute key,
- source unavailable,
- insufficient history,
- not point-in-time safe,
- entitlement denied,
- stale data,
- unsupported transform.

#### Transform Node

Inputs:

- one or more numeric attribute columns.

Config:

- `transform`
- `direction`
- transform-specific params.

Supported prototype transforms:

- percentile rank,
- z-score,
- absolute-value rank,
- trailing average,
- change over period,
- boolean threshold.

Execution:

- validate compatible units,
- compute transformed columns,
- retain source lineage to input columns,
- emit transform diagnostics.

Warnings:

- non-numeric input,
- too few observations,
- all values missing,
- constant column,
- unsupported transform.

#### Filter Node

Inputs:

- entity table.

Config:

- `attribute_key`
- `operator`
- `value`
- optional `min_value`
- optional `max_value`

Operators:

- `is_available`
- `greater_than`
- `less_than`
- `between`
- `equals`
- `sector_equals`
- `industry_equals`
- `ticker_in`

Execution:

- evaluate predicate row by row,
- preserve count before/after,
- produce dropped-row diagnostics.

Warnings:

- filter removed all rows,
- filter attribute missing,
- incompatible operator/unit.

#### Score Node

Inputs:

- transformed or raw numeric attributes.

Config:

- `method`
- `weights`
- `missing_data`

Methods:

- weighted sum,
- average rank.

Missing policies:

- renormalize available weights,
- require all inputs,
- penalize missing.

Execution:

- validate score inputs are numeric,
- normalize weights,
- compute score,
- attach row warnings for missing inputs,
- preserve score formula in evidence.

Warnings:

- no scoreable attributes,
- no scoreable rows,
- unknown weight key,
- non-positive weights.

#### Output Radar Node

Inputs:

- scored entity table.

Config:

- `top_n`
- `sort`
- `columns`
- evidence fields.

Execution:

- sort rows,
- select top N,
- project requested columns,
- assign rank,
- attach row evidence refs.

Warnings:

- unknown output columns,
- zero output rows,
- truncated result set.

#### Relationship Node

Inputs:

- radar output rows and entity table.

Config:

- relationship families,
- optional max edges,
- optional min strength,
- optional evidence-only flag.

Execution:

- generate requested relationships,
- filter by selected output rows,
- attach evidence refs and weights.

Warnings:

- relationship family unavailable,
- no edges generated,
- peer data missing,
- source lineage incomplete.

### Result Payload Contract

Promote the current result payload toward:

```json
{
  "run_id": "uuid",
  "methodology_id": "uuid",
  "graph_hash": "sha256",
  "status": "completed",
  "timestamp_cutoff": "2026-05-12T00:00:00Z",
  "rows": [],
  "relationships": [],
  "warnings": [],
  "node_results": [],
  "evidence": {},
  "manifest": {}
}
```

### Deliverables

- Graph compiler module.
- Node executor registry.
- Runtime context model.
- Node result model.
- Run manifest model.
- Updated `/viza/execute` payload.
- UI display for node-level status.

### Acceptance Criteria

- Output changes when graph topology changes.
- Disconnected attribute nodes do not silently affect scores.
- Invalid edges are caught before execution where possible.
- Node warnings are associated with the node that caused them.
- Result includes a deterministic graph hash and run manifest.

### Verification

- Unit tests for compiler order.
- Unit tests for invalid graph shapes.
- Unit tests for every node executor.
- Regression test using the sample radar graph.
- UI test that shows node statuses after run.

## Phase 4: First Data-Backed Radar

Status: prototype radar exists; this phase replaces fake values with real data where available.

### Goal

Make the first VIZA radar analytically credible by replacing deterministic prototype feature values with AAT-backed or source-backed values.

### Scope

The first data-backed radar should still be narrow:

- equity universe only,
- starter attributes only,
- local-first execution,
- clear missing-data warnings,
- no institutional connectors required.

### Attribute Priority

#### Tier 1: Already Native To AAT

Attributes:

- `observed_return_bps`
- `unexplained_residual_bps`
- `residual_share_stable`
- `french_market_contribution_bps`
- `french_smb_contribution_bps`
- `french_hml_contribution_bps`
- `french_rmw_contribution_bps`
- `french_cma_contribution_bps`
- `run_status`

Implementation:

- Read latest eligible `attribution_run`.
- Read associated `attribution_contribution` rows.
- Respect methodology and window.
- Respect `timestamp_available <= cutoff`.
- Preserve contribution stage and evidence payload.
- Return missing state when no run exists.

Workload:

- Medium if current DB is available and stable.
- Large if packaged/offline sample data must also be generated.

#### Tier 2: Universe And Classification

Attributes:

- `sector`
- `industry`
- `latest_price`
- `price_bar_count`

Implementation:

- Use local universe files for prototype.
- Use DB-backed security and price data when available.
- Move toward `sector_classification_history` for point-in-time history.
- Flag current-snapshot classification when used for historical analysis.

Workload:

- Small to medium for current snapshot.
- Medium to large for point-in-time classification history.

#### Tier 3: Return Style Descriptors

Attributes:

- `momentum`
- `short_term_reversal`
- `realized_volatility`
- `liquidity`

Implementation:

- Use `engine/factors/style_model.py`.
- Load visible price bars through cutoff.
- Respect lookback config.
- Return descriptor value, unit, confidence, observations, and model version.
- Return missing when price history is insufficient.

Workload:

- Medium.

#### Tier 4: Event Features

Attributes:

- `event_count`
- `event_materiality`
- `event_novelty`
- event source credibility if added to registry.

Implementation:

- Read visible event and event feature rows.
- Filter by lookback window.
- Aggregate per ticker:
  - count,
  - max materiality,
  - max novelty,
  - max/source-weighted credibility.
- Attach event IDs and evidence spans.
- Keep as evidence-only until event contribution is calibrated.

Workload:

- Medium to large depending on event data availability.

#### Tier 5: Sector, Peer, Macro Contributions

Attributes:

- `sector_contribution_bps`
- `peer_contribution_bps`
- `macro_contribution_bps`

Implementation:

- Wire to existing expanded model modules:
  - `engine/factors/sector_model.py`,
  - `engine/factors/peer_model.py`,
  - `engine/factors/macro_model.py`.
- Use point-in-time classification and peer-basket definitions.
- Use `macro_series` for macro moves.
- Apply confidence penalties.
- Store or expose contribution evidence payloads.

Workload:

- Large.

### Data Access Strategy

Use a layered adapter:

1. Local config/sample data.
2. Local AAT database.
3. Public adapters.
4. Paid API connectors.

Every attribute fetch should return:

- value,
- unit,
- source,
- source record ID or file reference,
- event time,
- timestamp available,
- data version,
- model version,
- contribution stage,
- confidence,
- diagnostics,
- missing reason.

### Deliverables

- Attribute value resolver interface.
- DB-backed resolver for attribution fields.
- Price-bar resolver for style descriptors.
- Event-feature resolver.
- Missing-data reason model.
- Updated evidence payloads.
- Tests proving values are no longer prototype hashes for supported data.

### Acceptance Criteria

- The demo graph still runs.
- Rows are generated from real local/AAT data where available.
- Every fake/prototype fallback is explicitly labeled.
- Missing data appears as warnings and cell-level evidence, not as crashes.
- Existing prototype behavior still works without a DB by using sample/local data.

### Verification

- Unit tests for each resolver.
- Look-ahead tests for cutoff behavior.
- Snapshot-like expected-result test for sample data.
- Manual packaged run with no database.
- Manual connected run with database.

## Phase 5: Relationship And Evidence Experience

Status: basic company-centered relationship view exists.

### Goal

Turn the relationship panel from a demo visualization into a usable inspection surface for why an asset surfaced.

### Current Behavior

- Selecting a radar row shows a centered company node.
- Relationship edges can include:
  - selected attributes,
  - sector,
  - industry,
  - peers,
  - recent event evidence.
- Clicking graph nodes or edge chips updates evidence detail.

### Required Improvements

#### Relationship Data Model

Each edge should include:

- source ID,
- target ID,
- relationship type,
- relationship family,
- weight,
- direction,
- confidence,
- timestamp available,
- evidence ref,
- source lineage,
- diagnostics.

Each node should include:

- ID,
- label,
- kind,
- family,
- entity metadata,
- evidence refs,
- visible/missing state.

#### Relationship Families

Prototype families:

- company to selected attributes,
- company to sector,
- company to industry,
- company to peers,
- company to recent event evidence.

Next product families:

- company to security,
- company to owner,
- company to supplier,
- company to customer,
- company to macro exposure,
- company to factor,
- attribute to attribute correlation,
- attribute to lagged attribute,
- event co-occurrence,
- shared peer basket,
- common source.

#### UI Improvements

- Add relationship family filters.
- Add edge strength filter.
- Add search within displayed graph.
- Add selected edge detail drawer.
- Add evidence table below the graph.
- Add mini legend for node/edge families.
- Add graph layout stability for more than 18 edges.
- Add "open evidence" actions for source records where available.
- Add empty states for no peer data, no events, no selected attribute relationships.

#### Relationship Engine Improvements

- Separate edge generation from radar execution.
- Add a relationship query API:
  - `POST /viza/relationships/query`.
- Support on-demand expansion from selected node.
- Add max-depth and max-edge controls.
- Add relationship scoring:
  - raw weight,
  - confidence,
  - recency,
  - source quality.

### Deliverables

- Relationship graph data models.
- Relationship query interface.
- Relationship family filters.
- Evidence inspector improvements.
- Tests for edge generation and evidence refs.

### Acceptance Criteria

- Clicking a radar row explains why it surfaced through attributes and peers.
- Edge evidence is always available or explicitly missing.
- Relationship filters update the graph without rerunning the methodology.
- Peer relationships appear when peer data exists.
- Event relationships appear only when event evidence exists.

### Verification

- Unit tests for relationship generation.
- UI test for selecting a radar row and opening evidence.
- Test for no-peer-data behavior.
- Test for no-event-data behavior.

## Phase 6: Packaging And Desktop Runtime Hardening

Status: Windows unpacked development package exists.

### Goal

Make VIZA reliable to launch and run as a local desktop app.

### Current State

The packaged Windows app:

- builds with Electron Builder,
- includes React app,
- includes Electron main/preload,
- copies `viza/` and selected config into `resources/engine`,
- autostarts local engine,
- saves methodologies under Documents.

Limitations:

- system Python dependency,
- fixed engine port,
- generic Electron executable metadata,
- no installer,
- no signing,
- no bundled dependencies,
- no local service token,
- no macOS artifact from Windows.

### Implementation Details

#### Windows Development Package Hardening

- Set product metadata:
  - product name,
  - file description,
  - company name,
  - copyright,
  - product version.
- Add app icon.
- Add installer target after unpacked dir is stable.
- Decide installer format:
  - NSIS for standard installer,
  - MSI only if enterprise deployment needs it.
- Add release folder cleanup rules.
- Add release notes/checklist.

#### Python Runtime Bundling

Preferred options:

1. PyInstaller sidecar for `viza.service`.
2. Embedded Python distribution with vendored wheels.
3. Nuitka/compiled service if PyInstaller is too brittle.

The first production-grade beta should avoid relying on arbitrary system Python.

Bundled runtime must include:

- FastAPI,
- Uvicorn,
- Pydantic,
- any AAT runtime packages needed by data-backed execution,
- local config,
- sample data,
- license files if needed.

#### Engine Lifecycle

- Allocate a free local port.
- Pass port to renderer through IPC or preload.
- Add health wait.
- Add explicit failure state.
- Kill child process on app quit.
- Avoid duplicate child services.
- Write logs under app user data path.
- Add diagnostics view or copyable log path.

#### Security

- Generate local session token.
- Require token for engine requests.
- Do not expose service outside `127.0.0.1`.
- Avoid storing secrets in graph files.
- Prepare for OS credential storage.

#### macOS Development Package

- Build on macOS.
- Produce `dir` target first.
- Validate engine startup.
- Validate save/load path.
- Document system Python limitation until bundled runtime exists.

#### macOS Release Package

- Add Developer ID certificate.
- Enable hardened runtime.
- Notarize and staple.
- Validate Gatekeeper launch.

### Deliverables

- Hardened `electron-builder.yml`.
- Bundled engine sidecar.
- Dynamic engine port IPC.
- Engine token auth.
- Windows installer.
- Packaging smoke script.
- macOS build notes and later macOS artifact.

### Acceptance Criteria

- User can launch VIZA without installing Python.
- Launch succeeds if port `8765` is already in use.
- Engine failures are visible and logged.
- App quits without leaving engine child processes.
- Windows package has VIZA branding.
- Methodology save/load works from a user-writable directory.

### Verification

- Packaged Windows smoke:
  - launch,
  - engine health,
  - runtime metadata,
  - execute sample graph,
  - save methodology,
  - quit,
  - verify no child process remains.
- Port conflict smoke.
- No-system-Python smoke on clean Windows VM.
- macOS smoke once build machine exists.

## Phase 7: Attribute Registry V1 And Searchable Attribute UX

Status: implemented for the prototype registry and desktop picker; next work is scaling the catalog and adding real connector-backed entitlement checks.

### Goal

Make the registry capable of scaling from 20-40 prototype attributes to hundreds or thousands of production/research attributes.

### Schema Upgrade

Promote `viza_attribute_registry_v0` to `viza_attribute_registry_v1`.

Add fields:

- `registry_version`
- `key`
- `display_name`
- `description`
- `family`
- `unit`
- `source`
- `source_type`
- `frequency`
- `coverage`
- `coverage_universe`
- `freshness`
- `timestamp_policy`
- `point_in_time_status`
- `license_policy`
- `entitlement_policy`
- `cache_policy`
- `production_scoring_allowed`
- `evidence_only`
- `contribution_stage`
- `allowed_transforms`
- `compatible_node_types`
- `availability_function`
- `diagnostics`
- `limitations`
- `owner`
- `model_version`
- `data_version`
- `deprecation_status`

### UI Improvements

- Replace simple dropdown with searchable attribute picker.
- Support filters:
  - family,
  - source,
  - unit,
  - point-in-time status,
  - contribution stage,
  - entitlement status,
  - production/evidence-only.
- Show attribute detail panel:
  - description,
  - coverage,
  - freshness,
  - source,
  - license policy,
  - allowed transforms,
  - limitations.
- Add recently used attributes.
- Add favorite/pinned attributes.
- Add unavailable/locked state with explanation.

### Runtime Improvements

- Validate transform compatibility from registry metadata.
- Validate scoring eligibility.
- Validate evidence-only attributes are not silently used as production scoring inputs unless user config permits it.
- Return clear warnings for entitlement or source limitations.

### Deliverables

- Registry V1 schema and migration loader.
- Searchable attribute picker.
- Attribute detail UI.
- Runtime validation using registry metadata.
- Tests for registry validation and compatibility.

### Acceptance Criteria

- User can find attributes quickly by search and filter.
- Attribute node selection explains source, units, freshness, and restrictions.
- Runtime rejects or warns for incompatible transforms.
- Evidence-only attributes are visibly marked.

## Phase 8: Data Source And Entitlement Layer

Status: implemented for the first local-first connector and entitlement layer; next work is real connector configuration UI, credential storage backends, and production source readers.

### Goal

Let users connect entitled data sources and make source rights a first-class runtime constraint.

### Connector Types

Prototype-to-beta order:

1. Local CSV.
2. Local parquet.
3. Local SQLite/DuckDB.
4. Existing AAT Postgres.
5. Kenneth French public data.
6. SEC EDGAR public data.
7. FRED public data.
8. FMP paid API.
9. Institutional connectors later.

### Connector Interface

Each connector should implement:

- `connector_id`
- `display_name`
- `source_type`
- `credential_requirements`
- `test_connection`
- `list_fields`
- `preview`
- `read_window`
- `read_latest`
- `get_lineage`
- `get_license_policy`
- `get_cache_policy`
- `explain_missing`

### Entitlement Model

Track rights at source, field, and derived-output levels:

- query allowed,
- local cache allowed,
- raw snapshot allowed,
- derived value allowed,
- export allowed,
- redistribution allowed,
- expires at,
- attribution required,
- user credential required,
- organization credential required.

### Credential Storage

- Use OS credential storage:
  - Windows Credential Manager,
  - macOS Keychain.
- Never store secrets in methodology JSON.
- Redact secrets in logs.
- Include credential test status in connector settings.

### Missing Data Explanations

Every missing value should explain:

- missing source,
- missing field,
- no entitlement,
- no coverage,
- not point-in-time visible,
- stale data,
- parser failure,
- connector unavailable.

### Deliverables

- Connector base classes/interfaces.
- Local file connector.
- AAT DB connector.
- Public source connector skeletons.
- Entitlement policy model.
- Credential storage wrapper.
- Connector settings UI.

### Acceptance Criteria

- User can connect a local data source.
- Runtime can explain missing data by source and entitlement status.
- Secrets are not persisted in graph files.
- Export behavior respects source policy.
- Connector failures do not crash graph execution.

## Phase 9: Local Project Store And Methodology Versioning

Status: implemented for a local SQLite project store and desktop version-history workflow; next work is richer project management, persistent run records, and visual graph diffing.

### Goal

Move beyond standalone graph files into local projects, while keeping methodology JSON portable.

### Storage Strategy

Use local SQLite or DuckDB for:

- projects,
- methodology versions,
- run records,
- run manifests,
- saved radar outputs,
- cached allowed data,
- connector settings metadata,
- user settings,
- watchlists,
- alerts later.

Keep `.viza.json` as:

- portable methodology exchange format,
- import/export surface,
- backup-friendly artifact.

### Methodology Versioning

Each save should produce:

- methodology ID,
- version ID,
- graph hash,
- parent version ID,
- created at,
- updated at,
- user label/message,
- schema version.

Add UI support for:

- version history,
- clone version,
- compare versions,
- revert by creating a new version from an old version.

### Deliverables

- Local project DB schema.
- Project open/create flow.
- Methodology import/export.
- Version history UI.
- Version compare data model.

### Acceptance Criteria

- User can save multiple versions of a methodology.
- User can reopen a project and see prior runs.
- User can export a methodology JSON.
- User can import a methodology JSON into a project.
- Version compare shows changed nodes, edges, and configs.

## Phase 10: Audit, Evidence, And Reproducibility

Status: implemented for normalized evidence, run manifests, result checksums, persisted run records, and reproduce-run comparisons; next work is richer evidence drilldowns and full source-data reproducibility.

### Goal

Make every VIZA output reproducible and inspectable.

### Run Manifest

Every run should store:

- run ID,
- methodology ID,
- methodology version ID,
- graph schema version,
- graph hash,
- runtime version,
- registry version,
- timestamp cutoff,
- run started/finished timestamps,
- connector states,
- entitlement states,
- data versions,
- model versions,
- universe version,
- node execution statuses,
- warnings,
- result checksum.

### Evidence Contract

Every evidence item should include:

- evidence ref,
- source,
- source record ID,
- source timestamp,
- timestamp available,
- value,
- unit,
- calculation fields,
- model version,
- data version,
- confidence,
- limitations,
- license policy.

### Reproducibility Rules

- Same graph hash plus same data versions should reproduce the same rows, relationships, warnings, and result checksum.
- If data versions changed, the run should say so.
- If connector entitlements changed, the run should say so.
- If a source is query-only and cannot be cached, manifest should record the query fingerprint and policy, not raw restricted data.

### Deliverables

- Run manifest model.
- Evidence model.
- Manifest persistence.
- Evidence inspector upgrade.
- Reproduce-run command/API.

### Acceptance Criteria

- User can inspect why a row ranked where it did.
- User can see which data and model versions were used.
- User can rerun a methodology and compare manifests.
- Missing data and source restrictions are visible in the run.

## Phase 11: Backtesting And Batch Execution

Status: implemented for the first local in-memory batch/backtest runner, point-in-time checks, cache-key diagnostics, persisted historical runs, and desktop batch history view; next work is streaming progress, durable cancellation, and larger-data execution.

### Goal

Let users run methodologies over historical cutoffs and larger universes.

### Batch Execution

Support:

- selected universe,
- ticker subset,
- multiple dates,
- multiple methodology versions,
- result persistence,
- progress reporting,
- cancellation.

### Point-In-Time Backtests

Backtest runner should:

- choose cutoff calendar,
- run graph at each cutoff,
- enforce `timestamp_available <= cutoff`,
- store run manifest per cutoff,
- produce result history,
- compute simple output diagnostics.

### Performance Plan

- Start with Python in-memory execution.
- Move larger table operations to Polars or DuckDB.
- Add intermediate cache keyed by:
  - node ID,
  - graph hash,
  - universe version,
  - timestamp cutoff,
  - attribute version,
  - source version.

### Deliverables

- Batch execution API.
- Backtest node or run mode.
- Progress UI.
- Result history view.
- Cache key model.

### Acceptance Criteria

- User can run one methodology over multiple historical cutoffs.
- Each historical result has a manifest.
- Backtest respects point-in-time rules.
- Long runs show progress and can fail per node without losing all diagnostics.

## Phase 12: Radar Designer, Watchlists, Alerts, And Exports

Status: implemented for the first local research-surface layer: configurable radar display, saved radar outputs, watchlists, local alert definitions, watchlist-specific runs, and entitlement-aware CSV/JSON/manifest/methodology exports; next work is richer alert evaluation, visual radar templates, and export destinations.

### Goal

Turn methodology outputs into reusable research surfaces.

### Radar Designer

Add configurable:

- ranked table,
- column ordering,
- column formatting,
- evidence columns,
- filters,
- grouping,
- sorting,
- scorecards,
- relationship view layout,
- attribution/evidence table panels.

### Saved Radar Outputs

Store:

- radar ID,
- methodology version,
- run ID,
- timestamp cutoff,
- selected columns,
- displayed rows,
- evidence refs,
- result checksum.

### Watchlists

Support:

- watchlist creation from radar output,
- add/remove tickers,
- watchlist-specific methodology runs,
- watchlist history.

### Alerts

Support local alert definitions:

- score crosses threshold,
- rank enters top N,
- attribute missing,
- event materiality above threshold,
- residual above threshold,
- relationship edge appears/disappears.

### Exports

Support:

- CSV export,
- JSON export,
- methodology export,
- run manifest export.

Export must respect entitlement policy.

### Deliverables

- Output designer UI.
- Saved radar model.
- Watchlist model.
- Alert model.
- Export pipeline with entitlement checks.

### Acceptance Criteria

- User can save a radar output.
- User can create a watchlist from results.
- User can define a local alert.
- User can export permitted outputs.
- Restricted source data is blocked or redacted according to policy.

## Phase 13: Production Attribute Expansion

Status: implemented for the first 73-attribute Phase 13 catalog with deterministic prototype resolvers, promotion metadata, entitlement restrictions, and an implementation checklist; next work is replacing prototype values with source-backed resolvers and validation reports.

### Goal

Expand from the 20-40 starter attributes toward a credible analyst-facing attribute library.

### Attribute Expansion Order

#### A: Institutionally Recognizable Baseline

- market contribution,
- sector contribution,
- industry contribution,
- subindustry basket contribution,
- custom peer basket contribution,
- peer residual spread,
- momentum,
- volatility,
- liquidity.

#### B: Macro Attribution

- 2Y yield change,
- 10Y yield change,
- 2s10s curve change,
- dollar index,
- WTI,
- natural gas,
- high-yield spread,
- investment-grade spread,
- VIX,
- inflation expectations.

#### C: Event Intelligence

- event category,
- event subtype,
- event direction,
- event surprise,
- event materiality,
- event relevance,
- event novelty,
- source credibility,
- exposure match,
- evidence span.

#### D: Fundamentals And Exposure Gates

- size,
- value,
- growth,
- quality,
- leverage,
- dividend yield,
- geographic revenue exposure,
- segment revenue exposure,
- customer concentration,
- supplier concentration,
- commodity input exposure,
- interest-rate exposure,
- credit exposure,
- regulatory exposure,
- product-cycle exposure,
- FX exposure.

#### E: Positioning And Options

Only after licensing and timestamp handling are clear:

- short interest,
- days to cover,
- borrow cost,
- ATM implied volatility,
- IV change,
- put-call skew,
- options volume/open interest,
- dealer gamma exposure,
- ETF flow exposure.

### Attribute Promotion Stages

Each attribute moves through:

1. research,
2. evidence-only,
3. shadow,
4. production scoring,
5. production contribution if applicable.

Promotion requires:

- source definition,
- timestamp policy,
- license policy,
- point-in-time test,
- evidence payload,
- confidence rules,
- validation results,
- model/data versioning.

### Deliverables

- Attribute implementation checklist.
- Expanded registry.
- Attribute resolver implementations.
- Attribute validation tests.
- Evidence and confidence payloads.
- Documentation for limitations.

### Acceptance Criteria

- VIZA can expose 40-80 high-signal attributes with clear status.
- Production-scoring attributes are point-in-time safe.
- Evidence-only attributes are clearly marked.
- Attribute limitations are visible to users.

## Phase 14: Product Release Readiness

Status: implemented for prototype release readiness with backend diagnostics, desktop diagnostics/restart controls, package smoke coverage, and a release checklist; remaining work is signed installers, native credential vaults, and a fully bundled engine runtime.

### Goal

Prepare VIZA for a reliable beta/release outside the development machine.

### Required Areas

#### Reliability

- clean install,
- clean uninstall,
- app upgrade,
- project migration,
- crash logging,
- engine restart,
- offline startup,
- corrupted project handling.

#### Security

- local service token,
- secure credential storage,
- log redaction,
- safe connector failure modes,
- least-privilege local file access.

#### Compliance

- source license policy visible,
- export restrictions enforced,
- connector terms documented,
- user-owned credentials separated from app state.

#### Observability

- diagnostics panel,
- app version,
- engine version,
- runtime path,
- project path,
- log path,
- connector status,
- last run status.

#### Documentation

- install guide,
- quickstart,
- methodology file format,
- connector guide,
- packaging notes,
- troubleshooting,
- release checklist.

### Deliverables

- Windows signed installer.
- macOS signed/notarized package.
- Bundled runtime.
- Release checklist.
- User docs.
- Smoke-test automation.

### Acceptance Criteria

- Non-developer user can install and run VIZA.
- App launches without source repo checkout.
- App works without system Python.
- App can run the sample methodology.
- App can save/load methodology files.
- App gives clear recovery path when engine/data/connector fails.

## Cross-Phase Test Strategy

### Always Run For VIZA Changes

```powershell
python -m pytest tests\unit\test_viza_graph_schema.py tests\unit\test_viza_attribute_registry.py tests\unit\test_viza_service.py
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

### Before Runtime/Data Changes

```powershell
python -m pytest tests\unit tests\lookahead_audit
```

### Before Packaging Changes

```powershell
cd apps\viza-desktop
npm run build
npm run package:win
```

Then smoke the packaged executable:

- launch app,
- confirm no blank screen,
- confirm engine health,
- run sample graph,
- save methodology,
- reload methodology,
- quit app,
- confirm engine process exits.

### Required Future Test Additions

- Graph compiler tests.
- Node executor tests.
- Attribute resolver tests.
- Point-in-time data tests for every resolver.
- Connector entitlement tests.
- Packaged app port-conflict test.
- Bundled Python clean-machine test.
- Electron/Playwright canvas workflow test.
- Backtest reproducibility tests.
- Export restriction tests.

## Suggested Delivery Milestones

### Milestone 1: Hardened Prototype

Target:

- robust Windows development package,
- dynamic engine port,
- bundled runtime decision made,
- graph compiler skeleton,
- node status payload,
- current demo preserved.

Expected effort:

- 2-4 weeks.

### Milestone 2: Data-Backed Internal Alpha

Target:

- starter attributes backed by real AAT/local data where possible,
- missing-data reasons,
- run manifest v0,
- evidence inspector v1,
- project store decision made.

Expected effort:

- 6-10 weeks after Milestone 1.

### Milestone 3: Analyst Beta

Target:

- searchable registry,
- local project store,
- saved methodology versions,
- real sector/peer/style/event values,
- relationship filters,
- Windows installer,
- no system Python dependency.

Expected effort:

- 3-5 months after Milestone 1.

### Milestone 4: Product-Grade Research Sandbox

Target:

- connectors and entitlement layer,
- backtests,
- saved radars,
- watchlists,
- alerts,
- macOS package,
- broader attribute library,
- reproducibility guarantees.

Expected effort:

- 9-15 months total, depending on data licensing and connector scope.

## Implementation Principles

- Keep the blank canvas as the first screen.
- Treat graph JSON as a durable contract, not a screenshot.
- Make missing data visible and non-fatal.
- Keep source lineage and timestamp cutoff visible everywhere.
- Do not hide residuals or force narratives onto unexplained moves.
- Promote attributes slowly from research to production.
- Keep licensing and entitlement checks in runtime, not only in docs.
- Prefer local-first behavior, with remote data only through explicit connectors.
- Keep AAT as the analytical engine foundation rather than replacing it.
- Do not disrupt live backfill paths unless a phase explicitly includes that work.
