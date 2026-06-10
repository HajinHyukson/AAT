from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from jobs import run_pilot_kospi_daily as daily
from jobs.pilot_kospi_common import PILOT_KOSPI_UNIVERSE_NAME


class _ImportReport:
    imported_counts = {"fact_price_daily": 948, "dim_stock": 0}


class _PromotionReport:
    bars_promoted = 948
    quarantined_bars = 3
    continuity_suspects = ["140910:2026-05-29"]


class _AttributionReport:
    ran_windows = 950
    skipped_windows = 2
    already_completed_windows = 1800


class _SummaryReport:
    refreshed = 948
    available = 940


@pytest.fixture
def chain_calls(monkeypatch, tmp_path):
    calls: list[tuple] = []
    config_path = tmp_path / "universe.json"
    config_path.write_text('{"version": "kospi_static_test_v0", "securities": []}', encoding="utf-8")

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://attribution:attribution@localhost:55432/aat_pilot_kospi",
    )
    monkeypatch.setattr(
        daily,
        "import_acquin_snapshot",
        lambda **kwargs: calls.append(("import", kwargs)) or _ImportReport(),
    )
    monkeypatch.setattr(
        daily,
        "promote_acquin_data",
        lambda **kwargs: calls.append(("promote", kwargs)) or _PromotionReport(),
    )
    monkeypatch.setattr(
        daily,
        "run_pilot_kospi_attribution",
        lambda **kwargs: calls.append(("attribution", kwargs)) or _AttributionReport(),
    )
    monkeypatch.setattr(
        daily,
        "refresh_attribution_summaries",
        lambda **kwargs: calls.append(("summaries", kwargs)) or _SummaryReport(),
    )

    class _FakeScope:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(daily, "session_scope", lambda **kwargs: _FakeScope())
    return calls, config_path


def test_daily_chain_runs_steps_in_order(chain_calls) -> None:
    calls, config_path = chain_calls
    report = daily.run_pilot_kospi_daily(config_path=Path(config_path), today=date(2026, 6, 10))

    assert [name for name, _ in calls] == ["import", "promote", "attribution", "summaries"]
    assert report.imported_rows == 948
    assert report.bars_promoted == 948
    assert report.continuity_suspects == ["140910:2026-05-29"]
    assert report.ran_windows == 950
    assert report.summaries_refreshed == 948
    assert report.summaries_available == 940


def test_daily_chain_attribution_window_and_universe(chain_calls) -> None:
    calls, config_path = chain_calls
    daily.run_pilot_kospi_daily(config_path=Path(config_path), today=date(2026, 6, 10))

    attribution_kwargs = next(kwargs for name, kwargs in calls if name == "attribution")
    assert attribution_kwargs["start"] == date(2026, 6, 10) - timedelta(days=daily.DEFAULT_ATTRIBUTION_DAYS)
    assert attribution_kwargs["end"] == date(2026, 6, 10)
    assert attribution_kwargs["cadences"] == ("daily", "weekly", "monthly")

    summary_kwargs = next(kwargs for name, kwargs in calls if name == "summaries")
    assert summary_kwargs["universe_name"] == PILOT_KOSPI_UNIVERSE_NAME
    assert summary_kwargs["universe_version"] == "kospi_static_test_v0"


def test_daily_chain_skip_import(chain_calls) -> None:
    calls, config_path = chain_calls
    report = daily.run_pilot_kospi_daily(
        config_path=Path(config_path),
        today=date(2026, 6, 10),
        skip_import=True,
    )
    assert [name for name, _ in calls] == ["promote", "attribution", "summaries"]
    assert report.imported_rows == 0


def test_daily_chain_requires_pilot_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://attribution:attribution@localhost:55432/attribution",
    )
    with pytest.raises(RuntimeError, match="aat_pilot_kospi"):
        daily.run_pilot_kospi_daily(config_path=tmp_path / "missing.json")
