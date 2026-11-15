from __future__ import annotations

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology, validate_executable_graph
from viza.graph_schema import MethodologyGraph, load_methodology_graph
from viza.runtime import compile_execution_plan
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH


def test_runtime_compiler_orders_sample_graph_and_hashes_it() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)

    plan = compile_execution_plan(graph)

    assert len(plan.graph_hash) == 64
    assert plan.ordered_node_ids[0] == "universe-1"
    assert "score-1" in plan.ordered_node_ids
    assert plan.ordered_node_ids.index("score-1") < plan.ordered_node_ids.index("output-radar-1")
    assert plan.warnings == []


def test_runtime_rejects_data_flow_cycles() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    payload = graph.model_dump(mode="json")
    payload["edges"].append(
        {
            "id": "edge-score-back-to-momentum",
            "source": "score-1",
            "target": "attribute-momentum",
            "type": "data_flow",
        }
    )

    result = run_methodology(MethodologyGraph.model_validate(payload), registry)

    assert result.status == "failed"
    assert "data_flow_cycle" in {warning.code for warning in result.warnings}


def test_disconnected_attribute_nodes_do_not_change_scores() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    baseline = run_methodology(graph, registry)

    payload = graph.model_dump(mode="json")
    payload["nodes"].append(
        {
            "id": "attribute-liquidity-disconnected",
            "type": "attribute",
            "position": {"x": 320, "y": 460},
            "label": "Disconnected Liquidity",
            "config": {
                "attribute_key": "liquidity",
                "lookback_days": 30,
                "missing_data": "warn_and_exclude_from_score",
            },
        }
    )
    score_node = next(node for node in payload["nodes"] if node["id"] == "score-1")
    score_node["config"]["weights"]["liquidity"] = 99

    changed = run_methodology(MethodologyGraph.model_validate(payload), registry)

    assert changed.status == "completed"
    assert [row.ticker for row in changed.rows] == [row.ticker for row in baseline.rows]
    assert [row.score for row in changed.rows] == [row.score for row in baseline.rows]
    assert any(
        warning.code == "disconnected_node"
        and warning.node_id == "attribute-liquidity-disconnected"
        for warning in changed.warnings
    )


def test_output_only_attribute_weights_do_not_change_scores() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    baseline = run_methodology(graph, registry)

    payload = graph.model_dump(mode="json")
    payload["nodes"].append(
        {
            "id": "attribute-liquidity-output-only",
            "type": "attribute",
            "position": {"x": 320, "y": 460},
            "label": "Output Liquidity",
            "config": {
                "attribute_key": "liquidity",
                "lookback_days": 30,
                "missing_data": "warn_and_exclude_from_score",
            },
        }
    )
    payload["edges"].append(
        {
            "id": "edge-liquidity-output-only",
            "source": "attribute-liquidity-output-only",
            "target": "output-radar-1",
            "type": "data_flow",
        }
    )
    score_node = next(node for node in payload["nodes"] if node["id"] == "score-1")
    score_node["config"]["weights"]["liquidity"] = 99

    changed = run_methodology(MethodologyGraph.model_validate(payload), registry)

    assert changed.status == "completed"
    assert [row.ticker for row in changed.rows] == [row.ticker for row in baseline.rows]
    assert [row.score for row in changed.rows] == [row.score for row in baseline.rows]
    assert any(
        warning.code == "ignored_score_weight" and warning.node_id == "score-1"
        for warning in changed.warnings
    )


def test_runtime_returns_structured_error_when_output_has_no_upstream_universe() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    payload = graph.model_dump(mode="json")
    payload["edges"] = [
        edge
        for edge in payload["edges"]
        if edge["source"] != "universe-1" and edge["target"] != "universe-1"
    ]

    result = run_methodology(MethodologyGraph.model_validate(payload), registry)

    assert result.status == "failed"
    assert "missing_upstream_universe" in {warning.code for warning in result.warnings}


def test_graph_hash_ignores_volatile_timestamps() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    payload = graph.model_dump(mode="json")
    payload["updated_at"] = "2026-05-13T00:00:00Z"
    changed_timestamp_graph = MethodologyGraph.model_validate(payload)

    assert compile_execution_plan(graph).graph_hash == compile_execution_plan(
        changed_timestamp_graph
    ).graph_hash


def test_runtime_result_includes_manifest_and_node_results() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()

    result = run_methodology(graph, registry)

    assert result.graph_hash == result.manifest["graph_hash"]
    assert result.manifest["runtime_version"] == "viza_runtime_phase_10_audit_v0"
    assert result.manifest["run_id"] == result.run_id
    assert result.result_checksum == result.manifest["result_checksum"]
    assert len(result.result_checksum) == 64
    assert len(result.manifest["evidence_checksum"]) == 64
    assert result.manifest["run_started_at"]
    assert result.manifest["run_finished_at"]
    assert result.manifest["registry_version"] == "1.1.0"
    assert result.manifest["attribute_registry_schema_version"] == "viza_attribute_registry_v1"
    assert "local_viza_workspace" in result.manifest["connectors"]
    assert result.manifest["connector_states"]["local_viza_workspace"] == "available"
    assert "deterministic_prototype_v0" in result.manifest["data_versions"]
    assert "phase_4_deterministic_resolver_v0" in result.manifest["model_versions"]
    assert "momentum" in result.manifest["connectors"]["local_viza_workspace"]["attribute_keys"]
    assert result.node_results
    assert {node.node_id for node in result.node_results}.issuperset(
        {"universe-1", "score-1", "output-radar-1"}
    )


def test_runtime_warns_when_registry_disallows_transform() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    payload = graph.model_dump(mode="json")
    sector_node = next(node for node in payload["nodes"] if node["id"] == "attribute-momentum")
    sector_node["label"] = "Sector"
    sector_node["config"]["attribute_key"] = "sector"

    warnings = validate_executable_graph(MethodologyGraph.model_validate(payload), registry)

    assert any(
        warning.code == "incompatible_attribute_transform"
        and warning.node_id == "transform-percentile-ranks"
        for warning in warnings
    )


def test_score_node_can_explicitly_acknowledge_evidence_only_inputs() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    payload = graph.model_dump(mode="json")
    score_node = next(node for node in payload["nodes"] if node["id"] == "score-1")
    score_node["config"]["allow_evidence_only"] = True

    result = run_methodology(MethodologyGraph.model_validate(payload), registry)

    assert result.status == "completed"
    assert "evidence_only_score_input" not in {warning.code for warning in result.warnings}


def test_runtime_result_checksum_is_stable_for_same_graph_and_versions() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()

    first = run_methodology(graph, registry)
    second = run_methodology(graph, registry)

    assert first.result_checksum == second.result_checksum
    assert first.manifest["result_checksum"] == second.manifest["result_checksum"]
    assert first.manifest["data_versions"] == second.manifest["data_versions"]
