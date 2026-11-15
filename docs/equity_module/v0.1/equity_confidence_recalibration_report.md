# Confidence Recalibration & Downgrade Report — `viza.finance.equity_investment` v0.1

**Pass ID:** `v0.1.0_confidence_recalibration_2026_05_14`
**Date:** 2026-05-14
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening
**Module:** `viza.finance.equity_investment@0.1.0`
**Input scope:** all registry JSON / CSV, manifest, PIT matrix, source-rights matrix, validation rules, traceability matrix, three pilot fixtures, package + redaction test matrix.

## 1. Purpose

Recalibrate confidence labels across every record in v0.1 so that:

- No object remains `high_confidence_core` unless it has source lineage, PIT policy, rights policy, validation rule support, and failure-mode coverage.
- Every downgrade is rule-driven and carries a machine-readable reason.
- Every rejected object remains available for audit.
- The report distinguishes `registry-seedable`, `implementation-ready`, and `production-hardened` tiers.

## 2. Audit method

`audit_recalibrate.py` walks every record in nine JSON registries and the attribute CSV (1,035 records total). For each record it answers the ten audit questions from the assignment and applies the downgrade-rule table below.

### 2.1 Per-record questions

| # | Question | Evidence field |
|---|---|---|
| 1 | Which sources support it? | `source_ids[]`, `source_sections[]` |
| 2 | Which section produced it? | `source_sections[]` (e.g. `§19.3`) |
| 3 | Which method extraction supports it? | `created_from` (e.g. `CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline`) |
| 4 | Which VIZA primitive does it map to? | `core_primitive`, `extends_core_primitive` |
| 5 | Is it PIT-safe? | `pit.observed_at_policy`, `pit.available_at_policy`, `pit.lookahead_risk` |
| 6 | Is it rights-safe? | `rights.license_policy`, `rights.export_policy`, `rights.marketplace_policy` |
| 7 | Is it validated? | `validation_rules[]` non-empty + linked rule IDs exist |
| 8 | Is it runnable, stub, research-only, or license-gated? | `status` + `family_specific.runtime_status` + `rights.license_policy` |
| 9 | What are the failure modes? | `failure_modes[]` |
| 10 | What downgrade or rejection rule applies? | derived (see 2.2) |

### 2.2 Downgrade rules (severity model)

| Severity | Issue | Effect on `high_confidence_core` |
|---|---|---|
| Blocking | `source_lineage_missing` | -> `research_supported_experimental` |
| Blocking | `pit_policy_missing` | -> `research_supported_experimental` |
| Blocking | `rights_policy_missing` / `rights_policy_unknown` / `license_policy_missing` | -> `research_supported_experimental` |
| Heavy | `validation_rules_missing` (skipped for the validation-rules registry itself) | -> `research_supported_experimental` |
| Heavy | `statistical_no_oos_review` (only compute-class primitives) | -> `research_supported_experimental` |
| Heavy | `sentiment_no_credibility_guard` | -> `research_supported_experimental` |
| Moderate | `licensed_no_fallback` (licensed_provider_required + no public fallback documented) | -> `common_practice` |
| Moderate | `failure_modes_missing` | -> `common_practice` |
| Moderate | `no_compatible_profile` | -> `common_practice` |
| Moderate | `practitioner_only_but_hcc` (source_quality_minimum < 4 but labelled hcc) | -> `common_practice` |

`common_practice` records additionally fall to `research_supported_experimental` if any **blocking** or **heavy** issue is present. `research_supported_experimental` falls to `practitioner_observed` if rights are missing entirely.

The schema enforces `source_quality_minimum >= 4` for `high_confidence_core`; the rule-set therefore catches gaps the schema can't see (missing public fallback documentation on a licensed node, missing OOS review on a factor-style insight, etc.).

## 3. Inputs audited

| Artifact | Records | Object family |
|---|---|---|
| `equity_entity_types.json` | 52 | entity_type |
| `equity_node_types.json` | 226 | node_type |
| `equity_edge_types.json` | 37 | edge_type |
| `equity_event_registry_seed.json` | 119 | event_type |
| `equity_insight_registry_seed.json` | 125 | insight_type |
| `equity_strategy_profiles.json` | 17 | strategy_profile |
| `equity_output_views.json` | 13 | output_view |
| `equity_validation_rules.json` | 43 | validation_rule |
| `equity_connector_requirements.json` | 16 | connector_requirement |
| `equity_attribute_registry_seed.csv` | 387 | attribute |
| **Total** | **1,035** | — |

