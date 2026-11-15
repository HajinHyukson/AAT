from __future__ import annotations

import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from viza.file_format import (
    export_methodology_graph_to_viza,
    inspect_viza_container,
    read_viza_manifest,
    read_viza_section,
)
from viza.file_format.models import VIZA_DOCUMENT_SCHEMA_VERSION, VizaChecksumError
from viza.graph_schema import MethodologyGraph
from viza.sample_data import load_sample_methodology_graph


def test_viza_container_writes_reads_and_inspects_manifest(tmp_path) -> None:
    graph = load_sample_methodology_graph()
    target = tmp_path / "arbitrary-name.bin"

    result, manifest = export_methodology_graph_to_viza(graph, target)
    loaded_manifest = read_viza_manifest(target)
    inspection = inspect_viza_container(target)
    section = read_viza_section(target, "methodology_graph")

    assert result.file_id == loaded_manifest.file_id
    assert manifest["schema"] == VIZA_DOCUMENT_SCHEMA_VERSION
    assert inspection.status == "ok"
    assert inspection.file_id == result.file_id
    assert inspection.section_statuses["methodology_graph"] == "included"
    assert "manifest.json" in inspection.entries
    assert "graph/methodology.json" in inspection.entries
    assert MethodologyGraph.model_validate_json(section.content) == graph


def test_manifest_only_inspection_does_not_load_corrupt_section(tmp_path) -> None:
    graph = load_sample_methodology_graph()
    target = tmp_path / "methodology.viza"
    corrupt_target = tmp_path / "methodology-corrupt.viza"
    export_methodology_graph_to_viza(graph, target)

    with ZipFile(target, mode="r") as source, ZipFile(
        corrupt_target,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as destination:
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "graph/methodology.json":
                payload = b'{"schema_version":"viza_graph_v0","corrupt":true}\n'
            destination.writestr(info.filename, payload)

    inspection = inspect_viza_container(corrupt_target)

    assert inspection.status == "ok"
    with pytest.raises(VizaChecksumError, match="checksum mismatch"):
        read_viza_section(corrupt_target, "methodology_graph")


def test_unsupported_manifest_schema_warns_without_loading_sections(tmp_path) -> None:
    target = tmp_path / "unsupported.viza"
    with ZipFile(target, mode="w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema": "viza.document.v99",
                    "file_id": "future-file",
                    "sections": {
                        "methodology_graph": {
                            "status": "included",
                            "path": "graph/methodology.json",
                        }
                    },
                }
            ),
        )
        zip_file.writestr("graph/methodology.json", b"not loaded during inspection")

    inspection = inspect_viza_container(target)

    assert inspection.status == "warning"
    assert inspection.file_id == "future-file"
    assert any("Unsupported VIZA file schema" in warning for warning in inspection.warnings)
