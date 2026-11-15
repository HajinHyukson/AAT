from __future__ import annotations

import json
from pathlib import Path

from viza.file_format.container import read_viza_manifest
from viza.file_format.legacy import legacy_graph_json_to_viza_manifest, unwrap_methodology_graph_from_viza
from viza.graph_schema import MethodologyGraph


def import_viza_methodology_graph(path: str | Path) -> tuple[MethodologyGraph, dict]:
    source_path = Path(path)
    if source_path.name.endswith(".viza.json"):
        graph_payload = json.loads(source_path.read_text(encoding="utf-8"))
        graph = MethodologyGraph.model_validate(graph_payload)
        manifest = legacy_graph_json_to_viza_manifest(graph.model_dump(mode="json"))
        return graph, manifest.model_dump(mode="json", by_alias=True)

    manifest = read_viza_manifest(source_path)
    graph = unwrap_methodology_graph_from_viza(source_path)
    return graph, manifest.model_dump(mode="json", by_alias=True)
