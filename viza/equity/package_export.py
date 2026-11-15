from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from viza.equity.config import EquityRuntimeConfig
from viza.equity.persistence import EquityPreviewRunDetail, get_equity_preview_store
from viza.equity.registry import EQUITY_MODULE_ID, EQUITY_MODULE_VERSION
from viza.equity.runtime import NON_ADVICE_BOUNDARY, QUALITY_VALUE_PROFILE_ID
from viza.file_format.container import read_viza_manifest, write_viza_container
from viza.file_format.models import (
    CANONICAL_SECTION_NAMES,
    SectionStatus,
    VisibilityMode,
    VizaFileManifest,
    VizaModuleRequirement,
    VizaSectionDescriptor,
)
from viza.graph_schema import (
    GraphPosition,
    MethodologyEdge,
    MethodologyGraph,
    MethodologyNode,
    VizaNodeType,
)
from viza.project_store import get_project_store, project_store_path


EquityPreviewPackageMode = Literal["white_box", "output_only", "marketplace_draft"]


class EquityPreviewPackageDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_mode: EquityPreviewPackageMode = "marketplace_draft"
    target_path: str | None = None
    project_id: str | None = None
    creator_id: str | None = None
    creator_display_name: str | None = None
    not_investment_advice_acknowledged: bool = True


class EquityPreviewPackageDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    package_mode: EquityPreviewPackageMode
    package_ready_status: str
    target_path: str
    result: dict[str, Any]
    manifest: dict[str, Any]
    export_record: dict[str, Any] | None = None
    proof_checksum: str
    pit_summary: dict[str, Any]
    rights_summary: dict[str, Any]
    package_redaction_preview: dict[str, Any]
    non_advice_boundary: str = NON_ADVICE_BOUNDARY
    warnings: list[str] = Field(default_factory=list)


def export_equity_preview_package_draft(
    run_id: str,
    request: EquityPreviewPackageDraftRequest,
) -> EquityPreviewPackageDraftResponse:
    _require_package_export_enabled()
    detail = get_equity_preview_store().require_detail(run_id)
    target_path = _target_path(detail, request)
    manifest, sections, warnings = build_equity_preview_package_manifest_and_sections(
        detail,
        package_mode=request.package_mode,
        creator_id=request.creator_id,
        creator_display_name=request.creator_display_name,
        not_investment_advice_acknowledged=request.not_investment_advice_acknowledged,
    )
    result = write_viza_container(target_path, manifest, sections)
    written_manifest = read_viza_manifest(target_path).model_dump(mode="json", by_alias=True)
    export_record = None
    if request.project_id is not None:
        export_record = get_project_store().save_viza_file_export(
            file_id=result.file_id,
            manifest=written_manifest,
            target_path=str(target_path),
            project_id=request.project_id,
            container_checksum=result.container_checksum,
            manifest_checksum=result.manifest_checksum,
            purpose="marketplace_draft"
            if request.package_mode == "marketplace_draft"
            else "equity_preview_package",
            visibility=_visibility_for_mode(request.package_mode).value,
            warnings=[*result.warnings, *warnings],
        )
    package_preview = detail.package_redaction_preview
    return EquityPreviewPackageDraftResponse(
        run_id=run_id,
        package_mode=request.package_mode,
        package_ready_status=_package_ready_status(package_preview),
        target_path=str(target_path),
        result=result.model_dump(mode="json"),
        manifest=written_manifest,
        export_record=(
            export_record.model_dump(mode="json") if export_record is not None else None
        ),
        proof_checksum=_read_string(detail.audit.get("proof_checksum")),
        pit_summary=_pit_summary(detail),
        rights_summary=_rights_summary(detail),
        package_redaction_preview=package_preview,
        warnings=[*result.warnings, *warnings],
    )


