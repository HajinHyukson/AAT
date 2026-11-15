# VIZA Desktop Prototype

VIZA starts as a downloadable desktop research sandbox for visually defining investment methodologies. Phase 0 creates the workspace and shared graph vocabulary without changing active AAT attribution or backfill paths.

## Phase 0 Stack Choice

The prototype shell starts with Electron-ready TypeScript because the first priority is fast canvas iteration, React Flow compatibility, and straightforward Windows development. Packaging can be revisited after the Phase 5 spike if Tauri's smaller footprint becomes more important than Electron's ecosystem speed.

## Current Contents

- `src/vizaGraph.ts`: TypeScript graph and attribute-registry types that mirror the Python schema.
- `package.json`: Desktop workspace placeholder.
- `tsconfig.json`: Strict TypeScript settings for Phase 1 UI work.

## Contract With Python

Methodology graphs are saved as JSON with `schema_version: "viza_graph_v0"`. The Python package under `viza/` owns validation and future execution. The desktop app should treat graph JSON as the durable project file format.

## Phase 1 Canvas

The app now opens to a methodology canvas backed by the `viza_graph_v0` JSON contract.

Current Phase 1 behavior:

- Create Universe, Attribute, Score, and Output Radar nodes from the left toolbar.
- Connect nodes by dragging between handles.
- Configure selected nodes in the right inspector.
- Save graph JSON through Electron native dialogs or browser download fallback.
- Load graph JSON through Electron native dialogs or browser file picker fallback.

Run the canvas in browser development mode:

```powershell
cd apps\viza-desktop
npm install
npm run dev:engine
npm run dev
```

Run the Electron development shell:

```powershell
cd apps\viza-desktop
npm install
npm run dev:desktop
```

## Phase 2 Engine Bridge

The canvas can call the local VIZA Python service at `http://127.0.0.1:8765`.

Current Phase 2 behavior:

- `GET /viza/attributes` loads the starter attribute registry.
- `GET /viza/universes` loads local MVP and pilot S&P 500 universe summaries.
- `POST /viza/execute` validates a `viza_graph_v0` graph and returns a structured run payload.
- The Run button sends the current canvas graph to the engine and displays warnings, row counts, relationship counts, and evidence summary.

## Phase 3 First Radar

The engine now returns ranked radar rows from the graph definition.

Current Phase 3 behavior:

- Universe nodes resolve local MVP or pilot S&P 500 universe JSON.
- Attribute nodes materialize starter attributes for each company.
- Transform nodes support percentile rank, z-score, and absolute-value ranking.
- Filter nodes can restrict rows by availability, equality, numeric comparisons, ranges, and ticker lists.
- Score nodes support weighted sum and average rank.
- Output Radar nodes control top N, sort direction, and displayed columns.
- Relationship nodes return company-to-attribute, sector, industry, peer, and event-evidence edges.
- The toolbar can create Universe, Attribute, Transform, Filter, Score, Output Radar, and Relationship nodes.

The current research attributes are Phase 3 prototype values derived locally and deterministically, with evidence and warnings. Phase 4 will turn the relationship payload into a dedicated graph view.

## Phase 4 Relationship View

The radar table now drives a company-centered relationship view.

Current Phase 4 behavior:

- Selecting a radar row reveals the company's relationship graph.
- The graph shows company-to-attribute, sector, industry, peer, and event-evidence relationships when those edges are present in the run payload.
- Clicking graph nodes, edge handles, or edge chips updates the evidence inspector.
- The evidence inspector shows the selected evidence ref, edge metadata, weights, source, target, and stored evidence values.

Phase 5 will focus on desktop packaging behavior.

## Phase 5 Packaging

Windows development package:

```powershell
cd apps\viza-desktop
npm run package:win
```

Output:

```text
apps/viza-desktop/release/win-unpacked/VIZA.exe
```

The package copies the VIZA Python service and local config into `resources/engine`, autostarts the local engine, and defaults graph saves to `%USERPROFILE%\Documents\VIZA Methodologies`.

Current limitation: this development package still uses system Python. Set `VIZA_PYTHON` to point at a specific Python executable if needed.

macOS external release package:

```bash
# From the repository root.
python3 -m pip install -e ".[release]"
cd apps/viza-desktop
npm install
npm run release:mac
```

The macOS release command must be run on macOS with Developer ID signing and Apple notarization credentials. It builds the bundled `viza-engine` sidecar, then emits signed/notarized DMG and ZIP artifacts under `release/`.

See `docs/VIZA_PACKAGING.md` for Windows validation and macOS release requirements.
