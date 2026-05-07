from __future__ import annotations

from jobs.run_attribution import (
    HIERARCHICAL_BASELINE_MODEL_VERSION,
    HIERARCHICAL_FACTOR_BASKET_VERSION,
    RESIDUAL_SAFETY_FACTOR_BASKET_VERSION,
    RESIDUAL_SAFETY_MODEL_VERSION,
)
from jobs.run_pilot_sp500_attribution import (
    PilotAttributionReport,
    factor_basket_version_for_methodology,
    model_version_for_methodology,
)


def test_pilot_attribution_report_includes_completed_resume_count() -> None:
    report = PilotAttributionReport(
        methodology="residual_safety_v1",
        tickers=503,
        expected_windows=20_525,
        already_completed_windows=877,
        ran_windows=100,
    )

    rendered = report.render()

    assert "expected_windows=20525" in rendered
    assert "already_completed_windows=877" in rendered
    assert "ran_windows=100" in rendered


def test_pilot_methodology_versions_match_persisted_run_keys() -> None:
    assert model_version_for_methodology("legacy") == "factor-baseline-v0"
    assert factor_basket_version_for_methodology("legacy") == "mvp_expanded_v0"

    assert model_version_for_methodology("residual_safety_v1") == RESIDUAL_SAFETY_MODEL_VERSION
    assert factor_basket_version_for_methodology("residual_safety_v1") == RESIDUAL_SAFETY_FACTOR_BASKET_VERSION

    assert model_version_for_methodology("hierarchical_market_first_v1") == HIERARCHICAL_BASELINE_MODEL_VERSION
    assert factor_basket_version_for_methodology("hierarchical_market_first_v1") == HIERARCHICAL_FACTOR_BASKET_VERSION
