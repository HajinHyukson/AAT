from __future__ import annotations

import argparse
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from db import models
from db.session import make_engine, session_scope
from engine.contracts import TimeWindow
from jobs.advisory_locks import advisory_lock_key
from jobs.attribution_methodologies import load_methodology
from jobs.attribution_windowing import missing_windows_for_range
from jobs.refresh_attribution_summaries import refresh_attribution_summaries
from jobs.run_attribution import (
    FRENCH_FACTOR_NAMES,
    load_active_peer_context,
    load_active_sector_factor_names,
    load_engine_price_bars,
    load_factor_returns_by_name,
    load_macro_values,
    run_attribution_for_security,
)


MACRO_SERIES_NAMES = ("DGS2", "DGS10", "BAMLH0A0HYM2", "BAMLC0A0CM", "VIXCLS", "T5YIE")


@dataclass
class OnDemandWorkerReport:
    processed: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0

    def render(self) -> str:
        return (
            "on-demand attribution worker "
            f"processed={self.processed} completed={self.completed} "
            f"failed={self.failed} skipped={self.skipped}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run queued web-triggered attribution jobs")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    while True:
        report = run_worker_once(limit=args.limit, prefer_compose_port=args.prefer_compose_port)
        print(report.render(), flush=True)
        if args.once:
            break
        time.sleep(args.poll_interval)


def run_worker_once(*, limit: int = 10, prefer_compose_port: bool = False) -> OnDemandWorkerReport:
    report = OnDemandWorkerReport()
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        job_ids = [
            row[0]
            for row in session.execute(
                select(models.AttributionOnDemandJob.attribution_on_demand_job_id)
                .where(models.AttributionOnDemandJob.status == "queued")
                .order_by(models.AttributionOnDemandJob.created_at.asc())
                .limit(limit)
            )
        ]

    for job_id in job_ids:
        result = process_job(job_id=job_id, prefer_compose_port=prefer_compose_port)
        report.processed += 1
        if result == "completed":
            report.completed += 1
        elif result == "skipped":
            report.skipped += 1
        else:
            report.failed += 1
    return report


def process_job(*, job_id: uuid.UUID, prefer_compose_port: bool = False) -> str:
    lock = try_acquire_job_lock(job_id=job_id, prefer_compose_port=prefer_compose_port)
    if lock is None:
        return "skipped"
    try:
        return _process_job_locked(job_id=job_id, prefer_compose_port=prefer_compose_port)
    finally:
        lock.release()


