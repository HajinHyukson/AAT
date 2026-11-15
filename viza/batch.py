from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.audit import (
    PointInTimeEvidenceCheck,
    point_in_time_evidence_checks,
    point_in_time_summary,
    stable_checksum,
)
from viza.attribute_registry import AttributeRegistry
from viza.execution import MethodologyRunResult, VizaExecutionStatus, run_methodology
from viza.graph_schema import MethodologyGraph, VizaNodeType
from viza.project_store import ProjectStore
from viza.runtime import compile_execution_plan, hash_methodology_graph


class BatchMethodologyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: MethodologyGraph
    methodology_version_id: str | None = None
    label: str | None = None


class BatchExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: MethodologyGraph | None = None
    methodologies: list[BatchMethodologyInput] = Field(default_factory=list)
    cutoffs: list[str] = Field(default_factory=list)
    project_id: str | None = None
    persist_results: bool = True
    ticker_subset: list[str] = Field(default_factory=list)
    universe_name: str | None = None
    universe_version: str | None = None
    cancel_after_runs: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_batch_shape(self) -> BatchExecutionRequest:
        if not self.cutoffs:
            raise ValueError("batch execution requires at least one cutoff")
        if self.graph is None and not self.methodologies:
            raise ValueError("batch execution requires graph or methodologies")
        if self.graph is not None and self.methodologies:
            raise ValueError("send either graph or methodologies, not both")
        return self


class BatchCacheKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    graph_hash: str
    universe_version: str | None = None
    timestamp_cutoff: str
    attribute_versions: dict[str, str] = Field(default_factory=dict)
    source_versions: dict[str, str] = Field(default_factory=dict)
    checksum: str = ""


class BatchRunDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_count: int = 0
    relationship_count: int = 0
    warning_count: int = 0
    top_ticker: str | None = None
    score_min: float | None = None
    score_max: float | None = None
    score_mean: float | None = None
    pit_status: str = "not_run"
    pit_checked_count: int = 0
    pit_violation_count: int = 0
    pit_not_applicable_count: int = 0


class BatchRunItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    cutoff: str
    methodology_id: str
    methodology_version_id: str | None = None
    label: str | None = None
    run_id: str | None = None
    status: str
    graph_hash: str = ""
    result_checksum: str = ""
    warning_codes: list[str] = Field(default_factory=list)
    pit_status: str = "not_run"
    pit_checks: list[PointInTimeEvidenceCheck] = Field(default_factory=list)
    diagnostics: BatchRunDiagnostics = Field(default_factory=BatchRunDiagnostics)
    cache_keys: list[BatchCacheKey] = Field(default_factory=list)
    error: str | None = None
    result: MethodologyRunResult | None = None


class BatchProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    total: int
    cutoff: str | None = None
    methodology_id: str | None = None
    methodology_version_id: str | None = None
    run_id: str | None = None
    status: str
    message: str = ""


class BatchExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    status: str
    started_at: str
    finished_at: str
    total_runs: int
    completed_runs: int = 0
    failed_runs: int = 0
    cancelled_runs: int = 0
    progress: list[BatchProgressEvent] = Field(default_factory=list)
    results: list[BatchRunItem] = Field(default_factory=list)


def execute_batch(
    request: BatchExecutionRequest,
    registry: AttributeRegistry,
    store: ProjectStore | None = None,
) -> BatchExecutionResult:
    batch_id = f"batch-{uuid4()}"
    started_at = _utc_now()
    methodology_inputs = _methodology_inputs(request)
    total_runs = len(methodology_inputs) * len(request.cutoffs)
    progress: list[BatchProgressEvent] = []
    results: list[BatchRunItem] = []

    for methodology in methodology_inputs:
        for cutoff in request.cutoffs:
            sequence = len(results) + 1
            if request.cancel_after_runs is not None and sequence > request.cancel_after_runs:
                cancelled_runs = total_runs - len(results)
                progress.append(
                    BatchProgressEvent(
                        sequence=sequence,
                        total=total_runs,
                        cutoff=cutoff,
                        methodology_id=methodology.graph.methodology_id,
                        methodology_version_id=methodology.methodology_version_id,
                        status="cancelled",
                        message="Batch execution was cancelled before this run started.",
                    )
                )
                return _batch_result(
                    batch_id=batch_id,
                    started_at=started_at,
                    finished_at=_utc_now(),
                    total_runs=total_runs,
                    progress=progress,
                    results=results,
                    cancelled_runs=cancelled_runs,
                )

            progress.append(
                BatchProgressEvent(
                    sequence=sequence,
                    total=total_runs,
                    cutoff=cutoff,
                    methodology_id=methodology.graph.methodology_id,
                    methodology_version_id=methodology.methodology_version_id,
                    status="running",
                    message="Running methodology for cutoff.",
                )
            )
            item = _execute_batch_item(
                request=request,
                methodology=methodology,
                cutoff=cutoff,
                sequence=sequence,
                registry=registry,
                batch_id=batch_id,
                store=store,
            )
            results.append(item)
            progress.append(
                BatchProgressEvent(
                    sequence=sequence,
                    total=total_runs,
                    cutoff=cutoff,
                    methodology_id=item.methodology_id,
                    methodology_version_id=item.methodology_version_id,
                    run_id=item.run_id,
                    status=item.status,
                    message=_progress_message(item),
                )
            )

    return _batch_result(
        batch_id=batch_id,
        started_at=started_at,
        finished_at=_utc_now(),
        total_runs=total_runs,
        progress=progress,
        results=results,
        cancelled_runs=0,
    )


