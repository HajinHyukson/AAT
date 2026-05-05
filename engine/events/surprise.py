from __future__ import annotations

from datetime import datetime
from uuid import UUID

from engine.contracts import EventSurpriseRecord


MODEL_VERSION = "event-surprise-v0"


def calculate_numeric_surprise(
    *,
    event_id: UUID,
    surprise_name: str,
    actual_value: float,
    expected_value: float,
    surprise_unit: str,
    event_time: datetime,
    ingestion_time: datetime,
    timestamp_available: datetime,
    scale: float | None = None,
) -> EventSurpriseRecord:
    denominator = scale if scale is not None else max(abs(expected_value), 1e-9)
    surprise_value = (actual_value - expected_value) / denominator
    return EventSurpriseRecord(
        event_id=event_id,
        surprise_name=surprise_name,
        surprise_value=surprise_value,
        surprise_unit=surprise_unit,
        expected_value=expected_value,
        actual_value=actual_value,
        model_version=MODEL_VERSION,
        evidence_payload={
            "actual_value": actual_value,
            "expected_value": expected_value,
            "scale": denominator,
            "model_version": MODEL_VERSION,
        },
        event_time=event_time,
        ingestion_time=ingestion_time,
        timestamp_available=timestamp_available,
    )


def direction_from_surprise(value: float, neutral_band: float = 0.01) -> str:
    if value > neutral_band:
        return "positive"
    if value < -neutral_band:
        return "negative"
    return "neutral"
