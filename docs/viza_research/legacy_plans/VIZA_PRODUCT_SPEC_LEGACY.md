# VIZA Product Spec

Last updated: 2026-05-12

Version: v0.3 - current prototype status plus strategic insight-translation roadmap

Status: canonical repo product spec. This replaces the earlier Phase 0-5 oriented spec and incorporates the newer strategy/insight direction from `VIZA_Product_Spec_Updated_2026-05-12.md`, while keeping implemented capabilities separate from roadmap concepts.

## Purpose

VIZA is the intended next product form of AAT.

AAT starts as an attribution engine: it explains a stock move through point-in-time-visible modeled drivers and an explicit residual. VIZA expands that foundation into a downloadable desktop research sandbox for Windows and macOS. The product lets users visually design research methodologies, connect entitled data sources, analyze relationships between attributes, run methodology-defined radars, preserve evidence, and eventually translate raw market information into strategy-specific insight.

VIZA should not try to beat Bloomberg, LSEG, FactSet, Koyfin, AlphaSense, or other financial terminals by owning more raw data. Its wedge is not raw data ownership. Its wedge is user-owned research logic and strategy-aware interpretation.

Product principle:

```text
Outsource commodity data. Own the meaning.
```

VIZA should use external providers for raw asset data where appropriate, but build and own the methodology graph, evidence model, entitlement layer, point-in-time discipline, validation ledger, and strategy-aware translation layer that turn data into user-specific research intelligence.

## North Star

VIZA is "Visio for investment research methodology" and, over time, an insight translation layer for investing.

The user starts from a blank canvas, designs a methodology as a graph, connects attributes, data sources, transforms, filters, scoring logic, relationship views, and output nodes, then runs that graph over selected universes. The output is not a generic screener. It is a user-defined research radar that lists, analyzes, explains, and preserves assets in the format implied by the methodology the user built.

The deeper ambition is that market insight should become portable. A filing, price move, event, news item, transcript sentence, unusual options event, or macro observation should not remain trapped in its original format. VIZA should be able to extract it, verify it, encode it, and translate it into the language of a user's strategy.

The final product should feel like a blend of:

- MS Visio for visual methodology design.
- Obsidian graph view for relationship discovery.
- A quant research notebook for repeatable methodology execution.
- A financial terminal for source-connected company and asset data.
- A strategy lab for encoding, testing, validating, and deploying user-specific investment logic.

## Product Thesis

Individual investors and independent researchers already have access to more information than ever: prices, filings, charts, news, analyst notes, social media, sentiment, transcripts, and alternative data. Access alone does not create edge.

When many investors use the same dashboards, indicators, feeds, and screens, they are pushed toward similar interpretations. The information is abundant, but the lens is generic.

VIZA is built on a different belief:

```text
Alpha does not come from receiving the same information as everyone else.
It comes from translating information through a lens that is uniquely your own.
```

Insight is not just information. Insight is information transformed into something actionable inside a specific investment framework.

Example:

- A trader using RSI may need an acquisition rumor translated into a catalyst overlay, timing trigger, invalidation condition, and risk adjustment.
- A fundamental investor may need the same rumor translated into valuation impact, deal probability, downside protection, and comparable transaction context.
- A macro investor may need to know whether the event matters for sector positioning, liquidity, rates sensitivity, or broader market risk.
- A risk analyst may only care whether the event creates crowding, exposure concentration, or tail-risk asymmetry.

The information is the same. The application is different. VIZA exists to bridge that gap.

## Product Positioning

### VIZA Is Not

- A Bloomberg replacement.
- A FactSet, LSEG, Koyfin, or AlphaSense clone.
- A trading-signal vending machine.
- A black-box AI market explainer.
- A static dashboard.
- A portfolio optimizer.
- A generic social investing feed.
- A copy-trading app by default.
- A licensed investment adviser by default.

### VIZA Is

- A desktop research-methodology builder.
- A visual attribute, event, and relationship graph.
- A data-source integration layer for user-entitled data.
- A local-first research runtime with strong auditability.
- A point-in-time evidence and validation environment.
- A deployment surface for custom radars, scorecards, watchlists, alerts, and exports.
- A future strategy-aware insight translation system.
- A possible future marketplace for methodology templates and research outputs, only after legal, compliance, and data-rights constraints are designed carefully.

Best one-line positioning:

```text
VIZA translates market information into the language of each investor's strategy.
```

Supporting line:

```text
It lets investors design their own research logic, run it over real assets,
and receive insight in the exact format their strategy needs.
```

## Target Users

### Beachhead Users

The first wedge should favor sophisticated individuals and independent researchers who already have a lens but are underserved by institutional terminals and generic trading apps:

