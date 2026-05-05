from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from engine.confidence.scoring import confidence_from_penalties, standard_factor_penalties
from engine.contracts import DriverType, FactorContributionInput, PriceBar, TimeWindow
from engine.factors.market_model import _daily_returns_bps
from engine.factors.regression import (
    attribution_factor_move,
    paired_estimation_returns,
    simple_beta,
    visible_stock_returns,
)
from engine.time import is_point_in_time_visible


MODEL_VERSION = "peer-basket-v0"


@dataclass(frozen=True)
class PeerWeight:
    peer_security_id: UUID
    weight: float
    active_from: datetime
    active_to: datetime | None
    timestamp_available: datetime


def build_peer_basket_returns(
    *,
    peer_weights: list[PeerWeight],
    price_bars_by_security: dict[UUID, list[PriceBar]],
    attribution_cutoff: datetime,
) -> dict[datetime, float]:
    normalized_weights = _active_visible_weights(
        peer_weights=peer_weights,
        attribution_cutoff=attribution_cutoff,
    )
    if not normalized_weights:
        return {}

    returns_by_peer = {}
    for security_id, weight in normalized_weights.items():
        bars = [
            bar
            for bar in price_bars_by_security.get(security_id, [])
            if is_point_in_time_visible(bar, attribution_cutoff)
        ]
        bars.sort(key=lambda item: item.event_time)
        returns_by_peer[security_id] = _daily_returns_bps(bars)

    common_dates = set.intersection(
        *[set(peer_returns) for peer_returns in returns_by_peer.values()]
    ) if returns_by_peer else set()
    return {
        event_time: sum(
            normalized_weights[security_id] * returns_by_peer[security_id][event_time]
            for security_id in normalized_weights
        )
        for event_time in common_dates
    }


def build_peer_factor_input(
    *,
    security_id: UUID,
    basket_name: str,
    basket_version: str,
    price_bars: list[PriceBar],
    peer_basket_returns: dict[datetime, float],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
    min_observations: int = 10,
) -> FactorContributionInput | None:
    stock_returns = visible_stock_returns(
        security_id=security_id,
        price_bars=price_bars,
        estimation_window=estimation_window,
        attribution_window=attribution_window,
        attribution_cutoff=attribution_cutoff,
    )
    paired = paired_estimation_returns(
        stock_returns=stock_returns,
        factor_returns=peer_basket_returns,
        estimation_window=estimation_window,
    )
    if len(paired) < min_observations:
        return None
    beta = simple_beta(y=[item[0] for item in paired], x=[item[1] for item in paired])
    factor_move = attribution_factor_move(
        factor_returns=peer_basket_returns,
        attribution_window=attribution_window,
    )
    contribution_bps = beta * factor_move
    confidence = confidence_from_penalties(
        penalties=standard_factor_penalties(
            observations=len(paired),
            min_observations=min_observations,
        )
    )
    return FactorContributionInput(
        security_id=security_id,
        driver=DriverType.PEER,
        name=f"Peer basket ({basket_name})",
        contribution_bps=contribution_bps,
        confidence=confidence,
        factor_move=factor_move,
        factor_move_unit="bps",
        exposure_value=beta,
        exposure_unit="beta",
        evidence=[
            f"beta={beta:.4f}",
            f"peer_basket_return_bps={factor_move:.4f}",
            f"observations={len(paired)}",
            f"basket_version={basket_version}",
            f"model={MODEL_VERSION}",
        ],
        evidence_payload={
            "basket_name": basket_name,
            "basket_version": basket_version,
            "beta": beta,
            "factor_move_bps": factor_move,
            "observations": len(paired),
            "model_version": MODEL_VERSION,
        },
        event_time=attribution_window.end,
        ingestion_time=attribution_cutoff,
        timestamp_available=attribution_cutoff,
    )


def _active_visible_weights(
    *,
    peer_weights: list[PeerWeight],
    attribution_cutoff: datetime,
) -> dict[UUID, float]:
    raw = {
        item.peer_security_id: item.weight
        for item in peer_weights
        if item.timestamp_available <= attribution_cutoff
        and item.active_from <= attribution_cutoff
        and (item.active_to is None or item.active_to > attribution_cutoff)
        and item.weight > 0
    }
    total = sum(raw.values())
    if total <= 0:
        return {}
    return {security_id: weight / total for security_id, weight in raw.items()}
