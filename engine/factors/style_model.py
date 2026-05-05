from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, pstdev
from uuid import UUID

from engine.contracts import ConfidenceLevel, PriceBar, SecurityFactorExposure
from engine.factors.market_model import _daily_returns_bps
from engine.time import is_point_in_time_visible


MODEL_VERSION = "return-style-descriptor-v0"


@dataclass(frozen=True)
class StyleDescriptor:
    name: str
    value: float
    unit: str
    confidence: ConfidenceLevel
    diagnostics: dict


def build_return_style_descriptors(
    *,
    security_id: UUID,
    price_bars: list[PriceBar],
    as_of: datetime,
    min_observations: int = 20,
) -> list[StyleDescriptor]:
    bars = [
        bar
        for bar in price_bars
        if bar.security_id == security_id
        and bar.event_time <= as_of
        and is_point_in_time_visible(bar, as_of)
    ]
    bars.sort(key=lambda item: item.event_time)
    returns = list(_daily_returns_bps(bars).values())
    if len(returns) < min_observations:
        return []

    descriptors = [
        StyleDescriptor(
            name="momentum",
            value=_cumulative_return_bps(returns[-252:-21] if len(returns) >= 252 else returns[:-5]),
            unit="bps",
            confidence=_descriptor_confidence(len(returns), 252),
            diagnostics={"observations": len(returns), "model_version": MODEL_VERSION},
        ),
        StyleDescriptor(
            name="short_term_reversal",
            value=-_cumulative_return_bps(returns[-21:]),
            unit="bps",
            confidence=_descriptor_confidence(len(returns), 21),
            diagnostics={"observations": len(returns[-21:]), "model_version": MODEL_VERSION},
        ),
        StyleDescriptor(
            name="realized_volatility",
            value=pstdev(returns[-60:]) * math.sqrt(252) if len(returns[-60:]) >= 2 else 0.0,
            unit="annualized_bps",
            confidence=_descriptor_confidence(len(returns), 60),
            diagnostics={"observations": len(returns[-60:]), "model_version": MODEL_VERSION},
        ),
    ]
    liquidity = _average_dollar_volume(bars[-60:])
    if liquidity is not None:
        descriptors.append(
            StyleDescriptor(
                name="liquidity",
                value=math.log1p(liquidity),
                unit="log_average_daily_dollar_volume",
                confidence=_descriptor_confidence(len(bars[-60:]), 60),
                diagnostics={
                    "observations": len(bars[-60:]),
                    "model_version": MODEL_VERSION,
                    "average_daily_dollar_volume": liquidity,
                },
            )
        )
    return descriptors


def descriptors_to_exposures(
    *,
    security_id: UUID,
    descriptors: list[StyleDescriptor],
    as_of: datetime,
) -> list[SecurityFactorExposure]:
    return [
        SecurityFactorExposure(
            security_id=security_id,
            factor_name=descriptor.name,
            exposure_value=descriptor.value,
            exposure_unit=descriptor.unit,
            exposure_method=MODEL_VERSION,
            confidence=descriptor.confidence,
            model_version=MODEL_VERSION,
            diagnostics=descriptor.diagnostics,
            event_time=as_of,
            ingestion_time=as_of,
            timestamp_available=as_of,
        )
        for descriptor in descriptors
    ]


def _cumulative_return_bps(returns_bps: list[float]) -> float:
    compounded = 1.0
    for value in returns_bps:
        compounded *= 1 + value / 10_000
    return (compounded - 1.0) * 10_000


def _average_dollar_volume(bars: list[PriceBar]) -> float | None:
    values = [
        bar.adjusted_close * bar.volume
        for bar in bars
        if bar.volume is not None
    ]
    if not values:
        return None
    return mean(values)


def _descriptor_confidence(observations: int, target: int) -> ConfidenceLevel:
    if observations >= target:
        return ConfidenceLevel.MEDIUM_HIGH
    if observations >= max(20, target // 2):
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW_MEDIUM
