from __future__ import annotations

from datetime import date, datetime, timezone

from engine.contracts import ContributionStage, DriverType, TimeWindow
from engine.factors.baseline import build_factor_baseline_result
from jobs.acquin_flow_evidence import (
    _domestic_flow_input,
    _foreign_flow_input,
    _foreign_ownership_input,
    _streak_days,
)


import uuid

SECURITY_ID = uuid.uuid4()
WINDOW = TimeWindow(
    start=datetime(2026, 6, 5, 6, 30, tzinfo=timezone.utc),
    end=datetime(2026, 6, 9, 6, 30, tzinfo=timezone.utc),
)
AVAILABLE = datetime(2026, 6, 9, 7, 22, tzinfo=timezone.utc)


def flow_row(day: date, group: str, amount: float) -> dict:
    return {
        "flow_date": day,
        "investor_group": group,
        "net_buy_amount": amount,
        "timestamp_available": AVAILABLE,
    }


def test_streak_counts_consecutive_same_sign_days() -> None:
    rows = [
        flow_row(date(2026, 6, 9), "foreign", 100.0),
        flow_row(date(2026, 6, 8), "foreign", 50.0),
        flow_row(date(2026, 6, 5), "foreign", -10.0),
    ]

    assert _streak_days(rows) == 2


def test_streak_is_negative_for_selling() -> None:
    rows = [
        flow_row(date(2026, 6, 9), "foreign", -100.0),
        flow_row(date(2026, 6, 8), "foreign", -50.0),
    ]

    assert _streak_days(rows) == -2


def test_foreign_flow_input_is_evidence_only() -> None:
    rows = [
        flow_row(date(2026, 6, 9), "foreign", 200.0),
        flow_row(date(2026, 6, 8), "foreign", 100.0),
        flow_row(date(2026, 6, 5), "foreign", -300.0),
    ]

    item = _foreign_flow_input(
        security_id=SECURITY_ID,
        flow_rows=rows,
        window_start_date=WINDOW.start.date(),
        window_end_date=WINDOW.end.date(),
        window=WINDOW,
    )

    assert item is not None
    assert item.driver == DriverType.POSITIONING
    assert item.contribution_bps == 0.0
    assert item.contribution_stage == ContributionStage.EVIDENCE_ONLY
    assert item.event_time == WINDOW.end
    # 6/5 is the window-start date and is excluded from the window sum.
    assert item.evidence_payload["window_net_buy_amount_krw"] == 300.0
    assert item.evidence_payload["net_buy_streak_days"] == 2


def test_domestic_flow_input_splits_institution_and_retail() -> None:
    rows = [
        flow_row(date(2026, 6, 9), "institution", 500.0),
        flow_row(date(2026, 6, 9), "retail", -200.0),
        flow_row(date(2026, 6, 8), "institution", 100.0),
    ]

    item = _domestic_flow_input(
        security_id=SECURITY_ID,
        flow_rows=rows,
        window_start_date=WINDOW.start.date(),
        window_end_date=WINDOW.end.date(),
        window=WINDOW,
    )

    assert item is not None
    assert item.evidence_payload["window_institution_net_buy_amount_krw"] == 600.0
    assert item.evidence_payload["window_retail_net_buy_amount_krw"] == -200.0


def test_foreign_ownership_input_reports_window_change() -> None:
    holding_rows = [
        {
            "holding_date": date(2026, 6, 9),
            "foreign_ownership_pct": 51.5,
            "foreign_limit_exhaustion_pct": 51.5,
            "timestamp_available": AVAILABLE,
        },
        {
            "holding_date": date(2026, 6, 5),
            "foreign_ownership_pct": 51.0,
            "foreign_limit_exhaustion_pct": 51.0,
            "timestamp_available": AVAILABLE,
        },
    ]

    item = _foreign_ownership_input(
        security_id=SECURITY_ID,
        holding_rows=holding_rows,
        window_start_date=WINDOW.start.date(),
        window=WINDOW,
    )

    assert item is not None
    assert item.evidence_payload["foreign_ownership_pct_change"] == 0.5


def test_evidence_only_inputs_do_not_reduce_residual() -> None:
    rows = [flow_row(date(2026, 6, 9), "foreign", 1_000_000.0)]
    evidence_input = _foreign_flow_input(
        security_id=SECURITY_ID,
        flow_rows=rows,
        window_start_date=WINDOW.start.date(),
        window_end_date=WINDOW.end.date(),
        window=WINDOW,
    )

    result = build_factor_baseline_result(
        security_id=SECURITY_ID,
        window=WINDOW,
        attribution_cutoff=datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc),
        observed_return_bps=150.0,
        factor_inputs=[evidence_input],
    )

    assert result.unexplained_residual_bps == 150.0
    names = [item.name for item in result.contributions]
    assert "Foreign investor flow (KRX)" in names
