from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest

from jobs.pilot_kospi_common import (
    ACQUIN_BULK_BACKFILL_BOUNDARY,
    PILOT_KOSPI_DATABASE_NAME,
    acquin_vintage_stamps,
    apply_continuity_guard,
    assert_pilot_kospi_database_url,
    build_kospi_universe_payload,
    continuity_issue_key,
    ensure_pilot_kospi_database_url,
    normalize_kospi_ticker,
    pilot_kospi_database_url,
    placeholder_company_name,
)


@dataclass
class FakePriceRow:
    price_date: date
    adj_close: float


@dataclass
class FakeStockRow:
    ticker: str
    market: str
    is_preferred: bool
    is_active: bool


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)


def test_ticker_normalization_keeps_opaque_krx_codes() -> None:
    assert normalize_kospi_ticker(" 005930 ") == "005930"
    assert normalize_kospi_ticker("33637l") == "33637L"


def test_vintage_backfilled_rows_get_next_day_availability() -> None:
    stamps = acquin_vintage_stamps(
        trade_date=date(2024, 3, 15),
        source_created_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        fallback_ingestion_time=NOW,
    )

    assert stamps.event_time == datetime(2024, 3, 15, 6, 30, tzinfo=timezone.utc)
    assert stamps.timestamp_available == datetime(2024, 3, 16, tzinfo=timezone.utc)


def test_vintage_missing_created_at_is_treated_as_backfilled() -> None:
    stamps = acquin_vintage_stamps(
        trade_date=date(2024, 3, 15),
        source_created_at=None,
        fallback_ingestion_time=NOW,
    )

    assert stamps.ingestion_time == NOW
    assert stamps.timestamp_available == datetime(2024, 3, 16, tzinfo=timezone.utc)


def test_vintage_live_rows_use_real_created_at() -> None:
    created = datetime(2026, 6, 9, 7, 22, tzinfo=timezone.utc)
    stamps = acquin_vintage_stamps(
        trade_date=date(2026, 6, 9),
        source_created_at=created,
        fallback_ingestion_time=NOW,
    )

    assert created >= ACQUIN_BULK_BACKFILL_BOUNDARY
    assert stamps.timestamp_available == created
    assert stamps.ingestion_time == created


def test_vintage_live_rows_never_precede_market_close() -> None:
    created = datetime(2026, 6, 9, 5, 0, tzinfo=timezone.utc)
    stamps = acquin_vintage_stamps(
        trade_date=date(2026, 6, 9),
        source_created_at=created,
        fallback_ingestion_time=NOW,
    )

    assert stamps.timestamp_available == stamps.event_time


def test_continuity_guard_quarantines_from_first_suspect() -> None:
    rows = [
        FakePriceRow(date(2026, 6, 1), 10_000.0),
        FakePriceRow(date(2026, 6, 2), 10_300.0),
        FakePriceRow(date(2026, 6, 3), 3_500.0),
        FakePriceRow(date(2026, 6, 4), 3_550.0),
    ]

    verdict = apply_continuity_guard(ticker="204210", rows=rows, resolved_keys=set())

    assert verdict.suspect_key == "204210:2026-06-03"
    assert verdict.suspect_return == pytest.approx(3_500.0 / 10_300.0 - 1.0)
    assert [row.price_date for row in verdict.promotable] == [date(2026, 6, 1), date(2026, 6, 2)]
    assert verdict.quarantined_count == 2


def test_continuity_guard_passes_resolved_suspects() -> None:
    rows = [
        FakePriceRow(date(2026, 6, 1), 10_000.0),
        FakePriceRow(date(2026, 6, 2), 3_500.0),
        FakePriceRow(date(2026, 6, 3), 3_550.0),
    ]
    resolved = {continuity_issue_key(ticker="204210", trade_date=date(2026, 6, 2))}

    verdict = apply_continuity_guard(ticker="204210", rows=rows, resolved_keys=resolved)

    assert verdict.suspect_key is None
    assert len(verdict.promotable) == 3


def test_continuity_guard_allows_krx_limit_moves() -> None:
    rows = [
        FakePriceRow(date(2026, 6, 1), 10_000.0),
        FakePriceRow(date(2026, 6, 2), 13_000.0),
        FakePriceRow(date(2026, 6, 3), 9_100.0),
    ]

    verdict = apply_continuity_guard(ticker="005930", rows=rows, resolved_keys=set())

    assert verdict.suspect_key is None
    assert len(verdict.promotable) == 3


def test_universe_payload_excludes_inactive_and_sorts_tickers() -> None:
    stocks = [
        FakeStockRow("005935", "KOSPI", True, True),
        FakeStockRow("005930", "KOSPI", False, True),
        FakeStockRow("999999", "KOSPI", False, False),
    ]

    payload = build_kospi_universe_payload(
        stocks=stocks,
        retrieved_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert payload["version"] == "kospi_static_2026_06_09_v0"
    assert payload["universe_name"] == "pilot_kospi_static"
    assert [item["ticker"] for item in payload["securities"]] == ["005930", "005935"]
    assert payload["securities"][1]["is_preferred"] is True


def test_placeholder_names_are_marked_for_phase_2() -> None:
    assert placeholder_company_name("005930") == "KOSPI 005930 (placeholder)"


def test_kospi_database_url_guard_rejects_other_databases(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution",
    )

    with pytest.raises(RuntimeError, match=PILOT_KOSPI_DATABASE_NAME):
        assert_pilot_kospi_database_url()


def test_kospi_database_url_guard_rejects_sp500_pilot(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://attribution:attribution@localhost:55432/aat_pilot_sp500",
    )

    with pytest.raises(RuntimeError, match=PILOT_KOSPI_DATABASE_NAME):
        assert_pilot_kospi_database_url()


def test_ensure_kospi_database_url_defaults_to_local_pilot(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST_PORT", "55432")

    database_url = ensure_pilot_kospi_database_url()

    assert database_url == pilot_kospi_database_url()
    assert database_url.endswith(f"/{PILOT_KOSPI_DATABASE_NAME}")
