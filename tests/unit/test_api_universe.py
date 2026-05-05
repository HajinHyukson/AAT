from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import api.main as api_main
from db import models


def test_universe_endpoint_returns_available_and_missing_rows(monkeypatch) -> None:
    security_id = uuid4()
    company_id = uuid4()
    run_id = uuid4()

    rows = [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
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
    assert response.contributions[0].attribution_contribution_id == contribution_id