- Advanced individual investors.
- Independent traders with a repeatable process.
- Quantamental retail investors.
- Event-driven retail investors who combine qualitative catalysts with technical confirmation.
- Independent research creators who want to encode and eventually monetize a research process.

### Primary Long-Term Users

- Equity analysts.
- Sector PMs.
- Independent research shops.
- Family-office analysts.
- Quantamental investors.
- Strategy researchers.
- Advanced individual investors with an existing research process.

### Secondary Users

- Risk analysts.
- Macro researchers.
- Data vendors who want their data usable inside custom research workflows.
- Strategy creators who want to distribute research logic or black-box research outputs.
- Educators and investment communities that want structured, auditable research templates.

## First Product Wedge

The first product wedge should not attempt to map every possible investing insight.

The first wedge should be:

```text
VIZA for event-driven individual investors who combine technical signals with qualitative catalysts.
```

Concrete job:

```text
Turn qualitative catalysts into strategy-ready signals for investors who already use
technical or quantamental methods.
```

Initial catalyst families:

- Acquisition rumors.
- Confirmed merger and acquisition announcements.
- Earnings surprises.
- Analyst upgrades and downgrades.
- Insider transactions.
- Unusual volume and liquidity events.
- Regulatory events.
- SEC filing novelty.
- Management commentary changes.
- News and social sentiment shifts.
- Sector or peer contagion events.

Initial technical and quantitative overlays:

- RSI.
- Momentum.
- Moving-average trend.
- Volume spike.
- Realized volatility.
- Short-term reversal.
- Peer-relative return.
- Market beta.
- Sector-relative strength.
- Residual return from AAT.

## Current Implementation Snapshot

As of 2026-05-12, the implemented prototype is materially beyond the original Phase 0-5 spec. It is current through the Phase 15 implementation log.

### Implemented

- Electron + React desktop workspace at `apps/viza-desktop/`.
- React Flow methodology canvas as the first screen.
- Python FastAPI local engine at `viza/service.py`.
- Token-protected local engine bridge with dynamic loopback port allocation.
- Durable graph schema `viza_graph_v0`.
- Current node types: `universe`, `attribute`, `transform`, `filter`, `score`, `relationship`, `output_radar`.
- Current edge types: `data_flow`, `relationship`, `evidence`.
- Graph validation, topology-aware execution, stable graph hashes, and node execution results.
- Attribute registry schema `viza_attribute_registry_v1`.
- Registry version `1.1.0` with 73 attributes exposed by the local engine.
- Searchable desktop attribute picker with family/source/unit/status/entitlement/scoring filters.
- Deterministic prototype resolvers plus local universe-backed values for available fields.
- Connector and entitlement catalog with local workspace, local CSV, local parquet skeleton, local SQLite/DuckDB skeleton, AAT Postgres skeleton, Kenneth French, SEC EDGAR, FRED, and FMP.
- Runtime warnings for unavailable, credential-required, non-queryable, and export-limited sources.
- Relationship view with company-to-attribute, company-to-sector/industry, peer, and event-style evidence edges.
- `/viza/relationships/query` for filtered relationship queries.
- Local SQLite project store with projects, methodology versions, run records, saved radar outputs, connector settings metadata, user settings, watchlists, and alerts.
- Methodology version save/load/history/compare/clone/revert workflow.
- Run manifests with graph hash, registry versions, runtime version, universe metadata, connector states, entitlement states, warning codes, evidence checksum, and result checksum.
- Reproducibility endpoint `/viza/reproduce`.
- Batch/backtest endpoint `/viza/batch/execute` with cutoff execution, point-in-time checks, per-run diagnostics, cache keys, and persisted historical runs.
- Radar designer controls for filtering, sorting, displayed columns, evidence counts, scorecards, saved radars, watchlists, local alerts, and CSV/JSON/manifest/methodology exports.
- Entitlement-aware export redaction for restricted evidence and cells.
- Backend release diagnostics endpoint `/viza/diagnostics`.
- Desktop diagnostics panel with app version, engine version, Python version, runtime path, project path, log path, connector summary, last run status, refresh, and local engine restart.
- Windows unpacked development package and package contents smoke test.
- macOS release automation scripts/configuration for a signed/notarized DMG/ZIP build on macOS.
- Desktop package version `0.1.0`.

### Not Yet Implemented

- Native OS credential vault storage for connector secrets.
- Fully source-backed production resolvers for the expanded 73-attribute catalog.
- Full canonical asset/security master.
- Insight object schema in executable runtime output.
- Strategy profile nodes and strategy translation engine.
- Marketplace, creator reputation, or monetized strategy-output flows.
- Production Windows signed installer.
- Signed/notarized macOS artifact built on an actual macOS machine with Apple credentials.
- Fully bundled engine runtime for all release targets; Windows development packaging can still use system Python unless a sidecar exists.
- Large-data execution architecture, streaming progress, durable cancellation, and scheduler services.

