from __future__ import annotations

from fastapi.testclient import TestClient

from viza.diagnostics import collect_runtime_diagnostics, diagnose_project_store
from viza.project_store import get_project_store
from viza.service import app


client = TestClient(app)


def test_project_store_diagnostics_reports_initialized_store(tmp_path) -> None:
    store_path = tmp_path / "viza_projects.sqlite3"
    store = get_project_store(store_path)
    store.ensure_default_project()

    diagnostics = diagnose_project_store(store_path)

    assert diagnostics.status == "ok"
    assert diagnostics.database_exists is True
    assert diagnostics.directory_writable is True
    assert diagnostics.project_count == 1
    assert "projects" in diagnostics.schema_tables
    assert diagnostics.missing_tables == []


def test_project_store_diagnostics_handles_missing_and_corrupt_store(tmp_path) -> None:
    missing = diagnose_project_store(tmp_path / "missing.sqlite3")
    assert missing.status == "not_initialized"
    assert missing.database_exists is False

    corrupt_path = tmp_path / "corrupt.sqlite3"
    corrupt_path.write_text("not a sqlite database", encoding="utf-8")

    corrupt = diagnose_project_store(corrupt_path)

    assert corrupt.status == "error"
    assert corrupt.error


def test_runtime_diagnostics_endpoint_reports_release_readiness(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    client.get("/viza/projects/default")

    response = client.get("/viza/diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "viza-local-engine"
    assert payload["engine_version"] == "0.2.0"
    assert payload["diagnostics_version"] == "viza_runtime_phase_14_release_readiness_v0"
    assert payload["attribute_registry_version"] == "1.1.0"
    assert payload["attribute_count"] >= 70
    assert payload["config_root"]
    assert all(file["exists"] for file in payload["config_files"])
    assert payload["project_store"]["status"] == "ok"
    assert payload["project_store"]["path"].endswith("viza_projects.sqlite3")
    assert payload["file_format_version"] == "viza.document.v1"
    assert payload["installed_modules"]
    assert payload["credential_mode"]
    assert payload["observation_store_health"]["status"] == "ok"
    assert payload["viza_file_health"]["status"] == "ok"
    assert "local_viza_workspace" in {
        connector["connector_id"] for connector in payload["connector_statuses"]
    }
    assert {check["name"] for check in payload["checks"]} == {
        "project_store",
        "config_files",
        "attribute_registry",
        "connectors",
        "local_service_token",
    }


def test_collect_runtime_diagnostics_uses_token_presence(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    monkeypatch.setenv("VIZA_ENGINE_TOKEN", "session-token")
    store = get_project_store()
    store.ensure_default_project()
    store.save_viza_file_import(
        file_id="file-quarantine-test",
        manifest={"schema": "viza.document.v1"},
        warnings=["unit"],
        quarantine_status="quarantined",
    )

    diagnostics = collect_runtime_diagnostics(engine_version="test")

    assert diagnostics.engine_version == "test"
    assert diagnostics.token_required is True
    assert diagnostics.project_store.status == "ok"
    assert any(
        check.name == "local_service_token" and check.status == "ok"
        for check in diagnostics.checks
    )
    assert diagnostics.viza_file_health["quarantined_import_count"] == 1
    assert diagnostics.last_quarantine_event["file_id"] == "file-quarantine-test"
