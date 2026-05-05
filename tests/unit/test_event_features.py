from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from engine.events.features import build_edgar_event_feature


def test_edgar_feature_returns_structured_scores_without_causal_claims() -> None:
    feature = build_edgar_event_feature(
        event_id=uuid4(),
        company_id=uuid4(),
        security_id=uuid4(),
        event_type="8-K",
        source="sec_edgar",
        source_id="0000320193-26-000001",
        event_time=datetime(2026, 1, 30, tzinfo=timezone.utc),
        ingestion_time=datetime(2026, 1, 30, tzinfo=timezone.utc),
        timestamp_available=datetime(2026, 1, 30, tzinfo=timezone.utc),
    )

    assert feature.relevance == 0.95
    assert feature.source_credibility == 1.0
    assert "drove" not in feature.evidence_span.lower()
    assert "accession=0000320193-26-000001" in feature.evidence_span


def test_faustcalc_sec_snapshot_keeps_official_sec_credibility() -> None:
    feature = build_edgar_event_feature(
        event_id=uuid4(),
        company_id=uuid4(),
        security_id=uuid4(),
        event_type="10-K",
        source="faustcalc_sec_edgar_snapshot",
        source_id="0000320193-26-000002",
        event_time=datetime(2026, 1, 30, tzinfo=timezone.utc),
        ingestion_time=datetime(2026, 1, 30, tzinfo=timezone.utc),
        timestamp_available=datetime(2026, 1, 30, tzinfo=timezone.utc),
    )

    assert feature.source_credibility == 1.0
