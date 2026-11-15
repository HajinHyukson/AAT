from __future__ import annotations

import json

import pytest

from viza.attribute_registry import (
    AttributeRegistry,
    DEFAULT_REGISTRY_VERSION,
    VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION,
    load_attribute_registry,
)
from viza.graph_schema import load_methodology_graph
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH


def test_starter_attribute_registry_loads() -> None:
    registry = load_attribute_registry()

    assert registry.schema_version == "viza_attribute_registry_v1"
    assert registry.registry_version == DEFAULT_REGISTRY_VERSION
    assert 40 <= len(registry.attributes) <= 80
    assert registry.require("unexplained_residual_bps").family == "attribution"
    assert registry.require("event_materiality").evidence_policy == "event_reference"
    assert registry.require("event_materiality").evidence_only is True
    assert registry.require("event_materiality").production_scoring_allowed is False
    assert "percentile_rank" in registry.require("momentum").allowed_transforms
    assert registry.require("market_contribution_bps").contribution_stage == "production"
    assert registry.require("yield_10y_change_bps").family == "macro"
    assert registry.require("quality").family == "fundamental"
    assert registry.require("short_interest").evidence_only is True
    assert registry.require("short_interest").entitlement_policy == (
        "query_only_no_export_credential_required"
    )
    assert registry.require("short_interest").limitations


def test_registry_rejects_duplicate_keys() -> None:
    attribute = load_attribute_registry().attributes[0].model_dump()

    with pytest.raises(ValueError, match="duplicate attribute keys"):
        AttributeRegistry(
            schema_version=VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION,
            description="Invalid duplicate registry",
            attributes=[attribute, attribute],
        )


def test_legacy_v0_registry_payload_migrates_to_v1(tmp_path) -> None:
    attribute = load_attribute_registry().attributes[0].model_dump()
    legacy_path = tmp_path / "legacy_registry.json"
    for key in [
        "source_type",
        "frequency",
        "coverage",
        "coverage_universe",
        "freshness",
        "timestamp_policy",
        "entitlement_policy",
        "cache_policy",
        "production_scoring_allowed",
        "evidence_only",
        "allowed_transforms",
        "compatible_node_types",
        "diagnostics",
        "limitations",
        "owner",
        "model_version",
        "data_version",
        "deprecation_status",
    ]:
        attribute.pop(key, None)

    legacy_path.write_text(
        json.dumps(
            {
                "schema_version": "viza_attribute_registry_v0",
                "description": "Legacy registry",
                "attributes": [attribute],
            }
        ),
        encoding="utf-8",
    )

    registry = load_attribute_registry(legacy_path)

    assert registry.schema_version == "viza_attribute_registry_v1"
    assert registry.registry_version == DEFAULT_REGISTRY_VERSION
    assert registry.attributes[0].source_type == "internal_aat"


def test_sample_graph_attribute_nodes_exist_in_registry() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()

    assert set(graph.attribute_keys()).issubset(registry.keys())
