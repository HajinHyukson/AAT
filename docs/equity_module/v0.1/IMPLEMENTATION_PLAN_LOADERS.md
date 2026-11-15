# Implementation Plan — `viza.finance.equity_investment` Registry Seeders + Validators

**Path:** `docs/equity_module/v0.1/IMPLEMENTATION_PLAN_LOADERS.md`
**Source of truth:** CLAUDE log + all generated registry artifacts under `docs/equity_module/v0.1/registries/`.
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening.
**Conformance:** shared metadata contract at `docs/equity_module/v0.1/equity_registry_shared_metadata.schema.json`; manifest contract at `docs/equity_module/v0.1/viza.module.manifest.v1.schema.json`.

The repo already exposes parallel patterns to follow:
- Loader pattern: [viza/attribute_registry.py](../../../viza/attribute_registry.py) — Pydantic `BaseModel` with `ConfigDict(extra="forbid")`, schema-version constants, `load_*()` factory, `*Registry` container.
- Module-level orchestration: [viza/modules/registry.py](../../../viza/modules/registry.py) — `ModuleRegistry` with graceful missing-module degradation (`create_unknown_node_placeholder`).
- Config-path resolution: [viza/config_paths.py](../../../viza/config_paths.py) — `VIZA_CONFIG_DIR` / `VIZA_ENGINE_ROOT` env var resolution + source fallback.
- Test pattern: [tests/unit/test_viza_attribute_registry.py](../../../tests/unit/test_viza_attribute_registry.py).

The equity module fits cleanly into a new sub-package `viza/equity/`. No existing `viza_graph_v0`, attribute-registry, manifest-checksum, or universal-entity-store code is touched.

---

## 1. Proposed file paths

```text
viza/equity/                                       <- new sub-package
  __init__.py                                      <- exports + version constants
  errors.py                                        <- exception + warning hierarchy
  types.py                                         <- common type aliases / enums
  source_corpus.py                                 <- source-ID resolver
  entity_registry.py                               <- viza.equity.entity_registry.v1
  node_type_registry.py                            <- viza.equity.node_type_registry.v1
  edge_type_registry.py                            <- viza.equity.edge_type_registry.v1
  attribute_registry.py                            <- viza.equity.attribute.v1
  event_registry.py                                <- viza.equity.event_type.v1
  insight_registry.py                              <- viza.equity.insight_type.v1
  strategy_profile_registry.py                     <- viza.equity.strategy_profile.v1
  output_view_registry.py                          <- viza.equity.output_view.v1
  validation_rule_registry.py                      <- viza.equity.validation_rule.v1
  connector_requirement_registry.py                <- viza.equity.connector_requirement.v1
  rights_matrix.py                                 <- equity_source_rights_matrix.csv loader
  pit_matrix.py                                    <- equity_PIT_matrix.csv loader
  manifest.py                                      <- viza.module.manifest.v1 loader
  cross_reference.py                               <- cross-artifact validators (profile↔view, insight↔profile, node↔connector, etc.)
  pit_validator.py                                 <- PIT enforcement (no-lookahead, 13F lag, vintage)
  rights_validator.py                              <- rights enforcement (fail-closed, redaction, package mode)
  validation_engine.py                             <- runs validation rules from equity_validation_rules.json

tests/unit/                                        <- existing dir (33 viza tests today)
  test_equity_entity_registry.py
  test_equity_node_type_registry.py
  test_equity_edge_type_registry.py
  test_equity_attribute_registry.py
  test_equity_event_registry.py
  test_equity_insight_registry.py
  test_equity_strategy_profile_registry.py
  test_equity_output_view_registry.py
  test_equity_validation_rule_registry.py
  test_equity_connector_requirement_registry.py
  test_equity_rights_matrix.py
  test_equity_pit_matrix.py
  test_equity_manifest.py
  test_equity_cross_reference.py
  test_equity_pit_validator.py
  test_equity_rights_validator.py
  test_equity_validation_engine.py
  test_equity_fail_closed.py
  test_equity_missing_optional_module.py
  test_equity_marketplace_draft_redaction.py
  test_equity_ticker_never_primary_key.py
  test_equity_non_advice_boundary.py
  test_equity_human_review_gate.py

tests/fixtures/equity_module/                     <- new
  v0.1/                                            <- mirrors the registries dir
  invalid_records/                                 <- crafted invalid records for fail-closed tests
  golden_runs/                                     <- canonical loader output snapshots

docs/equity_module/v0.1/                          <- already populated
  registries/...                                   <- the 12 artifacts (already generated)
  equity_registry_shared_metadata.schema.json      <- already generated
  viza.module.manifest.v1.schema.json              <- already generated
  viza.finance.equity_investment.manifest.json     <- already generated
  GENERATION_MAP.md, shared_metadata_contract.md, etc.
```

Notes:
- **No file under `viza/equity/` exists today.** Adding the sub-package is purely additive per the existing `viza/modules/` precedent.
- Artifact path resolution at runtime uses [viza/config_paths.py](../../../viza/config_paths.py) extended with one helper: `equity_module_dir()` returning `<config_root>/equity_module/v0.1/registries/`. Until that path is wired into the packaged engine, the loaders accept an explicit `artifact_dir` argument defaulting to the repo-root `docs/equity_module/v0.1/registries/` so tests work without env config.
- Test fixtures reuse the on-disk artifacts directly when possible (single source of truth) and only copy into `tests/fixtures/equity_module/` for the negative cases (crafted invalid records).

---

## 2. Loader responsibilities

Every loader follows the same five-step contract:

```
1. Read the artifact file (JSON or CSV).
2. Validate every record against the strict shared metadata contract
   (equity_registry_shared_metadata.schema.json, object_family-specific oneOf branch).
3. Apply restrictive defaults: license=unknown -> export blocked + marketplace redacted;
   PIT unknown -> vintage_required=true + lookahead_risk=high.
4. Build typed Pydantic objects + an indexed Registry container.
5. Emit a LoadReport summarising counts, warnings, downgrades, and rejections.
```

Per-loader specifics:

