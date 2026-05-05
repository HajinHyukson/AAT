from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from adapters.sec_edgar.client import EdgarFiling, fetch_submissions, normalize_cik
from db import models
from db.session import session_scope


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SEC EDGAR recent submissions")
    parser.add_argument("cik", help="Company CIK")
    parser.add_argument("--ticker", help="Ticker used to link to an existing security")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    filings = fetch_submissions(cik=args.cik)
    filings = filings[: args.limit]

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        company = ensure_company(session=session, filing=filings[0], ticker=args.ticker)
        security = find_security(session=session, ticker=args.ticker) if args.ticker else None
        upsert_filings(session=session, company=company, security=security, filings=filings)

    print(f"ingested {len(filings)} EDGAR filings for CIK {normalize_cik(args.cik)}")


def ensure_company(*, session, filing: EdgarFiling, ticker: str | None) -> models.Company:
    company = session.execute(
        select(models.Company).where(models.Company.cik == filing.cik)
    ).scalar_one_or_none()
    if company is not None:
        if filing.company_name and company.legal_name != filing.company_name:
            company.legal_name = filing.company_name
        return company

    if ticker:
        security = find_security(session=session, ticker=ticker)
        if security is not None:
            security.company.cik = filing.cik
            if filing.company_name:
                security.company.legal_name = filing.company_name
            return security.company

    company = models.Company(
        company_id=uuid.uuid4(),
        cik=filing.cik,
        legal_name=filing.company_name or filing.cik,
        created_at=datetime.now(timezone.utc),
    )
    session.add(company)
    session.flush()
    return company


def find_security(*, session, ticker: str | None) -> models.Security | None:
    if not ticker:
        return None
    return session.execute(
        select(models.Security)
        .join(
            models.SecurityTickerHistory,
            models.Security.security_id == models.SecurityTickerHistory.security_id,
        )
        .where(models.SecurityTickerHistory.ticker == ticker.upper())
        .where(models.SecurityTickerHistory.active_to.is_(None))
    ).scalar_one_or_none()


def upsert_filings(
    *,
    session,
    company: models.Company,
    security: models.Security | None,
    filings: list[EdgarFiling],
) -> None:
    for filing in filings:
        stmt = insert(models.Event).values(
            event_id=uuid.uuid4(),
            company_id=company.company_id,
            security_id=security.security_id if security else None,
            event_type=filing.form,
            source=filing.source,
            source_id=filing.accession_number,
            payload_uri=filing.primary_document,
            structured_payload={
                "cik": filing.cik,
                "filing_date": filing.filing_date.isoformat(),
                "report_date": filing.report_date.isoformat() if filing.report_date else None,
                "company_name": filing.company_name,
            },
            event_time=filing.event_time,
            ingestion_time=filing.ingestion_time,
            timestamp_available=filing.timestamp_available,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_event_source_id",
            set_={
                "company_id": stmt.excluded.company_id,
                "security_id": stmt.excluded.security_id,
                "event_type": stmt.excluded.event_type,
                "payload_uri": stmt.excluded.payload_uri,
                "structured_payload": stmt.excluded.structured_payload,
                "event_time": stmt.excluded.event_time,
                "ingestion_time": stmt.excluded.ingestion_time,
                "timestamp_available": stmt.excluded.timestamp_available,
            },
        )
        session.execute(stmt)


if __name__ == "__main__":
    main()