def _require_package_export_enabled() -> None:
    config = EquityRuntimeConfig.from_env()
    if not config.runtime_handlers_enabled or not config.sec_wedge_enabled:
        raise PermissionError("Equity runtime wedge package export is feature-flag disabled.")
    if not config.preview_persistence_enabled:
        raise PermissionError(
            "Equity preview package export requires VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED."
        )


def build_equity_preview_package_manifest_and_sections(
    detail: EquityPreviewRunDetail,
    *,
    package_mode: EquityPreviewPackageMode,
    creator_id: str | None = None,
    creator_display_name: str | None = None,
    not_investment_advice_acknowledged: bool = True,
) -> tuple[VizaFileManifest, dict[str, Any], list[str]]:
    timestamp = datetime.now(timezone.utc)
    visibility = _visibility_for_mode(package_mode)
    proof_checksum = _read_string(detail.audit.get("proof_checksum"))
    warnings = _package_warnings(detail, package_mode)
    redaction_policy = "marketplace_draft" if package_mode == "marketplace_draft" else package_mode
    sections = {
        section_name: VizaSectionDescriptor(status=SectionStatus.ABSENT, reason="not_included")
        for section_name in CANONICAL_SECTION_NAMES
    }
    payloads: dict[str, Any] = {}
    graph = _equity_preview_graph(detail)

    if package_mode == "white_box":
        sections["methodology_graph"] = VizaSectionDescriptor(
            status=SectionStatus.INCLUDED,
            path="graph/methodology.json",
            schema="viza_graph_v0",
        )
        payloads["methodology_graph"] = graph.model_dump(mode="json")
    else:
        sections["methodology_graph"] = VizaSectionDescriptor(
            status=SectionStatus.REDACTED,
            reason=f"{package_mode}_summary_only",
        )

    sections["strategy_profile"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="strategies/strategy_profile.json",
        schema="viza.equity.strategy_profile.v1",
    )
    payloads["strategy_profile"] = {
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "display_name": "Quality Value Long Only",
        "module_id": EQUITY_MODULE_ID,
        "package_mode": package_mode,
        "non_advice_boundary": NON_ADVICE_BOUNDARY,
    }

    sections["module_state"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="modules/equity_preview_run.json",
        schema="viza.equity.preview_run_package.v1",
    )
    payloads["module_state"] = _module_state_payload(detail, package_mode)

    sections["entity_snapshot"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="entities/entity_snapshot.json",
        schema="viza.equity.target_entity_snapshot.v1",
    )
    payloads["entity_snapshot"] = {
        "target": detail.target,
        "primary_key_policy": "CIK/internal entity IDs anchor the run; ticker is alias only.",
    }

    sections["radar_output"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="radar/equity_preview_output.json",
        schema="viza.equity.output_preview.v1",
    )
    payloads["radar_output"] = _radar_output_payload(detail, package_mode)

    sections["validation_proof"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="proof/validation_manifest.json",
        schema="viza.equity.validation_proof.v1",
    )
    payloads["validation_proof"] = {
        "schema": "viza.equity.validation_proof.v1",
        "run_id": detail.run_record.get("run_id"),
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "validation_report": detail.validation_report,
        "proof_checksum": proof_checksum,
        "non_advice_boundary_present": bool(
            _read_string(detail.output_preview.get("non_advice_boundary"))
        ),
    }

    sections["rights"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="rights/license_and_entitlements.json",
        schema="viza.equity.source_rights.v1",
    )
    payloads["rights"] = {
        "schema": "viza.equity.source_rights.v1",
        "source_rights_report": detail.source_rights_report,
        "package_redaction_preview": detail.package_redaction_preview,
        "rights_summary": _rights_summary(detail),
    }

    sections["audit_manifest"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="audit/run_manifest.json",
        schema="viza.equity.audit_manifest.v1",
    )
    payloads["audit_manifest"] = {
        "schema": "viza.equity.audit_manifest.v1",
        "run_id": detail.run_record.get("run_id"),
        "parent_run_id": detail.run_record.get("parent_run_id"),
        "created_from": detail.run_record.get("created_from"),
        "graph_hash": detail.audit.get("graph_hash"),
        "profile_hash": detail.audit.get("profile_hash"),
        "request_hash": detail.audit.get("request_hash"),
        "response_hash": detail.audit.get("response_hash"),
        "proof_checksum": proof_checksum,
        "pit_summary": _pit_summary(detail),
        "package_mode": package_mode,
    }

    sections["checksums"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="audit/checksums.json",
        schema="viza.equity.package_checksums.v1",
    )
    payloads["checksums"] = {
        "schema": "viza.equity.package_checksums.v1",
        "run_id": detail.run_record.get("run_id"),
        "proof_checksum": proof_checksum,
        "graph_hash": detail.audit.get("graph_hash"),
        "profile_hash": detail.audit.get("profile_hash"),
        "request_hash": detail.audit.get("request_hash"),
        "response_hash": detail.audit.get("response_hash"),
    }

    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id=f"viza-file-{uuid4()}",
        display_name=_display_name(detail, package_mode),
        object_kind="marketplace_draft"
        if package_mode == "marketplace_draft"
        else "equity_preview_package",
        primary_mode=package_mode,
        exchange_modes=[package_mode],
        visibility=visibility,
        created_at=timestamp,
        updated_at=timestamp,
        minimum_viza_version="0.2.0",
        required_modules=[
            VizaModuleRequirement(
                module_id="viza.finance.securities",
                version_range=">=0.1.0",
                required=True,
            ),
            VizaModuleRequirement(
                module_id=EQUITY_MODULE_ID,
                version_range=">=0.1.0",
                required=True,
            ),
        ],
        sections=sections,
        data_requirements={"required_connectors": _required_connectors(detail)},
        permissions=_permissions(package_mode),
        purpose="marketplace_draft"
        if package_mode == "marketplace_draft"
        else "equity_preview_package",
        creator=_creator(creator_id, creator_display_name),
        rights_summary=_rights_summary(detail),
        compliance_warnings=_compliance_warnings(detail, package_mode, warnings),
        readiness_checklist=_readiness(detail, package_mode),
        marketplace={
            "draft": package_mode == "marketplace_draft",
            "publish_status": "not_published",
            "monetization_enabled": False,
        },
        integrity={
            "signature_status": "unsigned",
            "redaction_policy": redaction_policy,
            "proof_checksum": proof_checksum,
            "non_advice_boundary_acknowledged": not_investment_advice_acknowledged,
            "marketplace_publish_status": "not_published"
            if package_mode == "marketplace_draft"
            else None,
        },
    )
    return manifest, payloads, warnings


