from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from viza.file_format.container import read_viza_manifest, write_viza_container
from viza.file_format.models import (
    CANONICAL_SECTION_NAMES,
    SectionStatus,
    VisibilityMode,
    VizaFileManifest,
    VizaModuleRequirement,
    VizaSectionDescriptor,
    VizaWriteResult,
)
from viza.graph_schema import MethodologyGraph, VIZA_GRAPH_SCHEMA_VERSION
from viza.marketplace import (
    MARKETPLACE_DRAFT_PURPOSE,
    build_marketplace_draft_assessment,
    compliance_warning_labels,
    marketplace_metadata_payload,
)
from viza.validation_ledger import VizaValidationRecord, validation_proof_for_export


class VizaPackagingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: MethodologyGraph
    target_path: str | Path
    purpose: str = "methodology_graph"
    visibility: VisibilityMode = VisibilityMode.WHITE_BOX
    display_name: str | None = None
    include_validation_proof: bool = False
    validation_record: VizaValidationRecord | None = None
    include_signal_outputs: bool = False
    include_sample_outputs: bool = False
    redact_parameters: bool = False
    lock_sections: list[str] = Field(default_factory=list)
    creator_id: str | None = None
    creator_display_name: str | None = None
    source_rights: list[dict[str, Any]] = Field(default_factory=list)
    not_investment_advice_acknowledged: bool = False


def export_packaged_viza(request: VizaPackagingRequest) -> tuple[VizaWriteResult, dict[str, Any]]:
    manifest, sections = build_packaged_viza_manifest_and_sections(request)
    result = write_viza_container(request.target_path, manifest, sections)
    written_manifest = read_viza_manifest(request.target_path)
    return result, written_manifest.model_dump(mode="json", by_alias=True)


def build_packaged_viza_manifest_and_sections(
    request: VizaPackagingRequest,
) -> tuple[VizaFileManifest, dict[str, Any]]:
    sections = {
        section_name: VizaSectionDescriptor(status=SectionStatus.ABSENT, reason="not_included")
        for section_name in CANONICAL_SECTION_NAMES
    }
    payloads: dict[str, Any] = {}
    visibility = request.visibility

    if request.purpose == MARKETPLACE_DRAFT_PURPOSE:
        return _marketplace_draft_manifest_and_sections(request, sections)

    if visibility == VisibilityMode.WHITE_BOX:
        sections["methodology_graph"] = _included_graph_descriptor()
        payloads["methodology_graph"] = request.graph.model_dump(mode="json")
    elif visibility == VisibilityMode.GRAY_BOX:
        sections["methodology_graph"] = _included_graph_descriptor(reason="parameters_redacted")
        payloads["methodology_graph"] = _redacted_graph_payload(request.graph)
    else:
        sections["methodology_graph"] = VizaSectionDescriptor(
            status=SectionStatus.REDACTED,
            reason=f"{visibility.value}_does_not_expose_graph",
        )

    if request.include_signal_outputs or visibility in {
        VisibilityMode.BLACK_BOX,
        VisibilityMode.OUTPUT_ONLY,
        VisibilityMode.PREVIEW_ONLY,
    }:
        sections["radar_output"] = VizaSectionDescriptor(
            status=SectionStatus.INCLUDED,
            path="radar/radar_output.json",
            reason="sample_only" if visibility == VisibilityMode.PREVIEW_ONLY else None,
        )
        payloads["radar_output"] = _safe_output_payload(
            request.graph,
            sample_only=visibility == VisibilityMode.PREVIEW_ONLY or request.include_sample_outputs,
        )

    if request.include_validation_proof:
        if request.validation_record is None:
            sections["validation_proof"] = VizaSectionDescriptor(
                status=SectionStatus.ABSENT,
                reason="validation_record_not_available",
            )
        else:
            sections["validation_proof"] = VizaSectionDescriptor(
                status=SectionStatus.INCLUDED,
                path="proof/validation_manifest.json",
            )
            payloads["validation_proof"] = validation_proof_for_export(request.validation_record)

    for section_name in request.lock_sections:
        if section_name not in sections:
            continue
        sections[section_name] = VizaSectionDescriptor(
            status=SectionStatus.ENTITLEMENT_LOCKED,
            reason="creator_permission_required",
        )
        payloads.pop(section_name, None)

    timestamp = datetime.now(timezone.utc)
    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id=f"viza-file-{uuid4()}",
        display_name=request.display_name or request.graph.name,
        object_kind="methodology" if visibility in {VisibilityMode.WHITE_BOX, VisibilityMode.GRAY_BOX} else "strategy_package",
        primary_mode=visibility.value,
        exchange_modes=[visibility.value],
        visibility=visibility,
        created_at=timestamp,
        updated_at=timestamp,
        minimum_viza_version="0.2.0",
        required_modules=[
            VizaModuleRequirement(
                module_id="viza.finance.securities",
                version_range=">=0.1.0",
                required=True,
            )
        ],
        sections=sections,
        permissions=_permissions_for_visibility(visibility),
        purpose=request.purpose,
        integrity={
            "signature_status": "unsigned",
            "redaction_policy": visibility.value,
            "redacted_parameters": visibility == VisibilityMode.GRAY_BOX or request.redact_parameters,
        },
    )
    return manifest, payloads