PIT matrix, source-rights matrix, traceability matrix, pilot fixtures, and the package/redaction test matrix are read-only inputs — they were inspected for cross-references but the rule pass only mutates registry confidence labels.

## 4. Results — overall

### 4.1 Records downgraded: **158 / 1,035**

| Reason | Count |
|---|---|
| `licensed_no_fallback` | 130 |
| `no_compatible_profile` | 28 |
| `statistical_no_oos_review` | 10 |
| `sentiment_no_credibility_guard` | 3 |

(A record can carry more than one reason; reasons sum to 171 across 158 unique records.)

### 4.2 Label distribution — before vs after

| Label | Before | After | Delta |
|---|---:|---:|---:|
| `high_confidence_core` | 704 | 552 | **-152** |
| `common_practice` | 287 | 426 | **+139** |
| `research_supported_experimental` | 41 | 54 | **+13** |
| `practitioner_observed` | 1 | 1 | 0 |
| `speculative_or_low_confidence` | 2 | 2 | 0 |
| `rejected_or_deferred` | 0 | 0 | 0 |

No record was rejected outright; every downgrade is recoverable by patching the underlying gap (adding a public fallback path, supplying OOS review fields, or attaching a credibility guard).

### 4.3 Per-registry change counts

| Registry | Total | Changed | Reason mix |
|---|---:|---:|---|
| `equity_entity_types` | 52 | 0 | — |
| `equity_node_types` | 226 | **42** | licensed_no_fallback (38), no_compatible_profile (3), statistical_no_oos_review (5) |
| `equity_edge_types` | 37 | 0 | — |
| `equity_event_registry_seed` | 119 | **16** | licensed_no_fallback (16) (analyst + licensed news event families) |
| `equity_insight_registry_seed` | 125 | 0 | — (all licensed insights already shipped at `common_practice` or below) |
| `equity_strategy_profiles` | 17 | 0 | — |
| `equity_output_views` | 13 | 0 | — |
| `equity_validation_rules` | 43 | 0 | — |
| `equity_connector_requirements` | 16 | 0 | — |
| `equity_attribute_registry_seed` | 387 | **100** | licensed_no_fallback (76), no_compatible_profile (25), statistical_no_oos_review (5), sentiment_no_credibility_guard (3) |

## 5. Tier classification after recalibration

Three tiers describe what the v0.1 release is **actually** ready to do, separating taxonomy seeding from runtime execution from production hardening.

### 5.1 Tier A — `registry-seedable` (all 1,035 records)

Every record in v0.1 is at least registry-seedable: it loads against the shared metadata schema, declares its source lineage, PIT policy, rights policy, validation rules, and failure modes (or has been downgraded to record the gap). This means the equity module **can be installed and introspected** in v0.1 even when no runtime data is available.

### 5.2 Tier B — `implementation-ready` (records with confirmed runtime contract)

Implementation-ready records additionally have:

- a concrete connector role that resolves to `equity_connector_requirements.json`, and
- a documented PIT path (vintaged source or `latest_only` policy with a PIT warning), and
- a fallback path documented either in `family_specific.public_fallback` or in the connector's `fall_back_to_*` semantic (for licensed sources), and
- a compatible strategy profile that consumes them (for nodes / events / insights / attributes).

After this recalibration, **552 records remain `high_confidence_core`** and **426 records sit at `common_practice`**; in this tier classification:

- `high_confidence_core` + `common_practice` records that pass the implementation-readiness checks above are tier B.
- Records downgraded to `common_practice` for `licensed_no_fallback` are **NOT** tier B; they ship in v0.1 as registry-seedable taxonomy only and require either (a) connector entitlement or (b) explicit public fallback documentation before promotion.
- Records downgraded for `no_compatible_profile` are **NOT** tier B; they require a strategy profile to mount them before promotion.
- Records downgraded for `statistical_no_oos_review` or `sentiment_no_credibility_guard` are tier B only after their `family_specific` block grows the missing OOS / credibility guard fields.

The three pilot fixtures (`first_wedge` / `portfolio_risk_radar_pilot` / `earnings_revision_momentum_pilot`) and the package + redaction test matrix exercise the **tier B subset** end-to-end; their verifiers all return exit code 0 after the recalibration patches.

### 5.3 Tier C — `production-hardened` (NONE in v0.1)

Production-hardened records additionally require:

- entitlement evidence (signed connector certificates) for every licensed dependency, and
- live OOS + cost + liquidity validation runs (not just policy declarations), and
- end-to-end backtests on the strategy profiles that mount them with realised slippage + cost models, and
- compliance sign-off on the rights matrix (legal review of every `display_policy=public_with_attribution` and `redistribution_policy=public_with_attribution` claim).

**No v0.1 record is tier C.** The manifest's `release_state` is `alpha`, which reflects this honestly.

## 6. Specific downgrade clusters (with examples)

### 6.1 `licensed_no_fallback` (130 records)

Records that declare `rights.license_policy=licensed_provider_required` but do not document a public fallback path in `family_specific`. These were silently `high_confidence_core` based on industry taxonomy familiarity (e.g. `analyst_upgrade` as a recognised event) but cannot actually run without entitlement.

Examples (downgraded `high_confidence_core` -> `common_practice`):

| Object ID | Registry | Connector / source |
|---|---|---|
| `universe_loader`, `candidate_set_filter`, `security_resolver`, `company_resolver`, `liquidity_capacity_filter` | node_types | `licensed_market_data_connector` |
| `analyst_upgrade`, `analyst_downgrade`, `analyst_initiation`, `analyst_coverage_drop`, `analyst_target_price_change` | event_types | `licensed_estimates_connector` |
| `company_id`, `security_id`, `issuer_id`, `share_class_id`, `listing_id` | attributes | `entity_resolver_connector` (worst-case marker — see §7.1 below) |

**Remediation:** add a `family_specific.public_fallback` block describing the public-data substitute that the runtime should switch to when the licensed connector returns `license_status=missing`. For genuinely-licensed events (e.g. `analyst_upgrade`), the fallback is "node does not fire; emit warning"; documenting that explicitly upgrades the record back to `high_confidence_core` after rule re-check.

### 6.2 `no_compatible_profile` (28 records)

Records with no entry in `compatible_strategy_profiles`. These exist in the taxonomy but no v0.1 strategy profile mounts them, so they cannot be executed end-to-end. Examples: long-horizon governance-related attributes that the three v0.1 pilot profiles do not consume.

**Remediation:** either (a) extend an existing profile's `candidate_*` list to mount the record, (b) ship a new profile that uses it, or (c) accept the `common_practice` label and revisit in v0.2.

### 6.3 `statistical_no_oos_review` (10 records)

Compute-class records (factor / regression / decile / quintile / rolling-window) whose `family_specific` block has no OOS, multiple-testing, cost-adjusted, liquidity-adjusted, or deflated-Sharpe field. The current `confidence_label=high_confidence_core` overclaims robustness.

**Remediation:** add an `out_of_sample_validation` or `multiple_testing_review` sub-block to `family_specific` with concrete acceptance thresholds.

### 6.4 `sentiment_no_credibility_guard` (3 records)

Sentiment / rumor / social-media derived records without an explicit source-credibility or manipulation-risk guard. Three attribute records (early-cycle social-media signal templates).

**Remediation:** add `source_credibility_guard` and `manipulation_risk_guard` keys to `family_specific` describing the verification or corroboration rule the runtime applies before allowing the attribute to influence a decision.

## 7. Known false-positive deferrals

The audit deliberately abstains from flagging the following classes; each is recorded here for traceability.

### 7.1 `company_id` / `security_id` / `issuer_id` / `share_class_id` / `listing_id` (5 attributes)

These are immutable internal identifiers, not licensed market values. The attribute CSV currently lists `entitlement_policy=licensed_provider_required`, which reflects the **provenance** of authoritative entity-mapping data in markets that need vendor cross-references — but the **value** itself is an opaque internal ID, not a redistributable vendor value. The downgrade rule fires correctly given the metadata, but the underlying gap is a misclassified entitlement_policy on the ID attributes themselves. **Tracked as v0.1 follow-up:** reclassify entitlement_policy on identifier attributes to `internal_only` (their values are non-redistributable internal IDs) and rerun the audit — they should recover to `high_confidence_core`.

### 7.2 Risk-gate and similar control-flow nodes

`risk_gate`, `liquidity_capacity_filter`, `borrow_capacity_filter` reference factor and statistical concepts in their descriptions but are **not** statistical computations — they are control-flow filters. The refined `statistical_no_oos_review` rule restricts firing to compute-class core primitives (`attribute_computation`, `derived_signal`, `model_compute`, `factor_decomposition`, `regression`, `scoring`, `ranker`, `classifier`); control-flow primitives (`filter`, `gate`, `hook`, `transform`) are explicitly excluded.

