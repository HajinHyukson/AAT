from __future__ import annotations

import argparse
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from engine.contracts import TimeWindow
from jobs.faustcalc_common import (
    DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    stable_uuid,
)
from jobs.refresh_attribution_summaries import refresh_attribution_summaries
from jobs.run_attribution import (
    FRENCH_FACTOR_NAMES,
    load_active_sector_factor_names,
    load_active_peer_context,
    load_engine_price_bars,
    load_factor_returns_by_name,
    load_macro_values,
    run_attribution_for_security,
)
from jobs.run_batch_attribution import build_windows, load_trading_dates


VALID_CADENCES = ("daily", "weekly", "monthly")
VALID_TASK_ORDERS = ("expected-windows", "ticker")


@dataclass
class CadenceBackfillCoverage:
    expected: int = 0
    ran: int = 0
    skipped: int = 0
    failed_tasks: int = 0


@dataclass
class FaustcalcAttributionBackfillReport:
    backfill_run_id: str | None = None
    universe_name: str = DEFAULT_FAUSTCALC_UNIVERSE_NAME
    universe_version: str = DEFAULT_FAUSTCALC_UNIVERSE_VERSION
    analysis_start: date | None = None
    analysis_end: date | None = None
    tasks_created: int = 0
    tasks_processed: int = 0
    summaries_refreshed: int = 0
    final_task_progress: dict[str, object] = field(default_factory=dict)
    cadence_coverage: dict[str, CadenceBackfillCoverage] = field(default_factory=dict)
    skip_reasons: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not any(coverage.failed_tasks for coverage in self.cadence_coverage.values())

    def coverage_payload(self) -> dict:
        return {
            "universe_name": self.universe_name,
            "universe_version": self.universe_version,
            "analysis_start": self.analysis_start.isoformat() if self.analysis_start else None,
            "analysis_end": self.analysis_end.isoformat() if self.analysis_end else None,
            "tasks_created": self.tasks_created,
            "tasks_processed": self.tasks_processed,
            "summaries_refreshed": self.summaries_refreshed,
            "final_task_progress": self.final_task_progress,
            "cadence_coverage": {
                cadence: {
                    "expected": coverage.expected,
                    "ran": coverage.ran,
                    "skipped": coverage.skipped,
                    "failed_tasks": coverage.failed_tasks,
                }
                for cadence, coverage in self.cadence_coverage.items()
            },
            "top_skip_reasons": Counter(self.skip_reasons).most_common(10),
        }

    def render(self) -> str:
        lines = [
            "FaustCalc attribution backfill report",
            f"  backfill_run_id={self.backfill_run_id}",
            f"  universe={self.universe_name} version={self.universe_version}",
            f"  analysis_window={self.analysis_start}->{self.analysis_end}",
            f"  tasks_created={self.tasks_created} tasks_processed={self.tasks_processed}",
            f"  task_progress={format_task_progress(self.final_task_progress)}",
            f"  summaries_refreshed={self.summaries_refreshed}",
            f"  success={self.success}",
        ]
        for cadence, coverage in self.cadence_coverage.items():
            lines.append(
                f"  {cadence}: expected={coverage.expected} ran={coverage.ran} "
                f"skipped={coverage.skipped} failed_tasks={coverage.failed_tasks}"
            )
        if self.skip_reasons:
            lines.append(f"  top_skip_reasons={Counter(self.skip_reasons).most_common(10)}")
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run resumable attribution for the FaustCalc universe")
    parser.add_argument("--universe-name", default=DEFAULT_FAUSTCALC_UNIVERSE_NAME)
    parser.add_argument("--universe-version", default=DEFAULT_FAUSTCALC_UNIVERSE_VERSION)
    parser.add_argument("--backfill-run-id", help="Resume an existing backfill run")
    parser.add_argument("--from", dest="start", help="Analysis start date YYYY-MM-DD; defaults to universe min")
    parser.add_argument("--to", dest="end", help="Analysis end date YYYY-MM-DD; defaults to universe max")
    parser.add_argument("--cadences", nargs="+", choices=VALID_CADENCES, default=list(VALID_CADENCES))
    parser.add_argument("--lookback-days", type=int, default=252)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--max-tasks", type=int, help="Stop after processing this many tasks")
    parser.add_argument("--window-commit-size", type=int, default=25)
    parser.add_argument("--task-order", choices=VALID_TASK_ORDERS, default="expected-windows")
    parser.add_argument("--status-only", action="store_true")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1,
        help="Print DB-backed task progress after this many processed tasks; 0 disables progress output",
    )
    parser.add_argument("--skip-summary-refresh", action="store_true")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()
    requested_backfill_run_id = uuid.UUID(args.backfill_run_id) if args.backfill_run_id else None

    if args.status_only:
        with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
            backfill_run_id = resolve_backfill_run_id(
                session=session,
                backfill_run_id=requested_backfill_run_id,
                universe_name=args.universe_name,
                universe_version=args.universe_version,
            )
            print_task_progress(
                session=session,
                backfill_run_id=backfill_run_id,
                prefix="status",
            )
        return

    report = run_faustcalc_attribution_backfill(
        universe_name=args.universe_name,
        universe_version=args.universe_version,
        backfill_run_id=requested_backfill_run_id,
        analysis_start=date.fromisoformat(args.start) if args.start else None,
        analysis_end=date.fromisoformat(args.end) if args.end else None,
        cadences=tuple(args.cadences),
        lookback_days=args.lookback_days,
        batch_size=args.batch_size,
        max_tasks=args.max_tasks,
        window_commit_size=args.window_commit_size,
        task_order=args.task_order,
        progress_every=args.progress_every,
        refresh_summaries=not args.skip_summary_refresh,
        prefer_compose_port=args.prefer_compose_port,
    )
    print(report.render())
    if not report.success:
        raise SystemExit(1)


