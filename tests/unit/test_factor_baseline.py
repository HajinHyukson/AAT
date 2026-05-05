from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from engine.contracts import DriverType, FactorContributionInput, TimeWindow
from engine.factors.baseline import build_factor_baseline_result


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_factor_baseline_reconciles_with_explicit_residual() -> None:
    security_id = uuid4()
    result = build_factor_baseline_result(
        security_id=security_id,
        window=TimeWindow(start=dt(1), end=dt(2)),
        attribution_cutoff=dt(2),
        observed_return_bps=400,
        factor_inputs=[
            FactorContributionInput(
                security_id=security_id,
                driver=DriverType.MARKET,
                name="Market beta",
                contribution_bps=100,
                event_time=dt(2),
                ingestion_time=dt(2),
                timestamp_available=dt(2),
            ),
            FactorContributionInput(
                security_id=security_id,
                driver=DriverType.SECTOR,
                name="Sector beta",
                contribution_bps=50,
                event_time=dt(2),
                ingestion_time=dt(2),
                timestamp_available=dt(2),
            ),
        ],
    )

    assert result.unexplained_residual_bps == 250
    assert sum(item.contribution_bps for item in result.contributions) == pytest.approx(400)
    assert result.contributions[-1].driver == DriverType.UNEXPLAINED_RESIDUAL


def test_factor_baseline_excludes_future_available_inputs() -> None:
    security_id = uuid4()
    result = build_factor_baseline_result(
        security_id=security_id,
        window=TimeWindow(start=dt(1), end=dt(2)),
        attribution_cutoff=dt(2),
        observed_return_bps=100,
        factor_inputs=[
            FactorContributionInput(
                security_id=security_id,
                driver=DriverType.MARKET,
                name="Leaky market",
                contribution_bps=90,
                event_time=dt(2),
                ingestion_time=dt(2),
                timestamp_available=dt(3),
            ),
        ],
    )

    assert len(result.contributions) == 1
    assert result.unexplained_residual_bps == 100
