# VIZA Detailed Implementation Plan

Last updated: 2026-05-12
Plan version: v0.1
Basis: latest `specs.md` v0.4 universal `.viza` strategy-exchange direction + current Phase 0-15 implementation log

---

## 0. Purpose Of This Plan

This document converts the latest VIZA specification into an engineering implementation plan.

It assumes the current implementation already exists through Phase 15 and should not be rewritten. The task is to build the next VIZA program on top of the current foundation:

```text
Current foundation:
Canvas -> Methodology Graph -> Local Engine -> Radar Table -> Evidence/Audit

Next direction:
.viza File -> Visual Strategy Object -> Domain Module Graph
  -> Entity/Event Evidence -> Insight Extraction -> Strategy Translation
  -> Strategy-Fit Output -> Validation Ledger -> Exchange / Future Marketplace
```

The most important product shift is this:

```text
VIZA is not a securities app with extra domains.
VIZA is a universal strategy medium with finance/securities as its first domain module.
```

The implementation should therefore preserve the existing stock-focused prototype but refactor its conceptual boundary:

```text
Current stock graph vocabulary -> viza.finance.securities module
VIZA core -> domain-neutral strategy document system
.viza file -> universal strategy exchange container
```

---

## 1. Non-Negotiable Engineering Principles

### 1.1 Build on the existing Phase 0-15 base

Do not throw away the existing Electron, React, TypeScript, React Flow, Python FastAPI, SQLite project store, attribute registry, connector layer, runtime, evidence, audit, backtest, export, diagnostics, or packaging work.

The current implementation is the foundation. New systems should be added as adapters, modules, and extensions first.

### 1.2 Preserve `viza_graph_v0`

`viza_graph_v0` remains supported until a safe migration path exists.

Do not break:

- current methodology graph save/load,
- current graph execution,
- current node types,
- current test fixtures,
- current methodology version history,
- current audit/reproduce behavior,
- current batch/backtest behavior,
- current exports.

The near-term path is:

```text
Legacy graph remains executable.
Legacy graph can be wrapped into `.viza`.
Legacy graph can be shown through the finance/securities module.
Future graph schema can become module-aware.
```

### 1.3 Use one `.viza` extension

All exchange files use:

```text
.viza
```

Do not create separate user-facing extensions for methodologies, radars, insights, proofs, signals, or templates.

The file contents are described by the internal manifest, not by the filename.

### 1.4 Do not rely on filename semantics

The filename may be arbitrary.

The app must determine everything from `manifest.json` and internal section descriptors:

- object kind,
- exchange modes,
- required modules,
- visibility mode,
- data requirements,
- permissions,
- schema versions,
- integrity state,
- required connectors,
- import/open actions.

### 1.5 Do not use blank sections as semantics

A missing section must have an explicit status, not a blank placeholder.

Allowed section statuses:

```text
included
absent
redacted
entitlement_locked
external_reference
unsupported_schema
deprecated
corrupt
```

### 1.6 Make domain modules the expansion mechanism

The `.viza` format must expand by loading domain modules.

Examples:

```text
viza.finance.securities
viza.real_estate.acquisition
viza.corporate.strategy
viza.sports.soccer
viza.product.roadmap
viza.hiring.selection
```

VIZA core should define domain-neutral primitives only:

```text
entity
candidate_set
attribute
event
evidence
assumption
transform
gate
score
relationship
scenario
decision
output
audit
```

### 1.7 Keep imported files safe

A `.viza` file must never execute arbitrary embedded code.

Runtime behavior comes from trusted, installed, signed, or explicitly approved modules.

Imported strategy files may contain:

- graph structure,
- node configuration,
- evidence,
- outputs,
- manifests,
- audit records,
- permissions,
- UI state,
- documentation.

They may not contain arbitrary executable code that runs on import.

### 1.8 Keep marketplace out of the early build

Do not build marketplace monetization until these are credible:

- insight objects,
- strategy profiles,
- translation engine,
- validation ledger,
- point-in-time data discipline,
- anti-overfitting controls,
- data-rights enforcement,
- creator identity and reputation,
- compliance review.

The early product should support local exchange, import/export, validation, and packaging primitives only.

---

## 2. Existing Baseline To Preserve

### 2.1 Current stack

```text
Desktop shell: Electron
Frontend: React + TypeScript + React Flow
Engine: Python FastAPI local service
Storage: local SQLite project store
Packaging: Windows unpacked dev package; macOS release automation scripts/config
```

Current key paths:

```text
apps/viza-desktop/                 desktop workspace
viza/                              Python graph/runtime package
config/viza_attribute_registry.json starter attribute registry
docs/VIZA_*.md                     VIZA documentation
```

### 2.2 Current graph contract

```text
Schema: viza_graph_v0

Node types:
- universe
- attribute
- transform
- filter
- score
- relationship
- output_radar

Edge types:
- data_flow
- relationship
- evidence
```

### 2.3 Current capabilities that must continue working

The implementation must preserve:

- blank methodology canvas,
- drag/drop node creation,
- typed edge validation,
- graph save/load/new,
- dirty-state tracking,
- node duplication/deletion,
- readiness badges,
- local engine bridge with token and dynamic loopback port,
- graph compiler,
- topology-aware execution,
- graph hashing,
- runtime warnings,
- attribute resolver layer,
- deterministic prototype fallbacks,
- source/evidence metadata,
- relationship/evidence experience,
- relationship query endpoint,
- attribute registry v1,
- 73-attribute registry version `1.1.0`,
- searchable attribute picker,
- connector and entitlement catalog,
- local CSV connector,
- connector field/preview/test endpoints,
- runtime connector warnings,
- export redaction,
- local SQLite project store,
- methodology version save/load/history/compare/clone/revert,
- run records,
- saved radar outputs,
- watchlists,
- alerts,
- audit manifests,
- checksums,
- `/viza/reproduce`,
- batch/backtest endpoint,
- point-in-time cutoff checks,
- radar designer,
- CSV/JSON/manifest/methodology exports,
- diagnostics endpoint,
- desktop diagnostics panel,
- local engine restart,
- Windows unpacked package,
- macOS release automation scripts.

---

## 3. Target Architecture

### 3.1 High-level architecture

```text
.viza File
  ↓
Manifest Inspection + Safety Validation
  ↓
Required Module Detection
  ↓
Module Registry
  ↓
Visual Strategy Object
  ↓
Domain Graph Runtime
  ↓
Entity / Event / Evidence Resolution
  ↓
Insight Extraction
  ↓
Strategy Profile Translation
  ↓
Output Views + Audit + Validation Ledger
  ↓
Export / Share / Package
```

### 3.2 Data architecture

```text
External Domain Data Providers
        ↓
Provider Connectors
        ↓
VIZA Normalization Layer
        ↓
Canonical Entity Database
        ↓
Point-In-Time Observation Store
        ↓
Event + Attribute Resolver Layer
        ↓
Insight Extraction Engine
        ↓
Strategy Profile + Translation Engine
        ↓
Domain Output Views
        ↓
.viza Exchange Container
```

### 3.3 Core technical subsystems to add

| Subsystem | Purpose |
|---|---|
| `.viza` container | Universal strategy document format. |
| Module registry | Makes VIZA expandable across domains. |
| Finance module | Converts current securities prototype into first domain module. |
| File viewer | Visualizes `.viza` contents after opening. |
| Entity store | Domain-neutral identity layer. |
| Security master | Finance-specific canonical asset identity. |
| Observation store | Point-in-time observations and data-version tracking. |
| Event model | First-class catalyst/event objects. |
| Insight model | Structured meaning derived from attributes/events. |
| Strategy profiles | User/domain strategy lens. |
| Translation engine | Converts insight into strategy-specific output. |
| Validation ledger | Trust layer for strategy outputs over time. |
| Packaging permissions | White-box, gray-box, black-box, output-only exchange. |
| Non-finance smoke module | Proves `.viza` expands beyond securities. |

---

## 4. Repository Layout Additions

The following paths are recommendations. Keep naming consistent with the existing repo conventions if they differ.

### 4.1 Backend additions

```text
viza/
  file_format/
    __init__.py
    models.py                 # manifest, section, permissions, compatibility models
    container.py              # zip read/write, path safety, checksums
    inspect.py                # manifest-only inspection and file visualization payloads
    export.py                 # graph/project/run/export packaging into .viza
    import_.py                # import/fork/save flows
    legacy.py                 # .viza.json -> .viza wrappers and migration helpers
    security.py               # zip safety, script rejection, path traversal checks
    checksums.py              # canonical JSON and section checksums

  modules/
    __init__.py
    registry.py               # installed module registry
    models.py                 # module manifest, node type, edge type, entity type definitions
    core_strategy.py          # viza.core.strategy primitives
    finance_securities.py     # current stock node vocabulary as first module
    real_estate_acquisition.py# later smoke-test module
    placeholders.py           # missing/unknown module placeholder nodes

  entities.py                 # universal entity model and APIs
  assets.py                   # finance security master and asset resolver
  observations.py             # point-in-time observation store
  credentials.py              # OS credential vault facade
  events.py                   # event/catalyst schema, registry, store, extraction
  insights.py                 # insight object schema, registry, extraction
  strategy_profiles.py        # profile schema, persistence, versioning
  translation.py              # deterministic strategy-fit rules and translation output
  validation_ledger.py        # output records, proof objects, replay/compare
  rights.py                   # data rights policy enforcement helpers
```

### 4.2 Frontend additions

```text
apps/viza-desktop/src/
  features/
    vizaFiles/
      VizaFileViewer.tsx
      VizaContentsMap.tsx
      VizaCompatibilityPanel.tsx
      VizaImportActions.tsx
      VizaExportWizard.tsx
      StrategyExchangeInbox.tsx
      fileClient.ts
      types.ts

    modules/
      ModuleProvider.tsx
      ModulePalette.tsx
      UnknownNodePlaceholder.tsx
      moduleClient.ts
      types.ts

    entities/
      EntitySearch.tsx
      AssetResolverPanel.tsx
      entityClient.ts
      types.ts

    strategyProfiles/
      StrategyProfileBuilder.tsx
      StrategyProfileInspector.tsx
      profileClient.ts
      templates.ts
      types.ts

    insights/
      InsightCardsPanel.tsx
      InsightCard.tsx
      insightClient.ts
      types.ts

    validation/
      ValidationLedgerPanel.tsx
      validationClient.ts
      types.ts
```

### 4.3 Test additions

```text
tests/unit/
  test_viza_file_format.py
  test_viza_file_security.py
  test_viza_file_import_export.py
  test_viza_modules.py
  test_viza_entities.py
  test_viza_assets.py
  test_viza_observations.py
  test_viza_events.py
  test_viza_insights.py
  test_viza_strategy_profiles.py
  test_viza_translation.py
  test_viza_validation_ledger.py

apps/viza-desktop/src/**/__tests__/
  vizaFileViewer.test.tsx
  exportWizard.test.tsx
  modulePalette.test.tsx
  strategyProfileBuilder.test.tsx
  insightCards.test.tsx
```

### 4.4 Config additions

```text
config/
  viza_modules/
    viza.core.strategy.json
    viza.finance.securities.json
    viza.real_estate.acquisition.json     # later

  viza_insight_registry.json
  viza_strategy_profile_templates.json
  viza_event_registry.json
```

---

## 5. Global Testing And Release Discipline

### 5.1 Run after every backend phase

```powershell
python -m pytest tests\unit tests\lookahead_audit
```

For targeted work, run the new test file plus the dependent runtime/service tests:

```powershell
python -m pytest tests\unit\test_viza_service.py tests\unit\test_viza_runtime.py tests\unit\test_viza_project_store.py
```

### 5.2 Run after every frontend phase

```powershell
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
npm run build
```

### 5.3 Run after packaging-impacting phases

```powershell
cd apps\viza-desktop
npm run package:win
npm run smoke:package
```

### 5.4 Never move forward with known regressions

A phase is not complete if it breaks:

- current graph execution,
- current save/load,
- current project store,
- current reproduce endpoint,
- current batch/backtest,
- current export redaction,
- current diagnostics,
- look-ahead audit tests.

---

# Phase 16 — Baseline Lock And Migration Guardrails

Status: implemented and verified for baseline lock, compatibility policy, and
schema/feature-flag guardrails. No visible product behavior was changed.

## Goal

Prepare the repo for the universal `.viza` and module migration without changing product behavior.

## Why this phase exists

The current implementation is stable through Phase 15. Before introducing a container format and module system, freeze the current behavior with tests and create migration boundaries.

## Backend tasks

1. Create a working branch:

   ```bash
   git checkout -b viza-universal-file-and-modules
   ```

2. Run the full current verification suite.

3. Add a short baseline document:

   ```text
   docs/VIZA_PHASE_16_BASELINE_LOCK.md
   ```

   It should record:

   - current test pass date,
   - current graph schema,
   - current node types,
   - current edge types,
   - current registry version,
   - current project store tables,
   - current package behavior.

