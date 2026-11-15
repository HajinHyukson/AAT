from __future__ import annotations

from fastapi.testclient import TestClient

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology
from viza.graph_schema import MethodologyGraph, load_methodology_graph
from viza.project_store import get_project_store
from viza.relationships import RelationshipQueryRequest, query_relationships
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app


client = TestClient(app)


def test_viza_project_store_endpoints_round_trip_versions(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)

    project_response = client.get("/viza/projects/default")
    save_response = client.post(
        "/viza/projects/local-sandbox/methodology-versions",
        json={
            "graph": graph.model_dump(mode="json"),
            "label": "Initial",
            "message": "Saved from service test.",
        },
    )
    versions_response = client.get(f"/viza/methodologies/{graph.methodology_id}/versions")

    assert project_response.status_code == 200
    assert project_response.json()["project_id"] == "local-sandbox"
    assert save_response.status_code == 200
    saved_version = save_response.json()
    assert saved_version["graph"]["methodology_id"] == graph.methodology_id
    assert saved_version["graph_hash"]
    assert versions_response.status_code == 200
    assert versions_response.json()[0]["version_id"] == saved_version["version_id"]


def test_viza_project_store_compare_endpoint_reports_changes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    client.get("/viza/projects/default")
    first = client.post(
        "/viza/projects/local-sandbox/methodology-versions",
        json={"graph": graph.model_dump(mode="json"), "label": "Initial"},
    )
    payload = graph.model_dump(mode="json")
    payload["nodes"][1]["label"] = "Momentum Updated"
    second = client.post(
        "/viza/projects/local-sandbox/methodology-versions",
        json={"graph": payload, "label": "Updated"},
    )

    compare_response = client.get(
        f"/viza/methodologies/{graph.methodology_id}/versions/compare",
        params={
            "left_version_id": first.json()["version_id"],
            "right_version_id": second.json()["version_id"],
        },
    )

    assert compare_response.status_code == 200
    assert compare_response.json()["changed_nodes"] == ["attribute-momentum"]


def test_viza_files_endpoint_lists_exchange_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    store = get_project_store()
    project = store.ensure_default_project()
    store.save_viza_file_export(
        file_id="file-service-list",
        manifest={"schema": "viza.document.v1", "file_id": "file-service-list"},
        project_id=project.project_id,
        purpose="marketplace_draft",
        visibility="gray_box",
    )

    response = client.get("/viza/files")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["file_id"] == "file-service-list"
    assert payload[0]["exports"][0]["purpose"] == "marketplace_draft"


def test_viza_attributes_endpoint_returns_registry() -> None:
    response = client.get("/viza/attributes")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "viza_attribute_registry_v1"
    assert payload["registry_version"] == "1.1.0"
    assert 40 <= len(payload["attributes"]) <= 80


def test_viza_service_rejects_invalid_local_engine_token(monkeypatch) -> None:
    monkeypatch.setenv("VIZA_ENGINE_TOKEN", "expected-token")

    missing_token = client.get("/viza/attributes")
    wrong_token = client.get(
        "/viza/attributes",
        headers={"x-viza-engine-token": "wrong-token"},
    )
    valid_token = client.get(
        "/viza/attributes",
        headers={"x-viza-engine-token": "expected-token"},
    )

    assert missing_token.status_code == 401
    assert wrong_token.status_code == 401
    assert valid_token.status_code == 200


