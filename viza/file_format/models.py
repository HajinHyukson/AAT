from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.graph_schema import MethodologyGraph


VIZA_DOCUMENT_SCHEMA_VERSION = "viza.document.v1"
LEGACY_DOCUMENT_SCHEMA_ALIASES = frozenset({"viza_file_v0"})

CANONICAL_SECTION_NAMES = frozenset(
    {
        "methodology_graph",
        "strategy_profile",
        "strategy_profiles",
        "module_state",
        "entity_snapshot",
        "asset_universe_snapshot",
        "asset_map",
        "events",
        "insights",
        "translations",
        "radar_definition",
        "radar_output",
        "validation_proof",
        "signal_outputs",
        "rights",
        "audit_manifest",
        "checksums",
        "ui_layout",
        "creator_notes",
        "marketplace_metadata",
    }
)

DEFAULT_SECTION_PATHS: dict[str, str] = {
    "methodology_graph": "graph/methodology.json",
    "strategy_profile": "strategies/strategy_profile.json",
    "strategy_profiles": "strategies/strategy_profiles.json",
    "module_state": "modules/module_state.json",
    "entity_snapshot": "entities/entity_snapshot.json",
    "asset_universe_snapshot": "assets/universe_snapshot.json",
    "asset_map": "assets/asset_map.json",
    "events": "events/events.json",
    "insights": "insights/insights.json",
    "translations": "translations/translations.json",
    "radar_definition": "radar/radar_definition.json",
    "radar_output": "radar/radar_output.json",
    "validation_proof": "proof/validation_manifest.json",
    "signal_outputs": "signals/signal_outputs.json",
    "rights": "rights/license_and_entitlements.json",
    "audit_manifest": "audit/run_manifest.json",
    "checksums": "audit/checksums.json",
    "ui_layout": "ui/layout_state.json",
    "creator_notes": "notes/creator_notes.md",
    "marketplace_metadata": "marketplace/metadata.json",
}


class VizaFileError(ValueError):
    pass


class VizaFileSecurityError(VizaFileError):
    pass


class VizaManifestError(VizaFileError):
    pass


class VizaChecksumError(VizaFileError):
    pass


class VizaSectionUnavailableError(VizaFileError):
    pass


class SectionStatus(StrEnum):
    INCLUDED = "included"
    ABSENT = "absent"
    REDACTED = "redacted"
    ENTITLEMENT_LOCKED = "entitlement_locked"
    EXTERNAL_REFERENCE = "external_reference"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    DEPRECATED = "deprecated"
    CORRUPT = "corrupt"


class VisibilityMode(StrEnum):
    WHITE_BOX = "white_box"
    GRAY_BOX = "gray_box"
    BLACK_BOX = "black_box"
    OUTPUT_ONLY = "output_only"
    PREVIEW_ONLY = "preview_only"


class VizaSectionDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: SectionStatus
    path: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")
    checksum: str | None = None
    reason: str | None = None
    required_module_id: str | None = None
    required_module_version: str | None = None


class VizaModuleRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str = Field(min_length=1)
    version_range: str = "*"
    required: bool = True


class ProvAttribution(BaseModel):
    """Subset of W3C PROV applied to the .viza file manifest.

    Phase 26 of `docs/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`. Each
    field maps to a PROV predicate:

      file_entity_iri               -> prov:Entity (the .viza file itself)
      was_generated_by_activity_iri -> prov:wasGeneratedBy (the run/activity)
      was_attributed_to_agent_iri   -> prov:wasAttributedTo (the agent)
      generated_at_time             -> prov:generatedAtTime

    All fields are optional in MVP — legacy files written before Phase 26
    have no attribution, and the runtime must keep loading them. New files
    written by Phase 27 onwards populate them.
    """

    model_config = ConfigDict(extra="forbid")

    file_entity_iri: str | None = None
    was_generated_by_activity_iri: str | None = None
    was_attributed_to_agent_iri: str | None = None
    generated_at_time: datetime | None = None
    derived_from_iris: list[str] = Field(default_factory=list)


class VizaFileManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["viza.document.v1"] = Field(alias="schema")
    file_id: str = Field(min_length=1)
    display_name: str | None = None
    object_kind: str = Field(min_length=1)
    primary_mode: str | None = None
    exchange_modes: list[str] = Field(default_factory=list)
    visibility: VisibilityMode
    created_at: datetime
    updated_at: datetime
    minimum_viza_version: str = "0.2.0"
    required_modules: list[VizaModuleRequirement] = Field(default_factory=list)
    sections: dict[str, VizaSectionDescriptor] = Field(default_factory=dict)
    data_requirements: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)
    purpose: str = "methodology_graph"
    creator: dict[str, Any] = Field(default_factory=dict)
    rights_summary: dict[str, Any] = Field(default_factory=dict)
    compliance_warnings: list[dict[str, Any]] = Field(default_factory=list)
    readiness_checklist: dict[str, Any] = Field(default_factory=dict)
    marketplace: dict[str, Any] = Field(default_factory=dict)
    integrity: dict[str, Any] = Field(default_factory=dict)
    prov_attribution: ProvAttribution = Field(default_factory=ProvAttribution)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_schema_alias(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if value.get("schema") not in LEGACY_DOCUMENT_SCHEMA_ALIASES:
            return value
        migrated = dict(value)
        migrated["schema"] = VIZA_DOCUMENT_SCHEMA_VERSION
        integrity = dict(migrated.get("integrity") or {})
        integrity["migrated_from_schema"] = value.get("schema")
        migrated["integrity"] = integrity
        return migrated

    @model_validator(mode="after")
    def validate_manifest(self) -> VizaFileManifest:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self

    def section_statuses(self) -> dict[str, str]:
        return {name: descriptor.status.value for name, descriptor in self.sections.items()}


class VizaWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    file_id: str
    manifest_checksum: str
    container_checksum: str
    section_checksums: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class VizaSectionReadResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", populate_by_name=True)

    section_name: str
    path: str
    schema_name: str | None = Field(default=None, alias="schema")
    checksum: str | None = None
    content: bytes


class VizaInspectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    file_id: str | None = None
    status: str
    manifest: dict[str, Any] = Field(default_factory=dict)
    manifest_checksum: str | None = None
    container_checksum: str | None = None
    section_statuses: dict[str, str] = Field(default_factory=dict)
    entries: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    visualization: VizaFileVisualization | None = None


class VizaValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    inspection: VizaInspectionResult


class VizaFilePathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str

    def resolved_path(self) -> Path:
        return Path(self.path)


class VizaFileExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_path: str
    graph: MethodologyGraph | None = None
    project_id: str | None = None
    methodology_version_id: str | None = None
    run_id: str | None = None
    display_name: str | None = None
    purpose: str = "methodology_graph"
    visibility: VisibilityMode = VisibilityMode.WHITE_BOX
    include_sections: list[str] = Field(default_factory=lambda: ["methodology_graph"])
    include_validation_proof: bool = False
    include_signal_outputs: bool = False
    include_sample_outputs: bool = False
    redact_parameters: bool = False
    lock_sections: list[str] = Field(default_factory=list)
    creator_id: str | None = None
    creator_display_name: str | None = None
    source_rights: list[dict[str, Any]] = Field(default_factory=list)
    not_investment_advice_acknowledged: bool = False


class VizaFileExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: VizaWriteResult
    manifest: dict[str, Any]
    export_record: dict[str, Any] | None = None


class VizaFileImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    project_id: str | None = None
    mode: str = "import_to_project"
    save_methodology_version: bool = False
    label: str | None = None
    message: str | None = None


class VizaFileImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    source_path: str
    manifest: dict[str, Any]
    graph: MethodologyGraph | None = None
    import_record: dict[str, Any] | None = None
    methodology_version: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class VizaFileQuarantineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    reason: str = "manual_quarantine"


class VizaFileRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    imports: list[dict[str, Any]] = Field(default_factory=list)
    exports: list[dict[str, Any]] = Field(default_factory=list)


class VizaFileSectionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    sections: dict[str, VizaSectionDescriptor]


class VizaFileQuarantineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    quarantine_status: str
    records_updated: int


class VizaWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: str = "warning"


class VizaSectionVisualization(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    section_name: str
    status: str
    path: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")
    checksum: str | None = None
    reason: str | None = None
    readable: bool = False
    included_in_container: bool = False


class ModuleCompatibilityStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str
    required: bool = True
    version_range: str = "*"
    installed: bool
    installed_version: str | None = None
    status: str
    message: str


class VizaCompatibilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_status: str
    checksum_status: str
    missing_modules: list[str] = Field(default_factory=list)
    missing_connectors: list[str] = Field(default_factory=list)
    required_connectors: list[str] = Field(default_factory=list)
    permissions: dict[str, Any] = Field(default_factory=dict)


class VizaFileVisualization(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    file_id: str
    display_name: str | None = None
    object_kind: str
    visibility: str
    schema_name: str = Field(alias="schema")
    required_modules: list[ModuleCompatibilityStatus] = Field(default_factory=list)
    contents_map: dict[str, VizaSectionVisualization] = Field(default_factory=dict)
    compatibility: VizaCompatibilitySummary
    available_actions: list[str] = Field(default_factory=list)
    warnings: list[VizaWarning] = Field(default_factory=list)
    creator: dict[str, Any] = Field(default_factory=dict)
    compliance_warnings: list[VizaWarning] = Field(default_factory=list)
    readiness_checklist: dict[str, Any] = Field(default_factory=dict)
    marketplace: dict[str, Any] = Field(default_factory=dict)


VizaInspectionResult.model_rebuild()
VizaValidationResult.model_rebuild()