def _target_path(
    detail: EquityPreviewRunDetail,
    request: EquityPreviewPackageDraftRequest,
) -> Path:
    if request.target_path:
        return Path(request.target_path)
    run_id = _read_string(detail.run_record.get("run_id"), "equity-preview-run")
    package_mode = request.package_mode
    export_dir = project_store_path().parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir / f"{run_id}-{package_mode}.viza"


def _visibility_for_mode(package_mode: EquityPreviewPackageMode) -> VisibilityMode:
    if package_mode == "white_box":
        return VisibilityMode.WHITE_BOX
    return VisibilityMode.OUTPUT_ONLY


def _equity_preview_graph(detail: EquityPreviewRunDetail) -> MethodologyGraph:
    timestamp = datetime.now(timezone.utc)
    run_id = _read_string(detail.run_record.get("run_id"), "equity-preview-run")
    return MethodologyGraph(
        methodology_id=f"viza-equity-preview-{run_id}",
        name="SEC-first equity preview workflow",
        description="Feature-flagged SEC-first equity research preview; not investment advice.",
        created_at=timestamp,
        updated_at=timestamp,
        nodes=[
            MethodologyNode(
                id="target_identity",
                type=VizaNodeType.UNIVERSE,
                position=GraphPosition(x=0, y=0),
                label="Target identity",
                config={
                    "entity_id": detail.target.get("entity_id"),
                    "cik": detail.target.get("cik"),
                    "ticker_alias": detail.target.get("ticker_alias"),
                    "ticker_primary_key": False,
                },
            ),
            MethodologyNode(
                id="sec_evidence",
                type=VizaNodeType.ATTRIBUTE,
                position=GraphPosition(x=220, y=0),
                label="SEC evidence",
                config={"source": "sec_public", "PIT_required": True},
            ),
            MethodologyNode(
                id="fundamentals",
                type=VizaNodeType.TRANSFORM,
                position=GraphPosition(x=440, y=0),
                label="Derived fundamentals",
                config={"rights_policy": "metadata_and_derived_allowed"},
            ),
            MethodologyNode(
                id="profile_check",
                type=VizaNodeType.SCORE,
                position=GraphPosition(x=660, y=0),
                label="quality_value_long_only compatibility",
                config={"profile_id": QUALITY_VALUE_PROFILE_ID},
            ),
            MethodologyNode(
                id="preview_output",
                type=VizaNodeType.OUTPUT_RADAR,
                position=GraphPosition(x=880, y=0),
                label="Equity preview output",
                config={"non_advice_boundary": NON_ADVICE_BOUNDARY},
            ),
        ],
        edges=[
            MethodologyEdge(id="e1", source="target_identity", target="sec_evidence"),
            MethodologyEdge(id="e2", source="sec_evidence", target="fundamentals"),
            MethodologyEdge(id="e3", source="fundamentals", target="profile_check"),
            MethodologyEdge(id="e4", source="profile_check", target="preview_output"),
        ],
        metadata={
            "module_id": EQUITY_MODULE_ID,
            "module_version": EQUITY_MODULE_VERSION,
            "run_id": run_id,
            "packaging_note": "Generated from persisted equity preview run.",
        },
    )


