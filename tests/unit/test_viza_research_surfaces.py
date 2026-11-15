from __future__ import annotations

import json

from fastapi.testclient import TestClient

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology
from viza.exports import ExportFormat, ExportRequest, export_payload
from viza.project_store import (
    CreateAlertRequest,
    CreateWatchlistRequest,
    SaveRadarOutputRequest,
    get_project_store,
)
from viza.sample_data import load_sample_methodology_graph
from viza.service import app


client = TestClient(app)


def test_project_store_saves_radars_watchlists_and_alerts(tmp_path) -> None:
    store = get_project_store(tmp_path / "viza_projects.sqlite3")
    project = store.ensure_default_project()
    graph = load_sample_methodology_graph()
    result = run_methodology(graph, load_attribute_registry())

    radar = store.save_radar_output(
        project.project_id,
        SaveRadarOutputRequest(
            result=result.model_dump(mode="json"),
            name="Top momentum radar",
            selected_columns=["ticker", "score", "momentum"],
            displayed_tickers=[row.ticker for row in result.rows[:5]],
            designer={"sort": "score", "direction": "descending"},
        ),
    )
    watchlist = store.create_watchlist(
        project.project_id,
        CreateWatchlistRequest(
            name="Top radar names",
            tickers=[row.ticker for row in result.rows[:3]],
            source_radar_id=radar.radar_id,
            source_run_id=result.run_id,
        ),
    )
    alert = store.create_alert(
        project.project_id,
        CreateAlertRequest(
            name="Rank enters top ten",
            definition={"alert_type": "rank_enters_top_n", "top_n": 10},
        ),
    )

    assert radar.row_count == 5
    assert radar.selected_columns == ["ticker", "score", "momentum"]
    assert store.list_radar_outputs(project_id=project.project_id)[0].radar_id == radar.radar_id
    assert watchlist.tickers == [row.ticker for row in result.rows[:3]]
    assert store.list_watchlists(project_id=project.project_id)[0].watchlist_id == watchlist.watchlist_id
    assert alert.definition.alert_type == "rank_enters_top_n"
    assert store.list_alerts(project_id=project.project_id)[0].alert_id == alert.alert_id


def test_export_pipeline_redacts_non_exportable_evidence() -> None:
    result = {
        "run_id": "run-1",
        "methodology_id": "methodology-1",
        "result_checksum": "checksum",
        "rows": [
            {
                "ticker": "ABC",
                "company_name": "ABC Corp",
                "score": 0.91,
                "rank": 1,
                "attributes": {"paid_sentiment_score": 0.91},
                "warnings": [],
                "evidence_refs": ["attr:ABC:paid_sentiment_score"],
            }
        ],
        "relationships": [],
        "warnings": [],
        "manifest": {},
        "evidence": {
            "attr:ABC:paid_sentiment_score": {
                "evidence_ref": "attr:ABC:paid_sentiment_score",
                "value": 0.91,
                "entitlement_policy": "query_only_no_export_credential_required",
                "entitlement": {"export_allowed": False},
            }
        },
    }

    csv_export = export_payload(
        ExportRequest(
            export_format=ExportFormat.CSV,
            result=result,
            selected_columns=["ticker", "paid_sentiment_score"],
        )
    )
    json_export = export_payload(
        ExportRequest(
            export_format=ExportFormat.JSON,
            result=result,
            include_evidence=True,
        )
    )
    json_payload = json.loads(json_export.payload)

    assert "[redacted]" in csv_export.payload
    assert csv_export.redactions[0].evidence_ref == "attr:ABC:paid_sentiment_score"
    assert json_payload["rows"][0]["attributes"]["paid_sentiment_score"] == "[redacted]"
    assert json_payload["evidence"]["attr:ABC:paid_sentiment_score"]["value"] == "[redacted]"


def test_phase_12_service_endpoints_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_sample_methodology_graph()
    result = run_methodology(graph, load_attribute_registry()).model_dump(mode="json")
    client.get("/viza/projects/default")

    radar_response = client.post(
        "/viza/projects/local-sandbox/radars",
        json={
            "result": result,
            "name": "Saved test radar",
            "selected_columns": ["ticker", "score"],
            "displayed_tickers": [row["ticker"] for row in result["rows"][:4]],
            "designer": {"filter": ""},
        },
    )
    watchlist_response = client.post(
        "/viza/projects/local-sandbox/watchlists",
        json={
            "name": "Saved radar tickers",
            "tickers": [row["ticker"] for row in result["rows"][:4]],
            "source_radar_id": radar_response.json()["radar_id"],
            "source_run_id": result["run_id"],
        },
    )
    alert_response = client.post(
        "/viza/projects/local-sandbox/alerts",
        json={
            "name": "Score above 0.8",
            "definition": {
                "alert_type": "score_crosses_threshold",
                "operator": "greater_than",
                "threshold": 0.8,
            },
        },
    )
    export_response = client.post(
        "/viza/exports",
        json={
            "export_format": "csv",
            "result": result,
            "selected_columns": ["ticker", "score"],
        },
    )
    watchlist_run_response = client.post(
        f"/viza/watchlists/{watchlist_response.json()['watchlist_id']}/execute",
        json={"graph": graph.model_dump(mode="json")},
    )

    assert radar_response.status_code == 200
    assert radar_response.json()["row_count"] == 4
    assert watchlist_response.status_code == 200
    assert watchlist_response.json()["tickers"]
    assert alert_response.status_code == 200
    assert alert_response.json()["definition"]["alert_type"] == "score_crosses_threshold"
    assert export_response.status_code == 200
    assert "ticker,score" in export_response.json()["payload"]
    assert watchlist_run_response.status_code == 200
    assert len(watchlist_run_response.json()["rows"]) <= 4