def _process_job_locked(*, job_id: uuid.UUID, prefer_compose_port: bool) -> str:
    now = datetime.now(timezone.utc)
    try:
        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            job = session.get(models.AttributionOnDemandJob, job_id)
            if job is None:
                return "skipped"
            if job.status in {"completed", "failed", "skipped"}:
                return job.status
            job.status = "running"
            job.started_at = job.started_at or now
            job.updated_at = now

            methodology = load_methodology(session=session, methodology=job.methodology)
            if methodology is None:
                raise ValueError(f"unsupported attribution methodology {job.methodology}")
            runner_config = methodology.runner_config or {}
            lookback_days = int(runner_config.get("lookback_days", 252))
            use_expanded_mvp = bool(runner_config.get("use_expanded_mvp", True))
            include_event_evidence = bool(runner_config.get("include_event_evidence", True))

            security = session.get(models.Security, job.security_id)
            if security is None:
                raise RuntimeError(f"security {job.security_id} not found")

            price_window = TimeWindow(
                start=job.target_range_start - timedelta(days=lookback_days),
                end=job.target_range_end,
            )
            price_bars = load_engine_price_bars(
                session=session,
                security_id=job.security_id,
                window=price_window,
                through=job.target_range_end,
                attribution_cutoff=now,
            )
            if len(price_bars) < 2:
                job.status = "failed"
                job.finished_at = datetime.now(timezone.utc)
                job.updated_at = job.finished_at
                job.error_payload = {"error": "not enough price history"}
                return "failed"

            sector_factor_names = load_active_sector_factor_names(
                session=session,
                security_id=job.security_id,
                attribution_cutoff=now,
            )
            preloaded_factor_returns = load_factor_returns_by_name(
                session=session,
                factor_names=tuple(sorted(set(FRENCH_FACTOR_NAMES) | set(sector_factor_names))),
                window=price_window,
                attribution_cutoff=now,
            )
            preloaded_macro_values = {
                name: load_macro_values(
                    session=session,
                    series_name=name,
                    window=price_window,
                    attribution_cutoff=now,
                )
                for name in MACRO_SERIES_NAMES
            }
            preloaded_peer_context = load_active_peer_context(
                session=session,
                security_id=job.security_id,
                price_window=price_window,
                through=job.target_range_end,
                attribution_cutoff=now,
            )

            trading_dates = [bar.event_time for bar in price_bars]
            windows = missing_windows_for_job(
                session=session,
                security_id=job.security_id,
                methodology=job.methodology,
                cadence=job.cadence,
                trading_dates=trading_dates,
                target_range_start=job.target_range_start,
                target_range_end=job.target_range_end,
            )
            job.expected_windows = len(windows)
            latest_run_id = job.latest_run_id
            for window in windows:
                try:
                    run_attribution_for_security(
                        session=session,
                        security=security,
                        window=window,
                        attribution_cutoff=now,
                        use_expanded_mvp=use_expanded_mvp,
                        include_event_evidence=include_event_evidence,
                        lookback_days=lookback_days,
                        cadence=job.cadence,
                        preloaded_price_bars=price_bars,
                        preloaded_factor_returns_by_name=preloaded_factor_returns,
                        preloaded_macro_values_by_name=preloaded_macro_values,
                        preloaded_peer_context=preloaded_peer_context,
                        methodology=job.methodology,
                    )
                    job.ran_windows = int(job.ran_windows or 0) + 1
                    latest_run = latest_run_for_window(
                        session=session,
                        security_id=job.security_id,
                        methodology=job.methodology,
                        cadence=job.cadence,
                        window=window,
                    )
                    latest_run_id = latest_run.attribution_run_id if latest_run is not None else latest_run_id
                except (RuntimeError, ValueError) as exc:
                    job.skipped_windows = int(job.skipped_windows or 0) + 1
                    job.error_payload = {"last_skip": str(exc).splitlines()[0]}

            job.latest_run_id = latest_run_id or latest_methodology_run_id(
                session=session,
                security_id=job.security_id,
                methodology=job.methodology,
                cadence=job.cadence,
            )
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            job.updated_at = job.finished_at
            refresh_attribution_summaries(
                session=session,
                methodology=job.methodology,
                tickers=(job.ticker,),
            )
            return "completed"
    except Exception as exc:
        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            job = session.get(models.AttributionOnDemandJob, job_id)
            if job is not None:
                job.status = "failed"
                job.finished_at = datetime.now(timezone.utc)
                job.updated_at = job.finished_at
                job.error_payload = {"error": str(exc).splitlines()[0]}
        return "failed"


def missing_windows_for_job(
    *,
    session,
    security_id: uuid.UUID,
    methodology: str,
    cadence: str,
    trading_dates: list[datetime],
    target_range_start: datetime,
    target_range_end: datetime,
) -> list[TimeWindow]:
    return missing_windows_for_range(
        session=session,
        security_id=security_id,
        methodology=methodology,
        cadence=cadence,
        trading_dates=trading_dates,
        target_range_start=target_range_start,
        target_range_end=target_range_end,
    )


def latest_run_for_window(*, session, security_id: uuid.UUID, methodology: str, cadence: str, window: TimeWindow):
    return session.execute(
        select(models.AttributionRun)
        .where(models.AttributionRun.security_id == security_id)
        .where(models.AttributionRun.methodology == methodology)
        .where(models.AttributionRun.cadence == cadence)
        .where(models.AttributionRun.window_start == window.start)
        .where(models.AttributionRun.window_end == window.end)
        .order_by(models.AttributionRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def latest_methodology_run_id(*, session, security_id: uuid.UUID, methodology: str, cadence: str):
    return session.execute(
        select(models.AttributionRun.attribution_run_id)
        .where(models.AttributionRun.security_id == security_id)
        .where(models.AttributionRun.methodology == methodology)
        .where(models.AttributionRun.cadence == cadence)
        .order_by(models.AttributionRun.window_end.desc(), models.AttributionRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


@dataclass
class JobAdvisoryLock:
    connection: object
    key: int

    def release(self) -> None:
        try:
            self.connection.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": self.key})
        finally:
            self.connection.close()


def try_acquire_job_lock(*, job_id: uuid.UUID, prefer_compose_port: bool) -> JobAdvisoryLock | None:
    connection = make_engine(prefer_compose_port).connect()
    key = advisory_lock_key(f"aat:on_demand_attribution_job:{job_id}")
    try:
        acquired = bool(
            connection.execute(text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": key}).scalar_one()
        )
        if not acquired:
            connection.close()
            return None
        return JobAdvisoryLock(connection=connection, key=key)
    except Exception:
        connection.close()
        raise


if __name__ == "__main__":
    main()
