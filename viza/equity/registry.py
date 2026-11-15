from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal


EQUITY_MODULE_ID = "viza.finance.equity_investment"
EQUITY_MODULE_VERSION = "0.1.0"

REPO_ROOT = Path(os.getenv("VIZA_ENGINE_ROOT") or Path(__file__).resolve().parents[2])
DEFAULT_EQUITY_MODULE_DIR = REPO_ROOT / "docs" / "equity_module" / "v0.1"
DEFAULT_EQUITY_REGISTRIES_DIR = DEFAULT_EQUITY_MODULE_DIR / "registries"

SchemaState = Literal["pass", "warn", "block"]
PackageMode = Literal[
    "white_box",
    "gray_box",
    "black_box",
    "output_only",
    "preview",
    "marketplace_draft",
]

JSON_ARTIFACTS: dict[str, tuple[str, str]] = {
    "entity_types": ("equity_entity_types.json", "entity_type"),
    "edge_types": ("equity_edge_types.json", "edge_type"),
    "node_types": ("equity_node_types.json", "node_type"),
    "event_types": ("equity_event_registry_seed.json", "event_type"),
    "insight_types": ("equity_insight_registry_seed.json", "insight_type"),
    "strategy_profiles": ("equity_strategy_profiles.json", "strategy_profile"),
    "output_views": ("equity_output_views.json", "output_view"),
    "validation_rules": ("equity_validation_rules.json", "validation_rule"),
    "connector_requirements": ("equity_connector_requirements.json", "connector_requirement"),
}

CSV_ARTIFACTS: dict[str, tuple[str, str]] = {
    "attributes": ("equity_attribute_registry_seed.csv", "key"),
    "rights_matrix": ("equity_source_rights_matrix.csv", "data_type"),
    "pit_matrix": ("equity_PIT_matrix.csv", "data_type"),
}

OPTIONAL_CSV_ARTIFACTS: dict[str, tuple[str, str]] = {
    "research_traceability_matrix": ("equity_research_traceability_matrix.csv", "artifact_or_object_id"),
    "rejection_and_downgrade_log": ("equity_rejection_and_downgrade_log.csv", "object_id"),
}

VALID_CONFIDENCE_LABELS = {
    "high_confidence_core",
    "common_practice",
    "research_supported_experimental",
    "practitioner_observed",
    "speculative_or_low_confidence",
    "rejected_or_deferred",
}

RECOMMENDATION_LIKE_OUTPUTS = {
    "equity_radar",
    "investment_memo",
    "trade_plan",
    "risk_dashboard",
    "portfolio_impact_report",
}

OBSERVATION_BEARING_ARTIFACTS = {
    "node_types",
    "event_types",
    "insight_types",
    "strategy_profiles",
    "output_views",
    "connector_requirements",
}

CONNECTOR_ROLE_ALIASES = {
    "analyst_estimates": "licensed_estimates_connector",
    "analyst_ratings": "licensed_estimates_connector",
    "attention_data": "licensed_text_connector",
    "borrow_availability_cost": "licensed_borrow_connector",
    "company_press_releases": "official_public_connector",
    "corporate_actions": "official_public_connector",
    "earnings_releases": "sec_filings",
    "edgar_filings_intake": "sec_filings",
    "factor_data": "derived_calculation_engine",
    "fund_flows": "licensed_market_data_connector",
    "fundamentals_as_reported": "xbrl_facts",
    "fundamentals_standardized": "licensed_fundamentals_connector",
    "identifier_mapping": "official_public_connector",
    "index_membership": "licensed_index_membership_connector",
    "insider_transactions": "sec_filings",
    "macro_official": "fred_macro",
    "news_events": "licensed_text_connector",
    "options": "licensed_options_connector",
    "ownership_filings": "sec_filings",
    "prices_ohlcv": "licensed_market_data_connector",
    "credit_data": "fred_macro",
    "macro_provider": "fred_macro",
    "risk_model_factors": "derived_calculation_engine",
    "security_master": "official_public_connector",
    "short_interest": "finra_short_interest",
    "social_data": "licensed_text_connector",
    "transcripts": "licensed_text_connector",
}


