from __future__ import annotations

from engine.contracts import AttributionContribution, DriverType, FactorContributionInput


DRIVER_ORDER = {
    DriverType.MARKET: 0,
    DriverType.SECTOR: 1,
    DriverType.PEER: 2,
    DriverType.STYLE: 3,
    DriverType.MACRO: 4,
    DriverType.POSITIONING: 5,
    DriverType.EVENT: 6,
    DriverType.UNEXPLAINED_RESIDUAL: 99,
}


def sort_factor_inputs(inputs: list[FactorContributionInput]) -> list[FactorContributionInput]:
    return sorted(inputs, key=lambda item: (DRIVER_ORDER[item.driver], item.name))


def sort_contributions(contributions: list[AttributionContribution]) -> list[AttributionContribution]:
    return sorted(contributions, key=lambda item: (DRIVER_ORDER[item.driver], item.name))


def assert_systematic_before_events(inputs: list[FactorContributionInput]) -> None:
    seen_event = False
    for item in inputs:
        if item.driver == DriverType.EVENT:
            seen_event = True
        elif seen_event and DRIVER_ORDER[item.driver] < DRIVER_ORDER[DriverType.EVENT]:
            raise ValueError("systematic factor inputs must be ordered before event inputs")