| Loader file | Reads | Returns | Key index | Source CLAUDE section |
|---|---|---|---|---|
| `entity_registry.py` | `equity_entity_types.json` | `EntityTypeRegistry` | by `id` + by `family_specific.identifiers` | §20.3 |
| `node_type_registry.py` | `equity_node_types.json` | `NodeTypeRegistry` | by `id` + by `family_specific.family` + by `extends_core_primitive` | §21.3 |
| `edge_type_registry.py` | `equity_edge_types.json` | `EdgeTypeRegistry` | by `id` + by `(from_entity_type, to_entity_type)` | §20.5 |
| `attribute_registry.py` | `equity_attribute_registry_seed.csv` | `EquityAttributeRegistry` | by `key` + by `family` | §22 |
| `event_registry.py` | `equity_event_registry_seed.json` | `EventTypeRegistry` | by `id` + by `family_specific.event_family` | §23 |
| `insight_registry.py` | `equity_insight_registry_seed.json` | `InsightTypeRegistry` | by `id` + by `family_specific.insight_family` | §24 |
| `strategy_profile_registry.py` | `equity_strategy_profiles.json` | `StrategyProfileRegistry` | by `id` + by `family_specific.strategy_family_ids` | §25 |
| `output_view_registry.py` | `equity_output_views.json` | `OutputViewRegistry` | by `id` + by `family_specific.view_family` | §26 |
| `validation_rule_registry.py` | `equity_validation_rules.json` | `ValidationRuleRegistry` | by `id` + by `family_specific.validation_level` + by `family_specific.domain` | §19 |
| `connector_requirement_registry.py` | `equity_connector_requirements.json` | `ConnectorRequirementRegistry` | by `id` + by `family_specific.data_types` | §18.4 |
| `rights_matrix.py` | `equity_source_rights_matrix.csv` | `RightsMatrix` | by `data_type` + by `connector_role` | §18.5 |
| `pit_matrix.py` | `equity_PIT_matrix.csv` | `PITMatrix` | by `data_type` | §18.6/18.8 |
| `manifest.py` | `viza.finance.equity_investment.manifest.json` | `EquityModuleManifest` | loads all of the above, computes combined sha256, exposes `EquityModule` facade | §27 |

Each Registry container exposes a uniform read API:

```python
class EntityTypeRegistry:
    def get(self, id: str) -> EntityType | None: ...
    def require(self, id: str) -> EntityType: ...      # raises EntityTypeUnknownError
    def by_family(self, family: str) -> list[EntityType]: ...
    def all_ids(self) -> list[str]: ...
    def load_report(self) -> LoadReport: ...
```

`LoadReport` carries:

```python
@dataclass
class LoadReport:
    artifact_file: Path
    artifact_sha256: str
    records_loaded: int
    records_rejected: int
    warnings: list[LoadWarning]
    downgrades: list[ConfidenceDowngrade]
    restrictive_defaults_applied: list[RestrictiveDefaultApplication]
    duration_ms: float
    loaded_at: datetime
```

`EquityModule` is a single facade that holds the 12 registries plus the manifest, and is the entry point downstream code uses:

```python
module = EquityModule.load()              # uses config_paths default
module.entity_types.require("equity_security")
module.profiles.require("quality_value_long_only")
module.cross_reference.verify_all()       # raises CrossReferenceError on first failure
```

---

## 3. Validation checks

Every check is implemented as a pure function `check_X(record, *registries) -> CheckResult` so it can be unit-tested independently. The checks are wired into the loader pipeline and the standalone `validation_engine.py`.

### 3.1 Per-record checks (run inside each loader)

| Check | Enforces | Implementation |
|---|---|---|
| `schema_conformance` | record validates against `equity_registry_shared_metadata.schema.json` strict oneOf branch | `jsonschema.Draft202012Validator(schema).iter_errors(record)` (already wired in test harness) |
| `source_sections_valid` | every entry matches `^§[0-9]+(\.[0-9]+){0,2}$` | regex |
| `source_ids_resolve` | every `source_id` either resolves against `source_corpus.py` or carries `created_from=internal_design_hypothesis` marker | `source_corpus.resolve(id)` |
| `confidence_label_valid` | enum membership + downgrade gates (high_confidence_core requires `source_quality_minimum>=4` AND non-empty `source_ids`) | conditional |
| `restrictive_defaults_applied` | unknown rights force blocked export + redacted marketplace; unknown PIT forces vintage_required + lookahead_risk=high | mutation with log |
| `confidence_downgrade_on_missing_lineage` | empty `source_ids` for a record labeled `high_confidence_core`/`common_practice` → forced to `research_supported_experimental` | mutation with log |

### 3.2 Cross-artifact checks (run in `cross_reference.py`)

| Check | What it enforces | Reads |
|---|---|---|
| `no_ticker_as_primary_key` | No entity's `immutable_keys` contains `ticker` or alias | entity registry |
| `pit_fields_on_observation_bearing_objects` | `attribute`, `event_type`, `insight_type`, `connector_requirement`, `pit_policy` all declare `pit.observed_at_policy != not_applicable` AND `pit.available_at_policy != not_applicable` | all registries |
| `rights_fields_on_data_dependent_objects` | every observation-bearing record carries the full 12-field `rights` block (already enforced at schema level — cross-reference adds the assertion that `license_policy` and `connector_roles` resolve via the rights matrix / connector registry) | rights matrix + connector registry |
| `valid_source_section_references` | every `§X.Y` reference is recognised; unknown sections trigger warning | regex + a curated section index |
| `valid_source_ids_or_internal_design_hypothesis` | every source_id resolves OR the record carries `created_from` marking it as an internal design hypothesis | source_corpus |
| `valid_confidence_labels` | enum membership + per-label minimum source_quality + non-empty source_ids when label ≥ common_practice | per-record |
| `output_views_have_rights_redaction_rules` | every `output_view` record has non-empty `family_specific.rights_redaction_rules` | output view registry |
| `insight_types_map_to_profiles` | every insight's `family_specific.translation_rules.per_profile_translation` references a profile that exists in the strategy_profile registry | insight + profile registries |
| `profiles_map_to_output_views` | every profile's `family_specific.output_views` (or top-level `output_views`) references views that exist in the output_view registry | profile + output_view registries |
| `node_connector_roles_exist` | every node's `rights.connector_roles` resolves either to a `connector_requirement.id` or to one of its `family_specific.data_types` | node + connector registries |
| `package_visibility_rules_compatible_with_rights` | every output view's `family_specific.package_visibility_modes` is consistent with `data_rights.marketplace_policy` (marketplace_draft permitted only when marketplace_policy ∈ {redacted, conditional, allowed}) | output_view registry |
| `marketplace_draft_redacts_restricted_or_unclear` | every record with `rights.license_policy ∈ {unknown, restricted_or_unclear}` must have `rights.marketplace_policy ∈ {redacted, blocked}` AND `redaction_required=true` | all registries |
| `non_advice_boundary_on_recommendation_outputs` | every output_view with `extends_core_primitive=output_radar` AND `view_family ∈ {memo, trade_plan, radar, risk_dashboard}` must have `family_specific.non_advice_boundary_required_explicit=true` AND `required_sections` includes `non_advice_boundary` | output_view registry |
| `human_review_gates_attached` | every `short_state` insight + every `manipulation_*`/`meme_*` insight has `human_review_required=true`; every short-side profile (directionality ∈ {short_only, long_short, market_neutral}) has `human_review_required=true` | insight + profile registries |
| `binding_to_manifest_arrays` | every manifest array (entity_types, node_types, …, validation_rules) equals the set of IDs loaded from the corresponding registry | manifest + registries |
| `combined_artifact_checksum_matches` | the manifest's `artifact_checksums.combined_sha256` equals SHA-256 of every artifact's individual SHA-256 concatenated in artifact_definition order | manifest + filesystem |

