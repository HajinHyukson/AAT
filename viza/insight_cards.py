from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.audit import stable_checksum


class InsightCardEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_ref: str
    source: str
    observed_at: str | None = None
    available_at: str | None = None
    source_credibility: float | None = None
    license_policy: str
    export_status: str
    redacted: bool = False


class InsightCardRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    source: str
    target: str
    relationship_family: str
    relationship_type: str
    direction: str
    confidence: float | None = None
    evidence_ref: str | None = None


class InsightCardAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph_hash: str
    profile_version: str | None = None
    run_id: str
    evidence_checksum: str
    result_checksum: str


class InsightCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insight_id: str
    entity_id: str
    asset_id: str | None = None
    insight_type: str
    direction: str
    confidence: float
    horizon: dict[str, str] = Field(default_factory=dict)
    strategy_fit_score: float | None = None
    translated_summary: str | None = None
    strategy_fit_reasons: list[str] = Field(default_factory=list)
    missing_confirmations: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    suggested_research_action: str | None = None
    evidence: list[InsightCardEvidence] = Field(default_factory=list)
    relationships: list[InsightCardRelationship] = Field(default_factory=list)
    audit: InsightCardAudit


def build_insight_cards_from_result(result: dict[str, Any]) -> list[InsightCardPayload]:
    insights = _dict_items(result.get("insights"))
    translations = {
        _read_string(translation.get("insight_id")): translation
        for translation in _dict_items(result.get("translations"))
        if _read_string(translation.get("insight_id"))
    }
    relationships = [
        *_dict_items(result.get("relationships")),
        *_dict_items(result.get("insight_relationships")),
    ]
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}

    cards: list[InsightCardPayload] = []
    for insight in insights:
        insight_id = _read_string(insight.get("insight_id"))
        if not insight_id:
            continue
        translation = translations.get(insight_id, {})
        evidence_refs = _read_string_list(
            translation.get("evidence_refs") or insight.get("evidence_refs")
        )
        related_relationships = _relationships_for_insight(insight, relationships)
        cards.append(
            InsightCardPayload(
                insight_id=insight_id,
                entity_id=_read_string(insight.get("entity_id")),
                asset_id=_read_optional_string(insight.get("asset_id")),
                insight_type=_read_string(insight.get("insight_type"), "unknown"),
                direction=_read_string(insight.get("direction"), "unknown"),
                confidence=_read_float(insight.get("confidence"), 0.0),
                horizon=_read_string_dict(insight.get("time_horizon")),
                strategy_fit_score=_read_optional_float(translation.get("fit_score")),
                translated_summary=_read_optional_string(translation.get("translated_summary")),
                strategy_fit_reasons=_read_string_list(translation.get("strategy_fit_reasons")),
                missing_confirmations=_read_string_list(translation.get("missing_confirmations")),
                invalidation_conditions=_read_string_list(
                    translation.get("invalidation_conditions")
                    or insight.get("invalidation_conditions")
                ),
                risk_factors=_read_string_list(
                    translation.get("risk_factors") or insight.get("risk_factors")
                ),
                suggested_research_action=_read_optional_string(
                    translation.get("suggested_research_action")
                ),
                evidence=[
                    _evidence_card(
                        evidence_ref,
                        evidence.get(evidence_ref) if isinstance(evidence, dict) else None,
                        insight,
                    )
                    for evidence_ref in evidence_refs
                ],
                relationships=related_relationships,
                audit=InsightCardAudit(
                    graph_hash=_read_string(result.get("graph_hash")),
                    profile_version=_read_optional_string(translation.get("strategy_profile_id")),
                    run_id=_read_string(result.get("run_id")),
                    evidence_checksum=_read_string(
                        _read_dict(result.get("manifest")).get("evidence_checksum")
                    )
                    or stable_checksum({ref: evidence.get(ref) for ref in evidence_refs}),
                    result_checksum=_read_string(result.get("result_checksum")),
                ),
            )
        )
    return cards


def _evidence_card(
    evidence_ref: str,
    raw_record: Any,
    insight: dict[str, Any],
) -> InsightCardEvidence:
    record = raw_record if isinstance(raw_record, dict) else {}
    entitlement = record.get("entitlement") if isinstance(record.get("entitlement"), dict) else {}
    export_allowed = entitlement.get("export_allowed")
    policy = (
        _read_string(record.get("license_policy"))
        or _read_string(record.get("entitlement_policy"))
        or _read_string(_read_dict(insight.get("source_policy")).get("license_policy"))
        or "internal"
    )
    redacted = export_allowed is False or _read_bool(_read_dict(record.get("diagnostics")).get("export_redacted"))
    source_credibility = _read_optional_float(record.get("confidence"))
    if source_credibility is None:
        source_credibility = _read_optional_float(
            _read_dict(insight.get("derivation_trace")).get("source_credibility")
        )
    return InsightCardEvidence(
        evidence_ref=evidence_ref,
        source=_read_string(record.get("source"), "unknown"),
        observed_at=_read_optional_string(record.get("source_timestamp") or record.get("observed_at")),
        available_at=_read_optional_string(
            record.get("timestamp_available") or record.get("available_at")
        ),
        source_credibility=source_credibility,
        license_policy=policy,
        export_status="redacted" if redacted else "exportable",
        redacted=redacted,
    )


def _relationships_for_insight(
    insight: dict[str, Any],
    relationships: list[dict[str, Any]],
) -> list[InsightCardRelationship]:
    insight_id = _read_string(insight.get("insight_id"))
    related_ids = {
        insight_id,
        _read_string(insight.get("entity_id")),
        _read_string(insight.get("asset_id")),
        *(_read_string_list(insight.get("evidence_refs"))),
    }
    related_ids.discard("")
    cards: list[InsightCardRelationship] = []
    for index, relationship in enumerate(relationships):
        source = _read_string(relationship.get("source") or relationship.get("source_id"))
        target = _read_string(relationship.get("target") or relationship.get("target_id"))
        if source not in related_ids and target not in related_ids:
            continue
        cards.append(
            InsightCardRelationship(
                relationship_id=_read_string(
                    relationship.get("relationship_id"),
                    f"relationship-{index}",
                ),
                source=source,
                target=target,
                relationship_family=_read_string(
                    relationship.get("relationship_family") or relationship.get("family"),
                    "unknown",
                ),
                relationship_type=_read_string(relationship.get("relationship_type"), "related"),
                direction=_read_string(relationship.get("direction"), "directed"),
                confidence=_read_optional_float(relationship.get("confidence")),
                evidence_ref=_read_optional_string(relationship.get("evidence_ref")),
            )
        )
    return cards[:24]


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _read_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_string(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) else fallback


def _read_optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _read_float(value: Any, fallback: float) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else fallback


def _read_optional_float(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _read_bool(value: Any) -> bool:
    return value if isinstance(value, bool) else False


def _read_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _read_string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, str) and isinstance(item, str)}
