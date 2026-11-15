# Shared Metadata Contract — `viza.finance.equity_investment v0.1` Registry Objects

**Path:** `docs/equity_module/v0.1/shared_metadata_contract.md`
**Companion schema:** [`equity_registry_shared_metadata.schema.json`](equity_registry_shared_metadata.schema.json)
**Source of truth:** [docs/CLAUDE_EQUITY_MODULE.md](../../CLAUDE_EQUITY_MODULE.md) (the CLAUDE log).
**Protocol:** masterplan §§1–15.
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening.
**Status of this contract:** `registry-seedable` (status 6). Promotes to `implementation_ready` (status 7) when a loader validates every artifact in `registries/` against the companion JSON Schema with zero violations.

This contract is binding. Every registry record across the 12 object families below must carry the fields specified here. The companion JSON Schema is the machine-enforceable form. When the prose contract and the JSON Schema disagree, the JSON Schema wins because it is the loader's input; report the disagreement and patch both.

The 12 object families bound by this contract:

```text
entity_type          (registries/equity_entity_types.json)
node_type            (registries/equity_node_types.json)
edge_type            (registries/equity_edge_types.json)
attribute            (registries/equity_attribute_registry_seed.csv)
event_type           (registries/equity_event_registry_seed.json)
insight_type         (registries/equity_insight_registry_seed.json)
strategy_profile     (registries/equity_strategy_profiles.json)
output_view          (registries/equity_output_views.json)
validation_rule      (registries/equity_validation_rules.json)
connector_requirement(registries/equity_connector_requirements.json)
rights_policy        (registries/equity_source_rights_matrix.csv)   — rows are rights policy records
pit_policy           (registries/equity_PIT_matrix.csv)              — rows are PIT policy records
```

Every record is a `RegistryObject`. The base contract requires the fields listed in §§2–7 below. Object-family-specific extensions (§9) add or constrain fields but never remove a base requirement.

---

## 1. Top-level conformance rules

| Rule | Reason | Enforcement |
|---|---|---|
| `additionalProperties: false` on the base contract. | Catch typos, drift, and silent field additions. | JSON Schema. |
| Restrictive defaults: any **rights** field with value `"unknown"` forces `export_policy ∈ {blocked, conditional}`, `marketplace_policy ∈ {redacted, blocked}`, `redistribution_policy ∈ {blocked, conditional}`, `redaction_required=true`. | CLAUDE §18.13–§18.14 + upgrade-prompt restrictive-defaults rule. | JSON Schema conditional + loader assertion. |
| Restrictive defaults: any **PIT** field with value `"unknown"` forces `vintage_required=true`, `lookahead_risk="high"`. | CLAUDE §18.6 + upgrade-prompt restrictive-defaults rule. | JSON Schema conditional. |
| Confidence-label promotion gate: `confidence_label ∈ {high_confidence_core, common_practice}` requires `source_ids.length >= 1` and `evidence_requirements.length >= 1`. | CLAUDE §2.5 + §34. | JSON Schema conditional. |
| Confidence-label promotion gate: `confidence_label = high_confidence_core` requires that at least one referenced source carries `source_quality_score >= 4` (verified by loader against the global source corpus). | CLAUDE §2.5 + §34.4. | Loader assertion; schema records the requirement in `source_quality_minimum`. |
| Source-lineage gate: missing `source_sections` or `source_ids` blocks `status` from promoting above `research_supported_experimental`. | Upgrade-prompt acceptance criterion 4. | JSON Schema conditional + loader assertion. |
| Every record carries `module_id="viza.finance.equity_investment"` unless the record explicitly belongs to `viza.core.strategy` (universal primitive extension). | CLAUDE §1.3, §27.2. | JSON Schema enum. |
| Every record carries `created_from="CLAUDE_EQUITY_MODULE.md@<commit_sha>"`. | Traceability. | JSON Schema pattern. |
| Every observation-bearing family (`attribute`, `event_type`, `insight_type`, `connector_requirement`) must carry **non-null** PIT and rights policy fields. | CLAUDE.md project rule (PIT mandatory). | JSON Schema conditional on `object_family`. |
| `core_primitive` must be one of the seven universal node primitives (`universe`, `attribute`, `transform`, `filter`, `score`, `relationship`, `output_radar`) or one of the universal grammar primitives (`entity`, `candidate_set`, `event`, `evidence`, `assumption`, `transform`, `gate`, `score`, `relationship`, `scenario`, `decision`, `output`, `audit`). | CLAUDE §3, §21.2. | JSON Schema enum. |