A single entry point runs all cross-reference checks:

```python
def verify_all(self, *, raise_first_error: bool = False) -> CrossReferenceReport:
    """Run every cross-reference check; collect all errors before returning unless raise_first_error is True."""
```

---

## 4. Error and warning classes

`viza/equity/errors.py`:

```python
class EquityRegistryError(Exception):
    """Base error for all equity-module registry failures. Always carries the
    artifact_file, record_id, and remediation hint."""

class SchemaConformanceError(EquityRegistryError): ...
class RecordRejectedError(EquityRegistryError): ...
class UnknownIdReferenceError(EquityRegistryError): ...    # e.g., insight references a profile that doesn't exist
class CrossReferenceError(EquityRegistryError): ...        # one or more cross-artifact checks failed
class RightsViolationError(EquityRegistryError): ...       # marketplace_draft contains unredacted restricted evidence
class PITViolationError(EquityRegistryError): ...          # lookahead detected, vintage missing, 13F used as current
class TickerAsPrimaryKeyError(EquityRegistryError): ...    # CLAUDE.md project rule
class MissingHumanReviewError(EquityRegistryError): ...    # short/fraud/legal exported without review
class NonAdviceBoundaryMissingError(EquityRegistryError): ...
class LicenseFailClosedError(EquityRegistryError): ...     # production_required connector running without license

class EquityRegistryWarning(UserWarning):
    """Non-fatal warning; promoted to error only when --strict is set."""

class RestrictiveDefaultApplied(EquityRegistryWarning): ...
class ConfidenceDowngraded(EquityRegistryWarning): ...
class StaleSourceReference(EquityRegistryWarning): ...     # source published before record updated
class UnknownOptionalModuleReferenced(EquityRegistryWarning): ...   # AAT or similar referenced but not installed
class PITLatestOnlyNotBacktestSafe(EquityRegistryWarning): ...      # FRED / Kenneth French until ALFRED ships
```

Severity → action mapping:

| Severity | Default | `--strict` mode |
|---|---|---|
| `block` | raise `EquityRegistryError` subclass | unchanged |
| `error` | raise unless caller passes `tolerate_errors=True` | always raise |
| `warn` | emit `EquityRegistryWarning` subclass + log + LoadReport entry | promoted to error |
| `info` | LoadReport entry only | unchanged |

CLAUDE.md project-rule violations (`no_ticker_as_primary_key`, `pit_no_lookahead`, `rights_production_connector_fail_closed`, `package_no_monetized_endpoints`) are always `block`-severity and never tolerated — they raise even when `tolerate_errors=True`.

---

## 5. Test fixtures

Three categories:

### 5.1 Live artifact fixtures

The loaders, by default, read the live artifacts in `docs/equity_module/v0.1/registries/`. Tests that exercise the canonical, valid path use these files directly:

```python
def test_entity_registry_loads_canonical() -> None:
    registry = load_entity_registry()
    assert registry.require("equity_security").module_id == "viza.finance.equity_investment"
    assert "ticker" not in registry.require("equity_security").family_specific.immutable_keys
```

### 5.2 Crafted invalid records (negative cases)

Stored as JSON / CSV stubs under `tests/fixtures/equity_module/invalid_records/`. Each negative fixture is the smallest possible mutation of a valid record that exercises exactly one failure mode:

```text
invalid_records/
  entity_types_ticker_as_primary_key.json           <- triggers TickerAsPrimaryKeyError
  entity_types_missing_immutable_keys.json          <- triggers SchemaConformanceError
  node_types_unresolved_connector_role.json         <- triggers UnknownIdReferenceError
  attribute_unknown_license_policy_unblocked_export.csv  <- triggers RightsViolationError
  event_rumor_without_unverified_flag.json          <- triggers schema rule violation
  insight_profile_translation_unknown.json          <- triggers UnknownIdReferenceError
  profile_short_without_borrow_review.json          <- triggers schema rule violation
  output_view_recommendation_missing_non_advice.json <- triggers NonAdviceBoundaryMissingError
  validation_rule_missing_severity.json             <- triggers SchemaConformanceError
  connector_production_missing_license_unblocked.json <- triggers LicenseFailClosedError
  package_marketplace_draft_unredacted.json         <- triggers RightsViolationError
  manifest_artifact_sha_mismatch.json               <- triggers CrossReferenceError
```

### 5.3 Golden loader output snapshots

`tests/fixtures/equity_module/golden_runs/`:

```text
golden_runs/
  entity_registry.snapshot.json                     <- canonical loaded form (after restrictive defaults)
  node_registry.snapshot.json
  manifest_load_report.snapshot.json                <- LoadReport for the manifest load
```

Snapshot tests assert the canonical artifact loads into a stable, hashable representation. Regenerate via `pytest --snapshot-update` (using `syrupy` or equivalent).

### 5.4 Integration test: end-to-end module load

`tests/unit/test_equity_manifest.py`:

```python
def test_equity_module_loads_end_to_end() -> None:
    module = EquityModule.load(strict=True)
    assert module.entity_types.all_ids()
    assert module.profiles.require("quality_value_long_only")
    report = module.cross_reference.verify_all()
    assert report.errors == []
    assert module.manifest.artifact_checksums.combined_sha256 == report.computed_combined_sha256
```

---

## 6. Backward-compatibility behavior

The equity module is additive. Backward compatibility commitments:

| Surface | Commitment |
|---|---|
| `viza_graph_v0` | Unchanged. No node-palette primitive added to `viza.core.strategy`. Equity nodes extend the seven existing palette primitives (universe, attribute, transform, filter, score, relationship, output_radar). |
| `viza_attribute_registry_v1` | Unchanged. The current legacy registry continues to load; the new `viza.equity.attribute.v1` is a separate schema and registry that runs alongside. Promotion to v2 is out of scope. |
| Existing 303 Python unit/look-ahead tests | Must remain green. The plan adds new tests but does not modify existing test files. |
| 18 desktop helper tests | Unchanged. The desktop bridge is unaware of the equity sub-package unless explicitly wired. |
| `.viza` container format | Unchanged. Equity manifest is just another module manifest loaded by the existing module registry. |
| Manifest checksums | Unchanged at the container level. The new combined-sha256 in the equity manifest is in addition to, not in place of, existing manifest hashing. |
| Existing module loader (`viza/modules/registry.py`) | Augmented additively: `ModuleRegistry` learns one new `build_equity_investment_module()` call that constructs the `viza.finance.equity_investment` manifest object. Until that call is wired, the module remains discoverable only via direct import from `viza.equity`. |
| Unknown optional module references | Preserved verbatim. The loader records `UnknownOptionalModuleReferenced` warning but never deletes or rewrites the reference. (See §7.) |
| Schema version | `viza.equity.*.v1` is a fresh family-of-schemas. v1→v2 migration follows additive-by-default policy in `docs/VIZA_COMPATIBILITY_POLICY.md`. |
| File on-disk layout | `docs/equity_module/v0.1/` is purely additive. No existing `docs/` files are renamed or removed. |

A migration test pinned at `tests/unit/test_equity_compat.py` asserts that:

```python
def test_legacy_viza_attribute_registry_still_loads() -> None:
    from viza.attribute_registry import load_attribute_registry
    assert load_attribute_registry().schema_version == "viza_attribute_registry_v1"

def test_legacy_module_registry_still_loads() -> None:
    from viza.modules.registry import get_module_registry
    registry = get_module_registry()
    assert {m.module_id for m in registry.list_modules()} >= {"viza.core.strategy", "viza.finance.securities"}

def test_equity_module_load_does_not_mutate_legacy_state() -> None:
    legacy_before = load_attribute_registry().model_dump_json()
    EquityModule.load()
    legacy_after = load_attribute_registry().model_dump_json()
    assert legacy_before == legacy_after
```

---

## 7. Missing optional module behavior

Three classes of "missing":

### 7.1 Missing hard dependency

`viza.core.strategy` or `viza.finance.securities` missing → manifest loader raises `ModuleLoadBlockedError("hard dependency X not installed")`. The manifest's `depends_on[*].missing_behavior=block_module_load` is enforced. No registry is loaded. No graceful fallback.

### 7.2 Missing optional module (AAT)

`viza.aat.attribute_analysis` declared optional in the manifest with `missing_behavior=degrade_gracefully`. When AAT is not installed:

```python
class EquityModule:
    def load(self, ...) -> "EquityModule":
        manifest = load_manifest(...)
        registry = ModuleRegistry()  # existing viza/modules/registry.py
        for opt in manifest.optional_modules:
            if not registry.has_module(opt.module_id):
                warnings.warn(UnknownOptionalModuleReferenced(opt.module_id))
                # Mark dependent nodes/profiles as locked-but-preserved:
                for node in node_types.all():
                    if node.dependents_on_module(opt.module_id):
                        node.runtime_status = "open_locked_preserve_config"
                # Mark profiles that reference factor_attribution_node:
                for profile in profiles.all():
                    if profile.uses_factor_attribution():
                        profile.runtime_status = "open_locked_preserve_config"
                        profile.warnings.append(
                            f"AAT submodule missing; profile degrades to research-only "
                            f"and factor_residual_calculator emits warn-only signals."
                        )
        return self
```

Concretely, when AAT is missing:
- `factor_attribution_node` opens as a locked placeholder.
- `factor_residual_calculator` emits `pit_safe_label=unknown` + `confidence_label=research_supported_experimental` warnings.
- `factor_neutral_quantamental_selector` profile downgrades to `runtime_status=research_only` (still loadable, no production scoring).
- The unknown-module reference is preserved verbatim in the manifest and the load report.

### 7.3 Missing connector (license)

Per `missing_module_behavior.default_connector_behavior=fail_closed`: a connector requirement with `production_required=true` and `entitlement_metadata.license_status=missing` forces `rights.query_policy=blocked`. Dependent nodes:
- Stay registered (id resolves, config preserved).
- `family_specific.runtime_status = open_locked_preserve_config`.
- Any profile that requires the node downgrades to `research_only`.
- No silent fallback. Public-data fallback runs only when explicitly declared via `fallback_behavior` (e.g., `fall_back_to_delayed_eod_public_when_available`).

This is the literal `licensed_estimates_connector.family_specific.fallback_allowed=False`, `licensed_borrow_connector.family_specific.fallback_allowed=True` pattern.

---

## 8. Rights/PIT fail-closed behavior

Rights fail-closed flow:

```text
1. Loader reads record.
2. Schema validates: license_policy must be in the enum.
3. If license_policy ∈ {unknown, restricted_or_unclear}:
     a. Force export_policy ∈ {blocked, conditional}.
     b. Force marketplace_policy ∈ {redacted, blocked}.
     c. Force redaction_required=true.
     d. Emit RestrictiveDefaultApplied warning.
4. If license_policy=licensed_provider_required:
     a. Force redistribution_policy ∈ {blocked, conditional}.
     b. Force marketplace_policy ∈ {redacted, blocked, conditional}.
5. If license_policy=internal_research_only:
     a. Force export_policy=blocked, redistribution_policy=blocked, marketplace_policy=blocked.
6. If license_policy used by a production connector AND license_status=missing:
     a. Raise LicenseFailClosedError.
     b. The dependent node is marked open_locked_preserve_config.
     c. Dependent profiles downgrade to research_only.
```

PIT fail-closed flow:

```text
1. Loader reads record.
2. Schema validates: PIT block is complete.
3. If data_version_policy=unknown OR available_at_policy=unknown:
     a. Force vintage_required=true.
     b. Force lookahead_risk=high.
4. If record family ∈ {attribute, event_type, insight_type, connector_requirement, pit_policy}:
     a. observed_at_policy != not_applicable AND available_at_policy != not_applicable.
5. If record references FRED current data OR Kenneth French current data:
     a. Force pit_safe_label=latest_only.
     b. Emit PITLatestOnlyNotBacktestSafe warning.
     c. Any backtest path that consumes the attribute raises PITViolationError unless explicit not_backtest_safe label.
6. If 13F-derived attribute used:
     a. Validation rule filing_13f_data_must_not_be_used_as_current_positioning enforced.
     b. Treating 13F as current raises PITViolationError.
7. If short_interest interpolated:
     a. Validation rule short_interest_uses_publication_date_for_available_at enforced.
     b. Interpolation raises PITViolationError.
```