## Final Product Workflow

1. The user opens the desktop application.
2. The first screen is a blank methodology canvas.
3. A left toolbar exposes universes, assets, attributes, events, data sources, transforms, filters, technical indicators, scoring nodes, strategy-profile nodes, insight-extraction nodes, relationship nodes, validation gates, and output nodes.
4. The user drags nodes onto the canvas and connects them into a methodology graph.
5. The user selects data sources, universes, asset classes, and strategy constraints.
6. VIZA validates data availability, entitlements, units, identifiers, timestamps, point-in-time rules, and licensing policies.
7. VIZA resolves assets through its canonical asset database.
8. VIZA runs the methodology graph.
9. VIZA extracts or computes attributes, events, and candidate insights.
10. VIZA translates candidate insights through the user's strategy profile.
11. VIZA produces ranked assets, strategy-compatible insight objects, relationship graph views, evidence tables, signal-fit explanations, diagnostics, saved radars, watchlist updates, alerts, and point-in-time manifests.
12. The user inspects individual companies/assets in the exact context of the methodology graph.
13. The user sees why an insight matters, where it came from, how fresh it is, whether it fits the strategy, and what conditions would invalidate it.
14. The user iterates, saves the methodology, compares versions, and optionally deploys it as a recurring research radar.
15. In future versions, the user may publish a methodology template or black-box research output stream into a marketplace.

The current prototype implements the canvas, local execution, radar output, relationship/evidence inspection, methodology versioning, batch/backtest runs, exports, diagnostics, and package readiness pieces. Strategy profiles, insight extraction, canonical asset resolution, and marketplace flows are roadmap items.

## Core Concepts

### Asset

An asset is any investable or researchable object that can be referenced by VIZA.

Examples:

- Common stock.
- ETF.
- Option contract.
- Index.
- Future.
- Currency pair.
- Crypto asset.
- Commodity.
- Bond or credit instrument.
- Private company, if used for relationship context.
- Macro series, if treated as a research object.

Every asset should map to a canonical VIZA asset ID. The current prototype mostly uses ticker-level local universe records; full canonical asset identity is future work.

### Canonical Asset Database / Security Master

The canonical asset database is VIZA's internal identity layer.

VIZA should not manually create raw asset data from scratch. It should use external providers for source data, then normalize that data into an internal security master.

The canonical asset object should eventually include:

```text
asset_id
asset_class
primary_symbol
current_name
former_names
exchange
country
currency
CIK
FIGI
LEI, where applicable
CUSIP / ISIN / SEDOL, where licensed and available
sector
industry
listing_status
tradable_instruments
corporate_action_history
identifier_history
related_entities
provider_identifier_map
source_lineage
license_policy
created_at
updated_at
```

The purpose of this layer is to prevent VIZA from becoming brittle when different providers use different identifiers, ticker histories, corporate-action handling, or naming conventions.

### Attribute

An attribute is any research variable that can describe or relate an asset, company, event, market, or macro condition.

Examples:

- Market beta.
- Sector return.
- Peer basket return.
- Revenue growth.
- Gross margin trend.
- EPS revision.
- Filing materiality.
- Insider activity.
- Ownership change.
- Credit spread sensitivity.
- Supply-chain exposure.
- Theme score.
- Momentum.
- RSI.
- Volatility.
- Liquidity.
- Analyst estimate dispersion.
- Event novelty.
- Social sentiment.
- News-source credibility.

Every attribute must define:

- key and display name,
- description,
- family,
- unit,
- source and source type,
- frequency,
- coverage,
- freshness,
- timestamp policy,
- license/entitlement/cache policy,
- point-in-time status,
- contribution stage,
- whether it can be used in production scoring,
- whether it is research-only or evidence-only,
- compatible transforms and nodes,
- diagnostics and limitations,
- model/data versioning.

Current implementation: VIZA exposes 73 registry v1 attributes with metadata, entitlement restrictions, deterministic prototype resolvers, and a promotion checklist for source-backed production readiness.

### Event

An event is a timestamped occurrence that may affect an asset or relationship.

Examples:

- Filing publication.
- Earnings release.
- Acquisition rumor.
- Merger announcement.
- Analyst upgrade.
- Insider purchase.
- Regulatory action.
- Product launch.
- Management change.
- Supply-chain disruption.
- Social sentiment spike.
- Peer-company shock.