---

## 2. Core identity (required for all 12 families)

| Field | Type | Required | Constraint |
|---|---|---|---|
| `id` | string | yes | `snake_case`, regex `^[a-z][a-z0-9_]{1,127}$`; unique within the object family. |
| `display_name` | string | yes | 1–120 chars; not equal to `id`. |
| `description` | string | yes | 1–2000 chars; explains the object's role to a reviewer. |
| `module_id` | string | yes | One of `viza.finance.equity_investment`, `viza.core.strategy`, `viza.aat.attribute_analysis`, `viza.finance.securities`. |
| `schema_version` | string | yes | Semver; matches the family's `viza.equity.<family>.<v1>` schema (e.g., `v1`, `v1.1`). |
| `source_sections` | array of strings | yes | Each entry is a CLAUDE-log section reference like `"§3"`, `"§10.4"`, `"§22.3"`. Min length 1. |
| `source_ids` | array of strings | conditional | Required when `confidence_label ∈ {high_confidence_core, common_practice}`; min length 1. Each entry is a source ID from the CLAUDE source corpus (e.g., `"F-001"`, `"FA-040"`, `"DA-022"`). |
| `confidence_label` | enum | yes | `high_confidence_core` \| `common_practice` \| `research_supported_experimental` \| `practitioner_observed` \| `speculative_or_low_confidence` \| `rejected_or_deferred`. |
| `status` | enum | yes | `registry-seedable` \| `implementation_ready` \| `deprecated` \| `retired` \| `draft`. New records default to `registry-seedable`. |
| `created_from` | string | yes | Pattern `CLAUDE_EQUITY_MODULE.md@<commit_sha_or_marker>`; e.g., `"CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline"`. |

`source_quality_minimum` (see §4) is the integer floor (1–5) on the lowest acceptable `source_quality_score` of any cited `source_id`. The loader cross-references against the global source corpus and rejects records whose cited sources fall below this floor.

---

## 3. VIZA mapping (required where the family supports it)

| Field | Type | Required | Applies to families |
|---|---|---|---|
| `core_primitive` | enum | yes | All families. One of: `entity`, `candidate_set`, `attribute`, `event`, `evidence`, `assumption`, `transform`, `gate`, `score`, `relationship`, `scenario`, `decision`, `output`, `audit`, `universe`, `filter`, `output_radar`. |
| `extends_core_primitive` | enum | conditional | Required for `node_type`. Must be one of the seven palette primitives (`universe`, `attribute`, `transform`, `filter`, `score`, `relationship`, `output_radar`). |
| `compatible_entity_types` | array of strings | yes (may be empty for purely meta records) | Entity-type IDs that this record may bind to. |
| `compatible_strategy_profiles` | array of strings | yes (may be empty for raw-data records) | Strategy-profile IDs this record is meaningful under. Empty array allowed only when the record is universally compatible (e.g., a connector_requirement). |
| `candidate_node_types` | array of strings | conditional | Required for `attribute`, `event_type`, `insight_type` — lists node IDs that consume/emit this object. |
| `candidate_attribute_keys` | array of strings | conditional | Required for `node_type`, `event_type`, `insight_type`, `strategy_profile`, `output_view` — lists attribute keys read by the object. |
| `candidate_event_types` | array of strings | conditional | Required for `node_type`, `insight_type`, `strategy_profile`, `output_view`. |
| `candidate_insight_types` | array of strings | conditional | Required for `node_type`, `strategy_profile`, `output_view`. |
| `output_views` | array of strings | conditional | Required for `strategy_profile`. Lists output view IDs the profile may emit. |

Loader resolution: every ID in any of these arrays must resolve against the corresponding registry. Unresolved IDs are loader errors, not warnings.

---

## 4. Evidence and audit (required for all 12 families)

| Field | Type | Required | Constraint |
|---|---|---|---|
| `evidence_requirements` | array of objects | yes | Each entry: `{evidence_type, required, source_quality_minimum, notes}`. Min length 1 when `confidence_label ∈ {high_confidence_core, common_practice}`. May be empty for purely structural records (e.g., entity_type / edge_type), but the loader emits a `warning` in that case. |
| `audit_requirements` | array of strings | yes | Subset of: `source_refs`, `pit_timestamps`, `rights_state`, `methodology_graph_hash`, `strategy_profile_hash`, `validation_record_ids`, `proof_checksum`, `connector_entitlement_record`, `human_review_record`. |
| `source_quality_minimum` | integer 1–5 | yes | Lowest acceptable `source_quality_score` for any cited source. Defaults: `high_confidence_core`→4, `common_practice`→3, `research_supported_experimental`→3, `practitioner_observed`→3, `speculative_or_low_confidence`→1. |
| `human_review_required` | boolean | yes | True when the record either (a) carries `confidence_label ∈ {research_supported_experimental, practitioner_observed, speculative_or_low_confidence}` and emits an action ≠ `watch`/`alert_only`, or (b) crosses any §19.9 human-review trigger (short/fraud language, restatement, binary event action, material litigation, manipulation alert, governance red flag high/critical). |

