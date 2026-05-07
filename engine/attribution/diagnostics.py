from __future__ import annotations

import math
import os
from dataclasses import dataclass

from engine.contracts import ConfidenceLevel


DEFAULT_SHARE_STABILITY_THRESHOLD_BPS = 25.0


@dataclass(frozen=True)
class ShareDiagnostics:
    share_denominator_bps: float
    share_is_stable: bool
    share_stability_threshold_bps: float
    gross_contribution_leverage: float
    net_explained_leverage: float
    residual_leverage: float
    share_display_status: str

    def as_payload(self) -> dict[str, float | bool | str]:
        return {
            "share_denominator_bps": self.share_denominator_bps,
            "share_is_stable": self.share_is_stable,
            "share_stability_threshold_bps": self.share_stability_threshold_bps,
            "gross_contribution_leverage": self.gross_contribution_leverage,
            "net_explained_leverage": self.net_explained_leverage,
            "residual_leverage": self.residual_leverage,
            "share_display_status": self.share_display_status,
        }


def configured_share_stability_threshold_bps() -> float:
    raw = os.getenv("AAT_SHARE_STABILITY_THRESHOLD_BPS")
    if raw is None:
        return DEFAULT_SHARE_STABILITY_THRESHOLD_BPS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_SHARE_STABILITY_THRESHOLD_BPS
    return value if value > 0 else DEFAULT_SHARE_STABILITY_THRESHOLD_BPS


def is_share_stable(observed_return_bps: float, threshold_bps: float | None = None) -> bool:
    threshold = threshold_bps or configured_share_stability_threshold_bps()
    return abs(observed_return_bps) >= threshold


def safe_share_of_move(
    *,
    contribution_bps: float,
    observed_return_bps: float,
    threshold_bps: float | None = None,
) -> float | None:
    if observed_return_bps == 0 or not is_share_stable(observed_return_bps, threshold_bps):
        return None
    return contribution_bps / observed_return_bps


def legacy_share_of_move(*, contribution_bps: float, observed_return_bps: float) -> float | None:
    if observed_return_bps == 0:
        return None
    return contribution_bps / observed_return_bps


def build_share_diagnostics(
    *,
    observed_return_bps: float,
    non_residual_contribution_bps: list[float],
    residual_bps: float,
    threshold_bps: float | None = None,
) -> ShareDiagnostics:
    threshold = threshold_bps or configured_share_stability_threshold_bps()
    denominator = max(abs(observed_return_bps), threshold)
    explained_bps = sum(non_residual_contribution_bps)
    stable = is_share_stable(observed_return_bps, threshold)
    return ShareDiagnostics(
        share_denominator_bps=observed_return_bps,
        share_is_stable=stable,
        share_stability_threshold_bps=threshold,
        gross_contribution_leverage=sum(abs(value) for value in non_residual_contribution_bps) / denominator,
        net_explained_leverage=abs(explained_bps) / denominator,
        residual_leverage=abs(residual_bps) / denominator,
        share_display_status="stable" if stable else "unstable_small_observed_move",
    )


def residual_confidence(
    *,
    residual_bps: float,
    observed_return_bps: float,
    threshold_bps: float | None = None,
) -> ConfidenceLevel:
    threshold = threshold_bps or configured_share_stability_threshold_bps()
    denominator = max(abs(observed_return_bps), threshold)
    return ConfidenceLevel.LOW if abs(residual_bps) > denominator * 0.5 else ConfidenceLevel.MEDIUM


def finite_bps(value: float, *, max_abs_bps: float = 100_000.0) -> bool:
    return math.isfinite(value) and abs(value) <= max_abs_bps