def run_faustcalc_attribution_backfill(
    *,
    universe_name: str = DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    universe_version: str = DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    backfill_run_id: uuid.UUID | None = None,
    analysis_start: date | None = None,
    analysis_end: date | None = None,
    cadences: tuple[str, ...] = VALID_CADENCES,
    lookback_days: int = 252,
    batch_size: int = 200,
    max_tasks: int | None = None,
    window_commit_size: int = 25,
    task_order: str = "expected-windows",
    progress_every: int = 1,
    refresh_summaries: bool = True,
    prefer_compose_port: bool = False,
) -> FaustcalcAttributionBackfillReport:
    if window_commit_size <= 0:
        raise ValueError("window_commit_size must be positive")
    if task_order not in VALID_TASK_ORDERS:
        raise ValueError(f"task_order must be one of {VALID_TASK_ORDERS}")
    report = FaustcalcAttributionBackfillReport(
        universe_name=universe_name,
        universe_version=universe_version,
        cadence_coverage={cadence: CadenceBackfillCoverage() for cadence in cadences},
    )
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        start_date, end_date = resolve_analysis_dates(
            session=session,
            universe_name=universe_name,
            universe_version=universe_version,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
        report.analysis_start = start_date
        report.analysis_end = end_date
        if backfill_run_id is None:
            backfill_run_id = create_backfill_run(
                session=session,
                universe_name=universe_name,
                universe_version=universe_version,
                analysis_start=start_date,
                analysis_end=end_date,
                cadences=cadences,
                lookback_days=lookback_days,
            )
            report.tasks_created = ensure_backfill_tasks(
                session=session,
                backfill_run_id=backfill_run_id,
                universe_name=universe_name,
                universe_version=universe_version,
                start=_date_to_utc_datetime(start_date),
                end=_date_to_utc_datetime(end_date),
                cadences=cadences,
                lookback_days=lookback_days,
            )
        report.backfill_run_id = str(backfill_run_id)
        if progress_every > 0:
            print_task_progress(
                session=session,
                backfill_run_id=backfill_run_id,
                prefix="progress initial",
            )

    processed = 0
    while max_tasks is None or processed < max_tasks:
        limit = batch_size if max_tasks is None else min(batch_size, max_tasks - processed)
        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            tasks = load_pending_tasks(
                session=session,
                backfill_run_id=backfill_run_id,
                limit=limit,
                task_order=task_order,
            )
        if not tasks:
            break
        for task_id in tasks:
            task_report = process_task(
                task_id=task_id,
                lookback_days=lookback_days,
                window_commit_size=window_commit_size,
                progress_every=progress_every,
                prefer_compose_port=prefer_compose_port,
            )
            processed += 1
            report.tasks_processed += 1
            coverage = report.cadence_coverage.setdefault(task_report["cadence"], CadenceBackfillCoverage())
            coverage.expected += task_report["expected_windows"]
            coverage.ran += task_report["ran_windows"]
            coverage.skipped += task_report["skipped_windows"]
            if task_report["status"] == "failed":
                coverage.failed_tasks += 1
            report.skip_reasons.extend(task_report["skip_reasons"])
            if progress_every > 0 and processed % progress_every == 0:
                with session_scope(prefer_compose_port=prefer_compose_port) as session:
                    print_task_progress(
                        session=session,
                        backfill_run_id=backfill_run_id,
                        prefix="progress",
                    )
            if max_tasks is not None and processed >= max_tasks:
                break

    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        report.final_task_progress = task_progress(session=session, backfill_run_id=backfill_run_id)
        remaining = remaining_task_count(session=session, backfill_run_id=backfill_run_id)
        final_status = "running" if remaining else ("completed" if report.success else "failed")
        if refresh_summaries:
            summary_report = refresh_attribution_summaries(
                session=session,
                universe_name=universe_name,
                universe_version=universe_version,
            )
            report.summaries_refreshed = summary_report.refreshed
        finish_backfill_run(
            session=session,
            backfill_run_id=backfill_run_id,
            status=final_status,
            coverage_payload=report.coverage_payload(),
            error_payload=None if final_status != "failed" else {"error": "one_or_more_tasks_failed"},
        )
    return report


def resolve_analysis_dates(
    *,
    session,
    universe_name: str,
    universe_version: str,
    analysis_start: date | None,
    analysis_end: date | None,
) -> tuple[date, date]:
    first_price, last_price = session.execute(
        select(
            func.min(models.ModelUniverseMember.first_price_time),
            func.max(models.ModelUniverseMember.last_price_time),
        )
        .where(models.ModelUniverseMember.universe_name == universe_name)
        .where(models.ModelUniverseMember.universe_version == universe_version)
        .where(models.ModelUniverseMember.eligibility_status == "eligible")
    ).one()
    if first_price is None or last_price is None:
        raise RuntimeError(f"no eligible universe members found for {universe_name}/{universe_version}")
    start = analysis_start or first_price.date()
    end = analysis_end or last_price.date()
    if end <= start:
        raise ValueError("analysis end must be after analysis start")
    return start, end


def resolve_backfill_run_id(
    *,
    session,
    backfill_run_id: uuid.UUID | None,
    universe_name: str,
    universe_version: str,
) -> uuid.UUID:
    if backfill_run_id is not None:
        return backfill_run_id
    resolved = session.execute(
        select(models.BackfillRun.backfill_run_id)
        .where(models.BackfillRun.config_version == f"{universe_name}:{universe_version}")
        .order_by(models.BackfillRun.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if resolved is None:
        raise RuntimeError(f"no backfill run found for {universe_name}:{universe_version}")
    return resolved


def create_backfill_run(
    *,
    session,
    universe_name: str,
    universe_version: str,
    analysis_start: date,
    analysis_end: date,
    cadences: tuple[str, ...],
    lookback_days: int,
) -> uuid.UUID:
    backfill_run_id = uuid.uuid4()
    session.add(
        models.BackfillRun(
            backfill_run_id=backfill_run_id,
            config_version=f"{universe_name}:{universe_version}",
            analysis_start=_date_to_utc_datetime(analysis_start),
            analysis_end=_date_to_utc_datetime(analysis_end),
            data_start=_date_to_utc_datetime(analysis_start) - timedelta(days=lookback_days * 2),
            data_end=_date_to_utc_datetime(analysis_end),
            cadences=list(cadences),
            lookback_days=lookback_days,
            status="running",
            started_at=datetime.now(timezone.utc),
            finished_at=None,
            coverage_payload={},
            error_payload=None,
        )
    )
    session.flush()
    return backfill_run_id


def ensure_backfill_tasks(
    *,
    session,
    backfill_run_id: uuid.UUID,
    universe_name: str,
    universe_version: str,
    start: datetime,
    end: datetime,
    cadences: tuple[str, ...],
    lookback_days: int,
) -> int:
    members = list(
        session.execute(
            select(models.ModelUniverseMember)
            .where(models.ModelUniverseMember.universe_name == universe_name)
            .where(models.ModelUniverseMember.universe_version == universe_version)
            .where(models.ModelUniverseMember.eligibility_status == "eligible")
            .where(models.ModelUniverseMember.active_to.is_(None))
            .order_by(models.ModelUniverseMember.ticker)
        ).scalars()
    )
    created = 0
    now = datetime.now(timezone.utc)
    for member in members:
        trading_dates = load_trading_dates(
            session=session,
            security_id=member.security_id,
            start=max_datetime(start, member.first_price_time),
            end=min_datetime(end, member.last_price_time),
        )
        for cadence in cadences:
            windows = valid_windows_for_backfill(
                trading_dates=trading_dates,
                cadence=cadence,
                first_price_time=member.first_price_time,
                lookback_days=lookback_days,
            )
            stmt = insert(models.AttributionBackfillTask).values(
                attribution_backfill_task_id=stable_uuid(
                    f"backfill-task:{backfill_run_id}:{member.security_id}:{cadence}"
                ),
                backfill_run_id=backfill_run_id,
                universe_name=universe_name,
                universe_version=universe_version,
                security_id=member.security_id,
                ticker=member.ticker,
                cadence=cadence,
                status="pending",
                expected_windows=len(windows),
                ran_windows=0,
                skipped_windows=0,
                last_window_end=None,
                error_payload=None,
                created_at=now,
                started_at=None,
                finished_at=None,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_nothing(constraint="uq_attribution_backfill_task_run_security")
            result = session.execute(stmt)
            created += int(result.rowcount or 0)
    session.flush()
    return created


def load_pending_tasks(
    *,
    session,
    backfill_run_id: uuid.UUID,
    limit: int,
    task_order: str = "expected-windows",
) -> list[uuid.UUID]:
    rows = session.execute(
        pending_tasks_statement(
            backfill_run_id=backfill_run_id,
            limit=limit,
            task_order=task_order,
        )
    ).scalars()
    return list(rows)


def pending_tasks_statement(*, backfill_run_id: uuid.UUID, limit: int, task_order: str = "expected-windows"):
    stmt = (
        select(models.AttributionBackfillTask.attribution_backfill_task_id)
        .where(models.AttributionBackfillTask.backfill_run_id == backfill_run_id)
        .where(models.AttributionBackfillTask.status.in_(("pending", "running")))
        .limit(limit)
    )
    if task_order == "expected-windows":
        stmt = stmt.order_by(
            case((models.AttributionBackfillTask.expected_windows == 0, 1), else_=0).asc(),
            models.AttributionBackfillTask.expected_windows.asc(),
            models.AttributionBackfillTask.ticker.asc(),
            models.AttributionBackfillTask.cadence.asc(),
        )
    elif task_order == "ticker":
        stmt = stmt.order_by(models.AttributionBackfillTask.ticker.asc(), models.AttributionBackfillTask.cadence.asc())
    else:
        raise ValueError(f"unknown task_order {task_order}")
    return stmt


def remaining_task_count(*, session, backfill_run_id: uuid.UUID) -> int:
    return int(
        session.execute(
            select(func.count(models.AttributionBackfillTask.attribution_backfill_task_id))
            .where(models.AttributionBackfillTask.backfill_run_id == backfill_run_id)
            .where(models.AttributionBackfillTask.status.in_(("pending", "running")))
        ).scalar_one()
    )


def task_progress(*, session, backfill_run_id: uuid.UUID) -> dict[str, object]:
    status_counts = {
        status: int(count)
        for status, count in session.execute(
            select(models.AttributionBackfillTask.status, func.count())
            .where(models.AttributionBackfillTask.backfill_run_id == backfill_run_id)
            .group_by(models.AttributionBackfillTask.status)
        ).all()
    }
    totals = session.execute(
        select(
            func.coalesce(func.sum(models.AttributionBackfillTask.expected_windows), 0),
            func.coalesce(func.sum(models.AttributionBackfillTask.ran_windows), 0),
            func.coalesce(func.sum(models.AttributionBackfillTask.skipped_windows), 0),
        ).where(models.AttributionBackfillTask.backfill_run_id == backfill_run_id)
    ).one()
    current = session.execute(
        select(
            models.AttributionBackfillTask.ticker,
            models.AttributionBackfillTask.cadence,
            models.AttributionBackfillTask.last_window_end,
            models.AttributionBackfillTask.ran_windows,
            models.AttributionBackfillTask.expected_windows,
        )
        .where(models.AttributionBackfillTask.backfill_run_id == backfill_run_id)
        .where(models.AttributionBackfillTask.status == "running")
        .order_by(models.AttributionBackfillTask.updated_at.desc())
        .limit(1)
    ).one_or_none()
    total_tasks = sum(status_counts.values())
    completed_tasks = status_counts.get("completed", 0)
    skipped_tasks = status_counts.get("skipped", 0)
    failed_tasks = status_counts.get("failed", 0)
    finished_tasks = completed_tasks + skipped_tasks + failed_tasks
    progress = {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "finished_tasks": finished_tasks,
        "pending_tasks": status_counts.get("pending", 0),
        "running_tasks": status_counts.get("running", 0),
        "skipped_tasks": skipped_tasks,
        "failed_tasks": failed_tasks,
        "expected_windows": int(totals[0] or 0),
        "ran_windows": int(totals[1] or 0),
        "skipped_windows": int(totals[2] or 0),
    }
    if current is not None:
        progress.update(
            {
                "current_ticker": current.ticker,
                "current_cadence": current.cadence,
                "current_last_window_end": current.last_window_end.isoformat()
                if current.last_window_end is not None
                else None,
                "current_ran_windows": int(current.ran_windows or 0),
                "current_expected_windows": int(current.expected_windows or 0),
            }
        )
    return progress


def print_task_progress(*, session, backfill_run_id: uuid.UUID, prefix: str = "progress") -> None:
    print(
        f"{prefix} backfill_run_id={backfill_run_id} {format_task_progress(task_progress(session=session, backfill_run_id=backfill_run_id))}",
        flush=True,
    )


def format_task_progress(progress: dict[str, object]) -> str:
    if not progress:
        return "tasks_completed=0/0 tasks_finished=0/0 pending=0 running=0 failed=0 windows_ran=0 windows_skipped=0"
    total = progress.get("total_tasks", 0)
    text = (
        f"tasks_completed={progress.get('completed_tasks', 0)}/{total} "
        f"tasks_finished={progress.get('finished_tasks', 0)}/{total} "
        f"pending={progress.get('pending_tasks', 0)} "
        f"running={progress.get('running_tasks', 0)} "
        f"skipped_tasks={progress.get('skipped_tasks', 0)} "
        f"failed={progress.get('failed_tasks', 0)} "
        f"windows_ran={progress.get('ran_windows', 0)}/{progress.get('expected_windows', 0)} "
        f"windows_skipped={progress.get('skipped_windows', 0)}"
    )
    if progress.get("current_ticker"):
        text += (
            f" current_ticker={progress.get('current_ticker')} "
            f"current_cadence={progress.get('current_cadence')} "
            f"current_windows={progress.get('current_ran_windows', 0)}/{progress.get('current_expected_windows', 0)} "
            f"current_last_window_end={progress.get('current_last_window_end')}"
        )
    return text


def process_task(
    *,
    task_id: uuid.UUID,
    lookback_days: int,
    window_commit_size: int = 25,
    progress_every: int = 0,
    prefer_compose_port: bool,
) -> dict:
    skip_reasons: list[str] = []
    cutoff = datetime.now(timezone.utc)
    try:
        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            task = session.get(models.AttributionBackfillTask, task_id)
            if task is None:
                raise RuntimeError(f"backfill task {task_id} not found")
            task.status = "running"
            task.started_at = task.started_at or cutoff
            task.updated_at = cutoff
            member = session.execute(
                select(models.ModelUniverseMember)
                .where(models.ModelUniverseMember.universe_name == task.universe_name)
                .where(models.ModelUniverseMember.universe_version == task.universe_version)
                .where(models.ModelUniverseMember.security_id == task.security_id)
                .limit(1)
            ).scalar_one()
            backfill_run = session.get(models.BackfillRun, task.backfill_run_id)
            if backfill_run is None:
                raise RuntimeError(f"backfill run {task.backfill_run_id} not found")
            security = session.get(models.Security, task.security_id)
            if security is None:
                raise RuntimeError(f"security {task.security_id} not found")
            if task.expected_windows <= 0:
                task.status = "skipped"
                task.finished_at = datetime.now(timezone.utc)
                task.updated_at = task.finished_at
                return task_payload(task=task, skip_reasons=["no valid attribution windows"])

            task_state = {
                "backfill_run_id": task.backfill_run_id,
                "ticker": task.ticker,
                "cadence": task.cadence,
                "security_id": task.security_id,
                "last_window_end": task.last_window_end,
                "analysis_start": backfill_run.analysis_start,
                "analysis_end": backfill_run.analysis_end,
                "first_price_time": member.first_price_time,
                "last_price_time": member.last_price_time,
                "security": security,
            }

        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            price_window = TimeWindow(
                start=task_state["first_price_time"],
                end=task_state["last_price_time"],
            )
            price_bars = load_engine_price_bars(
                session=session,
                security_id=task_state["security_id"],
                window=price_window,
                through=task_state["last_price_time"],
                attribution_cutoff=cutoff,
            )
            sector_factor_names = load_active_sector_factor_names(
                session=session,
                security_id=task_state["security_id"],
                attribution_cutoff=cutoff,
            )
            preloaded_factor_returns = load_factor_returns_by_name(
                session=session,
                factor_names=tuple(sorted(set(FRENCH_FACTOR_NAMES) | set(sector_factor_names))),
                window=price_window,
                attribution_cutoff=cutoff,
            )
            preloaded_macro_values = {
                name: load_macro_values(
                    session=session,
                    series_name=name,
                    window=price_window,
                    attribution_cutoff=cutoff,
                )
                for name in ("DGS2", "DGS10", "BAMLH0A0HYM2", "BAMLC0A0CM", "VIXCLS", "T5YIE")
            }
            preloaded_peer_context = load_active_peer_context(
                session=session,
                security_id=task_state["security_id"],
                price_window=price_window,
                through=task_state["last_price_time"],
                attribution_cutoff=cutoff,
            )

        trading_dates = [
            bar.event_time
            for bar in price_bars
            if task_state["analysis_start"] <= bar.event_time <= task_state["analysis_end"]
        ]
        windows = valid_windows_for_backfill(
            trading_dates=trading_dates,
            cadence=task_state["cadence"],
            first_price_time=task_state["first_price_time"],
            lookback_days=lookback_days,
        )
        windows = windows_after_checkpoint(windows=windows, last_window_end=task_state["last_window_end"])

        for chunk in chunked_windows(windows=windows, size=window_commit_size):
            chunk_report = process_window_chunk(
                task_id=task_id,
                ticker=task_state["ticker"],
                cadence=task_state["cadence"],
                security=task_state["security"],
                windows=chunk,
                cutoff=cutoff,
                lookback_days=lookback_days,
                price_bars=price_bars,
                preloaded_factor_returns=preloaded_factor_returns,
                preloaded_macro_values=preloaded_macro_values,
                preloaded_peer_context=preloaded_peer_context,
                prefer_compose_port=prefer_compose_port,
            )
            skip_reasons.extend(chunk_report["skip_reasons"])
            if progress_every > 0 and chunk_report["processed_windows"] >= progress_every:
                with session_scope(prefer_compose_port=prefer_compose_port) as session:
                    print_task_progress(
                        session=session,
                        backfill_run_id=task_state["backfill_run_id"],
                        prefix="progress window",
                    )

        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            task = session.get(models.AttributionBackfillTask, task_id)
            if task is None:
                raise RuntimeError(f"backfill task {task_id} not found")
            task.status = "completed"
            task.finished_at = datetime.now(timezone.utc)
            task.updated_at = task.finished_at
            task.error_payload = None
            return task_payload(task=task, skip_reasons=skip_reasons)
    except Exception as exc:
        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            task = session.get(models.AttributionBackfillTask, task_id)
            if task is None:
                raise
            task.status = "failed"
            task.finished_at = datetime.now(timezone.utc)
            task.updated_at = task.finished_at
            task.error_payload = {"error": str(exc)}
            reason = str(exc).splitlines()[0]
            skip_reasons.append(f"{task.ticker} {task.cadence}: {reason}")
            return task_payload(task=task, skip_reasons=skip_reasons)


def process_window_chunk(
    *,
    task_id: uuid.UUID,
    ticker: str,
    cadence: str,
    security: models.Security,
    windows: list[TimeWindow],
    cutoff: datetime,
    lookback_days: int,
    price_bars,
    preloaded_factor_returns,
    preloaded_macro_values,
    preloaded_peer_context,
    prefer_compose_port: bool,
) -> dict:
    ran = 0
    skipped = 0
    skip_reasons = []
    last_window_end = None
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        task = session.get(models.AttributionBackfillTask, task_id)
        if task is None:
            raise RuntimeError(f"backfill task {task_id} not found")
        for window in windows:
            try:
                run_attribution_for_security(
                    session=session,
                    security=security,
                    window=window,
                    attribution_cutoff=cutoff,
                    use_expanded_mvp=True,
                    include_event_evidence=True,
                    lookback_days=lookback_days,
                    cadence=cadence,
                    preloaded_price_bars=price_bars,
                    preloaded_factor_returns_by_name=preloaded_factor_returns,
                    preloaded_macro_values_by_name=preloaded_macro_values,
                    preloaded_peer_context=preloaded_peer_context,
                )
                ran += 1
            except (RuntimeError, ValueError) as exc:
                skipped += 1
                reason = str(exc).splitlines()[0]
                skip_reasons.append(f"{ticker} {cadence}: {reason}")
            last_window_end = window.end

        task.ran_windows = int(task.ran_windows or 0) + ran
        task.skipped_windows = int(task.skipped_windows or 0) + skipped
        if last_window_end is not None:
            task.last_window_end = last_window_end
        task.updated_at = datetime.now(timezone.utc)
    return {
        "ran_windows": ran,
        "skipped_windows": skipped,
        "processed_windows": ran + skipped,
        "skip_reasons": skip_reasons,
    }


def task_payload(*, task, skip_reasons: list[str]) -> dict:
    return {
        "ticker": task.ticker,
        "cadence": task.cadence,
        "status": task.status,
        "expected_windows": int(task.expected_windows or 0),
        "ran_windows": int(task.ran_windows or 0),
        "skipped_windows": int(task.skipped_windows or 0),
        "skip_reasons": skip_reasons,
    }


def valid_windows_for_backfill(
    *,
    trading_dates: list[datetime],
    cadence: str,
    first_price_time: datetime | None,
    lookback_days: int,
) -> list[TimeWindow]:
    if first_price_time is None:
        return []
    minimum_start = first_price_time + timedelta(days=lookback_days)
    return [
        window
        for window in build_windows(trading_dates=trading_dates, cadence=cadence)
        if window.start >= minimum_start
    ]


def windows_after_checkpoint(
    *,
    windows: list[TimeWindow],
    last_window_end: datetime | None,
) -> list[TimeWindow]:
    if last_window_end is None:
        return windows
    return [window for window in windows if window.end > last_window_end]


def chunked_windows(*, windows: list[TimeWindow], size: int) -> list[list[TimeWindow]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [windows[index : index + size] for index in range(0, len(windows), size)]


def finish_backfill_run(
    *,
    session,
    backfill_run_id: uuid.UUID,
    status: str,
    coverage_payload: dict,
    error_payload: dict | None,
) -> None:
    run = session.get(models.BackfillRun, backfill_run_id)
    if run is None:
        raise RuntimeError(f"backfill run {backfill_run_id} not found")
    run.status = status
    run.finished_at = None if status == "running" else datetime.now(timezone.utc)
    run.coverage_payload = coverage_payload
    run.error_payload = error_payload


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def max_datetime(left: datetime, right: datetime | None) -> datetime:
    return max(left, right) if right is not None else left


def min_datetime(left: datetime, right: datetime | None) -> datetime:
    return min(left, right) if right is not None else left


if __name__ == "__main__":
    main()
