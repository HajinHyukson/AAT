from __future__ import annotations

from dataclasses import dataclass

from engine.contracts import ConfidenceLevel


@dataclass(frozen=True)
class ShortInterestSignal:
    short_interest: float
    average_daily_volume: float
    float_shares: float | None = None

    @property
    def days_to_cover(self) -> float:
        if self.average_daily_volume <= 0:
            raise ValueError("average_daily_volume must be positive")
        return self.short_interest / self.average_daily_volume

    @property
    def short_interest_pct_float(self) -> float | None:
        if self.float_shares is None:
            return None
        if self.float_shares <= 0:
            raise ValueError("float_shares must be positive")
        return self.short_interest / self.float_shares


def short_interest_confidence(signal: ShortInterestSignal) -> ConfidenceLevel:
    if signal.float_shares is None:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.MEDIUM_HIGH
