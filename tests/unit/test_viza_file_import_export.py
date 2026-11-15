from __future__ import annotations

from fastapi.testclient import TestClient

from viza.file_format import unwrap_methodology_graph_from_viza, wrap_legacy_graph_json
from viza.graph_schema import dump_methodology_graph
from viza.project_store import get_project_store
from viza.sample_data import load_sample_methodology_graph
from viza.service import app


client = TestClient(app)


def test_legacy_viza_json_wraps_and_unwraps_without_graph_loss(tmp_path) -> None:
    graph = load_sample_methodology_graph()
    legacy_path = tmp_path / "legacy-methodology.viza.json"
    target = tmp_path / "not-semantic-extension.data"
    dump_methodology_graph(graph, legacy_path)

    result = wrap_legacy_graph_json(legacy_path, target)
    unwrapped = unwrap_methodology_graph_from_viza(target)

    assert result.path.endswith("not-semantic-extension.data")
    assert unwrapped.model_dump(mode="json") == graph.model_dump(mode="json")


def test_file_endpoints_export_inspect_import_record_and_quarantine(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    project = get_project_store().ensure_default_project()
    graph = load_sample_methodology_graph()
    target = tmp_path / "portable-strategy.bin"

    export_response = client.post(
        "/viza/files/export",
        json={
            "target_path": str(target),
            "graph": graph.model_dump(mode="json"),
            "project_id": project.project_id,
            "display_name": "Portable Strategy",
        },
    )

    assert export_response.status_code == 200
    export_payload = export_response.json()
    file_id = export_payload["result"]["file_id"]
    assert target.exists()
    assert export_payload["manifest"]["sections"]["methodology_graph"]["status"] == "included"

    inspect_response = client.post("/viza/files/inspect", json={"path": str(target)})
    assert inspect_response.status_code == 200
    assert inspect_response.json()["file_id"] == file_id
    assert inspect_response.json()["status"] == "ok"

    import_response = client.post(
        "/viza/files/import",
        json={
            "path": str(target),
            "project_id": project.project_id,
            "save_methodology_version": True,
            "label": "Imported",
        },
    )
    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["graph"]["methodology_id"] == graph.methodology_id
    assert import_payload["methodology_version"]["label"] == "Imported"

    record_response = client.get(f"/viza/files/{file_id}")
    assert record_response.status_code == 200
    assert len(record_response.json()["imports"]) == 1
    assert len(record_response.json()["exports"]) == 1

    sections_response = client.get(f"/viza/files/{file_id}/sections")
    assert sections_response.status_code == 200
    assert sections_response.json()["sections"]["methodology_graph"]["status"] == "included"

    quarantine_response = client.post(
        "/viza/files/quarantine",
        json={"file_id": file_id, "reason": "unit_test"},
    )
    assert quarantine_response.status_code == 200
    assert quarantine_response.json()["records_updated"] == 1


def test_file_import_endpoint_accepts_legacy_viza_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_sample_methodology_graph()
    legacy_path = tmp_path / "legacy.viza.json"
    dump_methodology_graph(graph, legacy_path)

    response = client.post("/viza/files/import", json={"path": str(legacy_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "imported_legacy_graph_json"
    assert payload["graph"]["methodology_id"] == graph.methodology_id
    assert payload["manifest"]["object_kind"] == "methodology"
