from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.config_paths import resolve_config_path, source_root
from viza.event_patterns import EventPattern
from viza.events import VizaEvent, extract_events_from_run_result
from viza.graph_schema import MethodologyGraph
from viza.project_store import project_store_path


REPO_ROOT = source_root()
INSIGHT_REGISTRY_PATH = REPO_ROOT / "config" / "viza_insight_registry.json"


class InsightTypeDefinition(BaseModel):
    """Catalog entry for an insight type.

    Phase 32 (`docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`
    §3 Phase 32) adds the optional `event_pattern` field so a composite
    insight (e.g. ``acquisition_rumor_with_technical_reversal_context``)
    can declare the event sequence it requires as data instead of an
    imperative branch in ``viza/insights.py``. The existing imperative
    matcher remains as a fallback for legacy registry entries that have no
    ``event_pattern`` declared; new entries should prefer the declarative
    pattern form.
    """

    model_config = ConfigDict(extra="forbid")

    insight_type_key: str
    display_name: str
    description: str
    family: str
    compatible_strategy_profiles: list[str] = Field(default_factory=list)
    required_event_types: list[str] = Field(default_factory=list)
    required_attributes: list[str] = Field(default_factory=list)
    optional_confirmations: list[str] = Field(default_factory=list)
    direction_logic: str
    confidence_logic: str
    horizon_defaults: dict[str, str] = Field(default_factory=dict)
    risk_factors: list[str] = Field(default_factory=list)
    invalidation_templates: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    point_in_time_policy: str = "available_at_cutoff"
    event_pattern: EventPattern | None = None


class InsightRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.insight_registry.v1", alias="schema")
    registry_version: str = "0.1.0"
    insight_types: list[InsightTypeDefinition] = Field(default_factory=list)

    def get(self, insight_type_key: str) -> InsightTypeDefinition | None:
        for definition in self.insight_types:
            if definition.insight_type_key == insight_type_key:
                return definition
        return None


