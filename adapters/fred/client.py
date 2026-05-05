from __future__ import annotations

import csv
import os
import time as time_module
from datetime import date, datetime, time, timezone
from decimal import Decimal
from io import StringIO
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel


FRED_SERIES = {
    "DGS2": "2Y Treasury yield",
    "DGS10": "10Y Treasury yield",
    "BAMLH0A0HYM2": "High-yield credit spread",
    "BAMLC0A0CM": "Investment-grade credit spread",
    "VIXCLS": "VIX close",
    "T5YIE": "5Y breakeven inflation",
}

_REQUEST_LOCK = Lock()
_LAST_REQUEST_AT = 0.0


class FredObservation(BaseModel):
    series_name: str
    event_time: datetime
    ingestion_time: datetime
    timestamp_available: datetime
    value: Decimal
    vintage: str | None = None
    source: str = "fred"


def fetch_fred_csv_observations(
    *,
    series_name: str,
    start: date,
    end: date,
    ingestion_time: datetime | None = None,
) -> list[FredObservation]:
    timestamp = ingestion_time or datetime.now(timezone.utc)
    query = urlencode({"id": series_name.upper()})
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?{query}"
    request = Request(url, headers={"User-Agent": "AAT FRED adapter"})
    timeout = float(os.getenv("FRED_TIMEOUT_SECONDS", "30"))
    attempts = int(os.getenv("FRED_RETRY_ATTEMPTS", "4"))
    content = _read_with_retries(request=request, timeout=timeout, attempts=attempts)
    return parse_fred_csv_observations(
        content,
        series_name=series_name.upper(),
        start=start,
        end=end,
        ingestion_time=timestamp,
    )


def parse_fred_csv_observations(
    content: str,
    *,
    series_name: str,
    start: date,
    end: date,
    ingestion_time: datetime,
) -> list[FredObservation]:
    reader = csv.DictReader(StringIO(content))
    observations: list[FredObservation] = []
    for row in reader:
        raw_date = row.get("observation_date") or row.get("DATE")
        raw_value = row.get(series_name) or row.get("VALUE")
        if not raw_date or raw_value in {None, "", "."}:
            continue
        event_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        if event_date < start or event_date > end:
            continue
        observations.append(
            FredObservation(
                series_name=series_name,
                event_time=datetime.combine(event_date, time.min, tzinfo=timezone.utc),
                ingestion_time=ingestion_time,
                timestamp_available=ingestion_time,
                value=Decimal(str(raw_value)),
                vintage=None,
            )
        )
    observations.sort(key=lambda item: item.event_time)
    return observations


def _read_with_retries(*, request: Request, timeout: float, attempts: int) -> str:
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        _respect_fred_rate_limit()
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time_module.sleep(2.0 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("FRED request failed without an exception")


def _respect_fred_rate_limit() -> None:
    global _LAST_REQUEST_AT
    min_interval = float(os.getenv("FRED_MIN_REQUEST_INTERVAL_SECONDS", "0.55"))
    with _REQUEST_LOCK:
        now = time_module.monotonic()
        wait_seconds = min_interval - (now - _LAST_REQUEST_AT)
        if wait_seconds > 0:
            time_module.sleep(wait_seconds)
        _LAST_REQUEST_AT = time_module.monotonic()
