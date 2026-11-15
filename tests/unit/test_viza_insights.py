from __future__ import annotations

import zipfile
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from viza.attribute_registry import load_attribute_registry
from viza.events import ManualEventRequest, event_from_manual_request
from viza.execution import run_methodology
from viza.file_format.container import write_viza_container
from viza.file_format.models import SectionStatus, VisibilityMode, VizaFileManifest, VizaSectionDescriptor
from viza.graph_schema import load_methodology_graph
from viza.insights import (
    InsightQueryRequest,
    extract_insights_from_run_result,
    get_insight_store,
    insight_for_export,
    load_insight_registry,
)
from viza.relationships import RelationshipQueryRequest, query_relationships
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app


client = TestClient(app)


def test_insight_registry_loads_initial_types() -> None:
    registry = load_insight_registry()
    keys = {definition.insight_type_key for definition in registry.insight_types}

    assert registry.schema_name == "viza.insight_registry.v1"
    assert "acquisition_rumor_with_technical_reversal_context" in keys
    assert "earnings_surprise_momentum_confirmation" in keys


def test_rule_based_insight_extraction_from_runtime_result() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    result = run_methodology(graph, load_attribute_registry())

    insights = extract_insights_from_run_result(result, min_confidence=0.0)

    assert insights
    first = insights[0]
    assert first.insight_type == "earnings_surprise_momentum_confirmation"
    assert first.entity_id.startswith("entity-us-equity-")
    assert first.evidence_refs
    assert first.derivation_trace["event_type"] == "earnings_surprise"


def test_insight_evidence_refs_and_pit_cutoff_are_enforced() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    result = run_methodology(graph, load_attribute_registry())

    blocked = extract_insights_from_run_result(
        result,
        min_confidence=0.0,
        cutoff=datetime(1970, 1, 1, tzinfo=timezone.utc),
    )
    assert blocked == []

    event = event_from_manual_request(
        ManualEventRequest(
            event_type="acquisition_rumor",
            affected_entity_ids=["entity-us-equity-AAPL"],
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            available_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            confidence=0.9,
            evidence_refs=[],
        )
    )
    missing_refs = extract_insights_from_run_result(
        {"rows": [], "evidence": {}},
        events=[event],
        min_confidence=0.0,
        require_evidence_refs=True,
    )
    assert missing_refs == []


def test_insight_endpoints_extract_query_and_get(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)

    extract_response = client.post(
        "/viza/insights/extract",
        json={"graph": graph.model_dump(mode="json"), "min_confidence": 0.0},
    )
    assert extract_response.status_code == 200
    insight_id = extract_response.json()[0]["insight_id"]

    query_response = client.post(
        "/viza/insights/query",
        json={"insight_types": ["earnings_surprise_momentum_confirmation"]},
    )
    get_response = client.get(f"/viza/insights/{insight_id}")

    assert query_response.status_code == 200
    assert query_response.json()["insights"][0]["insight_id"] == insight_id
    assert get_response.status_code == 200
    assert get_response.json()["insight_type"] == "earnings_surprise_momentum_confirmation"
    assert get_insight_store().require_insight(insight_id).insight_id == insight_id


def test_runtime_result_and_relationship_query_include_insights() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    result = run_methodology(graph, load_attribute_registry())

    assert result.insights
    assert result.insight_relationships

    query = query_relationships(
        RelationshipQueryRequest(
            run_result=result,
            relationship_families=["insight"],
            max_edges=100,
        ),
        load_attribute_registry(),
    )

    assert any(edge.relationship_type == "entity_to_insight" for edge in query.relationships)


def test_insight_section_exports_into_viza(tmp_path) -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    insight = run_methodology(graph, load_attribute_registry()).insights[0]
    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id="file-insights-test",
        display_name="Insights Test",
        object_kind="strategy_package",
        visibility=VisibilityMode.WHITE_BOX,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        sections={"insights": VizaSectionDescriptor(status=SectionStatus.INCLUDED)},
    )
    target = tmp_path / "insights.viza"

    write_viza_container(
        target,
        manifest,
        {"insights": {"insights": [insight_for_export(insight)]}},
    )

    with zipfile.ZipFile(target) as archive:
        assert "insights/insights.json" in archive.namelist()


def test_restricted_insight_evidence_redacts_on_export() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    insight = run_methodology(graph, load_attribute_registry()).insights[0].model_copy(
        update={"source_policy": {"export_allowed": False}},
    )

    payload = insight_for_export(insight)

    assert payload["magnitude"] is None
    assert payload["evidence_refs"] == []
    assert payload["redaction_reason"] == "insight_source_rights_restricted"


def test_insight_store_query_filters(tmp_path) -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    insight = run_methodology(graph, load_attribute_registry()).insights[0]
    store = get_insight_store(tmp_path / "viza_projects.sqlite3")
    store.upsert_insight(insight)

    result = store.query_insights(
        InsightQueryRequest(
            entity_id=insight.entity_id,
            insight_types=[insight.insight_type],
            min_confidence=0.0,
        )
    )

    assert result[0].insight_id == insight.insight_id