---

## 5. PIT (point-in-time) — required for observation-bearing families

Applies to: `attribute`, `event_type`, `insight_type`, `connector_requirement`, `pit_policy`. Other families (`entity_type`, `node_type`, `edge_type`, `strategy_profile`, `output_view`, `validation_rule`, `rights_policy`) may declare these fields as `null` only when they do not directly carry observations.

| Field | Type | Required | Constraint |
|---|---|---|---|
| `observed_at_policy` | enum | yes | `event_time` \| `filing_accepted_at` \| `publication_time` \| `vendor_publication_at` \| `release_date` \| `computation_time` \| `creation_time_only` \| `not_applicable` \| `unknown`. |
| `available_at_policy` | enum | yes | Same enum as `observed_at_policy`. The loader rejects records where `observed_at_policy != not_applicable` but `available_at_policy = not_applicable`. |
| `retrieved_at_policy` | enum | yes | `vendor_retrieval_at` \| `connector_ingest_at` \| `user_upload_at` \| `not_applicable`. |
| `source_version_policy` | enum | yes | `provider_version` \| `filing_amendment_chain` \| `regulator_version` \| `not_applicable` \| `unknown`. |
| `data_version_policy` | enum | yes | `vintaged` \| `latest_only` \| `latest_revisable` \| `event_pit` \| `not_applicable` \| `unknown`. |
| `model_version_policy` | enum | yes | `model_run_id_required` \| `model_release_required` \| `not_applicable`. |
| `vintage_required` | boolean | yes | `true` when backtest correctness depends on as-of historical data (macro, factor, consensus, restatement). Defaults to `true` when `data_version_policy ∈ {unknown}` (restrictive default). |
| `lookahead_risk` | enum | yes | `low` \| `medium` \| `high` \| `unknown`. Defaults to `high` when `data_version_policy = unknown` or `available_at_policy = unknown` (restrictive default). |

PIT-derived gates:
- `vintage_required=true` + connector lacks vintage capability → loader emits a `block` rule attaching `pit_warning` to runtime use.
- `lookahead_risk ∈ {high, unknown}` → record cannot be used in any backtest unless explicitly labeled `not_backtest_safe=true`.

---

## 6. Rights — required for all observation-bearing families

Applies universally; for purely structural records (`entity_type`, `edge_type`, etc.), the rights block declares the policy that applies when the record is referenced by an observation-bearing object.

| Field | Type | Required | Constraint |
|---|---|---|---|
| `connector_roles` | array of strings | yes | Subset of the 35 connector roles in CLAUDE §18.4. Empty array allowed only for derived/computed records that consume no external data. |
| `license_policy` | enum | yes | `public_official` \| `public_professional` \| `academic_public` \| `licensed_provider_required` \| `user_entitled_provider` \| `restricted_or_unclear` \| `derived_only` \| `internal_research_only` \| `unknown`. |
| `query_policy` | enum | yes | `allowed` \| `user_entitled` \| `blocked` \| `unknown`. |
| `cache_policy` | enum | yes | `allowed` \| `conditional` \| `blocked` \| `unknown`. |
| `display_policy` | enum | yes | `allowed` \| `conditional` \| `blocked` \| `unknown`. |
| `export_policy` | enum | yes | `allowed` \| `conditional` \| `blocked` \| `unknown`. |
| `derived_value_policy` | enum | yes | `allowed` \| `conditional` \| `blocked` \| `unknown`. |
| `redistribution_policy` | enum | yes | `allowed` \| `conditional` \| `blocked` \| `unknown`. |
| `marketplace_policy` | enum | yes | `allowed` \| `conditional` \| `redacted` \| `blocked` \| `unknown`. |
| `attribution_required` | boolean | yes | True when the source requires attribution on display/export (e.g., Kenneth French, Damodaran, EDGAR-attribution-recommended). |
| `retention_policy` | string | yes | One of: `indefinite`, `<N>_days_after_decision`, `until_license_expires`, `delete_on_user_revocation`, `not_applicable`. |
| `redaction_required` | boolean | yes | True when the record's raw values must be redacted in marketplace_draft packages. |

