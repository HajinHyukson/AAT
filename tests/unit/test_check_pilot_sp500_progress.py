from __future__ import annotations

from datetime import date

from jobs.check_pilot_sp500_progress import (
    CadenceProgress,
    DataProgress,
    MethodologyProgress,
    PilotProgressReport,
    progress_percent,
)
from jobs.pilot_sp500_common import PILOT_DATABASE_NAME, PILOT_UNIVERSE_NAME


def test_progress_percent_handles_missing_or_empty_expected() -> None:
    assert progress_percent(runs=10, expected=None) is None
    assert progress_percent(runs=10, expected=0) is None
    assert progress_percent(runs=25, expected=100) == 25.0
    assert progress_percent(runs=125, expected=100) == 100.0


def test_pilot_progress_report_render_includes_population_and_attribution_state() -> None:
    report = PilotProgressReport(
        database_name=PILOT_DATABASE_NAME,
        universe_name=PILOT_UNIVERSE_NAME,
        universe_version="sp500_static_test",
        analysis_start=date(2025, 1, 1),
        analysis_end=date(2026, 5, 6),
        data=DataProgress(
            config_tickers=503,
            universe_members=503,
            eligible_members=500,
            missing_price_members=3,
            priced_members=500,
            price_bar_rows=250_000,
            latest_price_time=None,
            factor_return_rows=5_000,
            macro_series_rows=1_000,
            peer_baskets=503,
            peer_members=10_000,
            events=0,
            event_features=0,
        ),
        attribution=[
            MethodologyProgress(
                methodology="residual_safety_v1",
                model_version="factor-baseline-residual-safety-v1",
                cadences=[
                    CadenceProgress(
                        cadence="daily",
                        runs=250,
                        tickers_with_runs=25,
                        expected_windows=1_000,
                        remaining_windows=750,
                        percent_complete=25.0,
                        latest_created_at=None,
                    )
                ],
            )
        ],
    )

    rendered = report.render()

    assert "members=503/503" in rendered
    assert "daily: runs=250/1000" in rendered
    assert "pct=25.0%" in rendered
