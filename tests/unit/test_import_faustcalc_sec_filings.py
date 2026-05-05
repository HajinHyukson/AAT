from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from jobs.import_faustcalc_sec_filings import (
    build_sec_filing_value,
    parse_sec_filename,
    read_sec_candidate,
    scan_sec_filings,
)


def test_parse_sec_filename_normalizes_accession_and_ticker_alias() -> None:
    parsed = parse_sec_filename(Path("BRK-B-0001067983-25-000001.jsonl"))

    assert parsed.source_ticker == "BRK-B"
    assert parsed.canonical_ticker == "BRK.B"
    assert parsed.accession_number == "0001067983-25-000001"


def test_read_sec_candidate_cleans_text_and_omits_db_payload_body(tmp_path) -> None:
    accession = "0000320193-26-000001"
    path = _write_sec_file(tmp_path, ticker="AAPL", accession=accession, text="Line 1\r\nLine 2\x00")

    candidate = read_sec_candidate(
        path=path,
        clean_output_root=tmp_path / "clean",
        write_cleaned=True,
    )
    value = build_sec_filing_value(import_run_id=uuid4(), candidate=candidate)

    assert candidate.text_length == len("Line 1\nLine 2")
    assert candidate.cleaned_text_path is not None
    assert candidate.cleaned_text_path.read_text(encoding="utf-8") == "Line 1\nLine 2"
    assert candidate.raw_payload["text"]["omitted"] is True
    assert value["accession_number"] == accession
    assert value["source_tickers"] == ["AAPL"]
    assert value["available_at"].isoformat() == "2026-01-30T12:05:00+00:00"


def test_scan_sec_filings_rejects_filename_doc_id_mismatches(tmp_path) -> None:
    _write_sec_file(
        tmp_path,
        ticker="AAPL",
        accession="0000320193-26-000001",
        overrides={"doc_id": "0000320193-26-000002"},
    )

    report = scan_sec_filings(
        data_root=tmp_path,
        clean_output_root=tmp_path / "clean",
        write_cleaned=False,
    )

    assert report.files_seen == 1
    assert report.valid_records == 0
    assert report.rejected_records == 1
    assert report.issues[0]["issue_type"] == "sec_filing_rejected"


def test_scan_sec_filings_dedupes_accession_and_keeps_ticker_aliases(tmp_path) -> None:
    accession = "0000070858-26-000001"
    _write_sec_file(tmp_path, ticker="BAC", accession=accession, text="primary text")
    _write_sec_file(tmp_path, ticker="BAC-PE", accession=accession, text="preferred share text")

    report = scan_sec_filings(
        data_root=tmp_path,
        clean_output_root=tmp_path / "clean",
        write_cleaned=False,
    )
    candidate = report.candidates[0]
    value = build_sec_filing_value(import_run_id=uuid4(), candidate=candidate)

    assert report.valid_records == 2
    assert report.unique_accessions == 1
    assert report.duplicate_accessions == 1
    assert candidate.canonical_ticker == "BAC"
    assert value["source_tickers"] == ["BAC", "BAC-PE"]
    assert report.issues[0]["issue_type"] == "duplicate_accession_mixed_hash"


def _write_sec_file(
    root: Path,
    *,
    ticker: str,
    accession: str,
    text: str = "Filing body",
    overrides: dict | None = None,
) -> Path:
    directory = root / "normalized" / "sec_edgar" / "run-1"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{ticker}-{accession}.jsonl"
    record = {
        "ticker": ticker.upper(),
        "date": "2026-01-30",
        "source": "sec_edgar",
        "section": "full",
        "doc_id": accession,
        "published_at": "2026-01-30T12:00:00+00:00",
        "available_at": "2026-01-30T12:05:00+00:00",
        "observed_at": "2026-01-30T12:06:00+00:00",
        "ingested_at": "2026-01-30T12:07:00+00:00",
        "title": "10-K",
        "source_url": f"https://www.sec.gov/Archives/edgar/data/{accession}.txt",
        "text": text,
        "source_type": "sec_filing",
        "content_hash": f"source-{accession}-{ticker}",
    }
    record.update(overrides or {})
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return path