Every event should define event type, affected assets, related entities, observed timestamp, available timestamp, source, evidence, freshness, confidence, materiality, novelty, point-in-time status, and license policy.

Current implementation: VIZA has event-oriented attributes and event/evidence relationships, but not a standalone event object model or catalyst node yet.

### Insight Object

An insight is structured investment meaning derived from one or more attributes, events, relationships, or methodology outputs.

An insight is not just a summary. It is a strategy-aware object that can be used, tested, filtered, translated, audited, and potentially exchanged.

A VIZA insight should eventually include:

- `insight_id`
- `asset_id`
- related asset IDs
- `insight_type`
- direction
- magnitude
- confidence
- time horizon
- evidence references
- source policy
- observed/available/generated timestamps
- strategy compatibility
- risk factors
- invalidation conditions
- action layer
- derivation trace

Current implementation: VIZA produces ranked radar rows, evidence records, relationships, diagnostics, and manifests. It does not yet emit first-class insight objects.

### Methodology Graph

A methodology graph is the user's research logic.

It contains nodes and edges. Nodes represent universes, attributes, transforms, filters, scorers, relationship queries, outputs, and eventually assets, data sources, events, insight extractors, strategy profiles, validation gates, and explanations. Edges represent data flow, dependency, relationship type, evidence flow, or causal hypothesis.

The graph is saved as structured data, not a screenshot. A saved graph must be executable, auditable, versioned, and portable between machines when the required data sources are available.

Current implementation: VIZA uses `viza_graph_v0` with current node/edge vocabularies, graph validation, save/load, methodology versioning, graph hashing, and executable graph compilation.

### Strategy Profile

A strategy profile describes how a user thinks and acts as an investor.

It is not merely preferences. It is the interpretive lens that VIZA uses to translate raw information into useful output.

A strategy profile can include:

- asset classes,
- universe constraints,
- holding period,
- preferred indicators,
- catalyst types,
- required confirmations,
- risk limits,
- liquidity constraints,
- position-sizing assumptions,
- excluded sectors or securities,
- preferred output format,
- action thresholds,
- invalidation logic,
- evidence requirements.

Current implementation: not built yet. This is the next major strategic product layer after the current methodology/radar/runtime foundation.

### Insight Translation

Insight translation converts raw information into the format required by a user's strategy.

Example:

```text
Raw information:
A social post claims Company A is nearing an acquisition deal with Company B.

RSI swing strategy translation:
- Event type: acquisition rumor.
- Asset affected: target company.
- Strategy relevance: catalyst can reframe oversold RSI as potential reversal rather than weakness.
- Required confirmation: source credibility, volume spike, price reclaim of moving average.
- Suggested output: add to catalyst watchlist, do not trigger entry until confirmation gate passes.

Fundamental strategy translation:
- Event type: acquisition rumor.
- Asset affected: target company and acquirer.
- Strategy relevance: possible valuation floor and deal-premium upside.
- Required analysis: precedent transaction premium, regulatory likelihood, downside to unaffected price.
- Suggested output: research deeper and build event probability model.
```

Current implementation: not built yet. The current system provides the graph, evidence, attributes, connectors, and audit substrate needed before this layer is added.

### Relationship Graph

A relationship graph shows how companies, securities, sectors, factors, events, filings, peers, owners, suppliers, customers, macro variables, user-defined attributes, and insights are connected.

This is the Obsidian-inspired layer. It should reveal clusters, hidden dependency paths, common drivers, second-order relationships, and insight reactions.

Current implementation: VIZA supports company-centered relationship and evidence views with family filtering, search, confidence, source lineage, and evidence details. Deeper graph algorithms, cluster detection, path search, and insight relationships are future work.

### Research Radar

A radar is a deployed methodology graph.

It runs over a selected universe and emits assets that match the user's logic. It can be refreshed manually or on a schedule. It preserves methodology version, input data versions, timestamp cutoff, results, evidence, warnings, connector state, entitlement state, and checksums.

Current implementation: VIZA can run radars from methodology graphs, design/display the output, save radar outputs, create watchlists, define local alerts, export permitted payloads, and run historical batches.

### Data Connector

A connector is an integration with a data source.

Connector types should include:

- local CSV/parquet files,
- local databases,
- public sources such as SEC EDGAR, FRED, and Kenneth French,
- paid APIs such as FMP,
- institutional sources such as Bloomberg, FactSet, LSEG, S&P Capital IQ, or other user-entitled providers,
- internal company databases.

VIZA must treat provider data rights as an engineering constraint. Some data may be query-only, some may be cacheable, and some derived values may not be redistributable. The connector layer must track this explicitly.