class EquityRegistryError(ValueError):
    """Raised when the equity registry cannot be loaded or validated."""


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: SchemaState
    artifact: str
    message: str
    record_id: str | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(
        self,
        code: str,
        severity: SchemaState,
        artifact: str,
        message: str,
        record_id: str | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                severity=severity,
                artifact=artifact,
                message=message,
                record_id=record_id,
            )
        )

    @property
    def status(self) -> SchemaState:
        if any(issue.severity == "block" for issue in self.issues):
            return "block"
        if any(issue.severity == "warn" for issue in self.issues):
            return "warn"
        return "pass"

    def counts(self) -> dict[str, int]:
        counts = {"pass": 0, "warn": 0, "block": 0}
        counts[self.status] += 1
        for issue in self.issues:
            counts[issue.severity] += 1
        return counts

    def require_pass(self) -> None:
        if self.status != "pass":
            details = "; ".join(
                f"{issue.severity}:{issue.code}:{issue.artifact}:{issue.record_id or '-'}"
                for issue in self.issues[:12]
            )
            raise EquityRegistryError(f"equity registry validation did not pass: {details}")


@dataclass(frozen=True)
class RegistryArtifact:
    name: str
    path: Path
    records: list[dict[str, Any]]
    id_field: str
    expected_family: str | None = None

    @property
    def sha256(self) -> str:
        return _sha256_file(self.path)

    @property
    def record_count(self) -> int:
        return len(self.records)

    def ids(self) -> list[str]:
        return [str(record.get(self.id_field, "")) for record in self.records]

    def id_set(self) -> set[str]:
        return set(self.ids())

    def get(self, record_id: str) -> dict[str, Any] | None:
        return next((record for record in self.records if record.get(self.id_field) == record_id), None)

    def require(self, record_id: str) -> dict[str, Any]:
        record = self.get(record_id)
        if record is None:
            raise KeyError(f"unknown equity {self.name} record: {record_id}")
        return record


@dataclass(frozen=True)
class PackageDecision:
    included: bool
    redacted: bool
    blocked: bool
    entitlement_locked: bool
    reason: str


