from __future__ import annotations

from engine.contracts import AttributionContribution, AttributionResult, DriverType


def build_deterministic_narrative(result: AttributionResult) -> str:
    production = [
        item
        for item in result.contributions
        if item.driver != DriverType.UNEXPLAINED_RESIDUAL and abs(item.contribution_bps) > 0
    ]
    production.sort(key=lambda item: abs(item.contribution_bps), reverse=True)
    residual_share = (
        abs(result.unexplained_residual_bps) / abs(result.observed_return_bps)
        if result.observed_return_bps
        else 0.0
    )
    sentences: list[str] = [
        f"Observed move was {result.observed_return_bps:.1f} bps over the selected window."
    ]
    if production:
        top = production[:3]
        sentences.append(
            "Largest modeled drivers were "
            + ", ".join(f"{item.name} ({item.contribution_bps:.1f} bps)" for item in top)
            + "."
        )
    else:
        sentences.append("No production factor rows were available, so the move remains residual-driven.")
    residual_label = "large" if residual_share > 0.5 else "contained"
    sentences.append(
        f"Unexplained residual was {result.unexplained_residual_bps:.1f} bps, which is {residual_label} relative to the move."
    )
    event_evidence = _event_evidence_count(result.contributions)
    if event_evidence:
        sentences.append(f"{event_evidence} visible event evidence row(s) were attached but not assigned causal contribution.")
    return " ".join(sentences[:4])


def _event_evidence_count(contributions: list[AttributionContribution]) -> int:
    return sum(1 for item in contributions if item.driver == DriverType.EVENT)
