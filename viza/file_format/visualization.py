from __future__ import annotations

from viza.connectors import load_connector_catalog
from viza.file_format.models import (
    ModuleCompatibilityStatus,
    SectionStatus,
    VizaCompatibilitySummary,
    VizaFileManifest,
    VizaFileVisualization,
    VizaInspectionResult,
    VizaSectionVisualization,
    VizaWarning,
)
from viza.modules import get_module_registry


def build_file_visualization(
    manifest: VizaFileManifest,
    inspection: VizaInspectionResult | None = None,
) -> VizaFileVisualization:
    module_results = get_module_registry().check_compatibility(manifest.required_modules)
    required_modules = [
        ModuleCompatibilityStatus.model_validate(result.model_dump(mode="json"))
        for result in module_results
    ]
    missing_modules = [
        result.module_id
        for result in required_modules
        if result.required and not result.installed
    ]
    required_connectors = _required_connectors(manifest)
    installed_connectors = {connector.connector_id for connector in load_connector_catalog()}
    missing_connectors = [
        connector_id
        for connector_id in required_connectors
        if connector_id not in installed_connectors
    ]
    warnings = _visualization_warnings(
        manifest=manifest,
        inspection=inspection,
        missing_modules=missing_modules,
        missing_connectors=missing_connectors,
    )
    entries = set(inspection.entries if inspection is not None else [])
    checksum_status = "failed" if inspection is not None and inspection.errors else "passed"
    if inspection is not None and inspection.warnings:
        checksum_status = "warning"

    return VizaFileVisualization(
        file_id=manifest.file_id,
        display_name=manifest.display_name,
        object_kind=manifest.object_kind,
        visibility=manifest.visibility.value,
        schema=manifest.schema_name,
        required_modules=required_modules,
        contents_map={
            name: VizaSectionVisualization(
                section_name=name,
                status=descriptor.status.value,
                path=descriptor.path,
                schema=descriptor.schema_name,
                checksum=descriptor.checksum,
                reason=descriptor.reason,
                readable=descriptor.status == SectionStatus.INCLUDED and not missing_modules,
                included_in_container=bool(descriptor.path and descriptor.path in entries),
            )
            for name, descriptor in sorted(manifest.sections.items())
        },
        compatibility=VizaCompatibilitySummary(
            schema_status="supported",
            checksum_status=checksum_status,
            missing_modules=missing_modules,
            missing_connectors=missing_connectors,
            required_connectors=required_connectors,
            permissions=manifest.permissions,
        ),
        available_actions=_available_actions(
            manifest=manifest,
            missing_modules=missing_modules,
            missing_connectors=missing_connectors,
        ),
        warnings=warnings,
        creator=manifest.creator,
        compliance_warnings=_compliance_warnings(manifest),
        readiness_checklist=manifest.readiness_checklist,
        marketplace=manifest.marketplace,
    )


def _required_connectors(manifest: VizaFileManifest) -> list[str]:
    requirements = manifest.data_requirements.get("required_connectors")
    if not isinstance(requirements, list):
        return []
    return [item for item in requirements if isinstance(item, str)]


def _available_actions(
    *,
    manifest: VizaFileManifest,
    missing_modules: list[str],
    missing_connectors: list[str],
) -> list[str]:
    permissions = manifest.permissions
    actions = ["inspect"]
    if permissions.get("open_allowed", True):
        actions.append("open_without_import")
    if permissions.get("fork_allowed", True):
        actions.append("fork_as_new_methodology")
    if permissions.get("run_allowed", True) and not missing_modules and not missing_connectors:
        actions.append("run_locally")
    if permissions.get("export_allowed", True):
        actions.append("import_to_project")
    actions.append("quarantine")
    return list(dict.fromkeys(actions))


def _visualization_warnings(
    *,
    manifest: VizaFileManifest,
    inspection: VizaInspectionResult | None,
    missing_modules: list[str],
    missing_connectors: list[str],
) -> list[VizaWarning]:
    warnings: list[VizaWarning] = []
    warnings.extend(_compliance_warnings(manifest))
    if inspection is not None:
        warnings.extend(
            VizaWarning(code="inspection_warning", message=warning)
            for warning in inspection.warnings
        )
        warnings.extend(
            VizaWarning(code="inspection_error", message=error, severity="error")
            for error in inspection.errors
        )
    warnings.extend(
        VizaWarning(code="missing_module", message=f"Missing required module: {module_id}")
        for module_id in missing_modules
    )
    warnings.extend(
        VizaWarning(
            code="missing_connector",
            message=f"Missing required connector: {connector_id}",
        )
        for connector_id in missing_connectors
    )
    return warnings


def _compliance_warnings(manifest: VizaFileManifest) -> list[VizaWarning]:
    warnings: list[VizaWarning] = []
    for item in manifest.compliance_warnings:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        message = item.get("message")
        if not isinstance(code, str) or not isinstance(message, str):
            continue
        severity = item.get("severity")
        warnings.append(
            VizaWarning(
                code=code,
                message=message,
                severity=severity if isinstance(severity, str) else "warning",
            )
        )
    return warnings
