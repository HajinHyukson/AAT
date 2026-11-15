from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from threading import Thread
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.audit import stable_checksum
from viza.attribute_registry import AttributeRegistry, load_attribute_registry
from viza.batch import BatchExecutionRequest, BatchExecutionResult, execute_batch
from viza.connectors import load_connector_catalog
from viza.execution import MethodologyRunResult, run_methodology
from viza.graph_schema import MethodologyGraph, VizaNodeType
from viza.project_store import get_project_store, project_store_path
from viza.runtime import compile_execution_plan, hash_methodology_graph


class RuntimeJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeJobType(StrEnum):
    METHODOLOGY_RUN = "methodology_run"
    BATCH_EXECUTION = "batch_execution"


class ScheduleCadence(StrEnum):
    MANUAL = "manual"
    DAILY = "daily"
    WEEKLY = "weekly"
    ON_APP_START = "on_app_start"


class RuntimeCacheKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    graph_hash: str
    module_id: str = "viza.core.strategy"
    universe_version: str | None = None
    timestamp_cutoff: str | None = None
    attribute_versions: dict[str, str] = Field(default_factory=dict)
    source_versions: dict[str, str] = Field(default_factory=dict)
    connector_states: dict[str, str] = Field(default_factory=dict)
    strategy_profile_hash: str | None = None
    checksum: str = ""


class RuntimeCacheEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cache_checksum: str
    cache_key: RuntimeCacheKey
    result_ref: str | None = None
    result_checksum: str | None = None
    source_versions: dict[str, str] = Field(default_factory=dict)
    created_at: str
    last_hit_at: str | None = None
    hit_count: int = 0


class RuntimeJobProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str = "pending"
    current: int = 0
    total: int = 0
    message: str = ""
    cache_status: str = "not_checked"
    cache_key_count: int = 0
    result_ref: str | None = None


class RuntimeJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_type: RuntimeJobType = RuntimeJobType.METHODOLOGY_RUN
    project_id: str | None = None
    methodology_version_id: str | None = None
    graph: MethodologyGraph | None = None
    batch_request: BatchExecutionRequest | None = None
    timestamp_cutoff: str | None = None
    source_versions: dict[str, str] = Field(default_factory=dict)
    connector_states: dict[str, str] = Field(default_factory=dict)
    strategy_profile_hash: str | None = None
    use_cache: bool = True
    start_immediately: bool = True

    @model_validator(mode="after")
    def validate_job_payload(self) -> RuntimeJobCreateRequest:
        if self.job_type == RuntimeJobType.METHODOLOGY_RUN and self.graph is None:
            raise ValueError("methodology_run jobs require graph")
        if self.job_type == RuntimeJobType.BATCH_EXECUTION and self.batch_request is None:
            raise ValueError("batch_execution jobs require batch_request")
        return self


class RuntimeJobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    project_id: str | None = None
    job_type: RuntimeJobType
    status: RuntimeJobStatus
    request: dict[str, Any]
    progress: RuntimeJobProgress = Field(default_factory=RuntimeJobProgress)
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    cancel_requested: bool = False
    result_ref: str | None = None
    warnings: list[str] = Field(default_factory=list)


class RuntimeJobEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    job_id: str
    sequence: int
    event_type: str
    status: RuntimeJobStatus
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class RuntimeScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radar_id: str | None = None
    methodology_id: str | None = None
    cadence: ScheduleCadence = ScheduleCadence.MANUAL
    enabled: bool = True
    timezone: str = "local"
    next_run_at: str | None = None
    definition: dict[str, Any] = Field(default_factory=dict)


class RuntimeScheduleRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_id: str
    project_id: str
    radar_id: str | None = None
    methodology_id: str | None = None
    cadence: ScheduleCadence
    enabled: bool
    timezone: str
    next_run_at: str | None = None
    definition: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class RuntimeJobStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_job(self, request: RuntimeJobCreateRequest) -> RuntimeJobRecord:
        job_id = f"job-{uuid4()}"
        timestamp = _utc_now()
        progress = RuntimeJobProgress(message="Job queued.")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_jobs(
                    job_id,
                    project_id,
                    job_type,
                    status,
                    request_json,
                    progress_json,
                    created_at,
                    warnings_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    request.project_id,
                    request.job_type.value,
                    RuntimeJobStatus.PENDING.value,
                    json.dumps(request.model_dump(mode="json"), sort_keys=True),
                    json.dumps(progress.model_dump(mode="json"), sort_keys=True),
                    timestamp,
                    "[]",
                ),
            )
        self.append_event(
            job_id=job_id,
            event_type="queued",
            status=RuntimeJobStatus.PENDING,
            message="Job queued.",
        )
        return self.require_job(job_id)

    def require_job(self, job_id: str) -> RuntimeJobRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA runtime job: {job_id}")
        return _job_from_row(row)

    def list_jobs(self, project_id: str | None = None) -> list[RuntimeJobRecord]:
        where_sql = "WHERE project_id = ?" if project_id is not None else ""
        params = (project_id,) if project_id is not None else ()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM runtime_jobs
                {where_sql}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [_job_from_row(row) for row in rows]

    def mark_running(self, job_id: str, progress: RuntimeJobProgress) -> RuntimeJobRecord:
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runtime_jobs
                SET status = ?, started_at = ?, progress_json = ?
                WHERE job_id = ?
                """,
                (
                    RuntimeJobStatus.RUNNING.value,
                    timestamp,
                    json.dumps(progress.model_dump(mode="json"), sort_keys=True),
                    job_id,
                ),
            )
        self.append_event(
            job_id=job_id,
            event_type="progress",
            status=RuntimeJobStatus.RUNNING,
            message=progress.message,
            payload=progress.model_dump(mode="json"),
        )
        return self.require_job(job_id)

    def update_progress(
        self,
        job_id: str,
        status: RuntimeJobStatus,
        progress: RuntimeJobProgress,
    ) -> RuntimeJobRecord:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runtime_jobs
                SET status = ?, progress_json = ?
                WHERE job_id = ?
                """,
                (
                    status.value,
                    json.dumps(progress.model_dump(mode="json"), sort_keys=True),
                    job_id,
                ),
            )
        self.append_event(
            job_id=job_id,
            event_type="progress",
            status=status,
            message=progress.message,
            payload=progress.model_dump(mode="json"),
        )
        return self.require_job(job_id)

    def finish_job(
        self,
        job_id: str,
        status: RuntimeJobStatus,
        progress: RuntimeJobProgress,
        *,
        result_ref: str | None = None,
        warnings: list[str] | None = None,
    ) -> RuntimeJobRecord:
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runtime_jobs
                SET status = ?,
                    progress_json = ?,
                    finished_at = ?,
                    result_ref = COALESCE(?, result_ref),
                    warnings_json = ?
                WHERE job_id = ?
                """,
                (
                    status.value,
                    json.dumps(progress.model_dump(mode="json"), sort_keys=True),
                    timestamp,
                    result_ref,
                    json.dumps(warnings or [], sort_keys=True),
                    job_id,
                ),
            )
        self.append_event(
            job_id=job_id,
            event_type="finished",
            status=status,
            message=progress.message,
            payload=progress.model_dump(mode="json"),
        )
        return self.require_job(job_id)

    def request_cancel(self, job_id: str) -> RuntimeJobRecord:
        job = self.require_job(job_id)
        timestamp = _utc_now()
        if job.status == RuntimeJobStatus.PENDING:
            progress = RuntimeJobProgress(
                stage="cancelled",
                message="Cancellation requested before the job started.",
            )
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE runtime_jobs
                    SET cancel_requested = 1,
                        status = ?,
                        finished_at = ?,
                        progress_json = ?
                    WHERE job_id = ?
                    """,
                    (
                        RuntimeJobStatus.CANCELLED.value,
                        timestamp,
                        json.dumps(progress.model_dump(mode="json"), sort_keys=True),
                        job_id,
                    ),
                )
            self.append_event(
                job_id=job_id,
                event_type="cancelled",
                status=RuntimeJobStatus.CANCELLED,
                message=progress.message,
                payload=progress.model_dump(mode="json"),
            )
            return self.require_job(job_id)

        with self._connect() as connection:
            connection.execute(
                "UPDATE runtime_jobs SET cancel_requested = 1 WHERE job_id = ?",
                (job_id,),
            )
        self.append_event(
            job_id=job_id,
            event_type="cancel_requested",
            status=job.status,
            message="Cancellation requested.",
        )
        return self.require_job(job_id)

    def append_event(
        self,
        *,
        job_id: str,
        event_type: str,
        status: RuntimeJobStatus,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeJobEvent:
        event_id = f"job-event-{uuid4()}"
        timestamp = _utc_now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM runtime_job_events WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            sequence = int(row[0]) if row else 1
            connection.execute(
                """
                INSERT INTO runtime_job_events(
                    event_id,
                    job_id,
                    sequence,
                    event_type,
                    status,
                    message,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    job_id,
                    sequence,
                    event_type,
                    status.value,
                    message,
                    json.dumps(payload or {}, sort_keys=True),
                    timestamp,
                ),
            )
        return RuntimeJobEvent(
            event_id=event_id,
            job_id=job_id,
            sequence=sequence,
            event_type=event_type,
            status=status,
            message=message,
            payload=payload or {},
            created_at=timestamp,
        )

    def list_events(self, job_id: str) -> list[RuntimeJobEvent]:
        self.require_job(job_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM runtime_job_events
                WHERE job_id = ?
                ORDER BY sequence
                """,
                (job_id,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def find_cache_hit(self, keys: list[RuntimeCacheKey]) -> RuntimeCacheEntry | None:
        if not keys:
            return None
        checksums = [key.checksum for key in keys]
        placeholders = ", ".join("?" for _ in checksums)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM runtime_cache_entries
                WHERE cache_checksum IN ({placeholders})
                  AND result_ref IS NOT NULL
                """,
                tuple(checksums),
            ).fetchall()
            if len(rows) != len(checksums):
                return None
            timestamp = _utc_now()
            connection.execute(
                f"""
                UPDATE runtime_cache_entries
                SET last_hit_at = ?, hit_count = hit_count + 1
                WHERE cache_checksum IN ({placeholders})
                """,
                (timestamp, *checksums),
            )
        return _cache_entry_from_row(rows[0])

    def record_cache_entries(
        self,
        keys: list[RuntimeCacheKey],
        *,
        result_ref: str | None,
        result_checksum: str | None,
    ) -> None:
        timestamp = _utc_now()
        with self._connect() as connection:
            for key in keys:
                connection.execute(
                    """
                    INSERT INTO runtime_cache_entries(
                        cache_checksum,
                        cache_key_json,
                        result_ref,
                        result_checksum,
                        source_versions_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_checksum) DO UPDATE SET
                        cache_key_json = excluded.cache_key_json,
                        result_ref = excluded.result_ref,
                        result_checksum = excluded.result_checksum,
                        source_versions_json = excluded.source_versions_json
                    """,
                    (
                        key.checksum,
                        json.dumps(key.model_dump(mode="json"), sort_keys=True),
                        result_ref,
                        result_checksum,
                        json.dumps(key.source_versions, sort_keys=True),
                        timestamp,
                    ),
                )

    def save_schedule(
        self,
        project_id: str,
        request: RuntimeScheduleRequest,
    ) -> RuntimeScheduleRecord:
        timestamp = _utc_now()
        schedule_id = f"schedule-{request.radar_id}" if request.radar_id else f"schedule-{uuid4()}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO radar_schedules(
                    schedule_id,
                    project_id,
                    radar_id,
                    methodology_id,
                    cadence,
                    enabled,
                    timezone,
                    next_run_at,
                    definition_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    radar_id = excluded.radar_id,
                    methodology_id = excluded.methodology_id,
                    cadence = excluded.cadence,
                    enabled = excluded.enabled,
                    timezone = excluded.timezone,
                    next_run_at = excluded.next_run_at,
                    definition_json = excluded.definition_json,
                    updated_at = excluded.updated_at
                """,
                (
                    schedule_id,
                    project_id,
                    request.radar_id,
                    request.methodology_id,
                    request.cadence.value,
                    int(request.enabled),
                    request.timezone,
                    request.next_run_at,
                    json.dumps(request.definition, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        return self.require_schedule(schedule_id)

    def require_schedule(self, schedule_id: str) -> RuntimeScheduleRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM radar_schedules WHERE schedule_id = ?",
                (schedule_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA schedule: {schedule_id}")
        return _schedule_from_row(row)

    def list_schedules(self, project_id: str | None = None) -> list[RuntimeScheduleRecord]:
        where_sql = "WHERE project_id = ?" if project_id is not None else ""
        params = (project_id,) if project_id is not None else ()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM radar_schedules
                {where_sql}
                ORDER BY updated_at DESC
                """,
                params,
            ).fetchall()
        return [_schedule_from_row(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(RUNTIME_JOB_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def get_runtime_job_store(path: str | Path | None = None) -> RuntimeJobStore:
    return RuntimeJobStore(path)


def start_runtime_job_background(job_id: str) -> Thread:
    thread = Thread(target=run_runtime_job, args=(job_id,), daemon=True)
    thread.start()
    return thread


def run_runtime_job(
    job_id: str,
    *,
    registry: AttributeRegistry | None = None,
    runtime_store: RuntimeJobStore | None = None,
) -> RuntimeJobRecord:
    active_store = runtime_store or get_runtime_job_store()
    job = active_store.require_job(job_id)
    if job.cancel_requested or job.status == RuntimeJobStatus.CANCELLED:
        return active_store.finish_job(
            job_id,
            RuntimeJobStatus.CANCELLED,
            RuntimeJobProgress(stage="cancelled", message="Job was cancelled before start."),
        )

    try:
        active_registry = registry or load_attribute_registry()
        request = RuntimeJobCreateRequest.model_validate(job.request)
        active_store.mark_running(
            job_id,
            RuntimeJobProgress(stage="starting", message="Runtime job started."),
        )
        if request.job_type == RuntimeJobType.METHODOLOGY_RUN:
            return _run_methodology_job(job_id, request, active_registry, active_store)
        return _run_batch_job(job_id, request, active_registry, active_store)
    except Exception as exc:
        return active_store.finish_job(
            job_id,
            RuntimeJobStatus.FAILED,
            RuntimeJobProgress(stage="failed", message=str(exc)),
            warnings=["runtime_job_failed"],
        )


def build_runtime_cache_keys(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
    *,
    timestamp_cutoff: str | None = None,
    source_versions: dict[str, str] | None = None,
    connector_states: dict[str, str] | None = None,
    strategy_profile_hash: str | None = None,
) -> list[RuntimeCacheKey]:
    graph_hash = hash_methodology_graph(graph)
    metadata = graph.metadata or {}
    universe_version = _universe_version(graph)
    active_source_versions = _source_versions_from_graph(metadata)
    active_source_versions.update(source_versions or {})
    active_connector_states = _connector_states(registry)
    active_connector_states.update(connector_states or {})
    attribute_versions = _attribute_versions(graph, registry)
    module_id = _read_string(metadata.get("module_id"), "viza.core.strategy")
    cutoff = timestamp_cutoff or _read_optional_string(metadata.get("timestamp_cutoff"))
    keys: list[RuntimeCacheKey] = []
    for node_id in compile_execution_plan(graph).ordered_node_ids:
        key = RuntimeCacheKey(
            node_id=node_id,
            graph_hash=graph_hash,
            module_id=module_id,
            universe_version=universe_version,
            timestamp_cutoff=cutoff,
            attribute_versions=attribute_versions,
            source_versions=active_source_versions,
            connector_states=active_connector_states,
            strategy_profile_hash=strategy_profile_hash,
        )
        key.checksum = stable_checksum(key.model_dump(mode="json", exclude={"checksum"}))
        keys.append(key)
    return keys


def _run_methodology_job(
    job_id: str,
    request: RuntimeJobCreateRequest,
    registry: AttributeRegistry,
    runtime_store: RuntimeJobStore,
) -> RuntimeJobRecord:
    if request.graph is None:
        raise ValueError("methodology_run jobs require graph")
    keys = build_runtime_cache_keys(
        request.graph,
        registry,
        timestamp_cutoff=request.timestamp_cutoff,
        source_versions=request.source_versions,
        connector_states=request.connector_states,
        strategy_profile_hash=request.strategy_profile_hash,
    )
    cache_hit = runtime_store.find_cache_hit(keys) if request.use_cache else None
    if cache_hit is not None:
        progress = RuntimeJobProgress(
            stage="completed",
            current=len(keys),
            total=len(keys),
            message="Runtime job completed from cache.",
            cache_status="hit",
            cache_key_count=len(keys),
            result_ref=cache_hit.result_ref,
        )
        return runtime_store.finish_job(
            job_id,
            RuntimeJobStatus.COMPLETED,
            progress,
            result_ref=cache_hit.result_ref,
        )

    runtime_store.update_progress(
        job_id,
        RuntimeJobStatus.RUNNING,
        RuntimeJobProgress(
            stage="running",
            current=0,
            total=max(len(keys), 1),
            message="Cache miss; running methodology.",
            cache_status="miss",
            cache_key_count=len(keys),
        ),
    )
    if runtime_store.require_job(job_id).cancel_requested:
        return runtime_store.finish_job(
            job_id,
            RuntimeJobStatus.CANCELLED,
            RuntimeJobProgress(stage="cancelled", message="Job cancelled before execution."),
        )

    result = run_methodology(request.graph, registry)
    result.manifest["runtime_job"] = {
        "job_id": job_id,
        "cache_status": "miss",
        "cache_key_count": len(keys),
    }
    result.manifest["runtime_cache_keys"] = [key.model_dump(mode="json") for key in keys]
    project_store = get_project_store()
    project_store.save_run_record(
        result_payload=result.model_dump(mode="json"),
        project_id=request.project_id,
        version_id=request.methodology_version_id,
    )
    runtime_store.record_cache_entries(
        keys,
        result_ref=result.run_id,
        result_checksum=result.result_checksum,
    )
    progress = RuntimeJobProgress(
        stage="completed",
        current=len(keys),
        total=len(keys),
        message="Runtime job completed.",
        cache_status="miss",
        cache_key_count=len(keys),
        result_ref=result.run_id,
    )
    return runtime_store.finish_job(
        job_id,
        RuntimeJobStatus.COMPLETED,
        progress,
        result_ref=result.run_id,
        warnings=[warning.code for warning in result.warnings],
    )


def _run_batch_job(
    job_id: str,
    request: RuntimeJobCreateRequest,
    registry: AttributeRegistry,
    runtime_store: RuntimeJobStore,
) -> RuntimeJobRecord:
    if request.batch_request is None:
        raise ValueError("batch_execution jobs require batch_request")
    batch_request = request.batch_request
    runtime_store.update_progress(
        job_id,
        RuntimeJobStatus.RUNNING,
        RuntimeJobProgress(
            stage="running",
            current=0,
            total=len(batch_request.cutoffs),
            message="Running batch job.",
            cache_status="not_checked",
        ),
    )
    if runtime_store.require_job(job_id).cancel_requested:
        return runtime_store.finish_job(
            job_id,
            RuntimeJobStatus.CANCELLED,
            RuntimeJobProgress(stage="cancelled", message="Job cancelled before batch execution."),
        )
    result = execute_batch(batch_request, registry, store=get_project_store())
    progress = RuntimeJobProgress(
        stage="completed",
        current=result.completed_runs,
        total=result.total_runs,
        message=f"Batch job {result.status}.",
        cache_status="not_checked",
        result_ref=result.batch_id,
    )
    status = (
        RuntimeJobStatus.CANCELLED
        if result.status == "cancelled"
        else RuntimeJobStatus.COMPLETED
        if result.failed_runs == 0
        else RuntimeJobStatus.FAILED
    )
    return runtime_store.finish_job(
        job_id,
        status,
        progress,
        result_ref=result.batch_id,
        warnings=_batch_warnings(result),
    )


def _batch_warnings(result: BatchExecutionResult) -> list[str]:
    warnings: list[str] = []
    for item in result.results:
        warnings.extend(item.warning_codes)
    return list(dict.fromkeys(warnings))


def _attribute_versions(graph: MethodologyGraph, registry: AttributeRegistry) -> dict[str, str]:
    keys = set(graph.attribute_keys())
    for node in graph.nodes_by_type(VizaNodeType.OUTPUT_RADAR):
        keys.update(_read_string_list(node.config.get("columns")))
    versions: dict[str, str] = {}
    for key in sorted(keys):
        attribute = registry.get(key)
        if attribute is not None:
            versions[key] = f"{attribute.data_version}|{attribute.model_version}"
    return versions


def _source_versions_from_graph(metadata: dict[str, Any]) -> dict[str, str]:
    source_versions: dict[str, str] = {}
    raw_source_versions = metadata.get("source_versions")
    if isinstance(raw_source_versions, dict):
        source_versions.update(
            {str(key): str(value) for key, value in raw_source_versions.items()}
        )
    for key in ("universe_version", "observation_version", "event_version"):
        value = metadata.get(key)
        if isinstance(value, str) and value:
            source_versions[key] = value
    return source_versions


def _connector_states(registry: AttributeRegistry) -> dict[str, str]:
    return {
        connector.connector_id: connector.status
        for connector in load_connector_catalog(registry)
    }


def _universe_version(graph: MethodologyGraph) -> str | None:
    for node in graph.nodes_by_type(VizaNodeType.UNIVERSE):
        version = node.config.get("universe_version")
        if isinstance(version, str) and version:
            return version
    return None


def _job_from_row(row: sqlite3.Row) -> RuntimeJobRecord:
    return RuntimeJobRecord(
        job_id=row["job_id"],
        project_id=row["project_id"],
        job_type=RuntimeJobType(row["job_type"]),
        status=RuntimeJobStatus(row["status"]),
        request=json.loads(row["request_json"]),
        progress=RuntimeJobProgress.model_validate(json.loads(row["progress_json"])),
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        cancel_requested=bool(row["cancel_requested"]),
        result_ref=row["result_ref"],
        warnings=_read_string_list(json.loads(row["warnings_json"])),
    )


def _event_from_row(row: sqlite3.Row) -> RuntimeJobEvent:
    return RuntimeJobEvent(
        event_id=row["event_id"],
        job_id=row["job_id"],
        sequence=row["sequence"],
        event_type=row["event_type"],
        status=RuntimeJobStatus(row["status"]),
        message=row["message"],
        payload=json.loads(row["payload_json"]),
        created_at=row["created_at"],
    )


def _cache_entry_from_row(row: sqlite3.Row) -> RuntimeCacheEntry:
    return RuntimeCacheEntry(
        cache_checksum=row["cache_checksum"],
        cache_key=RuntimeCacheKey.model_validate(json.loads(row["cache_key_json"])),
        result_ref=row["result_ref"],
        result_checksum=row["result_checksum"],
        source_versions=json.loads(row["source_versions_json"]),
        created_at=row["created_at"],
        last_hit_at=row["last_hit_at"],
        hit_count=row["hit_count"],
    )


def _schedule_from_row(row: sqlite3.Row) -> RuntimeScheduleRecord:
    return RuntimeScheduleRecord(
        schedule_id=row["schedule_id"],
        project_id=row["project_id"],
        radar_id=row["radar_id"],
        methodology_id=row["methodology_id"],
        cadence=ScheduleCadence(row["cadence"]),
        enabled=bool(row["enabled"]),
        timezone=row["timezone"],
        next_run_at=row["next_run_at"],
        definition=json.loads(row["definition_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _read_string(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) and value else fallback


def _read_optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _read_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


RUNTIME_JOB_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS runtime_jobs (
  job_id TEXT PRIMARY KEY,
  project_id TEXT,
  job_type TEXT NOT NULL,
  status TEXT NOT NULL,
  request_json TEXT NOT NULL,
  progress_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0,
  result_ref TEXT,
  warnings_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS runtime_job_events (
  event_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_cache_entries (
  cache_checksum TEXT PRIMARY KEY,
  cache_key_json TEXT NOT NULL,
  result_ref TEXT,
  result_checksum TEXT,
  source_versions_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  last_hit_at TEXT,
  hit_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS radar_schedules (
  schedule_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  radar_id TEXT,
  methodology_id TEXT,
  cadence TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  timezone TEXT NOT NULL DEFAULT 'local',
  next_run_at TEXT,
  definition_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runtime_job_events_job
  ON runtime_job_events(job_id, sequence);

CREATE INDEX IF NOT EXISTS idx_radar_schedules_project
  ON radar_schedules(project_id, updated_at DESC);
"""