def _module_state_payload(
    detail: EquityPreviewRunDetail,
    package_mode: EquityPreviewPackageMode,
) -> dict[str, Any]:
    return {
        "schema": "viza.equity.preview_run_package.v1",
        "module_id": EQUITY_MODULE_ID,
        "module_version": EQUITY_MODULE_VERSION,
        "run_record": {
            "run_id": detail.run_record.get("run_id"),
            "run_type": detail.run_record.get("run_type"),
            "profile_id": detail.run_record.get("profile_id"),
            "target": detail.target,
            "input": detail.run_record.get("input"),
            "feature_flags": detail.run_record.get("feature_flags"),
            "connector_modes": detail.run_record.get("connector_modes"),
            "status": detail.run_record.get("status"),
            "warnings": detail.run_record.get("warnings"),
            "blocks": detail.run_record.get("blocks"),
            "created_from": detail.run_record.get("created_from"),
            "parent_run_id": detail.run_record.get("parent_run_id"),
        },
        "evidence_bundle": detail.evidence_bundle,
        "observations": _observations_for_package(detail, package_mode),
        "package_mode": package_mode,
        "non_advice_boundary": NON_ADVICE_BOUNDARY,
    }


def _radar_output_payload(
    detail: EquityPreviewRunDetail,
    package_mode: EquityPreviewPackageMode,
) -> dict[str, Any]:
    output_preview = dict(detail.output_preview)
    if package_mode == "marketplace_draft":
        output_preview["marketplace_draft"] = True
        output_preview["raw_provider_values_included"] = False
    return {
        "schema": "viza.equity.output_preview_package.v1",
        "run_id": detail.run_record.get("run_id"),
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "package_mode": package_mode,
        "output_preview": output_preview,
        "validation_status": detail.validation_report.get("status"),
        "rights_status": detail.source_rights_report.get("status"),
        "package_ready_status": _package_ready_status(detail.package_redaction_preview),
        "non_advice_boundary": _read_string(
            detail.output_preview.get("non_advice_boundary"),
            NON_ADVICE_BOUNDARY,
        ),
    }


