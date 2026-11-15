from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.file_format.models import VisibilityMode
from viza.graph_schema import MethodologyGraph
from viza.validation_ledger import VizaValidationRecord


MARKETPLACE_DRAFT_PURPOSE = "marketplace_draft"

COMPLIANCE_WARNING_MESSAGES = {
    "not_investment_advice_missing": "Marketplace drafts need an explicit not-investment-advice label.",
    "performance_claim_unverified": "Performance claims are present without validation proof.",
    "source_data_redistribution_forbidden": "At least one source policy forbids redistribution or marketplace packaging.",
    "rumor_data_unverified": "Rumor, social, or low-confidence source usage needs review.",
    "black_box_without_proof": "Black-box marketplace drafts need validation proof before review.",
    "insufficient_out_of_sample_history": "Out-of-sample validation history is not yet sufficient.",
    "lookahead_risk_detected": "Potential look-ahead risk needs review before marketplace use.",
}

READINESS_CHECK_KEYS = [
    "validation_record_count",
    "out_of_sample_candidate_count",
    "data_leakage_checks_passed",
    "source_rights_passed",
    "creator_identity_present",
    "proof_available",
    "redaction_safe",
    "performance_observation_pending_or_complete",
]


class MarketplaceDraftError(ValueError):
    pass


class MarketplaceComplianceWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: str = "warning"


class MarketplaceDraftAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str = MARKETPLACE_DRAFT_PURPOSE
    generated_at: str
    allowed_summary: dict[str, Any]
    creator: dict[str, Any]
    rights_summary: dict[str, Any]
    compliance_warnings: list[MarketplaceComplianceWarning] = Field(default_factory=list)
    readiness_checklist: dict[str, Any]
    monetization: dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": False,
            "reason": "marketplace draft review only; no monetization flow is active",
        }
    )


def build_marketplace_draft_assessment(
    graph: MethodologyGraph,
    *,
    visibility: VisibilityMode,
    creator_id: str | None = None,
    creator_display_name: str | None = None,
    validation_record: VizaValidationRecord | None = None,
    source_rights: list[dict[str, Any]] | None = None,
    include_validation_proof: bool = False,
    not_investment_advice_acknowledged: bool = False,
) -> MarketplaceDraftAssessment:
    rights_records = _rights_records(graph, validation_record, source_rights or [])
    blocking_rights = [
        record for record in rights_records if _marketplace_packaging_forbidden(record)
    ]
    if blocking_rights:
        blocked_sources = ", ".join(
            sorted(
                {
                    _source_label(record)
                    for record in blocking_rights
                    if _source_label(record)
                }
            )
        )
        message = COMPLIANCE_WARNING_MESSAGES["source_data_redistribution_forbidden"]
        detail = f" Restricted sources: {blocked_sources}." if blocked_sources else ""
        raise MarketplaceDraftError(
            f"source_data_redistribution_forbidden: {message}{detail}"
        )

    creator = _creator_placeholder(
        creator_id=creator_id,
        creator_display_name=creator_display_name,
    )
    warnings = _compliance_warnings(
        graph,
        visibility=visibility,
        validation_record=validation_record,
        include_validation_proof=include_validation_proof,
        rights_records=rights_records,
        not_investment_advice_acknowledged=not_investment_advice_acknowledged,
    )
    rights_summary = _rights_summary(rights_records)
    readiness = _readiness_checklist(
        creator=creator,
        warnings=warnings,
        rights_summary=rights_summary,
        validation_record=validation_record,
        visibility=visibility,
    )
    return MarketplaceDraftAssessment(
        generated_at=datetime.now(timezone.utc).isoformat(),
        allowed_summary=_allowed_summary(
            graph,
            visibility=visibility,
            include_validation_proof=include_validation_proof,
            validation_record=validation_record,
        ),
        creator=creator,
        rights_summary=rights_summary,
        compliance_warnings=warnings,
        readiness_checklist=readiness,
    )


def marketplace_metadata_payload(assessment: MarketplaceDraftAssessment) -> dict[str, Any]:
    return {
        "schema": "viza.marketplace_draft_metadata.v1",
        "purpose": assessment.purpose,
        "generated_at": assessment.generated_at,
        "allowed_summary": assessment.allowed_summary,
        "creator": assessment.creator,
        "rights_summary": assessment.rights_summary,
        "compliance_warnings": [
            warning.model_dump(mode="json") for warning in assessment.compliance_warnings
        ],
        "compliance_warning_labels": [
            warning.code for warning in assessment.compliance_warnings
        ],
        "readiness_checklist": assessment.readiness_checklist,
        "monetization": assessment.monetization,
    }


def compliance_warning_labels(assessment: MarketplaceDraftAssessment) -> list[str]:
    return [warning.code for warning in assessment.compliance_warnings]


