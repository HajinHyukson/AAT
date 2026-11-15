from __future__ import annotations

from fastapi.testclient import TestClient

from viza.audit import point_in_time_evidence_checks, point_in_time_summary
from viza.attribute_registry import load_attribute_registry
from viza.batch import BatchExecutionRequest, execute_batch
from viza.graph_schema import load_methodology_graph
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app


client = TestClient(app)


def test_batch_execution_runs_one_methodology_over_multiple_cutoffs() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()

    result = execute_batch(
        BatchExecutionRequest(
            graph=graph,
            cutoffs=["2026-05-06", "2026-05-12"],
            ticker_subset=["AAPL", "MSFT", "NVDA"],
            persist_results=False,
        ),
        registry,
    )

    assert result.status == "completed"
    assert result.total_runs == 2
    assert result.completed_runs == 2
    assert len(result.results) == 2
    assert {item.cutoff for item in result.results} == {"2026-05-06", "2026-05-12"}
    for item in result.results:
        assert item.result is not None
        assert item.status == "completed_with_warnings"
        assert item.result.manifest["timestamp_cutoff"] == item.cutoff
        assert item.result.manifest["point_in_time"]["status"] == "passed"
        assert item.pit_status == "passed"
        assert item.diagnostics.row_count <= 3
        assert item.diagnostics.pit_violation_count == 0
        assert item.cache_keys
        assert {cache_key.node_id for cache_key in item.cache_keys}.issuperset(
            {"universe-1", "score-1", "output-radar-1"}
        )


def test_batch_execution_can_fail_point_in_time_checks() -> None:
    checks = point_in_time_evidence_checks(
        {
            "future-source": {
                "source": "test",
                "timestamp_available": "2026-05-07T00:00:00Z",
            }
        },
        "2026-05-06",
    )
    summary = point_in_time_summary(checks)

    assert summary["status"] == "failed"
    assert summary["violation_count"] == 1
    assert checks[0].status == "violated"


def test_batch_execution_can_cancel_before_remaining_runs() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()

    result = execute_batch(
        BatchExecutionRequest(
            graph=graph,
            cutoffs=["2026-05-06", "2026-05-07", "2026-05-08"],
            ticker_subset=["AAPL"],
            persist_results=False,
            cancel_after_runs=1,
        ),
        registry,
    )

    assert result.status == "cancelled"
    assert result.total_runs == 3
    assert result.completed_runs == 1
    assert result.cancelled_runs == 2
    assert len(result.results) == 1
    assert result.progress[-1].status == "cancelled"


def test_batch_execute_endpoint_persists_each_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    client.get("/viza/projects/default")

    response = client.post(
        "/viza/batch/execute",
        json={
            "graph": graph.model_dump(mode="json"),
            "cutoffs": ["2026-05-12"],
            "project_id": "local-sandbox",
            "ticker_subset": ["AAPL", "MSFT"],
        },
    )
    runs_response = client.get(
        "/viza/projects/local-sandbox/runs",
        params={"methodology_id": graph.methodology_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 1
    assert payload["results"][0]["result"]["manifest"]["point_in_time"]["status"] == "passed"
    assert runs_response.status_code == 200
    assert runs_response.json()[0]["run_id"] == payload["results"][0]["run_id"]