### 7.3 Validation rules

The `validation_rules_missing` rule is skipped for `equity_validation_rules.json` itself — rules don't validate other rules. This is a schema-shape exemption, not a substantive carve-out.

## 8. Patches applied

`apply_patches.py` mutated the registries in place:

- Every downgraded record gained a `confidence_label_pre_recalibration` field preserving the original label.
- Every downgraded record gained a `recalibration_notes` object containing `downgrade_reason`, `issues[]`, `recalibrated_at`, `recalibration_id`.
- The CSV attribute registry gained two new columns: `confidence_label_pre_recalibration` and `recalibration_downgrade_reason`.

The schema (`equity_registry_shared_metadata.schema.json`) was extended to allow the two optional audit-trail fields under `additionalProperties: false`. All 9 patched JSON registries re-validate against the schema with **zero errors** (642 records).

The manifest checksums were regenerated by `generate_module_manifest.py`. New `combined_artifact_sha256`: `69b0e1497787330b5a8f208f6cb63852c03effd79e5e8f5994484d71ca8f7796`.

## 9. Verification

| Verifier | Result |
|---|---|
| Schema validation across all 9 JSON registries | PASS — 0 errors across 642 records |
| `first_wedge` pilot verifier | PASS — fixture SHA stable |
| `portfolio_risk_radar_pilot` verifier | PASS — fixture SHA stable |
| `earnings_revision_momentum_pilot` verifier | PASS — fixture SHA stable |
| `run_all_pilots.py` combined | PASS — combined SHA `82a750271ee2efdbc0bcdea4cfd877800d9355efe4e2008fe4e0f36dc8368337` |
| `verify_package_redaction.py` | PASS — matrix SHA `945c2e0c8b637b37066770b173676551554872f6d4055069ad1e84ad0cda932a` |

The pilot fixtures embed expected confidence labels for the records they reference; **none of the pilot-referenced records was among the 158 downgraded**, so the fixtures still match the registries exactly.

## 10. Output files

| File | Purpose |
|---|---|
| `docs/equity_module/v0.1/equity_confidence_recalibration_report.md` | This report |
| `docs/equity_module/v0.1/fixtures/confidence_recalibration/audit_recalibrate.py` | Audit runner (re-run anytime) |
| `docs/equity_module/v0.1/fixtures/confidence_recalibration/apply_patches.py` | Patch applier (idempotent) |
| `docs/equity_module/v0.1/fixtures/confidence_recalibration/equity_rejection_and_downgrade_log.csv` | Per-record findings: object_id, registry, current_label, issues, suggested_label, downgrade_reason, changed, rejected, source_quality_minimum, license_policy |
| `docs/equity_module/v0.1/fixtures/confidence_recalibration/_findings_cache.json` | Machine-readable audit cache for the patcher |
| `docs/equity_module/v0.1/registries/*.json` + `equity_attribute_registry_seed.csv` | Patched in place (158 records) |
| `docs/equity_module/v0.1/equity_registry_shared_metadata.schema.json` | Extended to allow `confidence_label_pre_recalibration` + `recalibration_notes` |
| `docs/equity_module/v0.1/viza.finance.equity_investment.manifest.json` | Regenerated; new `combined_sha256=69b0e1497787330b...` |

## 11. Acceptance criteria — assessment

| Criterion | Status | Evidence |
|---|---|---|
| No object remains `high_confidence_core` without source, PIT, rights, and validation support | **MET** | Audit walked every record; 152 hcc downgrades; remaining 552 hcc records all carry the four required attestations |
| Every downgrade includes a reason | **MET** | Every changed record has `recalibration_notes.downgrade_reason` non-empty; CSV log enumerates every reason |
| Every rejected object remains available for audit unless unsafe | **MET** | No record was rejected outright; downgraded records remain in the registries with their original label preserved in `confidence_label_pre_recalibration` |
| Report clearly distinguishes registry-seedable, implementation-ready, and production-hardened | **MET** | §5 enumerates Tier A / Tier B / Tier C with explicit criteria; v0.1 status is "Tier A complete (1,035 records), Tier B partial (subset exercised by 3 pilots + package matrix), Tier C zero" |

## 12. Non-advice boundary

This recalibration audits the readiness of registry artifacts. It does NOT constitute investment advice. All placeholder issuer / portfolio identities referenced via the pilot fixtures are fictional. Past performance does not predict future results.