def source_rights_from_run_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    connectors = manifest.get("connectors")
    if not isinstance(connectors, dict):
        return []
    records: list[dict[str, Any]] = []
    for connector_id, raw_connector in connectors.items():
        if not isinstance(connector_id, str) or not isinstance(raw_connector, dict):
            continue
        entitlement = raw_connector.get("entitlement")
        entitlement = entitlement if isinstance(entitlement, dict) else {}
        records.append(
            {
                "connector_id": connector_id,
                "source_id": connector_id,
                "license_policy": _read_string(raw_connector.get("license_policy"), "unknown"),
                "export_allowed": entitlement.get("export_allowed"),
                "redistribution_allowed": entitlement.get("redistribution_allowed"),
                "entitlement": entitlement,
            }
        )
    return records


def _creator_placeholder(
    *,
    creator_id: str | None,
    creator_display_name: str | None,
) -> dict[str, Any]:
    has_identity = bool((creator_id or "").strip() or (creator_display_name or "").strip())
    return {
        "creator_id": (creator_id or "local_unverified_creator").strip()
        or "local_unverified_creator",
        "display_name": (creator_display_name or "Local unverified creator").strip()
        or "Local unverified creator",
        "verification_status": "unverified",
        "identity_present": has_identity,
        "metadata": {},
    }


def _allowed_summary(
    graph: MethodologyGraph,
    *,
    visibility: VisibilityMode,
    include_validation_proof: bool,
    validation_record: VizaValidationRecord | None,
) -> dict[str, Any]:
    return {
        "schema": "viza.marketplace_draft_summary.v1",
        "methodology_id": graph.methodology_id,
        "name": graph.name,
        "description": graph.description,
        "graph_schema_version": graph.schema_version,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "visibility": visibility.value,
        "full_graph_included": False,
        "included_sections": [
            "marketplace_metadata",
            "rights",
            *(
                ["validation_proof"]
                if include_validation_proof and validation_record is not None
                else []
            ),
        ],
    }


def _compliance_warnings(
    graph: MethodologyGraph,
    *,
    visibility: VisibilityMode,
    validation_record: VizaValidationRecord | None,
    include_validation_proof: bool,
    rights_records: list[dict[str, Any]],
    not_investment_advice_acknowledged: bool,
) -> list[MarketplaceComplianceWarning]:
    labels: list[str] = []
    if not not_investment_advice_acknowledged:
        labels.append("not_investment_advice_missing")
    if _has_performance_claim(graph) and validation_record is None:
        labels.append("performance_claim_unverified")
    if _has_unverified_rumor_or_social_source(graph, rights_records):
        labels.append("rumor_data_unverified")
    if visibility == VisibilityMode.BLACK_BOX and validation_record is None:
        labels.append("black_box_without_proof")
    if validation_record is None or validation_record.in_sample_out_of_sample_label != "out_of_sample_candidate":
        labels.append("insufficient_out_of_sample_history")
    if _has_lookahead_risk(graph, validation_record):
        labels.append("lookahead_risk_detected")
    return [
        MarketplaceComplianceWarning(code=label, message=COMPLIANCE_WARNING_MESSAGES[label])
        for label in dict.fromkeys(labels)
    ]


def _readiness_checklist(
    *,
    creator: dict[str, Any],
    warnings: list[MarketplaceComplianceWarning],
    rights_summary: dict[str, Any],
    validation_record: VizaValidationRecord | None,
    visibility: VisibilityMode,
) -> dict[str, Any]:
    warning_codes = {warning.code for warning in warnings}
    performance_status = (
        (validation_record.performance_observation or {}).get("status")
        if validation_record is not None
        else None
    )
    checks = {
        "validation_record_count": {
            "value": 1 if validation_record is not None else 0,
            "passed": validation_record is not None,
        },
        "out_of_sample_candidate_count": {
            "value": (
                1
                if validation_record is not None
                and validation_record.in_sample_out_of_sample_label == "out_of_sample_candidate"
                else 0
            ),
            "passed": "insufficient_out_of_sample_history" not in warning_codes,
        },
        "data_leakage_checks_passed": {
            "passed": "lookahead_risk_detected" not in warning_codes,
        },
        "source_rights_passed": {
            "passed": bool(rights_summary.get("source_rights_passed")),
        },
        "creator_identity_present": {
            "passed": bool(creator.get("identity_present")),
        },
        "proof_available": {
            "passed": validation_record is not None,
        },
        "redaction_safe": {
            "passed": visibility != VisibilityMode.BLACK_BOX
            or "black_box_without_proof" not in warning_codes,
        },
        "performance_observation_pending_or_complete": {
            "status": performance_status or "missing",
            "passed": performance_status in {"pending", "complete", "completed"},
        },
    }
    return {key: checks[key] for key in READINESS_CHECK_KEYS}


def _rights_summary(rights_records: list[dict[str, Any]]) -> dict[str, Any]:
    sources = [_public_rights_record(record) for record in rights_records]
    return {
        "schema": "viza.rights_summary.v1",
        "source_count": len(sources),
        "source_rights_passed": True,
        "sources": sources,
    }


