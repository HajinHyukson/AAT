# Equity Module v0.1 — Artifact Directory Plan and Generation Map

**Owner:** equity-platform engineering.
**Source of truth:** [docs/CLAUDE_EQUITY_MODULE.md](../../CLAUDE_EQUITY_MODULE.md) (the CLAUDE log).
**Protocol:** masterplan §§1–15 from `masterplan_sections3_to_last_updated.md`.
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening.
**Target module:** `viza.finance.equity_investment`.
**Hard dependencies:** `viza.core.strategy` (always), optional `viza.finance.securities`, optional `viza.aat.attribute_analysis`.

This file is the **plan**, not the artifacts. Each artifact lives at the path below; this document defines the schema each artifact must satisfy, the CLAUDE-log sections it draws from, the cross-artifact references it must resolve, the PIT/rights/validation gates it must inherit, and the acceptance test that proves the artifact loads and validates.

**Downgrade rule (from upgrade prompt):** the CLAUDE log declares Sections 1–41 at `implementation_ready` (status 7). Until each artifact below actually loads against the documented schema and passes its acceptance test, the artifact ships as **`registry-seedable` (status 6)**. Promotion to `implementation_ready` requires the acceptance test to pass against a loader in the running engine.

**Restrictive defaults (from upgrade prompt):**
- Unknown rights → `restricted_or_unclear` + `marketplace_policy=redacted` + `export_policy=blocked`.
- Unknown PIT → `pit_safe=false` + `lookahead_risk=high`.
- Unknown validation → `confidence_label=research_supported_experimental` at most.
- Practitioner-only evidence → `practitioner_observed` until triangulated.
- License unconfirmed → connector `production_required=true`, fail-closed (CLAUDE.md project rule).

---

## 1. Directory layout (created)

```text
docs/CLAUDE_EQUITY_MODULE.md                          (research log — already at this path)
docs/equity_module/v0.1/
  GENERATION_MAP.md                                   (this file)
  registries/
    equity_entity_types.json
    equity_node_types.json
    equity_edge_types.json
    equity_attribute_registry_seed.csv
    equity_event_registry_seed.json
    equity_insight_registry_seed.json
    equity_strategy_profiles.json
    equity_output_views.json
    equity_validation_rules.json
    equity_connector_requirements.json
    equity_source_rights_matrix.csv
    equity_PIT_matrix.csv
    viza.finance.equity_investment.manifest.json
  reports/
    equity_module_backlog.md
    equity_research_traceability_matrix.csv
    equity_rejection_and_downgrade_log.csv
  fixtures/                                           (populated by Phase 1 of §41 launch sequence)
  proofs/                                             (proof_<sha256>.json + validation_record_<run_id>.json)
```

---

## 2. Cross-cutting acceptance rules

Every artifact in this plan must satisfy the following before it leaves `registry-seedable`:

| Rule | Source | Enforced by |
|---|---|---|
| Every observation-bearing record carries the `viza.equity.pit_fields.v1` block. | CLAUDE §18.6 | §19 pit_validator |
| Every observation-bearing record carries the `viza.equity.rights_fields.v1` block. | CLAUDE §18.7 | §19 rights_validator |
| No ticker as primary key. | CLAUDE.md project rule; CLAUDE §20.4 | §19 data_validator |
| Immutable IDs required (`company_id`, `security_id`, `issuer_id`, etc.). | CLAUDE.md; CLAUDE §20.4 | §19 data_validator |
| Every attribution result carries `unexplained_residual`. | CLAUDE.md | AAT submodule + §19 statistical_validator |
| Factor attribution runs before event attribution. | CLAUDE.md | runtime DAG (Section 21 allowed-connection rules) |
| Production connector must fail closed without credentials. | CLAUDE.md; CLAUDE §18.10 | §19 rights_validator |
| Marketplace_draft packages default to redacted; no monetized endpoints. | CLAUDE §18.14; §27.2 | §19 marketplace_validator |
| Confidence labels conservative; downgrade where evidence is practitioner-only or replication is weak. | CLAUDE §34 | §19 validation_record_writer |

The Section 18 (data architecture) and Section 19 (validation framework) artifacts are **gates**: no data-dependent artifact below ships before §18 + §19 land.

---

## 3. Artifact generation map

The map orders artifacts by dependency, not alphabetically. Each row specifies what the artifact must satisfy. The `references` column lists the other artifact files this one must resolve into; cross-reference validation runs after all artifacts are emitted (§30 handoff gate).

### 3.1 `registries/equity_entity_types.json` — entity registry

| Field | Value |
|---|---|
| Source CLAUDE sections | §20 (primary); §3 (thesis/decision/recommendation as entities); §13 (event/filing); §14 (holder/insider); §11 (portfolio/position/benchmark); §8 (sector/industry); §9 (activist); §18 (connector/data_quality_warning/package); §19 (validation_record/audit_proof). |
| Schema | `viza.equity.entity_registry.v1` (CLAUDE §20.3 verbatim). |
| Required references | None (root registry). |
| PIT requirements | Each entity type record must declare its `default_pit_policy` (which observation timestamps apply when the entity is instantiated). For lifecycle entities (decision/thesis/validation_record) the default is `creation_time_only`; for evidence-bearing entities (filing/event/macro_observation) the default is `available_at_required=true`. |
| Rights requirements | Each entity type record must declare its `default_rights_policy` reference (which `source_type` is the typical bearer). Entities backed by EDGAR/regulator data default to `public_official`; entities backed by provider data default to `licensed_provider_required`; entities backed by social/alt data default to `restricted_or_unclear`. |
| Validation requirements | `no_ticker_as_primary_key`; `immutable_id_required_for_core_entities`; `share_class_distinct_from_security`; `adr_must_link_to_underlying_security`; `position_must_link_to_portfolio_and_security`; `thesis_must_link_to_entity_and_strategy_profile`; `event_must_link_to_at_least_one_entity`; `package_links_to_run_id`. |
| Acceptance test | Loads via `viza/registry/entity_loader.py` (to be written); every entity declares `extends`, `module_id`, `identifiers`, `immutable_keys`; ≥ 30 entity types; the 30 names in CLAUDE §20.3 are all present; loader emits no warnings of severity ≥ medium. |
| Initial status | `registry-seedable` until loader exists. |

