# VIZA Knowledge-Representation Compliance Report

Last updated: 2026-05-21
Author: deep-research session against the Phase 0–15 prototype and the v0.4 product spec.
Scope: how the current VIZA codebase complies with the eight reference disciplines that should govern its strategies-and-decision-making schema, and what concrete changes would close the gaps.

Disciplines covered, in the order they appear:

1. Ontology engineering (OWL 2 / RDF / SKOS)
2. FIBO (Financial Industry Business Ontology)
3. W3C PROV (provenance and lineage)
4. OMG DMN (Decision Model and Notation, FEEL)
5. Rete (production-rule pattern matching)
6. Complex Event Processing (Esper EPL / event algebras)
7. Bitemporal data modeling (Snodgrass / SQL:2011)
8. Belief revision and argumentation (AGM / Dung / defeasible logic)

Each section is structured the same way:

- **The concept.** What the standard or theory actually says.
- **Where VIZA already complies.** Citations into the current source.
- **Where VIZA diverges.** What the current schema is doing instead.
- **What to change.** Concrete proposals, with rough effort.

A consolidated, prioritized roadmap follows in section 9.

---

## 0. Executive Summary

VIZA is, structurally, a knowledge-representation system disguised as a research methodology platform. Its core artifacts — the attribute registry, the event registry, the insight type registry, the strategy profile, the methodology graph, the relationship graph, the evidence record, the validation record — are all instances of well-studied formalisms in KR&R. The current prototype invents all of them locally and consistently.

That has been the right move for a Phase 0–15 prototype. It will become the wrong move starting around Phase 18 (canonical asset master), because:

- **Identity will leak.** Without FIBO-aligned IRIs, every connector mapping silently invents an identity contract.
- **Provenance will diverge.** `derivation_trace`, `evidence_refs`, `audit.run_id`, `graph_hash`, and `result_checksum` each carry partial lineage; no single subject/predicate vocabulary connects them.
- **Decision logic will ossify.** `compile_decisions` is a hand-rolled `O(rules × entities)` loop with hardcoded predicate operators. It will not survive a serious strategy library.
- **Bitemporal queries will be wrong.** `observed_at` / `available_at` / `retrieved_at` capture *moments*, not *intervals* — VIZA cannot today answer "what did the system believe at time T?" because it has no transaction-time interval.
- **Insight contradictions will not be reasoned over.** The five hardcoded reaction rules in `viza/relationships.py:247` (`acquisition_rumor confirms unusual_volume`, etc.) are a stand-in for an argumentation framework. As soon as a sixth or seventh insight reacts to either, the brittleness compounds.

The actionable takeaway is **not** "adopt all eight standards immediately." It is:

1. **Adopt three foundational vocabularies now** — FIBO for identity, PROV for lineage, SKOS for taxonomies — because they cost the least and pay off in every later phase.
2. **Refactor the rules layer to a DMN-shaped decision table** before the strategy library grows past ~10 profiles. This is the highest-leverage schema change.
3. **Make `viza.observations` and `viza.events` bitemporal** before the observation store grows past a few thousand rows, because the migration cost scales with row count.
4. **Defer Rete, CEP engines, and full Dung argumentation** until the data volume or rule count actually warrants them. Their absence is not currently a bug.

The rest of the report is what justifies each of those moves.

---

## 1. Ontology engineering (OWL 2 / RDF / SKOS)

### The concept

