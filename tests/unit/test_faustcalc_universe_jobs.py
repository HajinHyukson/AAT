from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from jobs.build_faustcalc_universe import eligible_member_statement
from jobs.run_faustcalc_attribution_backfill import (
    LOCKED_ELSEWHERE_STATUS,
    choose_candidate_task,
    chunked_windows,
    format_task_progress,
    pending_tasks_statement,
    process_task,
    process_window_chunk,
    task_advisory_lock_key,
    valid_windows_for_backfill,
    windows_after_checkpoint,
)
from jobs.seed_faustcalc_auto_mappings import MappingCandidate, build_peer_candidates


def test_faustcalc_universe_eligibility_statement_filters_active_us_stocks() -> None:
    sql = str(
        eligible_member_statement(min_price_bars=2).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "lower(faustcalc_asset.asset_type) = 'stock'" in sql
    assert "upper(faustcalc_asset.currency) = 'USD'" in sql
    assert "faustcalc_asset.is_active IS true" in sql
    assert "anon_1.price_bar_count >= 2" in sql


def test_generated_peer_candidates_are_deterministic_and_exclude_target() -> None:
    target = candidate("AAA", sector="Technology", industry="Software", bars=500)
    peers = [
        target,
        candidate("BBB", sector="Technology", industry="Software", bars=400),
        candidate("CCC", sector="Technology", industry="Software", bars=700),
        candidate("DDD", sector="Technology", industry="Software", bars=700),
        candidate("EEE", sector="Energy", industry="Oil & Gas", bars=900),
    ]

    result = build_peer_candidates(candidates=peers, max_peers=3, min_peers=3)

    assert [item.ticker for item in result[target.security_id]] == ["CCC", "DDD", "BBB"]
    assert target.security_id not in {item.security_id for item in result[target.security_id]}


def test_backfill_windows_start_after_required_lookback() -> None:
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    trading_dates = [
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 2, tzinfo=timezone.utc),
        datetime(2026, 1, 4, tzinfo=timezone.utc),
        datetime(2026, 1, 5, tzinfo=timezone.utc),
    ]

    windows = valid_windows_for_backfill(
        trading_dates=trading_dates,
        cadence="daily",
        first_price_time=first,
        lookback_days=2,
    )

    assert [(window.start, window.end) for window in windows] == [
        (
            datetime(2026, 1, 4, tzinfo=timezone.utc),
            datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
    ]


def test_task_progress_format_shows_completed_out_of_total() -> None:
    text = format_task_progress(
        {
            "total_tasks": 37971,
            "completed_tasks": 200,
            "finished_tasks": 201,
            "pending_tasks": 37770,
            "running_tasks": 0,
            "skipped_tasks": 1,
            "failed_tasks": 0,
            "expected_windows": 1_000,
            "ran_windows": 950,
            "skipped_windows": 10,
            "current_ticker": "A",
            "current_cadence": "daily",
            "current_ran_windows": 25,
            "current_expected_windows": 575,
            "current_last_window_end": "2024-08-01T00:00:00+00:00",
            "worker_id": "dev-1",
            "workers": 2,
            "locked_misses": 3,
        }
    )

    assert "tasks_completed=200/37971" in text
    assert "tasks_finished=201/37971" in text
    assert "windows_ran=950/1000" in text
    assert "current_ticker=A" in text
    assert "current_windows=25/575" in text
    assert "worker_id=dev-1" in text
    assert "workers=2" in text
    assert "locked_misses=3" in text


def test_task_advisory_lock_key_is_stable_signed_int64() -> None:
    task_id = uuid4()

    first = task_advisory_lock_key(task_id)
    second = task_advisory_lock_key(task_id)

    assert first == second
    assert -(2**63) <= first < 2**63


def test_choose_candidate_task_skips_inflight_and_deferred_locked() -> None:
    first = uuid4()
    second = uuid4()
    third = uuid4()

    selected = choose_candidate_task(
        candidates=[first, second, third],
        inflight_task_ids={first},
        deferred_locked_task_ids={second},
    )

    assert selected == third


def test_process_task_reports_locked_elsewhere_without_work(monkeypatch) -> None:
    task_id = uuid4()

    monkeypatch.setattr("jobs.run_faustcalc_attribution_backfill.try_acquire_task_lock", lambda **_kwargs: None)

    report = process_task(
        task_id=task_id,
        lookback_days=252,
        window_commit_size=25,
        progress_every=0,
        prefer_compose_port=True,
    )

    assert report["status"] == LOCKED_ELSEWHERE_STATUS
    assert report["ticker"] == str(task_id)


def test_pending_tasks_statement_orders_by_expected_windows() -> None:
    sql = str(
        pending_tasks_statement(
            backfill_run_id=uuid4(),
            limit=200,
            task_order="expected-windows",
        ).compile(dialect=postgresql.dialect())
    )

    assert "attribution_backfill_task.expected_windows ASC" in sql
    assert "CASE WHEN (attribution_backfill_task.expected_windows = " in sql


def test_window_helpers_resume_after_checkpoint_and_chunk() -> None:
    windows = [
        window("2026-01-01", "2026-01-02"),
        window("2026-01-02", "2026-01-03"),
        window("2026-01-03", "2026-01-04"),
        window("2026-01-04", "2026-01-05"),
        window("2026-01-05", "2026-01-06"),
    ]

    remaining = windows_after_checkpoint(
        windows=windows,
        last_window_end=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    assert [item.end for item in remaining] == [
        datetime(2026, 1, 4, tzinfo=timezone.utc),
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        datetime(2026, 1, 6, tzinfo=timezone.utc),
    ]
    assert [len(chunk) for chunk in chunked_windows(windows=remaining, size=2)] == [2, 1]


def test_process_window_chunk_checkpoints_counts(monkeypatch) -> None:
    task_id = uuid4()
    task = type(
        "Task",
        (),
        {
            "ran_windows": 2,
            "skipped_windows": 1,
            "last_window_end": None,
            "updated_at": None,
        },
    )()
    calls = []

    class FakeSession:
        def get(self, _model, requested_id):
            assert requested_id == task_id
            return task

    class FakeScope:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, *_args):
            return False

    def fake_session_scope(**_kwargs):
        return FakeScope()

    def fake_run_attribution_for_security(**kwargs):
        calls.append(kwargs["window"])
        if len(calls) == 2:
            raise ValueError("synthetic skip")

    monkeypatch.setattr("jobs.run_faustcalc_attribution_backfill.session_scope", fake_session_scope)
    monkeypatch.setattr(
        "jobs.run_faustcalc_attribution_backfill.run_attribution_for_security",
        fake_run_attribution_for_security,
    )

    report = process_window_chunk(
        task_id=task_id,
        ticker="A",
        cadence="daily",
        security=object(),
        windows=[
            window("2026-01-01", "2026-01-02"),
            window("2026-01-02", "2026-01-03"),
            window("2026-01-03", "2026-01-04"),
        ],
        cutoff=datetime(2026, 1, 10, tzinfo=timezone.utc),
        lookback_days=252,
        price_bars=[],
        preloaded_factor_returns={},
        preloaded_macro_values={},
        preloaded_peer_context=None,
        prefer_compose_port=True,
    )

    assert report["ran_windows"] == 2
    assert report["skipped_windows"] == 1
    assert task.ran_windows == 4
    assert task.skipped_windows == 2
    assert task.last_window_end == datetime(2026, 1, 4, tzinfo=timezone.utc)


def candidate(ticker: str, *, sector: str, industry: str, bars: int) -> MappingCandidate:
    return MappingCandidate(
        security_id=uuid4(),
        company_id=uuid4(),
        ticker=ticker,
        sector=sector,
        industry=industry,
        first_price_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        price_bar_count=bars,
    )


def window(start: str, end: str):
    from engine.contracts import TimeWindow

    return TimeWindow(
        start=datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
        end=datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
    )