def _observations_for_package(
    detail: EquityPreviewRunDetail,
    package_mode: EquityPreviewPackageMode,
) -> list[dict[str, Any]]:
    packaged: list[dict[str, Any]] = []
    for observation in detail.observations:
        connector_role = _read_string(observation.get("connector_role"))
        rights = observation.get("rights_policy") if isinstance(observation.get("rights_policy"), dict) else {}
        license_policy = _read_string(rights.get("license_policy"), "unknown")
        can_include_value = (
            package_mode == "white_box"
            and connector_role in {"sec_filings", "xbrl_facts", "fred_macro"}
            and license_policy != "dev_only_unconfirmed"
        )
        if package_mode != "white_box" and connector_role in {"sec_filings", "xbrl_facts"}:
            can_include_value = True
        row = {
            "observation_id": observation.get("observation_id"),
            "run_id": observation.get("run_id"),
            "entity_id": observation.get("entity_id"),
            "attribute_key": observation.get("attribute_key"),
            "value": observation.get("value") if can_include_value else "[redacted]",
            "value_redacted": not can_include_value,
            "unit": observation.get("unit"),
            "period_start": observation.get("period_start"),
            "period_end": observation.get("period_end"),
            "observed_at": observation.get("observed_at"),
            "available_at": observation.get("available_at"),
            "retrieved_at": observation.get("retrieved_at"),
            "source_id": observation.get("source_id"),
            "source_ref": observation.get("source_ref"),
            "source_version": observation.get("source_version"),
            "data_version": observation.get("data_version"),
            "model_version": observation.get("model_version"),
            "connector_role": connector_role,
            "PIT_safe": observation.get("PIT_safe"),
            "lookahead_risk": observation.get("lookahead_risk"),
            "rights_policy": rights,
        }
        packaged.append(row)
    return packaged


def _display_name(detail: EquityPreviewRunDetail, package_mode: str) -> str:
    target_name = _read_string(detail.target.get("display_name"), "Equity preview")
    return f"{target_name} equity preview package ({package_mode})"


def _pit_summary(detail: EquityPreviewRunDetail) -> dict[str, Any]:
    observations = detail.observations
    return {
        "status": detail.run_record.get("pit_status", "warn"),
        "observation_count": len(observations),
        "missing_available_at_count": sum(1 for item in observations if not item.get("available_at")),
        "not_backtest_safe_count": sum(
            1 for item in observations if item.get("PIT_safe") in {False, "false_for_backtest"}
        ),
        "lookahead_risks": sorted(
            {
                _read_string(item.get("lookahead_risk"))
                for item in observations
                if _read_string(item.get("lookahead_risk"))
            }
        ),
    }


def _rights_summary(detail: EquityPreviewRunDetail) -> dict[str, Any]:
    package_preview = detail.package_redaction_preview
    return {
        "status": detail.source_rights_report.get("status", "warn"),
        "policy_count": len(detail.source_rights_report.get("policies") or []),
        "included_count": len(package_preview.get("included") or []),
        "redacted_count": len(package_preview.get("redacted") or []),
        "blocked_count": len(package_preview.get("blocked") or []),
        "entitlement_locked_count": len(package_preview.get("entitlement_locked") or []),
        "policies": detail.source_rights_report.get("policies") or [],
    }


def _required_connectors(detail: EquityPreviewRunDetail) -> list[str]:
    connectors: list[str] = []
    for policy in detail.source_rights_report.get("policies") or []:
        if not isinstance(policy, dict):
            continue
        source = _read_string(policy.get("source"))
        if source == "sec_public":
            connectors.append("sec_filings")
        elif source == "fmp":
            connectors.append("licensed_market_data_connector")
        elif source == "fred":
            connectors.append("fred_macro")
    return list(dict.fromkeys(connectors))


