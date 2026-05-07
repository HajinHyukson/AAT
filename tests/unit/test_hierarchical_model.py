from __future__ import annotations

from datetime import datetime, timezone

import pytest

from engine.contracts import DriverType
from engine.factors.hierarchical_model import (
    HierarchicalFactorSpec,
    residualize_factor_returns,
)
from engine.contracts import TimeWindow


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_residualization_removes_prior_linear_projection() -> None:
    prior = {dt(day): float(day) for day in range(1, 8)}
    target = {event_time: 2.0 * value + 3.0 for event_time, value in prior.items()}

    residualized, condition_number, residualized_against = residualize_factor_returns(
        target_returns=target,
        prior_returns=[prior],
        estimation_window=TimeWindow(start=dt(1), end=dt(7)),
    )

    assert condition_number >= 1
    assert residualized_against == ["prior_layer_0"]
    assert all(value == pytest.approx(0.0, abs=1e-9) for value in residualized.values())


def test_hierarchical_factor_spec_preserves_driver_metadata() -> None:
    spec = HierarchicalFactorSpec(
        factor_name="sector:Information Technology",
        driver=DriverType.SECTOR,
        display_name="Residualized sector",
        raw_returns={},
    )

    assert spec.driver == DriverType.SECTOR
    assert spec.factor_name.startswith("sector:")
