from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from jobs.faustcalc_common import (
    FAUSTCALC_SEC_SOURCE,
    canonical_ticker,
    get_faustcalc_data_root,
    jsonable_mapping,
    parse_optional_date,
    parse_optional_datetime,
    parse_required_datetime,
    stable_uuid,
)
from jobs.generate_event_features import generate_event_features_for_source


SEC_FILENAME_RE = re.compile(r"^(?P<ticker>.+)-(?P<accession>\d{10}-\d{2}-\d{6})\.jsonl$", re.I)


@dataclass(frozen=True)
class ParsedSecFilename:
    source_ticker: str
    canonical_ticker: str
    accession_number: str


@dataclass
class SecCandidate:
    source_path: Path
    source_ticker: str
    canonical_ticker: str
    accession_number: str
    form_type: str
    filing_date: Any
    published_at: datetime | None
    available_at: datetime
    observed_at: datetime | None
    source_ingested_at: datetime | None
    source_url: str | None
    source_content_hash: str | None
    text_sha256: str
    text_length: int
    cleaned_text_path: Path | None
    raw_payload: dict[str, Any]


@dataclass
class SecScanReport:
    files_seen: int = 0
    valid_records: int = 0
    unique_accessions: int = 0
    duplicate_accessions: int = 0
    duplicate_hashes: int = 0
    rejected_records: int = 0
    source_tickers: int = 0
    form_counts: dict[str, int] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[SecCandidate] = field(default_factory=list)

    def source_counts(self) -> dict[str, Any]:
        return {
            "files_seen": self.files_seen,
            "valid_records": self.valid_records,
            "unique_accessions": self.unique_accessions,
            "duplicate_accessions": self.duplicate_accessions,
            "duplicate_hashes": self.duplicate_hashes,
            "rejected_records": self.rejected_records,
            "source_tickers": self.source_tickers,
            "form_counts": self.form_counts,
        }


