from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.insights import VizaInsight, get_insight_store
from viza.project_store import project_store_path
from viza.strategy_profiles import (
    VizaStrategyProfile,
    get_strategy_profile_store,
    load_strategy_profile_templates,
)


class VizaTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.translation.v1", alias="schema")
    translation_id: str
    insight_id: str
    strategy_profile_id: str
    entity_id: str
    asset_id: str | None = None
    fit_score: float = Field(ge=0, le=1)
    relevance: str
    translated_summary: str
    strategy_fit_reasons: list[str] = Field(default_factory=list)
    missing_confirmations: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    suggested_research_action: str
    evidence_refs: list[str] = Field(default_factory=list)
    generated_at: datetime
    not_investment_advice: bool = True


class TranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insight_id: str | None = None
    insight: VizaInsight | None = None
    strategy_profile_id: str | None = None
    strategy_profile: VizaStrategyProfile | None = None
    persist: bool = True

    @model_validator(mode="after")
    def require_inputs(self) -> "TranslationRequest":
        if self.insight_id is None and self.insight is None:
            raise ValueError("translation requires insight or insight_id")
        if self.strategy_profile_id is None and self.strategy_profile is None:
            raise ValueError("translation requires strategy_profile or strategy_profile_id")
        return self


class TranslationBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insights: list[VizaInsight] = Field(default_factory=list)
    insight_ids: list[str] = Field(default_factory=list)
    strategy_profile_id: str | None = None
    strategy_profile: VizaStrategyProfile | None = None
    persist: bool = True


class TranslationStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def upsert_translation(self, translation: VizaTranslation) -> VizaTranslation:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO translations(
                    translation_id,
                    insight_id,
                    strategy_profile_id,
                    entity_id,
                    asset_id,
                    fit_score,
                    relevance,
                    translated_summary,
                    strategy_fit_reasons_json,
                    missing_confirmations_json,
                    risk_factors_json,
                    invalidation_conditions_json,
                    suggested_research_action,
                    evidence_refs_json,
                    generated_at,
                    not_investment_advice
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(translation_id) DO UPDATE SET
                    fit_score = excluded.fit_score,
                    relevance = excluded.relevance,
                    translated_summary = excluded.translated_summary,
                    strategy_fit_reasons_json = excluded.strategy_fit_reasons_json,
                    missing_confirmations_json = excluded.missing_confirmations_json,
                    risk_factors_json = excluded.risk_factors_json,
                    invalidation_conditions_json = excluded.invalidation_conditions_json,
                    suggested_research_action = excluded.suggested_research_action,
                    evidence_refs_json = excluded.evidence_refs_json,
                    generated_at = excluded.generated_at,
                    not_investment_advice = excluded.not_investment_advice
                """,
                _translation_row_values(translation),
            )
        return self.require_translation(translation.translation_id)

    def get_translation(self, translation_id: str) -> VizaTranslation | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM translations WHERE translation_id = ?",
                (translation_id,),
            ).fetchone()
        return _translation_from_row(row) if row is not None else None

    def require_translation(self, translation_id: str) -> VizaTranslation:
        translation = self.get_translation(translation_id)
        if translation is None:
            raise KeyError(f"unknown VIZA translation: {translation_id}")
        return translation

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(TRANSLATION_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


TRANSLATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS translations (
  translation_id TEXT PRIMARY KEY,
  insight_id TEXT NOT NULL,
  strategy_profile_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  asset_id TEXT,
  fit_score REAL NOT NULL,
  relevance TEXT NOT NULL,
  translated_summary TEXT NOT NULL,
  strategy_fit_reasons_json TEXT NOT NULL DEFAULT '[]',
  missing_confirmations_json TEXT NOT NULL DEFAULT '[]',
  risk_factors_json TEXT NOT NULL DEFAULT '[]',
  invalidation_conditions_json TEXT NOT NULL DEFAULT '[]',
  suggested_research_action TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  generated_at TEXT NOT NULL,
  not_investment_advice INTEGER NOT NULL DEFAULT 1
);
"""


def get_translation_store(path: str | Path | None = None) -> TranslationStore:
    return TranslationStore(path)


def translate_insight(
    insight: VizaInsight,
    strategy_profile: VizaStrategyProfile,
    *,
    generated_at: datetime | None = None,
) -> VizaTranslation:
    generated = generated_at or datetime.now(timezone.utc)
    fit_score, reasons, missing, risk_flags = _fit_components(insight, strategy_profile)
    relevance = "high" if fit_score >= 0.75 else "medium" if fit_score >= 0.5 else "low"
    action = _suggested_action(fit_score, strategy_profile)
    summary = _translated_summary(insight, strategy_profile, relevance, action)
    payload = {
        "insight_id": insight.insight_id,
        "strategy_profile_id": strategy_profile.strategy_profile_id,
        "fit_score": fit_score,
        "evidence_refs": insight.evidence_refs,
    }
    return VizaTranslation(
        translation_id=f"translation-{_hash_payload(payload)[:24]}",
        insight_id=insight.insight_id,
        strategy_profile_id=strategy_profile.strategy_profile_id,
        entity_id=insight.entity_id,
        asset_id=insight.asset_id,
        fit_score=fit_score,
        relevance=relevance,
        translated_summary=summary,
        strategy_fit_reasons=reasons,
        missing_confirmations=missing,
        risk_factors=sorted(set([*insight.risk_factors, *risk_flags])),
        invalidation_conditions=insight.invalidation_conditions,
        suggested_research_action=action,
        evidence_refs=insight.evidence_refs,
        generated_at=generated,
    )


def translate_request(request: TranslationRequest) -> VizaTranslation:
    insight = request.insight or get_insight_store().require_insight(request.insight_id or "")
    profile = request.strategy_profile or get_strategy_profile_store().require_profile(
        request.strategy_profile_id or "",
    )
    translation = translate_insight(insight, profile)
    if request.persist:
        translation = get_translation_store().upsert_translation(translation)
    return translation


def translate_batch(request: TranslationBatchRequest) -> list[VizaTranslation]:
    profile = request.strategy_profile or get_strategy_profile_store().require_profile(
        request.strategy_profile_id or "",
    )
    insights = [
        *request.insights,
        *[get_insight_store().require_insight(insight_id) for insight_id in request.insight_ids],
    ]
    translations = [translate_insight(insight, profile) for insight in insights]
    if request.persist:
        store = get_translation_store()
        translations = [store.upsert_translation(translation) for translation in translations]
    return translations


def default_strategy_profile() -> VizaStrategyProfile:
    template = load_strategy_profile_templates().templates[0]
    now = datetime.now(timezone.utc)
    return VizaStrategyProfile(
        strategy_profile_id=template.strategy_profile_id or "default-rsi-catalyst",
        display_name=template.display_name,
        domain=template.domain,
        module_id=template.module_id,
        entity_types=template.entity_types,
        universe_constraints=template.universe_constraints,
        holding_period=template.holding_period,
        preferred_indicators=template.preferred_indicators,
        catalyst_types=template.catalyst_types,
        required_confirmations=template.required_confirmations,
        risk_limits=template.risk_limits,
        output_preferences=template.output_preferences,
        action_thresholds=template.action_thresholds,
        evidence_requirements=template.evidence_requirements,
        decision_rules=template.decision_rules,
        created_at=now,
        updated_at=now,
    )


def translation_for_export(translation: VizaTranslation) -> dict[str, Any]:
    payload = translation.model_dump(mode="json", by_alias=True)
    payload["not_investment_advice"] = True
    return payload


def _fit_components(
    insight: VizaInsight,
    profile: VizaStrategyProfile,
) -> tuple[float, list[str], list[str], list[str]]:
    reasons: list[str] = []
    missing: list[str] = []
    risk_flags: list[str] = []
    score = 0.0

    if profile.module_id == "viza.finance.securities" and profile.domain == "finance.securities":
        score += 0.15
        reasons.append("Profile domain matches the finance securities insight.")
    if _event_type(insight) in profile.catalyst_types:
        score += 0.25
        reasons.append(f"Catalyst type {_event_type(insight)} is explicitly in profile scope.")
    else:
        missing.append(f"catalyst:{_event_type(insight) or 'unknown'}")
    if _insight_indicator_match(insight, profile):
        score += 0.18
        reasons.append("Insight evidence includes a preferred indicator.")
    else:
        missing.append("preferred_indicator")
    for confirmation in profile.required_confirmations:
        if not _confirmation_present(insight, confirmation):
            missing.append(confirmation)
    score += min(0.22, insight.confidence * 0.22)
    technical = _technical_confirmation(insight)
    if technical is not None:
        score += min(0.15, technical * 0.15)
        reasons.append("Technical confirmation contributes to fit.")
    if insight.source_policy.get("raw_snapshot_allowed") is False:
        score += 0.05
        reasons.append("Evidence is derived/PIT-friendly rather than raw-source dependent.")
    if profile.risk_limits.get("avoid_extreme_volatility") and "extreme_volatility" in insight.risk_factors:
        score -= 0.15
        risk_flags.append("extreme_volatility")
    if not insight.evidence_refs:
        score -= 0.2
        risk_flags.append("weak_evidence")

    missing = sorted(set(missing))
    score -= min(0.25, len(missing) * 0.05)
    return round(max(0.0, min(1.0, score)), 6), reasons, missing, risk_flags


def _suggested_action(fit_score: float, profile: VizaStrategyProfile) -> str:
    thresholds = profile.action_thresholds
    if fit_score >= thresholds.get("high_conviction", 0.78):
        return "alert_candidate"
    if fit_score >= thresholds.get("watchlist", 0.6):
        return "watchlist"
    if fit_score >= thresholds.get("review", 0.45):
        return "research_deeper"
    return "reject_or_ignore"


def _translated_summary(
    insight: VizaInsight,
    profile: VizaStrategyProfile,
    relevance: str,
    action: str,
) -> str:
    return (
        f"{insight.insight_type.replace('_', ' ')} is {relevance} relevance for "
        f"{profile.display_name}; suggested workflow action: {action.replace('_', ' ')}."
    )


def _event_type(insight: VizaInsight) -> str | None:
    event_type = insight.derivation_trace.get("event_type")
    return event_type if isinstance(event_type, str) else None


def _insight_indicator_match(insight: VizaInsight, profile: VizaStrategyProfile) -> bool:
    joined_refs = " ".join(insight.evidence_refs)
    return any(indicator in joined_refs for indicator in profile.preferred_indicators)


def _confirmation_present(insight: VizaInsight, confirmation: str) -> bool:
    joined_refs = " ".join(insight.evidence_refs)
    if confirmation == "volume_confirmation":
        return "volume_spike" in joined_refs
    if confirmation == "source_credibility":
        return "source_credibility" in insight.derivation_trace
    return confirmation in joined_refs


def _technical_confirmation(insight: VizaInsight) -> float | None:
    magnitude = insight.magnitude or {}
    value = magnitude.get("technical_confirmation")
    return float(value) if isinstance(value, (int, float)) else None


def _translation_row_values(translation: VizaTranslation) -> tuple[Any, ...]:
    return (
        translation.translation_id,
        translation.insight_id,
        translation.strategy_profile_id,
        translation.entity_id,
        translation.asset_id,
        translation.fit_score,
        translation.relevance,
        translation.translated_summary,
        json.dumps(translation.strategy_fit_reasons, sort_keys=True),
        json.dumps(translation.missing_confirmations, sort_keys=True),
        json.dumps(translation.risk_factors, sort_keys=True),
        json.dumps(translation.invalidation_conditions, sort_keys=True),
        translation.suggested_research_action,
        json.dumps(translation.evidence_refs, sort_keys=True),
        translation.generated_at.isoformat(),
        1 if translation.not_investment_advice else 0,
    )


def _translation_from_row(row: sqlite3.Row) -> VizaTranslation:
    return VizaTranslation(
        translation_id=row["translation_id"],
        insight_id=row["insight_id"],
        strategy_profile_id=row["strategy_profile_id"],
        entity_id=row["entity_id"],
        asset_id=row["asset_id"],
        fit_score=row["fit_score"],
        relevance=row["relevance"],
        translated_summary=row["translated_summary"],
        strategy_fit_reasons=json.loads(row["strategy_fit_reasons_json"]),
        missing_confirmations=json.loads(row["missing_confirmations_json"]),
        risk_factors=json.loads(row["risk_factors_json"]),
        invalidation_conditions=json.loads(row["invalidation_conditions_json"]),
        suggested_research_action=row["suggested_research_action"],
        evidence_refs=json.loads(row["evidence_refs_json"]),
        generated_at=datetime.fromisoformat(row["generated_at"]),
        not_investment_advice=bool(row["not_investment_advice"]),
    )


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