def _execute_batch_item(
    *,
    request: BatchExecutionRequest,
    methodology: BatchMethodologyInput,
    cutoff: str,
    sequence: int,
    registry: AttributeRegistry,
    batch_id: str,
    store: ProjectStore | None,
) -> BatchRunItem:
    graph = _graph_for_cutoff(
        methodology=methodology,
        cutoff=cutoff,
        request=request,
    )
    try:
        result = run_methodology(graph, registry)
        pit_checks = point_in_time_evidence_checks(result.evidence, cutoff)
        pit_summary = point_in_time_summary(pit_checks)
        cache_keys = _build_cache_keys(result, graph, registry, cutoff)
        diagnostics = _diagnostics(result, pit_summary)
        status = _item_status(result, pit_summary)
        result.manifest["batch"] = {
            "batch_id": batch_id,
            "sequence": sequence,
            "label": methodology.label,
            "persisted": bool(request.project_id and request.persist_results),
        }
        result.manifest["point_in_time"] = pit_summary
        result.manifest["cache_keys"] = [
            cache_key.model_dump(mode="json") for cache_key in cache_keys
        ]
        if store is not None and request.project_id and request.persist_results:
            store.save_run_record(
                result_payload=result.model_dump(mode="json"),
                project_id=request.project_id,
                version_id=methodology.methodology_version_id,
            )

        return BatchRunItem(
            sequence=sequence,
            cutoff=cutoff,
            methodology_id=result.methodology_id,
            methodology_version_id=methodology.methodology_version_id,
            label=methodology.label,
            run_id=result.run_id,
            status=status,
            graph_hash=result.graph_hash,
            result_checksum=result.result_checksum,
            warning_codes=[warning.code for warning in result.warnings],
            pit_status=str(pit_summary["status"]),
            pit_checks=pit_checks,
            diagnostics=diagnostics,
            cache_keys=cache_keys,
            result=result,
        )
    except Exception as exc:
        return BatchRunItem(
            sequence=sequence,
            cutoff=cutoff,
            methodology_id=graph.methodology_id,
            methodology_version_id=methodology.methodology_version_id,
            label=methodology.label,
            status="failed",
            graph_hash=hash_methodology_graph(graph),
            warning_codes=["batch_run_failed"],
            error=str(exc),
        )


def _methodology_inputs(request: BatchExecutionRequest) -> list[BatchMethodologyInput]:
    if request.methodologies:
        return request.methodologies
    if request.graph is None:
        return []
    return [BatchMethodologyInput(graph=request.graph)]


