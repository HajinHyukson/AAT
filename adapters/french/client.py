from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, time, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from pydantic import Field

from engine.contracts import TimeWindow, TimestampedRecord


FRENCH_DAILY_5_FACTOR_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
)


class FrenchFactorReturn(TimestampedRecord):
    factor_name: str
    factor_family: str = "fama_french_5"
    return_bps: float
    source: str = "kenneth_french"
    source_dataset: str = "F-F_Research_Data_5_Factors_2x3_daily_CSV"
    raw_percent_return: float = Field(description="Return as published by Kenneth French, in percent")


def download_daily_5_factor_zip(*, cache_dir: Path | None = None) -> bytes:
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
        if cache_file.exists():
            return cache_file.read_bytes()

    request = Request(FRENCH_DAILY_5_FACTOR_URL, headers={"User-Agent": "AAT research adapter"})
    with urlopen(request, timeout=30) as response:
        content = response.read()

    if cache_dir is not None:
        cache_file.write_bytes(content)
    return content


def parse_daily_5_factor_zip(
    content: bytes,
    *,
    window: TimeWindow,
    ingestion_time: datetime,
) -> list[FrenchFactorReturn]:
    csv_text = _read_first_csv_from_zip(content)
    return parse_daily_5_factor_csv(csv_text, window=window, ingestion_time=ingestion_time)


def parse_daily_5_factor_csv(
    csv_text: str,
    *,
    window: TimeWindow,
    ingestion_time: datetime,
) -> list[FrenchFactorReturn]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    header_index = _find_header_index(rows)
    headers = [value.strip() for value in rows[header_index]]
    factor_names = [value for value in headers[1:] if value]
    parsed: list[FrenchFactorReturn] = []

    for row in rows[header_index + 1 :]:
        if not row or not row[0].strip().isdigit():
            break

        event_time = _parse_french_date(row[0].strip())
        if not (window.start <= event_time <= window.end):
            continue

        for factor_name, raw_value in zip(factor_names, row[1:], strict=False):
            value = raw_value.strip()
            if not value or value in {"-99.99", "-999"}:
                continue
            raw_percent = float(value)
            parsed.append(
                FrenchFactorReturn(
                    factor_name=factor_name,
                    raw_percent_return=raw_percent,
                    return_bps=raw_percent * 100.0,
                    event_time=event_time,
                    ingestion_time=ingestion_time,
                    timestamp_available=ingestion_time,
                )
            )

    return parsed


def fetch_daily_5_factors(
    *,
    window: TimeWindow,
    ingestion_time: datetime | None = None,
    cache_dir: Path | None = None,
) -> list[FrenchFactorReturn]:
    effective_ingestion_time = ingestion_time or datetime.now(timezone.utc)
    content = download_daily_5_factor_zip(cache_dir=cache_dir)
    return parse_daily_5_factor_zip(
        content,
        window=window,
        ingestion_time=effective_ingestion_time,
    )


def _read_first_csv_from_zip(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("Kenneth French archive did not contain a CSV file")
        with archive.open(csv_names[0]) as handle:
            return handle.read().decode("utf-8-sig")


def _find_header_index(rows: list[list[str]]) -> int:
    for index, row in enumerate(rows):
        normalized = [value.strip() for value in row]
        if normalized and normalized[0] == "" and "Mkt-RF" in normalized:
            return index
    raise ValueError("could not find French factor CSV header")


def _parse_french_date(value: str) -> datetime:
    return datetime.combine(
        datetime.strptime(value, "%Y%m%d").date(),
        time.min,
        tzinfo=timezone.utc,
    )
