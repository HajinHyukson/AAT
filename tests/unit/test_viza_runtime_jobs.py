from __future__ import annotations

from fastapi.testclient import TestClient

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology
from viza.graph_schema import load_methodology_graph
from viza.project_store import SaveRadarOutputRequest, get_project_store
from viza.runtime_jobs import (
    RuntimeJobCreateRequest,
    RuntimeJobStatus,
    get_runtime_job_store,
    run_runtime_job,
)
import viza.runtime_jobs as runtime_jobs
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app


client = TestClient(app)


def test_runtime_job_creation_progress_and_result_ref(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    project = get_project_store().ensure_default_project()
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    runtime_store = get_runtime_job_store()

    job = runtime_store.create_job(
        RuntimeJobCreateRequest(
            graph=graph,
            project_id=project.project_id,
            start_immediately=False,
        )
    )
    finished = run_runtime_job(
        job.job_id,
        registry=load_attribute_registry(),
        runtime_store=runtime_store,
    )

    assert finished.status == RuntimeJobStatus.COMPLETED
    assert finished.result_ref
    assert finished.progress.stage == "completed"
    assert finished.progress.cache_status == "miss"
    assert finished.progress.cache_key_count > 0
    assert get_project_store().require_run_record(finished.result_ref).result is not None
    assert {event.event_type for event in runtime_store.list_events(job.job_id)}.issuperset(
        {"queued", "progress", "finished"}
    )


def test_runtime_job_cancellation_is_durable_before_start(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    runtime_store = get_runtime_job_store()

    job = runtime_store.create_job(
        RuntimeJobCreateRequest(graph=graph, start_immediately=False)
    )
    cancelled = runtime_store.request_cancel(job.job_id)
    rerun = run_runtime_job(
        job.job_id,
        registry=load_attribute_registry(),
        runtime_store=runtime_store,
    )

    assert cancelled.status == RuntimeJobStatus.CANCELLED
    assert rerun.status == RuntimeJobStatus.CANCELLED
    assert rerun.cancel_requested is True
    assert runtime_store.require_job(job.job_id).finished_at is not None


def test_runtime_job_registry_load_failure_marks_job_failed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    runtime_store = get_runtime_job_store()

    job = runtime_store.create_job(
        RuntimeJobCreateRequest(graph=graph, start_immediately=False)
    )

    def fail_registry_load():
        raise FileNotFoundError("missing packaged registry")

    monkeypatch.setattr(runtime_jobs, "load_attribute_registry", fail_registry_load)
    finished = run_runtime_job(job.job_id, runtime_store=runtime_store)

    assert finished.status == RuntimeJobStatus.FAILED
    assert finished.finished_at is not None
    assert "missing packaged registry" in finished.progress.message
    assert {event.event_type for event in runtime_store.list_events(job.job_id)} >= {
        "queued",
        "finished",
    }


def test_runtime_cache_hits_identical_run_and_misses_source_version_change(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    project = get_project_store().ensure_default_project()
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    runtime_store = get_runtime_job_store()

    first = runtime_store.create_job(
        RuntimeJobCreateRequest(
            graph=graph,
            project_id=project.project_id,
            source_versions={"local_ohlcv_csv": "v1"},
            start_immediately=False,
        )
    )
    first_finished = run_runtime_job(first.job_id, registry=registry, runtime_store=runtime_store)

    second = runtime_store.create_job(
        RuntimeJobCreateRequest(
            graph=graph,
            project_id=project.project_id,
            source_versions={"local_ohlcv_csv": "v1"},
            start_immediately=False,
        )
    )
    second_finished = run_runtime_job(second.job_id, registry=registry, runtime_store=runtime_store)

    third = runtime_store.create_job(
        RuntimeJobCreateRequest(
            graph=graph,
            project_id=project.project_id,
            source_versions={"local_ohlcv_csv": "v2"},
            start_immediately=False,
        )
    )
    third_finished = run_runtime_job(third.job_id, registry=registry, runtime_store=runtime_store)

    assert first_finished.progress.cache_status == "miss"
    assert second_finished.progress.cache_status == "hit"
    assert second_finished.result_ref == first_finished.result_ref
    assert third_finished.progress.cache_status == "miss"
    assert third_finished.result_ref != first_finished.result_ref


def test_runtime_job_endpoints_create_cancel_and_list_events(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)

    response = client.post(
        "/viza/jobs",
        json={
            "job_type": "methodology_run",
            "graph": graph.model_dump(mode="json"),
            "start_immediately": False,
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    cancel_response = client.post(f"/viza/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    get_response = client.get(f"/viza/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["cancel_requested"] is True

    events_response = client.get(f"/viza/jobs/{job_id}/events")
    assert events_response.status_code == 200
    assert {event["event_type"] for event in events_response.json()} >= {"queued", "cancelled"}


def test_scheduler_definition_persists_for_saved_radar(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    project = get_project_store().ensure_default_project()
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    result = run_methodology(graph, load_attribute_registry()).model_dump(mode="json")
    radar = get_project_store().save_radar_output(
        project.project_id,
        SaveRadarOutputRequest(result=result, name="scheduled radar"),
    )

    response = client.post(
        f"/viza/projects/{project.project_id}/schedules",
        json={
            "radar_id": radar.radar_id,
            "methodology_id": radar.methodology_id,
            "cadence": "daily",
            "enabled": True,
            "timezone": "America/New_York",
            "definition": {"refresh": "local"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["radar_id"] == radar.radar_id
    assert payload["cadence"] == "daily"
    assert payload["definition"] == {"refresh": "local"}

    list_response = client.get(f"/viza/projects/{project.project_id}/schedules")
    assert list_response.status_code == 200
    assert list_response.json()[0]["schedule_id"] == payload["schedule_id"]
