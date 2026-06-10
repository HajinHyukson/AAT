"""Investor-flow evidence inputs for KOSPI pilot attribution.

Builds evidence-only ``FactorContributionInput`` rows (contribution_bps=0)
from staged Acquin investor flows and foreign holdings. Flows stay
evidence-only until a calibrated production factor return exists, per the
project contribution rules; they surface in the dashboard evidence drawer
without reducing the residual.

All descriptors are point-in-time filtered through the Acquin vintage policy:
a source row is only used if its derived ``timestamp_available`` is at or
before the attribution cutoff.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select

from db import models
from db.session import session_scope
from engine.contracts import (
    ConfidenceLevel,
    ContributionStage,
    DriverType,
    FactorContributionInput,
    TimeWindow,
)
from jobs.pilot_kospi_common import (
    acquin_vintage_stamps,
    ensure_pilot_kospi_database_url,
    normalize_kospi_ticker,
)


FOREIGN = "foreign"
INSTITUTION = "institution"
RETAIL = "retail"
TRAILING_SHORT_DAYS = 5
TRAILING_LONG_DAYS = 20


def build_flow_evidence_inputs(
    *,
    session,
    security_id: UUID,
    ticker: str,
    window: TimeWindow,
    attribution_cutoff: datetime,
) -> list[FactorContributionInput]:
    now = datetime.now(timezone.utc)
    window_start_date = window.start.date()
    window_end_date = window.end.date()

    flow_rows = _visible_flow_rows(
        session=session,
        ticker=ticker,
        through=window_end_date,
        attribution_cutoff=attribution_cutoff,
        fallback_ingestion_time=now,
    )
    holding_rows = _visible_holding_rows(
        session=session,
        ticker=ticker,
        through=window_end_date,
        attribution_cutoff=attribution_cutoff,
        fallback_ingestion_time=now,
    )

    inputs: list[FactorContributionInput] = []
    foreign_input = _foreign_flow_input(
        security_id=security_id,
        flow_rows=flow_rows,
        window_start_date=window_start_date,
        window_end_date=window_end_date,
        window=window,
    )
    if foreign_input is not None:
        inputs.append(foreign_input)
    domestic_input = _domestic_flow_input(
        security_id=security_id,
        flow_rows=flow_rows,
        window_start_date=window_start_date,
        window_end_date=window_end_date,
        window=window,
    )
    if domestic_input is not None:
        inputs.append(domestic_input)
    ownership_input = _foreign_ownership_input(
        security_id=security_id,
        holding_rows=holding_rows,
        window_start_date=window_start_date,
        window=window,
    )
    if ownership_input is not None:
        inputs.append(ownership_input)
    return inputs


def _visible_flow_rows(
    *,
    session,
    ticker: str,
    through: date,
    attribution_cutoff: datetime,
    fallback_ingestion_time: datetime,
) -> list[dict]:
    rows = (
        session.execute(
            select(models.AcquinInvestorFlow)
            .where(models.AcquinInvestorFlow.ticker == ticker)
            .where(models.AcquinInvestorFlow.flow_date <= through)
            .order_by(models.AcquinInvestorFlow.flow_date.desc())
            .limit((TRAILING_LONG_DAYS + 10) * 3)
        )
        .scalars()
        .all()
    )
    visible = []
    for row in rows:
        stamps = acquin_vintage_stamps(
            trade_date=row.flow_date,
            source_created_at=row.source_created_at,
            fallback_ingestion_time=fallback_ingestion_time,
        )
        if stamps.timestamp_available <= attribution_cutoff:
            visible.append(
                {
                    "flow_date": row.flow_date,
                    "investor_group": row.investor_group,
                    "net_buy_amount": row.net_buy_amount,
                    "timestamp_available": stamps.timestamp_available,
                }
            )
    return visible


def _visible_holding_rows(
    *,
    session,
    ticker: str,
    through: date,
    attribution_cutoff: datetime,
    fallback_ingestion_time: datetime,
) -> list[dict]:
    rows = (
        session.execute(
            select(models.AcquinForeignHolding)
            .where(models.AcquinForeignHolding.ticker == ticker)
            .where(models.AcquinForeignHolding.holding_date <= through)
            .order_by(models.AcquinForeignHolding.holding_date.desc())
            .limit(TRAILING_LONG_DAYS + 10)
        )
        .scalars()
        .all()
    )
    visible = []
    for row in rows:
        stamps = acquin_vintage_stamps(
            trade_date=row.holding_date,
            source_created_at=row.source_created_at,
            fallback_ingestion_time=fallback_ingestion_time,
        )
        if stamps.timestamp_available <= attribution_cutoff:
            visible.append(
                {
                    "holding_date": row.holding_date,
                    "foreign_ownership_pct": row.foreign_ownership_pct,
                    "foreign_limit_exhaustion_pct": row.foreign_limit_exhaustion_pct,
                    "timestamp_available": stamps.timestamp_available,
                }
            )
    return visible


def _foreign_flow_input(
    *,
    security_id: UUID,
    flow_rows: list[dict],
    window_start_date: date,
    window_end_date: date,
    window: TimeWindow,
) -> FactorContributionInput | None:
    foreign_rows = [row for row in flow_rows if row["investor_group"] == FOREIGN]
    if not foreign_rows:
        return None
    window_rows = [
        row for row in foreign_rows if window_start_date < row["flow_date"] <= window_end_date
    ]
    window_net = _sum_amounts(window_rows)
    trailing_short = _sum_amounts(foreign_rows[:TRAILING_SHORT_DAYS])
    trailing_long = _sum_amounts(foreign_rows[:TRAILING_LONG_DAYS])
    streak = _streak_days(foreign_rows)
    used = window_rows or foreign_rows[:1]
    return FactorContributionInput(
        security_id=security_id,
        driver=DriverType.POSITIONING,
        name="Foreign investor flow (KRX)",
        contribution_bps=0.0,
        confidence=ConfidenceLevel.MEDIUM,
        contribution_stage=ContributionStage.EVIDENCE_ONLY,
        evidence=[
            f"foreign net buy over window: {_format_krw(window_net)}",
            f"foreign net buy streak: {streak} day(s)",
        ],
        evidence_payload={
            "window_net_buy_amount_krw": window_net,
            "trailing_5d_net_buy_amount_krw": trailing_short,
            "trailing_20d_net_buy_amount_krw": trailing_long,
            "net_buy_streak_days": streak,
            "flow_days_in_window": len(window_rows),
        },
        event_time=window.end,
        ingestion_time=max(row["timestamp_available"] for row in used),
        timestamp_available=max(row["timestamp_available"] for row in used),
    )


def _domestic_flow_input(
    *,
    security_id: UUID,
    flow_rows: list[dict],
    window_start_date: date,
    window_end_date: date,
    window: TimeWindow,
) -> FactorContributionInput | None:
    window_rows = [
        row
        for row in flow_rows
        if window_start_date < row["flow_date"] <= window_end_date
        and row["investor_group"] in {INSTITUTION, RETAIL}
    ]
    if not window_rows:
        return None
    institution_net = _sum_amounts(
        [row for row in window_rows if row["investor_group"] == INSTITUTION]
    )
    retail_net = _sum_amounts([row for row in window_rows if row["investor_group"] == RETAIL])
    return FactorContributionInput(
        security_id=security_id,
        driver=DriverType.POSITIONING,
        name="Domestic investor flow (KRX)",
        contribution_bps=0.0,
        confidence=ConfidenceLevel.MEDIUM,
        contribution_stage=ContributionStage.EVIDENCE_ONLY,
        evidence=[
            f"institution net buy over window: {_format_krw(institution_net)}",
            f"retail net buy over window: {_format_krw(retail_net)}",
        ],
        evidence_payload={
            "window_institution_net_buy_amount_krw": institution_net,
            "window_retail_net_buy_amount_krw": retail_net,
            "flow_days_in_window": len({row["flow_date"] for row in window_rows}),
        },
        event_time=window.end,
        ingestion_time=max(row["timestamp_available"] for row in window_rows),
        timestamp_available=max(row["timestamp_available"] for row in window_rows),
    )


def _foreign_ownership_input(
    *,
    security_id: UUID,
    holding_rows: list[dict],
    window_start_date: date,
    window: TimeWindow,
) -> FactorContributionInput | None:
    if not holding_rows:
        return None
    latest = holding_rows[0]
    at_start = next(
        (row for row in holding_rows if row["holding_date"] <= window_start_date),
        None,
    )
    start_pct = at_start["foreign_ownership_pct"] if at_start else None
    end_pct = latest["foreign_ownership_pct"]
    change = (
        end_pct - start_pct
        if end_pct is not None and start_pct is not None
        else None
    )
    return FactorContributionInput(
        security_id=security_id,
        driver=DriverType.POSITIONING,
        name="Foreign ownership (KRX)",
        contribution_bps=0.0,
        confidence=ConfidenceLevel.MEDIUM,
        contribution_stage=ContributionStage.EVIDENCE_ONLY,
        evidence=[
            f"foreign ownership at window end: {end_pct}",
        ],
        evidence_payload={
            "foreign_ownership_pct_start": start_pct,
            "foreign_ownership_pct_end": end_pct,
            "foreign_ownership_pct_change": change,
            "foreign_limit_exhaustion_pct": latest["foreign_limit_exhaustion_pct"],
        },
        event_time=window.end,
        ingestion_time=latest["timestamp_available"],
        timestamp_available=latest["timestamp_available"],
    )


def _sum_amounts(rows: list[dict]) -> float:
    return float(sum(row["net_buy_amount"] or 0.0 for row in rows))


def _streak_days(rows_desc: list[dict]) -> int:
    """Consecutive same-sign foreign net-buy days ending at the latest row."""
    streak = 0
    sign = None
    for row in rows_desc:
        amount = row["net_buy_amount"]
        if amount is None or amount == 0:
            break
        current = 1 if amount > 0 else -1
        if sign is None:
            sign = current
        if current != sign:
            break
        streak += 1
    return streak * (sign or 0)


def _format_krw(value: float) -> str:
    return f"{value:,.0f} KRW"


def main() -> None:
    parser = argparse.ArgumentParser(description="Spot-check KOSPI flow evidence for a ticker/window")
    parser.add_argument("ticker")
    parser.add_argument("--from", dest="start", required=True, help="Window start YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="Window end YYYY-MM-DD")
    args = parser.parse_args()

    ensure_pilot_kospi_database_url()
    ticker = normalize_kospi_ticker(args.ticker)
    window = TimeWindow(
        start=datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc),
        end=datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc),
    )
    cutoff = datetime.now(timezone.utc)
    with session_scope() as session:
        security_id = session.execute(
            select(models.SecurityTickerHistory.security_id)
            .where(models.SecurityTickerHistory.ticker == ticker)
            .limit(1)
        ).scalar_one_or_none()
        if security_id is None:
            raise SystemExit(f"unknown ticker {ticker}; promote the universe first")
        inputs = build_flow_evidence_inputs(
            session=session,
            security_id=security_id,
            ticker=ticker,
            window=window,
            attribution_cutoff=cutoff,
        )
    for item in inputs:
        print(f"{item.name}: {item.evidence_payload}")


if __name__ == "__main__":
    main()
