# VIZA `specs.md`

Last updated: 2026-05-12
Version: v0.4 - universal `.viza` strategy-exchange direction
Status: Build specification for the next VIZA program on top of the existing Phase 0-15 prototype

---

## 0. Executive Summary

VIZA is a local-first desktop research methodology platform for investors. The current prototype already supports a methodology canvas, graph execution, radar output, evidence, relationships, project storage, versioning, backtesting, export redaction, diagnostics, and package readiness. The next version should build on that foundation and move VIZA toward its sharper strategic direction:

```text
VIZA translates market information into the language of each investor's strategy.
```

The new program should introduce a universal `.viza` file as the core medium for exchanging strategies, research methodologies, insight objects, radars, validation proofs, black-box outputs, and future marketplace packages.

The `.viza` file must not depend on the filename to explain what it contains. The filename can be arbitrary. The VIZA desktop program is responsible for opening the file, validating it, visualizing its contents, showing its internal modes, checking data requirements, and offering the correct actions.

Core product principle:

```text
Outsource commodity data. Own the meaning.
```

VIZA should use external providers for raw financial data, but own the canonical asset identity layer, methodology graph, insight ontology, strategy profile layer, translation engine, validation ledger, entitlement model, and exchange-file format.

---

## 1. Non-Negotiable Product Decisions

These decisions should guide the next implementation.

### 1.1 VIZA is not a raw data vendor

VIZA should not try to manually populate every raw asset datapoint. It should outsource commodity data such as prices, fundamentals, filings, transcripts, news, macro series, options chains, and other provider-owned datasets.

VIZA should own the normalized, point-in-time, strategy-aware layer built on top of that data.

VIZA owns:

- methodology graphs,
- strategy profiles,
- insight objects,
- insight ontology,
- translation rules,
- evidence records,
- validation ledger,
- canonical asset database,
- provider identifier maps,
- user-created radars,
- user-created watchlists,
- audit manifests,
- exchange-file format,
- creator and marketplace packaging rules.

### 1.2 VIZA should use one universal `.viza` extension

The new strategy-exchange format should use a single file extension:

```text
.viza
```

Do not create separate extensions such as `.vizamethod`, `.vizaradar`, `.vizainsight`, `.vizaproof`, or `.vizasignal`.

All exchange modes should be represented inside the `.viza` file manifest and internal sections.

### 1.3 The filename does not need to describe the contents

The user does not need to know what the file entails before opening it.

The `.viza` filename may be:

```text
my_strategy.viza
weekly_catalyst_pack.viza
johns_research_file.viza
2026-05-12-output.viza
```

The VIZA program must inspect and visualize the internal file structure after opening. The source of truth is the internal manifest, not the filename.

### 1.4 Do not rely on blank fields for missing exchange modes

A `.viza` file may not include every possible section. However, missing sections should not be represented only as blank values.

Instead, every optional section should have an explicit status:

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

This avoids ambiguity between:

- not applicable,
- missing by mistake,
- intentionally hidden,
- locked by entitlement,
- removed because of data-rights restrictions,
- external but not bundled,
- unsupported by the current app version,
- corrupted.

### 1.5 VIZA files are visualized by the app

Opening a `.viza` file should show a visual VIZA file environment, not just raw JSON.

The app should display:

- file summary,
- contents map,
- methodology graph if included,
- insight cards if included,
- radar/table output if included,
- validation proof if included,
- data requirements,
- missing connectors,
- permissions,
- entitlement restrictions,
- creator identity if available,
- signatures and checksums,
- import actions.

### 1.6 Strategy exchange does not require full transparency

VIZA should support white-box, gray-box, black-box, and output-only strategy exchange.

The same `.viza` extension should support all of them.

Visibility is an internal permission and manifest property, not a file-extension property.

### 1.7 The first strategic wedge remains narrow

The first strategic wedge should remain:

```text
U.S. equities + event-driven catalysts + technical confirmation.
```

The first strategy-profile template should be:

```text
RSI swing strategy + catalyst confirmation.
```

The first event/catalyst families should include:

- acquisition rumors,
- confirmed M&A announcements,
- earnings surprises,
- analyst upgrades/downgrades,
- insider transactions,
- unusual volume and liquidity events,
- regulatory events,
- SEC filing novelty,
- management commentary changes,
- news and social sentiment shifts,
- sector or peer contagion events.

The first technical overlays should include:

- RSI,
- momentum,
- moving-average trend,
- volume spike,
- realized volatility,
- short-term reversal,
- peer-relative return,
- market beta,
- sector-relative strength,
- AAT residual return.

### 1.8 The marketplace is future work

The marketplace should not be implemented until the following are credible:

- insight objects,
- strategy profiles,
- strategy translation,
- validation ledger,
- point-in-time data discipline,
- anti-overfitting controls,
- data-rights enforcement,
- creator identity/reputation,
- compliance review.

The early product should support file exchange and local validation first. Monetization can follow later.

---

## 2. Existing Implementation Baseline

The next version must build on the current implementation, not replace it.

### 2.1 Current app stack

Current implemented stack:

```text
Desktop shell: Electron
Frontend: React + TypeScript + React Flow
Engine: Python FastAPI local service
Storage: local SQLite project store
Package: Windows unpacked dev package; macOS release automation scripts/config
```

Current key paths:

```text
apps/viza-desktop/                 desktop workspace
viza/                              Python graph/runtime package
config/viza_attribute_registry.json starter attribute registry
docs/VIZA_*.md                     VIZA documentation
```

### 2.2 Current graph contract

Current durable graph schema:

```text
viza_graph_v0
```

Current node types:

```text
universe
attribute
transform
filter
score
relationship
output_radar
```

Current edge types:

```text
data_flow
relationship
evidence
```

### 2.3 Current implemented capabilities

The prototype already supports:

- blank methodology canvas as first screen,
- toolbar-driven node creation and canvas node dragging,
- typed edge validation,
- graph save/load/new flows,
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
- 73 attributes in registry version `1.1.0`,
- searchable attribute picker,
- connector and entitlement catalog,
- local CSV connector path,
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
- batch progress event payloads,
- cooperative batch cancellation before remaining runs,
- batch cache-key metadata,
- point-in-time cutoff checks,
- radar designer,
- CSV/JSON/manifest/methodology exports,
- diagnostics endpoint,
- desktop diagnostics panel,
- local engine restart,
- Windows unpacked packaging,
- macOS release automation scripts.

### 2.4 Current known gaps

The next version should prioritize these gaps:

- universal `.viza` file container,
- `.viza` open/import/export/visualization workflow,
- native OS credential vault storage,
- source-backed production resolvers for high-value attributes,
- canonical asset/security master,
- point-in-time observation store,
- first-class event/catalyst objects,
- first-class insight object output,
- strategy profile nodes,
- strategy translation engine,
- strategy-fit radar explanations,
- company-to-insight relationship edges,
- black-box/gray-box strategy packaging,
- validation ledger for strategy outputs,
- source-data reproducibility,
- signed Windows installer,
- signed/notarized macOS artifact from macOS build host,
- fully bundled engine runtime for all release targets; macOS sidecar automation exists, while Windows and development builds still need release-grade sidecar packaging,
- large-data execution with streaming progress transport, durable persisted cancellation, scheduler, and materialized execution caches.

