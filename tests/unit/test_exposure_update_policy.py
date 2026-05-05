from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from engine.events.features import build_edgar_event_feature
from engine.exposures.update_policy import decide_exposure_updates, exposure_name_for_event_type


def test_exposure_name_maps_filing_types() -> None:
    assert exposure_name_for_event_type("8-K") == "corporate_event_disclosure"
    assert exposure_name_for_event_type("10-Q") == "periodic_financial_reporting"
    assert exposure_name_for_event_type("4") == "insider_activity"


def test_exposure_policy_requires_review_for_high_impact_8k_without_auto_update() -> None:
    event_id = uuid4()
    company_id = uuid4()
    now = datetime(2026, 1, 30, tzinfo=timezone.utc)
    feature = build_edgar_event_feature(
        event_id=event_id,
        company_id=company_id,
        security_id=uuid4(),
        event_type="8-K",
        source="sec_edgar",
        source_id="0000320193-26-000001",
        event_time=now,
        ingestion_time=now,
        timestamp_available=now,
    )

    decisions = decide_exposure_updates(
        company_id=company_id,
        event_features=[feature],
        event_types_by_id={event_id: "8-K"},
        evaluated_at=now,
    )

    assert decisions[0].exposure_name == "corporate_event_disclosure"
    assert decisions[0].decision == "candidate_review"
    assert decisions[0].review_required is True
