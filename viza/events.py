from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.config_paths import resolve_config_path, source_root
from viza.graph_schema import MethodologyGraph
from viza.project_store import project_store_path


REPO_ROOT = source_root()
EVENT_REGISTRY_PATH = REPO_ROOT / "config" / "viza_event_registry.json"


class EventTypeDefinition(BaseModel):
    """Catalog entry for an event type.

    Phase 30 adds two nullable fields: ``fibo_iri`` (canonical FIBO-CAE
    classification where one exists, e.g. ``confirmed_mna`` →
    ``fibo-cae-mer:MergerEvent``) and ``family_concept_iri`` (the SKOS
    concept IRI for the family taxonomy, set when present). Both are
    optional so legacy event-registry JSON loads without modification.
    """

    model_config = ConfigDict(extra="forbid")

    event_type: str
    display_name: str
    family: str
    fibo_iri: str | None = None
    family_concept_iri: str | None = None


class EventRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str = Field(default="viza.event_registry.v1", alias="schema")
    registry_version: str = "0.1.0"
    event_types: list[EventTypeDefinition] = Field(default_factory=list)

    def has_event_type(self, event_type: str) -> bool:
        return any(definition.event_type == event_type for definition in self.event_types)


class VizaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.event.v1", alias="schema")
    event_id: str
    event_type: str
    affected_entity_ids: list[str]
    affected_asset_ids: list[str] = Field(default_factory=list)
    related_entity_ids: list[str] = Field(default_factory=list)
    observed_at: datetime
    available_at: datetime
    source: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    source_credibility: float | None = None
    materiality: float | None = None
    novelty: float | None = None
    direction_hint: str | None = None
    time_horizon_hint: str | None = None
    risk_factors: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    point_in_time_safe: bool = True


class ManualEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    affected_entity_ids: list[str] = Field(min_length=1)
    affected_asset_ids: list[str] = Field(default_factory=list)
    related_entity_ids: list[str] = Field(default_factory=list)
    observed_at: datetime
    available_at: datetime
    source: dict[str, Any] = Field(default_factory=lambda: {"kind": "manual"})
    confidence: float = Field(default=0.75, ge=0, le=1)
    source_credibility: float | None = None
    materiality: float | None = None
    novelty: float | None = None
    direction_hint: str | None = None
    time_horizon_hint: str | None = None
    risk_factors: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    point_in_time_safe: bool = True


class EventExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: MethodologyGraph | None = None
    run_result: dict[str, Any] | None = None
    event_types: list[str] = Field(default_factory=list)
    min_confidence: float = Field(default=0.4, ge=0, le=1)
    min_source_credibility: float = Field(default=0.0, ge=0, le=1)
    cutoff: datetime | None = None
    persist: bool = True


class EventQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affected_entity_id: str | None = None
    affected_asset_id: str | None = None
    event_types: list[str] = Field(default_factory=list)
    cutoff: datetime | None = None
    min_confidence: float | None = None
    limit: int = 50


class EventQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[VizaEvent] = Field(default_factory=list)


class EventStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def upsert_event(self, event: VizaEvent) -> VizaEvent:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO events(
                    event_id,
                    event_type,
                    affected_entity_ids_json,
                    affected_asset_ids_json,
                    related_entity_ids_json,
                    observed_at,
                    available_at,
                    source_json,
                    confidence,
                    source_credibility,
                    materiality,
                    novelty,
                    direction_hint,
                    time_horizon_hint,
                    risk_factors_json,
                    evidence_refs_json,
                    rights_policy_json,
                    point_in_time_safe
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    event_type = excluded.event_type,
                    affected_entity_ids_json = excluded.affected_entity_ids_json,
                    affected_asset_ids_json = excluded.affected_asset_ids_json,
                    related_entity_ids_json = excluded.related_entity_ids_json,
                    observed_at = excluded.observed_at,
                    available_at = excluded.available_at,
                    source_json = excluded.source_json,
                    confidence = excluded.confidence,
                    source_credibility = excluded.source_credibility,
                    materiality = excluded.materiality,
                    novelty = excluded.novelty,
                    direction_hint = excluded.direction_hint,
                    time_horizon_hint = excluded.time_horizon_hint,
                    risk_factors_json = excluded.risk_factors_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    rights_policy_json = excluded.rights_policy_json,
                    point_in_time_safe = excluded.point_in_time_safe
                """,
                _event_row_values(event),
            )
        return self.require_event(event.event_id)

    def query_events(self, request: EventQueryRequest) -> list[VizaEvent]:
        clauses: list[str] = []
        params: list[Any] = []
        if request.event_types:
            placeholders = ", ".join("?" for _ in request.event_types)
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(request.event_types)
        if request.cutoff:
            clauses.append("available_at <= ?")
            params.append(request.cutoff.isoformat())
        if request.min_confidence is not None:
            clauses.append("confidence >= ?")
            params.append(request.min_confidence)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(request.limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM events
                {where}
                ORDER BY available_at DESC, confidence DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        events = [_event_from_row(row) for row in rows]
        if request.affected_entity_id:
            events = [
                event for event in events if request.affected_entity_id in event.affected_entity_ids
            ]
        if request.affected_asset_id:
            events = [
                event for event in events if request.affected_asset_id in event.affected_asset_ids
            ]
        return events

    def get_event(self, event_id: str) -> VizaEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return _event_from_row(row) if row is not None else None

    def require_event(self, event_id: str) -> VizaEvent:
        event = self.get_event(event_id)
        if event is None:
            raise KeyError(f"unknown VIZA event: {event_id}")
        return event

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(EVENT_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


EVENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  affected_entity_ids_json TEXT NOT NULL,
  affected_asset_ids_json TEXT NOT NULL DEFAULT '[]',
  related_entity_ids_json TEXT NOT NULL DEFAULT '[]',
  observed_at TEXT NOT NULL,
  available_at TEXT NOT NULL,
  source_json TEXT NOT NULL,
  confidence REAL NOT NULL,
  source_credibility REAL,
  materiality REAL,
  novelty REAL,
  direction_hint TEXT,
  time_horizon_hint TEXT,
  risk_factors_json TEXT NOT NULL DEFAULT '[]',
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  rights_policy_json TEXT NOT NULL DEFAULT '{}',
  point_in_time_safe INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_type_available
  ON events(event_type, available_at);
"""


def load_event_registry(path: str | Path | None = None) -> EventRegistry:
    active_path = Path(path) if path is not None else resolve_config_path("viza_event_registry.json")
    with active_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return EventRegistry.model_validate(payload)


def get_event_store(path: str | Path | None = None) -> EventStore:
    return EventStore(path)


def event_from_manual_request(request: ManualEventRequest) -> VizaEvent:
    payload = request.model_dump(mode="json")
    event_id = _event_id(payload)
    return VizaEvent(event_id=event_id, **payload)


def extract_events_from_run_result(
    run_result: Any,
    *,
    event_types: list[str] | None = None,
    min_confidence: float = 0.4,
    min_source_credibility: float = 0.0,
    cutoff: datetime | None = None,
) -> list[VizaEvent]:
    payload = _model_or_mapping(run_result)
    rows = payload.get("rows") if isinstance(payload, dict) else []
    evidence = payload.get("evidence") if isinstance(payload, dict) else {}
    requested_types = set(event_types or [])
    events: list[VizaEvent] = []
    for row in rows if isinstance(rows, list) else []:
        row_payload = _model_or_mapping(row)
        ticker = str(row_payload.get("ticker") or "")
        attributes = row_payload.get("attributes") if isinstance(row_payload, dict) else {}
        if not isinstance(attributes, dict):
            attributes = {}
        materiality = _read_float(attributes.get("event_materiality"))
        novelty = _read_float(attributes.get("event_novelty"))
        event_count = _read_float(attributes.get("event_count"))
        if materiality is None and event_count is None:
            continue
        event_type = "earnings_surprise" if (materiality or 0) >= 0.55 else "news_sentiment_shift"
        if requested_types and event_type not in requested_types:
            continue
        source_credibility = max(0.5, min(1.0, 0.55 + (novelty or 0) * 0.35))
        confidence = round(max(materiality or 0.0, min_confidence), 6)
        if confidence < min_confidence or source_credibility < min_source_credibility:
            continue
        evidence_ref = f"attr:{ticker}:event_materiality"
        evidence_record = evidence.get(evidence_ref, {}) if isinstance(evidence, dict) else {}
        observed_at = _read_datetime(
            evidence_record.get("observed_at")
            or evidence_record.get("source_timestamp")
            or evidence_record.get("timestamp_available")
        )
        available_at = _read_datetime(
            evidence_record.get("available_at") or evidence_record.get("timestamp_available")
        )
        if cutoff and available_at > cutoff:
            continue
        entity_id = row_payload.get("entity_id")
        asset_id = row_payload.get("asset_id")
        if not isinstance(entity_id, str) or not entity_id:
            continue
        event_payload = {
            "event_type": event_type,
            "affected_entity_ids": [entity_id],
            "affected_asset_ids": [asset_id] if isinstance(asset_id, str) and asset_id else [],
            "related_entity_ids": [],
            "observed_at": observed_at.isoformat(),
            "available_at": available_at.isoformat(),
            "source": {
                "kind": "deterministic_attributes",
                "ticker": ticker,
                "attribute_keys": ["event_materiality", "event_novelty", "event_count"],
            },
            "confidence": confidence,
            "source_credibility": round(source_credibility, 6),
            "materiality": materiality,
            "novelty": novelty,
            "direction_hint": _direction_from_evidence(evidence, ticker),
            "time_horizon_hint": "30d",
            "risk_factors": ["deterministic_attribute_extraction"],
            "evidence_refs": [evidence_ref],
            "rights_policy": _rights_from_evidence(evidence_record),
            "point_in_time_safe": cutoff is None or available_at <= cutoff,
        }
        events.append(VizaEvent(event_id=_event_id(event_payload), **event_payload))
    return events


def event_for_export(event: VizaEvent) -> dict[str, Any]:
    payload = event.model_dump(mode="json", by_alias=True)
    if event.rights_policy.get("export_allowed") is False:
        payload["source"] = {"redacted": True}
        payload["evidence_refs"] = []
        payload["redaction_reason"] = "event_source_rights_restricted"
    return payload


def _event_row_values(event: VizaEvent) -> tuple[Any, ...]:
    return (
        event.event_id,
        event.event_type,
        json.dumps(event.affected_entity_ids, sort_keys=True),
        json.dumps(event.affected_asset_ids, sort_keys=True),
        json.dumps(event.related_entity_ids, sort_keys=True),
        event.observed_at.isoformat(),
        event.available_at.isoformat(),
        json.dumps(event.source, sort_keys=True),
        event.confidence,
        event.source_credibility,
        event.materiality,
        event.novelty,
        event.direction_hint,
        event.time_horizon_hint,
        json.dumps(event.risk_factors, sort_keys=True),
        json.dumps(event.evidence_refs, sort_keys=True),
        json.dumps(event.rights_policy, sort_keys=True),
        1 if event.point_in_time_safe else 0,
    )


def _event_from_row(row: sqlite3.Row) -> VizaEvent:
    return VizaEvent(
        event_id=row["event_id"],
        event_type=row["event_type"],
        affected_entity_ids=json.loads(row["affected_entity_ids_json"]),
        affected_asset_ids=json.loads(row["affected_asset_ids_json"]),
        related_entity_ids=json.loads(row["related_entity_ids_json"]),
        observed_at=datetime.fromisoformat(row["observed_at"]),
        available_at=datetime.fromisoformat(row["available_at"]),
        source=json.loads(row["source_json"]),
        confidence=row["confidence"],
        source_credibility=row["source_credibility"],
        materiality=row["materiality"],
        novelty=row["novelty"],
        direction_hint=row["direction_hint"],
        time_horizon_hint=row["time_horizon_hint"],
        risk_factors=json.loads(row["risk_factors_json"]),
        evidence_refs=json.loads(row["evidence_refs_json"]),
        rights_policy=json.loads(row["rights_policy_json"]),
        point_in_time_safe=bool(row["point_in_time_safe"]),
    )


def _event_id(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"event-{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:24]}"


def _model_or_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value if isinstance(value, dict) else {}


def _read_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _read_datetime(value: Any) -> datetime:
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)
    return datetime.now(timezone.utc)


def _direction_from_evidence(evidence: Any, ticker: str) -> str | None:
    if not isinstance(evidence, dict):
        return None
    record = evidence.get(f"attr:{ticker}:event_direction")
    if isinstance(record, dict) and isinstance(record.get("value"), str):
        return record["value"]
    return None


def _rights_from_evidence(evidence_record: Any) -> dict[str, Any]:
    if isinstance(evidence_record, dict):
        entitlement = evidence_record.get("entitlement")
        if isinstance(entitlement, dict):
            return entitlement
    return {"export_allowed": True, "raw_snapshot_allowed": False}
