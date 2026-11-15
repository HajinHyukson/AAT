# VIZA Prototype Plan

Last updated: 2026-05-12

## Objective

Build a downloadable desktop prototype that proves VIZA's core loop:

```text
Blank Canvas -> User-Defined Methodology Graph -> Engine Run -> Radar Output -> Relationship View -> Save/Load
```

The prototype should not try to support every final-product idea. It should prove that a user can visually design a small investment research methodology and execute it over real or locally cached AAT data.

## Prototype Principle

The prototype is successful if it feels like the beginning of a research sandbox, not a repackaged web dashboard.

The first screen should be a blank methodology canvas. The user should create logic by placing and connecting nodes. Tables, charts, and relationship graphs are outputs of that methodology, not the starting point.

## Recommended Stack

Initial recommendation:

- Desktop shell: Tauri or Electron.
- UI: React and TypeScript.
- Canvas: React Flow for the first prototype.
- Engine: existing Python AAT modules exposed through a local FastAPI service or sidecar process.
- Prototype storage: local project files for methodology graphs, plus SQLite or DuckDB for small app metadata if needed.
- Data source: existing local/server AAT database or a small exported sample dataset.

Decision rule:

- Use Tauri if small app size and desktop polish matter most.
- Use Electron if speed of UI development and ecosystem compatibility matter most.

For the first implementation, do not rewrite the analytical engine in C++ or Rust. Keep Python for research logic and use the desktop shell as the product surface.

## Non-Goals For Prototype

- No full Bloomberg/LSEG/FactSet integration.
- No production entitlement system.
- No thousands of attributes.
- No scheduler.
- No cloud sync.
- No multi-user collaboration.
- No complete macOS notarized release unless packaging time allows.
- No replacement of the current AAT backfill system.
- No schema changes that disrupt the active FaustCalc backfill.

## Prototype Workspace

Proposed repo layout:

```text
AAT/
  apps/
    viza-desktop/
      package.json
      src/
      src-tauri/ or electron/
      README.md
  viza/
    __init__.py
    graph_schema.py
    attribute_registry.py
    execution.py
    sample_data.py
  config/
    viza_attribute_registry.json
  docs/
    VIZA_PRODUCT_SPEC.md
    VIZA_PROTOTYPE_PLAN.md
```

Keep the first desktop app isolated under `apps/viza-desktop/`. Keep Python graph execution helpers under `viza/` so they can call existing `engine/`, `db/`, and `jobs/` modules without entangling UI code with attribution internals.

## Methodology Graph Format

The prototype graph should be saved as JSON.

Minimum graph shape:

```json
{
  "schema_version": "viza_graph_v0",
  "methodology_id": "uuid",
  "name": "Quality Momentum Radar",
  "created_at": "2026-05-12T00:00:00Z",
  "updated_at": "2026-05-12T00:00:00Z",
  "nodes": [
    {
      "id": "universe-1",
      "type": "universe",
      "position": {"x": 100, "y": 100},
      "config": {"universe_name": "pilot_sp500_static"}
    }
  ],
  "edges": [
    {
      "id": "edge-1",
      "source": "universe-1",
      "target": "score-1",
      "type": "data_flow"
    }
  ]
}
```

Required node fields:

- `id`
- `type`
- `position`
- `config`

Required edge fields:

- `id`
- `source`
- `target`
- `type`

## Prototype Node Types

### Universe Node

Purpose: choose the asset universe to analyze.

Prototype config:

- universe name,
- universe version,
- optional ticker subset,
- optional date/cutoff.

### Attribute Node

Purpose: select one research attribute.

Prototype config:

- attribute key,
- display name,
- source,
- lookback window if applicable,
- missing-data behavior.

### Transform Node

Purpose: transform an input attribute.

Prototype transforms:

- z-score,
- percentile rank,
- absolute value,
- trailing average,
- change over period,
- boolean threshold.

### Filter Node

Purpose: exclude assets from downstream results.

Prototype filters:

- greater than,
- less than,
- between,
- is available,
- sector equals,
- ticker in list.

### Score Node

Purpose: combine attributes into a ranking score.