Rights-derived gates (restrictive defaults — JSON Schema `if/then` conditionals):
- `license_policy = unknown` → `query_policy ∈ {blocked, user_entitled}`, `export_policy ∈ {blocked, conditional}`, `marketplace_policy ∈ {redacted, blocked}`, `redaction_required = true`.
- `license_policy = restricted_or_unclear` → same as above.
- `license_policy = licensed_provider_required` → `redistribution_policy ∈ {blocked, conditional}`, `marketplace_policy ∈ {redacted, blocked, conditional}`.
- `license_policy = internal_research_only` → `export_policy = blocked`, `marketplace_policy = blocked`.
- `license_policy = derived_only` → `display_policy ∈ {allowed, conditional}`, raw export blocked.

---

## 7. Validation — required for all 12 families

| Field | Type | Required | Constraint |
|---|---|---|---|
| `validation_rules` | array of strings | yes | Validation rule IDs that apply to this record. Each ID resolves against `equity_validation_rules.json`. Min length 1 except for records of family `validation_rule` itself. |
| `failure_modes` | array of strings | yes | Subset of the failure modes defined in the CLAUDE log per section (e.g., `lookahead_bias`, `rumor_treated_as_confirmed_event`, `borrow_assumed_available`). Min length 1 when `confidence_label ∈ {high_confidence_core, common_practice}`. |
| `downgrade_conditions` | array of objects | yes | Each entry: `{condition, from_label, to_label, evidence_required}`. Records the rules that would downgrade this record's confidence label (e.g., publication decay, microcap dominance, transaction-cost dominance). Drawn from CLAUDE §34.3. |
| `rejection_conditions` | array of strings | yes | Subset of CLAUDE §34.2 rejection criteria. Triggers reject the record outright (e.g., `requires_unlawful_data`, `contradicts_CLAUDE.md_rules`, `requires_personalized_advice_output`). |

---

## 8. Conditional and cross-cutting rules

The JSON Schema encodes these conditionals (`if`/`then`/`else` blocks):

| Condition | Implication |
|---|---|
| `confidence_label ∈ {high_confidence_core, common_practice}` | `source_ids.length >= 1`, `evidence_requirements.length >= 1`, `failure_modes.length >= 1`. |
| `confidence_label = high_confidence_core` | `source_quality_minimum >= 4`. |
| `source_ids.length = 0` AND `confidence_label NOT IN {speculative_or_low_confidence, rejected_or_deferred}` | Loader forces `confidence_label = research_supported_experimental` (downgrade rule). |
| `license_policy ∈ {unknown, restricted_or_unclear}` | `export_policy ∈ {blocked, conditional}`, `marketplace_policy ∈ {redacted, blocked}`, `redaction_required = true`. |
| `data_version_policy = unknown` OR `available_at_policy = unknown` | `lookahead_risk = high`, `vintage_required = true`. |
| `object_family ∈ {attribute, event_type, insight_type, connector_requirement, pit_policy}` | All PIT fields non-null. |
| `object_family = strategy_profile` AND `output_views.length > 0` AND any view's `binding.recommendation` = true | `human_review_required` field present; legal-language guardrails (CLAUDE §17.7) enforced via attached validation rule. |
| `object_family = node_type` AND `extends_core_primitive = output_radar` | Output views must declare `non_advice_boundary_required = true`. |
| `object_family = strategy_profile` AND `mandate.directionality ∈ {short_only, long_short}` | Must reference borrow / squeeze / legal-review validation rules. |

---

## 9. Object-family-specific extensions

Every family adds its own fields **on top of** the base contract. Family-specific fields live in a `family_specific` sub-object so the base contract's `additionalProperties: false` rule does not flag them.