### 3.2 `registries/equity_edge_types.json` — relationship edge registry

| Field | Value |
|---|---|
| Source CLAUDE sections | §20.5 (primary); §3 (relationship primitive); §8 (peer/competitor/supplier); §9 (insider/activist); §11 (position/portfolio/benchmark); §13 (filing references); §14 (ownership edges); §17 (regulator regulates issuer). |
| Schema | `viza.equity.edge_registry.v1` (derive from CLAUDE §20.5 edge list). Each edge: `edge_type`, `from_entity_type`, `to_entity_type`, `cardinality`, `directionality`, `optional_attributes` (e.g., `as_of`, `weight`, `similarity_score`, `evidence_refs`). |
| Required references | `equity_entity_types.json` — every `from_entity_type` and `to_entity_type` must resolve. |
| PIT requirements | Edges that change over time (ownership, classification, peer set, listing) must carry `as_of` timestamp and reference a vintaged record where applicable; static edges (share_class_of_company) carry `created_at`. |
| Rights requirements | Edges inherit rights from the data source that establishes the edge. `13F`-derived ownership edges = `public_official`; provider-derived peer_of edges = `licensed_provider_required` unless Hoberg-Phillips text-based public peers. |
| Validation requirements | `edge_endpoints_resolve_to_registered_entities`; `edge_cardinality_documented`; `dynamic_edges_carry_as_of`; `peer_drift_event_emitted_on_peer_change`. |
| Acceptance test | Loader resolves every `from_entity_type`/`to_entity_type` against `equity_entity_types.json`; ≥ 25 edge types covering the CLAUDE §20.5 list; no unresolved references. |
| Initial status | `registry-seedable`. |

### 3.3 `registries/equity_node_types.json` — node palette

