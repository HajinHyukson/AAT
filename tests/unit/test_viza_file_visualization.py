from __future__ import annotations

from fastapi.testclient import TestClient

from viza.file_format.container import write_viza_container
from viza.file_format.legacy import legacy_graph_json_to_viza_manifest
from viza.file_format.models import VizaModuleRequirement
from viza.project_store import get_project_store
from viza.sample_data import load_sample_methodology_graph
from viza.service import app


client = TestClient(app)


def test_inspect_returns_visualization_payload(tmp_path) -> None:
    graph = load_sample_methodology_graph()
    manifest = legacy_graph_json_to_viza_manifest(graph.model_dump(mode="json"))
    target = tmp_path / "opaque-name.data"
    write_viza_container(target, manifest, {"methodology_graph": graph.model_dump(mode="json")})

    response = client.post("/viza/files/inspect", json={"path": str(target)})

    assert response.status_code == 200
    payload = response.json()
    visualization = payload["visualization"]
    assert visualization["file_id"] == payload["file_id"]
    assert visualization["object_kind"] == "methodology"
    assert visualization["contents_map"]["methodology_graph"]["status"] == "included"
    assert "open_without_import" in visualization["available_actions"]
    assert "run_locally" in visualization["available_actions"]


def test_visualization_reports_missing_modules_and_connectors(tmp_path) -> None:
    graph = load_sample_methodology_graph()
    manifest = legacy_graph_json_to_viza_manifest(graph.model_dump(mode="json"))
    manifest.required_modules.append(
        VizaModuleRequirement(
            module_id="viza.real_estate.acquisition",
            version_range=">=0.1.0",
            required=True,
        )
    )
    manifest.data_requirements = {"required_connectors": ["made_up_connector"]}
    target = tmp_path / "missing-module.viza"
    write_viza_container(target, manifest, {"methodology_graph": graph.model_dump(mode="json")})

    response = client.post("/viza/files/inspect", json={"path": str(target)})

    assert response.status_code == 200
    visualization = response.json()["visualization"]
    assert "viza.real_estate.acquisition" in visualization["compatibility"]["missing_modules"]
    assert "made_up_connector" in visualization["compatibility"]["missing_connectors"]
    assert "run_locally" not in visualization["available_actions"]
    assert any(warning["code"] == "missing_module" for warning in visualization["warnings"])


def test_import_modes_open_fork_and_quarantine(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    project = get_project_store().ensure_default_project()
    graph = load_sample_methodology_graph()
    target = tmp_path / "strategy.viza"
    write_viza_container(
        target,
        legacy_graph_json_to_viza_manifest(graph.model_dump(mode="json")),
        {"methodology_graph": graph.model_dump(mode="json")},
    )

    open_response = client.post(
        "/viza/files/import",
        json={"path": str(target), "mode": "open_without_import"},
    )
    assert open_response.status_code == 200
    assert open_response.json()["import_record"] is None

    fork_response = client.post(
        "/viza/files/import",
        json={
            "path": str(target),
            "project_id": project.project_id,
            "mode": "fork_as_new_methodology",
        },
    )
    assert fork_response.status_code == 200
    assert fork_response.json()["graph"]["methodology_id"] != graph.methodology_id
    assert fork_response.json()["methodology_version"] is not None

    quarantine_response = client.post(
        "/viza/files/import",
        json={
            "path": str(target),
            "project_id": project.project_id,
            "mode": "quarantine",
        },
    )
    assert quarantine_response.status_code == 200
    assert quarantine_response.json()["import_record"]["quarantine_status"] == "quarantined"


def test_file_visualization_endpoint_uses_recorded_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    project = get_project_store().ensure_default_project()
    graph = load_sample_methodology_graph()
    target = tmp_path / "exported.viza"

    export_response = client.post(
        "/viza/files/export",
        json={
            "target_path": str(target),
            "graph": graph.model_dump(mode="json"),
            "project_id": project.project_id,
            "purpose": "collaboration",
            "visibility": "white_box",
            "include_sections": ["methodology_graph"],
        },
    )
    assert export_response.status_code == 200
    file_id = export_response.json()["result"]["file_id"]

    visualization_response = client.get(f"/viza/files/{file_id}/visualization")

    assert visualization_response.status_code == 200
    assert visualization_response.json()["file_id"] == file_id
    assert visualization_response.json()["contents_map"]["methodology_graph"]["status"] == "included"
