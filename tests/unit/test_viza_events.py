from __future__ import annotations

import zipfile
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from viza.attribute_registry import load_attribute_registry
from viza.events import (
    EventQueryRequest,
    ManualEventRequest,
    event_for_export,
    event_from_manual_request,
    extract_events_from_run_result,
    get_event_store,
    load_event_registry,
)
from viza.execution import run_methodology
from viza.file_format.container import write_viza_container
from viza.file_format.models import (
    SectionStatus,
    VisibilityMode,
    VizaFileManifest,
    VizaModuleRequirement,
    VizaSectionDescriptor,
)
from viza.graph_schema import load_methodology_graph
from viza.relationships import RelationshipQueryRequest, query_relationships
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app


client = TestClient(app)


def test_event_registry_loads_initial_types() -> None:
    registry = load_event_registry()
    event_types = {definition.event_type for definition in registry.event_types}

    assert registry.schema_name == "viza.event_registry.v1"
    assert "acquisition_rumor" in event_types
    assert "earnings_surprise" in event_types
    assert len(event_types) >= 16


def test_manual_event_create_query_and_get(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    observed_at = datetime(2026, 3, 1, tzinfo=timezone.utc)

    response = client.post(
        "/viza/events/manual",
        json={
            "event_type": "acquisition_rumor",
            "affected_entity_ids": ["entity-us-equity-AAPL"],
            "affected_asset_ids": ["asset-us-equity-AAPL"],
            "observed_at": observed_at.isoformat(),
            "available_at": observed_at.isoformat(),
            "confidence": 0.81,
            "materiality": 0.7,
            "source": {"kind": "manual", "note": "unit test"},
        },
    )

    assert response.status_code == 200
    event_id = response.json()["event_id"]

    query_response = client.post(
        "/viza/events/query",
        json={"affected_entity_id": "entity-us-equity-AAPL", "event_types": ["acquisition_rumor"]},
    )
    get_response = client.get(f"/viza/events/{event_id}")

    assert query_response.status_code == 200
    assert query_response.json()["events"][0]["event_id"] == event_id
    assert get_response.status_code == 200
    assert get_response.json()["event_type"] == "acquisition_rumor"


def test_event_extraction_from_deterministic_attributes_respects_pit_cutoff(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    result = run_methodology(graph, load_attribute_registry())

    events = extract_events_from_run_result(result, min_confidence=0.0)

    assert events
    assert events[0].event_type in {"earnings_surprise", "news_sentiment_shift"}
    assert events[0].affected_entity_ids
    assert events[0].affected_asset_ids
    assert events[0].evidence_refs == [f"attr:{result.rows[0].ticker}:event_materiality"]

    blocked = extract_events_from_run_result(
        result,
        min_confidence=0.0,
        cutoff=datetime(1970, 1, 1, tzinfo=timezone.utc),
    )
    assert blocked == []


def test_event_extract_endpoint_persists_events(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)

    response = client.post(
        "/viza/events/extract",
        json={"graph": graph.model_dump(mode="json"), "min_confidence": 0.0},
    )

    assert response.status_code == 200
    events = response.json()
    assert events
    stored = get_event_store().require_event(events[0]["event_id"])
    assert stored.event_id == events[0]["event_id"]


def test_event_relationships_appear_in_relationship_query_payload() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    result = run_methodology(graph, load_attribute_registry())
    query = query_relationships(
        RelationshipQueryRequest(
            run_result=result,
            relationship_families=["event"],
            max_edges=100,
        ),
        load_attribute_registry(),
    )

    assert any(edge.relationship_type == "entity_to_event" for edge in query.relationships)
    assert any(edge.target.startswith("event:event-") for edge in query.relationships)


def test_event_section_exports_into_viza(tmp_path) -> None:
    event = event_from_manual_request(
        ManualEventRequest(
            event_type="earnings_surprise",
            affected_entity_ids=["entity-us-equity-MSFT"],
            affected_asset_ids=["asset-us-equity-MSFT"],
            observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            available_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            confidence=0.9,
            evidence_refs=["attr:MSFT:event_materiality"],
        )
    )
    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id="file-events-test",
        display_name="Events Test",
        object_kind="strategy_package",
        visibility=VisibilityMode.WHITE_BOX,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        required_modules=[
            VizaModuleRequirement(module_id="viza.finance.securities", version_range=">=0.1.0")
        ],
        sections={
            "events": VizaSectionDescriptor(status=SectionStatus.INCLUDED),
        },
    )
    target = tmp_path / "events.viza"

    write_viza_container(
        target,
        manifest,
        {"events": {"events": [event.model_dump(mode="json", by_alias=True)]}},
    )

    with zipfile.ZipFile(target) as archive:
        assert "events/events.json" in archive.namelist()


def test_restricted_event_evidence_redacts_on_export() -> None:
    event = event_from_manual_request(
        ManualEventRequest(
            event_type="earnings_surprise",
            affected_entity_ids=["entity-us-equity-MSFT"],
            observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            available_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            confidence=0.9,
            source={"kind": "paid_news", "headline": "restricted"},
            evidence_refs=["paid:event"],
            rights_policy={"export_allowed": False},
        )
    )

    payload = event_for_export(event)

    assert payload["source"] == {"redacted": True}
    assert payload["evidence_refs"] == []
    assert payload["redaction_reason"] == "event_source_rights_restricted"