| Field | Value |
|---|---|
| Source CLAUDE sections | §21 (primary, 216 nodes); §3.11 (decision-grammar nodes); §5.9 (analyst workflow); §§6.7, 7.8, 8.10, 9.10, 10.10, 11.7, 12.8, 13.9, 14.8, 15.10, 16.8, 17.8 (domain nodes); §19.8 (validation nodes). |
| Schema | `viza.equity.node_type.v1` (CLAUDE §21.2 verbatim). |
| Required references | `equity_entity_types.json` (input/output port types resolve to entity types or universal primitives); `equity_attribute_registry_seed.csv` (config-schema attribute keys); `equity_event_registry_seed.json` (nodes that consume events); `equity_validation_rules.json` (each node's `validation_rules` array). |
| PIT requirements | Each node declares the PIT class of its inputs: `pit_safe_required` (factor / valuation / event nodes that feed scoring), `latest_only_allowed` (display/UI/audit nodes), `mixed` (memo renderers). Nodes that can run in backtest mode must declare `pit_safe_required=true` and the runtime compiler must enforce. |
| Rights requirements | Each node declares its `rights_requirements` array, which can include `connector_entitlement_required` (license-gated) and `redact_when_marketplace_draft`. Licensed-data nodes default to `missing_node_policy=open_locked_preserve_config` so unentitled imports don't break the graph. |
| Validation requirements | `node_extends_core_primitive_in_palette`; `node_input_ports_typed`; `node_output_ports_typed`; `node_allowed_connections_listed`; `node_runtime_handler_path_resolves`; `node_evidence_requirements_listed`; `licensed_data_nodes_default_locked`. |
| Acceptance test | Loader resolves all 216 nodes; every node's `extends_core_primitive ∈ {universe, attribute, transform, filter, score, relationship, output_radar}`; every node's `compatible_strategy_families` resolves against the 25 families in §4.4; missing-node policy honored on a synthetic import test. |
| Initial status | `registry-seedable`. Promotion to `implementation_ready` requires runtime_handler stubs to exist for the v0.1 minimum set in §21.7. |

### 3.4 `registries/equity_attribute_registry_seed.csv` — attribute registry

| Field | Value |
|---|---|
| Source CLAUDE sections | §22 (primary); §3.12 (decision grammar attrs); §6.4 (fundamental attrs); §7.5 (valuation attrs); §8.6 (industry attrs); §9.6 (governance attrs); §10.11 (factor attrs); §11.8 (portfolio attrs); §12.4 (market structure attrs); §13.10 (event attrs); §14.4 (ownership attrs); §15.6 (sentiment attrs); §16.5 (macro / sensitivity attrs); §17 (short attrs via §6 + §9 + §14 cross-refs). |
| Schema | `viza.equity.attribute.v1` (CLAUDE §22.2). CSV columns: `attribute_key`, `display_name`, `family`, `unit`, `data_type`, `directionality`, `raw_or_derived`, `source_type`, `connector_role`, `frequency`, `timestamp_policy`, `sector_applicability`, `compatible_strategy_families`, `compatible_nodes`, `validation_rules`, `pit_policy`, `rights_policy`, `confidence_label`, `supporting_sources`, `tier`. |
| Required references | `equity_entity_types.json` (sector_applicability resolves to sector entities); `equity_connector_requirements.json` (connector_role resolves); `equity_source_rights_matrix.csv` (rights_policy resolves); `equity_PIT_matrix.csv` (pit_policy resolves); `equity_validation_rules.json` (validation_rules ids resolve). |
| PIT requirements | Every row declares `timestamp_policy ∈ {event_time, filing_accepted_at, publication_time, computation_time, vendor_release_time}` and `pit_policy` references one of the entries in `equity_PIT_matrix.csv`. The current AAT note (PROJECT_STATUS.md) says Kenneth French + FRED rows are timestamped at ingest, not as vintages — all factor + macro-derived attributes must mark `pit_safe=false` until the vintaged pipeline ships (CLAUDE §10.17, §16.10). |
| Rights requirements | Every row declares `rights_policy` referencing `equity_source_rights_matrix.csv`. Defaults follow CLAUDE §18.5 (filings = `public_official`; consensus + options + borrow + risk model = `licensed_provider_required`; social = `restricted_or_unclear`). |
| Validation requirements | `attribute_must_specify_timestamp_policy`; `sector_inapplicable_attribute_blocked_in_score_node`; `licensed_attribute_requires_connector_entitlement`; `profile_dependent_directionality_must_record_profile_id`; `unit_consistency_within_normalization`; `derived_attribute_records_inputs_and_method_version`. |
| Acceptance test | CSV parses; ≥ 600 rows (target, expandable); every row resolves into the source-rights matrix and PIT matrix; no row missing `timestamp_policy` or `rights_policy`; the v0.1 must-have attributes from §22.6 are present. |
| Initial status | `registry-seedable`. |

### 3.5 `registries/equity_event_registry_seed.json` — event registry

| Field | Value |
|---|---|
| Source CLAUDE sections | §23 (primary, ~120 event types); §13 (event family registry); §6.8 (filing events); §9.7 (governance/insider events); §14.5 (ownership/flow events); §15.7 (sentiment events); §16.6 (macro events); §17.9 (distress events); §3.13 (lifecycle events). |
| Schema | `viza.equity.event_type.v1` (CLAUDE §23.2). Required fields per event: `event_type`, `event_family`, `display_name`, `source_origin`, `default_source_credibility`, `materiality_default`, `observed_at_policy`, `available_at_policy`, `materiality_rules`, `compatible_strategy_families`, `required_evidence`, `monitoring_triggers`, `invalidation_templates`, `rights_requirements`, `confidence_label`. |
| Required references | `equity_entity_types.json` (event entity type); `equity_strategy_profiles.json` (compatible_strategy_families subset); `equity_source_rights_matrix.csv` (rights_requirements); `equity_PIT_matrix.csv` (observed/available timestamps); `equity_validation_rules.json` (per-event validation rule ids). |
| PIT requirements | Every event type declares: `observed_at_policy` (when the underlying occurrence happened) and `available_at_policy` (when VIZA could legitimately know it). For filings, `available_at = filing_accepted_at`. For provider news, `available_at = vendor_publication_at`. For rumors, `available_at = first_credible_publication_at` and the event must carry `unverified_flag`. |
| Rights requirements | EDGAR filings: `public_official`. Provider news (RavenPack/Reuters/Bloomberg): `licensed_provider_required`. FINRA short interest releases: `public_official`. FDA / DOJ / FTC: `public_official`. Provider event taxonomies (Bloomberg event types): `licensed_provider_required`. |
| Validation requirements | `event_type_must_be_in_registry`; `event_must_carry_credibility_score`; `event_must_carry_materiality_assessment`; `event_must_carry_pit_and_rights_fields`; `rumor_must_carry_unverified_flag`; `binary_event_must_emit_binary_flag`; `restatement_event_must_emit_downgrade_signal`. |
| Acceptance test | Loader resolves all ~120 events; every event carries `source_origin` + `available_at_policy`; every rumor event carries `unverified_flag=true`; every binary FDA / merger-arb event carries `binary_flag=true`; the 8-K item-coded list (Item 1.01–9.01) is present; the lifecycle events from §3.13 are present. |
| Initial status | `registry-seedable`. |

### 3.6 `registries/equity_insight_registry_seed.json` — insight registry

| Field | Value |
|---|---|
| Source CLAUDE sections | §24 (primary, ~150 insights); §3.14 (decision-state insights); §5.12 (memo insights); §6.9 (fundamental insights); §7.10 (valuation insights); §8.8 (industry insights); §9.8 (governance insights); §10.13 (factor insights); §11.10 (portfolio insights); §12.10 (technical insights); §13.11 (event insights); §14.6 (ownership insights); §15.8 (sentiment insights); §16 (regime/scenario insights); §17.10 (short insights). |
| Schema | `viza.equity.insight_type.v1` (CLAUDE §24.2). Required fields: `insight_type`, `insight_family`, `display_name`, `supported_strategy_families`, `evidence_requirements`, `direction_logic`, `translation_rules`, `invalidation_templates`, `confirmation_templates`, `validation_rules`, `pit_requirements`, `rights_requirements`, `human_review_required`, `non_advice_boundary_required`, `confidence_label`. |
| Required references | `equity_attribute_registry_seed.csv` (evidence_requirements reference attribute keys); `equity_event_registry_seed.json` (event-based insights); `equity_strategy_profiles.json` (supported_strategy_families + translation_rules.per_profile_translation); `equity_validation_rules.json` (validation_rules ids); `equity_source_rights_matrix.csv` (rights_requirements). |
| PIT requirements | Inherits PIT from underlying attributes/events. An insight cannot mark `pit_safe=true` unless every input is PIT-safe at the decision timestamp. CLAUDE §3.18 rule applies. |
| Rights requirements | Inherits rights cumulatively from inputs (CLAUDE §4.5 rule 6). If any input is restricted, insight defaults to redacted in marketplace_draft. |
| Validation requirements | `insight_must_link_to_evidence_refs`; `insight_must_carry_strategy_profile_id_when_emitted`; `profile_dependent_insights_must_list_per_profile_translation`; `risk_only_insights_cannot_emit_buy_action`; `short_thesis_insights_require_legal_review_if_classified`; `manipulation_state_insight_requires_human_review`. |
| Acceptance test | Loader resolves all ~150 insights; every insight references ≥ 1 attribute or event; per-profile translations resolve against `equity_strategy_profiles.json`; `risk_only` and `short` insight flags are present where applicable. |
| Initial status | `registry-seedable`. |

### 3.7 `registries/equity_strategy_profiles.json` — strategy profile templates

| Field | Value |
|---|---|
| Source CLAUDE sections | §25 (primary, 17 v0.1 profiles); §4.4 (25-family taxonomy); §3.9 (strategy-profile dependency table — fixture source); §3.15 (strategy-profile interpreter). |
| Schema | `viza.equity.strategy_profile.v1` (CLAUDE §25.2). |
| Required references | `equity_entity_types.json` (mandate, universe, benchmark resolve); `equity_attribute_registry_seed.csv` (preferred_signals and score_methodology weights reference attribute keys); `equity_event_registry_seed.json` (catalyst types in `required_confirmations`); `equity_insight_registry_seed.json` (insight_translation_overrides); `equity_validation_rules.json` (per-profile `validation.*` ids); `equity_output_views.json` (output_views array). |
| PIT requirements | Each profile declares `evidence_standards.requires_pit_safe` (boolean) and a `pit_policy_ref` to a PIT matrix row. Backtest-bearing profiles MUST set `requires_pit_safe=true`. Profiles depending on factor or macro inputs whose vintaged pipeline hasn't shipped must downgrade `confidence_label` and emit a `pit_warning` insight at runtime. |
| Rights requirements | Each profile declares `rights_policy_ref` referencing the source-rights matrix. Profiles using licensed-data nodes must declare `connector_entitlement_required=true` and the runtime must fail-closed if licenses are missing. Profiles intended for marketplace_draft must declare `marketplace_redaction_default=true`. |
| Validation requirements | `profile_must_have_strategy_family`; `profile_actions_must_match_mandate`; `profile_score_method_must_record_caps`; `profile_must_link_required_risk_gates`; `profile_must_link_invalidation_policy`; `profile_must_carry_evidence_standards`; `backtest_uses_only_attributes_with_pit_safe=true_when_profile_requires_pit_safe`. |
| Acceptance test | Loader instantiates all 17 v0.1 profiles; the Section 3 §3.9 strategy-profile dependency table is executable as a fixture (`fixtures/strategy_profile_dependency_table.jsonl`) and every profile produces the expected primary/confirmation/risk/catalyst/irrelevant/blocker/monitor tag for the 12 test facts; conflicting signals surface explicitly when composite profiles are loaded. |
| Initial status | `registry-seedable` until §3.9 fixture passes. |

### 3.8 `registries/equity_output_views.json` — output views

| Field | Value |
|---|---|
| Source CLAUDE sections | §26 (primary, 10 views); §3.21 (output-view field requirements); §5 (memo / scorecard / thesis tracker); §11.10 (risk dashboard); §19.6 (validation_report). |
| Schema | `viza.equity.output_view.v1` (CLAUDE §26.2). |
| Required references | `equity_strategy_profiles.json` (`binding.strategy_profile_required`); `equity_validation_rules.json` (`audit_render.validation_record_refs`); `equity_source_rights_matrix.csv` (`data_rights`); `equity_attribute_registry_seed.csv` (fields referenced in `required_sections`). |
| PIT requirements | Every view's `required_sections` includes `pit_summary`; renderer must populate it with the `pit_safe` flag plus the most-recent `available_at` across all evidence used. |
| Rights requirements | Every view's `required_sections` includes `rights_summary`; renderer must populate it with per-section redaction state. Marketplace_draft outputs must redact restricted evidence by default (CLAUDE §26.5). |
| Validation requirements | `output_view_must_match_schema`; `output_lacking_strategy_profile_blocked`; `output_lacking_pit_or_rights_summary_blocked`; `output_with_unredacted_restricted_evidence_blocked`; `output_with_recommendation_without_invalidation_warn_or_block_by_profile`; `target_price_output_requires_valuation_methodology_link`; `non_advice_boundary_text_required_on_recommendation_outputs`. |
| Acceptance test | Loader resolves all 10 views; renderer dry-run on a sample strategy run produces a memo/radar/risk_dashboard/validation_report with all required sections present and PIT/rights/validation summaries populated. |
| Initial status | `registry-seedable`. |

### 3.9 `registries/equity_validation_rules.json` — validation rules

| Field | Value |
|---|---|
| Source CLAUDE sections | §19 (primary, validation framework); §3.16 (decision grammar validation); §5.14 (analyst workflow validation); §§6.12, 7.13, 8.13, 9.13, 10.6, 11.14, 12.13, 13.14, 14.11, 15.13, 16.12, 17.13 (per-domain validation); §18.15 (architecture-level validation); §22.8 (attribute validation); §25.9 (profile validation); §26.6 (output validation). |
| Schema | `viza.equity.validation_record.v1` (CLAUDE §19.2). Each validation rule entry: `rule_id`, `domain` (graph/data/PIT/rights/evidence/statistical/portfolio/output/marketplace), `description`, `severity` (info/warn/error/block), `applies_to` (entity types / node types / artifact types), `trigger_logic`, `remediation`, `human_review_required`, `source_refs`. |
| Required references | All other registries — rules cite the entity / node / attribute / event / insight / profile / output they apply to. |
| PIT requirements | Rules in the PIT domain implement CLAUDE §3.18 (decision PIT) and §18.6 (PIT fields). Backtest-relevant rules must declare `applies_to_backtest=true`. |
| Rights requirements | Rules in the rights domain implement CLAUDE §3.19 and §18.7. Marketplace rules implement §18.14 / §26.5. |
| Validation requirements | (Self-validating) — every rule must declare `domain`, `severity`, `applies_to`, and a non-empty `trigger_logic`. Rules that block actions must declare a clear `remediation`. |
| Acceptance test | Loader resolves every rule's `applies_to`; the CLAUDE rule list (≈ 80 rules across all sections) is fully represented; every output type from `equity_output_views.json` has at least one rule with severity ≥ warn; human-review triggers from §19.9 are represented. |
| Initial status | `registry-seedable`. Promotion requires the validator runtime to actually execute these rules against a sample graph. |

### 3.10 `registries/equity_connector_requirements.json` — connector configuration registry

| Field | Value |
|---|---|
| Source CLAUDE sections | §18.4 (connector role taxonomy, 35 roles); §18.10 (connector_config schema); §18.5 (rights matrix per role); PROJECT_STATUS.md (FMP / FaustCalc / FRED / Kenneth French current state); §10.17 (factor pipeline note); §16.10 (ALFRED requirement). |
| Schema | `viza.equity.connector_config.v1` (CLAUDE §18.10). |
| Required references | `equity_source_rights_matrix.csv` (`rights_policy_ref`); `equity_PIT_matrix.csv` (`pit_policy_ref`). |
| PIT requirements | Each connector declares its PIT class: `vintaged`, `latest_only`, `latest_revisable`, `event_pit`. ALFRED → `vintaged`. FRED → `latest_revisable` (current AAT ingestion is `latest_only`; mark as warning). I/B/E/S → `vintaged_provider_required`. EDGAR → `event_pit`. |
| Rights requirements | Each connector declares its source rights classification. Connectors providing `licensed_provider_required` data must default to `production_required=true` and `fail_closed_without_credentials=true` (CLAUDE.md project rule). |
| Validation requirements | `connector_must_declare_role`; `connector_must_declare_pit_class`; `connector_must_declare_rights_classification`; `licensed_connector_fails_closed_without_credentials`; `marketplace_draft_must_respect_redistribution_policy`. |
| Acceptance test | Loader resolves all ~35 connector roles; each role has at least one entry; fail-closed behavior is testable via a synthetic missing-credential probe; AAT note (FMP dev-only, FaustCalc dev-only) is reflected. |
| Initial status | `registry-seedable`. |

### 3.11 `registries/equity_source_rights_matrix.csv` — source rights matrix

| Field | Value |
|---|---|
| Source CLAUDE sections | §18.5 (primary, matrix); §15.5 (source credibility for social/news); §17.7 (legal language guardrails); §27.2 (manifest marketplace policy). |
| Schema | CSV columns: `connector_role`, `source_id_pattern` (e.g., regex over source_id), `source_type`, `license_policy`, `query_policy`, `cache_policy`, `display_policy`, `export_policy`, `derived_value_policy`, `redistribution_policy`, `marketplace_policy`, `attribution_required`, `retention_policy`, `redaction_required`, `notes`. |
| Required references | `equity_connector_requirements.json` (`connector_role`). |
| PIT requirements | N/A (this is the rights matrix, not the PIT matrix). |
| Rights requirements | This **is** the rights matrix. Default unknown → `restricted_or_unclear` + `marketplace_policy=redacted` + `export_policy=blocked`. |
| Validation requirements | `every_connector_role_in_connector_requirements_has_at_least_one_row`; `default_unknown_rights_redacted`; `licensed_provider_required_blocks_redistribution`; `restricted_or_unclear_blocks_export_and_marketplace`. |
| Acceptance test | CSV parses; ≥ 35 rows; every connector_role in the connector requirements registry has at least one matching row; restrictive defaults applied; the §18.5 matrix is reproduced. |
| Initial status | `registry-seedable`. |

### 3.12 `registries/equity_PIT_matrix.csv` — point-in-time matrix

| Field | Value |
|---|---|
| Source CLAUDE sections | §18.6 (PIT fields); §18.8 (vintage / restatement / amendment chain rules); §6.10 (fundamentals PIT); §10.8 (factor PIT); §13.12 (event PIT); §14.9 (ownership PIT, including 13F 45-day lag); §16.10 (macro PIT / ALFRED). |
| Schema | CSV columns: `pit_policy_id`, `connector_role`, `data_category`, `observed_at_definition`, `available_at_definition`, `revision_class` (`vintaged`, `latest_only`, `latest_revisable`, `event_pit`, `unknown`), `vintage_required_for_backtest`, `revised_after_publication`, `pit_safe_default`, `lookahead_risk_default`, `current_aat_status`, `notes`. |
| Required references | `equity_connector_requirements.json` (`connector_role`). |
| PIT requirements | This **is** the PIT matrix. Default unknown → `pit_safe_default=false`, `lookahead_risk_default=high`. |
| Rights requirements | N/A (rights matrix is separate). |
| Validation requirements | `every_data_category_has_pit_policy`; `vintage_required_categories_marked`; `current_aat_status_reflects_PROJECT_STATUS.md` (Kenneth French + FRED currently ingestion-timestamped); `13f_data_category_marks_45_day_lag`; `short_interest_marks_release_date`. |
| Acceptance test | CSV parses; rows cover every connector_role from `equity_connector_requirements.json`; the seven categories from §18.8 (fundamentals, consensus, macro, short_interest, ownership_filings, news, factor_data) are represented with their specific revision rules. |
| Initial status | `registry-seedable`. |

### 3.13 `registries/viza.finance.equity_investment.manifest.json` — module manifest

| Field | Value |
|---|---|
| Source CLAUDE sections | §27 (primary, manifest schema); §1.7 (submodule decomposition); §28 (backlog phases for capability matrix); §40 (success criteria for `release_state` selection). |
| Schema | `viza.module.manifest.v1` (CLAUDE §27.2). |
| Required references | All twelve registry files in `registries/` (entity types, node types, edge types, attribute seed, event seed, insight seed, strategy profiles, output views, validation rules, connector requirements, source rights matrix, PIT matrix). |
| PIT requirements | `pit_policy` block declares: `default_pit_safe=false`, `require_pit_or_warn_label=true`, `vintage_required_for_macro=true`, `vintage_required_for_factor=true_when_section_18_vintaged_pipeline_shipped` (literal string; pipeline currently not shipped per PROJECT_STATUS.md). |
| Rights requirements | `rights_policy` block declares `default_source_classification=public_official`, `fail_closed_on_missing_license=true`. `marketplace.monetized_marketplace_supported=false`. |
| Validation requirements | `module_must_declare_dependencies`; `module_must_list_registries`; `module_must_state_marketplace_policy`; `module_must_state_rights_policy`; `module_must_state_pit_policy`; `module_must_state_validation_policy`; `fail_closed_must_be_true_for_licensed_connectors`. |
| Acceptance test | Loader resolves every registry file referenced; submodule dependency graph resolves (`viza.core.strategy` required, others as declared); `release_state=alpha` (downgrade from `ga` until acceptance tests pass); `requires_engine_version>=2026.05.13`. |
| Initial status | `registry-seedable`; release state ships as `alpha` until §41 launch sequence Step 5 (verification) passes. |

### 3.14 `reports/equity_module_backlog.md` — engineering backlog

| Field | Value |
|---|---|
| Source CLAUDE sections | §28 (primary, consolidated backlog with phases P0–P3); every per-section backlog (§§3.20, 5.13, 6.14, 7.15, 8.15, 9.15, 10.15, 11.16, 12.15, 13.16, 14.13, 15.15, 16.14, 17.15, 18.17, 19.12, 20.10, 21 nodes, 22.10, 23.9, 24.8, 25.10, 26.7, 27.6); §37 (execution order); §38 (effort estimates); §41 (launch sequence). |
| Schema | Markdown with sections per phase (Phase 0, Phase 1, Phase 2, Phase 3). Each entry: `Backlog ID`, `Title`, `Priority` (P0/P1/P2/P3), `Phase`, `Source CLAUDE Section`, `Dependencies`, `Acceptance Tests`, `Notes`. |
| Required references | All registries (backlog items reference the registries they modify); `equity_research_traceability_matrix.csv` (every backlog item resolves to a CLAUDE-log section). |
| PIT requirements | N/A (planning artifact). PIT-related backlog items (`EQ-DA-005` vintaged macro, `EQ-DA-011` vintaged factor pipeline) carry `pit_blocker=true`. |
| Rights requirements | N/A. License-dependent items (`EQ-ATTR-004`, `EQ-TE-005`, `EQ-OW-007`) carry `license_required=true`. |
| Validation requirements | Each entry declares `acceptance_tests` (list). |
| Acceptance test | Markdown renders; every backlog ID is unique; Phase 0 items precede Phase 1 items, etc.; the ~150 items from CLAUDE §28 are present; PIT-blocker and license-required items are flagged. |
| Initial status | `registry-seedable` once the markdown is written; promotes to `implementation_ready` when items are tracked in the engineering tracker. |

### 3.15 `reports/equity_research_traceability_matrix.csv` — research → registry traceability

| Field | Value |
|---|---|
| Source CLAUDE sections | All 41 sections (this is the cross-cutting trace artifact). |
| Schema | CSV columns: `trace_id`, `claude_section`, `claude_subsection`, `source_id` (e.g., `F-001`, `FA-040`), `extracted_method_id` (if any), `viza_primitive` (entity/attribute/event/insight/profile/output/validation), `registry_artifact_file`, `registry_entry_key`, `confidence_label`, `tier`, `notes`. |
| Required references | `equity_entity_types.json`, `equity_node_types.json`, `equity_attribute_registry_seed.csv`, `equity_event_registry_seed.json`, `equity_insight_registry_seed.json`, `equity_strategy_profiles.json`, `equity_validation_rules.json`. Cross-reference must resolve in both directions: every CLAUDE source_id surfaces ≥ 1 trace row when it influenced an artifact; every registry key surfaces ≥ 1 trace row showing what evidence produced it. |
| PIT requirements | N/A (planning artifact). |
| Rights requirements | N/A. |
| Validation requirements | `every_registry_entry_has_at_least_one_trace_row`; `every_source_id_cited_in_claude_log_appears_in_trace`. |
| Acceptance test | CSV parses; ≥ 1000 rows (rough estimate given 510+ unique source IDs × multiple registry primitives); reverse lookup from a registry key to source_id succeeds for every row in the v0.1 minimum viable set (CLAUDE §21.7). |
| Initial status | `registry-seedable`. |

### 3.16 `reports/equity_rejection_and_downgrade_log.csv` — rejection / downgrade log

| Field | Value |
|---|---|
| Source CLAUDE sections | §34 (primary, rejection + downgrade criteria); §2.9 (rejection criteria); §2.10 (downgrade criteria); §22.5 (production-readiness tiers); §10.4 (factor tier deferrals); per-section open questions where labels were downgraded. |
| Schema | CSV columns: `entry_id`, `target_object_type` (method/attribute/event/insight/profile/factor/node), `target_object_key`, `original_label`, `final_label`, `decision` (`rejected` or `downgraded`), `reason_codes` (list from §34.2 / §34.3), `evidence_refs`, `claude_section_ref`, `date`, `reviewer`, `revisit_after` (e.g., "vintaged factor pipeline ships"). |
| Required references | `equity_attribute_registry_seed.csv`, `equity_event_registry_seed.json`, `equity_insight_registry_seed.json`, `equity_strategy_profiles.json` — every `target_object_key` must resolve in its target artifact. |
| PIT requirements | N/A. |
| Rights requirements | N/A. |
| Validation requirements | `every_rejection_has_reason_codes`; `every_downgrade_records_original_and_final_labels`; `revisit_after_present_when_decision_is_temporary`. |
| Acceptance test | CSV parses; covers every factor tagged `deferred_or_rejected` in §10.4 (options-OS, decayed anomalies); every `practitioner_observed` label in the registries that was previously a higher tier in the source CLAUDE log; every rights-blocked node from the licensed-data list. |
| Initial status | `registry-seedable`. |

---

## 4. Implementation order (binds §41 launch sequence)

```text
Phase 0  (foundation)        — §41 Step 1–3
  W0   Generate equity_PIT_matrix.csv               (§3.12)
  W0   Generate equity_source_rights_matrix.csv     (§3.11)
  W0   Generate equity_connector_requirements.json  (§3.10)
  W0   Generate equity_entity_types.json            (§3.1)
  W0   Generate equity_edge_types.json              (§3.2)
  W0   Generate equity_validation_rules.json        (§3.9)
  W0   Write loaders in viza/registry/ for the six artifacts above
  W0   Run cross-reference validator → produce proof_<sha256>.json in proofs/

Phase 1  (analytic core)     — §41 Step 4
  W1   Generate equity_attribute_registry_seed.csv  (§3.4)
  W1   Generate equity_event_registry_seed.json     (§3.5)
  W1   Generate equity_node_types.json              (§3.3)
  W1   Generate equity_insight_registry_seed.json   (§3.6)
  W1   Generate equity_strategy_profiles.json       (§3.7)
  W1   Generate equity_output_views.json            (§3.8)
  W1   Generate fixtures/strategy_profile_dependency_table.jsonl from CLAUDE §3.9
  W1   Write registry loaders + cross-reference validator
  W1   Run loaders; record validation_record_<run_id>.json in proofs/

Phase 2  (manifest + reports)
  W2   Generate viza.finance.equity_investment.manifest.json  (§3.13)
  W2   Generate reports/equity_module_backlog.md             (§3.14)
  W2   Generate reports/equity_research_traceability_matrix.csv (§3.15)
  W2   Generate reports/equity_rejection_and_downgrade_log.csv  (§3.16)
  W2   Run §41 Step 5 verification: full Python unit + look-ahead tests + desktop helper tests

Phase 3  (pilot)             — §41 Step 4 pilot
  W3   Pilot 3 v0.1 profiles end-to-end with public data only:
       1. quality_value_long_only
       2. portfolio_risk_radar
       3. earnings_revision_momentum (locked / fallback to EDGAR earnings surprise)
  W3   Generate fixtures/pilot_run_<profile_id>.json
  W3   Confirm marketplace_draft + redaction behavior
  W3   Update CHANGELOG.md, ARCHITECTURE.md, PROJECT_STATUS.md
```

---

## 5. Acceptance criteria (matches the user's requirements)

| Criterion | Result |
|---|---|
| Every artifact maps back to at least one CLAUDE section. | PASS — every artifact in §3 lists its source CLAUDE sections. |
| Sections 18 and 19 gate every data-dependent artifact. | PASS — every data-dependent artifact references `equity_source_rights_matrix.csv` (§18), `equity_PIT_matrix.csv` (§18), `equity_connector_requirements.json` (§18), and `equity_validation_rules.json` (§19). The cross-cutting acceptance rules in §2 are §18/§19 derived. |
| Sections 20–26 produce the main registry artifacts. | PASS — entity types (§20), node palette (§21), attribute registry (§22), event registry (§23), insight registry (§24), strategy profiles (§25), output views (§26). |
| Section 27 produces the manifest. | PASS — `viza.finance.equity_investment.manifest.json` cited to §27. |
| Section 28 produces the backlog. | PASS — `reports/equity_module_backlog.md` cited to §28. |
| Section 41 launch sequence is reflected in the implementation order. | PASS — §4 of this plan binds §41 steps 1–5 directly to phase-by-phase artifact emission. |
| Restrictive rights defaults applied where ambiguous. | PASS — `restricted_or_unclear → marketplace_policy=redacted, export_policy=blocked` is the default for every artifact in §3. |
| Conservative confidence labels where validation incomplete. | PASS — every artifact ships at `registry-seedable` (status 6), not at `implementation_ready` (status 7), until its acceptance test passes against a loader. |
| Output is implementation-ready files or precise patch instructions, not broad narrative. | PASS — this document is a generation map; the next pass emits the artifacts named in §3 to the paths in §1. |

---

## 6. Downgrades applied vs the CLAUDE log

| CLAUDE log claim | Downgrade applied here | Reason |
|---|---|---|
| All 41 sections at `implementation_ready` (status 7). | Each artifact ships at `registry-seedable` (status 6) until a loader exists and acceptance test passes. | Upgrade prompt rule: "When the log overclaims implementation readiness, downgrade to 'registry-seedable' unless the artifact actually loads and validates." |
| Module manifest `release_state=alpha` (default). | Manifest must ship `release_state=alpha` until §41 Step 5 verification passes. | No live verification yet. |
| Factor / macro `pit_safe=true` after vintaged pipeline ships. | Until §18 vintaged pipeline ships, factor + macro attributes mark `pit_safe=false` and emit `pit_warning` insights. | PROJECT_STATUS.md: Kenneth French + FRED currently ingestion-timestamped, not vintaged. |
| Marketplace_draft outputs default to creator-upgradable. | Marketplace_draft outputs default to redacted; upgrade requires documented license + compliance acknowledgement. | Upgrade prompt rule + CLAUDE §18.14. |
| Sentiment / narrative nodes shippable when sources triangulated. | Sentiment / narrative nodes default-locked in v0.1 (`open_locked_preserve_config`); require model-governance ledger + license confirmation before activation. | CLAUDE §15.16 (research_supported_experimental at best). |
| Short / negative thesis nodes shippable. | Short / negative nodes require legal review gate and language guardrails; default-restricted for marketplace_draft. | CLAUDE §17.7 + §17.13. |
| Practitioner-only evidence promoted to core. | Practitioner-only evidence stays `practitioner_observed`; promotion requires triangulation with score-5 source. | CLAUDE §14.3 + §2.10. |
| Public 13F data treated as current positioning. | 13F data marked with 45-day lag; never used as current positioning (validation rule `13f_data_must_not_be_used_as_current_positioning`). | CLAUDE §14.11. |

---

## 7. Pending decisions deferred to next pass

These open questions from the CLAUDE log remain unresolved and must be answered before the artifacts in §3 promote past `registry-seedable`:

1. `viza.aat.attribute_analysis` placement (sibling vs sub-module). The manifest currently lists AAT as a sub-module per §1.7; if engineering prefers sibling, the manifest must be regenerated.
2. `viza.finance.securities` as hard vs optional dependency. Currently optional per §27.2; revisit when v0.1 ships.
3. `thesis` as entity vs insight subtype. The current entity registry lists `thesis` as a first-class entity (§3.22 resolution); confirm before manifest sign-off.
4. Action vocabulary default (`research_action` vs `buy/sell`). Profiles currently default to `research_action` (§25.12).
5. Target price required in v0.1 outputs. Currently `profile-opt-in only` (§7.18); confirm.
6. Default Kelly cap at 25%. Confirm in §11.19; manifest currently inherits.
7. Hidden vs visible validation nodes. Currently visible-but-auto-suggested (§21.10).
8. Default GICS as primary classification key. Currently chosen `gics_subindustry` (§8.18); confirm license.

---

## 8. Cross-reference contract

After all artifacts in §3 are emitted, the cross-reference validator must produce zero unresolved keys. The contract:

```text
equity_entity_types.json                  -> referenced by all other registries
equity_edge_types.json                    -> resolves entity_types
equity_attribute_registry_seed.csv        -> resolves entity_types + connector_requirements + source_rights_matrix + PIT_matrix + validation_rules
equity_event_registry_seed.json           -> resolves entity_types + source_rights_matrix + PIT_matrix + validation_rules + strategy_profiles
equity_insight_registry_seed.json         -> resolves attribute_registry + event_registry + strategy_profiles + validation_rules + source_rights_matrix
equity_strategy_profiles.json             -> resolves attribute_registry + event_registry + insight_registry + validation_rules + output_views
equity_output_views.json                  -> resolves strategy_profiles + validation_rules + source_rights_matrix + attribute_registry
equity_validation_rules.json              -> resolves all other registries (rules apply to specific objects)
equity_connector_requirements.json        -> resolves source_rights_matrix + PIT_matrix
equity_source_rights_matrix.csv           -> resolves connector_requirements
equity_PIT_matrix.csv                     -> resolves connector_requirements
viza.finance.equity_investment.manifest.json -> resolves all twelve registries above
equity_module_backlog.md                  -> resolves CLAUDE sections + all registries
equity_research_traceability_matrix.csv   -> resolves CLAUDE source_ids + all registries
equity_rejection_and_downgrade_log.csv    -> resolves all registries
```

Cross-reference validation failure on any one of these blocks the manifest from advancing past `release_state=alpha`.

---

## 9. Proof contract (per §30.3 and §36.2)

After all artifacts emit and the cross-reference validator passes:

```text
proofs/proof_<sha256_of_concatenated_artifacts>.json
proofs/validation_record_<run_id>.json
```

The proof file records:

```json
{
  "schema":"viza.equity.proof.v1",
  "run_id":"",
  "captured_at":"",
  "baseline":"Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening",
  "module_id":"viza.finance.equity_investment",
  "module_version":"0.1.0",
  "release_state":"alpha",
  "artifact_files":[{"path":"","sha256":"","schema":""}],
  "registry_keys_total":0,
  "registry_keys_resolved":0,
  "cross_reference_failures":0,
  "validation_record_ref":"",
  "downgrade_log_ref":"",
  "traceability_matrix_ref":"",
  "manifest_ref":""
}
```

A non-zero `cross_reference_failures` blocks promotion. A failed validation_record blocks promotion.

---

**End of GENERATION_MAP.md** — this is the plan only. The artifacts named in §3 are emitted by the next pass.
