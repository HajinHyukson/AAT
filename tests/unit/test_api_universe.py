from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import api.main as api_main
from db import models
from engine.contracts import TimeWindow


def test_universe_endpoint_returns_available_and_missing_rows(monkeypatch) -> None:
    security_id = uuid4()
    company_id = uuid4()
    run_id = uuid4()

    rows = [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "methodology": "residual_safety_v1",
            "security_id": security_id,
            "company_id": company_id,
            "exchange": "NASDAQ",
            "sector": "Information Technology",
            "industry": "Technology Hardware",
            "latest_run_id": run_id,
            "latest_window_end": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "latest_observed_return_bps": 123.4,
            "latest_residual_bps": 12.3,
            "latest_price_change_usd": 2.5,
            "top_driver": "market",
            "top_driver_confidence": "Medium",
            "contribution_count": 6,
            "evidence_count": 2,
        },
        {
            "ticker": "MSFT",
            "company_name": "Microsoft Corporation",
            "methodology": "residual_safety_v1",
            "security_id": uuid4(),
            "company_id": uuid4(),
            "exchange": "NASDAQ",
            "sector": "Information Technology",
            "industry": "Software",
            "latest_run_id": None,
            "latest_window_end": None,
            "latest_observed_return_bps": None,
            "latest_residual_bps": None,
            "latest_price_change_usd": None,
            "top_driver": None,
            "top_driver_confidence": None,
            "contribution_count": 0,
            "evidence_count": 0,
        },
    ]

    class CountResult:
        def scalar_one(self):
            return 2

    class LatestResult:
        def scalar_one_or_none(self):
            return datetime(2026, 5, 1, tzinfo=timezone.utc)

    class RowResult:
        def mappings(self):
            return self

        def all(self):
            return rows

    class Session:
        def __init__(self):
            self.calls = 0

        def execute(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return CountResult()
            if self.calls == 4:
                return LatestResult()
            return RowResult()

    @contextmanager
    def fake_session_scope(**_kwargs):
        yield Session()

    monkeypatch.setattr(api_main, "session_scope", fake_session_scope)

    response = api_main.universe(
        search="app",
        status=None,
        sort="ticker",
        order="asc",
        limit=50,
        offset=0,
    )

    assert response.total == 2
    assert response.rows[0].ticker == "AAPL"
    assert response.rows[0].run_status == "available"
    assert response.rows[0].has_evidence is True
    assert response.rows[0].latest_price_change_usd == 2.5
    assert round(response.rows[0].latest_residual_usd or 0, 4) == round(12.3 / 123.4 * 2.5, 4)
    assert response.rows[1].ticker == "MSFT"
    assert response.rows[1].run_status == "missing"
    assert response.rows[1].latest_price_change_usd is None
    assert response.rows[1].latest_residual_usd is None
    assert [option.ticker for option in response.company_options] == ["AAPL", "MSFT"]
    assert response.sector_options == ["Information Technology"]
    assert response.industry_options == ["Software", "Technology Hardware"]
    assert response.exchange_options == ["NASDAQ"]


def test_universe_statement_exposes_expected_sort_columns() -> None:
    _statement, sort_columns = api_main.build_universe_statement(
        search="apple",
        sector="Information Technology",
        industry="Software",
        exchange="NASDAQ",
        status="available",
    )

    assert {"ticker", "company", "sector", "latest_run", "move", "residual", "status"}.issubset(
        sort_columns
    )


def test_latest_residual_usd_returns_none_without_required_inputs() -> None:
    assert (
        api_main.latest_residual_usd(
            latest_residual_bps=12.3,
            latest_observed_return_bps=0,
            latest_price_change_usd=2.5,
        )
        is None
    )
    assert (
        api_main.latest_residual_usd(
            latest_residual_bps=12.3,
            latest_observed_return_bps=123.4,
            latest_price_change_usd=None,
        )
        is None
    )


def test_attribution_response_includes_cadence() -> None:
    run_id = uuid4()
    security_id = uuid4()
    contribution_id = uuid4()
    run = models.AttributionRun(
        attribution_run_id=run_id,
        security_id=security_id,
        window_start=datetime(2026, 1, 2, tzinfo=timezone.utc),
        window_end=datetime(2026, 1, 9, tzinfo=timezone.utc),
        attribution_cutoff=datetime(2026, 1, 10, tzinfo=timezone.utc),
        observed_return_bps=100,
        unexplained_residual_bps=100,
        methodology="legacy",
        model_version="factor-baseline-v0",
        data_version="local-dev",
        factor_basket_version="mvp_expanded_v0",
        cadence="weekly",
        created_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
    )
    contribution = models.AttributionContribution(
        attribution_contribution_id=contribution_id,
        attribution_run_id=run_id,
        driver="unexplained_residual",
        name="Unexplained residual",
        contribution_bps=100,
        share_of_move=1,
        confidence="Low",
        evidence=[],
        contribution_stage="production",
        evidence_payload={},
    )

    class ScalarResult:
        def scalars(self):
            return [contribution]

    class Session:
        def execute(self, _statement):
            return ScalarResult()

    response = api_main.build_attribution_response(session=Session(), run=run, ticker="AAPL")

    assert response.cadence == "weekly"
    assert response.methodology == "legacy"
    assert response.contributions[0].attribution_contribution_id == contribution_id


def test_ensure_latest_returns_fresh_methodology_run(monkeypatch) -> None:
    run_id = uuid4()
    security_id = uuid4()
    latest_price_time = datetime(2026, 5, 6, tzinfo=timezone.utc)
    security = models.Security(
        security_id=security_id,
        company_id=uuid4(),
        exchange="NASDAQ",
        active_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    run = models.AttributionRun(
        attribution_run_id=run_id,
        security_id=security_id,
        window_start=datetime(2026, 5, 5, tzinfo=timezone.utc),
        window_end=latest_price_time,
        attribution_cutoff=datetime(2026, 5, 7, tzinfo=timezone.utc),
        observed_return_bps=5,
        unexplained_residual_bps=5,
        methodology="residual_safety_v1",
        model_version="factor-baseline-residual-safety-v1",
        data_version="local-dev",
        factor_basket_version="mvp_expanded_residual_safety_v1",
        cadence="daily",
        created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )
    contribution = models.AttributionContribution(
        attribution_contribution_id=uuid4(),
        attribution_run_id=run_id,
        driver="unexplained_residual",
        name="Unexplained residual",
        contribution_bps=5,
        share_of_move=0.2,
        confidence="Low",
        evidence=[],
        contribution_stage="production",
        evidence_payload={},
    )

    class ScalarResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def scalars(self):
            return self

    class ContributionResult:
        def scalars(self):
            return [contribution]

    class Session:
        def __init__(self):
            self.calls = 0

        def execute(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return ScalarResult(security)
            if self.calls == 2:
                return ScalarResult(latest_price_time)
            if self.calls == 3:
                return ScalarResult(run)
            return ContributionResult()

    @contextmanager
    def fake_session_scope(**_kwargs):
        yield Session()

    monkeypatch.setattr(api_main, "session_scope", fake_session_scope)
    monkeypatch.setattr(api_main, "methodology_lookback_days", lambda **_kwargs: 252)
    monkeypatch.setattr(api_main, "target_start_for_range", lambda **_kwargs: run.window_start)
    monkeypatch.setattr(
        api_main,
        "load_trading_dates_for_range",
        lambda **_kwargs: [run.window_start, run.window_end],
    )
    monkeypatch.setattr(
        api_main,
        "candidate_windows_for_range",
        lambda **_kwargs: [TimeWindow(start=run.window_start, end=run.window_end)],
    )
    monkeypatch.setattr(api_main, "missing_windows_for_range", lambda **_kwargs: [])

    response = api_main.ensure_latest_attribution_run(
        ticker="AAPL",
        methodology="residual_safety_v1",
        cadence="daily",
        range_="1m",
    )

    assert response.status == "fresh"
    assert response.run is not None
    assert response.run.attribution_run_id == run_id
    assert response.run.methodology == "residual_safety_v1"


def test_ensure_latest_defaults_long_range_to_weekly(monkeypatch) -> None:
    security_id = uuid4()
    latest_price_time = datetime(2026, 5, 6, tzinfo=timezone.utc)
    target_start = datetime(2025, 5, 6, tzinfo=timezone.utc)
    missing_window = TimeWindow(
        start=datetime(2026, 4, 27, tzinfo=timezone.utc),
        end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    security = models.Security(
        security_id=security_id,
        company_id=uuid4(),
        exchange="NASDAQ",
        active_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    captured = {}

    @contextmanager
    def fake_session_scope(**_kwargs):
        yield object()

    def fake_candidate_windows(**kwargs):
        captured["candidate_cadence"] = kwargs["cadence"]
        return [missing_window]

    def fake_missing_windows(**kwargs):
        captured["missing_cadence"] = kwargs["cadence"]
        return [missing_window]

    def fake_enqueue(**kwargs):
        captured["enqueue_cadence"] = kwargs["cadence"]
        return SimpleNamespace(
            attribution_on_demand_job_id=uuid4(),
            status="queued",
            latest_existing_window_end=None,
            target_window_end=latest_price_time,
        )

    monkeypatch.setattr(api_main, "session_scope", fake_session_scope)
    monkeypatch.setattr(api_main, "find_security_or_404", lambda **_kwargs: security)
    monkeypatch.setattr(api_main, "latest_price_event_time", lambda **_kwargs: latest_price_time)
    monkeypatch.setattr(api_main, "latest_run_for_security", lambda **_kwargs: None)
    monkeypatch.setattr(api_main, "target_start_for_range", lambda **_kwargs: target_start)
    monkeypatch.setattr(api_main, "methodology_lookback_days", lambda **_kwargs: 252)
    monkeypatch.setattr(api_main, "load_trading_dates_for_range", lambda **_kwargs: [])
    monkeypatch.setattr(api_main, "candidate_windows_for_range", fake_candidate_windows)
    monkeypatch.setattr(api_main, "missing_windows_for_range", fake_missing_windows)
    monkeypatch.setattr(api_main, "enqueue_or_reuse_on_demand_job", fake_enqueue)

    response = api_main.ensure_latest_attribution_run(
        ticker="AAPL",
        methodology="residual_safety_v1",
        range_="1y",
    )

    assert response.status == "queued"
    assert captured == {
        "candidate_cadence": "weekly",
        "missing_cadence": "weekly",
        "enqueue_cadence": "weekly",
    }


def test_ensure_latest_queues_when_visible_range_has_missing_windows(monkeypatch) -> None:
    security_id = uuid4()
    latest_price_time = datetime(2026, 5, 6, tzinfo=timezone.utc)
    target_start = datetime(2026, 4, 6, tzinfo=timezone.utc)
    latest_window = TimeWindow(
        start=datetime(2026, 5, 5, tzinfo=timezone.utc),
        end=latest_price_time,
    )
    missing_window = TimeWindow(
        start=datetime(2026, 4, 13, tzinfo=timezone.utc),
        end=datetime(2026, 4, 14, tzinfo=timezone.utc),
    )
    security = models.Security(
        security_id=security_id,
        company_id=uuid4(),
        exchange="NASDAQ",
        active_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    run = models.AttributionRun(
        attribution_run_id=uuid4(),
        security_id=security_id,
        window_start=latest_window.start,
        window_end=latest_window.end,
        attribution_cutoff=datetime(2026, 5, 7, tzinfo=timezone.utc),
        observed_return_bps=5,
        unexplained_residual_bps=5,
        methodology="residual_safety_v1",
        model_version="factor-baseline-residual-safety-v1",
        data_version="local-dev",
        factor_basket_version="mvp_expanded_residual_safety_v1",
        cadence="daily",
        created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )
    captured = {}

    @contextmanager
    def fake_session_scope(**_kwargs):
        yield object()

    def fake_enqueue(**kwargs):
        captured["latest_existing_window_end"] = kwargs["latest_existing_window_end"]
        return SimpleNamespace(
            attribution_on_demand_job_id=uuid4(),
            status="queued",
            latest_existing_window_end=kwargs["latest_existing_window_end"],
            target_window_end=latest_price_time,
        )

    monkeypatch.setattr(api_main, "session_scope", fake_session_scope)
    monkeypatch.setattr(api_main, "find_security_or_404", lambda **_kwargs: security)
    monkeypatch.setattr(api_main, "latest_price_event_time", lambda **_kwargs: latest_price_time)
    monkeypatch.setattr(api_main, "latest_run_for_security", lambda **_kwargs: run)
    monkeypatch.setattr(api_main, "target_start_for_range", lambda **_kwargs: target_start)
    monkeypatch.setattr(api_main, "methodology_lookback_days", lambda **_kwargs: 252)
    monkeypatch.setattr(api_main, "load_trading_dates_for_range", lambda **_kwargs: [])
    monkeypatch.setattr(
        api_main,
        "candidate_windows_for_range",
        lambda **_kwargs: [missing_window, latest_window],
    )
    monkeypatch.setattr(api_main, "missing_windows_for_range", lambda **_kwargs: [missing_window])
    monkeypatch.setattr(api_main, "enqueue_or_reuse_on_demand_job", fake_enqueue)

    response = api_main.ensure_latest_attribution_run(
        ticker="AAPL",
        methodology="residual_safety_v1",
        cadence="daily",
        range_="1m",
    )

    assert response.status == "queued"
    assert response.run is None
    assert captured["latest_existing_window_end"] == latest_price_time
