from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from viza.file_format.container import read_viza_section, write_viza_container
from viza.file_format.models import (
    CANONICAL_SECTION_NAMES,
    SectionStatus,
    VisibilityMode,
    VizaFileManifest,
    VizaModuleRequirement,
    VizaSectionDescriptor,
    VizaWriteResult,
)
from viza.graph_schema import MethodologyGraph, VIZA_GRAPH_SCHEMA_VERSION


def legacy_graph_json_to_viza_manifest(graph: dict[str, Any]) -> VizaFileManifest:
    methodology_graph = MethodologyGraph.model_validate(graph)
    sections = {
        section_name: VizaSectionDescriptor(
            status=SectionStatus.ABSENT,
            reason="not_included",
        )
        for section_name in CANONICAL_SECTION_NAMES
    }
    sections["methodology_graph"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="graph/methodology.json",
        schema=VIZA_GRAPH_SCHEMA_VERSION,
    )

    timestamp = datetime.now(timezone.utc)
    return VizaFileManifest(
        schema="viza.document.v1",
        file_id=f"viza-file-{uuid4()}",
        display_name=methodology_graph.name,
        object_kind="methodology",
        primary_mode="methodology_graph",
        exchange_modes=["methodology_graph"],
        visibility=VisibilityMode.WHITE_BOX,
        created_at=timestamp,
        updated_at=timestamp,
        minimum_viza_version="0.2.0",
        required_modules=[
            VizaModuleRequirement(
                module_id="viza.finance.securities",
                version_range=">=0.1.0",
                required=True,
            )
        ],
        sections=sections,
        permissions={
            "open_allowed": True,
            "run_allowed": True,
            "fork_allowed": True,
            "export_allowed": True,
            "redistribute_allowed": False,
        },
        integrity={"signature_status": "unsigned"},
    )


def wrap_legacy_graph_json(path: str | Path, target_path: str | Path) -> VizaWriteResult:
    graph_path = Path(path)
    graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
    graph = MethodologyGraph.model_validate(graph_payload)
    manifest = legacy_graph_json_to_viza_manifest(graph.model_dump(mode="json"))
    return write_viza_container(
        target_path,
        manifest,
        {"methodology_graph": graph.model_dump(mode="json")},
    )


def unwrap_methodology_graph_from_viza(path: str | Path) -> MethodologyGraph:
    section = read_viza_section(path, "methodology_graph")
    return MethodologyGraph.model_validate_json(section.content)