---

## 3. Product Thesis

Individual investors and independent researchers already have access to more information than ever: prices, filings, charts, news, analyst notes, social media, sentiment, transcripts, fundamentals, and alternative data.

Access alone does not create edge.

When many investors use the same dashboards, feeds, indicators, and screens, they are pushed toward similar strategies. The information is abundant, but the lens is generic.

VIZA is built on this belief:

```text
Alpha does not come from receiving the same information as everyone else.
It comes from translating information through a lens that is uniquely your own.
```

Insight is not just information. Insight is information transformed into something actionable inside a specific investment framework.

Example:

```text
Raw information:
A social post claims Company A is nearing an acquisition deal with Company B.

RSI swing strategy translation:
- Event type: acquisition rumor.
- Asset affected: target company.
- Strategy relevance: catalyst can reframe oversold RSI as possible reversal rather than weakness.
- Required confirmation: source credibility, volume spike, price reclaim of moving average.
- Suggested output: add to catalyst watchlist; do not trigger entry until confirmation gate passes.

Fundamental strategy translation:
- Event type: acquisition rumor.
- Asset affected: target company and acquirer.
- Strategy relevance: possible valuation floor and deal-premium upside.
- Required analysis: precedent transaction premium, regulatory likelihood, downside to unaffected price.
- Suggested output: research deeper and build event probability model.
```

The information is the same. The application is different.

VIZA exists to bridge that gap.

---

## 4. Product Positioning

### 4.1 VIZA is not

- A Bloomberg replacement.
- A FactSet, LSEG, Koyfin, or AlphaSense clone.
- A trading-signal vending machine.
- A generic AI stock explainer.
- A static dashboard.
- A generic social investing feed.
- A copy-trading app by default.
- A portfolio optimizer.
- A licensed investment adviser by default.

### 4.2 VIZA is

- A desktop research methodology builder.
- A visual asset, attribute, event, insight, and relationship graph.
- A data-source integration layer for user-entitled data.
- A local-first research runtime with strong auditability.
- A point-in-time evidence and validation environment.
- A deployment surface for custom radars, scorecards, watchlists, alerts, and exports.
- A strategy-aware insight translation system.
- A universal `.viza` strategy exchange environment.
- A future marketplace for methodology templates and research-output objects, only after legal, compliance, and data-rights foundations are implemented.

### 4.3 Product statement

```text
VIZA is a local-first research methodology platform that lets investors design their own investment logic, connect entitled data, transform market information into structured insight, and translate that insight into the exact format their strategy requires.
```

Supporting line:

```text
It is not another dashboard. It is the infrastructure layer for personalized alpha discovery.
```

---

## 5. Target Users

### 5.1 Beachhead users

The first wedge should favor sophisticated individuals and independent researchers who already have a lens but are underserved by institutional terminals and generic trading apps:

- advanced individual investors,
- independent traders with repeatable processes,
- quantamental retail investors,
- event-driven retail investors who combine qualitative catalysts with technical confirmation,
- independent research creators who want to encode and eventually monetize a research process.

### 5.2 Long-term users

- Equity analysts.
- Sector PMs.
- Independent research shops.
- Family-office analysts.
- Quantamental investors.
- Strategy researchers.
- Advanced individual investors with existing research processes.

### 5.3 Secondary users

- Risk analysts.
- Macro researchers.
- Data vendors who want their data usable inside custom research workflows.
- Strategy creators who want to distribute research logic or black-box research outputs.
- Educators and investment communities that want structured, auditable research templates.

---

## 6. Final Product Workflow

The final product workflow should be:

1. User opens VIZA.
2. The first screen is a blank methodology canvas or recent `.viza` file/project surface.
3. User creates or opens a `.viza` file.
4. VIZA reads the internal manifest and visualizes contents.
5. User designs or inspects a methodology graph.
6. User selects data sources, universes, asset classes, strategy constraints, and profile assumptions.
7. VIZA validates graph structure, data availability, entitlements, units, identifiers, timestamps, point-in-time rules, and licensing policies.
8. VIZA resolves assets through its canonical asset database.
9. VIZA runs the methodology graph.
10. VIZA extracts or computes attributes, events, and candidate insights.
11. VIZA translates candidate insights through the user's strategy profile.
12. VIZA produces ranked assets, strategy-compatible insight objects, relationship views, evidence tables, strategy-fit explanations, diagnostics, saved radars, watchlist updates, alerts, and point-in-time manifests.
13. User inspects individual companies/assets in the context of the methodology graph.
14. User sees why an insight matters, where it came from, how fresh it is, whether it fits the strategy, and what conditions would invalidate it.
15. User saves, exports, or shares a `.viza` file.
16. Another user opens the `.viza` file in VIZA, sees the visual contents, runs a compatibility check, maps missing connectors, and can open, run, fork, install, or reject the file.
17. Future versions may let users publish methodology templates or black-box research-output streams into a marketplace.

---

## 7. Universal `.viza` File System

### 7.1 Purpose

A `.viza` file is the universal exchange container for VIZA.

It can contain one or more of the following:

- methodology graph,
- strategy profile,
- radar definition,
- radar output,
- insight objects,
- event objects,
- asset universe snapshot,
- validation proof,
- audit manifest,
- signal outputs,
- creator notes,
- permissions,
- entitlement requirements,
- marketplace metadata,
- UI layout state,
- references to external data or local project records.

The file is not merely a saved graph. It is a portable VIZA research object.

### 7.2 Extension

All exchange files use:

```text
.viza
```

Backward-compatible import should support existing portable methodology files such as:

```text
.viza.json
```

But the next product should prefer `.viza`.

### 7.3 Filename semantics

The filename is not the semantic contract.

The filename may be descriptive or arbitrary. VIZA must never rely on the filename to determine:

- file type,
- object kind,
- visibility,
- exchange modes,
- permissions,
- validity,
- data requirements,
- strategy family,
- creator identity,
- marketplace rights.

All of those must come from the internal manifest.

### 7.4 Container structure

A `.viza` file should be a structured container. It can be implemented as one of:

- a zipped directory with JSON/Markdown payloads,
- a JSON envelope for the initial version,
- a binary envelope later if needed.

Recommendation:

- Phase 16 should use a zip-based container because it supports modular sections and future growth.
- Provide a migration path from the current `.viza.json` methodology graph format.

Internal layout:

```text
example.viza
│
├── manifest.json
├── graph/
│   └── methodology.json
├── strategies/
│   └── strategy_profile.json
├── assets/
│   ├── universe_snapshot.json
│   └── asset_map.json
├── events/
│   └── events.json
├── insights/
│   └── insights.json
├── radar/
│   ├── radar_definition.json
│   └── radar_output.json
├── proof/
│   └── validation_manifest.json
├── signals/
│   └── signal_outputs.json
├── rights/
│   └── license_and_entitlements.json
├── audit/
│   ├── run_manifest.json
│   └── checksums.json
├── ui/
│   └── layout_state.json
└── notes/
    └── creator_notes.md
```

