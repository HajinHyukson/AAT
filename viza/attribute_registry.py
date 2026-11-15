from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.attribute_expansion import (
    PHASE_13_REGISTRY_VERSION,
    phase_13_attribute_definitions,
)
from viza.config_paths import resolve_config_path, source_config_dir

VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION = "viza_attribute_registry_v1"
LEGACY_ATTRIBUTE_REGISTRY_SCHEMA_VERSIONS = {"viza_attribute_registry_v0"}
DEFAULT_REGISTRY_VERSION = PHASE_13_REGISTRY_VERSION
DEFAULT_ATTRIBUTE_REGISTRY_PATH = source_config_dir() / "viza_attribute_registry.json"


class AttributeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(min_length=1)
    family: str = Field(min_length=1)
    description: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_type: str = "internal_aat"
    frequency: str = "unknown"
    coverage: str = "starter"
    coverage_universe: str = "local_viza_starter_universes"
    freshness: str = "prototype_snapshot"
    timestamp_policy: str = "timestamp_available"
    availability_function: str = Field(min_length=1)
    point_in_time_status: str = Field(min_length=1)
    contribution_stage: str = Field(min_length=1)
    evidence_policy: str = Field(min_length=1)
    license_policy: str = Field(min_length=1)
    entitlement_policy: str = "internal"
    cache_policy: str = "local_cache_allowed"
    production_scoring_allowed: bool | None = None
    evidence_only: bool | None = None
    allowed_transforms: list[str] = Field(default_factory=list)
    compatible_node_types: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    owner: str = "aat"
    model_version: str = "prototype_v0"
    data_version: str = "local_or_prototype_v0"
    deprecation_status: str = "active"

    @model_validator(mode="after")
    def apply_v1_defaults(self) -> AttributeDefinition:
        is_evidence_only = self.contribution_stage == "evidence_only"
        if self.evidence_only is None:
            self.evidence_only = is_evidence_only
        if self.production_scoring_allowed is None:
            self.production_scoring_allowed = (
                not self.evidence_only
                and self.deprecation_status == "active"
                and self.contribution_stage in {"production", "research", "shadow"}
            )
        if not self.allowed_transforms:
            self.allowed_transforms = _default_allowed_transforms(self.unit)
        if not self.compatible_node_types:
            node_types = ["attribute", "filter", "output_radar", "relationship"]
            if self.production_scoring_allowed:
                node_types.append("score")
            self.compatible_node_types = node_types
        if self.evidence_only and not self.limitations:
            self.limitations = [
                "Evidence-only attributes require explicit user acknowledgement before scoring."
            ]
        return self


class AttributeRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION
    registry_version: str = DEFAULT_REGISTRY_VERSION
    description: str
    attributes: list[AttributeDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_registry(self) -> AttributeRegistry:
        if self.schema_version != VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION}"
            )
        keys = [attribute.key for attribute in self.attributes]
        duplicate_keys = sorted({key for key in keys if keys.count(key) > 1})
        if duplicate_keys:
            raise ValueError(f"duplicate attribute keys: {', '.join(duplicate_keys)}")
        return self

    def get(self, key: str) -> AttributeDefinition | None:
        return next((attribute for attribute in self.attributes if attribute.key == key), None)

    def require(self, key: str) -> AttributeDefinition:
        attribute = self.get(key)
        if attribute is None:
            raise KeyError(f"unknown VIZA attribute: {key}")
        return attribute

    def keys(self) -> set[str]:
        return {attribute.key for attribute in self.attributes}


def load_attribute_registry(path: str | Path | None = None) -> AttributeRegistry:
    registry_path = Path(path) if path is not None else resolve_config_path("viza_attribute_registry.json")
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    migrated_payload = _migrate_registry_payload(payload)
    if path is None or registry_path.resolve() == resolve_config_path("viza_attribute_registry.json").resolve():
        migrated_payload = _with_phase_13_attributes(migrated_payload)
    return AttributeRegistry.model_validate(migrated_payload)


def _migrate_registry_payload(payload: dict[str, Any]) -> dict[str, Any]:
    schema_version = payload.get("schema_version")
    if schema_version in LEGACY_ATTRIBUTE_REGISTRY_SCHEMA_VERSIONS:
        payload = {
            **payload,
            "schema_version": VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION,
            "registry_version": DEFAULT_REGISTRY_VERSION,
        }
    elif schema_version == VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION:
        payload = {
            **payload,
            "registry_version": payload.get("registry_version", DEFAULT_REGISTRY_VERSION),
        }
    return payload


def _with_phase_13_attributes(payload: dict[str, Any]) -> dict[str, Any]:
    attributes = payload.get("attributes")
    if not isinstance(attributes, list):
        return payload

    attributes_by_key = {
        attribute.get("key"): attribute
        for attribute in attributes
        if isinstance(attribute, dict) and isinstance(attribute.get("key"), str)
    }
    for attribute in phase_13_attribute_definitions():
        attributes_by_key.setdefault(attribute["key"], attribute)

    return {
        **payload,
        "registry_version": PHASE_13_REGISTRY_VERSION,
        "description": (
            "Phase 13 VIZA attribute registry with starter AAT attributes plus expanded "
            "baseline, macro, event, fundamental, exposure, and positioning research attributes."
        ),
        "attributes": list(attributes_by_key.values()),
    }


def _default_allowed_transforms(unit: str) -> list[str]:
    if unit in {"basis_points", "score", "usd", "count"}:
        return ["percentile_rank", "z_score", "absolute_value"]
    if unit == "boolean":
        return ["boolean_threshold"]
    return []