Current implementation: VIZA has connector definitions, health/field/preview endpoints, entitlement policies, credential availability checks, source-state manifests, warnings, and export redaction. Real credential UI and production readers remain future work.

### Project Store

The project store is the local durable workspace for user-owned VIZA work.

Current implementation: the local SQLite store persists projects, methodology versions, run records, saved radar outputs, watchlists, alerts, connector settings metadata, and user settings. Portable `.viza.json` methodology files remain the import/export format.

### Audit Manifest

Every result must be reproducible or clearly explain why it is not.

Current implementation: run manifests include methodology/version context, graph schema/hash, runtime version, registry versions, timestamp cutoff, universe metadata, connector states, entitlement states, model/data versions, node statuses, warnings, evidence checksum, and result checksum. `/viza/reproduce` compares baseline and observed manifests.

### Diagnostics

Diagnostics are a first-class release-readiness feature, not an afterthought.

Current implementation: `/viza/diagnostics` reports engine version, diagnostics version, Python/platform/runtime paths, local token mode, registry version/count, connector readiness, project-store health, and backend checks. The desktop panel adds app version, engine runtime mode, log path, project path, refresh, and engine restart.

## Data Strategy

### High-Level Answer

VIZA should not become a raw data vendor. It should:

1. Use external providers for commodity raw data.
2. Build its own normalized, point-in-time, insight-aware database on top.
3. Preserve evidence, provenance, licensing policy, and strategy context.
4. Make source limitations visible at design time, runtime, and export time.

VIZA should be data-provider agnostic but insight-proprietary.

### Data VIZA Should Outsource

- Historical prices and OHLCV.
- Corporate fundamentals.
- SEC filings and XBRL facts.
- News and transcripts.
- Social/media sources where legally and technically appropriate.
- Macro series.
- Options and positioning data.
- Institutional data from user-entitled providers.

### Data VIZA Should Own Internally

- Canonical asset and entity identity.
- Provider identifier maps.
- Attribute registry and metadata.
- Methodology graph definitions.
- Strategy profile definitions.
- Evidence records and checksums.
- Point-in-time observation metadata.
- Run manifests and validation ledger.
- Extracted insights and strategy translations.
- User-created radars, watchlists, alerts, and methodology versions.

Current implementation owns the methodology graph, registry metadata, local project store, run/evidence manifests, connector metadata, and local research outputs. The canonical asset database, point-in-time observation store, extracted insight database, and strategy profile layer are future work.

## Final Application Modules

### 1. Desktop Shell

Required final capabilities:

- downloadable Windows and macOS app,
- local project files and local project store,
- secure credential storage,
- local engine sidecar,
- background workers,
- diagnostics and crash/log visibility,
- offline access to cached and permitted data,
- app updates eventually.

Current implementation:

- Electron + React desktop app,
- local FastAPI engine bridge,
- Windows unpacked dev package,
- macOS release automation scripts/config,
- diagnostics panel,
- restartable local engine,
- file save/load,
- local project store.

Next work:

- signed Windows installer,
- signed/notarized macOS artifact produced on macOS,
- native credential vaults,
- fully bundled engine runtime for all release targets.

### 2. Methodology Canvas

Required final capabilities:

- drag and drop nodes,
- connect typed edges,
- inspect/configure nodes,
- group subgraphs,
- annotate graphs,
- save/load methodology files,
- validate graph execution,
- version methodology definitions,
- clone/compare/revert versions,
- show execution status at each node,
- show missing data and invalid connections before running,
- support strategy-profile and insight-extraction nodes.

Current implementation covers the core graph creation, configuration, validation, save/load, execution, versioning, and comparison loop for the current node vocabulary.

### 3. Attribute And Insight Registry

Required final capabilities:

- search and filter thousands of attributes,
- search and filter insight types,
- group attributes by family and source,
- show coverage, freshness, entitlements, and point-in-time status,
- distinguish production, research, shadow, and evidence-only attributes,
- expose compatible transforms and node types,
- let users create custom attributes and insight types.

Current implementation covers the attribute side with registry v1, 73 attributes, source/entitlement metadata, and a searchable picker. Insight type registry is future work.

### 4. Canonical Asset And Entity Layer

Required final capabilities:

- canonical VIZA asset IDs,
- provider identifier mapping,
- corporate action handling,
- entity/security/instrument relationships,
- source lineage and license policy by identifier.

Current implementation uses local universe ticker records and relationship metadata. Full canonical asset identity is future work.

### 5. Data Source And Entitlement Layer

Required final capabilities:

- connect data sources,
- test credentials,
- report available fields,
- enforce source licensing rules,
- preserve raw snapshots where allowed,
- store source lineage,
- support point-in-time cutoffs,
- explain missing data by source and entitlement status,
- block exports or marketplace distribution when source terms do not permit it.