An ontology is a shared, formal specification of the concepts in a domain and the relations between them ([Gruber 1993](https://tomgruber.org/writing/ontolingua-kaj-1993.pdf)). The web stack:

- **RDF** — subject/predicate/object triples; the universal data model.
- **RDFS** — `rdfs:Class`, `rdfs:subClassOf`, `rdfs:domain`, `rdfs:range`.
- **OWL 2** — adds disjointness, inverse properties, cardinality, equivalence, property chains, and decidable reasoning profiles (EL, QL, RL, DL, Full).
- **SKOS** — *Simple Knowledge Organization System*, for taxonomies. `skos:Concept`, `skos:broader` / `skos:narrower` (deliberately loose), `skos:related`, `skos:prefLabel` / `skos:altLabel`, `skos:inScheme`. `skos:broader` and `skos:narrower` are inverse and **only assert direct hierarchical links** ([W3C SKOS reference](https://www.w3.org/TR/skos-reference/)).

When you have a *strict* type hierarchy with logical consequences (every Common Stock IS A Listed Share IS A Security), use OWL. When you have a *navigable* label hierarchy with no logical entailment (catalysts → corporate-action catalysts → M&A catalysts), use SKOS.

### Where VIZA already complies

VIZA has registries that ARE ontologies in disguise:

- `viza/attribute_registry.py:21` — `AttributeDefinition` defines key, family, unit, allowed_transforms, compatible_node_types, point_in_time_status, evidence_policy, license_policy, entitlement_policy. This is an `rdfs:Class` with axioms, written in Pydantic.
- `viza/events.py:21` — `EventTypeDefinition` (key, family).
- `viza/insights.py:22` — `InsightTypeDefinition` (key, family, compatible_strategy_profiles, required_event_types, required_attributes, optional_confirmations, direction_logic, confidence_logic, horizon_defaults, invalidation_templates).
- `viza/graph_schema.py:18` — `VizaNodeType` and `VizaEdgeType` are closed enums (StrEnum), i.e. a closed-world `owl:oneOf` over node/edge classes.
- `viza/relationships.py:369` — `_expand_family_aliases` maps `"insight"` to `{"insight", "entity_to_insight", "insight_to_event", "insight_to_attribute", "insight_to_strategy_profile", "insight_confirms_insight", "insight_conflicts_with_insight", "insight_invalidates_insight"}`. This is a hand-coded `skos:broader` graph.

### Where VIZA diverges

- No formal IRI / namespace for any concept. `acquisition_rumor` is a string in three registries (`viza_event_registry.json`, `viza_insight_registry.json`, the hardcoded reaction list). Renaming one breaks the others silently.
- No subsumption. `acquisition_rumor_with_technical_reversal_context` is "a kind of" `acquisition_rumor` semantically, but the registry does not record that — the matcher in `viza/insights.py:336` re-derives it imperatively (`if event.event_type == "acquisition_rumor" and rsi <= 35`).
- No inverse / symmetric properties. `insight_confirms_insight` and `insight_invalidates_insight` should be declared symmetric or asymmetric; today they are just strings.
- No closed-vocabulary check. Adding a new family in `_expand_family_aliases` is invisible to the rest of the system.

### What to change

1. **Adopt SKOS for every "family" field.** Replace the strings `family`, `relationship_family`, `event_family` with `skos:Concept` IRIs. Persist a `viza_concepts.ttl` (or JSON-LD) alongside the JSON registries. Concrete change in `viza/attribute_registry.py:28`: `family: str` becomes `family_concept_iri: str` with validation against the concept scheme. Effort: small (one weekend of work plus migration), payoff: every taxonomy operation becomes type-safe.

2. **Adopt OWL 2 only for the registries that carry axioms** — i.e., attribute registry and insight registry. Generate the OWL from the Pydantic models rather than authoring it by hand. The Pydantic model stays the source of truth for the engine; OWL is the export for external alignment (FIBO, schema.org). Effort: medium; payoff: external partners and creators can validate `.viza` files without your engine.

3. **Make the node/edge enums extensible by `module_id`.** The spec at §13.2 already gives strategy profiles a `domain` and `module_id`; do the same for node and edge types. This turns `VizaNodeType` from a closed `StrEnum` into a registry. Effort: medium; payoff: future asset classes (real estate, crypto) can ship their own node types without forking the engine. The `viza/real_estate.py` module hint suggests this direction is already implied.

4. **Add a `skos:broader` column to `relationship_family`** so the existing `_expand_family_aliases` table becomes data, not code.

---

## 2. FIBO (Financial Industry Business Ontology)

### The concept

FIBO is the EDM Council's standardized financial ontology, governed jointly with the OMG. As of 2026 it contains ~2,400 classes across the domains: **FND** (Foundations), **BE** (Business Entities), **FBC** (Finance, Business & Commerce), **SEC** (Securities), **IND** (Indices & Indicators), **DER** (Derivatives), **LOAN**, **CAE** (Corporate Actions & Events) ([EDM Council FIBO spec](https://spec.edmcouncil.org/fibo/)).

FIBO gives you:

- Canonical IRIs for legal entities, listed securities, identifiers, exchanges, sectors, corporate actions, and analytical observations.
- A subsumption hierarchy: `ListedShare ⊑ Share ⊑ EquityInstrument ⊑ Security`.
- Identifier disambiguation: LEI, CIK, FIGI, ISIN, CUSIP, SEDOL are distinct identifier types attached to distinct entity types (a company is not a security, and an LEI identifies the company while a FIGI identifies an instrument).

### Where VIZA already complies

- `viza/__init__.py` exports `ConnectorDefinition`, `EntitlementPolicy`, and the PROJECT_SPEC §9.2 sketches an asset object with FIBO-compatible identifier fields: `cik`, `figi`, `lei`, `isin`, `cusip`, `sedol`. The shape is right.
- The spec at §9 distinguishes `asset_id` (an instrument) from `entity_id` (a legal entity), with `related_entities`. This is the FIBO instrument-vs-issuer distinction.
- `VizaEvent.affected_entity_ids` and `affected_asset_ids` are kept separate (`viza/events.py:46-48`) — also FIBO-aligned.

### Where VIZA diverges

- `asset_class: str` (PROJECT_SPEC §9.2) and `asset_class: list[str]` in StrategyProfile (`viza/strategy_profiles.py:142`) are bare strings. There is no link from `"US_EQ"` to the FIBO class `fibo-sec-sec-lst:ListedShare`.
- No FIBO IRIs anywhere. Every identifier (CIK, FIGI) is a string-keyed field on `Asset`, not typed via FIBO's `Identifier` hierarchy.
- `sector` and `industry` are free-form strings on the asset object; FIBO has formal Sector/Industry classes via the GICS/NAICS alignment.
- Events are catalysts ("acquisition_rumor") with no link to FIBO's `CAE` (Corporate Actions) module. A confirmed M&A event in VIZA is structurally unrelated to FIBO's `MergerEvent`.

### What to change

1. **Add a `fibo_iri: str | None` field to every concept registry** — attribute, event, insight, asset, identifier, sector — and populate it with the FIBO IRI where one exists. Leave it nullable for VIZA-native concepts that have no FIBO equivalent (e.g., `acquisition_rumor_with_technical_reversal_context`). Effort: small per field, large in aggregate; payoff: makes `.viza` files interpretable to anyone running a FIBO reasoner.

2. **Seed the canonical asset master (Phase 18) directly against FIBO-SEC.** The `Asset` schema in PROJECT_SPEC §9.2 should be a Pydantic projection of `fibo-sec-eq:CommonStock`, not a parallel invention. Specifically:
   - `asset_class` becomes `instrument_type_iri` referencing FIBO.
   - `identifiers.cik` becomes a typed `Identifier` with `identifier_scheme_iri = fibo-fbc-fct-ra:SecCikIdentifier`.
   - `current_name` is `fibo-fnd-rel-rel:hasName`.
   - `former_names` carries effective-dated FIBO `Name` instances (which, helpfully, is also where bitemporal modeling will need to bite — see §7).

3. **Map event_types to FIBO CAE.** Concretely, in `config/viza_event_registry.json`, add `fibo_iri` to each event type. `confirmed_mna` → `fibo-cae-mer:MergerEvent`. `earnings_surprise` → no direct FIBO concept; declare it as a VIZA-native subclass with `skos:related fibo-fbc-fi:EarningsAnnouncement`.

4. **Adopt FIBO's instrument-vs-issuer split everywhere.** Currently `VizaInsight.entity_id` and `VizaObservation.entity_id` are conflated with "the company"; some observations are about instruments (RSI on AAPL), others about entities (insider transaction by Tim Cook). Insist on both fields in observations: `instrument_iri` and `legal_entity_iri`, with FIBO `isIssuedBy` linking them.

---

## 3. W3C PROV (provenance and lineage)

### The concept

PROV is the W3C provenance model ([PROV-O](https://www.w3.org/TR/prov-o/)). Three core classes:

- `prov:Entity` — something whose provenance is being tracked (a data value, a row, an insight, a `.viza` file).
- `prov:Activity` — a process that generated or consumed entities (a methodology run, a connector fetch, an event extraction).
- `prov:Agent` — who or what is responsible (a user, a connector, a model version).

Five core relations:

- `prov:wasDerivedFrom` (Entity → Entity)
- `prov:wasGeneratedBy` (Entity → Activity)
- `prov:used` (Activity → Entity)
- `prov:wasInformedBy` (Activity → Activity, communication via shared entity)
- `prov:wasAttributedTo` (Entity → Agent)

PROV is deliberately small. The point is that *every* lineage graph in *every* tool can compile to these five edges.

### Where VIZA already complies

VIZA's lineage substrate exists; it just doesn't use PROV vocabulary.

- `viza/audit.py:13` — `EvidenceRecord` with `source`, `source_record_id`, `source_timestamp`, `timestamp_available`, `data_version`, `model_version`. PROV-equivalents: `prov:wasAttributedTo`, `prov:wasGeneratedAtTime`.
- `viza/insights.py:80` — `VizaInsight.derivation_trace` carries `event_id`, `event_type`, `source_credibility`, `definition`, `confidence_logic`. This is `prov:wasDerivedFrom` plus diagnostic metadata.
- `viza/decisions.py:119` — `DecisionAudit` with `graph_hash`, `profile_version`, `run_id`, `evidence_checksum`. This is `prov:Activity` with content-addressed identifiers.
- `viza/observations.py:31` — `VizaObservation.source_id`, `connector_id`, `source_record`, `data_version`, `model_version` — `prov:wasGeneratedBy` plus `prov:wasAttributedTo`.
- `viza/validation_ledger.py:28` — `VizaValidationRecord` ties `graph_hash`, `result_checksum`, `evidence_checksum`, `data_versions`, `model_versions`, `connector_states`. This is a PROV bundle.

### Where VIZA diverges

- No PROV namespace, no Activity-centric perspective. VIZA's lineage is recorded per-output (insight has trace, observation has source) rather than per-process. There is no first-class "Activity" record for "the methodology run that produced this insight."
- Lineage edges are not uniform. `evidence_refs` is a list of strings like `"attr:AAPL:event_materiality"`. To find what activity produced one of those, you grep.
- Agents are implicit. `creator_id` exists in the `.viza` manifest (PROJECT_SPEC §7.6) but no observation, insight, or decision carries `wasAttributedTo` an `Agent`.
- Activities are not first-class entities in storage. A run is a `run_id` string and a `validation_record`; it is not queryable as a node with incoming `prov:used` and outgoing `prov:wasGeneratedBy` edges.

### What to change

1. **Promote `MethodologyRunResult` to a first-class PROV Activity.** Persist a `runs` table whose rows ARE `prov:Activity` instances with `startedAtTime`, `endedAtTime`, `wasAssociatedWith` (the user/agent), and edges to every entity consumed/generated. The data is already there; this is renaming + indexing. Effort: small; payoff: every "where did this come from?" question becomes a single SQL/SPARQL query.

2. **Adopt PROV vocabulary at the manifest layer of `.viza` files.** PROJECT_SPEC §7.6 currently has `created_by.creator_id`. Promote it to a `prov:wasAttributedTo` with a full `prov:Agent` block, and add `prov:wasGeneratedBy` linking the file to the run that produced it. This is the cheapest single change with the highest external interop payoff (auditors, marketplace reviewers, regulators all speak PROV).

3. **Replace `evidence_refs: list[str]` with a typed PROV graph.** Today `viza/audit.py:82` normalizes evidence records into a dict. Replace with:
   ```python
   class ProvenanceEdge(BaseModel):
       subject_iri: str          # entity or activity
       predicate: Literal[
           "wasDerivedFrom", "wasGeneratedBy", "used",
           "wasInformedBy", "wasAttributedTo"
       ]
       object_iri: str
       generated_at_time: datetime | None = None
       rights_policy_ref: str | None = None
   ```
   This is the same data, but every edge becomes typed and queryable as a graph. Effort: medium; payoff: replay/reproduce/compare become graph isomorphism checks instead of dict comparisons.

4. **Make `graph_hash`, `result_checksum`, `evidence_checksum` content-addressed PROV Entities.** Each becomes an immutable `prov:Entity` with its sha256 as the IRI suffix. `wasDerivedFrom` then forms a Merkle DAG. This is the substrate for any future marketplace dispute: "show me the chain of entities that derive this signal."

---

## 4. OMG DMN (Decision Model and Notation)

### The concept

DMN is the OMG standard for representing business decisions ([DMN 1.5](https://www.omg.org/spec/DMN/)). Three main artifacts:

- **DRD (Decision Requirements Diagram).** A graph of `Decision`, `InputData`, `BusinessKnowledgeModel`, and `KnowledgeSource` nodes. The flow chart of the strategy.
- **Decision Table.** A table of rules. Columns are inputs and outputs; rows are rules; each cell is a FEEL expression. A **hit policy** (Unique, Any, Priority, First, Output Order, Collect) declares how multiple firing rules combine.
- **FEEL (Friendly Enough Expression Language).** A side-effect-free expression language for the cells. Supports ranges, intervals, dates, durations, contexts; allows spaces in identifiers.

DMN conformance levels: **L1** descriptive (decision tables, no execution), **L2** simplified executable (S-FEEL), **L3** full FEEL.

### Where VIZA already complies

Surprisingly close, structurally:

- `viza/strategy_profiles.py:46` — `DecisionTrigger` with `observation_predicates: list[ObservationPredicate]`. Each predicate is `(attribute_key, operator, threshold | range)`. The operators `lte`, `gte`, `lt`, `gt`, `eq`, `between` are exactly FEEL S-FEEL operators.
- `viza/strategy_profiles.py:108` — `DecisionRule` with `trigger`, `action_template`, `effective_from`, `cooldown_policy`, `evidence_requirements`. This is one row of a DMN decision table.
- `viza/strategy_profiles.py:134` — `VizaStrategyProfile.decision_rules: list[DecisionRule]`. This is the table.
- `viza/decisions.py:173` — `compile_decisions` is the table evaluator. It already has a "no overlap" cooldown logic that looks like a custom hit policy.

### Where VIZA diverges

- No DRD. There is no `InputData` / `Decision` / `BusinessKnowledgeModel` separation. The methodology graph at `viza/graph_schema.py` has nodes (`universe`, `attribute`, `transform`, `filter`, `score`, `output_radar`) that are *similar* — `attribute` is `InputData`, `score` and `filter` are `BusinessKnowledgeModel`, `output_radar` is `Decision`. But the mapping is implicit.
- No explicit hit policy. When two rules fire on the same entity, the system emits two decisions. There is no declared `COLLECT`/`PRIORITY`/`FIRST` semantics.
- No FEEL. Predicates are restricted to single-attribute comparisons. There is no way to author "RSI < 30 AND volume_spike > 2 AND days(event.observed_at, cutoff) < 5" as a single rule — you must build a `transform` node upstream or shard the predicate across nodes.
- No business knowledge model. Reusable formulas (RSI bands, materiality scoring) exist only as Python code in `viza/observations.py:374` (`technical_values_from_ohlcv`). DMN would persist these as named `BusinessKnowledgeModel` nodes that decisions reference.

### What to change

1. **Adopt DMN L2 (S-FEEL) for `DecisionTrigger`.** Replace `observation_predicates: list[ObservationPredicate]` with a single `feel_expression: str`. Parse it with a small FEEL subset (the existing operators plus boolean `and`/`or`/`not`). Effort: medium (need a FEEL-S parser); payoff: huge — one expression replaces three nodes of methodology graph.

2. **Declare a hit policy on every strategy profile.** Add `hit_policy: Literal["UNIQUE", "COLLECT", "PRIORITY", "FIRST"]` to `VizaStrategyProfile`. Default `COLLECT` (emit all firings — current behavior). Effort: tiny; payoff: makes the current implicit behavior explicit and reviewable, and unlocks `PRIORITY` for strategy profiles that need a single decision per entity.

3. **Project the methodology graph onto a DRD.** Add a derived view that maps:
   - `universe` / `attribute` nodes → `InputData`
   - `transform` / `score` / `filter` nodes → `BusinessKnowledgeModel`
   - `output_radar` → `Decision`
   - `strategy_profile` (future node, PROJECT_SPEC §15.2) → `KnowledgeSource`
   This makes `.viza` files exportable as DMN XML, which means standard DMN engines (Drools, Camunda, Trisotech) can replay them. Effort: medium; payoff: external auditability without VIZA needing to be the runtime.

4. **Introduce reusable BusinessKnowledgeModel nodes for technical indicators.** Currently `technical_values_from_ohlcv` lives in `viza/observations.py:374` as Python. Lift each indicator (RSI-14, volume-spike, momentum-21) to a named, versioned `BKM` with declared inputs and outputs. Decision rules then reference `RSI-14(closes)`. Effort: medium; payoff: indicators become first-class artifacts users can audit, swap, and override.

5. **Make `action_thresholds` a literal DMN decision table.** Today `viza/strategy_profiles.py:150` has `action_thresholds: dict[str, float]` with keys `watchlist_threshold`, `research_threshold`, `alert_threshold`. This is a DMN table waiting to happen: input = `score`, output = `action_layer`, hit policy = `FIRST` ordered by descending threshold.

---

## 5. Rete algorithm

### The concept

Rete (Forgy 1982) is a pattern-matching algorithm that lets a production rule system answer "which rules fire?" in time roughly proportional to *changed facts*, not *total facts × total rules* ([Rete on Wikipedia](https://en.wikipedia.org/wiki/Rete_algorithm)).

Structure:

- **Alpha network.** One node per atomic predicate. Maintains a set of facts that satisfy that predicate. Updated incrementally on `assert(fact)` / `retract(fact)`.
- **Beta network.** Join nodes that combine alpha outputs across variable bindings. Carries partial-match tokens.
- **Production nodes.** Terminal nodes; each complete token activates a rule.

The point of Rete is that asserting a single new observation re-evaluates only the paths that depend on it.

### Where VIZA already complies

Almost not at all. `viza/decisions.py:209-217` builds a `latest_by_key: dict[(entity_id, attribute_key), VizaObservation]` then iterates `for rule in profile.decision_rules: for entity_id in entity_ids: _evaluate_rule_for_entity(...)`. This is the textbook `O(rules × entities)` naive matcher that Rete was invented to replace.

### Where VIZA diverges

- No alpha network. Every rule re-reads every relevant attribute observation per run.
- No incremental update. Asserting one new observation re-runs `compile_decisions` from scratch.
- No beta joins. Rules can only reference one entity at a time (`_evaluate_rule_for_entity`); there is no way to fire a rule that joins two entities (e.g., "issuer A's insider purchase AND target B's unusual volume").

### What to change

**My recommendation: defer Rete adoption until either (a) `len(decision_rules) > 200`, or (b) cross-entity joins become necessary, or (c) batch runs over the observation store exceed ~5 seconds.** None of those are true today.

When that day comes:

1. **Don't write Rete from scratch.** Use `experta` (Python port of CLIPS) or wrap a Java Drools engine via subprocess. Drools also speaks DMN, which closes the loop with §4.

2. **Until then, prefer two cheaper optimizations:**
   - **Index observations by `(attribute_key, available_at)`.** `viza/observations.py:274` already has an index but it's `(entity_id, attribute_key, available_at)`. Add `(attribute_key, available_at DESC)` so rule evaluation can stream observations that *might* satisfy any predicate without scanning the full table.
   - **Memoize rule firings by `(rule_id, entity_id, max(triggering_obs.available_at))`.** A rule that fired yesterday on `(AAPL, rsi_14d=29.3, available_at=2026-05-20T15:30)` cannot un-fire when a new observation arrives unless the new observation contradicts it. This gives ~Rete-level incrementality without Rete's complexity.

3. **If you do adopt Rete, the prerequisite is DMN (§4).** Rete's strength is matching against declarative patterns. Imperative Python rules cannot be compiled into an alpha/beta network. The DMN → Rete bridge is well-trodden (Drools DMN runs on Drools Rete).

---

## 6. Complex Event Processing (CEP)

### The concept

CEP detects *temporal patterns* over event streams. Esper EPL ([EsperTech reference](https://esper.espertech.com/release-7.1.0/esper-reference/html/event_patterns.html)) is the canonical reference. Core operators:

- **Followed-by** (`A -> B`): event A precedes event B.
- **Conjunction** (`A and B`): both occur, order-free.
- **Disjunction** (`A or B`).
- **Negation** (`not B`): B does *not* occur. Combined with windows: "A and not B within 5 minutes."
- **Every** (`every A`): match every occurrence, not just the first.
- **Windows / guards** (`timer:within(5 min)`, `timer:interval`): bound the pattern in time.
- **MATCH_RECOGNIZE**: SQL:2016-style row-pattern matching, useful for state-machine patterns over an event series.

The semantics are Allen interval algebra ([temporal logic foundations](https://en.wikipedia.org/wiki/Allen%27s_interval_algebra)).

### Where VIZA already complies

Almost not at all on the engine side, but the data model is ready:

- `viza/events.py:40` — `VizaEvent` with `observed_at`, `available_at`, `event_type`, `confidence`. This is a CEP event stream waiting for a query engine.
- `viza/events.py:275` — `extract_events_from_run_result` is a row-by-row extractor that promotes a single observation row to an event. It has no notion of *patterns* across events.
- `viza/relationships.py:247` — five hardcoded reaction rules (`acquisition_rumor confirms unusual_volume`, etc.) are degenerate CEP patterns: each is a 2-event conjunction with no time bound.

### Where VIZA diverges

- No temporal pattern operators. There is no way today to declare "earnings_surprise within 5 trading days of unusual_volume." You can only declare "earnings_surprise" and "unusual_volume" as separate events and post-process.
- No event-stream windowing. Observations are query-time filtered by `available_at <= cutoff`, but there is no concept of a sliding window or session.
- No negation. "RSI is oversold AND no regulatory_action in the last 30 days" is not expressible.
- No MATCH_RECOGNIZE-style state machines. Multi-step patterns like "price reclaim → volume spike → confirming earnings" require manually orchestrated graph nodes.

### What to change

1. **Add a minimal pattern grammar to `DecisionTrigger` or to a new `EventPattern` type.** Don't ship Esper; ship a YAML or JSON grammar:

   ```yaml
   pattern:
     sequence:
       - event_type: acquisition_rumor
         confidence_gte: 0.5
       - event_type: unusual_volume
         within: P3D       # ISO-8601 duration
         confidence_gte: 0.7
     not:
       - event_type: regulatory_denial
         after_first_step: true
   ```
   Effort: medium (need a small evaluator); payoff: the insight reaction graph stops being five hardcoded `if` statements and becomes data.

2. **Promote the `acquisition_rumor_with_technical_reversal_context` logic in `viza/insights.py:336` to a declared pattern.** Today it's imperative:
   ```python
   if event.event_type == "acquisition_rumor":
       if isinstance(rsi, (int, float)) and rsi <= 35:
           candidates.insert(0, "acquisition_rumor_with_technical_reversal_context")
   ```
   This should be a pattern definition in the insight registry: "this insight type is satisfied by `acquisition_rumor` ∧ `rsi_14d ≤ 35` within the same `available_at` cutoff." Effort: small once the grammar from change #1 exists.

3. **Don't adopt a CEP engine yet.** Esper, Flink CEP, and Siddhi are streaming engines. VIZA is batch + cutoff-driven. The CEP model you want is *batch pattern matching over a bounded event store*, which a small Python evaluator handles in well under a second up to ~100k events. The engine question becomes real at ~1M events.

4. **Borrow Allen's interval algebra for the relationship graph.** When you do add an `EventPattern`, give it interval operators: `before`, `meets`, `overlaps`, `during`, `starts`, `finishes`, `equals`, plus their inverses. This is what lets "regulatory_action invalidates acquisition_rumor" be expressed as "regulatory_action `during` (acquisition_rumor.observed_at, acquisition_rumor.observed_at + horizon)."

---

## 7. Bitemporal data modeling (Snodgrass / SQL:2011)

### The concept

Bitemporal modeling tracks data along two orthogonal time axes ([Snodgrass 1999](https://www.cs.arizona.edu/~rts/publications.html), [SQL:2011](https://en.wikipedia.org/wiki/SQL:2011)):

- **Valid time** — when the fact is true in the real world. `valid_time_start`, `valid_time_end`. Closed-open intervals.
- **Transaction time** — when the system *knew* the fact. `transaction_time_start`, `transaction_time_end`. Append-only.

This combination makes three queries possible that single-time systems cannot answer correctly:

- *AS-OF valid time*: "what was true in the world on date D?"
- *AS-OF transaction time*: "what did the system *believe* on date D?" (audit, replay)
- *Bitemporal*: "what did the system believe on date D about what was true on date V?" (the right query for backtesting strategy decisions made on D)

A correction (the source provider revises yesterday's price) appends a new row with a new `transaction_time_start`; the previous row's `transaction_time_end` is set. Valid time intervals can overlap; transaction time intervals cannot.

### Where VIZA already complies

VIZA is *closer* to bitemporal than most prototypes, but not all the way:

- `viza/observations.py:31` — `VizaObservation.observed_at` (≈ valid time start), `available_at` (≈ when the data was queryable from the source — a hybrid of valid and transaction time), `retrieved_at` (≈ transaction time start). Three timestamps.
- `viza/events.py:40` — same triple on events.
- `viza/insights.py:57` — `observed_at`, `available_at`, `generated_at`. The `generated_at` is a derived-entity timestamp, not a transaction time.
- `viza/audit.py:198` — `point_in_time_evidence_checks` filters by `timestamp_available <= cutoff`. This is an AS-OF query on `available_at`.
- `viza/decisions.py:205` — `pit_observations = [obs for obs in observations if obs.available_at <= cutoff_timestamp]`. AS-OF cutoff filtering.

### Where VIZA diverges

- **No intervals, only moments.** Valid time is `observed_at` (a point), not `[valid_from, valid_to)`. This is fine for prices (a 4pm close has no end time semantically) but wrong for facts that have duration — "Apple's CEO was Tim Cook from 2011-08-24 to ∞", "AAPL is in sector Technology from 2007-09 to ∞."
- **No transaction-time end.** `retrieved_at` is a transaction-time *start*, but no row carries `transaction_time_end`. Corrections overwrite (`ON CONFLICT(observation_id) DO UPDATE` at `viza/observations.py:147`), so a corrected observation cannot be queried "as the system believed it last week."
- **No support for retroactive corrections.** When a data provider revises a historical earnings surprise, VIZA's current schema either overwrites (losing history) or inserts a new row with the same `observed_at` and a later `retrieved_at` (storing both but with no semantic distinction). Replay against the original belief is impossible.
- **Insight `available_at` is conflated.** An insight's `available_at` is "when the underlying evidence was available," not "when the insight itself was queryable." If a model improves and reissues a higher-confidence version of yesterday's insight, the schema has no way to express "this is a transaction-time-newer version of the same valid-time-bounded insight."

### What to change

This is the single change with the biggest medium-term payoff, because validation, backtesting, marketplace claims, and dispute resolution all depend on it.

1. **Promote every fact-bearing table to true bitemporal.** For `observations`, `events`, `insights`, `decisions`, and (later) the canonical asset master, add four explicit columns:
   ```python
   valid_time_start: datetime          # was observed_at
   valid_time_end: datetime | None     # NULL = "still true"
   transaction_time_start: datetime    # was retrieved_at
   transaction_time_end: datetime | None  # NULL = current belief
   ```
   `available_at` is **kept** as the "earliest moment the engine could have queried this," which is neither valid nor transaction time exactly — it's a *source-availability* timestamp specific to financial PIT discipline. (You're right to have it.) Effort: medium (schema migration + all writers); payoff: replay/audit/correction become trivially correct.

2. **Switch from `ON CONFLICT DO UPDATE` to append-only on observations and events.** Today `viza/observations.py:147` overwrites by `observation_id`. Change semantics: a "correction" closes the previous row's `transaction_time_end` and inserts a new row with a new `transaction_time_start`. The `observation_id` shifts from "primary key" to "logical observation key" — multiple rows can share it. Effort: medium; payoff: corrections become first-class.

3. **Build two AS-OF query helpers in `ObservationStore`:**
   ```python
   def get_as_of_transaction_time(self, ttx_cutoff: datetime) -> ...:
       """What the system believed at transaction time ttx_cutoff."""
       # WHERE transaction_time_start <= ttx_cutoff
       #   AND (transaction_time_end IS NULL OR transaction_time_end > ttx_cutoff)

   def get_as_of_valid_time(self, vt_cutoff: datetime) -> ...:
       """What was true in the world at valid time vt_cutoff,
          according to the system's CURRENT belief."""
       # WHERE valid_time_start <= vt_cutoff
       #   AND (valid_time_end IS NULL OR valid_time_end > vt_cutoff)
       #   AND transaction_time_end IS NULL
   ```
   These are the two queries `compile_decisions` actually needs. Today it conflates them.

4. **Make the SQLite schema target DuckDB-compatible for the bigger tables.** The PROJECT_SPEC §10.3 already recommends DuckDB for large PIT tables. DuckDB has better support for `INTERVAL` types, range joins, and the OLAP queries bitemporal modeling makes ergonomic.

5. **Don't try to make the SQL itself "temporal" via SQL:2011's `PERIOD FOR` syntax.** SQLite doesn't support it and DuckDB only partially does. Implement the bitemporal logic in Python query helpers. Reserve real `PERIOD FOR` for if/when you migrate to Postgres.

---

## 8. Belief revision and argumentation (AGM / Dung / defeasible logic)

### The concept

Three layered ideas:

- **AGM belief revision** (Alchourrón–Gärdenfors–Makinson, 1985). The classical theory of how a rational agent updates its belief set on new information, subject to postulates: success (new info accepted), inclusion (existing beliefs preserved when consistent), consistency (no contradictions), minimal change.

- **Defeasible logic.** Rules of the form "if A then B *unless* C." Conclusions are defeasible — they hold until a defeater is observed. Used heavily in legal and financial reasoning.

- **Abstract Argumentation Frameworks (Dung 1995, [paper](https://www.ijcai.org/Proceedings/15/Papers/387.pdf)).** A directed graph where nodes are arguments and edges are *attacks*. Extensions (admissible, complete, grounded, preferred, stable sets) define which arguments are jointly defensible. The mathematics composes cleanly with AGM (revising the AF on new arguments).

- **ASPIC+.** A practical instantiation: structured arguments built from strict + defeasible rules, with preferences over rules to resolve conflicts.

In a finance context, this matters because *insights contradict each other*. A bullish acquisition rumor and a bearish regulatory denial both target the same entity. The right framework is not "pick the highest-confidence" — it's "which set of insights is jointly defensible given the attack relations between them?"

### Where VIZA already complies

The seed is there, but it's hardcoded:

- `viza/relationships.py:247-253` — exactly five reaction rules, written as Python tuples:
  ```python
  ("acquisition_rumor", "unusual_volume", "confirms", "insight_confirms_insight"),
  ("insider_purchase", "momentum_breakout", "confirms", "insight_confirms_insight"),
  ("regulatory_action", "acquisition_rumor", "invalidates", "insight_invalidates_insight"),
  ("earnings_miss", "bullish_social_sentiment", "conflicts", "insight_conflicts_with_insight"),
  ("macro_liquidity_shock", "small_cap_breakout_signal", "conflicts", "insight_conflicts_with_insight"),
  ```
  This is, structurally, a tiny Dung AF: the third tuple is an *attack* edge, and the fourth/fifth are *rebut* edges.
- PROJECT_SPEC §17.3 names the right concepts: `confirms`, `invalidates`, `conflicts with`, `reinforces`.
- `viza/insights.py:78` — `VizaInsight.invalidation_conditions` is a list of strings. Each one is a *defeater* in defeasible-logic terms.

### Where VIZA diverges

- The reaction rules are not data. Adding a sixth requires a code change.
- No priority / preference relation. When `acquisition_rumor confirms unusual_volume` and `regulatory_action invalidates acquisition_rumor` both fire, the system does not compute the resulting argumentation extension — it emits both edges with no resolution.
- No temporal scoping. A regulatory denial from 2 years ago should not invalidate today's acquisition rumor, but the rule has no time bound.
- No grounding to evidence strength. ASPIC+ would let `source_credibility` and `confidence` enter as preferences over arguments; today they appear in the edge weight but do not affect which insights "win."

### What to change

1. **Lift the reaction rules to a config table.** Move `relationships.py:247` to `config/viza_reaction_rules.json` with schema:
   ```json
   {
     "trigger_insight_type": "regulatory_action",
     "target_insight_type": "acquisition_rumor",
     "relation": "attacks",
     "within_window": "P30D",
     "preference_basis": "source_credibility",
     "evidence_required": ["sec_filing_novelty"]
   }
   ```
   Effort: small; payoff: rules become reviewable and extendable without code changes. This is the *minimum* compliance move.

2. **Implement a small ASPIC+ evaluator over insight sets.** For each entity at each cutoff:
   - Build an argument graph: each insight is an argument, each reaction rule emits an attack edge.
   - Apply preference: stronger `confidence × source_credibility` defeats weaker.
   - Compute the grounded extension (the safest, skeptical answer): the maximal set of insights that defend each other against all attackers.
   - Tag each insight with its extension membership: `accepted`, `rejected`, `undecided`.

   This becomes a new field on the radar row: `argumentation_status`. Effort: medium (the algorithm is ~150 lines of Python); payoff: the relationship graph stops emitting confusing "this confirms that, but this other thing invalidates it" without resolution.

3. **Add a `defeaters` field to `InsightTypeDefinition`.** Today `invalidation_templates` is a list of strings (`viza/insights.py:37`). Make it a list of structured defeaters:
   ```python
   class Defeater(BaseModel):
       defeater_type: Literal["evidence_absent", "counter_event", "time_decay"]
       window: str | None  # ISO-8601 duration
       required_evidence_keys: list[str] = []
       countering_event_types: list[str] = []
   ```
   Then the executor can mechanically check "is this insight defeated *right now*?" rather than relying on the user to read the string template.

4. **Don't ship full AGM revision.** AGM postulates apply to logical theories, not to evidence-bearing time-stamped insights. The relevant theory is dynamic argumentation (revise the AF when new arguments arrive). The §8.1 ASPIC+ evaluator is sufficient — you do not need belief-set-level revision until you have a much larger reasoning surface.

---

## 9. Prioritized roadmap

Bundled by phase from the existing PROJECT_SPEC §24 plan, with the proposals in this report folded in.

### Phase 16 (universal `.viza` container) — adopt PROV at the manifest
- §3.2: PROV vocabulary in manifest (`prov:wasAttributedTo`, `prov:wasGeneratedBy`).
- §3.4: graph_hash / result_checksum / evidence_checksum become content-addressed `prov:Entity` IRIs.
- Cost: ~1 week. No engine change.

### Phase 18 (canonical asset master) — adopt FIBO
- §2.1: every asset/identifier field carries `fibo_iri`.
- §2.4: enforce FIBO instrument-vs-issuer split in observations.
- §1.1: SKOS for the `family` taxonomies across all registries.
- Cost: ~2–3 weeks. Mostly schema and seed work.

### Phase 19 (event/catalyst model) — adopt CEP grammar + Allen intervals
- §6.1: minimal pattern grammar for event patterns.
- §6.2: lift the `acquisition_rumor_with_technical_reversal_context` logic to data.
- §6.4: Allen interval operators on relationship edges.
- Cost: ~2 weeks. Pattern grammar evaluator is small.

### Phase 20 (insight object) — adopt argumentation
- §8.1: reaction rules become config.
- §8.2: ASPIC+ extension evaluator.
- §8.3: structured defeaters on insight types.
- Cost: ~2 weeks.

### Phase 21 (strategy profile & translation) — adopt DMN
- §4.1: FEEL (S-FEEL) in `DecisionTrigger`.
- §4.2: hit policy on every profile.
- §4.4: BusinessKnowledgeModel for indicators.
- §4.5: action_thresholds as a real decision table.
- Cost: ~3 weeks (FEEL-S parser is the bulk).

### Phase 23 (observation store) — adopt bitemporal
- §7.1: explicit `valid_time_*` and `transaction_time_*` columns.
- §7.2: append-only writes.
- §7.3: AS-OF query helpers.
- §7.4: DuckDB for the larger tables.
- Cost: ~3 weeks. Schema migration is the risk.

### Phase 25 (validation ledger / marketplace) — adopt full PROV graph
- §3.3: typed PROV edges replace evidence_refs strings.
- §3.1: `MethodologyRunResult` is a first-class `prov:Activity`.
- Cost: ~2 weeks once §3.2 is in.

### Deferred (do NOT do early)
- **Rete (§5)**: defer until rule count or data volume forces it. Indexes and memoization first.
- **Full Esper / Flink CEP (§6)**: defer until streaming becomes a real requirement. Batch evaluator first.
- **AGM belief revision (§8)**: defer indefinitely. ASPIC+ on the argument graph is sufficient.
- **OWL reasoners (§1)**: defer. Pydantic-as-source-of-truth, OWL-as-export is the right split.

---

## 10. Cross-cutting principles

A few principles fall out of all eight sections, and they're worth stating explicitly because they will keep recurring:

1. **Source of truth lives in code; standards are exports.** Pydantic models stay authoritative. FIBO, PROV, DMN, OWL are *projections* generated from the models. Do not invert this — authoring TTL or OWL by hand will outlive its usefulness in three releases.

2. **Every taxonomy field gets an IRI.** Strings like `acquisition_rumor` and `US_EQ` should be the *display* of a concept whose identity is a stable IRI. This single discipline is what makes FIBO alignment, SKOS taxonomies, and PROV provenance compose.

3. **Time is two-dimensional everywhere.** Valid time and transaction time are not optional. Backtesting, marketplace claims, audit, dispute resolution, and creator reputation all hit a wall the moment they are conflated.

4. **Rules are data; engines are configuration.** Today VIZA's reaction logic, indicator math, and translation thresholds live in Python. Each one of them is, structurally, a row in a table. Lifting them to data (decision tables, pattern grammars, reaction rule files) is the single highest-leverage refactor.

5. **Defer the engines, adopt the vocabularies.** Rete, Esper, Drools, FIBO reasoners, ASPIC+ implementations — none of these need to be in VIZA's first marketplace-ready release. Their vocabularies do. Adopting the *names* and *shapes* now keeps every later engine swap mechanical.

---

## 11. Sources

The standards summaries draw on:

- [Gruber, *A Translation Approach to Portable Ontology Specifications*](https://tomgruber.org/writing/ontolingua-kaj-1993.pdf)
- [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/)
- [W3C PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/)
- [EDM Council FIBO Specification](https://spec.edmcouncil.org/fibo/)
- [edmcouncil/fibo on GitHub](https://github.com/edmcouncil/fibo)
- [OMG DMN Specification](https://www.omg.org/spec/DMN/)
- [Drools DMN documentation](https://docs.drools.org/latest/drools-docs/drools/DMN/index.html)
- [Esper EPL Pattern Reference](https://esper.espertech.com/release-7.1.0/esper-reference/html/event_patterns.html)
- [Rete algorithm — Wikipedia](https://en.wikipedia.org/wiki/Rete_algorithm)
- [Bitemporal modeling — Martin Fowler](https://martinfowler.com/articles/bitemporal-history.html)
- [Temporal database — Wikipedia (Snodgrass / SQL:2011)](https://en.wikipedia.org/wiki/Temporal_database)
- [AGM Meets Abstract Argumentation (IJCAI 2015)](https://www.ijcai.org/Proceedings/15/Papers/387.pdf)
- [Defeasible Reasoning — Stanford Encyclopedia of Philosophy](https://plato.stanford.edu/entries/reasoning-defeasible/)

The VIZA-side claims are anchored to the current source tree at `C:/Users/gkwls/AAT/viza/` and to `docs/VIZA_PRODUCT_SPEC.md` v0.4 (2026-05-12).