4. Add a compatibility policy file:

   ```text
   docs/VIZA_COMPATIBILITY_POLICY.md
   ```

   Required policy:

   - `viza_graph_v0` remains loadable.
   - `.viza.json` remains importable.
   - New `.viza` export becomes default only after round-trip tests pass.
   - Existing project store records are not rewritten in place.
   - Migrations must be additive unless explicitly documented.

5. Add a feature flag layer if one does not already exist.

   Recommended flags:

   ```text
   VIZA_ENABLE_UNIVERSAL_CONTAINER=true
   VIZA_ENABLE_MODULE_REGISTRY=true
   VIZA_ENABLE_EXPERIMENTAL_GRAPH_V1=false
   VIZA_ENABLE_NON_FINANCE_MODULES=false
   ```

6. Add a Python compatibility utility:

   ```text
   viza/compat.py
   ```

   Minimum functions:

   ```python
   def is_legacy_graph_schema(schema: str) -> bool: ...
   def is_supported_graph_schema(schema: str) -> bool: ...
   def normalize_schema_name(schema: str) -> str: ...
   def feature_enabled(name: str, default: bool = False) -> bool: ...
   ```

## Frontend tasks

1. Add a frontend feature flag helper:

   ```text
   apps/viza-desktop/src/lib/featureFlags.ts
   ```

2. Do not expose new UI yet.

3. Ensure current canvas still opens first.

## Tests

Add or update:

```text
tests/unit/test_viza_compat.py
```

Test:

- `viza_graph_v0` recognized as supported.
- Unknown schemas rejected or warned.
- Feature flags default safely.

## Exit criteria

- All current tests pass.
- No visible product behavior changes.
- Compatibility policy exists.
- Future phases have a safe place for schema and feature flag logic.

---

# Phase 17 — Universal `.viza` Container Backend

Status: implemented and verified for the backend universal `.viza` container,
manifest schema, section status contract, integrity checks, local-path service
endpoints, project-store import/export records, and thin desktop API client.

## Goal

Implement the universal `.viza` container, manifest schema, section status contract, integrity checks, safe inspection, and legacy graph wrapping.

## Product requirement

A `.viza` file is the universal strategy exchange container. It may contain graphs, strategy profiles, radars, insights, events, validation proof, signal outputs, rights metadata, UI state, and notes. The filename is not semantic. The manifest is the source of truth.

## Design decision

Use a ZIP-based container for `.viza`.

Rationale:

- supports modular sections,
- supports future module payloads,
- supports embedded Markdown notes,
- supports optional sections without blank fields,
- supports checksums per section,
- easier to inspect and debug during early development.

## Backend implementation

### 17.1 Create file-format package

Create:

```text
viza/file_format/
  __init__.py
  models.py
  container.py
  inspect.py
  export.py
  import_.py
  legacy.py
  security.py
  checksums.py
```

### 17.2 Define manifest models

Use the existing project’s Python validation approach. If the service already uses Pydantic, define Pydantic models.

Core models:

```python
class SectionStatus(str, Enum):
    INCLUDED = "included"
    ABSENT = "absent"
    REDACTED = "redacted"
    ENTITLEMENT_LOCKED = "entitlement_locked"
    EXTERNAL_REFERENCE = "external_reference"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    DEPRECATED = "deprecated"
    CORRUPT = "corrupt"

class VisibilityMode(str, Enum):
    WHITE_BOX = "white_box"
    GRAY_BOX = "gray_box"
    BLACK_BOX = "black_box"
    OUTPUT_ONLY = "output_only"
    PREVIEW_ONLY = "preview_only"

class VizaSectionDescriptor(BaseModel):
    status: SectionStatus
    path: Optional[str] = None
    schema: Optional[str] = None
    checksum: Optional[str] = None
    reason: Optional[str] = None
    required_module_id: Optional[str] = None
    required_module_version: Optional[str] = None

class VizaModuleRequirement(BaseModel):
    module_id: str
    version_range: str
    required: bool = True

class VizaFileManifest(BaseModel):
    schema: Literal["viza.document.v1"]
    file_id: str
    display_name: Optional[str]
    object_kind: str
    primary_mode: Optional[str]
    exchange_modes: list[str] = []
    visibility: VisibilityMode
    created_at: datetime
    updated_at: datetime
    minimum_viza_version: str
    required_modules: list[VizaModuleRequirement] = []
    sections: dict[str, VizaSectionDescriptor]
    data_requirements: dict[str, Any] = {}
    permissions: dict[str, Any] = {}
    integrity: dict[str, Any] = {}
```

Use `viza.document.v1` as the durable universal document schema. If existing code or docs still use `viza_file_v0`, provide a migration alias, but do not make `viza_file_v0` the long-term schema.

### 17.3 Define the canonical section names

Supported section names:

```text
methodology_graph
strategy_profile
strategy_profiles
module_state
entity_snapshot
asset_universe_snapshot
asset_map
events
insights
translations
radar_definition
radar_output
validation_proof
signal_outputs
rights
audit_manifest
checksums
ui_layout
creator_notes
marketplace_metadata
```

Do not require all sections.

### 17.4 Implement container writer

`container.py` should expose:

```python
def write_viza_container(
    target_path: Path,
    manifest: VizaFileManifest,
    sections: dict[str, bytes | str | dict],
) -> VizaWriteResult: ...
```

Rules:

1. Always write `manifest.json` at the ZIP root.
2. Write included sections only if their status is `included`.
3. Do not write redacted content.
4. Do not write entitlement-locked content unless allowed and encrypted/supported later. For now, locked content should be absent from the ZIP and represented only by manifest metadata.
5. Normalize JSON before checksumming.
6. Store checksums in manifest before final write.
7. Compute a container checksum after write.
8. Never include credentials.
9. Never include raw restricted evidence unless export policy allows it.

### 17.5 Implement container reader

Expose:

```python
def read_viza_manifest(path: Path) -> VizaFileManifest: ...
def inspect_viza_container(path: Path) -> VizaInspectionResult: ...
def read_viza_section(path: Path, section_name: str) -> VizaSectionReadResult: ...
```

Rules:

1. Manifest-only inspection must not load every section.
2. Reject missing `manifest.json`.
3. Reject malformed manifest.
4. Warn on unsupported schema.
5. Preserve unknown sections but do not execute them.
6. Verify requested section checksum before returning content.

### 17.6 Implement ZIP safety

`security.py` must enforce:

- no absolute paths,
- no `..` path traversal,
- no symlinks,
- max file count,
- max manifest size,
- max section size,
- no executable paths by default,
- no `.exe`, `.dll`, `.so`, `.dylib`, `.bat`, `.cmd`, `.ps1`, `.sh`, `.py`, `.js`, `.ts` as executable payloads,
- suspicious files quarantined or refused.

Important: strategy files may contain JSON and Markdown, not executable module code.

### 17.7 Implement legacy `.viza.json` wrapper

`legacy.py` should expose:

```python
def legacy_graph_json_to_viza_manifest(graph: dict) -> VizaFileManifest: ...
def wrap_legacy_graph_json(path: Path, target_path: Path) -> VizaWriteResult: ...
def unwrap_methodology_graph_from_viza(path: Path) -> MethodologyGraph: ...
```

Legacy wrap behavior:

```text
object_kind = methodology
primary_mode = methodology_graph
exchange_modes = [methodology_graph]
visibility = white_box
required_modules = [viza.finance.securities]
sections.methodology_graph.status = included
sections.methodology_graph.schema = viza_graph_v0
```

### 17.8 Add backend endpoints

Add to `viza/service.py`:

```text
POST /viza/files/inspect
POST /viza/files/validate
POST /viza/files/export
POST /viza/files/import
GET  /viza/files/{file_id}
GET  /viza/files/{file_id}/sections
POST /viza/files/quarantine
```

For this phase, endpoints may operate on local paths in dev mode. In production UI, Electron should mediate file selection and pass safe paths to the engine.

### 17.9 Add project-store import/export records

Add SQLite tables:

```sql
CREATE TABLE IF NOT EXISTS viza_file_imports (
  import_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  project_id TEXT,
  source_path TEXT,
  imported_at TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  container_checksum TEXT,
  manifest_checksum TEXT,
  status TEXT NOT NULL,
  warnings_json TEXT NOT NULL DEFAULT '[]',
  quarantine_status TEXT NOT NULL DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS viza_file_exports (
  export_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  project_id TEXT,
  target_path TEXT,
  exported_at TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  container_checksum TEXT,
  manifest_checksum TEXT,
  purpose TEXT,
  visibility TEXT,
  warnings_json TEXT NOT NULL DEFAULT '[]'
);
```

Use additive migrations only.

## Frontend implementation

For this phase, only add a thin API client:

```text
apps/viza-desktop/src/features/vizaFiles/fileClient.ts
apps/viza-desktop/src/features/vizaFiles/types.ts
```

No full UI required yet.

## Tests

Create:

```text
tests/unit/test_viza_file_format.py
tests/unit/test_viza_file_security.py
tests/unit/test_viza_file_import_export.py
```

Test cases:

- valid `.viza` container writes and reads,
- manifest-only inspection,
- missing manifest rejected,
- invalid manifest rejected,
- unsupported schema warns,
- corrupt section checksum detected,
- path traversal blocked,
- executable payload blocked,
- redacted section not bundled,
- entitlement-locked section not readable,
- `.viza.json` graph wraps into `.viza`,
- `.viza` unwraps current `viza_graph_v0` graph without loss,
- container never includes credential-like keys.

## Exit criteria

- Current graph exports as `.viza`.
- Current graph imports from `.viza`.
- Manifest inspection works without loading all sections.
- Filename is ignored.
- Section status contract works.
- Security tests pass.
- Current Phase 0-15 tests still pass.

---

# Phase 18 — Module Registry And Finance/Securities Module Conversion

Status: implemented and verified. Current graph behavior and visible node
palette remain stable while legacy node types are internally recognized through
`viza.finance.securities`.

## Goal

Introduce VIZA’s domain module system and register the current stock-focused graph vocabulary as `viza.finance.securities`.

## Product requirement

VIZA must become expandable like Visio shape sets, but executable. Domain modules define blocks, entity types, edge types, runtime handlers, validation rules, output views, evidence rules, and inspector schemas.

## Backend implementation

### 18.1 Create module package

Create:

```text
viza/modules/
  __init__.py
  models.py
  registry.py
  core_strategy.py
  finance_securities.py
  placeholders.py
```

### 18.2 Define module models

Minimum models:

```python
class VizaModuleManifest(BaseModel):
    schema: Literal["viza.module_manifest.v1"]
    module_id: str
    module_version: str
    display_name: str
    domain: str
    description: Optional[str] = None
    entity_types: dict[str, EntityTypeDefinition] = {}
    node_types: dict[str, NodeTypeDefinition] = {}
    edge_types: dict[str, EdgeTypeDefinition] = {}
    output_views: dict[str, OutputViewDefinition] = {}
    data_connectors: list[str] = []
    validation_rules: list[str] = []
    runtime_handlers: dict[str, str] = {}
    palette_groups: list[PaletteGroupDefinition] = []

class NodeTypeDefinition(BaseModel):
    type_id: str
    display_name: str
    category: str
    extends: str
    description: Optional[str]
    inspector_schema: dict[str, Any]
    allowed_incoming_edges: list[str]
    allowed_outgoing_edges: list[str]
    runtime_handler: Optional[str]
    visual: dict[str, Any] = {}
```

### 18.3 Define core strategy module

`viza.core.strategy` should define domain-neutral primitives:

```text
entity
candidate_set
attribute
event
evidence
assumption
transform
gate
score
relationship
scenario
decision
output
audit
```

This module does not need full runtime behavior yet. It defines the conceptual base and extension targets.

### 18.4 Define finance/securities module

`viza.finance.securities` should wrap existing node types.

Mapping:

| Existing node type | Finance module type | Core primitive |
|---|---|---|
| `universe` | `viza.finance.securities.universe` | `candidate_set` |
| `attribute` | `viza.finance.securities.attribute` | `attribute` |
| `transform` | `viza.finance.securities.transform` | `transform` |
| `filter` | `viza.finance.securities.filter` | `gate` |
| `score` | `viza.finance.securities.score` | `score` |
| `relationship` | `viza.finance.securities.relationship` | `relationship` |
| `output_radar` | `viza.finance.securities.output_radar` | `output` |

Do not immediately rewrite existing graphs. Add adapter support:

```text
legacy node type -> finance module node type for display and validation
finance module node type -> legacy node type for existing runtime execution
```

### 18.5 Add module registry service

`registry.py` should expose:

