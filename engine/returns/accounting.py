from __future__ import annotations

from datetime import datetime
from uuid import UUID

from engine.contracts import PriceBar, TimeWindow
from engine.time import is_point_in_time_visible


def close_to_close_return_bps(
    *,
    security_id: UUID,
    window: TimeWindow,
    bars: list[PriceBar],
    attribution_cutoff: datetime,
) -> float:
    visible_bars = [
        bar
        for bar in bars
        if bar.security_id == security_id
        and window.start <= bar.event_time <= window.end
        and is_point_in_time_visible(bar, attribution_cutoff)
    ]
    visible_bars.sort(key=lambda bar: bar.event_time)

    if len(visible_bars) < 2:
        raise ValueError("at least two point-in-time visible price bars are required")

    start_price = visible_bars[0].adjusted_close
    end_price = visible_bars[-1].adjusted_close
    return ((end_price / start_price) - 1.0) * 10_000