A file does not need all sections.

### 7.5 Manifest is the source of truth

Every `.viza` file must include:

```text
manifest.json
```

The manifest defines:

- schema version,
- file ID,
- object kind,
- exchange modes,
- visibility mode,
- included sections,
- absent sections,
- redacted sections,
- entitlement-locked sections,
- creator identity if available,
- created/updated timestamps,
- versioning,
- data requirements,
- connector requirements,
- asset universe requirements,
- permissions,
- file integrity hashes,
- signature if available,
- import safety status,
- compatibility requirements,
- minimum VIZA app version.

### 7.6 Manifest example

```json
{
  "schema": "viza_file_v0",
  "file_id": "viza_file_01HX...",
  "display_name": "Catalyst RSI Strategy Pack",
  "object_kind": "strategy_package",
  "primary_mode": "methodology",
  "exchange_modes": [
    "methodology_graph",
    "installable_radar",
    "insight_objects",
    "validation_proof"
  ],
  "visibility": "white_box",
  "created_at": "2026-05-12T00:00:00Z",
  "updated_at": "2026-05-12T00:00:00Z",
  "created_by": {
    "creator_id": "local_or_marketplace_creator_id",
    "display_name": "Creator Name",
    "verification_status": "unverified"
  },
  "minimum_viza_version": "0.2.0",
  "sections": {
    "methodology_graph": {
      "status": "included",
      "path": "graph/methodology.json",
      "schema": "viza_graph_v0",
      "checksum": "sha256:..."
    },
    "strategy_profile": {
      "status": "included",
      "path": "strategies/strategy_profile.json",
      "schema": "viza_strategy_profile_v0",
      "checksum": "sha256:..."
    },
    "insight_objects": {
      "status": "included",
      "path": "insights/insights.json",
      "schema": "viza_insight_v0",
      "checksum": "sha256:..."
    },
    "radar_output": {
      "status": "absent",
      "reason": "not_generated"
    },
    "signal_outputs": {
      "status": "redacted",
      "reason": "creator_black_box_permission"
    },
    "validation_proof": {
      "status": "included",
      "path": "proof/validation_manifest.json",
      "schema": "viza_validation_proof_v0",
      "checksum": "sha256:..."
    }
  },
  "data_requirements": {
    "asset_classes": ["US_EQ"],
    "required_connectors": ["prices_ohlcv", "news_events", "sec_edgar"],
    "optional_connectors": ["insider_transactions", "options_positioning"],
    "required_attributes": ["rsi_14d", "volume_spike", "event_relevance", "source_credibility"],
    "point_in_time_required": true
  },
  "permissions": {
    "open_allowed": true,
    "run_allowed": true,
    "fork_allowed": true,
    "export_allowed": false,
    "redistribute_allowed": false,
    "commercial_use_allowed": false
  },
  "integrity": {
    "manifest_checksum": "sha256:...",
    "container_checksum": "sha256:...",
    "signature_status": "unsigned"
  }
}
```

### 7.7 Section status contract

Allowed section statuses:

| Status | Meaning |
|---|---|
| `included` | Section is bundled and can be read. |
| `absent` | Section is not part of this file. |
| `redacted` | Section exists conceptually but is intentionally hidden. |
| `entitlement_locked` | Section requires entitlement, subscription, or local connector rights. |
| `external_reference` | Section points to a local project record, remote object, or external source. |
| `unsupported_schema` | Section exists but requires a newer VIZA schema/app version. |
| `deprecated` | Section uses an older schema that can be migrated or viewed with warning. |
| `corrupt` | Section failed checksum or parse validation. |

### 7.8 Object kinds

A `.viza` file can have these object kinds:

```text
methodology
strategy_package
insight_package
radar_package
validation_package
signal_package
template_package
marketplace_listing_package
project_snapshot
```

Object kind is descriptive, not restrictive. A `strategy_package` may contain a methodology graph, insight objects, radar definition, proof, and notes.

### 7.9 Exchange modes

A `.viza` file can support any combination of these modes:

```text
methodology_graph
installable_radar
insight_objects
validation_proof
signal_outputs
strategy_profile
template
project_snapshot
marketplace_preview
```

### 7.10 Visibility modes

Visibility modes:

| Mode | Description |
|---|---|
| `white_box` | Full methodology graph and parameters are visible. |
| `gray_box` | Broad structure is visible; exact parameters, weights, or subgraphs may be hidden. |
| `black_box` | Methodology is hidden; outputs and proof may be visible. |
| `output_only` | User receives signals/radar results without methodology internals. |
| `preview_only` | User can inspect metadata and sample outputs but cannot run or fork. |

Visibility mode determines which sections are included, redacted, or entitlement-locked.

### 7.11 Import/open workflow

When a user opens, double-clicks, or drags a `.viza` file into VIZA:

1. VIZA reads only `manifest.json` first.
2. VIZA validates manifest schema.
3. VIZA checks the minimum app version.
4. VIZA checks container integrity and section checksums.
5. VIZA checks whether the file attempts to include arbitrary code. Arbitrary code must be rejected.
6. VIZA renders a visual file contents view.
7. VIZA shows included, absent, redacted, locked, and unsupported sections.
8. VIZA checks local connectors, entitlements, and credential availability.
9. VIZA checks whether required data can be queried, cached, displayed, exported, or derived.
10. VIZA presents actions based on the manifest and local environment.

Available actions may include:

```text
Open Methodology Canvas
Inspect Strategy Profile
Inspect Insight Objects
Install Radar
Run Compatibility Check
Map Missing Data
Connect Required Data Source
Run Locally
Fork As New Local Methodology
Save To Project Store
Create Watchlist
View Validation Proof
View Audit Manifest
Export Allowed Sections
Quarantine File
Reject File
```

### 7.12 Export workflow

When a user exports to `.viza`:

1. User selects export purpose:
   - local backup,
   - share with collaborator,
   - publish template,
   - package black-box output,
   - package validation proof,
   - marketplace draft.
2. VIZA selects included sections based on purpose.
3. VIZA computes checksums for every included section.
4. VIZA writes a manifest with section statuses.
5. VIZA checks data-rights and entitlement restrictions.
6. VIZA redacts or locks restricted data.
7. VIZA warns if the export contains prototype, non-production, evidence-only, or non-PIT-safe data.
8. VIZA saves the `.viza` container.
9. VIZA optionally persists export metadata to the local project store.

### 7.13 File visualization surface

The file viewer should show:

```text
Header
  display name
  object kind
  visibility mode
  schema version
  creator if available
  created/updated timestamps
  integrity status

Contents Map
  methodology graph: included / absent / locked / redacted
  strategy profile: included / absent / locked / redacted
  insight objects: included / absent / locked / redacted
  radar definition: included / absent / locked / redacted
  radar output: included / absent / locked / redacted
  validation proof: included / absent / locked / redacted
  signal outputs: included / absent / locked / redacted
  audit manifest: included / absent / locked / redacted

Compatibility
  required app version
  required connectors
  missing connectors
  required entitlements
  unsupported schemas
  PIT safety status
  data rights status

Actions
  open
  run
  fork
  install
  map data
  connect source
  view proof
  save locally
  quarantine
```