@dataclass
class EquityModule:
    artifact_dir: Path
    module_dir: Path
    manifest: dict[str, Any]
    artifacts: dict[str, RegistryArtifact]

    def artifact(self, name: str) -> RegistryArtifact:
        if name not in self.artifacts:
            raise KeyError(f"unknown equity artifact: {name}")
        return self.artifacts[name]

    def validate(self) -> ValidationReport:
        report = ValidationReport()
        self._validate_manifest(report)
        self._validate_unique_ids(report)
        self._validate_required_metadata(report)
        self._validate_cross_references(report)
        self._validate_pit_and_rights(report)
        self._validate_output_redaction(report)
        self._validate_human_review_gates(report)
        return report

    def package_decision(
        self,
        *,
        license_policy: str,
        package_mode: PackageMode,
        raw_provider_data: bool = False,
        user_private: bool = False,
        rights_unknown: bool = False,
        entitlement_present: bool = False,
    ) -> PackageDecision:
        if rights_unknown or license_policy in {"unknown", "restricted_or_unclear"}:
            return PackageDecision(
                included=False,
                redacted=True,
                blocked=True,
                entitlement_locked=False,
                reason="unknown or restricted rights block export and marketplace packaging",
            )
        if raw_provider_data and package_mode in {"output_only", "marketplace_draft"}:
            return PackageDecision(
                included=False,
                redacted=True,
                blocked=package_mode == "marketplace_draft",
                entitlement_locked=False,
                reason="raw provider data is not bundled in output-only or marketplace draft packages",
            )
        if license_policy == "licensed_provider_required":
            if not entitlement_present:
                return PackageDecision(
                    included=False,
                    redacted=package_mode in {"output_only", "preview", "marketplace_draft"},
                    blocked=False,
                    entitlement_locked=True,
                    reason="licensed data is entitlement-locked when connector entitlement is absent",
                )
            return PackageDecision(
                included=package_mode == "white_box",
                redacted=package_mode != "white_box",
                blocked=False,
                entitlement_locked=False,
                reason="licensed entitlement present; raw redistribution remains restricted",
            )
        if user_private or license_policy == "internal_research_only":
            if package_mode == "white_box":
                return PackageDecision(
                    included=True,
                    redacted=False,
                    blocked=False,
                    entitlement_locked=False,
                    reason="creator-local white-box package may include user-private data",
                )
            return PackageDecision(
                included=False,
                redacted=True,
                blocked=package_mode == "marketplace_draft",
                entitlement_locked=False,
                reason="user-private/internal research data is redacted or blocked outside creator-local mode",
            )
        if license_policy in {"public_official", "public_professional", "academic_public", "derived_only"}:
            return PackageDecision(
                included=True,
                redacted=False,
                blocked=False,
                entitlement_locked=False,
                reason="public or derived data may be packaged with attribution and policy checks",
            )
        return PackageDecision(
            included=False,
            redacted=True,
            blocked=True,
            entitlement_locked=False,
            reason=f"unrecognized license policy fails closed: {license_policy}",
        )

    def _validate_manifest(self, report: ValidationReport) -> None:
        if self.manifest.get("module_id") != EQUITY_MODULE_ID:
            report.add(
                "manifest_module_id",
                "block",
                "manifest",
                f"manifest module_id must be {EQUITY_MODULE_ID}",
            )
        if self.manifest.get("module_version") != EQUITY_MODULE_VERSION:
            report.add(
                "manifest_module_version",
                "block",
                "manifest",
                f"manifest module_version must be {EQUITY_MODULE_VERSION}",
            )
        required_modes = {
            "white_box",
            "gray_box",
            "black_box",
            "output_only",
            "preview",
            "marketplace_draft",
        }
        actual_modes = set(self.manifest.get("package_visibility_modes", []))
        missing_modes = required_modes - actual_modes
        if missing_modes:
            report.add(
                "manifest_package_modes",
                "block",
                "manifest",
                f"missing package visibility modes: {sorted(missing_modes)}",
            )

    def _validate_unique_ids(self, report: ValidationReport) -> None:
        for artifact in self.artifacts.values():
            if artifact.name in OPTIONAL_CSV_ARTIFACTS and all(
                not record.get(artifact.id_field) for record in artifact.records
            ):
                continue
            ids = artifact.ids()
            if any(not record_id for record_id in ids):
                report.add(
                    "id_required",
                    "block",
                    artifact.name,
                    f"all records require {artifact.id_field}",
                )
            duplicates = sorted({record_id for record_id in ids if ids.count(record_id) > 1})
            if duplicates:
                report.add(
                    "unique_ids",
                    "block",
                    artifact.name,
                    f"duplicate record IDs: {duplicates[:10]}",
                )

    def _validate_required_metadata(self, report: ValidationReport) -> None:
        for artifact in self._json_artifacts():
            for record in artifact.records:
                record_id = str(record.get("id", ""))
                if record.get("object_family") != artifact.expected_family:
                    report.add(
                        "object_family_matches_artifact",
                        "block",
                        artifact.name,
                        f"expected {artifact.expected_family}, got {record.get('object_family')}",
                        record_id,
                    )
                if record.get("module_id") != EQUITY_MODULE_ID:
                    report.add(
                        "module_id_required",
                        "block",
                        artifact.name,
                        f"module_id must be {EQUITY_MODULE_ID}",
                        record_id,
                    )
                if record.get("confidence_label") not in VALID_CONFIDENCE_LABELS:
                    report.add(
                        "valid_confidence_label",
                        "block",
                        artifact.name,
                        f"invalid confidence_label={record.get('confidence_label')!r}",
                        record_id,
                    )
                if not record.get("source_sections"):
                    report.add(
                        "valid_source_sections",
                        "block",
                        artifact.name,
                        "source_sections is required and must be non-empty",
                        record_id,
                    )
                if (
                    record.get("confidence_label") in {"high_confidence_core", "common_practice"}
                    and not record.get("source_ids")
                ):
                    report.add(
                        "source_id_required",
                        "block",
                        artifact.name,
                        "high/common confidence records require source_ids",
                        record_id,
                    )
                if not record.get("validation_rules") and artifact.name != "validation_rules":
                    report.add(
                        "validation_rules_required",
                        "block",
                        artifact.name,
                        "registry records require validation_rules",
                        record_id,
                    )
                if not record.get("failure_modes"):
                    report.add(
                        "failure_modes_required",
                        "block",
                        artifact.name,
                        "registry records require failure_modes",
                        record_id,
                    )

        attributes = self.artifact("attributes")
        for row in attributes.records:
            record_id = str(row.get("key", ""))
            if not row.get("source_ids"):
                report.add("source_id_required", "block", attributes.name, "attribute source_ids missing", record_id)
            if row.get("confidence_label") not in VALID_CONFIDENCE_LABELS:
                report.add(
                    "valid_confidence_label",
                    "block",
                    attributes.name,
                    f"invalid confidence_label={row.get('confidence_label')!r}",
                    record_id,
                )
            if row.get("production_scoring_eligible", "").lower() == "true" and not row.get(
                "validation_requirements"
            ):
                report.add(
                    "production_attribute_validation_required",
                    "block",
                    attributes.name,
                    "production-scoring attributes require validation_requirements",
                    record_id,
                )

    def _validate_cross_references(self, report: ValidationReport) -> None:
        entities = self.artifact("entity_types").id_set()
        profiles = self.artifact("strategy_profiles").id_set()
        outputs = self.artifact("output_views").id_set()
        rules = self.artifact("validation_rules").id_set()
        connectors = self._connector_roles()

        for edge in self.artifact("edge_types").records:
            fs = edge.get("family_specific", {})
            for field_name in ("from_entity_type", "to_entity_type"):
                value = fs.get(field_name)
                if value not in entities:
                    report.add(
                        "edge_entity_reference",
                        "block",
                        "edge_types",
                        f"{field_name} does not resolve: {value}",
                        edge.get("id"),
                    )

        for entity in self.artifact("entity_types").records:
            immutable_keys = set(entity.get("family_specific", {}).get("immutable_keys", []))
            if "ticker" in immutable_keys or "ticker_symbol" in immutable_keys:
                report.add(
                    "no_ticker_as_primary_key",
                    "block",
                    "entity_types",
                    "ticker cannot be an immutable key",
                    entity.get("id"),
                )

        for artifact in self._json_artifacts():
            for record in artifact.records:
                record_id = record.get("id")
                for profile_id in record.get("compatible_strategy_profiles", []):
                    if profile_id not in profiles:
                        report.add(
                            "valid_profile_references",
                            "block",
                            artifact.name,
                            f"compatible_strategy_profiles reference does not resolve: {profile_id}",
                            record_id,
                        )
                for rule_id in record.get("validation_rules", []):
                    if rule_id not in rules:
                        report.add(
                            "valid_validation_rule_references",
                            "block",
                            artifact.name,
                            f"validation rule does not resolve: {rule_id}",
                            record_id,
                        )
                for role in record.get("rights", {}).get("connector_roles", []):
                    if role not in connectors:
                        report.add(
                            "valid_connector_roles",
                            "block",
                            artifact.name,
                            f"connector role does not resolve: {role}",
                            record_id,
                        )

        for insight in self.artifact("insight_types").records:
            if not insight.get("compatible_strategy_profiles"):
                report.add(
                    "insight_maps_to_profile",
                    "block",
                    "insight_types",
                    "insight does not map to any strategy profile",
                    insight.get("id"),
                )

        for profile in self.artifact("strategy_profiles").records:
            output_refs = profile.get("output_views", [])
            if not output_refs:
                report.add(
                    "profile_maps_to_output_view",
                    "block",
                    "strategy_profiles",
                    "profile does not map to any output view",
                    profile.get("id"),
                )
            for output_id in output_refs:
                if output_id not in outputs:
                    report.add(
                        "profile_maps_to_output_view",
                        "block",
                        "strategy_profiles",
                        f"output view does not resolve: {output_id}",
                        profile.get("id"),
                    )

        for row in self.artifact("attributes").records:
            for role in _split_cell(row.get("connector_roles", "")):
                if role not in connectors:
                    report.add(
                        "valid_connector_roles",
                        "block",
                        "attributes",
                        f"connector role does not resolve: {role}",
                        row.get("key"),
                    )
            for profile_id in _split_cell(row.get("compatible_strategy_profiles", "")):
                if profile_id != "*" and profile_id not in profiles:
                    report.add(
                        "valid_profile_references",
                        "block",
                        "attributes",
                        f"compatible_strategy_profiles reference does not resolve: {profile_id}",
                        row.get("key"),
                    )

    def _validate_pit_and_rights(self, report: ValidationReport) -> None:
        pit_fields = {
            "observed_at_policy",
            "available_at_policy",
            "retrieved_at_policy",
            "source_version_policy",
            "data_version_policy",
            "model_version_policy",
            "vintage_required",
            "lookahead_risk",
        }
        rights_fields = {
            "connector_roles",
            "license_policy",
            "query_policy",
            "cache_policy",
            "display_policy",
            "export_policy",
            "derived_value_policy",
            "redistribution_policy",
            "marketplace_policy",
            "attribution_required",
            "retention_policy",
            "redaction_required",
        }
        for artifact in self._json_artifacts():
            for record in artifact.records:
                record_id = record.get("id")
                pit = record.get("pit") or {}
                rights = record.get("rights") or {}
                if artifact.name in OBSERVATION_BEARING_ARTIFACTS:
                    missing_pit = sorted(pit_fields - set(pit))
                    if missing_pit:
                        report.add(
                            "pit_policy_required",
                            "block",
                            artifact.name,
                            f"missing PIT fields: {missing_pit}",
                            record_id,
                        )
                    for field_name in ("observed_at_policy", "available_at_policy", "retrieved_at_policy"):
                        if not pit.get(field_name) or pit.get(field_name) == "unknown":
                            report.add(
                                f"{field_name}_required",
                                "block",
                                artifact.name,
                                f"{field_name} must be known for data-dependent objects",
                                record_id,
                            )
                missing_rights = sorted(rights_fields - set(rights))
                if missing_rights:
                    report.add(
                        "rights_policy_required",
                        "block",
                        artifact.name,
                        f"missing rights fields: {missing_rights}",
                        record_id,
                    )
                if rights.get("license_policy") in {"unknown", "restricted_or_unclear"}:
                    if rights.get("export_policy") != "blocked":
                        report.add(
                            "unknown_rights_block_export",
                            "block",
                            artifact.name,
                            "unknown/restricted rights must block export",
                            record_id,
                        )
                    if rights.get("marketplace_policy") not in {"blocked", "redacted"}:
                        report.add(
                            "marketplace_draft_redacts_restricted_or_unclear_rights",
                            "block",
                            artifact.name,
                            "unknown/restricted rights must be blocked or redacted in marketplace_draft",
                            record_id,
                        )

        for row in self.artifact("attributes").records:
            record_id = row.get("key")
            for field_name in pit_fields:
                if field_name not in row or row.get(field_name) == "":
                    report.add(
                        "pit_policy_required",
                        "block",
                        "attributes",
                        f"missing PIT column: {field_name}",
                        record_id,
                    )
            for field_name in (
                "entitlement_policy",
                "cache_policy",
                "display_policy",
                "export_policy",
                "derived_value_policy",
                "redistribution_policy",
                "marketplace_policy",
            ):
                if field_name not in row or row.get(field_name) == "":
                    report.add(
                        "rights_policy_required",
                        "block",
                        "attributes",
                        f"missing rights column: {field_name}",
                        record_id,
                    )

        for row in self.artifact("rights_matrix").records:
            if row.get("license_policy") in {"unknown", "restricted_or_unclear"}:
                decision = self.package_decision(
                    license_policy=row.get("license_policy", "unknown"),
                    package_mode="marketplace_draft",
                    rights_unknown=row.get("license_policy") == "unknown",
                )
                if not decision.blocked:
                    report.add(
                        "unknown_rights_block_export",
                        "block",
                        "rights_matrix",
                        "unknown/restricted rights must fail closed",
                        row.get("data_type"),
                    )

    def _validate_output_redaction(self, report: ValidationReport) -> None:
        for output in self.artifact("output_views").records:
            output_id = output.get("id")
            fs = output.get("family_specific", {})
            required_sections = set(fs.get("required_sections", []))
            data_rights = fs.get("data_rights", {})
            if "pit_summary" not in required_sections:
                report.add(
                    "output_pit_summary_required",
                    "block",
                    "output_views",
                    "output view must expose PIT state",
                    output_id,
                )
            if "rights_summary" not in required_sections and output_id != "source_rights_report":
                report.add(
                    "output_rights_summary_required",
                    "block",
                    "output_views",
                    "output view must expose rights state",
                    output_id,
                )
            if not data_rights:
                report.add(
                    "output_redaction_policy_exists",
                    "block",
                    "output_views",
                    "output view must declare data_rights redaction policy",
                    output_id,
                )
            if output_id in RECOMMENDATION_LIKE_OUTPUTS:
                binding = fs.get("binding", {})
                if not binding.get("non_advice_boundary_required") or "non_advice_boundary" not in required_sections:
                    report.add(
                        "recommendation_like_outputs_have_non_advice_boundary",
                        "block",
                        "output_views",
                        "recommendation-like outputs require a non-advice boundary",
                        output_id,
                    )
            if data_rights.get("marketplace_policy") == "allowed" and data_rights.get(
                "export_policy"
            ) == "allowed":
                report.add(
                    "marketplace_draft_redacts_restricted_or_unclear_rights",
                    "warn",
                    "output_views",
                    "marketplace_draft should be reviewed when an output allows unredacted export",
                    output_id,
                )

    def _validate_human_review_gates(self, report: ValidationReport) -> None:
        for artifact_name in ("node_types", "insight_types", "strategy_profiles"):
            for record in self.artifact(artifact_name).records:
                record_id = str(record.get("id", ""))
                if any(token in record_id for token in ("short", "fraud", "legal")):
                    if not record.get("human_review_required"):
                        report.add(
                            "fraud_legal_short_claims_require_human_review",
                            "block",
                            artifact_name,
                            "fraud/legal/short records require human review",
                            record_id,
                        )

    def _connector_roles(self) -> set[str]:
        base_roles = self.artifact("connector_requirements").id_set()
        matrix_roles = {
            str(row.get("connector_role", "")) for row in self.artifact("rights_matrix").records
        }
        return base_roles | matrix_roles | set(CONNECTOR_ROLE_ALIASES)

    def _json_artifacts(self) -> Iterable[RegistryArtifact]:
        for name in JSON_ARTIFACTS:
            yield self.artifact(name)