@dataclass
class SecImportReport:
    scan: SecScanReport
    import_run_id: str | None = None
    staged_filings: int = 0
    promoted_events: int = 0
    generated_event_features: int = 0
    dry_run: bool = False

    def render(self) -> str:
        return "\n".join(
            [
                "FaustCalc SEC filing import report",
                f"  dry_run={self.dry_run}",
                f"  import_run_id={self.import_run_id}",
                f"  files_seen={self.scan.files_seen}",
                f"  valid_records={self.scan.valid_records}",
                f"  unique_accessions={self.scan.unique_accessions}",
                f"  duplicate_accessions={self.scan.duplicate_accessions}",
                f"  rejected_records={self.scan.rejected_records}",
                f"  staged_filings={self.staged_filings}",
                f"  promoted_events={self.promoted_events}",
                f"  generated_event_features={self.generated_event_features}",
            ]
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean and import FaustCalc SEC filing files")
    parser.add_argument("--data-root", help="FaustCalc data root")
    parser.add_argument("--clean-output-root", help="Destination for cleaned filing text")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-staging", action="store_true")
    parser.add_argument("--skip-promote", action="store_true")
    parser.add_argument("--generate-event-features", action="store_true")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    report = run_sec_filings_import(
        data_root=get_faustcalc_data_root(args.data_root),
        clean_output_root=Path(args.clean_output_root) if args.clean_output_root else None,
        dry_run=args.dry_run,
        load_staging=not args.skip_staging,
        promote=not args.skip_promote,
        generate_features=args.generate_event_features,
        prefer_compose_port=args.prefer_compose_port,
    )
    print(report.render())


def run_sec_filings_import(
    *,
    data_root: Path | None = None,
    clean_output_root: Path | None = None,
    dry_run: bool = False,
    load_staging: bool = True,
    promote: bool = True,
    generate_features: bool = False,
    prefer_compose_port: bool = False,
) -> SecImportReport:
    resolved_data_root = data_root or get_faustcalc_data_root()
    output_root = clean_output_root or Path("data/raw/faustcalc_sec_clean")
    started_at = datetime.now(timezone.utc)

    if dry_run:
        scan = scan_sec_filings(
            data_root=resolved_data_root,
            clean_output_root=output_root,
            write_cleaned=False,
        )
        return SecImportReport(scan=scan, dry_run=True)

    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        import_run = models.FaustcalcImportRun(
            faustcalc_import_run_id=uuid.uuid4(),
            mode="sec_filings",
            source_database_fingerprint=None,
            data_root=str(resolved_data_root),
            status="running",
            started_at=started_at,
            finished_at=None,
            source_counts=None,
            validation_payload=None,
            error_payload=None,
        )
        session.add(import_run)
        session.flush()
        import_run_id = import_run.faustcalc_import_run_id

    try:
        scan = scan_sec_filings(
            data_root=resolved_data_root,
            clean_output_root=output_root,
            write_cleaned=True,
        )
        report = SecImportReport(scan=scan, import_run_id=str(import_run_id))

        if load_staging:
            with session_scope(prefer_compose_port=prefer_compose_port) as session:
                report.staged_filings = upsert_sec_filings(
                    session=session,
                    import_run_id=import_run_id,
                    candidates=scan.candidates,
                )
                upsert_validation_issues(
                    session=session,
                    import_run_id=import_run_id,
                    issues=scan.issues,
                )

        if promote:
            with session_scope(prefer_compose_port=prefer_compose_port) as session:
                report.promoted_events = promote_sec_events(session=session)

        if generate_features:
            with session_scope(prefer_compose_port=prefer_compose_port) as session:
                report.generated_event_features = generate_event_features_for_source(
                    session=session,
                    source=FAUSTCALC_SEC_SOURCE,
                )

        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            finish_sec_import_run(
                session=session,
                import_run_id=import_run_id,
                status="completed",
                source_counts=scan.source_counts(),
                validation_payload={
                    "staged_filings": report.staged_filings,
                    "promoted_events": report.promoted_events,
                    "generated_event_features": report.generated_event_features,
                    "issues": len(scan.issues),
                },
            )
        return report
    except Exception as exc:
        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            finish_sec_import_run(
                session=session,
                import_run_id=import_run_id,
                status="failed",
                error_payload={"error": str(exc)},
            )
        raise


def scan_sec_filings(*, data_root: Path, clean_output_root: Path, write_cleaned: bool) -> SecScanReport:
    files = sorted((data_root / "normalized" / "sec_edgar").rglob("*.jsonl"))
    report = SecScanReport(files_seen=len(files))
    valid_by_accession: dict[str, list[SecCandidate]] = defaultdict(list)
    hash_counts: Counter[str] = Counter()
    source_tickers: set[str] = set()
    form_counts: Counter[str] = Counter()

    for path in files:
        try:
            candidate = read_sec_candidate(
                path=path,
                clean_output_root=clean_output_root,
                write_cleaned=write_cleaned,
            )
        except ValueError as exc:
            report.rejected_records += 1
            report.issues.append(
                {
                    "severity": "error",
                    "issue_type": "sec_filing_rejected",
                    "source_table": "normalized_sec_edgar",
                    "source_key": str(path),
                    "details": {"error": str(exc)},
                }
            )
            continue

        valid_by_accession[candidate.accession_number].append(candidate)
        hash_counts[candidate.text_sha256] += 1
        source_tickers.add(candidate.source_ticker)
        form_counts[candidate.form_type.upper()] += 1

    report.valid_records = sum(len(items) for items in valid_by_accession.values())
    report.unique_accessions = len(valid_by_accession)
    report.duplicate_accessions = sum(1 for items in valid_by_accession.values() if len(items) > 1)
    report.duplicate_hashes = sum(1 for value in hash_counts.values() if value > 1)
    report.source_tickers = len(source_tickers)
    report.form_counts = dict(form_counts)

    for accession, items in valid_by_accession.items():
        hashes = {item.text_sha256 for item in items}
        if len(items) > 1 and len(hashes) > 1:
            report.issues.append(
                {
                    "severity": "warning",
                    "issue_type": "duplicate_accession_mixed_hash",
                    "source_table": "normalized_sec_edgar",
                    "source_key": accession,
                    "details": {
                        "source_tickers": sorted({item.source_ticker for item in items}),
                        "hashes": sorted(hashes),
                    },
                }
            )
        report.candidates.append(choose_accession_candidate(items))

    return report


def parse_sec_filename(path: Path) -> ParsedSecFilename:
    match = SEC_FILENAME_RE.match(path.name)
    if not match:
        raise ValueError(f"SEC normalized file name does not match expected pattern: {path.name}")
    source_ticker = match.group("ticker").upper()
    return ParsedSecFilename(
        source_ticker=source_ticker,
        canonical_ticker=canonical_ticker(source_ticker),
        accession_number=match.group("accession"),
    )


def read_sec_candidate(*, path: Path, clean_output_root: Path, write_cleaned: bool) -> SecCandidate:
    parsed = parse_sec_filename(path)
    with path.open("r", encoding="utf-8") as handle:
        line = handle.readline()
    if not line.strip():
        raise ValueError("empty normalized SEC JSONL file")

    record = json.loads(line)
    doc_id = str(record.get("doc_id") or "")
    if doc_id != parsed.accession_number:
        raise ValueError(f"filename accession {parsed.accession_number} does not match doc_id {doc_id}")
    source_ticker = str(record.get("ticker") or parsed.source_ticker).upper()
    if source_ticker != parsed.source_ticker:
        raise ValueError(f"filename ticker {parsed.source_ticker} does not match payload ticker {source_ticker}")

    text_value = record.get("text")
    if not isinstance(text_value, str) or not text_value.strip():
        raise ValueError("missing filing text")
    cleaned_text = clean_filing_text(text_value)
    text_sha256 = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
    cleaned_text_path = clean_output_root / f"{text_sha256}.txt"
    if write_cleaned:
        cleaned_text_path.parent.mkdir(parents=True, exist_ok=True)
        if not cleaned_text_path.exists():
            cleaned_text_path.write_text(cleaned_text, encoding="utf-8")

    available_at = parse_required_datetime(record.get("available_at"))
    raw_payload = jsonable_mapping(record)
    raw_payload["text"] = {
        "omitted": True,
        "text_length": len(text_value),
        "cleaned_text_length": len(cleaned_text),
    }

    return SecCandidate(
        source_path=path,
        source_ticker=source_ticker,
        canonical_ticker=parsed.canonical_ticker,
        accession_number=parsed.accession_number,
        form_type=str(record.get("title") or record.get("source_type") or "SEC filing").upper(),
        filing_date=parse_optional_date(record.get("date")),
        published_at=parse_optional_datetime(record.get("published_at")),
        available_at=available_at,
        observed_at=parse_optional_datetime(record.get("observed_at")),
        source_ingested_at=parse_optional_datetime(record.get("ingested_at")),
        source_url=record.get("source_url"),
        source_content_hash=record.get("content_hash"),
        text_sha256=text_sha256,
        text_length=len(cleaned_text),
        cleaned_text_path=cleaned_text_path,
        raw_payload=raw_payload,
    )


def clean_filing_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "").strip()


