from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from engine.contracts import DriverType, PriceBar, TimeWindow
from engine.events.surprise import calculate_numeric_surprise, direction_from_surprise
from engine.events.taxonomy import classify_event
from engine.exposures.gates import commodity_gate, credit_gate, fx_gate
from engine.factors.macro_model import build_macro_factor_inputs, level_changes_by_date, spread_by_date
from engine.factors.peer_model import PeerWeight, build_peer_basket_returns
from engine.factors.sector_model import build_sector_factor_inputs
from engine.factors.style_model import build_return_style_descriptors
from engine.factors.positioning_model import ShortInterestSignal


def dt(day: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


def bars(security_id, returns_bps: list[float]) -> list[PriceBar]:
    price = 100.0
    rows = [
        PriceBar(
            security_id=security_id,
            event_time=dt(1),
            ingestion_time=dt(1),
            timestamp_available=dt(1),
            close=price,
            adjusted_close=price,
            volume=1_000_000,
        )
    ]
    for offset, return_bps in enumerate(returns_bps, start=2):
        price *= 1 + return_bps / 10_000
        rows.append(
            PriceBar(
                security_id=security_id,
                event_time=dt(offset),
                ingestion_time=dt(offset),
                timestamp_available=dt(offset),
                close=price,
                adjusted_close=price,
                volume=1_000_000,
            )
        )
    return rows


def test_sector_factor_input_estimates_beta_and_contribution() -> None:
    security_id = uuid4()
    factor_returns = {dt(day): float(day) for day in range(2, 15)}
    stock_returns = [2 * factor_returns[dt(day)] for day in range(2, 15)]

    inputs = build_sector_factor_inputs(
        security_id=security_id,
        price_bars=bars(security_id, stock_returns),
        factor_returns_by_name={"XLK": factor_returns},
        estimation_window=TimeWindow(start=dt(1), end=dt(13)),
        attribution_window=TimeWindow(start=dt(13), end=dt(14)),
        attribution_cutoff=dt(15),
    )

    assert len(inputs) == 1
    assert inputs[0].driver == DriverType.SECTOR
    assert inputs[0].exposure_value == pytest.approx(2.0)
    assert inputs[0].contribution_bps == pytest.approx(28.0)


def test_peer_basket_returns_use_visible_active_weights() -> None:
    peer_a = uuid4()
    peer_b = uuid4()
    target = uuid4()
    result = build_peer_basket_returns(
        peer_weights=[
            PeerWeight(peer_a, 0.75, dt(1), None, dt(1)),
            PeerWeight(peer_b, 0.25, dt(1), None, dt(1)),
        ],
        price_bars_by_security={
            peer_a: bars(peer_a, [10, 10, 10]),
            peer_b: bars(peer_b, [30, 30, 30]),
            target: bars(target, [99, 99, 99]),
        },
        attribution_cutoff=dt(4),
    )

    assert result[dt(2)] == pytest.approx(15.0)


def test_style_descriptors_cover_momentum_volatility_and_liquidity() -> None:
    security_id = uuid4()
    descriptors = build_return_style_descriptors(
        security_id=security_id,
        price_bars=bars(security_id, [5.0] * 70),
        as_of=dt(31),
        min_observations=20,
    )

    names = {descriptor.name for descriptor in descriptors}
    assert {"momentum", "short_term_reversal", "realized_volatility", "liquidity"}.issubset(names)
    liquidity = next(descriptor for descriptor in descriptors if descriptor.name == "liquidity")
    assert liquidity.unit == "log_average_daily_dollar_volume"
    assert liquidity.value < liquidity.diagnostics["average_daily_dollar_volume"]


def test_macro_transforms_and_factor_input() -> None:
    values = {dt(1): 4.0, dt(2): 4.1, dt(3): 4.0}
    changes = level_changes_by_date(values, multiplier=100)
    assert changes[dt(2)] == pytest.approx(10.0)
    assert spread_by_date(long_values_by_date={dt(1): 5}, short_values_by_date={dt(1): 3})[dt(1)] == 2

    security_id = uuid4()
    macro_moves = {dt(day): float(day) for day in range(2, 25)}
    stock_returns = [1.5 * macro_moves[dt(day)] for day in range(2, 25)]
    inputs = build_macro_factor_inputs(
        security_id=security_id,
        price_bars=bars(security_id, stock_returns),
        macro_factor_moves_by_name={"DGS10_change": macro_moves},
        estimation_window=TimeWindow(start=dt(1), end=dt(23)),
        attribution_window=TimeWindow(start=dt(23), end=dt(24)),
        attribution_cutoff=dt(25),
    )

    assert inputs[0].driver == DriverType.MACRO
    assert inputs[0].exposure_value == pytest.approx(1.5)


def test_event_taxonomy_and_surprise() -> None:
    event_id = uuid4()
    taxonomy = classify_event(
        event_id=event_id,
        event_type="8-K",
        structured_payload={"item_code": "2.02"},
        event_time=dt(1),
        ingestion_time=dt(1),
        timestamp_available=dt(1),
    )
    surprise = calculate_numeric_surprise(
        event_id=event_id,
        surprise_name="eps_surprise",
        actual_value=1.10,
        expected_value=1.00,
        surprise_unit="ratio",
        event_time=dt(1),
        ingestion_time=dt(1),
        timestamp_available=dt(1),
    )

    assert taxonomy.event_category == "earnings"
    assert surprise.surprise_value == pytest.approx(0.10)
    assert direction_from_surprise(surprise.surprise_value) == "positive"


def test_exposure_gates_and_positioning_signal() -> None:
    commodity = commodity_gate(
        commodity="WTI",
        producer_exposure_pct=0.50,
        consumer_input_pct=0.10,
        hedge_coverage_pct=0.25,
    )
    fx = fx_gate(currency_basket="broad_usd", foreign_revenue_pct=0.60, foreign_cost_pct=0.20)
    credit = credit_gate(
        net_debt_to_ebitda_z=1.0,
        interest_coverage_z=-1.0,
        debt_maturity_wall_z=1.0,
    )
    short_interest = ShortInterestSignal(
        short_interest=10_000_000,
        average_daily_volume=2_000_000,
        float_shares=100_000_000,
    )

    assert commodity.gate_weight == 1.0
    assert fx.gate_weight == 1.0
    assert 0.0 < credit.gate_weight < 1.0
    assert short_interest.days_to_cover == 5
    assert short_interest.short_interest_pct_float == pytest.approx(0.10)