| Family | `family_specific` shape | Source CLAUDE schema |
|---|---|---|
| `entity_type` | `{identifiers, immutable_keys, relationship_types_outgoing, lifecycle_states}` | §20.3 |
| `node_type` | `{input_ports, output_ports, config_schema, allowed_connections, runtime_handler, missing_node_policy}` | §21.2 |
| `edge_type` | `{from_entity_type, to_entity_type, cardinality, directionality, optional_attributes}` | §20.5 |
| `attribute` | `{family, unit, data_type, directionality, raw_or_derived, source_type, frequency, timestamp_policy, sector_applicability, tier}` | §22.2 |
| `event_type` | `{event_family, source_origin, default_source_credibility, materiality_default, observed_at_policy, available_at_policy, materiality_rules, monitoring_triggers, invalidation_templates}` | §23.2 |
| `insight_type` | `{insight_family, direction_logic, translation_rules, invalidation_templates, confirmation_templates, non_advice_boundary_required}` | §24.2 |
| `strategy_profile` | `{strategy_family_ids, composition_rules, mandate, universe, preferred_signals, required_confirmations, required_risk_gates, invalidation_policy, monitoring_cadence, score_methodology, insight_translation_overrides, evidence_standards, validation_block}` | §25.2 |
| `output_view` | `{view_family, required_sections, optional_sections, binding, evidence_render, audit_render, lifecycle, data_rights}` | §26.2 |
| `validation_rule` | `{domain, severity, applies_to, trigger_logic, remediation}` | §19.2 |
| `connector_requirement` | `{provider, credential_ref, entitlement_metadata, rate_limits, retry_policy, production_required}` | §18.10 |
| `rights_policy` | `{source_id_pattern, notes}` | §18.5 (rights matrix row) |
| `pit_policy` | `{data_category, observed_at_definition, available_at_definition, revision_class, current_aat_status, notes}` | §18.6 + §18.8 |

The companion JSON Schema applies `oneOf` on `object_family` to select the correct `family_specific` sub-schema.

---

## 10. Acceptance criteria

| Criterion (from upgrade prompt) | How this contract satisfies it |
|---|---|
| Schema strict enough to catch missing PIT and rights fields. | PIT block (§5) and rights block (§6) are required on every observation-bearing family. Missing fields fail `required` enforcement; ambiguous fields fall through restrictive defaults (§8 conditionals). The JSON Schema sets `additionalProperties: false` and uses `if/then` to enforce conditional requirements. |
| Schema flexible enough for all registry object families. | Base contract is family-agnostic (§§2–7). Family-specific fields live in `family_specific` (§9) selected via `oneOf` on `object_family`. |
| Unknown rights default to blocked export and redacted marketplace packaging. | Rights restrictive-defaults conditionals (§6 + §8): `license_policy ∈ {unknown, restricted_or_unclear}` forces `export_policy ∈ {blocked, conditional}` and `marketplace_policy ∈ {redacted, blocked}` and `redaction_required = true`. |
| Missing source lineage blocks promotion above `research_supported_experimental`. | Source-lineage promotion gate (§1 + §8): when `source_ids.length = 0`, the loader forces `confidence_label = research_supported_experimental` at most; the JSON Schema enforces `source_ids.minItems = 1` when `confidence_label ∈ {high_confidence_core, common_practice}`. |

---

## 11. Loader contract (informative)

A registry loader (to be implemented under `viza/registry/`) must:

1. Parse the artifact file using the family-appropriate parser (JSON or CSV with documented columns).
2. Validate every record against `equity_registry_shared_metadata.schema.json`.
3. Apply the restrictive-default forcing rules (§§5–6) and downgrade rules (§8) **after** schema validation; record every forced change to `equity_rejection_and_downgrade_log.csv`.
4. Resolve every cross-reference ID (entity, attribute, event, insight, profile, output_view, validation_rule, connector_role, rights_policy_id, pit_policy_id).
5. Cross-reference cited `source_ids` against the global source corpus and assert `source_quality_score >= source_quality_minimum`.
6. Emit a `validation_record` per artifact and a combined `proof_<sha256>.json` per artifact set.
7. Fail closed on missing license credentials (CLAUDE.md project rule) for connector requirements with `production_required=true`.

---

## 12. Open questions deferred to next pass

1. Whether `source_quality_score` should be stored on each record (denormalized) or only on the global source corpus (loader cross-reference). **Decision applied here:** loader cross-reference; records carry only `source_quality_minimum` as a floor.
2. Whether `human_review_required` should be a single boolean or a structured `{required, trigger_codes, reviewer_role}` object. **Decision applied here:** boolean for v0.1; expand to structured object in v0.2 if needed.
3. Whether to support multi-module records (e.g., a node bound to both `viza.finance.equity_investment` and `viza.core.strategy`). **Decision applied here:** single `module_id` per record; cross-module records are duplicated with distinct IDs.
4. Whether the PIT block should support partial null (some fields filled, others not). **Decision applied here:** all PIT fields required and non-null for observation-bearing families; `not_applicable`/`unknown` allowed as enum values.

These questions do not block adoption of the contract.

---

**End of `shared_metadata_contract.md`** — companion JSON Schema is at [`equity_registry_shared_metadata.schema.json`](equity_registry_shared_metadata.schema.json).