All fail-closed raises propagate up to the loader's caller. The loader never silently substitutes a less-restrictive policy.

---

## 9. Patch plan

Sequenced, additive only. Each step adds files; no existing file is modified except the explicit additive edits in the final step.

### Phase 0 — scaffold (Day 0, 1–2 hours)

```text
[A] Create viza/equity/__init__.py with:
      VIZA_EQUITY_MODULE_ID = "viza.finance.equity_investment"
      VIZA_EQUITY_MODULE_VERSION = "0.1.0"
      and re-exports of load_entity_registry, …, EquityModule.

[A] Create viza/equity/errors.py with the exception hierarchy in §4.

[A] Create viza/equity/types.py with shared type aliases (PITPolicy, RightsPolicy, ConfidenceLabel, etc.).

[A] Add viza/equity/source_corpus.py: trivial lookup keyed by source_id; the
    initial table is the union of source_ids cited by the artifacts. Lookup misses
    return StaleSourceReference warnings, not errors.

[T] Add tests/unit/test_equity_errors.py and tests/unit/test_equity_source_corpus.py.

[V] Verify: existing 303 Python tests + 18 desktop tests still green.
```

### Phase 1 — schema-conformant loaders (Day 1–3, ~12 hours)

```text
[A] Add viza/equity/entity_registry.py: load_entity_registry(artifact_dir=None) -> EntityTypeRegistry.
      Uses jsonschema.Draft202012Validator(shared_schema).iter_errors(record) to
      validate each record's oneOf branch.
[T] Add tests/unit/test_equity_entity_registry.py covering canonical load + 3 negative cases (missing immutable_keys, ticker as primary key, unknown identifier).

Repeat the pattern for each of the 10 loaders:
[A] viza/equity/node_type_registry.py
[A] viza/equity/edge_type_registry.py
[A] viza/equity/attribute_registry.py
[A] viza/equity/event_registry.py
[A] viza/equity/insight_registry.py
[A] viza/equity/strategy_profile_registry.py
[A] viza/equity/output_view_registry.py
[A] viza/equity/validation_rule_registry.py
[A] viza/equity/connector_requirement_registry.py
[A] viza/equity/rights_matrix.py
[A] viza/equity/pit_matrix.py
[T] One unit test file per loader.

[V] Re-run python -m pytest tests\unit tests\lookahead_audit (must remain green).
```

### Phase 2 — cross-reference + validators (Day 3–5, ~12 hours)

```text
[A] Add viza/equity/cross_reference.py implementing every check in §3.2.
[A] Add viza/equity/pit_validator.py + viza/equity/rights_validator.py.
[A] Add viza/equity/validation_engine.py that runs the 43 validation rules from equity_validation_rules.json.
[T] tests/unit/test_equity_cross_reference.py — every check in §3.2, both positive and negative fixtures.
[T] tests/unit/test_equity_pit_validator.py — 13F lag, vintage required, no lookahead.
[T] tests/unit/test_equity_rights_validator.py — fail-closed, redaction, package mode.
[T] tests/unit/test_equity_ticker_never_primary_key.py.
[T] tests/unit/test_equity_marketplace_draft_redaction.py.
[T] tests/unit/test_equity_non_advice_boundary.py.
[T] tests/unit/test_equity_human_review_gate.py.

[V] All new tests pass; existing tests remain green.
```

### Phase 3 — manifest + module facade (Day 5–6, ~6 hours)

```text
[A] Add viza/equity/manifest.py: load_equity_manifest(...) -> EquityModuleManifest
    that also verifies registry_artifacts SHA-256s + combined_sha256 + reads the
    shared metadata contract sha256.
[A] Add EquityModule facade in viza/equity/__init__.py that orchestrates all 12
    loaders and the cross-reference engine. Exposes:
      EquityModule.load(strict=False) -> EquityModule
      module.cross_reference.verify_all() -> CrossReferenceReport
[T] tests/unit/test_equity_manifest.py — checksum verification, hard-dependency block,
    optional-module degrade, artifact path resolution.
[T] tests/unit/test_equity_compat.py — legacy compatibility (see §6).
[T] tests/unit/test_equity_fail_closed.py — license missing fail-closed, PIT lookahead fail-closed.
[T] tests/unit/test_equity_missing_optional_module.py — AAT-missing → degrade_gracefully.

[V] All tests green; manifest loads end-to-end with combined sha256 match.
```

### Phase 4 — registry integration (Day 6, ~3 hours)

```text
[E] Edit viza/modules/registry.py additively: import build_equity_investment_module
    from viza.equity.manifest; append the module to the loaded_modules list.
    The edit is two lines plus an import. No legacy behavior is changed.
[E] Edit viza/modules/__init__.py to re-export EquityModule for discoverability.
[E] Edit viza/config_paths.py to add equity_module_dir() helper. The existing
    REQUIRED_CONFIG_FILES tuple is unchanged; equity_module is loaded from
    docs/equity_module/v0.1/registries/ (config-relative path) but never required
    for the existing engine to start.
[T] tests/unit/test_viza_modules.py picks up the new module automatically; one
    assertion added that "viza.finance.equity_investment" is in the listed modules.

[V] Full Python + lookahead test suite green. Desktop suite unchanged. Windows
    package smoke + packaged sidecar API smoke remain green per
    docs/VIZA_PACKAGING.md.
```

### Phase 5 — golden-run snapshot + fail-closed regression (Day 7, ~3 hours)

```text
[A] Add tests/fixtures/equity_module/golden_runs/*.snapshot.json
    (regenerable via pytest --snapshot-update).
[A] Add tests/fixtures/equity_module/invalid_records/ with the 12 crafted
    invalid records listed in §5.2.
[T] tests/unit/test_equity_golden_runs.py — snapshot diff per loader.
[T] tests/unit/test_equity_invalid_records.py — every invalid record raises
    the expected error subclass.

[V] Full Python + lookahead + desktop suite green.
```

### Patch order summary

