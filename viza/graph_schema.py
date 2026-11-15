from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


VIZA_GRAPH_SCHEMA_VERSION = "viza_graph_v0"

OUTPUT_RADAR_DEFAULT_MODE = "sandbox_replay"
OUTPUT_RADAR_SUPPORTED_MODES = ("sandbox_replay", "live")


class VizaNodeType(StrEnum):
    UNIVERSE = "universe"
    ATTRIBUTE = "attribute"
    TRANSFORM = "transform"
    FILTER = "filter"
    SCORE = "score"
    RELATIONSHIP = "relationship"
    OUTPUT_RADAR = "output_radar"


class VizaEdgeType(StrEnum):
    DATA_FLOW = "data_flow"
    RELATIONSHIP = "relationship"
    EVIDENCE = "evidence"


class GraphPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class MethodologyNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: VizaNodeType
    position: GraphPosition
    label: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class MethodologyEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: VizaEdgeType = VizaEdgeType.DATA_FLOW
    config: dict[str, Any] = Field(default_factory=dict)


class MethodologyGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = VIZA_GRAPH_SCHEMA_VERSION
    methodology_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    nodes: list[MethodologyNode] = Field(default_factory=list)
    edges: list[MethodologyEdge] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_shape(self) -> MethodologyGraph:
        if self.schema_version != VIZA_GRAPH_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {VIZA_GRAPH_SCHEMA_VERSION}")

        node_ids = [node.id for node in self.nodes]
        duplicate_node_ids = sorted(
            {node_id for node_id in node_ids if node_ids.count(node_id) > 1}
        )
        if duplicate_node_ids:
            raise ValueError(f"duplicate node ids: {', '.join(duplicate_node_ids)}")

        edge_ids = [edge.id for edge in self.edges]
        duplicate_edge_ids = sorted(
            {edge_id for edge_id in edge_ids if edge_ids.count(edge_id) > 1}
        )
        if duplicate_edge_ids:
            raise ValueError(f"duplicate edge ids: {', '.join(duplicate_edge_ids)}")

        known_node_ids = set(node_ids)
        for edge in self.edges:
            if edge.source not in known_node_ids:
                raise ValueError(f"edge {edge.id} source node does not exist: {edge.source}")
            if edge.target not in known_node_ids:
                raise ValueError(f"edge {edge.id} target node does not exist: {edge.target}")
            if edge.source == edge.target:
                raise ValueError(f"edge {edge.id} cannot connect a node to itself")

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")

        return self

    def node_by_id(self, node_id: str) -> MethodologyNode | None:
        return next((node for node in self.nodes if node.id == node_id), None)

    def nodes_by_type(self, node_type: VizaNodeType) -> list[MethodologyNode]:
        return [node for node in self.nodes if node.type == node_type]

    def attribute_keys(self) -> list[str]:
        keys: list[str] = []
        for node in self.nodes_by_type(VizaNodeType.ATTRIBUTE):
            attribute_key = node.config.get("attribute_key")
            if isinstance(attribute_key, str):
                keys.append(attribute_key)
        return keys


def output_radar_mode(node: MethodologyNode) -> str:
    """Return the output_radar mode declared on the node.

    Defaults to ``sandbox_replay`` when unset. Live mode (``live``) is
    supported as of Phase C.2 of
    ``docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md``; live activation is gated
    on ``VIZA_LIVE_MODE_ENABLED=true`` and a per-profile opt-in enforced by
    ``viza.decisions._enforce_live_mode_preconditions``. Raises
    ``ValueError`` for unknown modes.
    """
    if node.type is not VizaNodeType.OUTPUT_RADAR:
        raise ValueError(f"node {node.id} is not an output_radar node")
    raw_mode = node.config.get("mode", OUTPUT_RADAR_DEFAULT_MODE)
    if not isinstance(raw_mode, str):
        raise ValueError(f"output_radar mode on node {node.id} must be a string")
    if raw_mode not in OUTPUT_RADAR_SUPPORTED_MODES:
        raise ValueError(
            f"unknown output_radar mode={raw_mode!r} on node {node.id}; "
            f"supported: {OUTPUT_RADAR_SUPPORTED_MODES}"
        )
    return raw_mode


def load_methodology_graph(path: str | Path) -> MethodologyGraph:
    graph_path = Path(path)
    return MethodologyGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))


def dump_methodology_graph(graph: MethodologyGraph, path: str | Path) -> None:
    graph_path = Path(path)
    graph_path.write_text(
        json.dumps(graph.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
