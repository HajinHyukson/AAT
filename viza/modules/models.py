from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from viza.file_format.models import VizaModuleRequirement


MODULE_MANIFEST_SCHEMA = "viza.module_manifest.v1"


class EntityTypeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_id: str
    display_name: str
    description: str | None = None
    identifiers: list[str] = Field(default_factory=list)
    visual: dict[str, Any] = Field(default_factory=dict)


class NodeTypeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_id: str
    display_name: str
    category: str
    extends: str
    description: str | None = None
    inspector_schema: dict[str, Any] = Field(default_factory=dict)
    allowed_incoming_edges: list[str] = Field(default_factory=list)
    allowed_outgoing_edges: list[str] = Field(default_factory=list)
    runtime_handler: str | None = None
    legacy_type: str | None = None
    visual: dict[str, Any] = Field(default_factory=dict)


class OutputViewDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view_id: str
    display_name: str
    description: str | None = None
    result_key: str | None = None
    visual: dict[str, Any] = Field(default_factory=dict)


class PaletteGroupDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    display_name: str
    node_types: list[str] = Field(default_factory=list)


class VizaModuleManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["viza.module_manifest.v1"] = Field(
        default=MODULE_MANIFEST_SCHEMA,
        alias="schema",
    )
    module_id: str
    module_version: str
    display_name: str
    domain: str
    description: str | None = None
    entity_types: dict[str, EntityTypeDefinition] = Field(default_factory=dict)
    node_types: dict[str, NodeTypeDefinition] = Field(default_factory=dict)
    edge_types: dict[str, dict[str, Any]] = Field(default_factory=dict)
    output_views: dict[str, OutputViewDefinition] = Field(default_factory=dict)
    data_connectors: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    runtime_handlers: dict[str, str] = Field(default_factory=dict)
    palette_groups: list[PaletteGroupDefinition] = Field(default_factory=list)


class ResolvedNodeType(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_type_id: str
    status: str
    module_id: str | None = None
    module_installed: bool = False
    node_type: NodeTypeDefinition | None = None
    legacy_type: str | None = None
    placeholder: dict[str, Any] | None = None
    message: str | None = None


class UnknownModuleNodePlaceholder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "module_not_installed"
    module_id: str
    node_type: str
    display_name: str = "Unknown Module Node"
    raw_config: dict[str, Any] = Field(default_factory=dict)
    editable: bool = False
    executable: bool = False


class ResolveNodeTypesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_ids: list[str] = Field(default_factory=list)


class ModuleCompatibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_modules: list[VizaModuleRequirement] = Field(default_factory=list)


class ModuleCompatibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str
    required: bool = True
    version_range: str = "*"
    installed: bool
    installed_version: str | None = None
    status: str
    message: str