### 7.14 Security requirements

A `.viza` file must never execute arbitrary code.

Allowed executable logic should be limited to schema-validated methodology graphs, supported transforms, allowed formulas, and runtime-supported node types.

Security requirements:

- parse manifest before reading other sections,
- validate all schemas,
- verify checksums,
- reject path traversal in zip containers,
- reject embedded scripts unless explicitly supported by a sandboxed expression engine,
- never expose connector secrets in exported files,
- never include credential values in `.viza` containers,
- redacted sections must not be recoverable from the file,
- entitlement-locked sections must remain inaccessible without rights,
- corrupted sections should be isolated without crashing the app,
- suspicious files should be quarantined.

---

## 8. Core Data Architecture

### 8.1 High-level architecture

```text
External Data Providers
        ↓
Provider Connectors
        ↓
VIZA Normalization Layer
        ↓
Canonical Asset / Entity Database
        ↓
Point-In-Time Observation Store
        ↓
Event + Attribute Resolver Layer
        ↓
Insight Extraction Engine
        ↓
Strategy Profile + Translation Engine
        ↓
Radar / Insight / Signal Outputs
        ↓
.viza Exchange Container
```

### 8.2 Outsourced data

VIZA should outsource:

- prices and OHLCV,
- historical price data,
- corporate fundamentals,
- SEC filings and XBRL facts,
- news,
- transcripts,
- analyst ratings,
- insider transactions,
- ETF holdings,
- corporate actions,
- macro series,
- options and positioning data,
- institutional data from user-entitled providers.

### 8.3 Internally owned data

VIZA should build and own:

- canonical asset IDs,
- entity IDs,
- provider identifier maps,
- source lineage records,
- attribute registry,
- insight ontology,
- methodology graphs,
- strategy profiles,
- evidence records,
- point-in-time observation metadata,
- validation ledger,
- run manifests,
- translation outputs,
- `.viza` file manifests,
- user-created research objects.

### 8.4 Data licensing and rights tracking

Every data-derived value must carry rights metadata.

Rights fields:

```text
connector_id
source_id
license_policy
cache_policy
query_policy
display_policy
export_policy
derived_value_policy
redistribution_policy
marketplace_policy
attribution_required
retention_policy
```

The runtime must enforce:

- no export when export is forbidden,
- no marketplace packaging when redistribution is forbidden,
- no raw value leakage from restricted sources,
- no credential leakage,
- visible warnings for limited sources,
- redaction records for exported files.

---

## 9. Canonical Asset Database / Security Master

### 9.1 Purpose

The canonical asset database is VIZA's internal identity layer.

It prevents VIZA from becoming brittle when providers disagree on tickers, names, corporate actions, security identifiers, listing status, or coverage rules.

### 9.2 Asset object schema

```json
{
  "schema": "viza_asset_v0",
  "asset_id": "viza_asset_us_eq_000001",
  "asset_class": "equity",
  "primary_symbol": "AAPL",
  "current_name": "Apple Inc.",
  "former_names": [],
  "exchange": "NASDAQ",
  "country": "US",
  "currency": "USD",
  "identifiers": {
    "cik": "...",
    "figi": "...",
    "lei": "...",
    "isin": "...",
    "cusip": "...",
    "sedol": "..."
  },
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "listing_status": "active",
  "tradable_instruments": ["common_stock", "options"],
  "corporate_action_history_ref": "...",
  "identifier_history_ref": "...",
  "related_entities": [],
  "provider_identifier_map": {},
  "source_lineage": [],
  "license_policy": {},
  "created_at": "...",
  "updated_at": "..."
}
```

### 9.3 Initial security master MVP

The initial seed should support U.S. equities only.

Minimum fields:

```text
asset_id
symbol
name
exchange
country
currency
CIK
FIGI if available
sector
industry
listing_status
provider_identifier_map
created_at
updated_at
```

### 9.4 Required APIs/endpoints

Add:

```text
GET  /viza/assets/search
POST /viza/assets/resolve
GET  /viza/assets/{asset_id}
GET  /viza/assets/{asset_id}/identifiers
GET  /viza/assets/{asset_id}/relationships
POST /viza/assets/reconcile
```

---

## 10. Point-In-Time Observation Store

### 10.1 Purpose

VIZA must know what information was available at a given point in time.

This is required for:

- backtesting,
- reproducibility,
- validation,
- creator claims,
- marketplace trust,
- anti-look-ahead controls,
- strategy-output audit.

### 10.2 Observation schema

```json
{
  "schema": "viza_observation_v0",
  "observation_id": "obs_...",
  "asset_id": "viza_asset_us_eq_000001",
  "attribute_key": "rsi_14d",
  "value": 31.5,
  "unit": "score",
  "observed_at": "2026-05-12T14:30:00Z",
  "available_at": "2026-05-12T14:35:00Z",
  "retrieved_at": "2026-05-12T14:36:00Z",
  "source_id": "provider_x",
  "connector_id": "prices_ohlcv",
  "source_record": "...",
  "data_version": "...",
  "model_version": "...",
  "confidence": 0.96,
  "license_policy": {},
  "entitlement_policy": {},
  "checksum": "sha256:..."
}
```

### 10.3 Storage recommendation

Initial implementation can use SQLite or DuckDB.

Recommended direction:

- SQLite for project metadata and small local store.
- DuckDB for larger local point-in-time observation tables and batch analytics.
- Keep schema abstract enough to later support Postgres or cloud sync.

---

## 11. Event / Catalyst Objects

### 11.1 Purpose

An event is a timestamped occurrence that may affect an asset, entity, sector, or relationship.

VIZA's first strategic wedge requires first-class event/catalyst objects.

### 11.2 Event schema

```json
{
  "schema": "viza_event_v0",
  "event_id": "event_...",
  "event_type": "acquisition_rumor",
  "affected_asset_ids": ["viza_asset_us_eq_000001"],
  "related_asset_ids": ["viza_asset_us_eq_000002"],
  "related_entity_ids": [],
  "observed_at": "2026-05-12T14:00:00Z",
  "available_at": "2026-05-12T14:02:00Z",
  "source": {
    "source_id": "news_or_social_source",
    "source_type": "news",
    "source_url_ref": "...",
    "source_record": "..."
  },
  "confidence": 0.42,
  "source_credibility": 0.55,
  "materiality": 0.7,
  "novelty": 0.8,
  "direction_hint": "bullish_target_uncertain_acquirer",
  "time_horizon_hint": "2d-3w",
  "risk_factors": ["rumor_false_positive", "source_uncertainty"],
  "evidence_refs": [],
  "license_policy": {},
  "point_in_time_safe": true
}
```

### 11.3 Initial event types

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

### 11.4 Event extraction

Event extraction can be rule-driven at first.

MVP extraction sources:

- SEC filing metadata,
- local/user-provided news CSV,
- provider news API once available,
- manually added event nodes,
- deterministic prototype event attributes already in registry.