```
A = add (new file)
E = edit (existing file, additive)
T = test
V = verify

Phase 0: A errors.py | A types.py | A source_corpus.py | T x2 | V
Phase 1: A x12 loaders | T x12 | V
Phase 2: A cross_reference | A pit_validator | A rights_validator | A validation_engine | T x7 | V
Phase 3: A manifest.py | A EquityModule facade | T x4 | V
Phase 4: E modules/registry.py | E modules/__init__.py | E config_paths.py | T patch | V
Phase 5: A golden_runs | A invalid_records | T x2 | V
```

Total: ~38 new files (loaders + tests + fixtures) + 3 additive edits to existing files. The diff to the running engine is restricted to Phase 4's three tiny edits.

---

## 10. Candidate code skeletons

### 10.1 `viza/equity/__init__.py`

```python
"""viza.finance.equity_investment module facade."""

from __future__ import annotations

from viza.equity.attribute_registry import EquityAttributeRegistry, load_attribute_registry
from viza.equity.connector_requirement_registry import (
    ConnectorRequirementRegistry,
    load_connector_requirement_registry,
)
from viza.equity.cross_reference import CrossReferenceEngine, CrossReferenceReport
from viza.equity.edge_type_registry import EdgeTypeRegistry, load_edge_type_registry
from viza.equity.entity_registry import EntityTypeRegistry, load_entity_registry
from viza.equity.errors import (
    CrossReferenceError,
    EquityRegistryError,
    LicenseFailClosedError,
    NonAdviceBoundaryMissingError,
    PITViolationError,
    RightsViolationError,
    TickerAsPrimaryKeyError,
)
from viza.equity.event_registry import EventTypeRegistry, load_event_registry
from viza.equity.insight_registry import InsightTypeRegistry, load_insight_registry
from viza.equity.manifest import EquityModuleManifest, load_equity_manifest
from viza.equity.node_type_registry import NodeTypeRegistry, load_node_type_registry
from viza.equity.output_view_registry import OutputViewRegistry, load_output_view_registry
from viza.equity.pit_matrix import PITMatrix, load_pit_matrix
from viza.equity.rights_matrix import RightsMatrix, load_rights_matrix
from viza.equity.strategy_profile_registry import (
    StrategyProfileRegistry,
    load_strategy_profile_registry,
)
from viza.equity.validation_rule_registry import (
    ValidationRuleRegistry,
    load_validation_rule_registry,
)

VIZA_EQUITY_MODULE_ID = "viza.finance.equity_investment"
VIZA_EQUITY_MODULE_VERSION = "0.1.0"


class EquityModule:
    """Single facade over all 12 registries + manifest + cross-reference engine."""

    def __init__(
        self,
        manifest: EquityModuleManifest,
        entity_types: EntityTypeRegistry,
        node_types: NodeTypeRegistry,
        edge_types: EdgeTypeRegistry,
        attributes: EquityAttributeRegistry,
        events: EventTypeRegistry,
        insights: InsightTypeRegistry,
        profiles: StrategyProfileRegistry,
        output_views: OutputViewRegistry,
        validation_rules: ValidationRuleRegistry,
        connectors: ConnectorRequirementRegistry,
        rights_matrix: RightsMatrix,
        pit_matrix: PITMatrix,
    ) -> None:
        self.manifest = manifest
        self.entity_types = entity_types
        self.node_types = node_types
        self.edge_types = edge_types
        self.attributes = attributes
        self.events = events
        self.insights = insights
        self.profiles = profiles
        self.output_views = output_views
        self.validation_rules = validation_rules
        self.connectors = connectors
        self.rights_matrix = rights_matrix
        self.pit_matrix = pit_matrix
        self.cross_reference = CrossReferenceEngine(self)

    @classmethod
    def load(
        cls,
        *,
        artifact_dir=None,
        strict: bool = False,
    ) -> "EquityModule":
        manifest = load_equity_manifest(artifact_dir=artifact_dir, strict=strict)
        return cls(
            manifest=manifest,
            entity_types=load_entity_registry(artifact_dir=artifact_dir, strict=strict),
            node_types=load_node_type_registry(artifact_dir=artifact_dir, strict=strict),
            edge_types=load_edge_type_registry(artifact_dir=artifact_dir, strict=strict),
            attributes=load_attribute_registry(artifact_dir=artifact_dir, strict=strict),
            events=load_event_registry(artifact_dir=artifact_dir, strict=strict),
            insights=load_insight_registry(artifact_dir=artifact_dir, strict=strict),
            profiles=load_strategy_profile_registry(artifact_dir=artifact_dir, strict=strict),
            output_views=load_output_view_registry(artifact_dir=artifact_dir, strict=strict),
            validation_rules=load_validation_rule_registry(artifact_dir=artifact_dir, strict=strict),
            connectors=load_connector_requirement_registry(artifact_dir=artifact_dir, strict=strict),
            rights_matrix=load_rights_matrix(artifact_dir=artifact_dir, strict=strict),
            pit_matrix=load_pit_matrix(artifact_dir=artifact_dir, strict=strict),
        )
```

### 10.2 `viza/equity/entity_registry.py` (representative loader)