```python
class ModuleRegistry:
    def list_modules(self) -> list[VizaModuleManifest]: ...
    def get_module(self, module_id: str) -> VizaModuleManifest: ...
    def resolve_node_type(self, type_id: str) -> ResolvedNodeType: ...
    def legacy_to_module_type(self, legacy_type: str) -> str: ...
    def module_to_legacy_type(self, module_type: str) -> str: ...
    def required_modules_for_graph(self, graph: MethodologyGraph) -> list[VizaModuleRequirement]: ...
```

### 18.6 Add missing-module placeholders

If a `.viza` file requires a module that is not installed:

- open in read-only or placeholder mode,
- show unknown nodes as locked placeholders,
- preserve raw config,
- preserve unknown node/edge payloads on save,
- prevent execution unless module is installed.

### 18.7 Add endpoints

```text
GET  /viza/modules
GET  /viza/modules/{module_id}
POST /viza/modules/resolve-node-types
POST /viza/modules/check-compatibility
```

## Frontend implementation

### 18.8 Module registry client

Add:

```text
apps/viza-desktop/src/features/modules/moduleClient.ts
apps/viza-desktop/src/features/modules/types.ts
```

### 18.9 Module-aware palette

Refactor the current left toolbar so it can be generated from module definitions.

Important: keep the current user-facing labels stable.

The user may still see:

```text
Universe
Attribute
Transform
Filter
Score
Relationship
Output Radar
```

Internally, the UI should know these come from `viza.finance.securities`.

### 18.10 Unknown node placeholder

Add:

```text
UnknownNodePlaceholder.tsx
```

It should render:

```text
Unknown Module Node
module: viza.real_estate.acquisition
node type: noi_model
status: module not installed
```

Do not allow editing or execution. Allow copy/view raw config if safe.

## Tests

Create:

```text
tests/unit/test_viza_modules.py
```

Test:

- core module loads,
- finance module loads,
- legacy node types map to finance module types,
- current graphs require `viza.finance.securities`,
- unknown module creates placeholder,
- unknown node config round-trips,
- module registry endpoint returns modules,
- palette data is serializable.

Frontend tests:

- module palette renders current nodes,
- unknown node placeholder renders,
- current canvas still works.

## Exit criteria

- Current graph still executes.
- Current node palette still appears.
- Internally, current nodes are recognized as finance module nodes.
- `.viza` export includes `viza.finance.securities` in `required_modules`.
- Missing module behavior is safe and round-trippable.

---

# Phase 19 — `.viza` File Viewer, Import Flow, Export Wizard, And Exchange Inbox

Status: implemented and verified for backend visualization payloads, local
import/export flow modes, safe Electron file-path bridges, and first file
viewer/inbox/export-wizard components.

## Goal

Make `.viza` files understandable inside the VIZA program after opening.

## Product requirement

The filename does not need to tell the user what the file entails. When opened through VIZA, the app visualizes the file contents, internal modes, modules, permissions, data requirements, sections, and actions.

## Backend implementation

### 19.1 File visualization payload

Add `VizaFileVisualization` model:

```python
class VizaFileVisualization(BaseModel):
    file_id: str
    display_name: Optional[str]
    object_kind: str
    visibility: str
    schema: str
    required_modules: list[ModuleCompatibilityStatus]
    contents_map: dict[str, VizaSectionVisualization]
    compatibility: VizaCompatibilitySummary
    available_actions: list[str]
    warnings: list[VizaWarning]
```

### 19.2 Inspect endpoint returns visualization

Update:

```text
POST /viza/files/inspect
GET  /viza/files/{file_id}/visualization
```

The response must include:

- file summary,
- contents map,
- required modules,
- missing modules,
- required connectors,
- missing connectors,
- permissions,
- checksum status,
- unsupported schemas,
- available actions.

### 19.3 Import behavior

`POST /viza/files/import` should support modes:

```text
open_without_import
import_to_project
fork_as_new_methodology
install_radar
save_snapshot
quarantine
```

For the first implementation, support:

- `open_without_import`,
- `import_to_project`,
- `fork_as_new_methodology`,
- `quarantine`.

### 19.4 Export wizard backend support

`POST /viza/files/export` should accept:

```json
{
  "project_id": "...",
  "methodology_version_id": "...",
  "run_id": "...",
  "purpose": "collaboration",
  "visibility": "white_box",
  "include_sections": ["methodology_graph", "audit_manifest", "radar_definition"],
  "target_path": "..."
}
```

The backend should:

1. Load requested local objects.
2. Check export permissions.
3. Redact restricted data.
4. Build manifest.
5. Write `.viza` container.
6. Record export.

## Frontend implementation

### 19.5 Electron file open integration

In Electron main/preload, add safe file selection and open-path bridges.

Suggested IPC:

```text
viza:selectVizaFile
viza:openRecentVizaFile
viza:selectExportPath
```

Renderer should not directly access arbitrary filesystem paths outside the existing safe bridge pattern.

### 19.6 File viewer route/screen

Add a screen:

```text
VizaFileViewer.tsx
```

Sections:

```text
Header
  display name
  file ID
  object kind
  visibility
  schema
  creator if available
  integrity status

Contents Map
  methodology graph
  strategy profile
  module state
  events
  insights
  radar definition
  radar output
  validation proof
  audit manifest
  rights
  notes

Compatibility
  required modules
  missing modules
  required connectors
  missing connectors
  app version compatibility
  schema compatibility
  PIT status
  rights status

Actions
  open canvas
  inspect graph
  import
  fork
  install radar
  map connectors
  run locally
  view proof
  quarantine
```

### 19.7 Strategy Exchange Inbox

Add:

```text
StrategyExchangeInbox.tsx
```

Views:

- recent `.viza` files,
- imported files,
- forked files,
- quarantined files,
- files with missing modules,
- files with missing connectors,
- files with proof,
- files with locked/redacted sections.

### 19.8 Export wizard

Add:

```text
VizaExportWizard.tsx
```

Steps:

1. Choose purpose.
2. Choose visibility.
3. Choose sections.
4. Run data-rights check.
5. Preview redactions.
6. Choose target path.
7. Export.
8. Show manifest summary.

## Tests

Backend:

- inspect returns visualization,
- actions change with visibility and sections,
- missing modules shown,
- missing connectors shown,
- import records written,
- export records written,
- quarantine state persists.

Frontend:

- file viewer renders all statuses,
- contents map shows included/absent/redacted/locked,
- export wizard writes expected request,
- exchange inbox lists imported/quarantined files.

## Exit criteria

- User can open any `.viza` file and see a visual summary inside VIZA.
- Current methodology graph can be exported, opened, imported, forked, and executed.
- File viewer never depends on the filename.
- Redacted/locked/unsupported sections are visually distinct.

---

# Phase 20 — Universal Entity Store And Finance Security Master Seed

## Goal

Create a domain-neutral entity identity layer and the first finance-specific asset/security master.

## Product requirement

The universal strategy direction should not use `asset` as the VIZA core identity concept. Use `entity` in the core. Finance-specific modules can use `asset`, `security`, `company`, or `instrument` as aliases/subtypes.

## Backend implementation

### 20.1 Create universal entity schema

Create `viza/entities.py`.

Core entity schema:

```python
class VizaEntity(BaseModel):
    schema: Literal["viza.entity.v1"]
    entity_id: str
    entity_type: str
    display_name: str
    domain: str
    module_id: Optional[str]
    aliases: list[str] = []
    identifiers: dict[str, str] = {}
    metadata: dict[str, Any] = {}
    source_lineage: list[dict[str, Any]] = []
    rights_policy: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
```

### 20.2 Create finance asset schema

Create `viza/assets.py`.

Finance asset schema:

```python
class VizaAsset(BaseModel):
    schema: Literal["viza.asset.v1"]
    entity_id: str
    asset_id: str
    asset_class: str
    primary_symbol: str
    current_name: str
    exchange: Optional[str]
    country: str
    currency: str
    identifiers: dict[str, str]
    sector: Optional[str]
    industry: Optional[str]
    listing_status: str
    provider_identifier_map: dict[str, str]
    source_lineage: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
```

### 20.3 Add project-store tables

Add tables:

```sql
CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  module_id TEXT,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  identifiers_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  source_lineage_json TEXT NOT NULL DEFAULT '[]',
  rights_policy_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS finance_assets (
  asset_id TEXT PRIMARY KEY,
  entity_id TEXT NOT NULL,
  asset_class TEXT NOT NULL,
  primary_symbol TEXT NOT NULL,
  current_name TEXT NOT NULL,
  exchange TEXT,
  country TEXT,
  currency TEXT,
  identifiers_json TEXT NOT NULL DEFAULT '{}',
  sector TEXT,
  industry TEXT,
  listing_status TEXT,
  provider_identifier_map_json TEXT NOT NULL DEFAULT '{}',
  source_lineage_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
);

CREATE TABLE IF NOT EXISTS entity_relationships (
  relationship_id TEXT PRIMARY KEY,
  source_entity_id TEXT NOT NULL,
  target_entity_id TEXT NOT NULL,
  relationship_type TEXT NOT NULL,
  family TEXT,
  confidence REAL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 20.4 Seed U.S. equity entities from existing local universe

Use the current local universe records as the first seed.

For each ticker:

1. Create `entity_id`.
2. Create `asset_id`.
3. Store symbol, name, sector, industry if available.
4. Store provider identifiers if known.
5. Mark missing identifiers explicitly.

### 20.5 Add resolver service

Expose:

```text
GET  /viza/entities/search
POST /viza/entities/resolve
GET  /viza/entities/{entity_id}
GET  /viza/entities/{entity_id}/relationships

GET  /viza/assets/search
POST /viza/assets/resolve
GET  /viza/assets/{asset_id}
GET  /viza/assets/{asset_id}/identifiers
POST /viza/assets/reconcile
```

### 20.6 Add asset resolver node

Add future node type through finance module:

```text
viza.finance.securities.asset_resolver
```

For `viza_graph_v0`, this may be implicit at runtime:

```text
Universe node -> resolve tickers -> attach asset_id/entity_id to rows
```

### 20.7 Update runtime row model

Radar rows should begin carrying:

```text
entity_id
asset_id
ticker/company_name legacy fields preserved
```

Do not remove existing `ticker` field.

### 20.8 Update evidence records

Evidence should include:

```text
entity_id
asset_id where applicable
source_identifier
resolved_identifier_type
```

## Frontend implementation

1. Add entity/asset resolver panel in node inspector.
2. Add entity IDs to debug/audit view.
3. Keep visible user-facing rows simple: ticker and company name remain primary.
4. Add resolver warnings when tickers cannot be resolved.

## Tests

Create:

```text
tests/unit/test_viza_entities.py
tests/unit/test_viza_assets.py
```

Test:

- seed local universe,
- resolve ticker to asset ID,
- duplicate ticker conflict warning,
- missing identifier warning,
- provider identifier map serialization,
- radar rows include asset/entity IDs,
- evidence records include asset/entity IDs,
- legacy graphs still run without explicit asset resolver node.

## Exit criteria

- Methodology runs resolve tickers to internal IDs.
- Evidence can reference entity/asset IDs.
- Current UI still works with ticker-first display.
- `.viza` export can include asset map or mark it as absent/external.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- Universal `VizaEntity` store with local-universe seeding, search, resolve, get, and relationship endpoints.
- Finance `VizaAsset` store with local-universe security-master seeding, provider identifier map serialization, identifier lookup, reconcile checks, and API endpoints.
- Additive project-store tables for `entities`, `finance_assets`, and `entity_relationships`.
- Runtime row and evidence enrichment with `entity_id`, `asset_id`, `source_identifier`, and `resolved_identifier_type` while preserving ticker-first UI behavior.
- Frontend entity/asset resolver client types and first-pass resolver panel scaffolding.
- Tests for entity seeding/resolution, asset seeding/resolution, duplicate warnings, provider identifier maps, endpoints, runtime rows, and evidence IDs.

Verification:

```powershell
python -m pytest tests\unit\test_viza_entities.py tests\unit\test_viza_assets.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 34 focused Phase 20/service/runtime tests, 211 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 21 — Credential Vault And Source-Backed Connector Configuration

## Goal

Add secure credential storage and real connector configuration paths so source-backed resolvers can be promoted without leaking secrets.

## Product requirement

VIZA should outsource raw data to user-entitled providers while owning normalization, evidence, point-in-time metadata, and strategy meaning. Credentials must never be written to `.viza` files, project exports, logs, manifests, or regular SQLite settings.

## Backend implementation

### 21.1 Choose credential architecture

Recommended initial approach:

- engine owns connector execution,
- engine uses Python OS keyring or an equivalent secure credential vault abstraction,
- project store stores only credential references and availability flags,
- renderer never receives saved secret values,
- `.viza` files store only connector requirements, never secrets.

Create:

```text
viza/credentials.py
```

Minimum interface:

```python
class CredentialStore:
    def set_secret(self, connector_id: str, key: str, value: str) -> CredentialRef: ...
    def has_secret(self, connector_id: str, key: str) -> bool: ...
    def get_secret_for_runtime(self, connector_id: str, key: str) -> str: ...
    def delete_secret(self, connector_id: str, key: str) -> None: ...
    def list_secret_status(self, connector_id: str) -> list[CredentialStatus]: ...
```

If OS keyring is unavailable, fall back to dev-only environment variables and clearly label the mode as insecure/dev-only.

### 21.2 Add connector settings persistence

The existing project store has connector settings metadata. Extend it to store:

```text
connector_id
project_id
settings_json without secrets
credential_refs_json
credential_status_json
updated_at
```

### 21.3 Add credential endpoints

```text
GET    /viza/connectors/{connector_id}/credentials
POST   /viza/connectors/{connector_id}/credentials
DELETE /viza/connectors/{connector_id}/credentials/{key}
POST   /viza/connectors/{connector_id}/configure
```

Rules:

- POST may receive secret value once.
- GET never returns secret value.
- Logs must redact values.
- Diagnostics must report availability only.

### 21.4 Update connector health

Connector health should include:

```text
credential_required
credential_configured
credential_mode
query_allowed
cache_allowed
display_allowed
export_allowed
redistribution_allowed
```

## Frontend implementation

1. Add connector settings panel.
2. Let user set API keys or local paths.
3. Show credential availability.
4. Do not show stored secret values.
5. Add “test connector” button.
6. Add warning if running in dev-only env-var mode.

## Tests

Backend:

- setting secret stores only credential ref in project store,
- `GET credentials` never returns values,
- diagnostics never returns values,
- `.viza` export never includes values,
- logs redact values,
- connector health reports credential status.

Frontend:

- credential input clears after save,
- status shows configured/unconfigured,
- no secret rendered after reload.

## Exit criteria

- Connector secrets can be configured safely.
- No credential values are present in `.viza`, exports, diagnostics, logs, or SQLite metadata.
- Source-backed resolver work can begin safely.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `viza/credentials.py` vault abstraction with OS keyring support when available and explicit `env_var_dev` fallback mode.
- Connector credential endpoints for status, one-time secret set, delete, and non-secret connector configuration.
- Additive connector settings persistence for project ID, redacted settings, credential references, credential status, and updated timestamp.
- Connector health and runtime diagnostics now report credential/configuration availability and entitlement booleans without secret values.
- Local CSV connector can read saved non-secret path settings.
- Frontend connector client/types plus a first-pass settings panel that clears secret input after save and shows configured/unconfigured status.
- Tests proving credentials do not appear in API responses, SQLite connector metadata, diagnostics, or `.viza` exports.

Verification:

```powershell
python -m pytest tests\unit\test_viza_credentials.py tests\unit\test_viza_connectors.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_project_store.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 35 focused Phase 21/connectors/project-store/service tests, 215 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 22 — Point-In-Time Observation Store And Technical Resolver Promotion

## Goal

Create the first durable point-in-time observation store and promote core technical indicators from deterministic prototype values to source-backed calculations where data exists.

## Product requirement

VIZA must know what information was available at a given point in time. This is required for backtesting, reproducibility, validation, and future marketplace trust.

## Backend implementation

### 22.1 Create observation schema

Create `viza/observations.py`.

Model:

```python
class VizaObservation(BaseModel):
    schema: Literal["viza.observation.v1"]
    observation_id: str
    entity_id: str
    asset_id: Optional[str]
    attribute_key: str
    value: Any
    unit: Optional[str]
    observed_at: datetime
    available_at: datetime
    retrieved_at: datetime
    source_id: str
    connector_id: str
    source_record: Optional[str]
    data_version: Optional[str]
    model_version: Optional[str]
    confidence: Optional[float]
    rights_policy: dict[str, Any]
    checksum: str