def choose_accession_candidate(items: list[SecCandidate]) -> SecCandidate:
    source_tickers = sorted({item.source_ticker for item in items})
    canonical = choose_canonical_ticker(source_tickers)
    chosen = sorted(
        items,
        key=lambda item: (
            item.canonical_ticker != canonical,
            -item.text_length,
            str(item.source_path),
        ),
    )[0]
    chosen.canonical_ticker = canonical
    chosen.raw_payload["source_ticker_aliases"] = source_tickers
    return chosen


def choose_canonical_ticker(source_tickers: list[str]) -> str:
    normalized = sorted({canonical_ticker(ticker) for ticker in source_tickers})
    return sorted(normalized, key=lambda ticker: (_looks_like_preferred_share(ticker), len(ticker), ticker))[0]


def _looks_like_preferred_share(ticker: str) -> bool:
    return bool(re.search(r"[-.]P[A-Z0-9]*$", ticker))


def upsert_sec_filings(*, session, import_run_id: uuid.UUID, candidates: list[SecCandidate]) -> int:
    if not candidates:
        return 0
    values = [build_sec_filing_value(import_run_id=import_run_id, candidate=candidate) for candidate in candidates]
    stmt = insert(models.FaustcalcSecFiling).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_faustcalc_sec_filing_accession",
        set_={
            "faustcalc_import_run_id": stmt.excluded.faustcalc_import_run_id,
            "canonical_ticker": stmt.excluded.canonical_ticker,
            "source_tickers": stmt.excluded.source_tickers,
            "form_type": stmt.excluded.form_type,
            "filing_date": stmt.excluded.filing_date,
            "published_at": stmt.excluded.published_at,
            "available_at": stmt.excluded.available_at,
            "observed_at": stmt.excluded.observed_at,
            "source_ingested_at": stmt.excluded.source_ingested_at,
            "source_url": stmt.excluded.source_url,
            "source_path": stmt.excluded.source_path,
            "cleaned_text_path": stmt.excluded.cleaned_text_path,
            "source_content_hash": stmt.excluded.source_content_hash,
            "text_sha256": stmt.excluded.text_sha256,
            "status": stmt.excluded.status,
            "rejection_reason": stmt.excluded.rejection_reason,
            "raw_payload": stmt.excluded.raw_payload,
        },
    )
    session.execute(stmt)
    return len(values)