Current implementation provides connector metadata, skeletons, a local CSV path, entitlement policy models, runtime warnings, connector manifests, and export redaction. Real connector configuration UI, OS credential storage, and production source readers remain future work.

### 6. Point-In-Time Observation Store

Required final capabilities:

- store observations with observed/available/as-of timestamps,
- preserve source versions,
- support historical cutoffs,
- support cache-key based reruns,
- detect look-ahead violations,
- support backtest-safe execution at scale.

Current implementation carries point-in-time evidence timestamps, cutoff checks, batch/backtest diagnostics, and cache keys, but does not yet have a full durable observation store.

### 7. Research Runtime

Required final capabilities:

- compile graphs into execution plans,
- run over selected universes,
- validate units and timestamps,
- cache intermediate outputs,
- produce deterministic run manifests,
- handle failures per node,
- support batch execution,
- support point-in-time backtests,
- produce diagnostics and explainability artifacts,
- emit structured insight objects and translated strategy outputs.

Current implementation covers graph compilation, local execution, scoring, relationships, evidence, manifests, batch/backtest execution, and diagnostics. Insight objects and translated strategy outputs are future work.

### 8. Insight Extraction And Ontology Engine

Required final capabilities:

- extract structured insights from attributes, events, text, filings, charts, and methodology outputs,
- classify insight type,
- assign direction, confidence, magnitude, horizon, and invalidation conditions,
- deduplicate, relate, and conflict-check insights,
- preserve source lineage and license constraints.

Current implementation has event/fundamental/macro/positioning attributes and evidence metadata, but not a first-class insight ontology or extraction engine.

### 9. Strategy Profile And Translation Engine

Required final capabilities:

- define user strategy profiles,
- map insight types to compatible strategies,
- transform insight objects into strategy-specific language,
- rank insights by relevance to a strategy,
- suppress irrelevant insights,
- explain strategy fit,
- convert insights into watchlist, research, alert, or radar actions.

Current implementation has methodology-defined scoring and local alerts, but not strategy profile nodes or insight translation.

### 10. Relationship Engine

Required final capabilities:

- entity relationships: company, security, peer, sector, owner, supplier, customer, executive, event, factor, macro series,
- attribute relationships: correlation, lag, co-movement, shared exposure, event co-occurrence, common source, common peer basket,
- insight relationships: conflict, reinforcement, dependency, confirmation, invalidation, time-horizon mismatch,
- visual graph exploration,
- relationship scoring,
- path search,
- cluster detection,
- edge evidence and timestamp lineage.

Current implementation covers the first company-centered relationship/evidence view and query API.

### 11. Radar And Output Designer

Required final capabilities:

- ranked tables,
- watchlists,
- graph views,
- scorecards,
- evidence tables,
- attribution tables,
- insight cards,
- strategy-fit explanations,
- custom columns,
- custom filters,
- exports where licensing permits,
- scheduled refresh definitions,
- result history,
- alerts and notification rules.

Current implementation covers configurable radar rows, selected columns, filtering, sorting, scorecards, saved radars, watchlists, local alerts, and entitlement-aware CSV/JSON/manifest/methodology exports.

### 12. Audit, Evidence, And Reproducibility

Required final capabilities:

- methodology version,
- strategy profile version,
- data-source versions,
- run timestamp,
- timestamp cutoff,
- information-available-at cutoff,
- connector entitlement state,
- node-level evidence,
- source lineage,
- licensing state,
- warnings and missing-data explanations,
- deterministic run manifests,
- exportable audit records where licensing allows.

Current implementation covers all items except strategy profile version and full source-data reproducibility.

### 13. Marketplace And Strategy Monetization Layer

This module is a future roadmap item, not the current MVP.

Required eventual capabilities:

- publish methodology templates,
- publish research packs,
- publish black-box research output streams,
- subscribe to strategy outputs,
- preserve creator privacy where appropriate,
- protect source data rights,
- track strategy-output history,
- show performance and calibration metrics,
- expose drawdown and failure periods,
- label in-sample vs out-of-sample results,
- prevent misleading performance claims,
- support creator reputation,
- support audit and dispute resolution.

Important constraint: VIZA should avoid treating strategies as securities, funds, managed accounts, or personalized investment advice without legal review. Early marketplace language should focus on methodology templates, research outputs, and software-generated research objects.

### 14. Compliance And Risk Controls

Required final capabilities:

- clear product boundaries between research software and personalized investment advice,
- source and confidence labeling,
- data rights enforcement,
- rumor and unverified catalyst labeling,
- model-output uncertainty labels,
- social-media-source risk warnings,
- creator performance disclaimers,
- marketplace compliance review before monetized output streams,
- audit logs for marketplace strategy claims,
- user-level entitlement enforcement.