def _permissions(package_mode: EquityPreviewPackageMode) -> dict[str, bool]:
    if package_mode == "white_box":
        return {
            "open_allowed": True,
            "run_allowed": False,
            "fork_allowed": False,
            "export_allowed": True,
            "redistribute_allowed": False,
            "marketplace_publish_allowed": False,
        }
    if package_mode == "output_only":
        return {
            "open_allowed": True,
            "run_allowed": False,
            "fork_allowed": False,
            "export_allowed": True,
            "redistribute_allowed": False,
            "marketplace_publish_allowed": False,
        }
    return {
        "open_allowed": True,
        "run_allowed": False,
        "fork_allowed": False,
        "export_allowed": False,
        "redistribute_allowed": False,
        "marketplace_publish_allowed": False,
    }


def _creator(creator_id: str | None, creator_display_name: str | None) -> dict[str, Any]:
    return {
        "creator_id": (creator_id or "local_unverified_creator").strip()
        or "local_unverified_creator",
        "display_name": (creator_display_name or "Local unverified creator").strip()
        or "Local unverified creator",
        "verification_status": "unverified",
        "metadata": {},
    }


def _compliance_warnings(
    detail: EquityPreviewRunDetail,
    package_mode: EquityPreviewPackageMode,
    warnings: list[str],
) -> list[dict[str, Any]]:
    labels = list(warnings)
    if package_mode == "marketplace_draft":
        labels.append("marketplace_draft_not_monetized")
    if detail.validation_report.get("status") == "block":
        labels.append("validation_status_block")
    if detail.source_rights_report.get("status") in {"warn", "block"}:
        labels.append("source_rights_require_review")
    return [
        {
            "code": label,
            "severity": "warning",
            "message": _warning_message(label),
        }
        for label in dict.fromkeys(labels)
    ]


def _warning_message(label: str) -> str:
    messages = {
        "marketplace_draft_not_monetized": "Marketplace draft is non-monetized and not publish-ready.",
        "validation_status_block": "Validation report contains blocking rules.",
        "source_rights_require_review": "Source rights include warnings or blocked/redacted components.",
        "fmp_dev_only_redacted": "FMP dev-only values are redacted or blocked in shared package modes.",
        "fred_latest_only_pit_warning": "FRED macro context is latest-only and not true PIT-safe for backtests.",
        "not_investment_advice": "Package output is a research preview, not investment advice.",
    }
    return messages.get(label, label)


def _readiness(
    detail: EquityPreviewRunDetail,
    package_mode: EquityPreviewPackageMode,
) -> dict[str, Any]:
    return {
        "preview_run_persisted": bool(detail.run_record.get("run_id")),
        "observations_linked": bool(detail.observations),
        "validation_report_present": bool(detail.validation_report),
        "source_rights_report_present": bool(detail.source_rights_report),
        "package_redaction_preview_present": bool(detail.package_redaction_preview),
        "non_advice_boundary_present": bool(detail.output_preview.get("non_advice_boundary")),
        "marketplace_publish_ready": False,
        "package_mode": package_mode,
    }


def _package_warnings(
    detail: EquityPreviewRunDetail,
    package_mode: EquityPreviewPackageMode,
) -> list[str]:
    warnings = ["not_investment_advice"]
    if any(
        _read_string((item.get("rights_policy") or {}).get("license_policy"))
        == "dev_only_unconfirmed"
        for item in detail.observations
        if isinstance(item.get("rights_policy"), dict)
    ):
        warnings.append("fmp_dev_only_redacted")
    if any(_read_string(item.get("connector_role")) == "fred_macro" for item in detail.observations):
        warnings.append("fred_latest_only_pit_warning")
    if package_mode == "marketplace_draft":
        warnings.append("marketplace_draft_not_monetized")
    return list(dict.fromkeys(warnings))


def _package_ready_status(package_preview: dict[str, Any]) -> str:
    blocked = package_preview.get("blocked") or []
    redacted = package_preview.get("redacted") or []
    entitlement_locked = package_preview.get("entitlement_locked") or []
    if blocked or redacted or entitlement_locked:
        return "exported_with_redactions_or_blocks"
    return "exported"


def _read_string(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) and value else fallback
