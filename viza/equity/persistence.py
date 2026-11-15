from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from viza.equity.registry import EQUITY_MODULE_ID, EQUITY_MODULE_VERSION
from viza.equity.runtime import NON_ADVICE_BOUNDARY, QUALITY_VALUE_PROFILE_ID
from viza.observations import (
    ObservationIngestRequest,
    ObservationInput,
    VizaObservation,
    get_observation_store,
)
from viza.project_store import get_project_store, project_store_path


EQUITY_PREVIEW_RUN_TYPE = "equity_runtime_wedge_preview"
EQUITY_PREVIEW_METHOD_ID = "viza.finance.equity_investment.equity_runtime_wedge_preview"


class EquityPreviewRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: str
    target_display_name: str
    cik: str | None = None
    ticker_alias: str | None = None
    profile_id: str = QUALITY_VALUE_PROFILE_ID
    status: Literal["pass", "warn", "block", "failed"]
    package_mode: Literal["white_box", "output_only", "marketplace_draft"]
    pit_status: Literal["pass", "warn", "block"]
    rights_status: Literal["pass", "warn", "block"]
    validation_status: Literal["pass", "warn", "block"]
    proof_checksum: str


class EquityPreviewRunList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[EquityPreviewRunSummary] = Field(default_factory=list)
    total: int = 0


class EquityPreviewRunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_record: dict[str, Any]
    target: dict[str, Any]
    evidence_bundle: dict[str, Any]
    observations: list[dict[str, Any]] = Field(default_factory=list)
    output_preview: dict[str, Any]
    validation_report: dict[str, Any]
    source_rights_report: dict[str, Any]
    package_redaction_preview: dict[str, Any]
    audit: dict[str, Any]


class EquityPreviewReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["replay_from_stored_observations", "replay_with_refresh"] = (
        "replay_from_stored_observations"
    )
    package_mode: Literal["white_box", "output_only", "marketplace_draft"] | None = None
    include_fmp: bool = False
    include_fred: bool = False


class EquityPreviewReplayResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    parent_run_id: str
    run_id: str
    preview: dict[str, Any]
    differences: list[dict[str, Any]] = Field(default_factory=list)


class PersistedEquityPreviewRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    proof_checksum: str
    observation_ids: list[str] = Field(default_factory=list)
    evidence_bundle_id: str
    validation_report_id: str
    source_rights_report_id: str
    package_redaction_preview_id: str
    history_url: str


class EquityPreviewStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def persist_preview_run(
        self,
        *,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        runtime_payload: dict[str, Any],
        created_from: str = "api_preview",
        parent_run_id: str | None = None,
    ) -> PersistedEquityPreviewRun:
        timestamp = _utc_now()
        run_id = f"eq-preview-run-{uuid4()}"
        target = _read_dict(response_payload.get("target"))
        profile = _read_dict(response_payload.get("profile"))
        audit = _read_dict(response_payload.get("audit"))
        validation = _read_dict(response_payload.get("validation_report"))
        rights = _read_dict(response_payload.get("source_rights_report"))
        package_preview = _read_dict(response_payload.get("package_redaction_preview"))
        evidence_summary = _read_dict(response_payload.get("evidence_summary"))
        input_payload = _preview_input_payload(request_payload)
        feature_flags = _read_dict(response_payload.get("feature_flags"))
        connector_modes = _connector_modes(response_payload, request_payload)
        warning_rows = list(profile.get("warnings") or [])
        block_rows = list(profile.get("blocks") or [])
        status = _status(profile.get("compatibility_status") or validation.get("status"))

        persisted_response = json.loads(json.dumps(response_payload, sort_keys=True, default=str))
        persisted_response["run_id"] = run_id
        persisted_response["persisted"] = True
        persisted_response["persistence_status"] = "persisted"
        persisted_response["history_url"] = f"/viza/equity/runtime-wedge/runs/{run_id}"
        persisted_response["proof_checksum"] = audit.get("proof_checksum") or _checksum(response_payload)
        persisted_response.setdefault("audit", {})["run_id"] = run_id

        request_hash = _checksum(input_payload)
        response_hash = _checksum(persisted_response)
        proof_checksum = _read_string(persisted_response.get("proof_checksum")) or response_hash
        graph_hash = _read_string(audit.get("graph_hash")) or _checksum(
            {"target": target, "evidence": evidence_summary}
        )
        profile_hash = _read_string(audit.get("profile_hash")) or _checksum(profile)[:32]
        pit_status = _status(_pit_status_from_response(response_payload))
        rights_status = _status(rights.get("status"))
        validation_status = _status(validation.get("status"))

        observation_ids = self._persist_observations(
            run_id=run_id,
            target=target,
            response_payload=persisted_response,
            runtime_payload=runtime_payload,
        )
        evidence_bundle = _evidence_bundle_payload(
            run_id=run_id,
            target=target,
            response_payload=persisted_response,
            observation_ids=observation_ids,
            created_at=timestamp,
        )
        evidence_bundle_id = f"eq-evidence-{_checksum(evidence_bundle)[:24].lower()}"
        validation_report_id = self._report_id(run_id, "validation_report", validation)
        rights_report_id = self._report_id(run_id, "source_rights_report", rights)
        package_report_id = self._report_id(run_id, "package_redaction_preview", package_preview)

        run_record = {
            "run_id": run_id,
            "module_id": EQUITY_MODULE_ID,
            "module_version": EQUITY_MODULE_VERSION,
            "run_type": EQUITY_PREVIEW_RUN_TYPE,
            "profile_id": profile.get("profile_id") or QUALITY_VALUE_PROFILE_ID,
            "target": target,
            "input": input_payload,
            "feature_flags": feature_flags,
            "connector_modes": connector_modes,
            "started_at": timestamp,
            "completed_at": timestamp,
            "status": status,
            "warnings": warning_rows,
            "blocks": block_rows,
            "graph_hash": graph_hash,
            "profile_hash": profile_hash,
            "request_hash": request_hash,
            "response_hash": response_hash,
            "proof_checksum": proof_checksum,
            "created_from": created_from,
            "parent_run_id": parent_run_id,
            "package_mode": package_preview.get("package_mode") or input_payload.get("package_mode"),
            "pit_status": pit_status,
            "rights_status": rights_status,
            "validation_status": validation_status,
            "observation_ids": observation_ids,
            "evidence_bundle_id": evidence_bundle_id,
            "validation_report_id": validation_report_id,
            "source_rights_report_id": rights_report_id,
            "package_redaction_preview_id": package_report_id,
            "history_url": f"/viza/equity/runtime-wedge/runs/{run_id}",
        }

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO equity_preview_runs(
                    run_id,
                    parent_run_id,
                    module_id,
                    module_version,
                    run_type,
                    profile_id,
                    target_json,
                    input_json,
                    feature_flags_json,
                    connector_modes_json,
                    started_at,
                    completed_at,
                    status,
                    warnings_json,
                    blocks_json,
                    graph_hash,
                    profile_hash,
                    request_hash,
                    response_hash,
                    proof_checksum,
                    created_from,
                    package_mode,
                    pit_status,
                    rights_status,
                    validation_status,
                    persisted_payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    parent_run_id,
                    EQUITY_MODULE_ID,
                    EQUITY_MODULE_VERSION,
                    EQUITY_PREVIEW_RUN_TYPE,
                    run_record["profile_id"],
                    _json(target),
                    _json(input_payload),
                    _json(feature_flags),
                    _json(connector_modes),
                    timestamp,
                    timestamp,
                    status,
                    _json(warning_rows),
                    _json(block_rows),
                    graph_hash,
                    profile_hash,
                    request_hash,
                    response_hash,
                    proof_checksum,
                    created_from,
                    run_record["package_mode"],
                    pit_status,
                    rights_status,
                    validation_status,
                    _json(persisted_response),
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO equity_preview_evidence_bundles(
                    evidence_bundle_id,
                    run_id,
                    target_entity_id,
                    profile_id,
                    evidence_bundle_json,
                    created_at,
                    checksum
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_bundle_id,
                    run_id,
                    target.get("entity_id"),
                    run_record["profile_id"],
                    _json(evidence_bundle),
                    timestamp,
                    _checksum(evidence_bundle),
                ),
            )
            self._save_report(
                connection,
                run_id=run_id,
                report_id=validation_report_id,
                report_type="validation_report",
                status=validation_status,
                payload=validation,
                created_at=timestamp,
            )
            self._save_report(
                connection,
                run_id=run_id,
                report_id=rights_report_id,
                report_type="source_rights_report",
                status=rights_status,
                payload=rights,
                created_at=timestamp,
            )
            self._save_report(
                connection,
                run_id=run_id,
                report_id=package_report_id,
                report_type="package_redaction_preview",
                status=_package_status(package_preview),
                payload=package_preview,
                created_at=timestamp,
            )

        generic_result = _generic_run_record_payload(
            run_record=run_record,
            response_payload=persisted_response,
        )
        get_project_store(self.path).save_run_record(result_payload=generic_result)

        return PersistedEquityPreviewRun(
            run_id=run_id,
            proof_checksum=proof_checksum,
            observation_ids=observation_ids,
            evidence_bundle_id=evidence_bundle_id,
            validation_report_id=validation_report_id,
            source_rights_report_id=rights_report_id,
            package_redaction_preview_id=package_report_id,
            history_url=f"/viza/equity/runtime-wedge/runs/{run_id}",
        )

    def list_runs(
        self,
        *,
        limit: int = 25,
        offset: int = 0,
        target_entity_id: str | None = None,
        cik: str | None = None,
        ticker_alias: str | None = None,
        profile_id: str | None = None,
        status: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> EquityPreviewRunList:
        clauses: list[str] = []
        params: list[Any] = []
        if target_entity_id:
            clauses.append("json_extract(target_json, '$.entity_id') = ?")
            params.append(target_entity_id)
        if cik:
            clauses.append("json_extract(target_json, '$.cik') = ?")
            params.append(cik.zfill(10) if cik.isdigit() else cik)
        if ticker_alias:
            clauses.append("UPPER(json_extract(target_json, '$.ticker_alias')) = ?")
            params.append(ticker_alias.upper())
        if profile_id:
            clauses.append("profile_id = ?")
            params.append(profile_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if created_after:
            clauses.append("created_at >= ?")
            params.append(created_after)
        if created_before:
            clauses.append("created_at <= ?")
            params.append(created_before)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) AS total FROM equity_preview_runs {where}",
                tuple(params),
            ).fetchone()["total"]
            rows = connection.execute(
                f"""
                SELECT *
                FROM equity_preview_runs
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
        return EquityPreviewRunList(
            runs=[_summary_from_row(row) for row in rows],
            total=int(total),
        )

    def require_detail(self, run_id: str) -> EquityPreviewRunDetail:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM equity_preview_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown equity preview run: {run_id}")
            evidence_row = connection.execute(
                """
                SELECT evidence_bundle_json
                FROM equity_preview_evidence_bundles
                WHERE run_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            report_rows = connection.execute(
                """
                SELECT report_type, report_json
                FROM equity_preview_report_records
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchall()
            observation_rows = connection.execute(
                """
                SELECT observation_id, normalized_json
                FROM equity_preview_run_observations
                WHERE run_id = ?
                ORDER BY observation_id
                """,
                (run_id,),
            ).fetchall()

        persisted_payload = _load_json(row["persisted_payload_json"])
        reports = {item["report_type"]: _load_json(item["report_json"]) for item in report_rows}
        observations: list[dict[str, Any]] = []
        observation_store = get_observation_store(self.path)
        for observation_row in observation_rows:
            normalized = _load_json(observation_row["normalized_json"])
            try:
                observation = observation_store.require_observation(observation_row["observation_id"])
                normalized["observation"] = observation.model_dump(mode="json", by_alias=True)
            except KeyError:
                normalized["missing_observation"] = True
            observations.append(normalized)

        run_record = _run_record_from_row(row)
        return EquityPreviewRunDetail(
            run_record=run_record,
            target=_load_json(row["target_json"]),
            evidence_bundle=_load_json(evidence_row["evidence_bundle_json"]) if evidence_row else {},
            observations=observations,
            output_preview=_read_dict(persisted_payload.get("output_preview")),
            validation_report=reports.get("validation_report", {}),
            source_rights_report=reports.get("source_rights_report", {}),
            package_redaction_preview=reports.get("package_redaction_preview", {}),
            audit={
                "graph_hash": row["graph_hash"],
                "profile_hash": row["profile_hash"],
                "request_hash": row["request_hash"],
                "response_hash": row["response_hash"],
                "proof_checksum": row["proof_checksum"],
                "parent_run_id": row["parent_run_id"],
                "created_from": row["created_from"],
            },
        )

    def replay_from_stored_observations(
        self,
        run_id: str,
        request: EquityPreviewReplayRequest,
    ) -> EquityPreviewReplayResult:
        detail = self.require_detail(run_id)
        original_payload = self._persisted_payload(run_id)
        replay_payload = json.loads(json.dumps(original_payload, sort_keys=True, default=str))
        replay_payload["persisted"] = False
        replay_payload["persistence_status"] = "replay_created"
        replay_payload["replay_mode"] = "replay_from_stored_observations"
        replay_payload["parent_run_id"] = run_id
        replay_payload["package_redaction_preview"]["package_mode"] = (
            request.package_mode or replay_payload["package_redaction_preview"].get("package_mode")
        )
        replay_payload.setdefault("audit", {})["fixture_mode"] = True
        replay_payload["audit"]["proof_checksum"] = _checksum(replay_payload)
        replay_payload["proof_checksum"] = replay_payload["audit"]["proof_checksum"]

        persisted = self.persist_preview_run(
            request_payload={
                **_read_dict(detail.run_record.get("input")),
                "package_mode": replay_payload["package_redaction_preview"]["package_mode"],
                "include_fmp": request.include_fmp,
                "include_fred": request.include_fred,
                "use_live_connectors": False,
                "persist_run": True,
            },
            response_payload=replay_payload,
            runtime_payload=_runtime_payload_from_detail(detail),
            created_from="replay_from_stored_observations",
            parent_run_id=run_id,
        )
        replay_payload["run_id"] = persisted.run_id
        replay_payload["persisted"] = True
        replay_payload["persistence_status"] = "persisted"
        replay_payload["history_url"] = persisted.history_url
        replay_payload["audit"]["run_id"] = persisted.run_id
        return EquityPreviewReplayResult(
            mode="replay_from_stored_observations",
            parent_run_id=run_id,
            run_id=persisted.run_id,
            preview=replay_payload,
            differences=[
                {
                    "field": "created_from",
                    "before": detail.run_record.get("created_from"),
                    "after": "replay_from_stored_observations",
                }
            ],
        )

    def _persisted_payload(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT persisted_payload_json FROM equity_preview_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown equity preview run: {run_id}")
        return _load_json(row["persisted_payload_json"])

    def _persist_observations(
        self,
        *,
        run_id: str,
        target: dict[str, Any],
        response_payload: dict[str, Any],
        runtime_payload: dict[str, Any],
    ) -> list[str]:
        inputs = _observation_inputs_from_preview(
            run_id=run_id,
            target=target,
            response_payload=response_payload,
            runtime_payload=runtime_payload,
        )
        observation_store = get_observation_store(self.path)
        saved = observation_store.ingest(ObservationIngestRequest(observations=inputs))
        with self._connect() as connection:
            for observation in saved:
                normalized = _normalized_observation_payload(run_id, observation)
                connection.execute(
                    """
                    INSERT OR REPLACE INTO equity_preview_run_observations(
                        run_id,
                        observation_id,
                        normalized_json
                    )
                    VALUES (?, ?, ?)
                    """,
                    (run_id, observation.observation_id, _json(normalized)),
                )
        return [observation.observation_id for observation in saved]

    def _save_report(
        self,
        connection: sqlite3.Connection,
        *,
        run_id: str,
        report_id: str,
        report_type: str,
        status: str,
        payload: dict[str, Any],
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO equity_preview_report_records(
                report_id,
                run_id,
                report_type,
                status,
                report_json,
                checksum,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                run_id,
                report_type,
                status,
                _json(payload),
                _checksum(payload),
                created_at,
            ),
        )

    def _report_id(self, run_id: str, report_type: str, payload: dict[str, Any]) -> str:
        return f"eq-report-{report_type}-{_checksum({'run_id': run_id, 'payload': payload})[:20].lower()}"

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(EQUITY_PREVIEW_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


EQUITY_PREVIEW_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS equity_preview_runs (
  run_id TEXT PRIMARY KEY,
  parent_run_id TEXT,
  module_id TEXT NOT NULL,
  module_version TEXT NOT NULL,
  run_type TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  target_json TEXT NOT NULL,
  input_json TEXT NOT NULL,
  feature_flags_json TEXT NOT NULL,
  connector_modes_json TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  status TEXT NOT NULL,
  warnings_json TEXT NOT NULL DEFAULT '[]',
  blocks_json TEXT NOT NULL DEFAULT '[]',
  graph_hash TEXT NOT NULL,
  profile_hash TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_hash TEXT NOT NULL,
  proof_checksum TEXT NOT NULL,
  created_from TEXT NOT NULL,
  package_mode TEXT NOT NULL,
  pit_status TEXT NOT NULL,
  rights_status TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  persisted_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_equity_preview_runs_created
  ON equity_preview_runs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_equity_preview_runs_target
  ON equity_preview_runs(profile_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS equity_preview_evidence_bundles (
  evidence_bundle_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  target_entity_id TEXT,
  profile_id TEXT NOT NULL,
  evidence_bundle_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  checksum TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_equity_preview_evidence_run
  ON equity_preview_evidence_bundles(run_id);

CREATE TABLE IF NOT EXISTS equity_preview_report_records (
  report_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  report_type TEXT NOT NULL,
  status TEXT NOT NULL,
  report_json TEXT NOT NULL,
  checksum TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_equity_preview_reports_run
  ON equity_preview_report_records(run_id, report_type);

CREATE TABLE IF NOT EXISTS equity_preview_run_observations (
  run_id TEXT NOT NULL,
  observation_id TEXT NOT NULL,
  normalized_json TEXT NOT NULL,
  PRIMARY KEY(run_id, observation_id)
);

CREATE INDEX IF NOT EXISTS idx_equity_preview_run_observations_run
  ON equity_preview_run_observations(run_id);
"""


def get_equity_preview_store(path: str | Path | None = None) -> EquityPreviewStore:
    return EquityPreviewStore(path)


def _observation_inputs_from_preview(
    *,
    run_id: str,
    target: dict[str, Any],
    response_payload: dict[str, Any],
    runtime_payload: dict[str, Any],
) -> list[ObservationInput]:
    entity_id = _read_string(target.get("entity_id")) or f"viza:eq:entity:unknown:{run_id}"
    inputs: list[ObservationInput] = []
    evidence = _read_dict(response_payload.get("evidence_summary"))
    if evidence.get("filing_refs"):
        filing = _read_dict(evidence["filing_refs"][0])
        timestamp = _parse_datetime(
            filing.get("accepted_at") or filing.get("available_at") or evidence.get("retrieved_at")
        )
        inputs.append(
            ObservationInput(
                entity_id=entity_id,
                asset_id=_read_optional_string(target.get("security_id")),
                attribute_key="sec_latest_periodic_filing",
                value={
                    "accession_number": filing.get("accession_number"),
                    "form_type": filing.get("form_type"),
                    "filing_date": filing.get("filing_date"),
                    "accepted_at": filing.get("accepted_at"),
                    "source_id": filing.get("source_id"),
                },
                unit="filing_metadata",
                observed_at=_parse_datetime(evidence.get("observed_at") or timestamp),
                available_at=_parse_datetime(evidence.get("available_at") or timestamp),
                retrieved_at=_parse_datetime(evidence.get("retrieved_at") or timestamp),
                source_id=_read_string(filing.get("source_id"), f"sec:{run_id}:filing"),
                connector_id="sec_filings",
                source_record=_json(
                    {
                        "run_id": run_id,
                        "source_ref": filing,
                        "PIT_safe": True,
                        "lookahead_risk": "low_if_accepted_at_available_else_filing_date_warning",
                    }
                ),
                data_version="sec_public_filing_metadata",
                model_version="viza.equity.preview.persistence.v1",
                confidence=0.98,
                rights_policy=_sec_rights_policy(),
            )
        )

    for attribute in response_payload.get("fundamental_attributes", []):
        if not isinstance(attribute, dict):
            continue
        source_ids = list(attribute.get("source_ids") or [])
        observed_at = _parse_datetime(attribute.get("observed_at"))
        available_at = _parse_datetime(attribute.get("available_at"))
        retrieved_at = _parse_datetime(attribute.get("retrieved_at"))
        rights_policy = _sec_rights_policy()
        rights_policy["PIT_safe"] = attribute.get("pit_status") == "pass"
        rights_policy["lookahead_risk"] = "low_if_available_at_present"
        inputs.append(
            ObservationInput(
                entity_id=entity_id,
                asset_id=_read_optional_string(target.get("security_id")),
                attribute_key=_read_string(attribute.get("key"), "unknown_sec_attribute"),
                value=attribute.get("value"),
                unit=_read_optional_string(attribute.get("unit")),
                observed_at=observed_at,
                available_at=available_at,
                retrieved_at=retrieved_at,
                source_id=source_ids[0] if source_ids else f"sec:{run_id}:{attribute.get('key')}",
                connector_id="xbrl_facts",
                source_record=_json(
                    {
                        "run_id": run_id,
                        "source_ids": source_ids,
                        "source_version": "sec_companyfacts_at_retrieval",
                        "PIT_safe": attribute.get("pit_status") == "pass",
                        "lookahead_risk": "low_if_available_at_present",
                    }
                ),
                data_version="sec_companyfacts_runtime_payload",
                model_version="viza.equity.runtime.sec_quality_value_wedge.v1",
                confidence=0.95,
                rights_policy=rights_policy,
            )
        )

    market_snapshot = _read_dict(runtime_payload.get("market_snapshot"))
    fmp_rights = _read_dict(market_snapshot.get("rights_policy"))
    for observation in market_snapshot.get("observations", []):
        if not isinstance(observation, dict):
            continue
        inputs.append(
            ObservationInput(
                entity_id=entity_id,
                asset_id=_read_optional_string(target.get("security_id")),
                attribute_key=_read_string(observation.get("field"), "fmp_observation"),
                value=observation.get("value"),
                unit=_read_optional_string(observation.get("unit")),
                observed_at=_parse_datetime(observation.get("observed_at") or market_snapshot.get("retrieved_at")),
                available_at=_parse_datetime(observation.get("available_at") or market_snapshot.get("retrieved_at")),
                retrieved_at=_parse_datetime(market_snapshot.get("retrieved_at")),
                source_id=_read_string(observation.get("source_id"), f"fmp:{run_id}:{observation.get('field')}"),
                connector_id="licensed_market_data_connector",
                source_record=_json(
                    {
                        "run_id": run_id,
                        "symbol": market_snapshot.get("symbol"),
                        "cik": market_snapshot.get("cik"),
                        "PIT_safe": False,
                        "lookahead_risk": "provider_timestamp_or_runtime_retrieval_only",
                    }
                ),
                data_version="fmp_runtime_market_snapshot",
                model_version="viza.equity.runtime.sec_quality_value_wedge.v1",
                confidence=0.85,
                rights_policy={
                    **_fmp_rights_policy(fmp_rights),
                    "PIT_safe": False,
                    "lookahead_risk": "provider_timestamp_or_runtime_retrieval_only",
                },
            )
        )

    macro_context = _read_dict(runtime_payload.get("macro_context"))
    fred_rights = _read_dict(macro_context.get("rights_policy"))
    fred_pit = _read_dict(macro_context.get("PIT_policy"))
    for observation in macro_context.get("observations", []):
        if not isinstance(observation, dict):
            continue
        inputs.append(
            ObservationInput(
                entity_id=entity_id,
                asset_id=None,
                attribute_key=f"fred_{_read_string(observation.get('series_id'), 'macro').lower()}",
                value=observation.get("value"),
                unit=_read_optional_string(observation.get("unit")) or "macro_value",
                observed_at=_parse_datetime(observation.get("observed_at") or observation.get("date")),
                available_at=_parse_datetime(observation.get("available_at") or macro_context.get("retrieved_at")),
                retrieved_at=_parse_datetime(macro_context.get("retrieved_at")),
                source_id=_read_string(observation.get("source_id"), f"fred:{observation.get('series_id', 'macro')}"),
                connector_id="fred_macro",
                source_record=_json(
                    {
                        "run_id": run_id,
                        "series_id": observation.get("series_id"),
                        "PIT_safe": bool(fred_pit.get("PIT_safe")),
                        "lookahead_risk": fred_pit.get("lookahead_risk")
                        or "macro_revision_or_latest_only",
                    }
                ),
                data_version="fred_latest_runtime_payload",
                model_version="viza.equity.runtime.sec_quality_value_wedge.v1",
                confidence=0.9,
                rights_policy={
                    **_fred_rights_policy(fred_rights),
                    "PIT_safe": bool(fred_pit.get("PIT_safe")),
                    "lookahead_risk": fred_pit.get("lookahead_risk")
                    or "macro_revision_or_latest_only",
                },
            )
        )
    return inputs


def _normalized_observation_payload(run_id: str, observation: VizaObservation) -> dict[str, Any]:
    rights = dict(observation.rights_policy)
    return {
        "observation_id": observation.observation_id,
        "run_id": run_id,
        "entity_id": observation.entity_id,
        "attribute_key": observation.attribute_key,
        "value": observation.value,
        "unit": observation.unit,
        "period_start": None,
        "period_end": None,
        "observed_at": observation.observed_at.isoformat(),
        "available_at": observation.available_at.isoformat(),
        "retrieved_at": observation.retrieved_at.isoformat(),
        "source_id": observation.source_id,
        "source_ref": observation.source_record,
        "source_version": rights.get("source_version_policy")
        or rights.get("source_version")
        or observation.data_version,
        "data_version": observation.data_version,
        "model_version": observation.model_version,
        "connector_role": observation.connector_id,
        "PIT_safe": bool(rights.get("PIT_safe", False)),
        "lookahead_risk": rights.get("lookahead_risk", "unknown"),
        "rights_policy": rights,
    }


def _evidence_bundle_payload(
    *,
    run_id: str,
    target: dict[str, Any],
    response_payload: dict[str, Any],
    observation_ids: list[str],
    created_at: str,
) -> dict[str, Any]:
    evidence_summary = _read_dict(response_payload.get("evidence_summary"))
    fmp_observations = [
        item for item in observation_ids if "fmp" in item or "latest_price" in item
    ]
    fred_observations = [item for item in observation_ids if "fred" in item]
    return {
        "evidence_bundle_id": "",
        "run_id": run_id,
        "target_entity_id": target.get("entity_id"),
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "source_refs": list(evidence_summary.get("sources") or []),
        "filing_refs": list(evidence_summary.get("filing_refs") or []),
        "observation_ids": observation_ids,
        "fundamental_attribute_keys": [
            item.get("key")
            for item in response_payload.get("fundamental_attributes", [])
            if isinstance(item, dict)
        ],
        "optional_market_context_refs": {"fmp": fmp_observations, "fred": fred_observations},
        "pit_summary_ref": "output_preview.PIT_status",
        "rights_summary_ref": "source_rights_report",
        "validation_report_ref": "validation_report",
        "package_redaction_preview_ref": "package_redaction_preview",
        "created_at": created_at,
    }


def _generic_run_record_payload(
    *,
    run_record: dict[str, Any],
    response_payload: dict[str, Any],
) -> dict[str, Any]:
    result_payload = {
        "run_id": run_record["run_id"],
        "methodology_id": EQUITY_PREVIEW_METHOD_ID,
        "graph_hash": run_record["graph_hash"],
        "status": run_record["status"],
        "result_checksum": run_record["response_hash"],
        "manifest": {
            "module_id": EQUITY_MODULE_ID,
            "module_version": EQUITY_MODULE_VERSION,
            "methodology_id": EQUITY_PREVIEW_METHOD_ID,
            "graph_hash": run_record["graph_hash"],
            "result_checksum": run_record["response_hash"],
            "evidence_checksum": _checksum(run_record.get("observation_ids", [])),
            "data_versions": ["sec_companyfacts_runtime_payload"],
            "model_versions": ["viza.equity.runtime.sec_quality_value_wedge.v1"],
            "connector_states": run_record["connector_modes"],
            "source_rights": response_payload.get("source_rights_report", {}),
        },
        "equity_preview_run": run_record,
        "equity_preview_response": response_payload,
    }
    return result_payload


def _runtime_payload_from_detail(detail: EquityPreviewRunDetail) -> dict[str, Any]:
    fundamentals = {
        "source": "persisted_observation_store",
        "connector_role": "xbrl_facts",
        "status": "available" if detail.observations else "unavailable",
        "attributes": [
            {
                "key": item.get("attribute_key"),
                "value": item.get("value"),
                "unit": item.get("unit"),
                "source_ids": [item.get("source_id")],
                "observed_at": item.get("observed_at"),
                "available_at": item.get("available_at"),
                "retrieved_at": item.get("retrieved_at"),
                "rights_policy": item.get("rights_policy", {}),
                "PIT_policy": {
                    "PIT_safe": item.get("PIT_safe", False),
                    "lookahead_risk": item.get("lookahead_risk", "unknown"),
                },
            }
            for item in detail.observations
            if item.get("connector_role") in {"xbrl_facts", "sec_filings"}
        ],
    }
    return {
        "identity": detail.target,
        "evidence_bundle": detail.evidence_bundle,
        "fundamentals": fundamentals,
        "market_snapshot": {},
        "macro_context": {},
        "outputs": {
            "validation_report": detail.validation_report,
            "source_rights_report": detail.source_rights_report,
            "package_redaction_preview": detail.package_redaction_preview,
        },
    }


def _preview_input_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    target = _read_dict(request_payload.get("target"))
    return {
        "cik": target.get("cik"),
        "ticker_alias": target.get("ticker_alias"),
        "package_mode": request_payload.get("package_mode"),
        "include_fmp": bool(request_payload.get("include_fmp")),
        "include_fred": bool(request_payload.get("include_fred")),
        "use_live_connectors": bool(request_payload.get("use_live_connectors")),
        "cutoff_timestamp": request_payload.get("cutoff_timestamp"),
        "mock_fixture_id": request_payload.get("mock_fixture_id"),
        "persist_run": bool(request_payload.get("persist_run")),
    }


def _connector_modes(response_payload: dict[str, Any], request_payload: dict[str, Any]) -> dict[str, str]:
    context = _read_dict(response_payload.get("optional_market_context"))
    fmp = _read_dict(context.get("fmp"))
    fred = _read_dict(context.get("fred"))
    live = bool(request_payload.get("use_live_connectors"))
    return {
        "sec": "live" if live else "mock",
        "fmp": _connector_mode("fmp", fmp, live),
        "fred": _connector_mode("fred", fred, live),
    }


def _connector_mode(source: str, context: dict[str, Any], live: bool) -> str:
    status = context.get("status")
    if status == "disabled":
        return "disabled"
    if status == "missing_key":
        return "missing_key"
    if source == "fmp":
        if status == "dev_only":
            return "live_dev_only" if live else "mock"
        if status == "available":
            return "live_license_confirmed" if live else "mock"
    if source == "fred":
        if status == "latest_only":
            return "live_latest_only" if live else "mock"
        if status == "vintage_safe":
            return "live_vintage_safe" if live else "mock"
    return str(status or "disabled")


def _run_record_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "module_id": row["module_id"],
        "module_version": row["module_version"],
        "run_type": row["run_type"],
        "profile_id": row["profile_id"],
        "target": _load_json(row["target_json"]),
        "input": _load_json(row["input_json"]),
        "feature_flags": _load_json(row["feature_flags_json"]),
        "connector_modes": _load_json(row["connector_modes_json"]),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "status": row["status"],
        "warnings": _load_json(row["warnings_json"]),
        "blocks": _load_json(row["blocks_json"]),
        "graph_hash": row["graph_hash"],
        "profile_hash": row["profile_hash"],
        "request_hash": row["request_hash"],
        "response_hash": row["response_hash"],
        "proof_checksum": row["proof_checksum"],
        "created_from": row["created_from"],
        "parent_run_id": row["parent_run_id"],
        "package_mode": row["package_mode"],
        "pit_status": row["pit_status"],
        "rights_status": row["rights_status"],
        "validation_status": row["validation_status"],
        "created_at": row["created_at"],
    }


def _summary_from_row(row: sqlite3.Row) -> EquityPreviewRunSummary:
    target = _load_json(row["target_json"])
    return EquityPreviewRunSummary(
        run_id=row["run_id"],
        created_at=row["created_at"],
        target_display_name=target.get("display_name") or target.get("entity_id") or "",
        cik=target.get("cik"),
        ticker_alias=target.get("ticker_alias"),
        profile_id=row["profile_id"],
        status=_status(row["status"]),
        package_mode=row["package_mode"],
        pit_status=_status(row["pit_status"]),
        rights_status=_status(row["rights_status"]),
        validation_status=_status(row["validation_status"]),
        proof_checksum=row["proof_checksum"],
    )


def _pit_status_from_response(payload: dict[str, Any]) -> str:
    validation = _read_dict(payload.get("validation_report"))
    if any(rule.get("status") == "block" for rule in validation.get("rules", [])):
        return "block"
    if any(rule.get("status") == "warn" for rule in validation.get("rules", [])):
        return "warn"
    return "pass"


def _package_status(package_preview: dict[str, Any]) -> str:
    if package_preview.get("blocked"):
        return "block"
    if package_preview.get("redacted") or package_preview.get("entitlement_locked"):
        return "warn"
    return "pass"


def _sec_rights_policy() -> dict[str, Any]:
    return {
        "license_policy": "public_official",
        "display_policy": "allowed_with_attribution",
        "export_policy": "metadata_and_derived_allowed",
        "derived_value_policy": "allowed",
        "redistribution_policy": "no_bulk_raw_filing_republication",
        "marketplace_policy": "metadata_and_derived_allowed_with_attribution",
        "redaction_required": False,
        "source_version_policy": "sec_public_payload_at_retrieval",
    }


def _fmp_rights_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "license_policy": policy.get("license_policy", "dev_only_unconfirmed"),
        "display_policy": policy.get("display_policy", "dev_only"),
        "export_policy": policy.get("export_policy", "blocked"),
        "derived_value_policy": policy.get("derived_value_policy", "allowed_internal_only"),
        "redistribution_policy": policy.get("redistribution_policy", "restricted"),
        "marketplace_policy": policy.get("marketplace_policy", "redacted"),
        "redaction_required": policy.get("redaction_required", True),
        "source_version_policy": "fmp_runtime_payload_at_retrieval",
    }


def _fred_rights_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "license_policy": policy.get("license_policy", "public_official"),
        "display_policy": policy.get("display_policy", "allowed_with_attribution"),
        "export_policy": policy.get("export_policy", "metadata_and_derived_allowed"),
        "derived_value_policy": policy.get("derived_value_policy", "allowed"),
        "redistribution_policy": policy.get("redistribution_policy", "metadata_with_attribution"),
        "marketplace_policy": policy.get("marketplace_policy", "metadata_and_derived_allowed_with_attribution"),
        "redaction_required": policy.get("redaction_required", False),
        "source_version_policy": "fred_runtime_payload_at_retrieval",
    }


def _status(value: Any) -> Literal["pass", "warn", "block", "failed"]:
    if value in {"pass", "warn", "block", "failed"}:
        return value
    return "block"


def _read_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_string(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) and value else default


def _read_optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _load_json(value: str | bytes | None) -> Any:
    if not value:
        return {}
    return json.loads(value)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _checksum(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest().upper()


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
