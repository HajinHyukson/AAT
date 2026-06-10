from __future__ import annotations

import pytest

from jobs.run_attribution import RESIDUAL_SAFETY_MODEL_VERSION
from jobs.run_pilot_kospi_attribution import (
    VALID_KOSPI_METHODOLOGIES,
    model_version_for_methodology,
    run_pilot_kospi_attribution,
    top_counts,
)


def test_model_version_per_methodology() -> None:
    assert model_version_for_methodology("legacy") == "factor-baseline-v0"
    assert model_version_for_methodology("residual_safety_v1") == RESIDUAL_SAFETY_MODEL_VERSION


def test_hierarchical_methodology_is_not_valid_for_market_only_pilot() -> None:
    assert "hierarchical_market_first_v1" not in VALID_KOSPI_METHODOLOGIES
    with pytest.raises(ValueError, match="unsupported"):
        model_version_for_methodology("hierarchical_market_first_v1")


def test_runner_rejects_unsupported_methodology(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://attribution:attribution@localhost:55432/aat_pilot_kospi",
    )
    from datetime import date

    with pytest.raises(ValueError, match="unsupported KOSPI pilot methodology"):
        run_pilot_kospi_attribution(
            tickers=["005930"],
            start=date(2026, 1, 2),
            end=date(2026, 1, 9),
            methodology="hierarchical_market_first_v1",
        )


def test_runner_guards_against_non_pilot_database(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution",
    )
    from datetime import date

    with pytest.raises(RuntimeError, match="aat_pilot_kospi"):
        run_pilot_kospi_attribution(
            tickers=["005930"],
            start=date(2026, 1, 2),
            end=date(2026, 1, 9),
        )


def test_top_counts_orders_by_frequency_then_name() -> None:
    values = ["b", "a", "b", "c", "a", "b"]

    assert top_counts(values, limit=2) == [("b", 3), ("a", 2)]
