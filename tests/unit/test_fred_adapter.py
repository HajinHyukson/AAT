from __future__ import annotations

import adapters.fred.client as fred_client


def test_fred_rate_limit_default_stays_under_120_requests_per_minute(monkeypatch) -> None:
    monkeypatch.delenv("FRED_MIN_REQUEST_INTERVAL_SECONDS", raising=False)

    intervals_per_minute = 60 / float("0.55")

    assert intervals_per_minute < 120


def test_fred_read_retries_after_transient_failure(monkeypatch) -> None:
    calls = {"count": 0}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b"observation_date,DGS10\n2026-01-01,4.00\n"

    def fake_urlopen(_request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("transient")
        return Response()

    monkeypatch.setattr(fred_client, "urlopen", fake_urlopen)
    monkeypatch.setattr(fred_client, "_respect_fred_rate_limit", lambda: None)
    monkeypatch.setattr(fred_client.time_module, "sleep", lambda _seconds: None)

    content = fred_client._read_with_retries(request=object(), timeout=1, attempts=2)

    assert "DGS10" in content
    assert calls["count"] == 2


def test_fred_default_retry_attempts_are_patient_for_backfills(monkeypatch) -> None:
    monkeypatch.delenv("FRED_RETRY_ATTEMPTS", raising=False)
    observed = {}

    def fake_read(*, request, timeout, attempts):
        observed["attempts"] = attempts
        return "observation_date,DGS2\n2026-01-01,4.00\n"

    monkeypatch.setattr(fred_client, "_read_with_retries", fake_read)

    records = fred_client.fetch_fred_csv_observations(
        series_name="DGS2",
        start=__import__("datetime").date(2026, 1, 1),
        end=__import__("datetime").date(2026, 1, 1),
    )

    assert observed["attempts"] == 4
    assert len(records) == 1
