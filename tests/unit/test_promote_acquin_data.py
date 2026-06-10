from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest

from jobs.promote_acquin_data import build_index_factor_values
from jobs.pilot_kospi_common import (
    KOSPI_MARKET_FACTOR_FAMILY,
    KOSPI_MARKET_FACTOR_NAME,
)


@dataclass
class FakeIndexRow:
    index_date: date
    close: float | None
    source_created_at: datetime | None


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
BACKFILL_CREATED = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)


def test_index_factor_values_skip_first_row_and_compute_bps() -> None:
    rows = [
        FakeIndexRow(date(2026, 6, 5), 2_000.0, BACKFILL_CREATED),
        FakeIndexRow(date(2026, 6, 8), 2_020.0, BACKFILL_CREATED),
        FakeIndexRow(date(2026, 6, 9), 2_010.0, BACKFILL_CREATED),
    ]

    values = build_index_factor_values(rows=rows, now=NOW)

    assert len(values) == 2
    assert values[0]["return_bps"] == pytest.approx((2_020.0 / 2_000.0 - 1.0) * 10_000.0)
    assert values[1]["return_bps"] == pytest.approx((2_010.0 / 2_020.0 - 1.0) * 10_000.0)
    assert values[0]["factor_name"] == KOSPI_MARKET_FACTOR_NAME
    assert values[0]["factor_family"] == KOSPI_MARKET_FACTOR_FAMILY


def test_index_factor_values_skip_invalid_closes_without_breaking_chain() -> None:
    rows = [
        FakeIndexRow(date(2026, 6, 5), 2_000.0, BACKFILL_CREATED),
        FakeIndexRow(date(2026, 6, 8), None, BACKFILL_CREATED),
        FakeIndexRow(date(2026, 6, 9), 2_100.0, BACKFILL_CREATED),
    ]

    values = build_index_factor_values(rows=rows, now=NOW)

    assert len(values) == 1
    assert values[0]["return_bps"] == pytest.approx((2_100.0 / 2_000.0 - 1.0) * 10_000.0)


def test_index_factor_values_apply_vintage_policy() -> None:
    rows = [
        FakeIndexRow(date(2024, 3, 14), 2_000.0, BACKFILL_CREATED),
        FakeIndexRow(date(2024, 3, 15), 2_050.0, BACKFILL_CREATED),
    ]

    values = build_index_factor_values(rows=rows, now=NOW)

    assert values[0]["event_time"] == datetime(2024, 3, 15, 6, 30, tzinfo=timezone.utc)
    # Backfilled rows are not available before the next day.
    assert values[0]["timestamp_available"] == datetime(2024, 3, 16, tzinfo=timezone.utc)


def test_index_factor_values_empty_input() -> None:
    assert build_index_factor_values(rows=[], now=NOW) == []
