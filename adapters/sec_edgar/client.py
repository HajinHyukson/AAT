from __future__ import annotations

import json
import gzip
import zlib
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.request import Request, urlopen

from pydantic import BaseModel

from config.env import get_required_env, load_dotenv


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


class EdgarFiling(BaseModel):
    cik: str
    company_name: str
    form: str
    accession_number: str
    filing_date: date
    report_date: date | None
    primary_document: str | None
    event_time: datetime
    ingestion_time: datetime
    timestamp_available: datetime
    source: str = "sec_edgar"


def fetch_submissions(
    *,
    cik: str,
    ingestion_time: datetime | None = None,
) -> list[EdgarFiling]:
    load_dotenv()
    user_agent = get_required_env("EDGAR_USER_AGENT")
    normalized_cik = normalize_cik(cik)
    request = Request(
        SEC_SUBMISSIONS_URL.format(cik=normalized_cik),
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
    )
    with urlopen(request, timeout=30) as response:
        content = _decode_response(response.read(), response.headers.get("Content-Encoding"))
        payload = json.loads(content)
    return parse_submissions(
        payload,
        cik=normalized_cik,
        ingestion_time=ingestion_time or datetime.now(timezone.utc),
    )


def parse_submissions(
    payload: dict[str, Any],
    *,
    cik: str,
    ingestion_time: datetime,
) -> list[EdgarFiling]:
    company_name = str(payload.get("name") or "")
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    acceptance_datetimes = recent.get("acceptanceDateTime", [])
    primary_documents = recent.get("primaryDocument", [])

    filings: list[EdgarFiling] = []
    for index, form in enumerate(forms):
        filing_date = _parse_date(_get(filing_dates, index))
        accepted_at = _parse_acceptance_datetime(_get(acceptance_datetimes, index))
        event_time = accepted_at or datetime.combine(filing_date, time.min, tzinfo=timezone.utc)
        filings.append(
            EdgarFiling(
                cik=normalize_cik(cik),
                company_name=company_name,
                form=str(form),
                accession_number=str(_get(accession_numbers, index)),
                filing_date=filing_date,
                report_date=_parse_optional_date(_get(report_dates, index)),
                primary_document=_empty_to_none(_get(primary_documents, index)),
                event_time=event_time,
                ingestion_time=ingestion_time,
                timestamp_available=accepted_at or ingestion_time,
            )
        )
    return filings


def normalize_cik(cik: str | int) -> str:
    digits = "".join(ch for ch in str(cik) if ch.isdigit())
    if not digits:
        raise ValueError("CIK must contain digits")
    return digits.zfill(10)


def _get(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def _parse_date(value: Any) -> date:
    return date.fromisoformat(str(value))


def _parse_optional_date(value: Any) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value))


def _parse_acceptance_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if "T" not in text:
        return None
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def _empty_to_none(value: Any) -> str | None:
    if not value:
        return None
    return str(value)


def _decode_response(content: bytes, encoding: str | None) -> str:
    normalized = (encoding or "").lower()
    if normalized == "gzip":
        content = gzip.decompress(content)
    elif normalized == "deflate":
        content = zlib.decompress(content)
    return content.decode("utf-8")
