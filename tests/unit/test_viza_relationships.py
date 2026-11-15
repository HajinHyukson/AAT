from __future__ import annotations

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology
from viza.graph_schema import load_methodology_graph
from viza.relationships import RelationshipQueryRequest, query_relationships
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH


def _run_result():
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    return run_methodology(graph, load_attribute_registry())


def test_relationship_query_can_center_on_insight() -> None:
    result = _run_result()
    insight = result.insights[0]

    query = query_relationships(
        RelationshipQueryRequest(
            run_result=result,
            insight_id=insight.insight_id,
            max_edges=100,
        ),
        load_attribute_registry(),
    )

    assert query.relationships
    assert all(edge.relationship_id for edge in query.relationships)
    assert all(edge.source_type or edge.target_type for edge in query.relationships)
    assert any(edge.family == "entity_to_insight" for edge in query.relationships)


def test_relationship_query_includes_insight_to_event_edges() -> None:
    result = _run_result()

    query = query_relationships(
        RelationshipQueryRequest(
            run_result=result,
            family="insight_to_event",
            max_edges=100,
        ),
        load_attribute_registry(),
    )

    assert any(edge.family == "insight_to_event" for edge in query.relationships)
    assert all(edge.rights_policy for edge in query.relationships)
    assert all(edge.available_at for edge in query.relationships)


def test_insight_reaction_rules_emit_invalidating_edges() -> None:
    result = _run_result()
    base = result.insights[0]
    regulatory = base.model_copy(
        update={
            "insight_id": "insight-regulatory-action",
            "insight_type": "regulatory_risk_event",
            "derivation_trace": {"event_type": "regulatory_action"},
        }
    )
    rumor = base.model_copy(
        update={
            "insight_id": "insight-acquisition-rumor",
            "insight_type": "acquisition_rumor",
            "derivation_trace": {"event_type": "acquisition_rumor"},
        }
    )
    synthetic = result.model_copy(
        update={
            "insights": [regulatory, rumor],
            "insight_relationships": [],
            "translations": [],
        }
    )

    query = query_relationships(
        RelationshipQueryRequest(
            run_result=synthetic,
            family="insight_invalidates_insight",
            relationship_type="invalidates",
        ),
        load_attribute_registry(),
    )

    assert len(query.relationships) == 1
    assert query.relationships[0].source == "insight:insight-regulatory-action"
    assert query.relationships[0].target == "insight:insight-acquisition-rumor"


def test_relationship_query_filters_by_pit_and_confidence() -> None:
    result = _run_result()

    query = query_relationships(
        RelationshipQueryRequest(
            run_result=result,
            PIT_only=True,
            min_confidence=0.5,
            source_type="insight",
            max_edges=100,
        ),
        load_attribute_registry(),
    )

    assert query.relationships
    assert all(edge.available_at or edge.timestamp_available for edge in query.relationships)
    assert all(edge.confidence is None or edge.confidence >= 0.5 for edge in query.relationships)
    assert {edge.source_type for edge in query.relationships} == {"insight"}


def test_legacy_family_alias_still_returns_event_edges() -> None:
    result = _run_result()

    query = query_relationships(
        RelationshipQueryRequest(
            run_result=result,
            relationship_families=["event"],
            max_edges=100,
        ),
        load_attribute_registry(),
    )

    assert query.relationships
    assert any(edge.family == "entity_to_event" for edge in query.relationships)
