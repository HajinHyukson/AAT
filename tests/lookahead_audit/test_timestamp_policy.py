from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from db import models  # noqa: F401
from db.base import Base
from engine.contracts import DriverType, FactorContributionInput, PriceBar, TimeWindow
from engine.factors.baseline import build_factor_baseline_result
from engine.returns.accounting import close_to_close_return_bps


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_feature_like_tables_have_point_in_time_columns() -> None:
    feature_tables = [
        "price_bar",
        "factor_return",
        "factor_observation",
        "security_factor_exposure",
        "sector_classification_history",
        "peer_basket",
        "peer_basket_member",
        "macro_series",
        "event",
        "event_feature",
        "event_taxonomy",
        "event_surprise",
        "company_exposure",
    ]
    for table_name in feature_tables:
        columns = Base.metadata.tables[table_name].columns
        assert "event_time" in columns
        assert "ingestion_time" in columns
        assert "timestamp_available" in columns


def test_future_available_price_bar_is_not_used() -> None:
    security_id = uuid4()
    with pytest.raises(ValueError, match="at least two"):
        close_to_close_return_bps(
            security_id=security_id,
            window=TimeWindow(start=dt(1), end=dt(2)),
            attribution_cutoff=dt(2),
            bars=[
                PriceBar(
                    security_id=security_id,
                    event_time=dt(1),
                    ingestion_time=dt(1),
                    timestamp_available=dt(1),
                    close=100,
                    adjusted_close=100,
                ),
                PriceBar(
                    security_id=security_id,
                    event_time=dt(2),
                    ingestion_time=dt(2),
                    timestamp_available=dt(3),
                    close=110,
                    adjusted_close=110,
                ),
            ],
        )


def test_future_available_factor_input_is_not_used() -> None:
    security_id = uuid4()
    result = build_factor_baseline_result(
        security_id=security_id,
        window=TimeWindow(start=dt(1), end=dt(2)),
        attribution_cutoff=dt(2),
        observed_return_bps=100,
        factor_inputs=[
            FactorContributionInput(
                security_id=security_id,
                driver=DriverType.MARKET,
                name="Future factor",
                contribution_bps=99,
                event_time=dt(2),
                ingestion_time=dt(2),
                timestamp_available=dt(3),
            )
        ],
    )

    assert len(result.contributions) == 1
    assert result.contributions[0].driver == DriverType.UNEXPLAINED_RESIDUAL
    assert result.unexplained_residual_bps == 100
