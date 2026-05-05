from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from engine.contracts import ConfidenceLevel
from engine.events.features import EventFeature


MODEL_VERSION = "exposure-update-policy-v0"


class ExposureUpdateDecision(BaseModel):
    company_id: UUID
    exposure_name: str
    decision: str
    review_required: bool
    confidence: ConfidenceLevel
    rationale: str
    evidence_event_ids: list[UUID] = Field(default_factory=list)
    model_version: str = MODEL_VERSION
    evaluated_at: datetime


def exposure_name_for_event_type(event_type: str) -> str:
    normalized = event_type.upper()
    if normalized in {"10-K", "10-Q"}:
        return "periodic_financial_reporting"
    if normalized == "8-K":
        return "corporate_event_disclosure"
    if normalized in {"13G", "SCHEDULE 13G", "13D", "SC 13D"}:
        return "ownership_structure"
    if normalized in {"4", "144"}:
        return "insider_activity"
    return "general_disclosure"


def decide_exposure_updates(
    *,
    company_id: UUID,
    event_features: list[EventFeature],
    event_types_by_id: dict[UUID, str],
    evaluated_at: datetime,
) -> list[ExposureUpdateDecision]:
    grouped: dict[str, list[EventFeature]] = defaultdict(list)
    for feature in event_features:
        exposure_name = exposure_name_for_event_type(event_types_by_id.get(feature.event_id, ""))
        grouped[exposure_name].append(feature)

    decisions: list[ExposureUpdateDecision] = []
    for exposure_name, features in sorted(grouped.items()):
        review_features = [
            feature
            for feature in features
            if feature.relevance >= 0.80 and feature.magnitude >= 0.50 and feature.novelty >= 0.45
        ]
        high_impact_features = [
            feature for feature in features if feature.relevance >= 0.90 and feature.magnitude >= 0.65
        ]
        review_required = len(review_features) >= 2 or bool(high_impact_features)
        decision = "candidate_review" if review_required else "no_update"
        confidence = ConfidenceLevel.MEDIUM if review_required else ConfidenceLevel.MEDIUM_HIGH
        if review_required:
            rationale = (
                f"{len(review_features)} material structured event feature(s) for {exposure_name}; "
                "MVP policy requires human review before structural exposure changes."
            )
        else:
            rationale = (
                f"{len(features)} event feature(s) for {exposure_name}, but evidence is not persistent "
                "or material enough for an exposure update."
            )

        decisions.append(
            ExposureUpdateDecision(
                company_id=company_id,
                exposure_name=exposure_name,
                decision=decision,
                review_required=review_required,
                confidence=confidence,
                rationale=rationale,
                evidence_event_ids=[feature.event_id for feature in review_features or features[:3]],
                evaluated_at=evaluated_at,
            )
        )
    return decisions