Later extraction may use financial NLP models, but model outputs must be labeled with confidence, limitations, source, and model version.

---

## 12. Insight Objects

### 12.1 Purpose

An insight is structured investment meaning derived from attributes, events, relationships, text, filings, or methodology outputs.

An insight is not a summary. It is a strategy-aware object that can be:

- tested,
- filtered,
- translated,
- audited,
- exchanged,
- validated,
- embedded in a `.viza` file.

### 12.2 Insight schema

```json
{
  "schema": "viza_insight_v0",
  "insight_id": "insight_...",
  "asset_id": "viza_asset_us_eq_000001",
  "related_asset_ids": ["viza_asset_us_eq_000002"],
  "insight_type": "acquisition_rumor_with_technical_reversal_context",
  "direction": "bullish",
  "magnitude": {
    "value": 0.65,
    "unit": "relative_signal_strength"
  },
  "confidence": 0.52,
  "time_horizon": {
    "min": "2d",
    "max": "3w"
  },
  "evidence_refs": ["evidence_..."],
  "source_policy": {
    "display_allowed": true,
    "export_allowed": false,
    "redistribution_allowed": false
  },
  "observed_at": "2026-05-12T14:00:00Z",
  "available_at": "2026-05-12T14:02:00Z",
  "generated_at": "2026-05-12T14:05:00Z",
  "strategy_compatibility": [
    {
      "strategy_profile_id": "strategy_rsi_catalyst_v0",
      "fit_score": 0.78,
      "fit_reason": "Catalyst can reframe oversold RSI as reversal candidate if confirmation passes."
    }
  ],
  "risk_factors": [
    "rumor_false_positive",
    "source_credibility_low",
    "liquidity_risk"
  ],
  "invalidation_conditions": [
    "deal_denial_by_company",
    "volume_confirmation_fails",
    "price_breaks_recent_low"
  ],
  "action_layer": {
    "suggested_action_type": "watchlist",
    "trigger_conditions": ["volume_spike", "moving_average_reclaim"],
    "not_investment_advice": true
  },
  "derivation_trace": {
    "methodology_graph_hash": "sha256:...",
    "node_ids": [],
    "event_ids": [],
    "attribute_keys": []
  }
}
```

### 12.3 Insight type registry

Create an insight type registry parallel to the attribute registry.

Initial registry fields:

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
license_policy
model_policy
point_in_time_policy
```

### 12.4 Initial insight types

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

---

## 13. Strategy Profiles

### 13.1 Purpose

A strategy profile describes how an investor thinks, filters, validates, and acts.

It is the interpretive lens VIZA uses to translate raw market information into strategy-specific output.

### 13.2 Strategy profile schema

```json
{
  "schema": "viza_strategy_profile_v0",
  "strategy_profile_id": "strategy_rsi_catalyst_v0",
  "display_name": "RSI Swing + Catalyst Confirmation",
  "asset_classes": ["US_EQ"],
  "universe_constraints": {
    "min_market_cap": null,
    "min_liquidity": "configurable",
    "exclude_sectors": []
  },
  "holding_period": {
    "min": "2d",
    "max": "3w"
  },
  "preferred_indicators": ["rsi_14d", "volume_spike", "moving_average_reclaim", "momentum"],
  "catalyst_types": ["acquisition_rumor", "earnings_surprise", "analyst_upgrade", "insider_purchase"],
  "required_confirmations": ["source_credibility", "volume_confirmation"],
  "risk_limits": {
    "avoid_low_liquidity": true,
    "avoid_extreme_volatility": true,
    "max_position_hint": null
  },
  "output_preferences": {
    "primary_view": "radar",
    "show_invalidation_conditions": true,
    "show_evidence": true,
    "show_confidence": true
  },
  "action_thresholds": {
    "watchlist_threshold": 0.55,
    "research_threshold": 0.65,
    "alert_threshold": 0.75
  },
  "evidence_requirements": {
    "require_point_in_time_safe": true,
    "minimum_source_credibility": 0.5,
    "minimum_event_confidence": 0.4
  }
}
```

### 13.3 Strategy profile nodes

Add a future node type:

```text
strategy_profile
```

The strategy profile node configures:

- strategy type,
- universe constraints,
- preferred insight types,
- confirmation rules,
- action thresholds,
- risk filters,
- output formatting,
- evidence requirements.

### 13.4 First strategy profile template

Implement this first:

```text
RSI Swing + Catalyst Confirmation
```

It should translate qualitative catalyst information into technical-swing research outputs.

---

## 14. Insight Translation Engine

### 14.1 Purpose

The translation engine converts insight objects into strategy-specific output.

It answers:

```text
Why does this information matter to this strategy?
What evidence supports it?
What confirmation is missing?
What would invalidate it?
What should the user do with it inside their research workflow?
```

### 14.2 Translation schema

```json
{
  "schema": "viza_translation_v0",
  "translation_id": "translation_...",
  "insight_id": "insight_...",
  "strategy_profile_id": "strategy_rsi_catalyst_v0",
  "asset_id": "viza_asset_us_eq_000001",
  "fit_score": 0.78,
  "relevance": "high",
  "translated_summary": "Acquisition rumor may reframe oversold RSI as a catalyst-backed reversal candidate, but volume confirmation is required.",
  "strategy_fit_reasons": [
    "Event type is compatible with catalyst strategy.",
    "RSI is currently oversold.",
    "Volume confirmation has not passed yet."
  ],
  "missing_confirmations": ["volume_spike", "moving_average_reclaim"],
  "risk_factors": ["rumor_false_positive", "source_credibility_low"],
  "invalidation_conditions": ["deal_denial", "price_breaks_recent_low"],
  "suggested_research_action": "add_to_watchlist",
  "evidence_refs": [],
  "not_investment_advice": true
}
```

### 14.3 Translation algorithm MVP

Use deterministic rules first.

MVP steps:

1. Read strategy profile.
2. Read insight object.
3. Check insight type compatibility.
4. Check required attributes and confirmations.
5. Check evidence and source credibility.
6. Check risk constraints.
7. Compute fit score.
8. Generate strategy-fit explanation from templates.
9. Output translation object.
10. Attach translation to radar row and insight card.

### 14.4 Model-assisted translation

Financial NLP or LLM-assisted components can be added later.

Requirements:

- model version must be recorded,
- prompt/template version must be recorded,
- source data must be cited internally by evidence refs,
- uncertain or low-confidence outputs must be labeled,
- model text must not override hard entitlement/data-rights restrictions,
- model output must be reproducible enough for audit or clearly marked non-deterministic.

---

## 15. Methodology Graph Evolution

### 15.1 Current graph

Continue using `viza_graph_v0` until migration is required.

### 15.2 Future nodes

Add these nodes in stages:

```text
asset_resolver
data_source
technical_indicator
event_catalyst
insight_extractor
strategy_profile
compatibility_gate
evidence
scheduler_refresh
validation_gate
```

### 15.3 Node definitions

#### `asset_resolver`

Resolves symbols, names, CIKs, FIGIs, and provider IDs into canonical `asset_id` values.

#### `data_source`

Represents a connector or data dependency in the graph.

#### `technical_indicator`

Computes indicators such as RSI, momentum, moving averages, volatility, and volume spikes.

#### `event_catalyst`

Extracts or filters event objects.

#### `insight_extractor`

Transforms attributes/events/relationships into insight objects.

#### `strategy_profile`

Defines the user's strategic lens.

#### `compatibility_gate`

Determines whether an insight is compatible with a strategy profile.

#### `evidence`

Explicitly exposes evidence, source lineage, and confidence requirements.

#### `scheduler_refresh`

Defines refresh or recurring execution behavior.

#### `validation_gate`

Applies proof, PIT, overfitting, and minimum evidence constraints.

### 15.4 Graph execution changes

The runtime compiler must eventually support:

```text
Universe
  -> Asset Resolver
  -> Attribute / Event / Technical Indicator
  -> Insight Extractor
  -> Strategy Profile / Compatibility Gate
  -> Score / Rank
  -> Output Radar / Insight Cards / Signal Outputs