def build_sec_filing_value(*, import_run_id: uuid.UUID, candidate: SecCandidate) -> dict[str, Any]:
    source_tickers = candidate.raw_payload.get("source_ticker_aliases") or [candidate.source_ticker]
    return {
        "faustcalc_sec_filing_id": stable_uuid(f"fc_sec_filing:{candidate.accession_number}"),
        "faustcalc_import_run_id": import_run_id,
        "accession_number": candidate.accession_number,
        "canonical_ticker": candidate.canonical_ticker,
        "source_tickers": sorted(set(source_tickers)),
        "form_type": candidate.form_type,
        "filing_date": candidate.filing_date,
        "published_at": candidate.published_at,
        "available_at": candidate.available_at,
        "observed_at": candidate.observed_at,
        "source_ingested_at": candidate.source_ingested_at,
        "source_url": candidate.source_url,
        "source_path": str(candidate.source_path),
        "cleaned_text_path": str(candidate.cleaned_text_path) if candidate.cleaned_text_path else None,
        "source_content_hash": candidate.source_content_hash,
        "text_sha256": candidate.text_sha256,
        "status": "valid",
        "rejection_reason": None,
        "raw_payload": candidate.raw_payload,
    }


def upsert_validation_issues(*, session, import_run_id: uuid.UUID, issues: list[dict[str, Any]]) -> int:
    for issue in issues:
        session.add(
            models.FaustcalcValidationIssue(
                faustcalc_validation_issue_id=stable_uuid(
                    "fc_issue:"
                    f"{import_run_id}:{issue.get('issue_type')}:{issue.get('source_key')}"
                ),
                faustcalc_import_run_id=import_run_id,
                severity=issue.get("severity", "warning"),
                issue_type=issue.get("issue_type", "unknown"),
                source_table=issue.get("source_table"),
                source_key=issue.get("source_key"),
                details=issue.get("details"),
                created_at=datetime.now(timezone.utc),
            )
        )
    return len(issues)


def promote_sec_events(*, session) -> int:
    sql = text(
        """
        INSERT INTO event (
            event_id,
            company_id,
            security_id,
            event_type,
            source,
            source_id,
            payload_uri,
            structured_payload,
            event_time,
            ingestion_time,
            timestamp_available
        )
        SELECT
            CAST(
                substr(md5(:source || ':' || f.accession_number), 1, 8) || '-' ||
                substr(md5(:source || ':' || f.accession_number), 9, 4) || '-' ||
                substr(md5(:source || ':' || f.accession_number), 13, 4) || '-' ||
                substr(md5(:source || ':' || f.accession_number), 17, 4) || '-' ||
                substr(md5(:source || ':' || f.accession_number), 21, 12)
                AS uuid
            ) AS event_id,
            s.company_id,
            s.security_id,
            f.form_type,
            :source,
            f.accession_number,
            f.cleaned_text_path,
            jsonb_build_object(
                'canonical_ticker', f.canonical_ticker,
                'source_tickers', f.source_tickers,
                'source_url', f.source_url,
                'source_path', f.source_path,
                'content_hash', f.source_content_hash,
                'text_sha256', f.text_sha256,
                'filing_date', f.filing_date,
                'source', :source
            ),
            COALESCE(f.published_at, f.available_at),
            COALESCE(f.source_ingested_at, f.available_at),
            f.available_at
        FROM faustcalc_sec_filing f
        JOIN LATERAL (
            SELECT th.security_id
              FROM security_ticker_history th
             WHERE th.ticker = f.canonical_ticker
               AND th.active_to IS NULL
             ORDER BY th.active_from DESC, th.security_id
             LIMIT 1
        ) th ON TRUE
        JOIN security s
          ON s.security_id = th.security_id
        WHERE f.status = 'valid'
        ON CONFLICT ON CONSTRAINT uq_event_source_id
        DO UPDATE SET
            company_id = EXCLUDED.company_id,
            security_id = EXCLUDED.security_id,
            event_type = EXCLUDED.event_type,
            payload_uri = EXCLUDED.payload_uri,
            structured_payload = EXCLUDED.structured_payload,
            event_time = EXCLUDED.event_time,
            ingestion_time = EXCLUDED.ingestion_time,
            timestamp_available = EXCLUDED.timestamp_available
        """
    )
    result = session.execute(sql, {"source": FAUSTCALC_SEC_SOURCE})
    return int(result.rowcount or 0)


def finish_sec_import_run(
    *,
    session,
    import_run_id: uuid.UUID,
    status: str,
    source_counts: dict | None = None,
    validation_payload: dict | None = None,
    error_payload: dict | None = None,
) -> None:
    import_run = session.get(models.FaustcalcImportRun, import_run_id)
    if import_run is None:
        return
    import_run.status = status
    import_run.finished_at = datetime.now(timezone.utc)
    if source_counts is not None:
        import_run.source_counts = source_counts
    if validation_payload is not None:
        import_run.validation_payload = validation_payload
    if error_payload is not None:
        import_run.error_payload = error_payload


if __name__ == "__main__":
    main()