def load_equity_module(
    artifact_dir: str | Path | None = None,
    *,
    module_dir: str | Path | None = None,
) -> EquityModule:
    registries_dir = Path(artifact_dir) if artifact_dir is not None else DEFAULT_EQUITY_REGISTRIES_DIR
    module_root = Path(module_dir) if module_dir is not None else registries_dir.parent

    artifacts: dict[str, RegistryArtifact] = {}
    for name, (filename, expected_family) in JSON_ARTIFACTS.items():
        path = registries_dir / filename
        artifacts[name] = RegistryArtifact(
            name=name,
            path=path,
            records=_read_json_records(path),
            id_field="id",
            expected_family=expected_family,
        )
    for name, (filename, id_field) in CSV_ARTIFACTS.items():
        path = registries_dir / filename
        artifacts[name] = RegistryArtifact(
            name=name,
            path=path,
            records=_read_csv_records(path),
            id_field=id_field,
        )
    for name, (filename, id_field) in OPTIONAL_CSV_ARTIFACTS.items():
        path = registries_dir / filename
        if path.exists():
            artifacts[name] = RegistryArtifact(
                name=name,
                path=path,
                records=_read_csv_records(path),
                id_field=id_field,
            )

    manifest_path = registries_dir / "viza.finance.equity_investment.manifest.json"
    if not manifest_path.exists():
        manifest_path = module_root / "viza.finance.equity_investment.manifest.json"
    manifest = _read_json_object(manifest_path)
    return EquityModule(
        artifact_dir=registries_dir,
        module_dir=module_root,
        manifest=manifest,
        artifacts=artifacts,
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise EquityRegistryError(f"missing equity JSON artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EquityRegistryError(f"equity JSON artifact must be an object: {path}")
    return payload


def _read_json_records(path: Path) -> list[dict[str, Any]]:
    payload = _read_json_object(path)
    records = payload.get("records")
    if not isinstance(records, list):
        raise EquityRegistryError(f"equity JSON artifact missing records list: {path}")
    return [record for record in records if isinstance(record, dict)]


def _read_csv_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise EquityRegistryError(f"missing equity CSV artifact: {path}")
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _split_cell(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
