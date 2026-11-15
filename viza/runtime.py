from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque

from pydantic import BaseModel, Field

from viza.graph_schema import MethodologyGraph, VizaEdgeType, VizaNodeType


class RuntimePlanWarning(BaseModel):
    code: str
    message: str
    node_id: str | None = None
    severity: str = "warning"


class ExecutionPlanStep(BaseModel):
    node_id: str
    node_type: VizaNodeType
    upstream_node_ids: list[str] = Field(default_factory=list)
    downstream_node_ids: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    graph_hash: str
    ordered_node_ids: list[str]
    steps: list[ExecutionPlanStep]
    warnings: list[RuntimePlanWarning] = Field(default_factory=list)


def compile_execution_plan(graph: MethodologyGraph) -> ExecutionPlan:
    graph_hash = hash_methodology_graph(graph)
    warnings: list[RuntimePlanWarning] = []
    node_by_id = {node.id: node for node in graph.nodes}
    order_index = {node.id: index for index, node in enumerate(graph.nodes)}
    data_edges = [edge for edge in graph.edges if edge.type == VizaEdgeType.DATA_FLOW]
    relationship_edges = [edge for edge in graph.edges if edge.type == VizaEdgeType.RELATIONSHIP]
    forward = _edge_map(data_edges, "source", "target")
    reverse = _edge_map(data_edges, "target", "source")

    warnings.extend(_validate_edge_semantics(graph))
    cycle_nodes = _cycle_nodes(data_edges)
    if cycle_nodes:
        warnings.append(
            RuntimePlanWarning(
                code="data_flow_cycle",
                message=f"Data-flow edges contain a cycle: {', '.join(cycle_nodes)}",
                severity="error",
            )
        )

    executable_node_ids: set[str] = set()
    output_nodes = graph.nodes_by_type(VizaNodeType.OUTPUT_RADAR)
    for output_node in output_nodes:
        ancestors = _collect_ancestors(output_node.id, reverse)
        if ancestors == {output_node.id}:
            warnings.append(
                RuntimePlanWarning(
                    code="unreachable_output",
                    message="Output Radar node has no upstream data-flow path.",
                    node_id=output_node.id,
                    severity="error",
                )
            )

        upstream_universe_ids = sorted(
            node_id
            for node_id in ancestors
            if node_by_id[node_id].type == VizaNodeType.UNIVERSE
        )
        if not upstream_universe_ids:
            warnings.append(
                RuntimePlanWarning(
                    code="missing_upstream_universe",
                    message="Output Radar node has no upstream Universe node.",
                    node_id=output_node.id,
                    severity="error",
                )
            )
        if len(upstream_universe_ids) > 1:
            warnings.append(
                RuntimePlanWarning(
                    code="ambiguous_upstream_universe",
                    message=(
                        "Output Radar node has multiple upstream universe nodes: "
                        f"{', '.join(upstream_universe_ids)}"
                    ),
                    node_id=output_node.id,
                    severity="error",
                )
            )

        executable_node_ids.update(ancestors)

    executable_output_ids = {
        node_id
        for node_id in executable_node_ids
        if node_by_id[node_id].type == VizaNodeType.OUTPUT_RADAR
    }
    for edge in relationship_edges:
        if edge.source in executable_output_ids:
            executable_node_ids.add(edge.target)

    disconnected_node_ids = [
        node.id
        for node in graph.nodes
        if node.id not in executable_node_ids
        and node.type not in {VizaNodeType.UNIVERSE, VizaNodeType.OUTPUT_RADAR}
    ]
    for node_id in disconnected_node_ids:
        warnings.append(
            RuntimePlanWarning(
                code="disconnected_node",
                message="Node is not on an executable path to an Output Radar node.",
                node_id=node_id,
            )
        )

    ordered_node_ids = _topological_order(
        data_edges=data_edges,
        executable_node_ids=executable_node_ids,
        order_index=order_index,
    )
    relationship_node_ids = sorted(
        [
            node_id
            for node_id in executable_node_ids
            if node_by_id[node_id].type == VizaNodeType.RELATIONSHIP
        ],
        key=lambda node_id: order_index[node_id],
    )
    ordered_node_ids.extend(
        node_id for node_id in relationship_node_ids if node_id not in ordered_node_ids
    )

    steps = [
        ExecutionPlanStep(
            node_id=node_id,
            node_type=node_by_id[node_id].type,
            upstream_node_ids=sorted(reverse.get(node_id, []), key=lambda item: order_index[item]),
            downstream_node_ids=sorted(forward.get(node_id, []), key=lambda item: order_index[item]),
        )
        for node_id in ordered_node_ids
    ]

    return ExecutionPlan(
        graph_hash=graph_hash,
        ordered_node_ids=ordered_node_ids,
        steps=steps,
        warnings=warnings,
    )