```python
"""Loader for equity_entity_types.json (viza.equity.entity_registry.v1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import BaseModel, ConfigDict, Field

from viza.equity.errors import (
    RecordRejectedError,
    SchemaConformanceError,
    TickerAsPrimaryKeyError,
)
from viza.equity.types import LoadReport, RestrictiveDefaultApplication, RightsBlock, PITBlock


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs/equity_module/v0.1/equity_registry_shared_metadata.schema.json"
DEFAULT_ARTIFACT = Path(__file__).resolve().parents[2] / "docs/equity_module/v0.1/registries/equity_entity_types.json"


class EntityTypeFamilySpecific(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifiers: list[str]
    immutable_keys: list[str]
    relationship_types_outgoing: list[str] = Field(default_factory=list)
    lifecycle_states: list[str] = Field(default_factory=list)


class EntityType(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    display_name: str
    description: str
    module_id: str
    schema_version: str
    object_family: str
    source_sections: list[str]
    source_ids: list[str]
    confidence_label: str
    status: str
    created_from: str
    core_primitive: str
    extends_core_primitive: str | None = None
    compatible_entity_types: list[str]
    compatible_strategy_profiles: list[str]
    candidate_node_types: list[str] = Field(default_factory=list)
    candidate_attribute_keys: list[str] = Field(default_factory=list)
    candidate_event_types: list[str] = Field(default_factory=list)
    candidate_insight_types: list[str] = Field(default_factory=list)
    output_views: list[str] = Field(default_factory=list)
    evidence_requirements: list[dict[str, Any]]
    audit_requirements: list[str]
    source_quality_minimum: int
    human_review_required: bool
    pit: PITBlock
    rights: RightsBlock
    validation_rules: list[str]
    failure_modes: list[str]
    downgrade_conditions: list[dict[str, Any]]
    rejection_conditions: list[str]
    family_specific: EntityTypeFamilySpecific


@dataclass(slots=True)
class EntityTypeRegistry:
    records: dict[str, EntityType] = field(default_factory=dict)
    load_report: LoadReport | None = None

    def get(self, id: str) -> EntityType | None:
        return self.records.get(id)

    def require(self, id: str) -> EntityType:
        try:
            return self.records[id]
        except KeyError as exc:
            raise KeyError(f"unknown equity entity_type id: {id}") from exc

    def by_family(self, family: str) -> list[EntityType]:
        return [r for r in self.records.values() if family in r.family_specific.identifiers]

    def all_ids(self) -> list[str]:
        return list(self.records)


def load_entity_registry(
    artifact_dir: Path | None = None,
    *,
    strict: bool = False,
) -> EntityTypeRegistry:
    artifact = (artifact_dir / "equity_entity_types.json") if artifact_dir else DEFAULT_ARTIFACT
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    raw = json.loads(artifact.read_text(encoding="utf-8"))

    records: dict[str, EntityType] = {}
    rejections = []
    warnings_log = []
    defaults_log: list[RestrictiveDefaultApplication] = []

    for raw_rec in raw["records"]:
        errors = sorted(validator.iter_errors(raw_rec), key=lambda e: list(e.absolute_path))
        if errors:
            err = SchemaConformanceError(
                f"entity_type {raw_rec.get('id')} fails schema: {errors[0].message[:200]}"
            )
            err.artifact_file = artifact
            err.record_id = raw_rec.get("id")
            err.remediation = "Fix the record to match the strict shared metadata contract."
            if strict:
                raise err
            rejections.append(err)
            continue

        # CLAUDE.md project rule: no ticker as primary key
        fs = raw_rec["family_specific"]
        if "ticker" in fs["immutable_keys"]:
            err = TickerAsPrimaryKeyError(
                f"entity_type {raw_rec['id']} has ticker in immutable_keys (CLAUDE.md violation)."
            )
            err.artifact_file = artifact
            err.record_id = raw_rec["id"]
            err.remediation = "Use immutable security_id / company_id / share_class_id as primary keys."
            raise err  # always raises, even in non-strict

        # Restrictive defaults (rights)
        rights = raw_rec["rights"]
        if rights["license_policy"] in {"unknown", "restricted_or_unclear"}:
            for field_name, allowed in (
                ("export_policy", {"blocked", "conditional"}),
                ("marketplace_policy", {"redacted", "blocked"}),
                ("redistribution_policy", {"blocked", "conditional"}),
            ):
                if rights[field_name] not in allowed:
                    defaults_log.append(
                        RestrictiveDefaultApplication(
                            record_id=raw_rec["id"],
                            field=f"rights.{field_name}",
                            from_value=rights[field_name],
                            to_value=sorted(allowed)[0],
                            reason="license_unknown_or_restricted",
                        )
                    )
                    rights[field_name] = sorted(allowed)[0]
            if not rights.get("redaction_required", True):
                rights["redaction_required"] = True

        records[raw_rec["id"]] = EntityType.model_validate(raw_rec)

    registry = EntityTypeRegistry(records=records)
    registry.load_report = LoadReport(
        artifact_file=str(artifact),
        records_loaded=len(records),
        records_rejected=len(rejections),
        warnings=warnings_log,
        downgrades=[],
        restrictive_defaults_applied=defaults_log,
        duration_ms=0.0,
        loaded_at=datetime.utcnow(),
    )
    return registry
```

The other 9 loaders follow the same template (read JSON / CSV, run schema validator, apply restrictive defaults, instantiate Pydantic model, return container). Only the Pydantic model and the per-family invariants vary.

### 10.3 `viza/equity/cross_reference.py` (skeleton)

```python
"""Cross-artifact validators for the equity module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from viza.equity.errors import (
    CrossReferenceError,
    NonAdviceBoundaryMissingError,
    RightsViolationError,
    UnknownIdReferenceError,
)

if TYPE_CHECKING:
    from viza.equity import EquityModule


@dataclass
class CrossReferenceCheckResult:
    check_id: str
    passed: bool
    severity: str  # info | warn | error | block
    message: str
    record_ids: list[str] = field(default_factory=list)


@dataclass
class CrossReferenceReport:
    results: list[CrossReferenceCheckResult] = field(default_factory=list)
    @property
    def errors(self) -> list[CrossReferenceCheckResult]:
        return [r for r in self.results if not r.passed and r.severity in {"error", "block"}]
    @property
    def warnings(self) -> list[CrossReferenceCheckResult]:
        return [r for r in self.results if not r.passed and r.severity == "warn"]


class CrossReferenceEngine:
    def __init__(self, module: "EquityModule") -> None:
        self.module = module

    def verify_all(self, *, raise_first_error: bool = False) -> CrossReferenceReport:
        report = CrossReferenceReport()
        checks = [
            self._check_insight_to_profile,
            self._check_profile_to_output_view,
            self._check_node_connector_roles,
            self._check_marketplace_draft_redaction,
            self._check_non_advice_boundary,
            self._check_output_view_rights_redaction_rules,
            self._check_no_ticker_as_primary_key,
            self._check_pit_on_observation_bearing,
            self._check_rights_on_data_dependent,
            self._check_manifest_arrays_match_registries,
            self._check_combined_artifact_checksum,
            self._check_package_visibility_compatible_with_rights,
            self._check_human_review_gates_attached,
        ]
        for check in checks:
            result = check()
            report.results.append(result)
            if raise_first_error and not result.passed and result.severity in {"error", "block"}:
                raise CrossReferenceError(result.message)
        return report

    def _check_insight_to_profile(self) -> CrossReferenceCheckResult:
        profile_ids = set(self.module.profiles.all_ids())
        orphans = []
        for insight in self.module.insights.records.values():
            referenced = {
                p["profile_id"]
                for p in insight.family_specific.translation_rules["per_profile_translation"]
            }
            if not (referenced & profile_ids):
                orphans.append(insight.id)
        return CrossReferenceCheckResult(
            check_id="insight_to_profile",
            passed=not orphans,
            severity="error",
            message=(
                f"{len(orphans)} insights orphaned from profiles" if orphans else "all insights map to >= 1 profile"
            ),
            record_ids=orphans,
        )

    # ... remaining 12 checks follow the same pattern ...
```

