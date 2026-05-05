from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

import api.main as api_main
from api.schemas import AnalystFeedbackRequest
from db import models


def test_feedback_rejects_missing_driver_without_name() -> None:
    with pytest.raises(HTTPException) as exc:
        api_main.create_analyst_feedback(
            AnalystFeedbackRequest(
                attribution_run_id=uuid4(),
                feedback="missing_driver",
            )
        )

    assert exc.value.status_code == 422


def test_feedback_rejects_unknown_feedback_value() -> None:
    with pytest.raises(HTTPException) as exc:
        api_main.create_analyst_feedback(
            AnalystFeedbackRequest(
                attribution_run_id=uuid4(),
                feedback="maybe",
            )
        )

    assert exc.value.status_code == 422


def test_feedback_accepts_missing_driver_with_name(monkeypatch) -> None:
    run_id = uuid4()

    class Result:
        def scalar_one_or_none(self):
            return models.AttributionRun(
                attribution_run_id=run_id,
                security_id=uuid4(),
                window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                window_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
                attribution_cutoff=datetime(2026, 1, 3, tzinfo=timezone.utc),
                observed_return_bps=100,
                unexplained_residual_bps=0,
                model_version="test",
                data_version="test",
                factor_basket_version="test",
                created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            )

    class Session:
        def execute(self, _statement):
            return Result()

        def add(self, item):
            self.item = item

        def flush(self):
            return None

    @contextmanager
    def fake_session_scope(**_kwargs):
        yield Session()

    monkeypatch.setattr(api_main, "session_scope", fake_session_scope)

    response = api_main.create_analyst_feedback(
        AnalystFeedbackRequest(
            attribution_run_id=run_id,
            feedback="missing_driver",
            missing_driver_name="FX translation",
        )
    )

    assert response.feedback == "missing_driver"
    assert response.missing_driver_name == "FX translation"
