from __future__ import annotations

import zipfile

import pytest
from fastapi.testclient import TestClient

from viza.file_format.container import read_viza_manifest, read_viza_section
from viza.file_format.export import export_methodology_graph_to_viza
from viza.file_format.models import VisibilityMode, VizaSectionUnavailableError
from viza.file_format.visualization import build_file_visualization
from viza.graph_schema import MethodologyGraph, load_methodology_graph
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app


client = TestClient(app)


def _graph() -> MethodologyGraph:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    payload = graph.model_dump(mode="json")
    score_node = next(node for node in payload["nodes"] if node["id"] == "score-1")
    score_node["config"]["weights"] = {"proprietary_alpha": 0.12345}
    score_node["config"]["proprietary_notes"] = "do not leak"
    return MethodologyGraph.model_validate(payload)


def test_white_box_package_includes_graph(tmp_path) -> None:
    target = tmp_path / "white-box.viza"

    export_methodology_graph_to_viza(_graph(), target, visibility=VisibilityMode.WHITE_BOX)

    manifest = read_viza_manifest(target)
    section = read_viza_section(target, "methodology_graph")
    assert manifest.visibility == VisibilityMode.WHITE_BOX
    assert manifest.sections["methodology_graph"].status.value == "included"
    assert b"proprietary_alpha" in section.content


def test_gray_box_redacts_parameters_but_keeps_graph(tmp_path) -> None:
    target = tmp_path / "gray-box.viza"

    export_methodology_graph_to_viza(_graph(), target, visibility=VisibilityMode.GRAY_BOX)

    section = read_viza_section(target, "methodology_graph")
    assert b"proprietary_alpha" not in section.content
    assert b"do not leak" not in section.content
    assert b"[redacted]" in section.content


def test_black_box_excludes_graph_bytes_and_disables_actions(tmp_path) -> None:
    target = tmp_path / "black-box.viza"

    export_methodology_graph_to_viza(_graph(), target, visibility=VisibilityMode.BLACK_BOX)
    manifest = read_viza_manifest(target)
    visualization = build_file_visualization(manifest)

    with zipfile.ZipFile(target) as archive:
        assert "graph/methodology.json" not in archive.namelist()
    assert manifest.sections["methodology_graph"].status.value == "redacted"
    assert "fork_as_new_methodology" not in visualization.available_actions
    assert "run_locally" not in visualization.available_actions
    with pytest.raises(VizaSectionUnavailableError):
        read_viza_section(target, "methodology_graph")


def test_output_only_includes_outputs_only(tmp_path) -> None:
    target = tmp_path / "output-only.viza"

    export_methodology_graph_to_viza(_graph(), target, visibility=VisibilityMode.OUTPUT_ONLY)
    manifest = read_viza_manifest(target)

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
    assert "radar/radar_output.json" in names
    assert "graph/methodology.json" not in names
    assert manifest.sections["radar_output"].status.value == "included"


def test_entitlement_locked_sections_are_not_bundled(tmp_path) -> None:
    target = tmp_path / "locked.viza"

    export_methodology_graph_to_viza(
        _graph(),
        target,
        visibility=VisibilityMode.WHITE_BOX,
        lock_sections=["methodology_graph"],
    )
    manifest = read_viza_manifest(target)

    with zipfile.ZipFile(target) as archive:
        assert "graph/methodology.json" not in archive.namelist()
    assert manifest.sections["methodology_graph"].status.value == "entitlement_locked"


def test_import_open_respects_black_box_permissions(tmp_path) -> None:
    target = tmp_path / "black-box-import.viza"
    export_methodology_graph_to_viza(_graph(), target, visibility=VisibilityMode.BLACK_BOX)

    open_response = client.post(
        "/viza/files/import",
        json={"path": str(target), "mode": "open_without_import"},
    )
    fork_response = client.post(
        "/viza/files/import",
        json={"path": str(target), "mode": "fork_as_new_methodology"},
    )

    assert open_response.status_code == 200
    assert open_response.json()["graph"] is None
    assert fork_response.status_code == 400
    assert "does not allow forking" in fork_response.text
