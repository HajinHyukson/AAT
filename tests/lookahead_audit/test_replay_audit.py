from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from db import models
from engine.audit.replay import evidence_payload_is_visible


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_replay_audit_detects_future_available_contribution_evidence() -> None:
    run = models.AttributionRun(
        attribution_run_id=uuid4(),
        security_id=uuid4(),
        window_start=dt(1),
        window_end=dt(2),
        attribution_cutoff=dt(2),
        observed_return_bps=100,
        unexplained_residual_bps=0,
        model_version="test",
        data_version="test",
        factor_basket_version="test",
        created_at=dt(3),
    )
    contribution = models.AttributionContribution(
        attribution_contribution_id=uuid4(),
        attribution_run_id=run.attribution_run_id,
        driver="market",
        name="Future evidence",
        contribution_bps=100,
        share_of_move=1,
        confidence="Medium",
        evidence=[],
        contribution_stage="production",
        evidence_payload={"timestamp_available": dt(3).isoformat()},
    )

    assert not evidence_payload_is_visible(
        evidence_payload=contribution.evidence_payload,
        attribution_cutoff=run.attribution_cutoff,
    )
