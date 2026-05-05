from __future__ import annotations

from dataclasses import dataclass

from engine.contracts import ConfidenceLevel


@dataclass(frozen=True)
class ConfidencePenalty:
    reason: str
    severity: int = 1

    def __post_init__(self) -> None:
        if self.severity < 0:
            raise ValueError("confidence penalty severity must be nonnegative")


CONFIDENCE_LADDER = [
    ConfidenceLevel.HIGH,
    ConfidenceLevel.MEDIUM_HIGH,
    ConfidenceLevel.MEDIUM,
    ConfidenceLevel.LOW_MEDIUM,
    ConfidenceLevel.LOW,
]


def confidence_from_penalties(
    *,
    base: ConfidenceLevel = ConfidenceLevel.HIGH,
    penalties: list[ConfidencePenalty] | None = None,
) -> ConfidenceLevel:
    penalty_steps = sum(item.severity for item in penalties or [])
    base_index = CONFIDENCE_LADDER.index(base)
    return CONFIDENCE_LADDER[min(base_index + penalty_steps, len(CONFIDENCE_LADDER) - 1)]


def standard_factor_penalties(
    *,
    observations: int,
    min_observations: int,
    condition_number: float | None = None,
    stale: bool = False,
    proxy_mismatch: bool = False,
    unstable_sign: bool = False,
) -> list[ConfidencePenalty]:
    penalties: list[ConfidencePenalty] = []
    if observations < min_observations:
        penalties.append(ConfidencePenalty("insufficient_observations", 2))
    if condition_number is not None and condition_number > 30:
        penalties.append(ConfidencePenalty("high_collinearity", 1))
    if stale:
        penalties.append(ConfidencePenalty("stale_source", 1))
    if proxy_mismatch:
        penalties.append(ConfidencePenalty("proxy_mismatch", 1))
    if unstable_sign:
        penalties.append(ConfidencePenalty("unstable_beta_sign", 1))
    return penalties
