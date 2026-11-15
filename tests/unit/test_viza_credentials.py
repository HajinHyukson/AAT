from __future__ import annotations

import sqlite3
import zipfile

from fastapi.testclient import TestClient

from viza.credentials import CredentialStore, dev_env_var
from viza.project_store import get_project_store
from viza.sample_data import load_sample_methodology_graph
from viza.service import app


client = TestClient(app)


def test_credential_store_falls_back_to_dev_env_without_values_in_refs(monkeypatch) -> None:
    monkeypatch.setenv("VIZA_CREDENTIAL_MODE", "env_var_dev")
    store = CredentialStore()

    credential_ref = store.set_secret("fmp", "fmp_credential", "unit-secret")

    assert credential_ref.storage == "env_var_dev"
    assert credential_ref.reference == dev_env_var("fmp", "fmp_credential")
    assert credential_ref.model_dump()["reference"] != "unit-secret"
    assert store.get_secret_for_runtime("fmp", "fmp_credential") == "unit-secret"
    store.delete_secret("fmp", "fmp_credential")


def test_connector_credential_endpoints_never_return_or_persist_values(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    monkeypatch.setenv("VIZA_CREDENTIAL_MODE", "env_var_dev")
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    secret_value = "phase-21-secret-value"

    response = client.post(
        "/viza/connectors/fmp/credentials",
        json={"key": "fmp_credential", "value": secret_value},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert secret_value not in response.text

    get_response = client.get("/viza/connectors/fmp/credentials")
    assert get_response.status_code == 200
    assert secret_value not in get_response.text
    assert get_response.json()[0]["configured"] is True

    record = get_project_store().require_connector_configuration("fmp")
    assert secret_value not in record.model_dump_json()
    with sqlite3.connect(tmp_path / "viza_projects.sqlite3") as connection:
        raw_rows = connection.execute("SELECT * FROM connector_settings").fetchall()
    assert secret_value not in repr(raw_rows)

    delete_response = client.delete("/viza/connectors/fmp/credentials/fmp_credential")
    assert delete_response.status_code == 200


def test_connector_config_redacts_secret_like_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    monkeypatch.setenv("VIZA_CREDENTIAL_MODE", "env_var_dev")

    response = client.post(
        "/viza/connectors/local_csv/configure",
        json={
            "settings": {
                "path": str(tmp_path / "data.csv"),
                "api_key": "should-not-persist",
            },
            "credentials": {},
        },
    )

    assert response.status_code == 200
    assert "should-not-persist" not in response.text
    assert response.json()["settings"]["api_key"] == "***REDACTED***"
    record = get_project_store().require_connector_configuration("local_csv")
    assert "should-not-persist" not in record.model_dump_json()


def test_diagnostics_health_and_viza_export_do_not_leak_credentials(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    monkeypatch.setenv("VIZA_CREDENTIAL_MODE", "env_var_dev")
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    secret_value = "phase-21-export-secret"

    set_response = client.post(
        "/viza/connectors/fmp/credentials",
        json={"key": "fmp_credential", "value": secret_value},
    )
    assert set_response.status_code == 200

    diagnostics_response = client.get("/viza/diagnostics")
    assert diagnostics_response.status_code == 200
    assert secret_value not in diagnostics_response.text

    health_response = client.get("/viza/connectors/fmp/test")
    assert health_response.status_code == 200
    health = health_response.json()
    assert health["credential_required"] is True
    assert health["credential_configured"] is True
    assert health["credential_mode"] == "env_var_dev"
    assert "query_allowed" in health
    assert "redistribution_allowed" in health

    target = tmp_path / "credential_export.viza"
    export_response = client.post(
        "/viza/files/export",
        json={
            "target_path": str(target),
            "graph": load_sample_methodology_graph().model_dump(mode="json"),
        },
    )
    assert export_response.status_code == 200

    with zipfile.ZipFile(target) as archive:
        exported_text = "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".json")
        )
    assert secret_value not in exported_text

    delete_response = client.delete("/viza/connectors/fmp/credentials/fmp_credential")
    assert delete_response.status_code == 200