```

Graph outputs should include:

- radar rows,
- insight objects,
- translations,
- evidence records,
- relationship edges,
- validation proof,
- audit manifest.

---

## 16. Radar, Insight Cards, And Strategy-Fit Output

### 16.1 Radar row fields

Add strategy-aware fields to radar rows:

```text
asset_id
ticker
company_name
rank
score
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

### 16.2 Insight card UI

Each insight card should show:

```text
Header
  asset
  insight type
  direction
  confidence
  horizon
  strategy fit score

Translation
  why it matters to the selected strategy
  required confirmations
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
  related assets
  related events
  related attributes
  reinforcing/conflicting insights

Audit
  graph hash
  strategy profile version
  run ID
  evidence checksum
  result checksum
```

### 16.3 Strategy-fit explanation

Each radar row should explain why it was surfaced.

Example:

```text
This asset was surfaced because an acquisition rumor was detected while RSI is oversold.
The event is compatible with the RSI Swing + Catalyst Confirmation profile.
Volume confirmation is not yet present, so the suggested action is watchlist rather than trigger.
The primary invalidation conditions are a credible deal denial or a break below the recent low.
```

---

## 17. Relationship Graph Evolution

### 17.1 Current relationship graph

The current app supports company-centered relationship and evidence views with family filtering, search, confidence, source lineage, and evidence details.

### 17.2 Future relationship families

Add:

```text
company_to_insight
insight_to_event
insight_to_attribute
insight_to_strategy_profile
insight_confirms_insight
insight_conflicts_with_insight
insight_invalidates_insight
asset_to_canonical_entity
asset_to_provider_identifier
asset_to_corporate_action
asset_to_supplier
asset_to_customer
asset_to_owner
asset_to_peer
asset_to_macro_series
```

### 17.3 Insight reaction graph

The relationship engine should eventually model reactions between insights.

Examples:

```text
acquisition_rumor reinforces unusual_volume
insider_purchase reinforces momentum_breakout
regulatory_action invalidates acquisition_rumor
earnings_miss conflicts with bullish_social_sentiment
macro_liquidity_shock weakens small_cap_breakout_signal
```

### 17.4 Graph viewer requirements

The relationship graph should support:

- family filters,
- confidence filters,
- source filters,
- time horizon filters,
- PIT filters,
- path search,
- cluster detection,
- edge evidence inspection,
- conflict/reinforcement labels,
- relationship export where licensing permits.

---

## 18. Local Project Store Evolution

### 18.1 Current project store

The current local SQLite store persists:

- projects,
- methodology versions,
- run records,
- saved radar outputs,
- connector settings metadata,
- user settings,
- watchlists,
- alerts.

### 18.2 New tables

Add or prepare tables for:

```text
viza_files
viza_file_imports
viza_file_exports
canonical_assets
asset_identifiers
asset_relationships
provider_identifier_maps
observations
observation_versions
events
insights
insight_translations
strategy_profiles
strategy_profile_versions
validation_records
strategy_output_records
creator_records
file_signatures
```

### 18.3 File/project relationship

A `.viza` file can be:

- imported into a local project,
- exported from a local project,
- opened without import,
- forked into a local project,
- saved as a project snapshot,
- used as a marketplace package in the future.

The local project store should record:

```text
file_id
container_checksum
manifest_checksum
imported_at
exported_at
source_path
project_id
created_local_objects
warnings
quarantine_status
```

---

## 19. API And Service Additions

### 19.1 File endpoints

Add:

```text
POST /viza/files/inspect
POST /viza/files/import
POST /viza/files/export
POST /viza/files/validate
POST /viza/files/quarantine
GET  /viza/files/{file_id}
GET  /viza/files/{file_id}/sections
GET  /viza/files/{file_id}/visualization
```

### 19.2 Asset endpoints

```text
GET  /viza/assets/search
POST /viza/assets/resolve
GET  /viza/assets/{asset_id}
GET  /viza/assets/{asset_id}/relationships
POST /viza/assets/reconcile
```

### 19.3 Event endpoints

```text
POST /viza/events/extract
GET  /viza/events/{event_id}
POST /viza/events/query
POST /viza/events/manual
```

### 19.4 Insight endpoints

```text
POST /viza/insights/extract
POST /viza/insights/query
GET  /viza/insights/{insight_id}
POST /viza/insights/{insight_id}/translate
```

### 19.5 Strategy profile endpoints

```text
GET  /viza/strategy-profiles
POST /viza/strategy-profiles
GET  /viza/strategy-profiles/{profile_id}
PUT  /viza/strategy-profiles/{profile_id}
POST /viza/strategy-profiles/{profile_id}/clone
```

### 19.6 Translation endpoints

```text
POST /viza/translate
POST /viza/translate/batch
GET  /viza/translations/{translation_id}
```

### 19.7 Validation ledger endpoints

```text
POST /viza/validation/record
GET  /viza/validation/{record_id}
POST /viza/validation/compare
POST /viza/validation/replay
```

---

## 20. Desktop UI Additions

### 20.1 File open surface

When a `.viza` file is opened, show a file visualization screen with:

- file identity,
- contents map,
- visibility mode,
- exchange modes,
- required connectors,
- missing connectors,
- entitlement warnings,
- PIT safety status,
- integrity status,
- available actions.

### 20.2 Strategy exchange inbox

Add a local view for imported/opened files:

```text
Strategy Exchange Inbox
  Recent .viza files
  Imported files
  Quarantined files
  Forked files
  Files with missing connectors
  Files with validation proof
  Files with redacted/locked sections
```

### 20.3 Strategy profile builder

Add a builder for strategy profiles:

- choose asset class,
- choose horizon,
- choose catalyst types,
- choose technical overlays,
- choose required confirmations,
- choose risk constraints,
- choose evidence requirements,
- choose output preferences,
- save as profile,
- export profile inside `.viza`.

### 20.4 Insight cards panel

Add insight cards alongside the radar table.

Each radar row can expand into insight cards showing:

- translated summary,
- strategy fit,
- confidence,
- evidence,
- missing confirmations,
- invalidation conditions,
- related insights,
- audit trace.