def _graph_for_cutoff(
    *,
    methodology: BatchMethodologyInput,
    cutoff: str,
    request: BatchExecutionRequest,
) -> MethodologyGraph:
    payload = methodology.graph.model_dump(mode="json")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["metadata"] = {
        **(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
        "run_mode": "batch_backtest",
        "timestamp_cutoff": cutoff,
    }
    if methodology.methodology_version_id:
        payload["metadata"]["methodology_version_id"] = methodology.methodology_version_id

    for node in payload["nodes"]:
        if node.get("type") != VizaNodeType.UNIVERSE.value:
            continue
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        config = {**config, "timestamp_cutoff": cutoff, "as_of": cutoff}
        if request.universe_name:
            config["universe_name"] = request.universe_name
        if request.universe_version:
            config["universe_version"] = request.universe_version
        if request.ticker_subset:
            config["ticker_subset"] = request.ticker_subset
        node["config"] = config

    return MethodologyGraph.model_validate(payload)


def _build_cache_keys(
    result: MethodologyRunResult,
    graph: MethodologyGraph,
    registry: AttributeRegistry,
    cutoff: str,
) -> list[BatchCacheKey]:
    manifest = result.manifest
    universe = manifest.get("universe") if isinstance(manifest.get("universe"), dict) else {}
    universe_version = universe.get("version") if isinstance(universe.get("version"), str) else None
    attribute_versions = _attribute_versions(graph, registry)
    source_versions = _source_versions(manifest)
    plan = compile_execution_plan(graph)
    keys: list[BatchCacheKey] = []
    for node_id in plan.ordered_node_ids:
        key = BatchCacheKey(
            node_id=node_id,
            graph_hash=result.graph_hash,
            universe_version=universe_version,
            timestamp_cutoff=cutoff,
            attribute_versions=attribute_versions,
            source_versions=source_versions,
        )
        key.checksum = stable_checksum(key.model_dump(mode="json", exclude={"checksum"}))
        keys.append(key)
    return keys


def _attribute_versions(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
) -> dict[str, str]:
    keys = set(graph.attribute_keys())
    for node in graph.nodes_by_type(VizaNodeType.OUTPUT_RADAR):
        keys.update(_read_string_list(node.config.get("columns")))

    versions: dict[str, str] = {}
    for key in sorted(keys):
        attribute = registry.get(key)
        if attribute is None:
            continue
        versions[key] = f"{attribute.data_version}|{attribute.model_version}"
    return versions


def _source_versions(manifest: dict[str, Any]) -> dict[str, str]:
    source_versions: dict[str, str] = {}
    connector_states = manifest.get("connector_states")
    if isinstance(connector_states, dict):
        for key, value in connector_states.items():
            if isinstance(key, str):
                source_versions[f"connector:{key}"] = str(value)
    for index, value in enumerate(_read_string_list(manifest.get("data_versions"))):
        source_versions[f"data:{index}"] = value
    for index, value in enumerate(_read_string_list(manifest.get("model_versions"))):
        source_versions[f"model:{index}"] = value
    return source_versions


def _diagnostics(
    result: MethodologyRunResult,
    pit_summary: dict[str, int | str],
) -> BatchRunDiagnostics:
    scores = [row.score for row in result.rows if row.score is not None]
    return BatchRunDiagnostics(
        row_count=len(result.rows),
        relationship_count=len(result.relationships),
        warning_count=len(result.warnings),
        top_ticker=result.rows[0].ticker if result.rows else None,
        score_min=min(scores) if scores else None,
        score_max=max(scores) if scores else None,
        score_mean=round(fmean(scores), 6) if scores else None,
        pit_status=str(pit_summary["status"]),
        pit_checked_count=int(pit_summary["checked_count"]),
        pit_violation_count=int(pit_summary["violation_count"]),
        pit_not_applicable_count=int(pit_summary["not_applicable_count"]),
    )


def _item_status(
    result: MethodologyRunResult,
    pit_summary: dict[str, int | str],
) -> str:
    if result.status == VizaExecutionStatus.FAILED:
        return "failed"
    if pit_summary["status"] == "failed":
        return "failed"
    if result.warnings:
        return "completed_with_warnings"
    return "completed"


def _batch_result(
    *,
    batch_id: str,
    started_at: str,
    finished_at: str,
    total_runs: int,
    progress: list[BatchProgressEvent],
    results: list[BatchRunItem],
    cancelled_runs: int,
) -> BatchExecutionResult:
    completed_runs = sum(
        1 for item in results if item.status in {"completed", "completed_with_warnings"}
    )
    failed_runs = sum(1 for item in results if item.status == "failed")
    status = "completed"
    if cancelled_runs:
        status = "cancelled"
    elif failed_runs:
        status = "completed_with_errors" if completed_runs else "failed"
    return BatchExecutionResult(
        batch_id=batch_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        total_runs=total_runs,
        completed_runs=completed_runs,
        failed_runs=failed_runs,
        cancelled_runs=cancelled_runs,
        progress=progress,
        results=results,
    )


def _progress_message(item: BatchRunItem) -> str:
    if item.error:
        return item.error
    return (
        f"{item.status}: {item.diagnostics.row_count} rows, "
        f"{item.diagnostics.pit_violation_count} PIT violations."
    )


def _read_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
