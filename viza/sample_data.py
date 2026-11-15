from __future__ import annotations

from pathlib import Path

from viza.attribute_registry import AttributeRegistry
from viza.attribute_registry import load_attribute_registry as _load_attribute_registry
from viza.graph_schema import MethodologyGraph, load_methodology_graph


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_METHODOLOGY_GRAPH_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "viza" / "residual_momentum_event_radar.json"
)


def load_sample_methodology_graph() -> MethodologyGraph:
    return load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)


def load_starter_attribute_registry() -> AttributeRegistry:
    return _load_attribute_registry()