Current implementation has source/entitlement labels, export redaction, warnings, audit manifests, and connector visibility. Formal compliance review and marketplace controls are future work.

## Relationship To The Current AAT Repo

The current AAT repo should not be thrown away.

Reusable parts:

- point-in-time timestamp discipline,
- deterministic return accounting,
- attribution contracts,
- factor models,
- event evidence model,
- exposure review policy,
- database schema concepts,
- ingestion adapters,
- backfill jobs,
- API response models,
- tests and look-ahead audit discipline.

Parts that can become secondary:

- current web dashboard layout,
- server-first dashboard assumption,
- attribution-only product framing,
- one-size-fits-all driver table as the only primary interface.

Repository direction:

- Keep this repository for now.
- Continue isolating VIZA under `apps/viza-desktop/`, `viza/`, `config/viza_attribute_registry.json`, and `docs/VIZA_*.md`.
- Let AAT become an engine package inside VIZA.
- Treat AAT attribution as one node family inside the broader methodology graph.
- Add schemas for asset identity, insight objects, strategy profiles, licensing policies, and validation ledgers as the next product layers mature.
- Split into a separate repository only if packaging, licensing, or team boundaries make the monorepo painful.

## Prototype Objective

The implemented prototype proves:

```text
Canvas -> Methodology Graph -> Local Engine -> Radar Table
  -> Relationship/Evidence View -> Project Store -> Audit/Backtest/Export
```

The next strategic prototype should prove:

```text
Canvas -> Methodology Graph -> Asset/Event Evidence
  -> Insight Extraction -> Strategy Translation -> Strategy-Fit Radar
```

The first strategic wedge should stay narrow:

```text
U.S. equities + event-driven catalysts + technical confirmation.
```

## Current Prototype Scope

### Platform

- Desktop shell: Electron.
- UI: React, TypeScript, React Flow.
- Engine: Python FastAPI local service.
- Storage: local SQLite project store.
- Packaging: Windows unpacked dev package; macOS release automation ready for macOS build host.

### Current Nodes

- Universe.
- Attribute.
- Transform.
- Filter.
- Score.
- Relationship.
- Output Radar.

### Future Nodes

- Asset Resolver.
- Data Source.
- Technical Indicator.
- Event/Catalyst.
- Insight Extractor.
- Strategy Profile.
- Compatibility Gate.
- Evidence.
- Scheduler/Refresh.

### Current Attributes

The current registry exposes 73 attributes across:

- baseline attribution,
- macro attribution,
- event intelligence,
- fundamentals,
- exposure gates,
- positioning/options,
- local universe descriptors.

Many expanded attributes are deterministic prototype values or evidence-only/shadow attributes. They are useful for workflow design and UI coverage, not yet fully source-backed production analytics.

### Current Acceptance Status

The prototype currently satisfies:

- local desktop app loads,
- blank methodology canvas is first screen,
- users can create/connect/configure/save/load nodes,
- app can execute graphs over local universes,
- output table is generated from the graph,
- relationship view shows company-to-attribute and company-to-peer/classification context,
- outputs include evidence metadata,
- missing data and source limitations do not crash execution,
- methodology versions can be saved, loaded, cloned, compared, and reverted,
- runs can be audited and reproduced,
- historical batches/backtests can run over cutoffs,
- radars can be configured, saved, exported, and used to create watchlists/alerts,
- diagnostics and engine restart are visible in the app,
- VIZA changes have maintained the broader AAT test suite.

The prototype does not yet satisfy:

- canonical asset resolution,
- first-class insight object output,
- strategy profile translation,
- company-to-insight relationship edges,
- production-grade source-backed attribute coverage,
- native credential vaults,
- signed release artifacts for users.

## Implementation Roadmap

The detailed engineering roadmap lives in `docs/VIZA_DETAILED_IMPLEMENTATION_PLAN.md`; implementation history lives in `docs/implementationlog.md`.

Current completed implementation phases:

- Phase 0: product/repo foundation.
- Phase 1: methodology canvas foundation.
- Phase 2: local engine bridge.
- Phase 3: executable methodology runtime.
- Phase 4: first data-backed radar with prototype fallbacks.
- Phase 5: relationship and evidence experience.
- Phase 6: packaging and desktop runtime hardening.
- Phase 7: attribute registry v1 and searchable attribute UX.
- Phase 8: data source and entitlement layer.
- Phase 9: local project store and methodology versioning.
- Phase 10: audit, evidence, and reproducibility.
- Phase 11: backtesting and batch execution.
- Phase 12: radar designer, watchlists, alerts, and exports.
- Phase 13: production attribute expansion.
- Phase 14: product release readiness.
- Phase 15: repository-side macOS external release automation.