### 20.5 File export wizard

Add export wizard:

```text
Export as .viza
  Purpose: backup / collaboration / template / black-box output / validation proof
  Visibility: white-box / gray-box / black-box / output-only / preview-only
  Sections to include
  Data-rights check
  Redaction preview
  Connector requirements
  Integrity/signature options
  Save file
```

### 20.6 Connector mapping workflow

When opening a `.viza` file with missing connectors:

```text
This file requires: prices_ohlcv, news_events, sec_edgar.
You have: local_workspace, local_csv.
Options:
  connect provider
  map local CSV field
  run degraded mode
  inspect without running
  reject file
```

---

## 21. Black-Box, Gray-Box, And White-Box Strategy Exchange

### 21.1 White-box

User can view and fork the full graph.

Included sections may include:

- methodology graph,
- strategy profile,
- insights,
- radar definition,
- proof,
- notes.

### 21.2 Gray-box

User can view broad structure but not exact proprietary parameters.

Possible redactions:

- exact thresholds,
- scoring weights,
- subgraph details,
- formula internals,
- creator notes,
- source-specific logic.

### 21.3 Black-box

User cannot view methodology internals.

Included sections may include:

- output signals,
- high-level strategy description,
- validation proof,
- data requirements,
- risk labels,
- audit manifest.

Hidden sections:

- methodology graph,
- proprietary parameters,
- internal feature weights,
- internal subgraphs.

### 21.4 Output-only

User receives signals or radar output only.

Must show:

- source limitations,
- confidence,
- horizon,
- risk labels,
- non-advice disclaimer,
- proof status if available.

---

## 22. Validation Ledger

### 22.1 Purpose

The validation ledger records strategy outputs over time.

It is required for:

- strategy quality assessment,
- marketplace readiness,
- creator reputation,
- anti-overfitting controls,
- dispute resolution,
- auditability.

### 22.2 Validation record schema

```json
{
  "schema": "viza_validation_record_v0",
  "validation_record_id": "val_...",
  "strategy_or_methodology_id": "...",
  "strategy_profile_id": "...",
  "run_id": "...",
  "graph_hash": "sha256:...",
  "result_checksum": "sha256:...",
  "timestamp_cutoff": "2026-05-12T00:00:00Z",
  "generated_at": "2026-05-12T00:05:00Z",
  "asset_universe": "US_EQ",
  "outputs": [],
  "evidence_checksum": "sha256:...",
  "data_versions": [],
  "model_versions": [],
  "connector_states": [],
  "PIT_summary": {},
  "performance_observation": {
    "status": "pending",
    "evaluation_window": "2d-3w"
  },
  "in_sample_out_of_sample_label": "out_of_sample_candidate",
  "warnings": []
}
```

### 22.3 Marketplace readiness metrics

Do not expose marketplace claims until validation can show:

- in-sample vs out-of-sample labels,
- drawdown periods,
- false positive rates,
- performance decay,
- regime sensitivity,
- data leakage checks,
- source entitlement compliance,
- version history,
- creator disclosure status.

---

## 23. Compliance And Risk Controls

### 23.1 Required controls

VIZA should include:

- clear research-software positioning,
- not-investment-advice labels,
- source confidence labels,
- rumor/unverified catalyst labels,
- social-media-source risk labels,
- model-output uncertainty labels,
- data-rights enforcement,
- export redaction,
- marketplace compliance review before monetized outputs,
- creator performance disclaimers,
- user-level entitlement enforcement,
- audit logs for strategy claims.

### 23.2 Marketplace caution

Marketplace language should focus on:

```text
methodology templates
research outputs
software-generated research objects
```

Avoid framing early marketplace products as:

```text
managed accounts
funds
securities
personalized investment advice
guaranteed alpha
copy-trading by default
```

### 23.3 Social and rumor data

All rumor/social/news-derived insights must include:

- source type,
- source credibility,
- confidence,
- timestamp availability,
- unverified label where applicable,
- risk factors,
- invalidation conditions,
- audit trail.

---

## 24. Implementation Roadmap From Current Prototype

The current prototype is implemented through Phase 15. The next phases should be:

### Phase 16: Universal `.viza` container

Goal: replace `.viza.json` as the preferred portable format with a universal `.viza` container.

Tasks:

- Define `viza_file_v0` manifest schema.
- Implement zip-based `.viza` container reader/writer.
- Add file integrity checks.
- Add section status contract.
- Add manifest-only inspection.
- Add compatibility checks.
- Add backwards import for `.viza.json` methodology graphs.
- Add tests for valid, missing, corrupt, redacted, unsupported, and locked sections.

Exit criteria:

- A current methodology graph can export as `.viza` and import back into VIZA without loss.
- VIZA can inspect a `.viza` file before importing it.
- VIZA does not rely on filename semantics.

### Phase 17: File visualization and strategy exchange UI

Goal: make `.viza` files visually understandable inside the program.

Tasks:

- Add file open screen.
- Add contents map.
- Add exchange mode badges.
- Add connector/data requirement panel.
- Add import/fork/install/open actions.
- Add quarantine state.
- Add strategy exchange inbox.
- Add export wizard.

Exit criteria:

- User can open any `.viza` file and see what it contains inside VIZA.
- User can choose appropriate actions based on file sections and permissions.

### Phase 18: Canonical asset/security master seed

Goal: create internal asset identity.

Tasks:

- Add asset schema.
- Add asset identifier table.
- Add provider identifier map table.
- Add asset resolver service.
- Add asset resolver node.
- Seed U.S. equity assets from local universe and public/provider sources.
- Add tests for ticker changes, duplicate symbols, missing identifiers, and provider conflicts.

Exit criteria:

- Methodology runs resolve tickers to internal `asset_id` values.
- Evidence and insights reference `asset_id`, not only ticker strings.

### Phase 19: Event/catalyst object model

Goal: make catalysts first-class objects.

Tasks:

- Add `viza_event_v0` schema.
- Add event registry.
- Add event/catalyst node.
- Add manual event creation.
- Add deterministic event extraction from current event attributes.
- Add event evidence refs.
- Add event-to-asset relationship edges.

Exit criteria:

- A methodology can output event objects linked to assets and evidence.

### Phase 20: Insight object schema and extraction

Goal: emit first-class insight objects.

Tasks:

- Add `viza_insight_v0` schema.
- Add insight type registry.
- Add insight extractor node.
- Add rule-based insight extraction for first wedge.
- Add insight evidence refs.
- Add insight-to-event and insight-to-attribute relationships.
- Add insight card backend payload.

Exit criteria:

- Runtime can output insight objects for U.S. equity catalyst + technical confirmation workflows.

### Phase 21: Strategy profile and translation engine

Goal: translate insight objects into user strategy language.

Tasks:

- Add `viza_strategy_profile_v0` schema.
- Add strategy profile builder UI.
- Add strategy profile node.
- Add first template: RSI Swing + Catalyst Confirmation.
- Add `viza_translation_v0` schema.
- Implement deterministic translation rules.
- Add strategy-fit scoring.
- Add strategy-fit explanation generation.