class VizaInsight(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.insight.v1", alias="schema")
    insight_id: str
    entity_id: str
    asset_id: str | None = None
    related_entity_ids: list[str] = Field(default_factory=list)
    related_asset_ids: list[str] = Field(default_factory=list)
    insight_type: str
    direction: str
    magnitude: dict[str, Any] | None = None
    confidence: float = Field(ge=0, le=1)
    time_horizon: dict[str, str]
    evidence_refs: list[str] = Field(default_factory=list)
    source_policy: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime
    available_at: datetime
    generated_at: datetime
    strategy_compatibility: list[dict[str, Any]] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    action_layer: dict[str, Any] = Field(default_factory=dict)
    derivation_trace: dict[str, Any] = Field(default_factory=dict)


class InsightExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: MethodologyGraph | None = None
    run_result: dict[str, Any] | None = None
    events: list[VizaEvent] = Field(default_factory=list)
    enabled_insight_types: list[str] = Field(default_factory=list)
    min_confidence: float = Field(default=0.45, ge=0, le=1)
    require_evidence_refs: bool = True
    require_point_in_time_safe: bool = True
    cutoff: datetime | None = None
    persist: bool = True


class InsightQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str | None = None
    asset_id: str | None = None
    insight_types: list[str] = Field(default_factory=list)
    cutoff: datetime | None = None
    min_confidence: float | None = None
    limit: int = 50


class InsightQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insights: list[VizaInsight] = Field(default_factory=list)


class InsightStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def upsert_insight(self, insight: VizaInsight) -> VizaInsight:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO insights(
                    insight_id,
                    entity_id,
                    asset_id,
                    related_entity_ids_json,
                    related_asset_ids_json,
                    insight_type,
                    direction,
                    magnitude_json,
                    confidence,
                    time_horizon_json,
                    evidence_refs_json,
                    source_policy_json,
                    observed_at,
                    available_at,
                    generated_at,
                    strategy_compatibility_json,
                    risk_factors_json,
                    invalidation_conditions_json,
                    action_layer_json,
                    derivation_trace_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(insight_id) DO UPDATE SET
                    entity_id = excluded.entity_id,
                    asset_id = excluded.asset_id,
                    related_entity_ids_json = excluded.related_entity_ids_json,
                    related_asset_ids_json = excluded.related_asset_ids_json,
                    insight_type = excluded.insight_type,
                    direction = excluded.direction,
                    magnitude_json = excluded.magnitude_json,
                    confidence = excluded.confidence,
                    time_horizon_json = excluded.time_horizon_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    source_policy_json = excluded.source_policy_json,
                    observed_at = excluded.observed_at,
                    available_at = excluded.available_at,
                    generated_at = excluded.generated_at,
                    strategy_compatibility_json = excluded.strategy_compatibility_json,
                    risk_factors_json = excluded.risk_factors_json,
                    invalidation_conditions_json = excluded.invalidation_conditions_json,
                    action_layer_json = excluded.action_layer_json,
                    derivation_trace_json = excluded.derivation_trace_json
                """,
                _insight_row_values(insight),
            )
        return self.require_insight(insight.insight_id)

    def query_insights(self, request: InsightQueryRequest) -> list[VizaInsight]:
        clauses: list[str] = []
        params: list[Any] = []
        if request.entity_id:
            clauses.append("entity_id = ?")
            params.append(request.entity_id)
        if request.asset_id:
            clauses.append("asset_id = ?")
            params.append(request.asset_id)
        if request.insight_types:
            placeholders = ", ".join("?" for _ in request.insight_types)
            clauses.append(f"insight_type IN ({placeholders})")
            params.extend(request.insight_types)
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
                FROM insights
                {where}
                ORDER BY available_at DESC, confidence DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_insight_from_row(row) for row in rows]

    def get_insight(self, insight_id: str) -> VizaInsight | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM insights WHERE insight_id = ?",
                (insight_id,),
            ).fetchone()
        return _insight_from_row(row) if row is not None else None

    def require_insight(self, insight_id: str) -> VizaInsight:
        insight = self.get_insight(insight_id)
        if insight is None:
            raise KeyError(f"unknown VIZA insight: {insight_id}")
        return insight

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(INSIGHT_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


INSIGHT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS insights (
  insight_id TEXT PRIMARY KEY,
  entity_id TEXT NOT NULL,
  asset_id TEXT,
  related_entity_ids_json TEXT NOT NULL DEFAULT '[]',
  related_asset_ids_json TEXT NOT NULL DEFAULT '[]',
  insight_type TEXT NOT NULL,
  direction TEXT NOT NULL,
  magnitude_json TEXT,
  confidence REAL NOT NULL,
  time_horizon_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  source_policy_json TEXT NOT NULL DEFAULT '{}',
  observed_at TEXT NOT NULL,
  available_at TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  strategy_compatibility_json TEXT NOT NULL DEFAULT '[]',
  risk_factors_json TEXT NOT NULL DEFAULT '[]',
  invalidation_conditions_json TEXT NOT NULL DEFAULT '[]',
  action_layer_json TEXT NOT NULL DEFAULT '{}',
  derivation_trace_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_insights_entity_available
  ON insights(entity_id, insight_type, available_at);
"""


def load_insight_registry(path: str | Path | None = None) -> InsightRegistry:
    active_path = Path(path) if path is not None else resolve_config_path("viza_insight_registry.json")
    with active_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return InsightRegistry.model_validate(payload)


def get_insight_store(path: str | Path | None = None) -> InsightStore:
    return InsightStore(path)


def extract_insights_from_run_result(
    run_result: Any,
    *,
    events: list[VizaEvent] | None = None,
    enabled_insight_types: list[str] | None = None,
    min_confidence: float = 0.45,
    require_evidence_refs: bool = True,
    require_point_in_time_safe: bool = True,
    cutoff: datetime | None = None,
    registry: InsightRegistry | None = None,
) -> list[VizaInsight]:
    active_registry = registry or load_insight_registry()
    payload = _model_or_mapping(run_result)
    evidence = payload.get("evidence") if isinstance(payload, dict) else {}
    generated_at = datetime.now(timezone.utc)
    candidate_events = events if events is not None else extract_events_from_run_result(
        run_result,
        min_confidence=0.0,
        cutoff=cutoff,
    )
    enabled = set(enabled_insight_types or [])
    insights: list[VizaInsight] = []
    for event in candidate_events:
        if require_point_in_time_safe and not event.point_in_time_safe:
            continue
        if cutoff and event.available_at > cutoff:
            continue
        if require_evidence_refs and not event.evidence_refs:
            continue
        definition = _definition_for_event(event, evidence, active_registry, enabled)
        if definition is None:
            continue
        confidence = _insight_confidence(event, evidence, definition)
        if confidence < min_confidence:
            continue
        insight = _build_insight(
            event=event,
            definition=definition,
            evidence=evidence,
            confidence=confidence,
            generated_at=generated_at,
        )
        insights.append(insight)
    return insights


def insight_for_export(insight: VizaInsight) -> dict[str, Any]:
    payload = insight.model_dump(mode="json", by_alias=True)
    payload["source_policy"] = _sanitize_export_policy(payload.get("source_policy"))
    if insight.source_policy.get("export_allowed") is False:
        payload["magnitude"] = None
        payload["evidence_refs"] = []
        payload["redaction_reason"] = "insight_source_rights_restricted"
    return payload


def _definition_for_event(
    event: VizaEvent,
    evidence: Any,
    registry: InsightRegistry,
    enabled: set[str],
) -> InsightTypeDefinition | None:
    rsi = _attribute_value(evidence, event, "rsi_14d")
    momentum = _attribute_value(evidence, event, "momentum")
    candidates: list[str] = []
    if event.event_type == "acquisition_rumor":
        candidates.append("acquisition_rumor")
        if isinstance(rsi, (int, float)) and rsi <= 35:
            candidates.insert(0, "acquisition_rumor_with_technical_reversal_context")
    if event.event_type == "earnings_surprise":
        if isinstance(momentum, (int, float)):
            candidates.append("earnings_surprise_momentum_confirmation")
    for key in candidates:
        if enabled and key not in enabled:
            continue
        definition = registry.get(key)
        if definition is not None:
            return definition
    return None


def _build_insight(
    *,
    event: VizaEvent,
    definition: InsightTypeDefinition,
    evidence: Any,
    confidence: float,
    generated_at: datetime,
) -> VizaInsight:
    entity_id = event.affected_entity_ids[0]
    asset_id = event.affected_asset_ids[0] if event.affected_asset_ids else None
    evidence_refs = sorted(set([*event.evidence_refs, *_attribute_evidence_refs(evidence, event)]))
    direction = _direction(event, definition, evidence)
    magnitude = {
        "materiality": event.materiality,
        "novelty": event.novelty,
        "technical_confirmation": _technical_confirmation(evidence, event),
    }
    source_policy = event.rights_policy or definition.rights_policy
    payload = {
        "entity_id": entity_id,
        "asset_id": asset_id,
        "insight_type": definition.insight_type_key,
        "direction": direction,
        "available_at": event.available_at.isoformat(),
        "evidence_refs": evidence_refs,
    }
    return VizaInsight(
        insight_id=f"insight-{_hash_payload(payload)[:24]}",
        entity_id=entity_id,
        asset_id=asset_id,
        related_entity_ids=event.related_entity_ids,
        related_asset_ids=[],
        insight_type=definition.insight_type_key,
        direction=direction,
        magnitude=magnitude,
        confidence=confidence,
        time_horizon=definition.horizon_defaults,
        evidence_refs=evidence_refs,
        source_policy=source_policy,
        observed_at=event.observed_at,
        available_at=event.available_at,
        generated_at=generated_at,
        strategy_compatibility=[
            {"strategy_profile": profile, "fit": "candidate"}
            for profile in definition.compatible_strategy_profiles
        ],
        risk_factors=sorted(set([*definition.risk_factors, *event.risk_factors])),
        invalidation_conditions=definition.invalidation_templates,
        action_layer={"suggested_action": "review", "requires_human_confirmation": True},
        derivation_trace={
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source_credibility": event.source_credibility,
            "definition": definition.insight_type_key,
            "confidence_logic": definition.confidence_logic,
        },
    )


def _insight_confidence(
    event: VizaEvent,
    evidence: Any,
    definition: InsightTypeDefinition,
) -> float:
    technical_confirmation = _technical_confirmation(evidence, event)
    components = [
        event.confidence,
        event.source_credibility if event.source_credibility is not None else 0.6,
        event.materiality if event.materiality is not None else 0.5,
        event.novelty if event.novelty is not None else 0.5,
        technical_confirmation if technical_confirmation is not None else 0.45,
    ]
    missing_penalty = 0.08 * max(0, len(definition.required_attributes) - len(_attribute_evidence_refs(evidence, event)))
    return round(max(0.0, min(1.0, sum(components) / len(components) - missing_penalty)), 6)


def _direction(event: VizaEvent, definition: InsightTypeDefinition, evidence: Any) -> str:
    if event.direction_hint:
        return event.direction_hint
    if definition.direction_logic == "positive_if_momentum_positive":
        momentum = _attribute_value(evidence, event, "momentum")
        return "positive" if isinstance(momentum, (int, float)) and momentum >= 0 else "negative"
    if definition.direction_logic == "positive_if_oversold":
        return "positive"
    return "watch"


def _technical_confirmation(evidence: Any, event: VizaEvent) -> float | None:
    momentum = _attribute_value(evidence, event, "momentum")
    if isinstance(momentum, (int, float)):
        return max(0.0, min(1.0, 0.5 + float(momentum) / 2))
    rsi = _attribute_value(evidence, event, "rsi_14d")
    if isinstance(rsi, (int, float)):
        return max(0.0, min(1.0, (35 - float(rsi)) / 35 + 0.5))
    return None


def _attribute_value(evidence: Any, event: VizaEvent, attribute_key: str) -> Any:
    if not isinstance(evidence, dict):
        return None
    for event_ref in event.evidence_refs:
        parts = event_ref.split(":")
        if len(parts) >= 3:
            candidate = f"attr:{parts[1]}:{attribute_key}"
            record = evidence.get(candidate)
            if isinstance(record, dict):
                return record.get("value")
    return None


def _attribute_evidence_refs(evidence: Any, event: VizaEvent) -> list[str]:
    refs: list[str] = []
    if not isinstance(evidence, dict):
        return refs
    for event_ref in event.evidence_refs:
        parts = event_ref.split(":")
        if len(parts) >= 3:
            for key in ["momentum", "rsi_14d", "volume_spike", "moving_average_trend"]:
                candidate = f"attr:{parts[1]}:{key}"
                if candidate in evidence:
                    refs.append(candidate)
    return refs


def _insight_row_values(insight: VizaInsight) -> tuple[Any, ...]:
    return (
        insight.insight_id,
        insight.entity_id,
        insight.asset_id,
        json.dumps(insight.related_entity_ids, sort_keys=True),
        json.dumps(insight.related_asset_ids, sort_keys=True),
        insight.insight_type,
        insight.direction,
        json.dumps(insight.magnitude, sort_keys=True) if insight.magnitude is not None else None,
        insight.confidence,
        json.dumps(insight.time_horizon, sort_keys=True),
        json.dumps(insight.evidence_refs, sort_keys=True),
        json.dumps(insight.source_policy, sort_keys=True),
        insight.observed_at.isoformat(),
        insight.available_at.isoformat(),
        insight.generated_at.isoformat(),
        json.dumps(insight.strategy_compatibility, sort_keys=True),
        json.dumps(insight.risk_factors, sort_keys=True),
        json.dumps(insight.invalidation_conditions, sort_keys=True),
        json.dumps(insight.action_layer, sort_keys=True),
        json.dumps(insight.derivation_trace, sort_keys=True),
    )


def _insight_from_row(row: sqlite3.Row) -> VizaInsight:
    return VizaInsight(
        insight_id=row["insight_id"],
        entity_id=row["entity_id"],
        asset_id=row["asset_id"],
        related_entity_ids=json.loads(row["related_entity_ids_json"]),
        related_asset_ids=json.loads(row["related_asset_ids_json"]),
        insight_type=row["insight_type"],
        direction=row["direction"],
        magnitude=json.loads(row["magnitude_json"]) if row["magnitude_json"] else None,
        confidence=row["confidence"],
        time_horizon=json.loads(row["time_horizon_json"]),
        evidence_refs=json.loads(row["evidence_refs_json"]),
        source_policy=json.loads(row["source_policy_json"]),
        observed_at=datetime.fromisoformat(row["observed_at"]),
        available_at=datetime.fromisoformat(row["available_at"]),
        generated_at=datetime.fromisoformat(row["generated_at"]),
        strategy_compatibility=json.loads(row["strategy_compatibility_json"]),
        risk_factors=json.loads(row["risk_factors_json"]),
        invalidation_conditions=json.loads(row["invalidation_conditions_json"]),
        action_layer=json.loads(row["action_layer_json"]),
        derivation_trace=json.loads(row["derivation_trace_json"]),
    )


def _model_or_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value if isinstance(value, dict) else {}


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sanitize_export_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    credential_fragments = {"credential", "password", "secret", "token", "api_key", "apikey"}
    return {
        key: nested_value
        for key, nested_value in value.items()
        if not any(fragment in str(key).lower() for fragment in credential_fragments)
    }
