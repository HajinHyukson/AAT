from __future__ import annotations

from datetime import date, datetime, timezone

from adapters.sec_edgar.client import normalize_cik, parse_submissions


def test_normalize_cik_zero_pads_digits() -> None:
    assert normalize_cik("320193") == "0000320193"


def test_parse_submissions_maps_recent_filings_with_acceptance_time() -> None:
    payload = {
        "name": "APPLE INC",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-26-000001"],
                "form": ["10-Q"],
                "filingDate": ["2026-01-30"],
                "reportDate": ["2025-12-27"],
                "acceptanceDateTime": ["2026-01-30T18:01:02.000Z"],
                "primaryDocument": ["aapl-20251227.htm"],
            }
        },
    }
    ingestion_time = datetime(2026, 1, 31, tzinfo=timezone.utc)

    filings = parse_submissions(payload, cik="320193", ingestion_time=ingestion_time)

    assert len(filings) == 1
    assert filings[0].company_name == "APPLE INC"
    assert filings[0].form == "10-Q"
    assert filings[0].report_date == date(2025, 12, 27)
    assert filings[0].timestamp_available == datetime(2026, 1, 30, 18, 1, 2, tzinfo=timezone.utc)
