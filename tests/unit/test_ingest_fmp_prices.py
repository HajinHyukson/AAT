from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db import models
from db.base import Base
from jobs.ingest_fmp_prices import ensure_security


def test_ensure_security_creates_company_security_and_ticker_history() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            models.Company.__table__,
            models.Security.__table__,
            models.SecurityTickerHistory.__table__,
        ],
    )
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    first_seen = datetime(2026, 1, 2, tzinfo=timezone.utc)

    security = ensure_security(
        ticker="AAPL",
        company_name="Apple Inc.",
        exchange="NASDAQ",
        first_seen=first_seen,
        session=session,
    )
    session.commit()

    ticker_history = session.execute(select(models.SecurityTickerHistory)).scalar_one()
    assert ticker_history.security_id == security.security_id
    assert ticker_history.ticker == "AAPL"
