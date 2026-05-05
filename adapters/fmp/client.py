from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from config.env import get_required_env, load_dotenv


class FmpHistoricalPriceBar(BaseModel):
    ticker: str
    event_time: datetime
    ingestion_time: datetime
    timestamp_available: datetime
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal = Field(gt=0)
    adjusted_close: Decimal = Field(gt=0)
    volume: int | None = None
    source: str = "fmp"
    currency: str = "USD"


def fetch_historical_prices(
    *,
    ticker: str,
    start: date,
    end: date,
    ingestion_time: datetime | None = None,
) -> list[FmpHistoricalPriceBar]:
    load_dotenv()
    api_key = get_required_env("FMP_API_KEY")
    base_url = _stable_base_url(os.getenv("FMP_BASE_URL", "https://financialmodelingprep.com/stable"))
    timeout = int(os.getenv("FMP_TIMEOUT_SECONDS", "30"))

    query = urlencode(
        {
            "symbol": ticker.upper(),
            "from": start.isoformat(),
            "to": end.isoformat(),
            "apikey": api_key,
        }
    )
    url = f"{base_url}/historical-price-eod/full?{query}"
    request = Request(url, headers={"User-Agent": "AAT FMP adapter"})

    with urlopen(request, timeout=timeout) as response:
        content = response.read().decode("utf-8")

    import json

    payload = json.loads(content)
    return parse_historical_prices(
        payload,
        ticker=ticker,
        ingestion_time=ingestion_time or datetime.now(timezone.utc),
    )


def parse_historical_prices(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    ticker: str,
    ingestion_time: datetime,
) -> list[FmpHistoricalPriceBar]:
    rows = payload if isinstance(payload, list) else payload.get("historical")
    if not isinstance(rows, list):
        raise ValueError("FMP historical price response did not contain a historical list")

    bars = [
        _parse_price_row(row, ticker=ticker.upper(), ingestion_time=ingestion_time)
        for row in rows
        if isinstance(row, dict)
    ]
    bars.sort(key=lambda bar: bar.event_time)
    return bars


def _parse_price_row(
    row: dict[str, Any],
    *,
    ticker: str,
    ingestion_time: datetime,
) -> FmpHistoricalPriceBar:
    event_date = datetime.strptime(str(row["date"]), "%Y-%m-%d").date()
    event_time = datetime.combine(event_date, time.min, tzinfo=timezone.utc)

    return FmpHistoricalPriceBar(
        ticker=ticker,
        event_time=event_time,
        ingestion_time=ingestion_time,
        timestamp_available=ingestion_time,
        open=_optional_decimal(row.get("open")),
        high=_optional_decimal(row.get("high")),
        low=_optional_decimal(row.get("low")),
        close=Decimal(str(row["close"])),
        adjusted_close=Decimal(str(row.get("adjClose", row["close"]))),
        volume=int(row["volume"]) if row.get("volume") is not None else None,
    )


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _stable_base_url(configured_base_url: str) -> str:
    base_url = configured_base_url.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.path.rstrip("/") == "/api":
        return f"{parsed.scheme}://{parsed.netloc}/stable"
    return base_url