def test_viza_runtime_endpoint_declares_no_database_required() -> None:
    response = client.get("/viza/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "viza-local-engine"
    assert payload["database_required"] is False
    assert "phase_4_attribute_resolvers" in payload["data_sources"]
    assert "local_csv" in payload["connectors"]
    assert "fmp" in payload["connectors"]


def test_viza_universes_endpoint_returns_local_universes() -> None:
    response = client.get("/viza/universes")

    assert response.status_code == 200
    universes = response.json()
    universe_names = {universe["universe_name"] for universe in universes}
    assert "pilot_sp500_static" in universe_names
    assert "mvp_50" in universe_names
    assert all(universe["asset_count"] > 0 for universe in universes)


def test_viza_connectors_endpoint_returns_catalog() -> None:
    response = client.get("/viza/connectors")

    assert response.status_code == 200
    connectors = response.json()
    connectors_by_id = {connector["connector_id"]: connector for connector in connectors}
    assert connectors_by_id["local_viza_workspace"]["status"] == "available"
    assert connectors_by_id["local_csv"]["source_type"] == "local_csv"
    assert connectors_by_id["fmp"]["credential_requirements"][0]["env_var"] == "FMP_API_KEY"


def test_viza_connector_fields_endpoint_returns_workspace_fields() -> None:
    response = client.get("/viza/connectors/local_viza_workspace/fields")

    assert response.status_code == 200
    fields = response.json()
    assert "momentum" in {field["field_key"] for field in fields}
    assert all("entitlement" in field for field in fields)


def test_viza_execute_endpoint_returns_ranked_radar_result() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)

    response = client.post("/viza/execute", json=graph.model_dump(mode="json"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["methodology_id"] == graph.methodology_id
    assert payload["status"] == "completed"
    assert len(payload["rows"]) == 25
    assert payload["rows"][0]["rank"] == 1
    assert payload["rows"][0]["score"] is not None
    assert payload["rows"][0]["attributes"]["momentum"] is not None
    assert payload["relationships"]
    first_company_ref = f"company:{payload['rows'][0]['ticker']}"
    first_company_relationships = [
        edge for edge in payload["relationships"] if edge["source"] == first_company_ref
    ]
    assert {"selected_attribute", "sector", "industry"}.issubset(
        {edge["relationship_type"] for edge in first_company_relationships}
    )
    assert "prototype_attribute_values" in {warning["code"] for warning in payload["warnings"]}
    assert payload["evidence"]["graph"]["attribute_keys"] == [
        "momentum",
        "unexplained_residual_bps",
        "event_materiality",
    ]
    assert payload["result_checksum"] == payload["manifest"]["result_checksum"]
    assert payload["manifest"]["runtime_version"] == "viza_runtime_phase_10_audit_v0"


def test_viza_execute_can_persist_run_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    client.get("/viza/projects/default")

    response = client.post(
        "/viza/execute",
        params={"project_id": "local-sandbox", "methodology_version_id": "version-test"},
        json=graph.model_dump(mode="json"),
    )
    runs_response = client.get(
        "/viza/projects/local-sandbox/runs",
        params={"methodology_id": graph.methodology_id},
    )

    assert response.status_code == 200
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert runs[0]["run_id"] == response.json()["run_id"]
    assert runs[0]["result_checksum"] == response.json()["result_checksum"]


def test_viza_reproduce_endpoint_compares_manifests() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    baseline = client.post("/viza/execute", json=graph.model_dump(mode="json")).json()

    response = client.post(
        "/viza/reproduce",
        json={
            "graph": graph.model_dump(mode="json"),
            "baseline_manifest": baseline["manifest"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matching"] is True
    assert {check["status"] for check in payload["checks"]} == {"match"}
    assert payload["result"]["result_checksum"] == baseline["result_checksum"]


def test_viza_execute_endpoint_returns_warnings_for_incomplete_graph() -> None:
    response = client.post(
        "/viza/execute",
        json={
            "schema_version": "viza_graph_v0",
            "methodology_id": "incomplete-methodology",
            "name": "Incomplete Methodology",
            "created_at": "2026-05-12T00:00:00Z",
            "updated_at": "2026-05-12T00:00:00Z",
            "nodes": [],
            "edges": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert {warning["code"] for warning in payload["warnings"]} == {
        "missing_universe",
        "missing_output_radar",
    }


def test_viza_execute_changes_scores_when_weights_change() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    momentum_only = _with_score_weights(graph, {"momentum": 1.0})
    event_only = _with_score_weights(graph, {"event_materiality": 1.0})

    momentum_result = run_methodology(momentum_only, registry)
    event_result = run_methodology(event_only, registry)

    assert momentum_result.status == "completed"
    assert event_result.status == "completed"
    assert [row.ticker for row in momentum_result.rows[:10]] != [
        row.ticker for row in event_result.rows[:10]
    ]


def test_viza_execute_filter_restricts_rows() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    payload = graph.model_dump(mode="json")
    payload["nodes"].append(
        {
            "id": "filter-sector-it",
            "type": "filter",
            "position": {"x": 680, "y": 40},
            "label": "Information Technology Only",
            "config": {
                "attribute_key": "sector",
                "operator": "equals",
                "value": "Information Technology",
            },
        }
    )
    payload["edges"].append(
        {
            "id": "edge-filter-sector-it",
            "source": "filter-sector-it",
            "target": "score-1",
            "type": "data_flow",
        }
    )

    result = run_methodology(MethodologyGraph.model_validate(payload), registry)

    assert result.status == "completed"
    assert result.rows
    assert {row.attributes["sector"] for row in result.rows} == {"Information Technology"}


def test_viza_execute_returns_peer_relationships_when_universe_has_peer_data() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    payload = graph.model_dump(mode="json")
    universe_node = next(node for node in payload["nodes"] if node["id"] == "universe-1")
    universe_node["config"]["universe_name"] = "mvp_50"
    universe_node["config"]["universe_version"] = "mvp_50_v0"

    result = run_methodology(MethodologyGraph.model_validate(payload), registry)

    assert result.status == "completed"
    assert any(edge.relationship_type == "peer" for edge in result.relationships)


def test_viza_relationship_query_filters_edges_for_entity() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    result = run_methodology(graph, registry)
    entity_ref = f"company:{result.rows[0].ticker}"

    response = client.post(
        "/viza/relationships/query",
        json={
            "graph": graph.model_dump(mode="json"),
            "entity_ref": entity_ref,
            "relationship_families": ["attribute", "classification"],
            "min_strength": 0.0,
            "max_edges": 20,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["entity_ref"] == entity_ref
    assert payload["relationships"]
    assert {
        edge["relationship_family"] for edge in payload["relationships"]
    }.issubset({"attribute", "classification"})
    assert all(
        edge["source"] == entity_ref or edge["target"] == entity_ref
        for edge in payload["relationships"]
    )
    assert all(edge["evidence_ref"] for edge in payload["relationships"])


def test_relationship_query_can_filter_existing_run_result_without_rerun() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    run_result = run_methodology(graph, registry)
    entity_ref = f"company:{run_result.rows[0].ticker}"

    result = query_relationships(
        RelationshipQueryRequest(
            run_result=run_result,
            entity_ref=entity_ref,
            relationship_families=["attribute"],
        ),
        registry,
    )

    assert result.run_id == run_result.run_id
    assert result.relationships
    assert {edge.relationship_family for edge in result.relationships} == {"attribute"}


def _with_score_weights(graph: MethodologyGraph, weights: dict[str, float]) -> MethodologyGraph:
    payload = graph.model_dump(mode="json")
    score_node = next(node for node in payload["nodes"] if node["id"] == "score-1")
    score_node["config"]["weights"] = weights
    return MethodologyGraph.model_validate(payload)