def _public_rights_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "connector_id": _read_string(record.get("connector_id")),
        "source_id": _read_string(record.get("source_id")),
        "license_policy": _read_string(record.get("license_policy"), "unknown"),
        "export_policy": _read_string(record.get("export_policy"), "unknown"),
        "redistribution_policy": _read_string(
            record.get("redistribution_policy")
            or record.get("redistribute_policy")
            or record.get("redistribute_allowed"),
            "unknown",
        ),
        "marketplace_policy": _read_string(record.get("marketplace_policy"), "unknown"),
        "attribution_required": bool(record.get("attribution_required", False)),
        "status": "allowed",
    }


def _rights_records(
    graph: MethodologyGraph,
    validation_record: VizaValidationRecord | None,
    source_rights: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for node in graph.nodes:
        records.extend(_rights_records_from_value(node.config))
    for edge in graph.edges:
        records.extend(_rights_records_from_value(edge.config))
    records.extend(_rights_records_from_value(graph.metadata))
    if validation_record is not None:
        records.extend(
            record
            for record in validation_record.source_rights
            if isinstance(record, dict)
        )
    records.extend(record for record in source_rights if isinstance(record, dict))
    return _dedupe_records(records)


def _rights_records_from_value(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key in ("rights_policy", "source_policy", "marketplace_policy"):
            candidate = value.get(key)
            if isinstance(candidate, dict):
                records.append(candidate)
        if _looks_like_rights_record(value):
            records.append(value)
        for child in value.values():
            records.extend(_rights_records_from_value(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_rights_records_from_value(child))
    return records


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (
            _read_string(record.get("connector_id")),
            _read_string(record.get("source_id")),
            _read_string(record.get("license_policy")),
            _read_string(record.get("redistribution_policy") or record.get("marketplace_policy")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _looks_like_rights_record(value: dict[str, Any]) -> bool:
    return any(
        key in value
        for key in (
            "connector_id",
            "source_id",
            "license_policy",
            "export_policy",
            "redistribution_policy",
            "marketplace_policy",
        )
    )


def _marketplace_packaging_forbidden(record: dict[str, Any]) -> bool:
    if record.get("marketplace_allowed") is False:
        return True
    for key in ("marketplace_policy", "redistribution_policy", "redistribute_policy"):
        label = _read_string(record.get(key)).lower().replace(" ", "_")
        if not label:
            continue
        if label in _FORBIDDEN_POLICY_TOKENS or any(
            token in label for token in _FORBIDDEN_POLICY_TOKENS
        ):
            return True
    if _is_internal_owned_record(record):
        return False
    if record.get("redistribution_allowed") is False:
        return True
    if record.get("redistribute_allowed") is False:
        return True
    return False


_FORBIDDEN_POLICY_TOKENS = {
    "blocked",
    "denied",
    "forbidden",
    "license_required",
    "no_marketplace",
    "no_redistribution",
    "restricted",
}


def _source_label(record: dict[str, Any]) -> str:
    connector_id = _read_string(record.get("connector_id"), "unknown_connector")
    source_id = _read_string(record.get("source_id"), "unknown_source")
    return f"{connector_id}:{source_id}"


def _is_internal_owned_record(record: dict[str, Any]) -> bool:
    connector_id = _read_string(record.get("connector_id")).lower()
    license_policy = _read_string(record.get("license_policy")).lower()
    return connector_id == "local_viza_workspace" or license_policy.startswith("internal")


def _has_performance_claim(graph: MethodologyGraph) -> bool:
    claim_keys = {
        "performance_claim",
        "performance_claims",
        "claimed_return",
        "claimed_alpha",
        "backtest_claim",
    }
    return _contains_key(graph.metadata, claim_keys)


def _has_unverified_rumor_or_social_source(
    graph: MethodologyGraph,
    rights_records: list[dict[str, Any]],
) -> bool:
    tokens = {"rumor", "social", "reddit", "x_twitter", "unverified_news"}
    if _contains_token(graph.model_dump(mode="json"), tokens):
        return True
    return any(_contains_token(record, tokens) for record in rights_records)


def _has_lookahead_risk(
    graph: MethodologyGraph,
    validation_record: VizaValidationRecord | None,
) -> bool:
    tokens = {"lookahead", "look_ahead", "future_data", "not_point_in_time"}
    if _contains_token(graph.metadata, tokens):
        return True
    if validation_record is None:
        return False
    if _contains_token(validation_record.PIT_summary, tokens):
        return True
    return any(_contains_token(warning, tokens) for warning in validation_record.warnings)


def _contains_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            (isinstance(key, str) and key in keys) or _contains_key(child, keys)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_key(item, keys) for item in value)
    return False


def _contains_token(value: Any, tokens: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            (isinstance(key, str) and _string_has_token(key, tokens))
            or _contains_token(child, tokens)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_token(item, tokens) for item in value)
    if isinstance(value, str):
        return _string_has_token(value, tokens)
    return False


def _string_has_token(value: str, tokens: set[str]) -> bool:
    normalized = value.lower().replace("-", "_").replace(" ", "_")
    return any(token in normalized for token in tokens)


def _read_string(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) else fallback
