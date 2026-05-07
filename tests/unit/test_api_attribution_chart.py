from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

import api.main as api_main
from db import models


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_chart_range_to_cadence_mapping() -> None:
    assert api_main.chart_cadence("10d") == "daily"
    assert api_main.chart_cadence("1m") == "daily"
    assert api_main.chart_cadence("3m") == "daily"
    assert api_main.chart_cadence("6m") == "weekly"
    assert api_main.chart_cadence("1y") == "weekly"
    assert api_main.chart_cadence("max") == "weekly"


def test_chart_price_points_normalize_to_range_start() -> None:
    security_id = uuid4()
    bars = [
        price_bar(security_id=security_id, day=2, adjusted_close=100),
        price_bar(security_id=security_id, day=3, adjusted_close=105),
        price_bar(security_id=security_id, day=4, adjusted_close=95),
    ]

    points = api_main.build_chart_price_points(bars)

    assert points[0].cumulative_return_pct == pytest.approx(0)
    assert points[1].cumulative_return_pct == pytest.approx(5)
    assert points[2].cumulative_return_pct == pytest.approx(-5)


def test_chart_attribution_points_convert_bps_to_percent_points() -> None:
    run_id = uuid4()
    security_id = uuid4()
    run = attribution_run(
        attribution_run_id=run_id,
        security_id=security_id,
        observed_return_bps=250,
    )
    contribution = attribution_contribution(
        attribution_run_id=run_id,
        driver="market",
        name="Market",
        contribution_bps=125,
        share_of_move=0.5,
    )

    points = api_main.build_chart_attribution_points(runs=[run], contributions=[contribution])

    assert points[0].observed_return_pct == pytest.approx(2.5)
    assert points[0].contributions[0].contribution_pct == pytest.approx(1.25)
    assert points[0].contributions[0].share_of_move == pytest.approx(0.5)


def test_chart_attribution_points_suppress_unstable_share_percentages() -> None:
    run_id = uuid4()
    security_id = uuid4()
    run = attribution_run(
        attribution_run_id=run_id,
        security_id=security_id,
        observed_return_bps=1,
    )
    contribution = attribution_contribution(
        attribution_run_id=run_id,
        driver="unexplained_residual",
        name="Residual",
        contribution_bps=70,
        share_of_move=70,
    )

    points = api_main.build_chart_attribution_points(runs=[run], contributions=[contribution])

    assert points[0].contributions[0].share_of_move is None


def test_latest_residual_usd_suppresses_unstable_denominator() -> None:
    assert api_main.latest_residual_usd(
        latest_residual_bps=70,
        latest_observed_return_bps=1,
        latest_price_change_usd=0.01,
    ) is None


def test_attribute_share_aggregation_includes_small_attributes() -> None:
    run_id = uuid4()
    security_id = uuid4()
    run = attribution_run(
        attribution_run_id=run_id,
        security_id=security_id,
        observed_return_bps=100,
    )
    points = api_main.build_chart_attribution_points(
        runs=[run],
        contributions=[
            attribution_contribution(
                attribution_run_id=run_id,
                driver="market",
                name="Market",
                contribution_bps=10,
                share_of_move=0.10,
            ),
            attribution_contribution(
                attribution_run_id=run_id,
                driver="style",
                name="Style",
                contribution_bps=2,
                share_of_move=0.02,
            ),
        ],
    )

    attribute_shares = api_main.average_attribute_shares(points)

    assert attribute_shares == [
        {"driver": "market", "name": "Market", "average_share_of_move": pytest.approx(0.10)},
        {"driver": "style", "name": "Style", "average_share_of_move": pytest.approx(0.02)},
    ]


def test_chart_attribution_points_allow_missing_attribution_rows() -> None:
    run_id = uuid4()
    security_id = uuid4()
    run = attribution_run(
        attribution_run_id=run_id,
        security_id=security_id,
        observed_return_bps=100,
    )

    points = api_main.build_chart_attribution_points(runs=[run], contributions=[])

    assert points[0].contributions == []


def price_bar(*, security_id, day: int, adjusted_close: float) -> models.PriceBar:
    return models.PriceBar(
        price_bar_id=uuid4(),
        security_id=security_id,
        event_time=dt(day),
        ingestion_time=dt(day),
        timestamp_available=dt(day),
        close=adjusted_close,
        adjusted_close=adjusted_close,
        currency="USD",
        source="test",
    )


def attribution_run(*, attribution_run_id, security_id, observed_return_bps: float) -> models.AttributionRun:
    return models.AttributionRun(
        attribution_run_id=attribution_run_id,
        security_id=security_id,
        window_start=dt(2),
        window_end=dt(3),
        attribution_cutoff=dt(4),
        observed_return_bps=observed_return_bps,
        unexplained_residual_bps=0,
        model_version="test",
        data_version="test",
        factor_basket_version="test",
        cadence="daily",
        created_at=dt(4),
    )


def attribution_contribution(
    *,
    attribution_run_id,
    driver: str,
    name: str,
    contribution_bps: float,
    share_of_move: float,
) -> models.AttributionContribution:
    return models.AttributionContribution(
        attribution_contribution_id=uuid4(),
        attribution_run_id=attribution_run_id,
        driver=driver,
        name=name,
        contribution_bps=contribution_bps,
        share_of_move=share_of_move,
        confidence="Medium",
        evidence=[],
        contribution_stage="production",
        evidence_payload={},
    )