def hash_methodology_graph(graph: MethodologyGraph) -> str:
    payload = graph.model_dump(mode="json")
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _validate_edge_semantics(graph: MethodologyGraph) -> list[RuntimePlanWarning]:
    warnings: list[RuntimePlanWarning] = []
    for edge in graph.edges:
        source = graph.node_by_id(edge.source)
        target = graph.node_by_id(edge.target)
        if source is None or target is None:
            continue

        if target.type == VizaNodeType.UNIVERSE:
            warnings.append(
                RuntimePlanWarning(
                    code="invalid_edge_target",
                    message="Universe nodes cannot receive upstream inputs.",
                    node_id=target.id,
                    severity="error",
                )
            )
        if source.type == VizaNodeType.RELATIONSHIP:
            warnings.append(
                RuntimePlanWarning(
                    code="invalid_edge_source",
                    message="Relationship nodes are terminal outputs.",
                    node_id=source.id,
                    severity="error",
                )
            )
        if source.type == VizaNodeType.OUTPUT_RADAR and target.type != VizaNodeType.RELATIONSHIP:
            warnings.append(
                RuntimePlanWarning(
                    code="invalid_output_edge",
                    message="Output Radar nodes can only connect to Relationship nodes.",
                    node_id=source.id,
                    severity="error",
                )
            )
        if target.type == VizaNodeType.RELATIONSHIP and edge.type != VizaEdgeType.RELATIONSHIP:
            warnings.append(
                RuntimePlanWarning(
                    code="invalid_relationship_edge_type",
                    message="Relationship nodes require relationship edges from Output Radar nodes.",
                    node_id=target.id,
                    severity="error",
                )
            )
    return warnings


def _edge_map(edges: list, source_attr: str, target_attr: str) -> dict[str, set[str]]:
    output: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        output[getattr(edge, source_attr)].add(getattr(edge, target_attr))
    return output


def _collect_ancestors(node_id: str, reverse: dict[str, set[str]]) -> set[str]:
    seen = {node_id}
    stack = [node_id]
    while stack:
        current = stack.pop()
        for upstream in reverse.get(current, set()):
            if upstream not in seen:
                seen.add(upstream)
                stack.append(upstream)
    return seen


def _topological_order(
    data_edges: list,
    executable_node_ids: set[str],
    order_index: dict[str, int],
) -> list[str]:
    incoming_counts = {node_id: 0 for node_id in executable_node_ids}
    downstream: dict[str, set[str]] = defaultdict(set)
    for edge in data_edges:
        if edge.source not in executable_node_ids or edge.target not in executable_node_ids:
            continue
        downstream[edge.source].add(edge.target)
        incoming_counts[edge.target] += 1

    queue = deque(sorted(
        [node_id for node_id, count in incoming_counts.items() if count == 0],
        key=lambda node_id: order_index[node_id],
    ))
    ordered: list[str] = []
    while queue:
        node_id = queue.popleft()
        ordered.append(node_id)
        for downstream_node_id in sorted(downstream.get(node_id, []), key=lambda item: order_index[item]):
            incoming_counts[downstream_node_id] -= 1
            if incoming_counts[downstream_node_id] == 0:
                queue.append(downstream_node_id)

    if len(ordered) != len(incoming_counts):
        return sorted(executable_node_ids, key=lambda node_id: order_index[node_id])
    return ordered


def _cycle_nodes(data_edges: list) -> list[str]:
    forward = _edge_map(data_edges, "source", "target")
    visiting: set[str] = set()
    visited: set[str] = set()
    cycle: list[str] = []

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            cycle.append(node_id)
            return True
        if node_id in visited:
            return False

        visiting.add(node_id)
        for downstream_node_id in forward.get(node_id, set()):
            if visit(downstream_node_id):
                cycle.append(node_id)
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    for node_id in sorted(forward):
        if visit(node_id):
            return list(reversed(cycle))
    return []
