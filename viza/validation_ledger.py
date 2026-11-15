from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.audit import (
    ReproducibilityCheck,
    compare_manifests,
    point_in_time_evidence_checks,
    point_in_time_summary,
    stable_checksum,
)
from viza.attribute_registry import load_attribute_registry
from viza.execution import MethodologyRunResult, run_methodology
from viza.graph_schema import MethodologyGraph
from viza.project_store import get_project_store, project_store_path

# NOTE: viza.file_format.container.read_viza_section is imported lazily inside
# read_validation_proof_from_viza below to break the import cycle with
# viza.marketplace (which imports VizaValidationRecord from this module).


class VizaValidationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["viza.validation_record.v1"] = Field(
        default="viza.validation_record.v1",
        alias="schema",
    )
    validation_record_id: str
    strategy_or_methodology_id: str
    strategy_profile_id: str | None = None
    run_id: str
    graph_hash: str
    result_checksum: str
    timestamp_cutoff: datetime | None = None
    generated_at: datetime
    domain: str
    module_id: str
    entity_universe: dict[str, Any] = Field(default_factory=dict)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    evidence_checksum: str
    data_versions: list[str] = Field(default_factory=list)
    model_versions: list[str] = Field(default_factory=list)
    connector_states: list[dict[str, Any]] = Field(default_factory=list)
    PIT_summary: dict[str, Any] = Field(default_factory=dict)
    performance_observation: dict[str, Any] = Field(default_factory=dict)
    in_sample_out_of_sample_label: str = "not_labeled"
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    source_rights: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_checksums(self) -> "VizaValidationRecord":
        if not self.graph_hash or not self.result_checksum or not self.evidence_checksum:
            raise ValueError("validation records require graph, result, and evidence checksums")
        return self


class ValidationRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: MethodologyRunResult | dict[str, Any] | None = None
    run_id: str | None = None
    strategy_profile_id: str | None = None
    domain: str = "finance"
    module_id: str = "viza.finance.securities"
    in_sample_out_of_sample_label: str = "not_labeled"
    performance_observation: dict[str, Any] = Field(
        default_factory=lambda: {"status": "pending", "evaluation_window": "2d-3w"}
    )
    persist: bool = True

    @model_validator(mode="after")
    def require_result_or_run(self) -> "ValidationRecordRequest":
        if self.result is None and self.run_id is None:
            raise ValueError("validation record requires result or run_id")
        return self


class ValidationCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_record_id: str
    candidate_record_id: str


class ValidationCompareResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_record_id: str
    candidate_record_id: str
    matching: bool
    checks: list[ReproducibilityCheck] = Field(default_factory=list)


class ValidationReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_record_id: str
    graph: MethodologyGraph


class ValidationReplayResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_record_id: str
    replayable: bool
    matching: bool
    checks: list[ReproducibilityCheck] = Field(default_factory=list)
    run_id: str | None = None
    result_checksum: str | None = None
    status: str


class ValidationLedgerStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save_record(self, record: VizaValidationRecord) -> VizaValidationRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO validation_records(
                    validation_record_id,
                    strategy_or_methodology_id,
                    strategy_profile_id,
                    run_id,
                    graph_hash,
                    result_checksum,
                    timestamp_cutoff,
                    generated_at,
                    domain,
                    module_id,
                    record_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.validation_record_id,
                    record.strategy_or_methodology_id,
                    record.strategy_profile_id,
                    record.run_id,
                    record.graph_hash,
                    record.result_checksum,
                    record.timestamp_cutoff.isoformat() if record.timestamp_cutoff else None,
                    record.generated_at.isoformat(),
                    record.domain,
                    record.module_id,
                    json.dumps(record.model_dump(mode="json"), sort_keys=True),
                ),
            )
        return record

    def require_record(self, validation_record_id: str) -> VizaValidationRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT record_json
                FROM validation_records
                WHERE validation_record_id = ?
                """,
                (validation_record_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA validation record: {validation_record_id}")
        return VizaValidationRecord.model_validate(json.loads(row["record_json"]))

    def list_by_run(self, run_id: str) -> list[VizaValidationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT record_json
                FROM validation_records
                WHERE run_id = ?
                ORDER BY generated_at DESC
                """,
                (run_id,),
            ).fetchall()
        return [VizaValidationRecord.model_validate(json.loads(row["record_json"])) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(VALIDATION_RECORDS_TABLE_SQL)


VALIDATION_RECORDS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS validation_records (
  validation_record_id TEXT PRIMARY KEY,
  strategy_or_methodology_id TEXT NOT NULL,
  strategy_profile_id TEXT,
  run_id TEXT NOT NULL,
  graph_hash TEXT NOT NULL,
  result_checksum TEXT NOT NULL,
  timestamp_cutoff TEXT,
  generated_at TEXT NOT NULL,
  domain TEXT,
  module_id TEXT,
  record_json TEXT NOT NULL
)
"""


def get_validation_ledger_store(path: str | Path | None = None) -> ValidationLedgerStore:
    return ValidationLedgerStore(path)


def create_validation_record(request: ValidationRecordRequest) -> VizaValidationRecord:
    result_payload = _request_result_payload(request)
    record = validation_record_from_result(
        result_payload,
        strategy_profile_id=request.strategy_profile_id,
        domain=request.domain,
        module_id=request.module_id,
        in_sample_out_of_sample_label=request.in_sample_out_of_sample_label,
        performance_observation=request.performance_observation,
    )
    if request.persist:
        get_validation_ledger_store().save_record(record)
    return record


def validation_record_from_result(
    result: MethodologyRunResult | dict[str, Any],
    *,
    strategy_profile_id: str | None = None,
    domain: str = "finance",
    module_id: str = "viza.finance.securities",
    in_sample_out_of_sample_label: str = "not_labeled",
    performance_observation: dict[str, Any] | None = None,
) -> VizaValidationRecord:
    result_payload = _model_payload(result)
    manifest = _read_dict(result_payload.get("manifest"))
    graph_hash = _read_string(result_payload.get("graph_hash")) or _read_string(manifest.get("graph_hash"))
    result_checksum = _read_string(result_payload.get("result_checksum")) or _read_string(
        manifest.get("result_checksum")
    )
    evidence_checksum = _read_string(manifest.get("evidence_checksum"))
    if not graph_hash or not result_checksum or not evidence_checksum:
        raise ValueError("validation proof cannot be recorded without required checksums")

    timestamp_cutoff = _parse_optional_datetime(
        result_payload.get("timestamp_cutoff") or manifest.get("timestamp_cutoff")
    )
    generated_at = datetime.now(timezone.utc)
    strategy_id = strategy_profile_id or _first_strategy_profile_id(result_payload)
    record_payload = {
        "strategy_or_methodology_id": _read_string(result_payload.get("methodology_id"), "unknown"),
        "strategy_profile_id": strategy_id,
        "run_id": _read_string(result_payload.get("run_id")),
        "graph_hash": graph_hash,
        "result_checksum": result_checksum,
        "timestamp_cutoff": timestamp_cutoff.isoformat() if timestamp_cutoff else None,
        "generated_at": generated_at.isoformat(),
        "domain": domain,
        "module_id": module_id,
        "entity_universe": _entity_universe(result_payload),
        "outputs": _output_references(result_payload),
        "evidence_checksum": evidence_checksum,
        "data_versions": _read_string_list(manifest.get("data_versions")),
        "model_versions": _read_string_list(manifest.get("model_versions")),
        "connector_states": _connector_states(manifest),
        "PIT_summary": _pit_summary(result_payload, manifest),
        "performance_observation": performance_observation
        or {"status": "pending", "evaluation_window": "2d-3w"},
        "in_sample_out_of_sample_label": in_sample_out_of_sample_label,
        "warnings": _warnings(result_payload),
        "source_rights": _source_rights(manifest),
    }
    record_payload["validation_record_id"] = "validation-" + stable_checksum(record_payload)[:24]
    return VizaValidationRecord.model_validate(record_payload)


def compare_validation_records(
    request: ValidationCompareRequest,
    store: ValidationLedgerStore | None = None,
) -> ValidationCompareResult:
    active_store = store or get_validation_ledger_store()
    baseline = active_store.require_record(request.baseline_record_id)
    candidate = active_store.require_record(request.candidate_record_id)
    checks = [
        _compare_record_field("graph_hash", baseline, candidate),
        _compare_record_field("result_checksum", baseline, candidate),
        _compare_record_field("evidence_checksum", baseline, candidate),
        _compare_record_field("data_versions", baseline, candidate),
        _compare_record_field("model_versions", baseline, candidate),
        _compare_record_field("connector_states", baseline, candidate),
        _compare_record_field("PIT_summary", baseline, candidate),
    ]
    return ValidationCompareResult(
        baseline_record_id=baseline.validation_record_id,
        candidate_record_id=candidate.validation_record_id,
        matching=all(check.status == "match" for check in checks),
        checks=checks,
    )


def replay_validation_record(
    request: ValidationReplayRequest,
    store: ValidationLedgerStore | None = None,
) -> ValidationReplayResult:
    active_store = store or get_validation_ledger_store()
    record = active_store.require_record(request.validation_record_id)
    result = run_methodology(request.graph, load_attribute_registry())
    baseline_manifest = _replay_manifest_for_record(record)
    observed_manifest = result.manifest
    checks = compare_manifests(baseline_manifest, observed_manifest)
    matching = all(check.status == "match" for check in checks)
    return ValidationReplayResult(
        validation_record_id=record.validation_record_id,
        replayable=True,
        matching=matching,
        checks=checks,
        run_id=result.run_id,
        result_checksum=result.result_checksum,
        status="replayed",
    )


def validation_proof_for_export(record: VizaValidationRecord) -> dict[str, Any]:
    proof = {
        "schema": record.schema_name,
        "validation_record_id": record.validation_record_id,
        "run_id": record.run_id,
        "run_ids": [record.run_id],
        "graph_hash": record.graph_hash,
        "result_checksum": record.result_checksum,
        "evidence_checksum": record.evidence_checksum,
        "PIT_summary": record.PIT_summary,
        "data_versions": record.data_versions,
        "model_versions": record.model_versions,
        "connector_states": {
            item.get("connector_id", f"connector_{index}"): item.get("status", "unknown")
            for index, item in enumerate(record.connector_states)
        },
        "entitlement_states": {
            item.get("connector_id", f"connector_{index}"): _safe_entitlement_state(
                item.get("entitlement", {})
            )
            for index, item in enumerate(record.connector_states)
        },
        "source_rights": record.source_rights,
        "output_references": record.outputs,
        "warnings": record.warnings,
        "warning_codes": [
            warning.get("code")
            for warning in record.warnings
            if isinstance(warning.get("code"), str)
        ],
        "performance_observation": record.performance_observation,
        "not_performance_claim": record.performance_observation.get("status") == "pending",
    }
    validate_validation_proof(proof)
    return proof


def _replay_manifest_for_record(record: VizaValidationRecord) -> dict[str, Any]:
    return {
        "graph_hash": record.graph_hash,
        "result_checksum": record.result_checksum,
        "data_versions": record.data_versions,
        "model_versions": record.model_versions,
        "connector_states": {
            item.get("connector_id", f"connector_{index}"): item.get("status", "unknown")
            for index, item in enumerate(record.connector_states)
        },
        "entitlement_states": {
            item.get("connector_id", f"connector_{index}"): item.get("entitlement", {})
            for index, item in enumerate(record.connector_states)
        },
        "warning_codes": [
            warning.get("code")
            for warning in record.warnings
            if isinstance(warning.get("code"), str)
        ],
    }


def read_validation_proof_from_viza(path: str | Path) -> dict[str, Any]:
    from viza.file_format.container import read_viza_section  # local import: cycle break

    section = read_viza_section(path, "validation_proof")
    try:
        proof = json.loads(section.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("validation proof section must be JSON") from exc
    if not isinstance(proof, dict):
        raise ValueError("validation proof section must be an object")
    validate_validation_proof(proof)
    return proof


def validate_validation_proof(proof: dict[str, Any]) -> None:
    for field_name in ["run_id", "graph_hash", "result_checksum", "evidence_checksum"]:
        if not _read_string(proof.get(field_name)):
            raise ValueError(f"validation proof missing {field_name}")
    performance = proof.get("performance_observation")
    if isinstance(performance, dict) and performance.get("status") == "complete":
        raise ValueError("validation proof cannot claim completed performance without observations")


def _request_result_payload(request: ValidationRecordRequest) -> MethodologyRunResult | dict[str, Any]:
    if request.result is not None:
        return request.result
    if request.run_id is None:
        raise ValueError("validation record requires result or run_id")
    record = get_project_store().require_run_record(request.run_id)
    if record.result is None:
        raise ValueError(f"run {request.run_id} has no persisted result payload")
    return record.result


def _compare_record_field(
    field_name: str,
    baseline: VizaValidationRecord,
    candidate: VizaValidationRecord,
) -> ReproducibilityCheck:
    expected = getattr(baseline, field_name)
    observed = getattr(candidate, field_name)
    status = "match" if expected == observed else "mismatch"
    return ReproducibilityCheck(
        name=field_name,
        status=status,
        expected=expected,
        observed=observed,
        message=f"{field_name} matched." if status == "match" else f"{field_name} changed.",
    )


def _model_payload(value: MethodologyRunResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, MethodologyRunResult):
        return value.model_dump(mode="json")
    return value


def _entity_universe(result: dict[str, Any]) -> dict[str, Any]:
    rows = _read_list(result.get("rows"))
    return {
        "row_count": len(rows),
        "entity_ids": sorted(
            {
                row.get("entity_id")
                for row in rows
                if isinstance(row.get("entity_id"), str) and row.get("entity_id")
            }
        ),
        "asset_ids": sorted(
            {
                row.get("asset_id")
                for row in rows
                if isinstance(row.get("asset_id"), str) and row.get("asset_id")
            }
        ),
        "tickers": [row["ticker"] for row in rows if isinstance(row.get("ticker"), str)],
    }


def _output_references(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _read_list(result.get("rows"))
    outputs = []
    for row in rows[:100]:
        outputs.append(
            {
                "ticker": row.get("ticker"),
                "entity_id": row.get("entity_id"),
                "asset_id": row.get("asset_id"),
                "rank": row.get("rank"),
                "score": row.get("score"),
                "strategy_fit_score": row.get("strategy_fit_score"),
                "result_checksum": result.get("result_checksum"),
            }
        )
    return outputs


def _pit_summary(result: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    existing = manifest.get("point_in_time")
    if isinstance(existing, dict):
        return existing
    cutoff = result.get("timestamp_cutoff") or manifest.get("timestamp_cutoff")
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    if isinstance(cutoff, str) and cutoff:
        return point_in_time_summary(point_in_time_evidence_checks(evidence, cutoff))
    return {"status": "not_available", "checked_count": 0}


def _connector_states(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    connectors = manifest.get("connectors")
    if not isinstance(connectors, dict):
        return []
    states = []
    for connector_id, raw_connector in connectors.items():
        if not isinstance(connector_id, str) or not isinstance(raw_connector, dict):
            continue
        entitlement = raw_connector.get("entitlement") if isinstance(raw_connector.get("entitlement"), dict) else {}
        states.append(
            {
                "connector_id": connector_id,
                "status": _read_string(raw_connector.get("status"), "unknown"),
                "data_version": _read_string(raw_connector.get("data_version")),
                "model_version": _read_string(raw_connector.get("model_version")),
                "export_allowed": entitlement.get("export_allowed"),
                "redistribution_allowed": entitlement.get("redistribution_allowed"),
                "entitlement": entitlement,
            }
        )
    return states


def _source_rights(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "connector_id": state["connector_id"],
            "export_allowed": state.get("export_allowed"),
            "redistribution_allowed": state.get("redistribution_allowed"),
        }
        for state in _connector_states(manifest)
    ]


def _safe_entitlement_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    blocked_fragments = ("credential", "secret", "token", "password", "api_key")
    return {
        key: nested_value
        for key, nested_value in value.items()
        if not any(fragment in str(key).lower() for fragment in blocked_fragments)
    }


def _warnings(result: dict[str, Any]) -> list[dict[str, Any]]:
    return _read_list(result.get("warnings"))


def _first_strategy_profile_id(result: dict[str, Any]) -> str | None:
    translations = _read_list(result.get("translations"))
    for translation in translations:
        strategy_profile_id = translation.get("strategy_profile_id")
        if isinstance(strategy_profile_id, str) and strategy_profile_id:
            return strategy_profile_id
    return None


def _parse_optional_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _read_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _read_string(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) else fallback