Prototype scoring:

- weighted sum,
- average rank,
- require all connected inputs,
- allow missing with penalty.

### Relationship Node

Purpose: request relationship edges for selected result assets.

Prototype relationships:

- company to selected attributes,
- company to sector,
- company to industry,
- company to peers,
- company to recent event evidence.

### Output Radar Node

Purpose: define the output surface.

Prototype output:

- ranked table,
- selected columns,
- top N,
- sort direction,
- evidence fields.

## Prototype Attribute Registry

Start with 20-40 attributes.

Recommended first attributes:

| Key | Family | Description |
|---|---|---|
| `observed_return_bps` | return | Latest observed close-to-close return. |
| `unexplained_residual_bps` | attribution | Latest unexplained residual from AAT. |
| `residual_share_stable` | diagnostics | Whether share-of-move display is stable. |
| `french_market_contribution_bps` | attribution | Latest `Mkt-RF` contribution. |
| `french_smb_contribution_bps` | attribution | Latest `SMB` contribution. |
| `french_hml_contribution_bps` | attribution | Latest `HML` contribution. |
| `french_rmw_contribution_bps` | attribution | Latest `RMW` contribution. |
| `french_cma_contribution_bps` | attribution | Latest `CMA` contribution. |
| `sector` | classification | Current sector label. |
| `industry` | classification | Current industry label. |
| `sector_contribution_bps` | attribution | Latest sector/industry contribution. |
| `peer_contribution_bps` | attribution | Latest peer basket contribution. |
| `macro_contribution_bps` | attribution | Latest macro contribution. |
| `momentum` | style | Return-style momentum descriptor. |
| `short_term_reversal` | style | Short-term reversal descriptor. |
| `realized_volatility` | style | Realized volatility descriptor. |
| `liquidity` | style | Liquidity descriptor. |
| `event_count` | event | Visible event count over a window. |
| `event_materiality` | event | Maximum visible event materiality. |
| `event_novelty` | event | Maximum visible event novelty. |
| `latest_price` | market_data | Latest adjusted close. |
| `price_bar_count` | coverage | Available canonical price bar count. |
| `run_status` | coverage | Whether attribution is available or missing. |

Each registry item should include:

- key,
- display name,
- family,
- unit,
- source,
- availability function,
- point-in-time status,
- contribution stage,
- evidence policy,
- license policy.

## Execution Model

Prototype execution can be simple:

1. Load graph JSON.
2. Validate required node types.
3. Resolve universe.
4. Load all requested attributes for each asset.
5. Apply transforms.
6. Apply filters.
7. Compute score.
8. Generate radar rows.
9. Generate relationship edges for displayed rows.
10. Return result payload to the desktop UI.

The engine should return structured output:

```json
{
  "run_id": "uuid",
  "methodology_id": "uuid",
  "status": "completed",
  "rows": [],
  "relationships": [],
  "warnings": [],
  "evidence": {}
}
```

## Result Payload

Minimum radar row:

```json
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "score": 0.82,
  "rank": 1,
  "attributes": {
    "momentum": 0.91,
    "realized_volatility": 0.33,
    "unexplained_residual_bps": 48.2
  },
  "warnings": [],
  "evidence_refs": ["attr:AAPL:momentum", "run:..."]
}
```

Minimum relationship edge:

```json
{
  "source": "company:AAPL",
  "target": "attribute:momentum",
  "relationship_type": "selected_attribute",
  "weight": 0.91,
  "evidence_ref": "attr:AAPL:momentum"
}
```

## Phase 0: Setup

Goal: create the VIZA prototype workspace without disturbing the active AAT code paths.

Tasks:

- Add `apps/viza-desktop/`.
- Add `viza/` Python package for graph execution.
- Add `config/viza_attribute_registry.json`.
- Add a desktop app README.
- Define graph schema types in Python and TypeScript.
- Add sample methodology graph fixture.

Exit criteria:

- `python -m pytest tests\unit tests\lookahead_audit` still passes.
- A sample graph JSON validates against the schema.
- No live backfill code path is changed.

Status as of 2026-05-12:

- Phase 0 scaffold is in place under `apps/viza-desktop/`, `viza/`, `config/viza_attribute_registry.json`, and `tests/fixtures/viza/`.
- The prototype shell choice is Electron-ready TypeScript for faster canvas iteration.
- `viza_graph_v0` and `viza_attribute_registry_v0` are defined in Python and mirrored in TypeScript.
- The sample "Residual Momentum Event Radar" graph validates against the Python schema.

## Phase 1: Canvas

Goal: make the first screen feel like VIZA.

Tasks:

- Render a blank canvas.
- Add a left toolbar.
- Add node creation for Universe, Attribute, Score, and Output Radar nodes.
- Add edge creation.
- Add node configuration side panel.
- Save graph to local JSON.
- Load graph from local JSON.

Exit criteria:

- A user can build, save, close, reopen, and reload a simple methodology graph.

Status as of 2026-05-12:

- Phase 1 canvas is implemented in `apps/viza-desktop/` with Vite, React, React Flow, and an Electron development shell.
- The first screen is a blank methodology canvas with a left node toolbar and right inspector.
- Users can add Universe, Attribute, Score, and Output Radar nodes, drag edges between handles, configure node fields, and save/load `viza_graph_v0` JSON.
- Electron native file dialogs are available through the preload bridge; browser download/upload fallbacks are available in Vite dev mode.

## Phase 2: Engine Bridge

Goal: connect the canvas to executable Python logic.

Tasks:

- Add local engine service or sidecar command.
- Implement `GET /viza/attributes`.
- Implement `GET /viza/universes`.
- Implement `POST /viza/execute`.
- Convert graph JSON into an execution request.
- Return warnings instead of crashing on unsupported nodes.

Exit criteria:

- The desktop UI can execute a graph and display a structured result payload.

Status as of 2026-05-12:

- Phase 2 engine bridge is implemented as an isolated FastAPI app in `viza/service.py`.
- The local service exposes `GET /viza/attributes`, `GET /viza/universes`, and `POST /viza/execute`.
- Electron development mode autostarts the local Python service; browser development mode can run it with `npm run dev:engine` from `apps/viza-desktop/`.
- The canvas Run button posts the current `viza_graph_v0` payload and displays the returned status, warnings, row count, relationship count, and graph evidence summary.
- Execution is intentionally still a structured stub; Phase 3 will produce real ranked radar rows.

## Phase 3: First Radar

Goal: produce real ranked output from graph-defined logic.

Tasks:

- Implement Universe node execution.
- Implement Attribute node execution for 20-40 starter attributes.
- Implement Transform node execution for percentile rank and z-score.
- Implement Filter node execution.
- Implement Score node weighted sum.
- Implement Output Radar table.
- Show evidence and missing-data warnings.

Exit criteria:

- A user can rank a local universe from a methodology they built on the canvas.
- The output changes when the user changes graph weights or filters.

Status as of 2026-05-12:

- Phase 3 first radar execution is implemented in `viza/execution.py`.
- Universe nodes resolve local universe JSON definitions from `config/mvp_universe.json` and `config/pilot_sp500_universe.json`.
- Attribute nodes materialize starter attributes for companies; classification and coverage fields use local universe/config data, while research metrics use deterministic Phase 3 prototype feature values with evidence warnings.
- Transform nodes support percentile rank, z-score, and absolute-value percentile ranking for score inputs.
- Filter nodes support availability, equality, numeric comparisons, ranges, and ticker lists.
- Score nodes support weighted sum and average-rank scoring.
- Output Radar nodes return ranked rows with configurable top N, sort direction, and display columns.
- Relationship nodes return company-to-attribute, sector, industry, peer, and event-evidence edges.
- The canvas toolbar can create all Phase 3 executable node types.
- The desktop result panel displays the returned radar table, warnings, row counts, relationship counts, and evidence summary.

## Phase 4: Relationship View

Goal: prove the relationship-graph idea.

Tasks:

- Add relationship graph panel beside or below radar results.
- Show company-to-attribute edges for displayed results.
- Show company-to-sector and company-to-industry edges.
- Show company-to-peer edges where peer basket data exists.
- Show edge evidence in an inspector panel.

