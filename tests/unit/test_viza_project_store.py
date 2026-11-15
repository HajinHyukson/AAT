from __future__ import annotations

import sqlite3

from viza.graph_schema import MethodologyGraph, load_methodology_graph
from viza.project_store import (
    SaveMethodologyVersionRequest,
    get_project_store,
)
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH


def test_project_store_creates_default_project_and_schema(tmp_path) -> None:
    store_path = tmp_path / "viza_projects.sqlite3"
    store = get_project_store(store_path)

    project = store.ensure_default_project()

    assert project.project_id == "local-sandbox"
    assert project.name == "Local Sandbox"
    with sqlite3.connect(store_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "projects",
        "methodology_versions",
        "run_records",
        "saved_radar_outputs",
        "connector_settings",
        "user_settings",
        "watchlists",
        "alerts",
        "creator_records",
    }.issubset(table_names)


def test_project_store_saves_multiple_methodology_versions_and_loads_graph(tmp_path) -> None:
    store = get_project_store(tmp_path / "viza_projects.sqlite3")
    project = store.ensure_default_project()
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)

    first = store.save_methodology_version(
        project.project_id,
        SaveMethodologyVersionRequest(graph=graph, label="Initial"),
    )
    payload = graph.model_dump(mode="json")
    payload["name"] = "Residual Momentum Event Radar Copy"
    payload["nodes"].append(
        {
            "id": "attribute-liquidity",
            "type": "attribute",
            "position": {"x": 320, "y": 420},
            "label": "Liquidity",
            "config": {
                "attribute_key": "liquidity",
                "lookback_days": 30,
                "missing_data": "warn_and_exclude_from_score",
            },
        }
    )
    changed_graph = MethodologyGraph.model_validate(payload)
    second = store.save_methodology_version(
        project.project_id,
        SaveMethodologyVersionRequest(graph=changed_graph, label="Liquidity"),
    )

    versions = store.list_methodology_versions(graph.methodology_id, project_id=project.project_id)
    loaded = store.require_methodology_version(graph.methodology_id, second.version_id)

    assert [version.version_id for version in versions] == [second.version_id, first.version_id]
    assert second.parent_version_id == first.version_id
    assert loaded.graph.name == "Residual Momentum Event Radar Copy"
    assert loaded.node_count == len(changed_graph.nodes)
    assert loaded.graph_hash != first.graph_hash


def test_project_store_compares_version_graph_changes(tmp_path) -> None:
    store = get_project_store(tmp_path / "viza_projects.sqlite3")
    project = store.ensure_default_project()
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    first = store.save_methodology_version(
        project.project_id,
        SaveMethodologyVersionRequest(graph=graph, label="Initial"),
    )

    payload = graph.model_dump(mode="json")
    payload["nodes"][1]["config"]["lookback_days"] = 252
    payload["edges"].append(
        {
            "id": "edge-extra-evidence",
            "source": "attribute-momentum",
            "target": "relationship-1",
            "type": "evidence",
        }
    )
    changed_graph = MethodologyGraph.model_validate(payload)
    second = store.save_methodology_version(
        project.project_id,
        SaveMethodologyVersionRequest(graph=changed_graph, label="Changed"),
    )

    diff = store.compare_versions(graph.methodology_id, first.version_id, second.version_id)

    assert diff.changed_nodes == ["attribute-momentum"]
    assert diff.added_edges == ["edge-extra-evidence"]
    assert diff.removed_nodes == []


def test_project_store_persists_run_records(tmp_path) -> None:
    store = get_project_store(tmp_path / "viza_projects.sqlite3")
    project = store.ensure_default_project()
    result_payload = {
        "run_id": "run-1",
        "methodology_id": "methodology-1",
        "graph_hash": "abc123",
        "status": "completed",
        "result_checksum": "checksum-1",
        "manifest": {"result_checksum": "checksum-1", "warning_codes": []},
        "rows": [],
        "relationships": [],
        "warnings": [],
        "evidence": {},
    }

    saved = store.save_run_record(
        result_payload=result_payload,
        project_id=project.project_id,
        version_id="version-1",
    )
    loaded = store.require_run_record("run-1")
    summaries = store.list_run_records(project_id=project.project_id)

    assert saved.result_checksum == "checksum-1"
    assert loaded.manifest["result_checksum"] == "checksum-1"
    assert loaded.result == result_payload
    assert summaries[0].run_id == "run-1"


def test_project_store_lists_viza_file_records(tmp_path) -> None:
    store = get_project_store(tmp_path / "viza_projects.sqlite3")
    project = store.ensure_default_project()

    export_record = store.save_viza_file_export(
        file_id="file-1",
        manifest={"schema": "viza.document.v1", "file_id": "file-1"},
        project_id=project.project_id,
        purpose="marketplace_draft",
        visibility="gray_box",
    )
    import_record = store.save_viza_file_import(
        file_id="file-1",
        manifest={"schema": "viza.document.v1", "file_id": "file-1"},
        project_id=project.project_id,
        status="quarantined",
        quarantine_status="quarantined",
    )

    records = store.list_viza_file_records()

    assert [record.file_id for record in records] == ["file-1"]
    assert records[0].exports[0].export_id == export_record.export_id
    assert records[0].imports[0].import_id == import_record.import_id