def _marketplace_draft_manifest_and_sections(
    request: VizaPackagingRequest,
    sections: dict[str, VizaSectionDescriptor],
) -> tuple[VizaFileManifest, dict[str, Any]]:
    assessment = build_marketplace_draft_assessment(
        request.graph,
        visibility=request.visibility,
        creator_id=request.creator_id,
        creator_display_name=request.creator_display_name,
        validation_record=request.validation_record,
        source_rights=request.source_rights,
        include_validation_proof=request.include_validation_proof
        or request.validation_record is not None,
        not_investment_advice_acknowledged=request.not_investment_advice_acknowledged,
    )
    metadata_payload = marketplace_metadata_payload(assessment)
    payloads: dict[str, Any] = {
        "marketplace_metadata": metadata_payload,
        "rights": assessment.rights_summary,
    }
    sections["methodology_graph"] = VizaSectionDescriptor(
        status=SectionStatus.REDACTED,
        reason="marketplace_draft_summary_only",
    )
    sections["marketplace_metadata"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="marketplace/metadata.json",
    )
    sections["rights"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="rights/license_and_entitlements.json",
    )
    include_proof = request.include_validation_proof or request.validation_record is not None
    if include_proof:
        if request.validation_record is None:
            sections["validation_proof"] = VizaSectionDescriptor(
                status=SectionStatus.ABSENT,
                reason="validation_record_not_available",
            )
        else:
            sections["validation_proof"] = VizaSectionDescriptor(
                status=SectionStatus.INCLUDED,
                path="proof/validation_manifest.json",
            )
            payloads["validation_proof"] = validation_proof_for_export(request.validation_record)

    timestamp = datetime.now(timezone.utc)
    warning_labels = compliance_warning_labels(assessment)
    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id=f"viza-file-{uuid4()}",
        display_name=request.display_name or request.graph.name,
        object_kind="marketplace_draft",
        primary_mode=MARKETPLACE_DRAFT_PURPOSE,
        exchange_modes=[MARKETPLACE_DRAFT_PURPOSE, request.visibility.value],
        visibility=request.visibility,
        created_at=timestamp,
        updated_at=timestamp,
        minimum_viza_version="0.2.0",
        required_modules=[
            VizaModuleRequirement(
                module_id="viza.finance.securities",
                version_range=">=0.1.0",
                required=True,
            )
        ],
        sections=sections,
        data_requirements={
            "required_connectors": _required_connectors_from_rights(assessment.rights_summary)
        },
        permissions={
            "open_allowed": True,
            "run_allowed": False,
            "fork_allowed": False,
            "export_allowed": False,
            "redistribute_allowed": False,
            "marketplace_publish_allowed": False,
        },
        purpose=MARKETPLACE_DRAFT_PURPOSE,
        creator=assessment.creator,
        rights_summary=assessment.rights_summary,
        compliance_warnings=[
            warning.model_dump(mode="json") for warning in assessment.compliance_warnings
        ],
        readiness_checklist=assessment.readiness_checklist,
        marketplace={
            "draft": True,
            "publish_status": "not_published",
            "monetization_enabled": False,
        },
        integrity={
            "signature_status": "unsigned",
            "redaction_policy": MARKETPLACE_DRAFT_PURPOSE,
            "redacted_parameters": True,
            "compliance_warning_labels": warning_labels,
            "marketplace_publish_status": "not_published",
        },
    )
    return manifest, payloads


def _included_graph_descriptor(reason: str | None = None) -> VizaSectionDescriptor:
    return VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="graph/methodology.json",
        schema=VIZA_GRAPH_SCHEMA_VERSION,
        reason=reason,
    )


def _redacted_graph_payload(graph: MethodologyGraph) -> dict[str, Any]:
    payload = graph.model_dump(mode="json")
    for node in payload.get("nodes", []):
        if not isinstance(node, dict):
            continue
        config = node.get("config")
        if isinstance(config, dict):
            node["config"] = _redact_config(config)
    payload["redaction_summary"] = {
        "status": "parameters_redacted",
        "redacted_keys": sorted(REDACTED_PARAMETER_KEYS),
    }
    return payload


REDACTED_PARAMETER_KEYS = {
    "threshold",
    "thresholds",
    "weight",
    "weights",
    "proprietary_notes",
    "secret_formula",
    "ranking_formula",
}


def _redact_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in config.items():
        if key.lower() in REDACTED_PARAMETER_KEYS:
            redacted[key] = "[redacted]"
        elif isinstance(value, dict):
            redacted[key] = _redact_config(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_config(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def _safe_output_payload(graph: MethodologyGraph, *, sample_only: bool) -> dict[str, Any]:
    return {
        "schema": "viza.radar_output.preview.v1",
        "methodology_id": graph.methodology_id,
        "sample_only": sample_only,
        "row_count": 0,
        "rows": [],
        "note": "Output payload placeholder; raw graph content is not bundled.",
    }


def _required_connectors_from_rights(rights_summary: dict[str, Any]) -> list[str]:
    sources = rights_summary.get("sources")
    if not isinstance(sources, list):
        return []
    connectors: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        connector_id = source.get("connector_id")
        if isinstance(connector_id, str) and connector_id:
            connectors.append(connector_id)
    return list(dict.fromkeys(connectors))


def _permissions_for_visibility(visibility: VisibilityMode) -> dict[str, bool]:
    if visibility == VisibilityMode.WHITE_BOX:
        return {
            "open_allowed": True,
            "run_allowed": True,
            "fork_allowed": True,
            "export_allowed": True,
            "redistribute_allowed": False,
        }
    if visibility == VisibilityMode.GRAY_BOX:
        return {
            "open_allowed": True,
            "run_allowed": True,
            "fork_allowed": False,
            "export_allowed": False,
            "redistribute_allowed": False,
        }
    return {
        "open_allowed": True,
        "run_allowed": False,
        "fork_allowed": False,
        "export_allowed": False,
        "redistribute_allowed": False,
    }