Recommended next roadmap:

1. Replace high-value deterministic prototype attributes with source-backed resolvers.
2. Add real connector configuration UI and OS credential vault storage.
3. Add canonical asset/security master seed schema.
4. Add first-class event/catalyst objects.
5. Define and implement the first insight object schema.
6. Add a template strategy profile for "RSI swing + catalyst confirmation."
7. Add strategy-fit explanation to radar rows.
8. Add signed Windows installer and execute macOS release on macOS.
9. Add larger-data runtime behavior: streaming progress, cancellation, scheduling, and durable caches.
10. Defer marketplace until insight objects, validation ledger, compliance rules, and data-rights enforcement are credible.

## Open Product Questions

### Product Scope

- Should the first strategic wedge be event-driven/technical translation, or should VIZA stay analyst-radar-first for one more cycle?
- Should VIZA serve advanced individual investors first, or professional analysts first?
- Should strategy profiles be user-defined from day one, or start with templates?
- Should VIZA support non-equity asset classes in the prototype or only after U.S. equities are strong?

### Data Architecture

- Which first external connector matters most after local/public data?
- Which identifiers should be mandatory in the first security master?
- How should VIZA reconcile conflicting provider data?
- How much raw data can be cached under each provider's terms?
- Should the first observation store be SQLite, DuckDB, Postgres, or a hybrid?

### Methodology Design

- Should users design formulas visually only, or also write small expressions?
- How much freedom should users have before graph validation rejects a methodology?
- Should methodology graphs support reusable subgraphs?
- Should relationship edges be calculated lazily on demand or materialized in a graph table?

### Insight Translation

- What is the first canonical insight schema?
- Which insight types should ship first?
- How much of insight extraction should be model-driven versus rule-driven?
- How should VIZA handle uncertainty, rumor, contradiction, and low-confidence sources?
- What does a good strategy-fit explanation look like?

### Marketplace And Compliance

- When should marketplace features enter the roadmap?
- What can be monetized without becoming investment advice or an investment product?
- How should VIZA distinguish research templates from personalized recommendations?
- How should VIZA validate strategy creators' performance claims?
- What source data can marketplace creators legally redistribute or derive from?

## Final-Version Success Criteria

VIZA reaches its intended final form when:

- It ships as a reliable Windows and macOS desktop app.
- Users can build reusable research methodologies visually.
- The app supports hundreds to thousands of attributes through a searchable registry.
- The app supports a structured ontology of investment insight types.
- Users can connect multiple data sources with entitlement-aware policies.
- The app maintains a canonical asset database and security master.
- Methodologies can run over user-selected universes and asset classes.
- Results are shown as user-defined radars, tables, scorecards, insight cards, and relationship graphs.
- Raw information can be translated into user-specific strategy output.
- Every output has source lineage, timestamp cutoff, evidence, license state, and reproducibility metadata.
- The system can run point-in-time backtests of user methodologies.
- Users can compare methodology versions.
- The app makes missing data, weak evidence, unstable relationships, low-confidence insights, and source restrictions visible.
- Strategy outputs can be validated over time through a ledger.
- Marketplace functionality, if launched, is backed by auditability, rights enforcement, anti-overfitting controls, and compliance review.
- The product's value comes from visual research-methodology design and strategy-aware insight translation, not from pretending to own better raw data than major terminals.

## Reference Notes For Implementation

These are implementation references, not product dependencies. The exact providers can change.

- SEC EDGAR APIs expose company submissions and extracted XBRL data through `data.sec.gov`, including submissions history and company facts.
- OpenFIGI can help map securities to FIGIs and related market identifiers.
- GLEIF can help with LEI-based legal entity identity.
- Financial Modeling Prep, Alpha Vantage, Polygon.io, Intrinio, Finnhub, Nasdaq Data Link, and similar providers can be considered for market data, fundamentals, news, transcripts, or other external data.
- QuantConnect's structured insight objects are a useful precedent, but VIZA should go beyond signal representation by adding strategy-specific translation, evidence lineage, licensing rules, and user-defined methodology graphs.
- Social-media-influenced investing and sentiment tools carry misinformation, manipulation, transparency, and data-quality risks; VIZA should label source quality and confidence carefully.

## Sharpest Product Statement

VIZA is a local-first research methodology platform that lets investors design their own investment logic, connect entitled data, transform market information into structured insight, and translate that insight into the exact format their strategy requires.

It is not another dashboard.

It is the infrastructure layer for personalized alpha discovery.