```

### 22.2 Add observation tables

SQLite is acceptable for MVP. If batch analytics become heavy, add DuckDB later.

```sql
CREATE TABLE IF NOT EXISTS observations (
  observation_id TEXT PRIMARY KEY,
  entity_id TEXT NOT NULL,
  asset_id TEXT,
  attribute_key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  unit TEXT,
  observed_at TEXT NOT NULL,
  available_at TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  source_id TEXT NOT NULL,
  connector_id TEXT NOT NULL,
  source_record TEXT,
  data_version TEXT,
  model_version TEXT,
  confidence REAL,
  rights_policy_json TEXT NOT NULL DEFAULT '{}',
  checksum TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_lookup
ON observations(entity_id, attribute_key, available_at);
```

### 22.3 Add OHLCV source-backed path

Promote technical indicators in this order:

1. `latest_price` or existing local price coverage,
2. `rsi_14d`,
3. `momentum`,
4. `moving_average_trend`,
5. `volume_spike`,
6. `realized_volatility`,
7. `short_term_reversal`.

Initial source path:

- Local CSV connector for OHLCV.
- Optional configured provider later.

Do not block runs when source data is absent. Return explicit missing/prototype status.

### 22.4 Update attribute resolver contract

Attribute resolver output already contains source, data version, model version, confidence, missing reason, and prototype status. Extend it with:

```text
entity_id
asset_id
observation_id
observed_at
available_at
retrieved_at
rights_policy
PIT_status
```

### 22.5 PIT-safe retrieval

Observation queries must support:

```python
def get_latest_observation_as_of(entity_id, attribute_key, cutoff): ...
```

Rule:

```text
available_at <= timestamp_cutoff
```

Never use observations that became available after the cutoff.

### 22.6 Add endpoints

```text
POST /viza/observations/query
GET  /viza/observations/{observation_id}
POST /viza/observations/ingest
```

## Frontend implementation

1. Add source-backed/prototype indicators to attribute detail view.
2. Add PIT status to evidence inspector.
3. Show when an attribute was calculated from local OHLCV.
4. Show missing-data reason when OHLCV is absent.

## Tests

Create:

```text
tests/unit/test_viza_observations.py
```

Test:

- insert observation,
- retrieve as-of cutoff,
- reject look-ahead observation,
- compute RSI from local OHLCV,
- use prototype fallback when source absent,
- evidence includes observation ID,
- export redacts restricted source data,
- result checksum stable with same observation versions.

## Exit criteria

- First wedge technical overlays can be source-backed where data exists.
- PIT lookup works.
- Prototype fallback remains explicit.
- Evidence and run manifests include observation metadata.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `viza/observations.py` with `VizaObservation`, observation ingestion/query models, SQLite store, deterministic checksums, and PIT-safe `available_at <= cutoff` retrieval.
- Additive project-store `observations` table and diagnostics coverage.
- Local OHLCV-to-technical observation calculation for latest price, RSI 14d, momentum, moving-average trend, volume spike, realized volatility, and short-term reversal where enough rows exist.
- Attribute resolver promotion path that uses source-backed observations for technical attributes when present and keeps explicit prototype fallback when absent.
- Runtime evidence now includes observation ID, observed/available/retrieved timestamps, rights policy, and PIT status.
- Observation API endpoints and frontend observation client/types plus a small PIT/source badge scaffold.
- Restricted observation export helper that redacts raw values when source rights disallow export.

Verification:

```powershell
python -m pytest tests\unit\test_viza_observations.py tests\unit\test_viza_attribute_resolvers.py tests\unit\test_viza_runtime.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 44 focused Phase 22/runtime/project-store/service tests, 221 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 23 — Event/Catalyst Object Model

## Goal

Make catalysts first-class objects.

## Product requirement

The first strategic wedge is U.S. equities + event-driven catalysts + technical confirmation. Therefore, events must become structured objects, not just loose attributes.

## Backend implementation

### 23.1 Create event schema

Create `viza/events.py`.

Model:

```python
class VizaEvent(BaseModel):
    schema: Literal["viza.event.v1"]
    event_id: str
    event_type: str
    affected_entity_ids: list[str]
    affected_asset_ids: list[str] = []
    related_entity_ids: list[str] = []
    observed_at: datetime
    available_at: datetime
    source: dict[str, Any]
    confidence: float
    source_credibility: Optional[float]
    materiality: Optional[float]
    novelty: Optional[float]
    direction_hint: Optional[str]
    time_horizon_hint: Optional[str]
    risk_factors: list[str]
    evidence_refs: list[str]
    rights_policy: dict[str, Any]
    point_in_time_safe: bool
```

### 23.2 Create event registry

Add config:

```text
config/viza_event_registry.json
```

Initial event types:

```text
acquisition_rumor
confirmed_mna
analyst_upgrade
analyst_downgrade
earnings_surprise
insider_purchase
insider_sale
unusual_volume
unusual_options_activity
regulatory_action
sec_filing_novelty
management_commentary_change
news_sentiment_shift
social_sentiment_shift
peer_contagion_event
sector_contagion_event
```

### 23.3 Add event tables

```sql
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  affected_entity_ids_json TEXT NOT NULL,
  affected_asset_ids_json TEXT NOT NULL DEFAULT '[]',
  related_entity_ids_json TEXT NOT NULL DEFAULT '[]',
  observed_at TEXT NOT NULL,
  available_at TEXT NOT NULL,
  source_json TEXT NOT NULL,
  confidence REAL NOT NULL,
  source_credibility REAL,
  materiality REAL,
  novelty REAL,
  direction_hint TEXT,
  time_horizon_hint TEXT,
  risk_factors_json TEXT NOT NULL DEFAULT '[]',
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  rights_policy_json TEXT NOT NULL DEFAULT '{}',
  point_in_time_safe INTEGER NOT NULL
);
```

### 23.4 Add event/catalyst node

Register through finance module:

```text
viza.finance.securities.event_catalyst
```

Config:

```json
{
  "event_types": ["acquisition_rumor", "earnings_surprise"],
  "min_confidence": 0.4,
  "min_source_credibility": 0.5,
  "time_window": "30d",
  "require_point_in_time_safe": true
}
```

### 23.5 Add deterministic event extraction

For MVP, extract events from:

- existing event intelligence attributes,
- local/user-provided news CSV,
- manually added events,
- SEC filing metadata if already available.

Do not require NLP yet.

### 23.6 Add event endpoints

```text
POST /viza/events/extract
POST /viza/events/query
GET  /viza/events/{event_id}
POST /viza/events/manual
```

### 23.7 Add relationships

Add relationship families:

```text
entity_to_event
asset_to_event
event_to_evidence
event_to_attribute
event_to_related_entity
```

## Frontend implementation

1. Add event/catalyst node to finance module palette.
2. Add event inspector.
3. Add manual event creation panel.
4. Add event cards in run results.
5. Add event badges in radar rows.

## Tests

Create:

```text
tests/unit/test_viza_events.py
```

Test:

- event registry loads,
- manual event create/query,
- event extraction from deterministic attributes,
- event respects PIT cutoff,
- event links to entity/asset/evidence,
- event section exports into `.viza`,
- restricted event evidence redacts on export.

## Exit criteria

- Methodology can output event objects linked to assets/entities and evidence.
- Acquisition-rumor and earnings-surprise event placeholders work.
- Event relationships appear in relationship query payloads.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `config/viza_event_registry.json` with the initial catalyst/event type catalog.
- `viza/events.py` with `VizaEvent`, manual event creation, deterministic event extraction from existing event-intelligence attributes, SQLite persistence, PIT cutoff filtering, query/get helpers, and restricted-export redaction.
- Additive project-store `events` table and diagnostics coverage.
- Event endpoints for extract, query, get, and manual create.
- Finance module registration for `viza.finance.securities.event_catalyst`.
- Relationship-query enrichment with `entity_to_event` and `asset_to_event` event-family edges linked to extracted events.
- Frontend event client/types plus a first-pass event card scaffold.
- Tests for registry loading, manual create/query/get, deterministic extraction, PIT cutoff handling, entity/asset/evidence links, `.viza` event section export, restricted redaction, and relationship payloads.

Verification:

```powershell
python -m pytest tests\unit\test_viza_events.py tests\unit\test_viza_modules.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 48 focused Phase 23/module/runtime/service tests, 228 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 24 — Insight Object Schema, Registry, And Extraction

## Goal

Emit first-class insight objects from methodology outputs.

## Product requirement

An insight is structured meaning, not a summary. It must be testable, filterable, translatable, auditable, exchangeable, and embeddable in `.viza`.

## Backend implementation

### 24.1 Create insight schema

Create `viza/insights.py`.

Model:

```python
class VizaInsight(BaseModel):
    schema: Literal["viza.insight.v1"]
    insight_id: str
    entity_id: str
    asset_id: Optional[str]
    related_entity_ids: list[str] = []
    related_asset_ids: list[str] = []
    insight_type: str
    direction: str
    magnitude: Optional[dict[str, Any]]
    confidence: float
    time_horizon: dict[str, str]
    evidence_refs: list[str]
    source_policy: dict[str, Any]
    observed_at: datetime
    available_at: datetime
    generated_at: datetime
    strategy_compatibility: list[dict[str, Any]] = []
    risk_factors: list[str]
    invalidation_conditions: list[str]
    action_layer: dict[str, Any]
    derivation_trace: dict[str, Any]
```

### 24.2 Create insight registry

Add:

```text
config/viza_insight_registry.json
```

Initial insight types:

```text
acquisition_rumor
acquisition_rumor_with_technical_reversal_context
confirmed_mna_spread_context
earnings_surprise_momentum_confirmation
analyst_upgrade_with_price_confirmation
insider_cluster_with_momentum_breakout
unusual_volume_catalyst_watch
sec_filing_novelty_materiality
regulatory_risk_event
peer_contagion_event
sentiment_shift_with_liquidity_check
```

Registry entry fields:

```text
insight_type_key
display_name
description
family
compatible_strategy_profiles
required_event_types
required_attributes
optional_confirmations
direction_logic
confidence_logic
horizon_defaults
risk_factors
invalidation_templates
evidence_requirements
rights_policy
point_in_time_policy
```

### 24.3 Add insight tables

```sql
CREATE TABLE IF NOT EXISTS insights (
  insight_id TEXT PRIMARY KEY,
  entity_id TEXT NOT NULL,
  asset_id TEXT,
  related_entity_ids_json TEXT NOT NULL DEFAULT '[]',
  related_asset_ids_json TEXT NOT NULL DEFAULT '[]',
  insight_type TEXT NOT NULL,
  direction TEXT NOT NULL,
  magnitude_json TEXT,
  confidence REAL NOT NULL,
  time_horizon_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  source_policy_json TEXT NOT NULL DEFAULT '{}',
  observed_at TEXT NOT NULL,
  available_at TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  strategy_compatibility_json TEXT NOT NULL DEFAULT '[]',
  risk_factors_json TEXT NOT NULL DEFAULT '[]',
  invalidation_conditions_json TEXT NOT NULL DEFAULT '[]',
  action_layer_json TEXT NOT NULL DEFAULT '{}',
  derivation_trace_json TEXT NOT NULL DEFAULT '{}'
);
```

### 24.4 Add insight extractor node

Register:

```text
viza.finance.securities.insight_extractor
```

Config:

```json
{
  "enabled_insight_types": [
    "acquisition_rumor_with_technical_reversal_context",
    "earnings_surprise_momentum_confirmation"
  ],
  "min_confidence": 0.45,
  "require_evidence_refs": true,
  "require_point_in_time_safe": true
}
```

### 24.5 Implement rule-based extraction for first wedge

MVP rule example:

```text
IF event_type = acquisition_rumor
AND rsi_14d <= configured oversold threshold
THEN insight_type = acquisition_rumor_with_technical_reversal_context
```

Confidence can combine:

```text
event confidence
source credibility
technical confirmation strength
materiality
novelty
missing confirmations penalty
```

### 24.6 Add insight endpoints

```text
POST /viza/insights/extract
POST /viza/insights/query
GET  /viza/insights/{insight_id}
```

### 24.7 Update runtime result model

Runtime result should include:

```text
insights: VizaInsight[]
insight_relationships: RelationshipEdge[]
```

Radar rows may not fully show them yet; UI comes next.

## Frontend implementation

1. Add insight extractor node to finance palette.
2. Add basic insight list in result panel.
3. Add insight count per radar row.

## Tests

Create:

```text
tests/unit/test_viza_insights.py
```

Test:

- registry loads,
- rule-based insight extraction,
- insight evidence refs required,
- PIT cutoff enforced,
- insight relationships to event/attribute,
- insight exported into `.viza`,
- restricted evidence redacted.

## Exit criteria

- Runtime emits first-class insight objects.
- First wedge insight type works.
- Insights can be included in `.viza` containers.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `config/viza_insight_registry.json` with the initial insight type catalog.
- `viza/insights.py` with `VizaInsight`, registry loading, rule-based extraction, SQLite persistence, PIT cutoff filtering, query/get helpers, and export redaction/sanitization.
- Additive project-store `insights` table and diagnostics coverage.
- Insight endpoints for extract, query, and get.
- Finance module registration for `viza.finance.securities.insight_extractor`.
- Runtime `MethodologyRunResult` now includes `insights` and `insight_relationships`.
- Relationship-query enrichment with insight-family relationships.
- Frontend insight client/types plus a first-pass insight list scaffold.
- Tests for registry loading, rule extraction, evidence requirements, PIT cutoff, runtime/result relationships, `.viza` insight section export, restricted redaction, and store queries.

Verification:

```powershell
python -m pytest tests\unit\test_viza_insights.py tests\unit\test_viza_events.py tests\unit\test_viza_modules.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 56 focused Phase 24/module/runtime/service tests, 236 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 25 — Strategy Profile System

## Goal

Create strategy profiles as the user/domain lens through which insights are interpreted.

## Product requirement

The same information should translate differently depending on strategy. VIZA needs strategy profiles to represent the investor’s lens.

## Backend implementation

### 25.1 Create strategy profile schema

Create `viza/strategy_profiles.py`.

Model:

```python
class VizaStrategyProfile(BaseModel):
    schema: Literal["viza.strategy_profile.v1"]
    strategy_profile_id: str
    display_name: str
    domain: str
    module_id: str
    entity_types: list[str]
    universe_constraints: dict[str, Any]
    holding_period: dict[str, str]
    preferred_indicators: list[str]
    catalyst_types: list[str]
    required_confirmations: list[str]
    risk_limits: dict[str, Any]
    output_preferences: dict[str, Any]
    action_thresholds: dict[str, float]
    evidence_requirements: dict[str, Any]
    created_at: datetime
    updated_at: datetime
```

### 25.2 Add strategy profile tables

```sql
CREATE TABLE IF NOT EXISTS strategy_profiles (
  strategy_profile_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  module_id TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_profile_versions (
  version_id TEXT PRIMARY KEY,
  strategy_profile_id TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  profile_hash TEXT NOT NULL,
  parent_version_id TEXT,
  label TEXT,
  message TEXT,
  created_at TEXT NOT NULL
);
```

### 25.3 Seed first profile template

Add to config:

```text
config/viza_strategy_profile_templates.json
```

First template:

```text
RSI Swing + Catalyst Confirmation
```

Default logic:

```text
Domain: finance/securities
Universe: U.S. equities
Holding period: 2d-3w
Preferred indicators: rsi_14d, volume_spike, moving_average_reclaim, momentum
Catalysts: acquisition_rumor, earnings_surprise, analyst_upgrade, insider_purchase
Confirmations: source_credibility, volume_confirmation
Risk limits: avoid low liquidity, avoid extreme volatility
Output: radar + insight cards + invalidation conditions
```

### 25.4 Add strategy profile node

Register:

```text
viza.finance.securities.strategy_profile
```

This node should select or define a profile and feed it into insight translation.

### 25.5 Add endpoints

```text
GET  /viza/strategy-profiles
POST /viza/strategy-profiles
GET  /viza/strategy-profiles/{profile_id}
PUT  /viza/strategy-profiles/{profile_id}
POST /viza/strategy-profiles/{profile_id}/clone
GET  /viza/strategy-profile-templates
```

## Frontend implementation

### 25.6 Strategy profile builder

Add:

```text
StrategyProfileBuilder.tsx
```

Steps:

1. Choose domain/module.
2. Choose universe/candidate constraints.
3. Choose time horizon.
4. Choose preferred indicators.
5. Choose catalyst/event types.
6. Choose required confirmations.
7. Choose risk limits.
8. Choose evidence requirements.
9. Choose output preferences.
10. Save as profile.

### 25.7 Strategy profile node inspector

Node inspector should let users:

- select existing profile,
- clone template,
- edit thresholds,
- view evidence requirements.

## Tests

Create:

```text
tests/unit/test_viza_strategy_profiles.py
```

Test:

- profile template loads,
- create/update/clone profile,
- profile version hash stable,
- strategy profile node config validates,
- profile exports into `.viza`,
- imported profile can be forked.

Frontend:

- builder creates valid request,
- template loads,
- profile node inspector displays selected profile.

## Exit criteria

- First strategy profile template exists.
- Users can create or clone profiles.
- Strategy profiles can be attached to graphs and exported in `.viza`.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `config/viza_strategy_profile_templates.json` with the first RSI Swing + Catalyst Confirmation template.
- `viza/strategy_profiles.py` with `VizaStrategyProfile`, template loading, SQLite persistence, stable profile hashing, version records, create/update/clone, and template-backed creation.
- Additive project-store `strategy_profiles` and `strategy_profile_versions` tables plus diagnostics coverage.
- Strategy profile endpoints for list, create, get, update, clone, and template catalog.
- Finance module registration for `viza.finance.securities.strategy_profile` and core primitive support.
- Frontend strategy profile client/types plus first-pass builder and inspector scaffolds.
- Tests for template loading, create/update/clone, version hash stability, node config, `.viza` export, imported-profile fork, and endpoint round trips.

Verification:

```powershell
python -m pytest tests\unit\test_viza_strategy_profiles.py tests\unit\test_viza_modules.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 37 focused Phase 25/module/service/project-store tests, 242 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 26 — Insight Translation Engine And Strategy-Fit Output

## Goal

Translate insight objects through strategy profiles and produce strategy-fit explanations.

## Product requirement

VIZA should answer:

```text
Why does this information matter to this strategy?
What confirmation is missing?
What would invalidate it?
What action does it imply inside the user's workflow?
```

## Backend implementation

### 26.1 Create translation schema

Create `viza/translation.py`.

Model:

```python
class VizaTranslation(BaseModel):
    schema: Literal["viza.translation.v1"]
    translation_id: str
    insight_id: str
    strategy_profile_id: str
    entity_id: str
    asset_id: Optional[str]
    fit_score: float
    relevance: str
    translated_summary: str
    strategy_fit_reasons: list[str]
    missing_confirmations: list[str]
    risk_factors: list[str]
    invalidation_conditions: list[str]
    suggested_research_action: str
    evidence_refs: list[str]
    generated_at: datetime
    not_investment_advice: bool = True
```

### 26.2 Implement deterministic translation rules

Initial algorithm:

1. Load insight.
2. Load strategy profile.
3. Check domain/module compatibility.
4. Check insight type compatibility.
5. Check required attributes.
6. Check required confirmations.
7. Check evidence requirements.
8. Apply risk constraints.
9. Compute fit score.
10. Choose suggested action.
11. Generate explanation from templates.

Suggested fit score components:

```text
+ insight type compatibility
+ catalyst compatibility
+ technical confirmation strength
+ evidence confidence
+ source credibility
+ PIT safety
- missing confirmations
- risk flags
- low liquidity/extreme volatility
- restricted or weak evidence
```

### 26.3 Add translation endpoints

```text
POST /viza/translate
POST /viza/translate/batch
GET  /viza/translations/{translation_id}
```

### 26.4 Integrate with runtime

When a graph includes:

```text
Insight Extractor -> Strategy Profile -> Score/Output
```

runtime should emit:

```text
translations: VizaTranslation[]
```

### 26.5 Update radar rows

Add fields:

```text
strategy_fit_score
primary_insight_type
translated_summary
confidence
horizon
missing_confirmations
invalidation_conditions
risk_flags
evidence_count
source_restrictions
PIT_status
```

Do not remove existing fields.

## Frontend implementation

1. Show strategy-fit score in radar table.
2. Show translated summary column.
3. Add filters:
   - strategy-fit score,
   - insight type,
   - missing confirmations,
   - risk flags.
4. Add action labels:
   - watchlist,
   - research deeper,
   - alert candidate,
   - reject/ignore.

## Tests

Create:

```text
tests/unit/test_viza_translation.py
```

Test:

- same insight translates differently for two profiles,
- missing confirmations reduce score,
- weak evidence reduces score,
- invalidation conditions propagate,
- output includes not-investment-advice flag,
- radar row includes translated fields,
- translation exports with rights policies.

## Exit criteria

- Same insight can produce different output for different strategy profiles.
- RSI catalyst profile generates useful deterministic explanation.
- Radar rows include strategy-fit output.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `viza/translation.py` with deterministic `VizaTranslation` creation, batch translation, SQLite persistence, default strategy-profile translation, and restricted-export translation payloads.
- Additive project-store `translations` table plus diagnostics coverage.
- Translation endpoints for single insight translation, batch translation, and saved translation lookup.
- Runtime translation integration so extracted insights can produce strategy-fit output and radar-row translation fields without removing existing row fields.
- Frontend translation client/types plus first-pass `StrategyFitBadge` support.
- Tests for profile-specific translations, missing-confirmation and weak-evidence penalties, invalidation propagation, advice disclaimers, radar-row fields, and export rights policies.

Verification:

```powershell
python -m pytest tests\unit\test_viza_translation.py tests\unit\test_viza_insights.py tests\unit\test_viza_strategy_profiles.py tests\unit\test_viza_runtime.py tests\unit\test_viza_service.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 56 focused Phase 26/insight/profile/runtime/service/project-store tests, 249 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 27 — Insight Cards And Strategy-Fit Radar UI

## Goal

Make translated insights visible, inspectable, and actionable in the desktop app.

## Product requirement

The user should be able to inspect why a row surfaced, what evidence supports it, what confirmations are missing, and what would invalidate it.

## Frontend implementation

### 27.1 Add insight cards panel

Add:

```text
InsightCardsPanel.tsx
InsightCard.tsx
```

Each card shows:

```text
Header
  entity / asset
  insight type
  direction
  confidence
  horizon
  strategy fit score

Translation
  translated summary
  strategy fit reasons
  missing confirmations
  invalidation conditions
  suggested research action

Evidence
  source list
  evidence refs
  observed/available timestamps
  source credibility
  license/export status

Relationships
  related events
  related attributes
  related insights
  reinforcing/conflicting signals

Audit
  graph hash
  profile version
  run ID
  evidence checksum
  result checksum
```

### 27.2 Radar integration

Radar row click should open:

- existing evidence panel,
- relationship panel,
- new insight cards panel.

### 27.3 Filters and sorting

Add:

```text
strategy_fit_score
primary_insight_type
confidence
missing_confirmations
risk_flags
PIT_status
source_restrictions
```

### 27.4 Export handling

CSV/JSON export should respect rights:

- translated summaries may export if derived output policy allows,
- evidence text may redact,
- restricted raw source values redact,
- redaction records must show why.

## Backend support

Add a consolidated endpoint if needed:

```text
GET /viza/runs/{run_id}/insight-cards
```

This can be derived from run result payload initially.

## Tests

Frontend:

- insight card renders,
- radar row opens insight cards,
- missing confirmations render,
- invalidation conditions render,
- restricted evidence displays as redacted,
- filters work.

Backend:

- run insight-card payload contains required fields,
- export redaction applies.

## Exit criteria

- User can run RSI catalyst strategy and inspect translated insight cards.
- UI makes evidence, missing confirmations, invalidation, and risk visible.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `viza/insight_cards.py` with consolidated run insight-card payloads for translated insight, evidence, relationships, and audit fields.
- `/viza/runs/{run_id}/insight-cards` endpoint backed by saved run records.
- Desktop `InsightCard` and `InsightCardsPanel` wiring from selected radar rows to translated insight cards, evidence selection, relationship summaries, and audit identifiers.
- Strategy-fit radar columns for fit score, insight type, and translated summary.
- Radar filters and sorting for strategy-fit score, insight type, confidence, missing confirmations, risk flags, PIT status, and source restrictions.
- CSV/JSON export handling for strategy-fit row fields, insights/translations sections, restricted evidence redaction, and derived-summary redaction records.
- Tests for insight-card payload shape, saved-run endpoint payloads, strategy-fit CSV export fields, and JSON evidence redaction.

Verification:

```powershell
python -m pytest tests\unit\test_viza_insight_cards.py tests\unit\test_viza_translation.py tests\unit\test_viza_research_surfaces.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 31 focused Phase 27/translation/research-surface/service tests, 253 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 28 — Relationship Graph Universalization And Insight Reaction Graph

## Goal

Expand the relationship system from company-centered relationships to universal entity, event, insight, strategy-profile, and domain relationships.

## Product requirement

VIZA should reveal relationships and reactions between entities, attributes, events, and insights. The relationship graph is a key part of strategy reasoning.

## Backend implementation

### 28.1 Expand relationship families

Add:

```text
entity_to_entity
entity_to_attribute
entity_to_event
entity_to_insight
insight_to_event
insight_to_attribute
insight_to_strategy_profile
insight_confirms_insight
insight_conflicts_with_insight
insight_invalidates_insight
asset_to_provider_identifier
asset_to_corporate_action
asset_to_supplier
asset_to_customer
asset_to_owner
asset_to_peer
asset_to_macro_series
```

### 28.2 Update relationship schema

Ensure edges support:

```text
relationship_id
source_id
source_type
target_id
target_type
family
relationship_type
direction
confidence
weight
time_horizon
observed_at
available_at
evidence_refs
rights_policy
module_id
```

### 28.3 Add insight reaction rules

Rules examples:

```text
acquisition_rumor reinforces unusual_volume
insider_purchase reinforces momentum_breakout
regulatory_action invalidates acquisition_rumor
earnings_miss conflicts with bullish_social_sentiment
macro_liquidity_shock weakens small_cap_breakout_signal
```

Start deterministic and rule-based.

### 28.4 Update relationship query endpoint

Existing:

```text
POST /viza/relationships/query
```

Add filters:

```text
entity_id
asset_id
insight_id
event_id
family
source_type
target_type
min_confidence
time_horizon
PIT_only
relationship_type
```

## Frontend implementation

1. Update graph viewer node types:
   - entity,
   - asset,
   - event,
   - insight,
   - attribute,
   - strategy profile,
   - output.
2. Add filters for relationship family and object type.
3. Add edge labels:
   - confirms,
   - conflicts,
   - invalidates,
   - depends_on,
   - derived_from.
4. Add edge evidence inspector.

## Tests

Create/update:

```text
tests/unit/test_viza_relationships.py
```

Test:

- relationship query by insight,
- insight-to-event edges,
- insight-conflict edges,
- PIT filtering,
- source rights propagation,
- frontend graph renders new node types.

## Exit criteria

- Insight cards can show related events/attributes/insights.
- Relationship graph can center on an insight, not just a company.
- Universal entity relationship structure is compatible with future domains.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- Additive universal relationship fields on `RelationshipEdge`: IDs, source/target object IDs and types, universal family, time metadata, evidence refs, rights policy, and module ID.
- Relationship query filters for entity, asset, insight, event, family, source type, target type, confidence, time horizon, PIT-only mode, and relationship type while preserving legacy family filters.
- Insight-to-event, insight-to-strategy-profile, and deterministic insight reaction edges for confirming, conflicting, and invalidating insight relationships.
- Rights-policy and PIT timestamp propagation on derived relationship edges.
- Desktop relationship graph updates for universal node types, object-type filtering, universal family filtering, and edge labels.
- Tests for insight-centered queries, insight-to-event edges, invalidating insight reaction edges, PIT/confidence/object filtering, and legacy event-family compatibility.

Verification:

```powershell
python -m pytest tests\unit\test_viza_relationships.py tests\unit\test_viza_events.py tests\unit\test_viza_insights.py tests\unit\test_viza_service.py tests\unit\test_viza_runtime.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 47 focused Phase 28/event/insight/service/runtime tests, 258 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 29 — Validation Ledger And Proof Objects

## Goal

Create a durable validation ledger for strategy outputs and proof packaging.

## Product requirement

The validation ledger is the trust layer. It records outputs, evidence, checksums, data versions, model versions, PIT status, and later performance observations.

## Backend implementation

### 29.1 Create validation record schema

Create `viza/validation_ledger.py`.

Model:

```python
class VizaValidationRecord(BaseModel):
    schema: Literal["viza.validation_record.v1"]
    validation_record_id: str
    strategy_or_methodology_id: str
    strategy_profile_id: Optional[str]
    run_id: str
    graph_hash: str
    result_checksum: str
    timestamp_cutoff: datetime
    generated_at: datetime
    domain: str
    module_id: str
    entity_universe: dict[str, Any]
    outputs: list[dict[str, Any]]
    evidence_checksum: str
    data_versions: list[str]
    model_versions: list[str]
    connector_states: list[dict[str, Any]]
    PIT_summary: dict[str, Any]
    performance_observation: dict[str, Any]
    in_sample_out_of_sample_label: str
    warnings: list[dict[str, Any]]
```

### 29.2 Add validation tables

```sql
CREATE TABLE IF NOT EXISTS validation_records (
  validation_record_id TEXT PRIMARY KEY,
  strategy_or_methodology_id TEXT NOT NULL,
  strategy_profile_id TEXT,
  run_id TEXT NOT NULL,
  graph_hash TEXT NOT NULL,
  result_checksum TEXT NOT NULL,
  timestamp_cutoff TEXT,
  generated_at TEXT NOT NULL,
  domain TEXT,
  module_id TEXT,
  record_json TEXT NOT NULL
);
```

### 29.3 Add endpoints

```text
POST /viza/validation/record
GET  /viza/validation/{record_id}
POST /viza/validation/compare
POST /viza/validation/replay
GET  /viza/validation/by-run/{run_id}
```

### 29.4 Add proof section export

`.viza` should support:

```text
validation_proof -> proof/validation_manifest.json
```

Proof must include:

- run IDs,
- graph hash,
- result checksum,
- evidence checksum,
- PIT summary,
- data/model versions,
- connector states,
- output references,
- warnings.

### 29.5 Performance observation placeholder

Do not claim performance yet. Use pending records:

```json
"performance_observation": {
  "status": "pending",
  "evaluation_window": "2d-3w"
}
```

## Frontend implementation

1. Add validation panel in run/audit view.
2. Show proof status:
   - recorded,
   - pending observation,
   - replayable,
   - not replayable,
   - missing source data.
3. Allow export proof into `.viza`.

## Tests

Create:

```text
tests/unit/test_viza_validation_ledger.py
```

Test:

- record validation from run,
- compare validation records,
- replay/compare baseline,
- export proof,
- import proof,
- proof cannot fake missing checksum,
- proof honors source rights.

## Exit criteria

- Strategy outputs can be recorded over time.
- `.viza` can include validation proof.
- Proof is honest about pending performance observation.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `viza/validation_ledger.py` with `VizaValidationRecord`, record creation from run results or saved run IDs, SQLite ledger persistence, record comparison, replay comparison, proof export/import helpers, and checksum validation.
- Additive `validation_records` project-store table plus diagnostics coverage.
- Validation endpoints for record, get, compare, replay, and by-run lookup.
- `.viza` validation-proof section export/import support using the existing `validation_proof -> proof/validation_manifest.json` mapping, with credential-like entitlement keys sanitized from exported proof payloads.
- Pending performance-observation placeholder that explicitly avoids claiming completed performance.
- Desktop validation panel in the audit view with proof status, record action, and proof export action.
- Tests for record persistence, by-run lookup, comparison mismatch detection, replay comparison, service endpoints, proof export/import, checksum honesty, and source-rights proof behavior.

Verification:

```powershell
python -m pytest tests\unit\test_viza_validation_ledger.py tests\unit\test_viza_file_security.py tests\unit\test_viza_file_format.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 41 focused Phase 29/file/security/project-store/diagnostics/service tests, 265 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 30 — White-Box, Gray-Box, Black-Box, And Output-Only Packaging

## Goal

Support creator-owned strategy exchange without requiring full transparency.

## Product requirement

The same `.viza` extension should support white-box, gray-box, black-box, output-only, and preview-only exchange through manifest visibility and section statuses.

## Backend implementation

### 30.1 Add packaging policies

Create:

```text
viza/file_format/packaging.py
```

Packaging modes:

```text
white_box
gray_box
black_box
output_only
preview_only
```

### 30.2 Define redaction behavior

| Visibility | Graph | Parameters | Outputs | Proof | Notes |
|---|---|---|---|---|---|
| white_box | included | included | optional | optional | optional |
| gray_box | included/redacted subgraphs | redacted thresholds/weights | optional | included if allowed | optional |
| black_box | redacted | redacted | included | included if allowed | high-level only |
| output_only | absent/redacted | redacted | included | optional | limited |
| preview_only | absent/redacted | redacted | sample only | optional | summary |

### 30.3 Ensure redacted content is not recoverable

Redaction means the content is not in the ZIP, not merely hidden by UI.

Rules:

- remove section payload,
- set status `redacted`,
- set reason,
- remove raw config values,
- remove proprietary notes,
- replace with safe summary if allowed,
- recompute checksums.

### 30.4 Entitlement-locked behavior

For now, entitlement-locked sections should not be bundled unless an encryption/entitlement system exists.

Use manifest metadata:

```json
{
  "status": "entitlement_locked",
  "reason": "creator_permission_required",
  "required_entitlement": "strategy_subscription"
}
```

### 30.5 Update export wizard backend

Export request should include:

```text
visibility
include_validation_proof
include_signal_outputs
include_sample_outputs
redact_parameters
lock_sections
```

### 30.6 Add permission enforcement

On import/open:

- fork disabled if `fork_allowed=false`,
- export disabled if `export_allowed=false`,
- run disabled if `run_allowed=false`,
- hidden sections not readable,
- black-box graph not exposed.

## Frontend implementation

1. Export wizard visibility step.
2. Redaction preview.
3. Locked-section preview.
4. File viewer badges:
   - white-box,
   - gray-box,
   - black-box,
   - output-only,
   - preview-only.
5. Disable actions based on permissions.

## Tests

Backend:

- white-box includes graph,
- gray-box redacts parameters,
- black-box excludes graph,
- output-only includes outputs only,
- redacted content absent from ZIP,
- permissions disable actions,
- redacted sections cannot be read via API.

Frontend:

- export wizard shows visibility implications,
- file viewer disables forbidden actions,
- locked/redacted badges render.

## Exit criteria

- Creator can export white-box, gray-box, black-box, and output-only `.viza` packages.
- Redacted data is not recoverable from file bytes.
- Import/open respects permissions.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `viza/file_format/packaging.py` with packaging policies for white-box, gray-box, black-box, output-only, and preview-only exports.
- ZIP-level section redaction/locking so redacted or entitlement-locked graph payloads are not written into containers.
- Gray-box graph parameter redaction for weights, thresholds, proprietary notes, and formula-like config keys.
- Output and preview package placeholders for output-only/black-box/preview-only modes without bundling raw graph content.
- Extended file export request fields for visibility, validation proof, signal/sample outputs, parameter redaction, and locked sections.
- Import/open permission enforcement so black-box/output-only packages can be inspected without exposing graphs and cannot be forked/imported as readable methodology graphs.
- File visualization action filtering and desktop export/viewer controls for visibility implications, redaction previews, locked sections, visibility badges, and disabled forbidden actions.
- Tests for white-box graph inclusion, gray-box parameter redaction, black-box graph exclusion, output-only payloads, entitlement locking, redacted-section unreadability, and import permission enforcement.

Verification:

```powershell
python -m pytest tests\unit\test_viza_packaging.py tests\unit\test_viza_file_security.py tests\unit\test_viza_file_format.py tests\unit\test_viza_file_import_export.py tests\unit\test_viza_file_visualization.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 39 focused Phase 30/file/security/import-export/visualization/service tests, 271 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 31 — First Non-Finance Module Smoke Test: Real Estate Acquisition

## Goal

Prove that `.viza` is a universal strategy container and not a securities-only file format.

## Product requirement

VIZA should be able to expand to domains such as real estate, corporate strategy, soccer, hiring, and product strategy. Real estate is the first non-finance smoke test because it is strategy-heavy and structurally similar enough to finance to validate the module architecture.

## Scope

Do not build a full real estate product.

Build a minimal real estate acquisition module that proves:

- module-defined block set,
- module-defined entity types,
- module-defined output views,
- graph visualization,
- local CSV data source,
- safe `.viza` import/export,
- missing-module placeholder behavior.

## Backend implementation

### 31.1 Create module manifest

Add:

```text
config/viza_modules/viza.real_estate.acquisition.json
```

Module ID:

```text
viza.real_estate.acquisition
```

Entity types:

```text
property
parcel
market
tenant
lease
loan
sponsor
```

Node types:

```text
property_universe
market_filter
comparable_sales
rent_roll
noi_model
cap_rate_filter
debt_terms
dscr_gate
renovation_budget
exit_scenario
deal_score
deal_pipeline
investment_memo
```

### 31.2 Register module behind feature flag

Only enable when:

```text
VIZA_ENABLE_NON_FINANCE_MODULES=true
```

### 31.3 Implement minimal runtime handlers

Use local CSV only.

Required CSV fields for smoke test:

```text
property_id
property_name
market
property_type
units
asking_price
noi
cap_rate
rent_growth_assumption
expense_growth_assumption
debt_rate
loan_to_value
```

Handlers:

- `property_universe`: load property records,
- `noi_model`: compute simple NOI projection,
- `dscr_gate`: pass/fail based on DSCR,
- `deal_score`: weighted score,
- `deal_pipeline`: table output,
- `investment_memo`: Markdown/JSON summary output.

### 31.4 `.viza` export/import

Export a real estate graph as `.viza` with:

```text
required_modules = [viza.core.strategy, viza.real_estate.acquisition]
sections.methodology_graph.schema = viza.graph.v1 or temporary module-aware graph schema
```

If graph schema v1 is not ready, use a module-aware JSON payload under `graph/methodology.json` and mark current runtime support as experimental.

### 31.5 Missing module round-trip test

Create a `.viza` requiring `viza.real_estate.acquisition`, open it with module disabled, render placeholders, save/export, then re-open with module enabled and confirm raw config preserved.

## Frontend implementation

1. Add module palette group:

   ```text
   Real Estate Acquisition
   ```

2. Add property-oriented node labels.
3. Add deal pipeline output view.
4. Add investment memo output view.
5. Ensure no finance-specific UI assumptions break.

## Tests

Create:

```text
tests/unit/test_viza_real_estate_module.py
```

Test:

- module loads,
- sample property graph validates,
- local CSV property universe loads,
- deal score runs,
- investment memo generated,
- `.viza` export/import works,
- missing module placeholders preserve config.

Frontend:

- real estate palette appears when flag enabled,
- placeholder appears when module disabled,
- deal pipeline renders.

## Exit criteria

- VIZA opens and visualizes a non-securities strategy file.
- Core `.viza` format proves domain expansion.
- Current finance functionality remains intact.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- `config/viza_modules/viza.real_estate.acquisition.json` and `viza/modules/real_estate_acquisition.py` for the feature-flagged real estate acquisition module.
- Module registry support behind `VIZA_ENABLE_NON_FINANCE_MODULES=true`.
- Minimal local-CSV real estate runtime in `viza/real_estate.py` for property universe loading, NOI projection, DSCR gate, deal scoring, deal pipeline output, and investment memo output.
- Experimental module-aware real estate `.viza` export/import using `graph/methodology.json` and required modules `[viza.core.strategy, viza.real_estate.acquisition]`.
- Missing-module placeholder behavior for disabled non-finance modules.
- Desktop real estate deal pipeline and investment memo view scaffolds.
- Tests for module loading/feature flag behavior, CSV universe loading, deal scoring, investment memo generation, `.viza` export/import, and placeholder config preservation.

Verification:

```powershell
python -m pytest tests\unit\test_viza_real_estate_module.py tests\unit\test_viza_modules.py tests\unit\test_viza_file_format.py tests\unit\test_viza_packaging.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 21 focused Phase 31/module/file/packaging tests, 277 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 32 — Source-Backed Resolver Promotion For First Wedge

## Goal

Promote the first wedge from prototype/demo values to credible source-backed values where connectors are configured.

## Product requirement

The first wedge remains U.S. equities + event-driven catalysts + technical confirmation. The app should support source-backed technical overlays and initial event data while keeping data rights visible.

## Backend implementation

### 32.1 Choose initial production-ish data path

Recommended order:

1. Local CSV OHLCV.
2. SEC EDGAR public metadata where implemented.
3. FMP or similar provider if user configures credentials.
4. Local news/events CSV.

### 32.2 Promote specific resolvers

Promote:

```text
rsi_14d
momentum
moving_average_trend
volume_spike
realized_volatility
short_term_reversal
sector_relative_strength where sector data exists
AAT residual return if local AAT data exists
```

### 32.3 Event source-backed path

Implement first source-backed event paths:

- SEC filing novelty from filing metadata,
- analyst/news/social event from local CSV,
- insider transaction from local CSV or provider if available,
- unusual volume from OHLCV.

### 32.4 Rights-aware derived values

Every source-backed value must carry:

```text
connector_id
source_id
license_policy
cache_policy
display_policy
export_policy
derived_value_policy
redistribution_policy
attribution_required
retention_policy
```

### 32.5 Update diagnostics

Diagnostics should show:

- source-backed resolver count,
- prototype fallback count,
- credential-ready connector count,
- observation store status,
- last resolver warning count.

## Frontend implementation

1. Attribute picker should distinguish:
   - source-backed,
   - prototype fallback,
   - evidence-only,
   - restricted export.
2. Result evidence should show source-backed values more prominently.
3. Missing source configuration should show a connector mapping path.

## Tests

- source-backed RSI from sample CSV,
- volume spike from OHLCV,
- filing event from sample metadata,
- local events CSV extraction,
- export redaction respects source policy,
- fallback warnings remain explicit.

## Exit criteria

- First wedge can run with source-backed technical overlays.
- Event extraction can use at least one source-backed path.
- Prototype values remain clearly labeled when used.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- Source-backed technical registry entries for `rsi_14d`, `moving_average_trend`, `volume_spike`, and `sector_relative_strength`, with connector mapping metadata for missing-source UI states.
- Local OHLCV CSV parsing and richer local-source rights defaults for observation ingestion.
- Observation-backed resolver rights completion for connector/source/license/cache/display/export/derived/redistribution/attribution/retention policy fields.
- Source-backed event extraction in `viza/source_events.py` for SEC filing metadata CSV, local events CSV, and unusual-volume events derived from OHLCV.
- Runtime diagnostics for source-backed resolver count, prototype fallback count, credential-ready connector count, observation-store status, and last resolver warning count.
- Export redaction that honors source rights policy even when entitlement policy otherwise allows export.
- Desktop attribute/evidence badges for source-backed, prototype fallback, evidence-only, and restricted-export states, plus source mapping display.
- Phase 32 focused test coverage in `tests/unit/test_viza_source_backed_resolvers.py`.

Verification:

```powershell
python -m pytest tests\unit\test_viza_source_backed_resolvers.py tests\unit\test_viza_observations.py tests\unit\test_viza_attribute_resolvers.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_events.py tests\unit\test_viza_research_surfaces.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 30 focused Phase 32/observation/resolver/diagnostics/event/research-surface tests, 284 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 33 — Large-Data Runtime, Streaming Progress, Cancellation, Scheduler, And Caches

## Goal

Prepare the runtime for larger universes, recurring radars, and long-running jobs.

## Product requirement

The current runtime works locally but future workflows need streaming progress, durable cancellation, scheduled refresh, and caching.

## Backend implementation

### 33.1 Job model

Add job tables:

```sql
CREATE TABLE IF NOT EXISTS runtime_jobs (
  job_id TEXT PRIMARY KEY,
  project_id TEXT,
  job_type TEXT NOT NULL,
  status TEXT NOT NULL,
  request_json TEXT NOT NULL,
  progress_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0,
  result_ref TEXT,
  warnings_json TEXT NOT NULL DEFAULT '[]'
);
```

### 33.2 Streaming progress endpoint

Add:

```text
POST /viza/jobs
GET  /viza/jobs/{job_id}
POST /viza/jobs/{job_id}/cancel
GET  /viza/jobs/{job_id}/events
```

Events may use polling first, SSE later.

### 33.3 Durable cancellation

Runtime should check cancellation between:

- node execution,
- universe chunks,
- connector calls,
- batch cutoffs.

### 33.4 Cache layer

Use existing cache-key concepts from batch phase.

Cache keys should include:

```text
node_id
graph_hash
module_id
universe_version
timestamp_cutoff
attribute_versions
source_versions
connector_states
strategy_profile_hash where relevant
```

### 33.5 Scheduler refresh

Add scheduler definitions but keep execution local:

```text
manual
daily
weekly
on_app_start
```

No background cloud service yet.

## Frontend implementation

1. Add progress panel for long runs.
2. Add cancel button.
3. Add scheduler UI for saved radars.
4. Add cache hit/miss diagnostics.

## Tests

- job creation,
- progress updates,
- cancellation,
- cache hit for identical run,
- cache miss when source version changes,
- scheduler definition persists.

## Exit criteria

- Long-running VIZA jobs no longer block UI.
- User can cancel running jobs.
- Saved radars can define refresh schedules locally.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- SQLite-backed runtime job tables for jobs, job events, cache entries, and radar schedules.
- `viza/runtime_jobs.py` with runtime job records, progress events, durable cancellation requests, background job launch, methodology/batch job execution, cache key construction, cache hit/miss persistence, and schedule records.
- Local job endpoints: `POST /viza/jobs`, `GET /viza/jobs/{job_id}`, `POST /viza/jobs/{job_id}/cancel`, `GET /viza/jobs/{job_id}/events`, and project job listing.
- Local scheduler endpoints for saved radars under `/viza/projects/{project_id}/schedules`.
- Runtime cache keys that include graph hash, node id, module id, universe version, timestamp cutoff, attribute versions, source versions, connector states, and strategy profile hash.
- Desktop run flow moved to runtime jobs with polling progress, cancel action, cache hit/miss diagnostics, and run-result hydration from saved run records.
- Desktop scheduler UI for saved radar refresh cadence (`manual`, `daily`, `weekly`, `on_app_start`).
- Phase 33 focused tests in `tests/unit/test_viza_runtime_jobs.py`.

Verification:

```powershell
python -m pytest tests\unit\test_viza_runtime_jobs.py tests\unit\test_viza_batch.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 34 focused Phase 33/batch/project-store/diagnostics/service tests, 289 full Python unit/look-ahead tests, TypeScript typecheck clean, and 14 desktop tests.

---

# Phase 34 — Release Packaging And Installer Hardening

## Goal

Move from development package readiness to user-distributable builds.

## Product requirement

VIZA should eventually ship as reliable Windows and macOS desktop software.

## Backend / packaging implementation

### 34.1 Fully bundled engine runtime

Build and package a Python engine sidecar for Windows and macOS.

The app should prefer bundled sidecar and avoid system Python for production builds.

### 34.2 Windows installer

Add:

- signed installer path,
- installer smoke tests,
- uninstall behavior,
- app data preservation,
- engine sidecar included.

### 34.3 macOS signed/notarized artifact

Use existing macOS automation on a macOS build machine with Apple credentials.

Verify:

- hardened runtime,
- notarization,
- stapler validation,
- Gatekeeper assessment,
- engine sidecar signed.

### 34.4 Diagnostics hardening

Diagnostics should include:

- file-format version,
- installed module list,
- credential mode,
- observation store health,
- `.viza` import/export health,
- last quarantine event.

## Frontend implementation

1. Add app update placeholder if desired.
2. Improve diagnostics panel for support use.
3. Add export diagnostics bundle, ensuring no secrets.

## Tests

```powershell
cd apps\viza-desktop
npm run package:win
npm run smoke:package
```

On macOS build host:

```bash
npm run release:mac
```

## Exit criteria

- Windows user package does not require system Python.
- macOS artifact can be produced externally with signing/notarization.
- Diagnostics show module/file-format health.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- PyInstaller-based engine sidecar build script for packaged desktop builds, with Windows output at `packaging/engine/viza-engine.exe` and macOS/Linux output at `packaging/engine/viza-engine`.
- Desktop packaging now includes the bundled engine sidecar as an Electron extra resource and production engine launch prefers the sidecar over system Python.
- Windows release preflight checks for signing configuration, allows unsigned local packaging by default, can require signing credentials for release automation, and validates package execution on Windows unless explicitly cross-platform overridden.
- Windows `package:win` now builds the engine sidecar, builds the app, and emits both `win-unpacked` and NSIS installer artifacts while preserving app data on uninstall.
- Package smoke tests now verify the bundled engine sidecar and installer artifact are present.
- macOS release smoke/preflight paths include sidecar signing verification on macOS build hosts.
- Runtime diagnostics now report file-format version, installed modules, credential mode, observation store health, `.viza` import/export health, and last quarantine event.
- Desktop diagnostics panel now summarizes module/file-format/observation/quarantine health and exports a redacted diagnostics bundle.

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

Result: passed with a Windows sidecar-backed NSIS package and smoke check, 289 full Python unit/look-ahead tests, TypeScript typecheck clean, and 17 desktop tests. `npm run release:mac` remains a macOS build-host verification path because signing/notarization require macOS and Apple credentials.

---

# Phase 35 — Marketplace Readiness Guardrails, Not Marketplace Launch

## Goal

Prepare the data structures and safety controls that would eventually support marketplace use without launching monetization.

## Product requirement

Marketplace should not launch until validation, compliance, rights, and anti-overfitting controls are credible.

## Backend implementation

### 35.1 Creator identity placeholder

Add creator records:

```sql
CREATE TABLE IF NOT EXISTS creator_records (
  creator_id TEXT PRIMARY KEY,
  display_name TEXT,
  verification_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
```

### 35.2 Marketplace draft package mode

Allow `.viza` export purpose:

```text
marketplace_draft
```

This does not publish anything.

It only packages:

- manifest,
- allowed summary,
- proof if available,
- permissions,
- rights summary,
- creator placeholder,
- compliance warning labels.

### 35.3 Compliance warning system

Warnings:

```text
not_investment_advice_missing
performance_claim_unverified
source_data_redistribution_forbidden
rumor_data_unverified
black_box_without_proof
insufficient_out_of_sample_history
lookahead_risk_detected
```

### 35.4 Marketplace readiness scoring

Do not expose as “quality score” to users yet. Use internal readiness checklist:

```text
validation_record_count
out_of_sample_candidate_count
data_leakage_checks_passed
source_rights_passed
creator_identity_present
proof_available
redaction_safe
performance_observation_pending_or_complete
```

## Frontend implementation

1. Add marketplace-draft export purpose.
2. Show compliance checklist.
3. Do not add buy/sell/subscription UI.

## Tests

- marketplace draft export created,
- restricted source blocks marketplace draft,
- black-box without proof gets warning,
- no monetization endpoint exists,
- compliance warnings stored in manifest.

## Exit criteria

- VIZA can package marketplace drafts for review.
- No monetized marketplace is launched.
- Compliance and validation gaps are visible.

## Status

Implemented and verified on 2026-05-12.

Delivered:

- SQLite-backed `creator_records` table plus creator record persistence helpers and local creator endpoints.
- `marketplace_draft` `.viza` export purpose that emits a review-only package with manifest metadata, allowed summary, rights summary, creator placeholder, compliance warning labels, readiness checklist, permissions, and validation proof when available.
- Marketplace draft packages redact the full methodology graph and disable run/fork/export/redistribution/publish permissions by default.
- Source-rights enforcement blocks marketplace draft export when explicit source policies forbid redistribution or marketplace packaging.
- Compliance warning system for not-investment-advice labels, unverified performance claims, forbidden redistribution, rumor/social sources, black-box-without-proof, insufficient out-of-sample history, and look-ahead risk.
- Internal readiness checklist for validation count, out-of-sample evidence, leakage checks, source rights, creator identity, proof availability, redaction safety, and performance observation status.
- Desktop export wizard now exposes marketplace draft purpose, creator placeholder input, not-investment-advice acknowledgement, and a compliance checklist. File visualization can surface compliance warnings and readiness status.
- No buy/sell/subscription/checkout/payment endpoints or UI were added.

Verification:

```powershell
python -m pytest tests\unit\test_viza_marketplace.py tests\unit\test_viza_packaging.py tests\unit\test_viza_file_format.py tests\unit\test_viza_project_store.py tests\unit\test_viza_diagnostics.py tests\unit\test_viza_service.py
python -m pytest tests\unit tests\lookahead_audit
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 39 focused Phase 35/packaging/file/project-store/diagnostics/service tests, 294 full Python unit/look-ahead tests, TypeScript typecheck clean, and 17 desktop tests.

---

## 6. Suggested Release Milestones

### Milestone v0.2 — Universal File And Module Foundation

Includes:

- Phase 16 baseline lock,
- Phase 17 `.viza` container,
- Phase 18 module registry,
- Phase 19 file viewer/import/export.

User-visible result:

```text
Users can export, open, inspect, import, and fork `.viza` files.
Current stock methodology graphs become portable `.viza` strategy documents.
```

### Milestone v0.3 — Finance Wedge With Strategy Translation

Includes:

- entity/security master seed,
- observation store,
- event model,
- insight model,
- strategy profiles,
- translation engine,
- insight cards.

User-visible result:

```text
VIZA can run a U.S. equity RSI + catalyst strategy and explain why each insight fits that strategy.
```

### Milestone v0.4 — Trust Layer And Packaging

Includes:

- validation ledger,
- proof export,
- gray/black-box packaging,
- stronger source-backed resolvers,
- rights enforcement.

User-visible result:

```text
VIZA strategy files can carry proof, redactions, locked sections, and output-only packages safely.
```

### Milestone v0.5 — Universal Strategy Medium Proof

Includes:

- real estate acquisition module smoke test,
- missing-module round-trip,
- module-aware UI and output views.

User-visible result:

```text
VIZA can open and visualize a non-securities strategy file, proving the format is universal.
```

### Milestone v1.0 Candidate — Reliable Local Strategy Software

Includes:

- release-grade packaging,
- bundled engine,
- source-backed first wedge,
- validation ledger,
- secure credential storage,
- large-job runtime,
- diagnostics.

User-visible result:

```text
VIZA can be used as a local-first strategy design, execution, validation, and exchange environment.
```

---

## 7. Developer Checklist By Workstream

### Backend schemas

- [ ] `viza.document.v1`
- [ ] `viza.module_manifest.v1`
- [ ] `viza.entity.v1`
- [ ] `viza.asset.v1`
- [ ] `viza.observation.v1`
- [ ] `viza.event.v1`
- [ ] `viza.insight.v1`
- [ ] `viza.strategy_profile.v1`
- [ ] `viza.translation.v1`
- [ ] `viza.validation_record.v1`

### Backend services

- [ ] file inspection/import/export
- [ ] module registry
- [ ] entity resolution
- [ ] asset/security master
- [ ] observation store
- [ ] credential vault
- [ ] event extraction
- [ ] insight extraction
- [ ] strategy profile management
- [ ] translation engine
- [ ] validation ledger
- [ ] packaging/redaction policy

### Frontend surfaces

- [ ] `.viza` file viewer
- [ ] contents map
- [ ] compatibility panel
- [ ] strategy exchange inbox
- [ ] export wizard
- [ ] module-aware palette
- [ ] unknown node placeholder
- [ ] entity/asset resolver panel
- [ ] connector credential UI
- [ ] strategy profile builder
- [ ] insight cards panel
- [ ] validation proof panel
- [ ] real estate module smoke UI

### Runtime integration

- [ ] legacy graph wrapper
- [ ] module-type adapter
- [ ] implicit asset resolution for legacy graphs
- [ ] event node execution
- [ ] insight extractor node execution
- [ ] strategy profile node execution
- [ ] translation output generation
- [ ] radar row enrichment
- [ ] validation record generation

### Security

- [ ] zip path traversal blocked
- [ ] executable payload blocked
- [ ] manifest-first inspection
- [ ] section checksum validation
- [ ] no credentials in files
- [ ] redacted content absent from ZIP
- [ ] entitlement-locked content inaccessible
- [ ] unknown modules safe
- [ ] suspicious files quarantined

### Data rights

- [ ] rights metadata on observations
- [ ] rights metadata on events
- [ ] rights metadata on insights
- [ ] rights metadata on translations
- [ ] export redaction checks
- [ ] marketplace draft rights checks
- [ ] source attribution requirements recorded

---

## 8. Critical Risks And Mitigations

### Risk 1: VIZA becomes finance-bound despite universal claims

Mitigation:

- Rename core concepts to entity/candidate/decision/output.
- Keep asset/security only inside finance module.
- Build real estate smoke module before marketplace work.

### Risk 2: `.viza` files become unsafe

Mitigation:

- Manifest-first inspection.
- Reject arbitrary code.
- Signed/trusted modules only.
- Unknown modules render placeholders.
- ZIP path traversal tests.

### Risk 3: Redacted files leak proprietary logic

Mitigation:

- Redaction means content absent from ZIP.
- Byte-level tests confirm hidden values are not present.
- Manifest records redaction reason only.

### Risk 4: Data provider rights are violated

Mitigation:

- Rights metadata attached to every derived value.
- Export wizard performs rights check.
- Restricted data redacted from `.viza`.
- Marketplace draft blocked when redistribution is forbidden.

### Risk 5: Strategy translation produces overconfident advice

Mitigation:

- Use research-action language, not trading commands.
- Include not-investment-advice flag.
- Show evidence, confidence, missing confirmations, invalidation conditions.
- Avoid marketplace until validation and compliance are credible.

### Risk 6: Current implementation regresses

Mitigation:

- Keep legacy graph support.
- Add adapters instead of rewrites.
- Run full unit/lookahead and frontend tests each phase.
- Keep current canvas UX stable until replacement is proven.

---

## 9. Final Definition Of Done For This Plan

The implementation plan is complete when VIZA can do all of the following:

1. Preserve all current Phase 0-15 functionality.
2. Export a current methodology graph as a `.viza` file.
3. Open a `.viza` file whose filename is arbitrary.
4. Inspect the manifest before loading sections.
5. Visualize file contents inside the VIZA app.
6. Detect required modules.
7. Render unknown modules as safe placeholders.
8. Treat current securities blocks as `viza.finance.securities`.
9. Store and resolve universal entities.
10. Resolve finance tickers to canonical asset IDs.
11. Store point-in-time observations.
12. Emit event/catalyst objects.
13. Emit insight objects.
14. Define and use strategy profiles.
15. Translate insights into strategy-fit explanations.
16. Show insight cards and strategy-fit radar rows.
17. Record validation proof.
18. Export white-box, gray-box, black-box, and output-only `.viza` packages.
19. Prove non-finance expansion with a real estate acquisition module smoke test.
20. Maintain source rights, audit, evidence, checksums, and point-in-time discipline throughout.

---

## 10. Immediate Next Actions

Start with these actions in order:

1. Run full current test suite and record baseline.
2. Add compatibility policy and feature flags.
3. Create `viza/file_format/` package.
4. Implement `viza.document.v1` manifest model.
5. Implement safe ZIP read/write and checksum utilities.
6. Wrap current `viza_graph_v0` graph into `.viza`.
7. Add `/viza/files/inspect`, `/viza/files/export`, and `/viza/files/import`.
8. Add module registry with `viza.core.strategy` and `viza.finance.securities`.
9. Add file viewer UI.
10. Add export wizard.

Do not start event/insight/translation work until `.viza` container and module registry are stable enough to hold those objects.
