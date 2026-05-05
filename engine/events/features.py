from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


MODEL_VERSION = "edgar-feature-heuristic-v0"
OFFICIAL_SEC_SOURCES = {"sec_edgar", "faustcalc_sec_edgar_snapshot"}


class EventFeature(BaseModel):
    event_id: UUID
    company_id: UUID
    security_id: UUID | None
    event_time: datetime
    ingestion_time: datetime
    timestamp_available: datetime
    relevance: float = Field(ge=0, le=1)
    novelty: float = Field(ge=0, le=1)
    sentiment: float = Field(ge=-1, le=1)
    magnitude: float = Field(ge=0, le=1)
    source_credibility: float = Field(ge=0, le=1)
    exposure_match: float = Field(ge=0, le=1)
    surprise: float = Field(ge=-1, le=1)
    evidence_span: str
    model_version: str = MODEL_VERSION


FORM_SCORES = {
    "8-K": {"relevance": 0.95, "novelty": 0.75, "magnitude": 0.70, "exposure_match": 0.70},
    "10-K": {"relevance": 0.90, "novelty": 0.55, "magnitude": 0.65, "exposure_match": 0.60},
    "10-Q": {"relevance": 0.85, "novelty": 0.45, "magnitude": 0.55, "exposure_match": 0.55},
    "SCHEDULE 13G": {
        "relevance": 0.80,
        "novelty": 0.70,
        "magnitude": 0.50,
        "exposure_match": 0.65,
    },
    "13G": {"relevance": 0.80, "novelty": 0.70, "magnitude": 0.50, "exposure_match": 0.65},
    "4": {"relevance": 0.65, "novelty": 0.35, "magnitude": 0.25, "exposure_match": 0.35},
    "144": {"relevance": 0.55, "novelty": 0.30, "magnitude": 0.20, "exposure_match": 0.30},
}


def build_edgar_event_feature(
    *,
    event_id: UUID,
    company_id: UUID,
    security_id: UUID | None,
    event_type: str,
    source: str,
    source_id: str,
    event_time: datetime,
    ingestion_time: datetime,
    timestamp_available: datetime,
) -> EventFeature:
    normalized_form = event_type.upper()
    scores = FORM_SCORES.get(
        normalized_form,
        {"relevance": 0.50, "novelty": 0.30, "magnitude": 0.20, "exposure_match": 0.25},
    )
    evidence_span = f"source={source}; form={event_type}; accession={source_id}"
    return EventFeature(
        event_id=event_id,
        company_id=company_id,
        security_id=security_id,
        event_time=event_time,
        ingestion_time=ingestion_time,
        timestamp_available=timestamp_available,
        relevance=scores["relevance"],
        novelty=scores["novelty"],
        sentiment=0.0,
        magnitude=scores["magnitude"],
        source_credibility=1.0 if source in OFFICIAL_SEC_SOURCES else 0.7,
        exposure_match=scores["exposure_match"],
        surprise=0.0,
        evidence_span=evidence_span,
    )
