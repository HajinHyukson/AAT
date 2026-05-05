from __future__ import annotations

import math
from dataclasses import dataclass

from engine.contracts import ExposureBucket, ExposureSign


@dataclass(frozen=True)
class ExposureGate:
    exposure_name: str
    gate_weight: float
    expected_sign: ExposureSign
    evidence_payload: dict


def bucket_to_gate(bucket: ExposureBucket | str | None) -> float:
    if bucket is None:
        return 0.0
    normalized = ExposureBucket(bucket)
    return {
        ExposureBucket.NONE: 0.0,
        ExposureBucket.LOW: 0.25,
        ExposureBucket.MEDIUM: 0.50,
        ExposureBucket.HIGH: 0.75,
        ExposureBucket.CRITICAL: 1.0,
    }[normalized]


def commodity_gate(
    *,
    commodity: str,
    producer_exposure_pct: float,
    consumer_input_pct: float,
    hedge_coverage_pct: float = 0.0,
    gate_threshold_pct: float = 0.20,
) -> ExposureGate:
    signed_exposure = (producer_exposure_pct - consumer_input_pct) * (1 - hedge_coverage_pct)
    gate_weight = _bounded(abs(signed_exposure) / gate_threshold_pct)
    return ExposureGate(
        exposure_name=f"commodity:{commodity}",
        gate_weight=gate_weight,
        expected_sign=_sign(signed_exposure),
        evidence_payload={
            "commodity": commodity,
            "producer_exposure_pct": producer_exposure_pct,
            "consumer_input_pct": consumer_input_pct,
            "hedge_coverage_pct": hedge_coverage_pct,
            "signed_exposure": signed_exposure,
        },
    )


def fx_gate(
    *,
    currency_basket: str,
    foreign_revenue_pct: float,
    foreign_cost_pct: float,
    hedge_coverage_pct: float = 0.0,
    gate_threshold_pct: float = 0.20,
) -> ExposureGate:
    net_fx_exposure = (foreign_revenue_pct - foreign_cost_pct) * (1 - hedge_coverage_pct)
    gate_weight = _bounded(abs(net_fx_exposure) / gate_threshold_pct)
    expected_usd_sign = ExposureSign.NEGATIVE if net_fx_exposure > 0 else _sign(-net_fx_exposure)
    return ExposureGate(
        exposure_name=f"fx:{currency_basket}",
        gate_weight=gate_weight,
        expected_sign=expected_usd_sign,
        evidence_payload={
            "currency_basket": currency_basket,
            "foreign_revenue_pct": foreign_revenue_pct,
            "foreign_cost_pct": foreign_cost_pct,
            "hedge_coverage_pct": hedge_coverage_pct,
            "net_fx_exposure": net_fx_exposure,
        },
    )


def rate_gate(
    *,
    floating_rate_debt_pct: float,
    net_debt_pct_market_cap: float,
    interest_expense_pct_ebit: float,
    duration_or_nii_sensitivity: float = 0.0,
    threshold: float = 1.0,
) -> ExposureGate:
    score = _average(
        [
            floating_rate_debt_pct,
            net_debt_pct_market_cap,
            interest_expense_pct_ebit,
            duration_or_nii_sensitivity,
        ]
    )
    return ExposureGate(
        exposure_name="interest_rate",
        gate_weight=_bounded(abs(score) / threshold),
        expected_sign=_sign(score),
        evidence_payload={
            "floating_rate_debt_pct": floating_rate_debt_pct,
            "net_debt_pct_market_cap": net_debt_pct_market_cap,
            "interest_expense_pct_ebit": interest_expense_pct_ebit,
            "duration_or_nii_sensitivity": duration_or_nii_sensitivity,
            "rate_exposure_score": score,
        },
    )


def credit_gate(
    *,
    net_debt_to_ebitda_z: float,
    interest_coverage_z: float,
    debt_maturity_wall_z: float,
    rating_score_z: float = 0.0,
) -> ExposureGate:
    score = _average(
        [
            net_debt_to_ebitda_z,
            -interest_coverage_z,
            debt_maturity_wall_z,
            -rating_score_z,
        ]
    )
    gate_weight = 1 / (1 + math.exp(-score))
    return ExposureGate(
        exposure_name="credit",
        gate_weight=gate_weight,
        expected_sign=ExposureSign.NEGATIVE,
        evidence_payload={
            "net_debt_to_ebitda_z": net_debt_to_ebitda_z,
            "interest_coverage_z": interest_coverage_z,
            "debt_maturity_wall_z": debt_maturity_wall_z,
            "rating_score_z": rating_score_z,
            "credit_exposure_score": score,
        },
    )


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _average(values: list[float]) -> float:
    return sum(values) / len(values)


def _sign(value: float) -> ExposureSign:
    if value > 0:
        return ExposureSign.POSITIVE
    if value < 0:
        return ExposureSign.NEGATIVE
    return ExposureSign.UNKNOWN
