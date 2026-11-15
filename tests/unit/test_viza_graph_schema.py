from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology_stub, validate_executable_graph
from viza.graph_schema import MethodologyGraph, load_methodology_graph
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH


def test_sample_methodology_graph_validates_against_schema() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)

    assert graph.schema_version == "viza_graph_v0"
    assert graph.name == "Residual Momentum Event Radar"
    assert len(graph.nodes) == 8
    assert len(graph.edges) == 9
    assert graph.attribute_keys() == [
        "momentum",
        "unexplained_residual_bps",
        "event_materiality",
    ]


def test_sample_methodology_graph_is_executable_shape() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()

    warnings = validate_executable_graph(graph, registry)
    result = run_methodology_stub(graph, registry)

    assert {warning.code for warning in warnings} == {"evidence_only_score_input"}
    assert result.status == "not_implemented"
    assert {warning.code for warning in result.warnings} == {
        "evidence_only_score_input",
        "execution_not_implemented",
    }


def test_graph_rejects_duplicate_node_ids() -> None:
    timestamp = datetime(2026, 5, 12, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="duplicate node ids"):
        MethodologyGraph(
            methodology_id="duplicate-node-test",
            name="Duplicate Node Test",
            created_at=timestamp,
            updated_at=timestamp,
            nodes=[
                {"id": "node-1", "type": "universe", "position": {"x": 0, "y": 0}},
                {"id": "node-1", "type": "output_radar", "position": {"x": 100, "y": 0}},
            ],
            edges=[],
        )


def test_graph_rejects_unsupported_schema_version() -> None:
    timestamp = datetime(2026, 5, 12, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="schema_version must be viza_graph_v0"):
        MethodologyGraph(
            schema_version="viza_graph_v1",
            methodology_id="unsupported-schema-test",
            name="Unsupported Schema Test",
            created_at=timestamp,
            updated_at=timestamp,
            nodes=[],
            edges=[],
        )


def test_graph_rejects_duplicate_edge_ids() -> None:
    timestamp = datetime(2026, 5, 12, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="duplicate edge ids"):
        MethodologyGraph(
            methodology_id="duplicate-edge-test",
            name="Duplicate Edge Test",
            created_at=timestamp,
            updated_at=timestamp,
            nodes=[
                {"id": "node-1", "type": "universe", "position": {"x": 0, "y": 0}},
                {"id": "node-2", "type": "output_radar", "position": {"x": 100, "y": 0}},
            ],
            edges=[
                {
                    "id": "edge-1",
                    "source": "node-1",
                    "target": "node-2",
                    "type": "data_flow",
                },
                {
                    "id": "edge-1",
                    "source": "node-1",
                    "target": "node-2",
                    "type": "relationship",
                },
            ],
        )


def test_graph_rejects_edges_that_reference_missing_nodes() -> None:
    timestamp = datetime(2026, 5, 12, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="target node does not exist"):
        MethodologyGraph(
            methodology_id="missing-edge-target-test",
            name="Missing Edge Target Test",
            created_at=timestamp,
            updated_at=timestamp,
            nodes=[
                {"id": "node-1", "type": "universe", "position": {"x": 0, "y": 0}},
            ],
            edges=[
                {
                    "id": "edge-1",
                    "source": "node-1",
                    "target": "node-2",
                    "type": "data_flow",
                }
            ],
        )


def test_graph_rejects_self_referential_edges() -> None:
    timestamp = datetime(2026, 5, 12, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="cannot connect a node to itself"):
        MethodologyGraph(
            methodology_id="self-edge-test",
            name="Self Edge Test",
            created_at=timestamp,
            updated_at=timestamp,
            nodes=[
                {"id": "node-1", "type": "universe", "position": {"x": 0, "y": 0}},
            ],
            edges=[
                {
                    "id": "edge-1",
                    "source": "node-1",
                    "target": "node-1",
                    "type": "data_flow",
                }
            ],
        )


def test_graph_rejects_updated_at_before_created_at() -> None:
    created_at = datetime(2026, 5, 12, tzinfo=timezone.utc)
    updated_at = datetime(2026, 5, 11, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="updated_at cannot be earlier than created_at"):
        MethodologyGraph(
            methodology_id="timestamp-order-test",
            name="Timestamp Order Test",
            created_at=created_at,
            updated_at=updated_at,
            nodes=[],
            edges=[],
        )