Exit criteria:

- Clicking a radar row reveals a relationship graph explaining why that asset surfaced.

Status as of 2026-05-12:

- Phase 4 relationship view is implemented in the desktop result panel.
- Selecting a radar row reveals a company-centered relationship graph for that asset.
- The graph renders company-to-attribute, sector, industry, peer, and event-evidence relationships when those relationships are present in the execution payload.
- Graph nodes, edge handles, and relationship chips update the evidence inspector.
- The evidence inspector shows selected evidence refs, edge metadata, source/target, weights, and stored evidence values.
- The demo fixture now requests sector and industry relationships; peer relationships are covered when the selected universe has peer data.

## Phase 5: Packaging Spike

Goal: prove local desktop distribution.

Tasks:

- Package a Windows development build.
- Document macOS build requirements.
- Validate local engine startup from the packaged app.
- Validate graph save/load in a user-writable location.
- Validate app behavior when no database connection is available.

Exit criteria:

- A developer can install and run VIZA locally without manually starting the old web dashboard.

Status as of 2026-05-12:

- Phase 5 Windows development packaging is implemented with Electron Builder.
- `npm run package:win` creates `apps/viza-desktop/release/win-unpacked/VIZA.exe`.
- The packaged app copies the VIZA Python package and local config files into `resources/engine`.
- Packaged engine startup resolves from `process.resourcesPath/engine`; development startup still resolves from the repo root.
- The app autostarts the local VIZA engine without starting the old AAT web dashboard.
- The local engine exposes `GET /viza/runtime`, which reports `database_required=false`.
- Graph save dialogs default to `%USERPROFILE%\Documents\VIZA Methodologies`, and the app creates that directory at startup.
- Windows packaged smoke test passed: local engine started, runtime reported no DB required, and the sample methodology returned 25 rows and 142 relationships.
- macOS build requirements and current system-Python limitation are documented in `docs/VIZA_PACKAGING.md`.

## Prototype Acceptance Criteria

The prototype is complete when:

- The app opens to a blank methodology canvas.
- Users can create, connect, configure, save, and reload nodes.
- The app can execute at least one methodology graph over a local universe.
- The radar table is generated from graph logic.
- The relationship view shows company-to-attribute and company-to-peer links.
- Every result row has evidence or missing-data metadata.
- Unsupported/missing data appears as warnings.
- Existing AAT tests still pass.

## First Demo Scenario

Demo methodology: "Residual Momentum Event Radar"

Graph:

```text
Universe: pilot_sp500_static
  -> Attribute: momentum
  -> Attribute: unexplained_residual_bps
  -> Attribute: event_materiality
  -> Transform: percentile ranks
  -> Score: 40% momentum + 40% residual + 20% event materiality
  -> Output Radar: top 25 companies
  -> Relationship View: peers + selected attributes + event evidence
```

Demo story:

1. Open VIZA.
2. Drag nodes onto the canvas.
3. Connect nodes.
4. Configure weights.
5. Run methodology.
6. Show top ranked companies.
7. Click a company.
8. Show why it surfaced through attributes, peers, and evidence.
9. Save the methodology.
10. Reload it.

## Risks

### Product Risk

The canvas could become a complicated screener rather than a new research workflow. Keep the first screen and first demo centered on methodology design.

### Data Risk

The prototype may expose gaps in current data coverage. Treat missing data as a first-class result, not a crash.

### Architecture Risk

Desktop packaging can become a distraction. Keep the first packaging spike narrow.

### Scope Risk

Thousands of attributes are a final-product goal, not a prototype requirement. Start with 20-40 attributes.

### Backfill Risk

The live FaustCalc backfill should not be disrupted. Do not modify schema, loader order, or persisted attribution semantics for the prototype without following the live-backfill guardrails.

## Immediate Next Step

Start Phase 0:

1. Choose Tauri or Electron for the prototype shell.
2. Add the workspace.
3. Define `viza_graph_v0`.
4. Define the starter attribute registry.
5. Add one sample methodology graph and a schema validation test.