### 10.4 `viza/equity/manifest.py` (skeleton)

```python
"""Manifest loader + checksum verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from viza.equity.errors import CrossReferenceError


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs/equity_module/v0.1/viza.module.manifest.v1.schema.json"
DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / "docs/equity_module/v0.1/viza.finance.equity_investment.manifest.json"


@dataclass
class EquityModuleManifest:
    raw: dict[str, Any]

    @property
    def module_id(self) -> str:
        return self.raw["module_id"]

    @property
    def module_version(self) -> str:
        return self.raw["module_version"]

    @property
    def release_state(self) -> str:
        return self.raw["release_state"]

    @property
    def baseline_reference(self) -> str:
        return self.raw["baseline_reference"]

    @property
    def artifact_files(self) -> dict[str, Path]:
        out = {}
        base = DEFAULT_MANIFEST.parent
        for key, art in self.raw["registry_artifacts"].items():
            out[key] = base / art["path"]
        return out

    @property
    def combined_sha256(self) -> str:
        return self.raw["artifact_checksums"]["combined_sha256"]


def load_equity_manifest(
    artifact_dir: Path | None = None,
    *,
    strict: bool = False,
) -> EquityModuleManifest:
    manifest_path = (artifact_dir / "viza.finance.equity_investment.manifest.json") if artifact_dir else DEFAULT_MANIFEST
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(raw),
        key=lambda e: list(e.absolute_path),
    )
    if errors:
        raise CrossReferenceError(f"manifest fails schema: {errors[0].message[:200]}")
    # Verify artifact checksums
    combined = hashlib.sha256()
    base = manifest_path.parent
    for key, art in raw["registry_artifacts"].items():
        artifact_path = base / art["path"]
        if not artifact_path.exists():
            raise CrossReferenceError(f"artifact {key} -> {art['path']} not found")
        h = hashlib.sha256()
        with artifact_path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if actual != art["sha256"]:
            raise CrossReferenceError(
                f"artifact {key} sha256 mismatch: manifest says {art['sha256'][:16]}..., disk is {actual[:16]}..."
            )
        combined.update(art["sha256"].encode("utf-8"))
    if combined.hexdigest() != raw["artifact_checksums"]["combined_sha256"]:
        raise CrossReferenceError("combined_sha256 mismatch")
    return EquityModuleManifest(raw=raw)
```

### 10.5 Representative test (Phase 2)

`tests/unit/test_equity_marketplace_draft_redaction.py`:

```python
import json
from pathlib import Path

import pytest

from viza.equity import EquityModule
from viza.equity.errors import RightsViolationError


@pytest.fixture
def invalid_unredacted_package(tmp_path):
    # Crafted invalid record where marketplace_draft package contains
    # an unredacted restricted_or_unclear evidence
    src = Path(__file__).parent.parent / "fixtures/equity_module/invalid_records/package_marketplace_draft_unredacted.json"
    dest = tmp_path / "registries" / "equity_event_registry_seed.json"
    dest.parent.mkdir()
    dest.write_text(src.read_text(encoding="utf-8"))
    return tmp_path


def test_canonical_marketplace_draft_redaction_holds() -> None:
    module = EquityModule.load(strict=True)
    report = module.cross_reference.verify_all()
    redaction_check = [r for r in report.results if r.check_id == "marketplace_draft_redaction"][0]
    assert redaction_check.passed


def test_unredacted_restricted_in_marketplace_draft_raises(invalid_unredacted_package: Path) -> None:
    with pytest.raises(RightsViolationError):
        EquityModule.load(artifact_dir=invalid_unredacted_package, strict=True)
```

---

## 11. Acceptance criteria mapping

| Acceptance criterion | Implementation reference |
|---|---|
| Loader fails closed on schema errors | Each loader runs `Draft202012Validator(schema).iter_errors(record)`; on first error raises `SchemaConformanceError` in `strict=True`, otherwise rejects the record and emits a `LoadReport` rejection. (§§2, 10.2) |
| Loader preserves unknown optional module references | `EquityModule.load` keeps the manifest's `optional_modules` list verbatim; when the referenced module is not installed, emits `UnknownOptionalModuleReferenced` warning but never deletes the reference. (§7.2) |
| Tests cover valid + invalid artifacts | §5.2 lists 12 crafted invalid records; §5.4 covers end-to-end; phase 1–5 patch plan creates one test file per loader plus cross-reference + fail-closed + missing-module + golden-run tests. |
| Existing Python, look-ahead, and desktop tests remain green | Phase 0–5 is additive only. Phase 4's 3 additive edits to `viza/modules/registry.py`, `viza/modules/__init__.py`, `viza/config_paths.py` are surgical and covered by phase-level verification gates. (§§6, 9) |
| Engineering plan + code skeletons | This document + §§10.1–10.5 skeletons. |

---

## 12. Open questions deferred to engineering

1. Should the loader read artifacts from `docs/equity_module/v0.1/registries/` or copy them to `config/equity_module/v0.1/registries/` at packaging time? Recommendation: copy to `config/` for the packaged engine (consistent with [viza/config_paths.py](../../../viza/config_paths.py)); leave docs-relative loading for development.
2. Should `viza/modules/registry.py` lazy-load the equity module or eager-load? Recommendation: eager-load, mirroring `build_finance_securities_module()`; the equity module's load_report is exposed via `/viza/diagnostics`.
3. Should validation rule severities be configurable per-environment (e.g., dev vs production)? Recommendation: yes — read `VIZA_VALIDATION_PROFILE` env var with values `dev` / `staging` / `production`; production maps `warn`→`error`.
4. Should `EquityModule.load()` accept a `module_overrides` dict for testing? Recommendation: yes — already factored into the constructor; `load()` is the convenience wrapper.

---

**End of IMPLEMENTATION_PLAN_LOADERS.md.**

Status: registry-seedable engineering plan. Promotion to `implementation_ready` requires (a) Phase 0 scaffolding merged, (b) Phase 1 loaders + tests merged, (c) full Python + look-ahead + desktop suite green per [docs/PROJECT_STATUS.md](../../PROJECT_STATUS.md), (d) packaged-sidecar smoke test green per [docs/VIZA_PACKAGING.md](../../VIZA_PACKAGING.md).