Exit criteria:

- Same insight can produce different output for different strategy profiles.
- Radar rows include strategy-fit score and explanation.

### Phase 22: Strategy-fit radar and insight cards

Goal: make translated insights visible and actionable.

Tasks:

- Add insight cards panel.
- Add translated summary in radar rows.
- Add missing confirmations.
- Add invalidation conditions.
- Add risk flags.
- Add strategy-fit filters/sorting.
- Add export redaction for translated insights.

Exit criteria:

- User can run the RSI catalyst strategy and inspect translated insight cards.

### Phase 23: Source-backed resolver promotion and observation store

Goal: replace high-value prototype values with source-backed data.

Tasks:

- Choose first production connectors.
- Add OS credential vault integration.
- Add source-backed OHLCV resolver.
- Add RSI/momentum/volume indicators from real data.
- Add first durable observation store.
- Add PIT-safe observation retrieval.
- Add data-version capture.

Exit criteria:

- First wedge strategy can run on source-backed prices and events where available.

### Phase 24: Black-box/gray-box packaging

Goal: support creator-owned strategy exchange without full transparency.

Tasks:

- Add visibility controls to export wizard.
- Add parameter redaction.
- Add locked sections.
- Add validation proof packaging.
- Add output-only signal packaging.
- Add permission enforcement.
- Add tests ensuring redacted data is not recoverable.

Exit criteria:

- A creator can export white-box, gray-box, black-box, and output-only `.viza` files.

### Phase 25: Validation ledger and marketplace readiness

Goal: prepare but not yet launch marketplace.

Tasks:

- Add validation record schema.
- Add validation ledger tables.
- Add strategy-output history.
- Add out-of-sample labels.
- Add performance observation windows.
- Add creator identity placeholder.
- Add compliance warning system.
- Add marketplace draft file mode.

Exit criteria:

- VIZA can track strategy outputs over time with enough evidence for future marketplace review.

---

## 25. Acceptance Criteria For The Next Program

The next VIZA program is successful when:

- It continues to support all current Phase 0-15 functionality.
- It can export current methodology graphs as `.viza` files.
- It can import current methodology graphs from `.viza` files.
- It can inspect `.viza` manifests before importing.
- It never depends on filename semantics.
- It visualizes `.viza` file contents inside the app.
- It shows included, absent, redacted, locked, and unsupported sections.
- It checks connector and entitlement requirements before running imported content.
- It prevents arbitrary code execution from imported files.
- It stores import/export records in the local project store.
- It supports at least one white-box `.viza` methodology package.
- It supports at least one redacted/locked section scenario.
- It starts implementing canonical asset IDs.
- It starts implementing event and insight objects.
- It ships a first RSI + catalyst strategy-profile template.
- It produces strategy-fit explanations in radar rows.
- It preserves evidence, source lineage, PIT metadata, and checksums.
- It maintains compatibility with existing tests and look-ahead audit discipline.

---

## 26. Testing Requirements

### 26.1 File format tests

Test:

- valid `.viza` container,
- missing manifest,
- invalid manifest schema,
- unsupported manifest schema,
- corrupt section checksum,
- redacted section not bundled,
- entitlement-locked section inaccessible,
- path traversal attempt,
- arbitrary script/code inclusion,
- backward import from `.viza.json`,
- round-trip export/import of methodology graph.

### 26.2 Runtime tests

Test:

- imported graph execution,
- imported graph with missing connector,
- imported graph with restricted export rights,
- imported strategy profile translation,
- insight object extraction,
- strategy-fit scoring,
- point-in-time cutoff enforcement,
- result checksum stability.

### 26.3 UI tests

Test:

- open `.viza` file,
- contents map renders,
- redacted/locked/absent sections render correctly,
- missing connector panel renders,
- export wizard writes correct manifest,
- quarantine action works,
- strategy exchange inbox lists imported files,
- graph opens from file viewer,
- insight cards render.

### 26.4 Security tests

Test:

- no arbitrary code execution,
- no credential values in exported file,
- restricted evidence redacted,
- redacted sections unrecoverable,
- entitlement-locked sections inaccessible,
- manifest mismatch warning,
- unsigned file warning,
- corrupt file quarantine.

---

## 27. Backward Compatibility

The current prototype uses portable `.viza.json` methodology files.

Backward compatibility plan:

1. Continue to load `.viza.json` for existing users.
2. Add `Import legacy methodology file` flow.
3. Convert legacy graph into `.viza` container with:
   - `object_kind = methodology`,
   - `primary_mode = methodology_graph`,
   - `visibility = white_box`,
   - methodology graph included,
   - strategy profile absent,
   - insights absent,
   - proof absent unless available.
4. Save newly exported files as `.viza` by default.
5. Keep JSON graph export available as a developer/debug export, not the main user-facing exchange format.

---

## 28. Build Priorities

Priority order:

1. Universal `.viza` manifest and container.
2. `.viza` import/export compatibility with current graph.
3. File visualization and strategy exchange UI.
4. Section status model and redaction/lock handling.
5. Canonical asset seed.
6. Event object model.
7. Insight object model.
8. RSI catalyst strategy profile template.
9. Translation engine.
10. Strategy-fit radar and insight cards.
11. Source-backed high-value resolvers.
12. Validation ledger.
13. Black-box/gray-box packaging.
14. Marketplace readiness only after compliance and validation foundations.

---

## 29. Glossary

### `.viza` file

Universal VIZA exchange container. It may contain methodologies, insights, radars, profiles, proofs, outputs, rights metadata, and UI state.

### Asset

An investable or researchable object such as an equity, ETF, option, index, future, currency pair, crypto asset, commodity, bond, private company, or macro series.

### Attribute

A research variable describing or relating an asset, company, event, market, or macro condition.

### Event

A timestamped occurrence that may affect an asset or relationship.

### Insight

Structured investment meaning derived from attributes, events, relationships, or methodology outputs.

### Strategy profile

The user's investment lens: horizon, preferred indicators, required confirmations, risk constraints, evidence requirements, and output preferences.

### Translation

The process of converting an insight into strategy-specific language and actions.

### Radar

A deployed methodology graph that runs over a universe and emits ranked assets, insights, evidence, and diagnostics.

### Validation ledger

A durable record of strategy outputs, evidence, checksums, and performance-observation context over time.

### Visibility mode

The degree to which a `.viza` file exposes internal methodology: white-box, gray-box, black-box, output-only, or preview-only.

---

## 30. Sharpest Final Direction

VIZA should evolve from:

```text
Canvas -> Methodology Graph -> Local Engine -> Radar Table -> Evidence/Audit
```

into:

```text
.viza File -> Visual Strategy Object -> Asset/Event Evidence
  -> Insight Extraction -> Strategy Translation -> Strategy-Fit Radar
  -> Validation Ledger -> Exchange / Future Marketplace
```

The file is the exchange object.

The manifest is the contract.

The graph is the methodology.

The insight object is the meaning.

The strategy profile is the lens.

The translation is the personalization layer.

The validation ledger is the trust layer.

The VIZA program is what makes the file understandable, executable, auditable, and exchangeable.
