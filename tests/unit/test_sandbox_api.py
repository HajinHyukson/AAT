import polars as pl
import json
import pytest
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from viza_sandbox.api import create_app
from viza_sandbox.canonical import InMemoryCanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.runner import LocalProcessRunner, RunOutcome
from viza_sandbox.runs import SandboxService, RunRequest
from viza_sandbox.store import SandboxStore

MOMENTUM = (
    "from viza_sandbox.sdk import scores\n"
    "def strategy(data):\n"
    "    return scores(data.prices('close').pct_change(2))\n"
)


def _service(tmp_path):
    days = [date(2024, 1, d) for d in (2, 3, 4, 5, 8, 9, 10, 11)]
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    rows = [
        (s, d, float(p), float(p), 1, "USD", t)
        for s, base in (("a", 10), ("b", 20), ("c", 30))
        for d, p in zip(days, [base + i * (1 if s != "c" else -1) for i in range(len(days))])
    ]
    prices = pl.DataFrame(
        rows,
        schema={
            "security_id": pl.Utf8,
            "event_date": pl.Date,
            "close": pl.Float64,
            "adjusted_close": pl.Float64,
            "volume": pl.Int64,
            "currency": pl.Utf8,
            "ingestion_time": pl.Datetime("us", "UTC"),
        },
        orient="row",
    )
    secs = pl.DataFrame(
        {
            "security_id": ["a", "b", "c"],
            "ticker": ["AAA", "BBB", "CCC"],
            "exchange": ["NYSE"] * 3,
            "currency": ["USD"] * 3,
            "sector": [None] * 3,
            "industry": [None] * 3,
            "classification_as_of": [None] * 3,
        }
    )
    settings = SandboxSettings(
        database_url=f"sqlite:///{tmp_path / 's.db'}",
        data_dir=tmp_path / "data",
        runs_dir=tmp_path / "runs",
        runner="local",
        wall_clock_seconds=120,
    )
    store = SandboxStore(settings.database_url)
    store.create_schema()
    source = InMemoryCanonicalSource(secs, prices)
    service = SandboxService(settings, store, source, LocalProcessRunner())
    return settings, store, service


def _client(tmp_path):
    settings, store, service = _service(tmp_path)
    client = TestClient(create_app(service, store))
    _, token = store.create_user("alice", is_owner=True)
    _, other = store.create_user("mallory")
    return client, {"Authorization": f"Bearer {token}"}, {"Authorization": f"Bearer {other}"}


def _request():
    return {
        "code": MOMENTUM,
        "start": "2024-01-01",
        "end": "2024-01-31",
        "backtest": {"quantiles": 3, "rebalance": "daily"},
    }


def test_end_to_end_momentum_run(tmp_path):
    client, auth, _ = _client(tmp_path)
    created = client.post("/sandbox/runs", json=_request(), headers=auth)
    assert created.status_code == 202
    run_id = created.json()["run_id"]
    result = client.get(f"/sandbox/runs/{run_id}/result", headers=auth)
    assert result.status_code == 200, client.get(f"/sandbox/runs/{run_id}", headers=auth).json()
    body = result.json()
    assert body["header"]["execution"] == {
        "signal_lag_days": 1,
        "transaction_cost": 0.0,
        "benchmark": None,
    }
    manifest = body["header"]["data_manifest"]
    assert manifest["availability_policy_version"] == "faustcalc_fmp_snapshot_eod_policy_v1"
    assert body["header"]["source_rights_state"] == "development_proving"
    assert set(body["evaluation"]["quantile_daily_returns"]) == {"q1", "q2", "q3"}


def test_unauthorized_and_cross_user_404(tmp_path):
    client, auth, other = _client(tmp_path)
    assert client.post("/sandbox/runs", json=_request()).status_code == 401
    run_id = client.post("/sandbox/runs", json=_request(), headers=auth).json()["run_id"]
    assert client.get(f"/sandbox/runs/{run_id}", headers=other).status_code == 404
    assert client.get(f"/sandbox/runs/{run_id}", headers=auth).status_code == 200


def test_failed_run_reports_error_and_result_409(tmp_path):
    client, auth, _ = _client(tmp_path)
    bad = dict(_request(), code="def strategy(data):\n    return data.prices('close')\n")
    run_id = client.post("/sandbox/runs", json=bad, headers=auth).json()["run_id"]
    run = client.get(f"/sandbox/runs/{run_id}", headers=auth).json()["run"]
    assert run["status"] == "failed" and "viza.scores(df)" in run["error"]
    assert client.get(f"/sandbox/runs/{run_id}/result", headers=auth).status_code == 409


def test_same_code_and_manifest_reproduce_identical_evaluation(tmp_path):
    settings, store, service = _service(tmp_path)
    user, _ = store.create_user("alice")
    req = RunRequest(
        code=MOMENTUM,
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        backtest={"quantiles": 3, "rebalance": "daily"},
    )
    first = service.execute(service.submit(user, req).run_id)
    second = service.execute(service.submit(user, req).run_id)
    assert first.data_manifest["manifest_id"] == second.data_manifest["manifest_id"]
    assert first.code_hash == second.code_hash and first.evaluation == second.evaluation


class _StubRunner:
    def __init__(self, exit_code, write_error=None):
        self.exit_code = exit_code
        self.write_error = write_error

    def run(self, run_dir, limits):
        if self.write_error is not None:
            (run_dir / "out" / "error.json").write_text(self.write_error)
        return RunOutcome(
            exit_code=self.exit_code,
            timed_out=False,
            stdout="hello",
            stderr="oops",
            duration_seconds=0.1,
        )


def _stub_run(tmp_path, runner):
    settings, store, service = _service(tmp_path)
    service._runner = runner
    user, _ = store.create_user("alice")
    req = RunRequest(
        code=MOMENTUM,
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        backtest={"quantiles": 3, "rebalance": "daily"},
    )
    return service.execute(service.submit(user, req).run_id), settings


def test_malformed_error_json_still_persists_output(tmp_path):
    run, _ = _stub_run(tmp_path, _StubRunner(1, write_error="{not json"))
    assert run.status == "failed"
    assert run.stdout == "hello" and run.stderr == "oops" and run.exit_code == 1
    assert run.data_manifest is not None and run.finished_at is not None
    assert run.error.startswith("JSONDecodeError: ")


def test_missing_result_parquet_hides_paths_and_keeps_output(tmp_path):
    run, settings = _stub_run(tmp_path, _StubRunner(0))
    assert run.status == "failed"
    assert run.stdout == "hello" and run.exit_code == 0
    assert run.data_manifest is not None and run.finished_at is not None
    assert str(settings.runs_dir) not in run.error and str(tmp_path) not in run.error


class _OutputRunner:
    """Stub runner that leaves crafted files in out/ and exits with ``exit_code``."""

    def __init__(self, exit_code, make_outputs):
        self.exit_code = exit_code
        self.make_outputs = make_outputs

    def run(self, run_dir, limits):
        self.make_outputs(run_dir / "out")
        return RunOutcome(
            exit_code=self.exit_code, timed_out=False, stdout="", stderr="", duration_seconds=0.1
        )


def _write_scores(out_dir, columns=("event_date", "security_id", "score")):
    import pandas as pd

    frame = pd.DataFrame(
        {
            "event_date": pd.to_datetime(["2024-01-03"] * 3),
            "security_id": ["a", "b", "c"],
            "score": [1.0, 2.0, 3.0],
        }
    )
    frame.columns = list(columns)
    frame.to_parquet(out_dir / "result.parquet", index=False)


def _assert_refused(run, settings, tmp_path, message):
    assert run.status == "failed" and run.error == message
    assert run.evaluation is None
    assert str(settings.runs_dir) not in run.error and str(tmp_path) not in run.error


def test_oversized_result_parquet_is_refused(tmp_path):
    settings, store, service = _service(tmp_path)
    assert settings.max_result_bytes == 268435456
    service._settings = settings.model_copy(update={"max_result_bytes": 10})
    service._runner = _OutputRunner(0, _write_scores)
    user, _ = store.create_user("alice")
    req = RunRequest.model_validate(_request())
    run = service.execute(service.submit(user, req).run_id)
    _assert_refused(run, settings, tmp_path, "Result file exceeds the size limit.")


def test_result_parquet_with_wrong_columns_is_refused(tmp_path):
    run, settings = _stub_run(
        tmp_path,
        _OutputRunner(0, lambda out: _write_scores(out, ("event_date", "security_id", "extra"))),
    )
    _assert_refused(
        run,
        settings,
        tmp_path,
        "Result file must have exactly the columns event_date, security_id, score.",
    )


def test_result_parquet_that_is_a_directory_is_refused(tmp_path):
    run, settings = _stub_run(
        tmp_path, _OutputRunner(0, lambda out: (out / "result.parquet").mkdir())
    )
    _assert_refused(run, settings, tmp_path, "Result file is not a regular file.")


def test_result_parquet_symlink_is_refused(tmp_path):
    import os

    target = tmp_path / "elsewhere.parquet"
    _write_scores(tmp_path)
    (tmp_path / "result.parquet").rename(target)

    def make(out):
        try:
            os.symlink(target, out / "result.parquet")
        except OSError:
            pytest.skip("symlinks not permitted on this host")

    run, settings = _stub_run(tmp_path, _OutputRunner(0, make))
    _assert_refused(run, settings, tmp_path, "Result file is not a regular file.")


def test_oversized_error_json_is_refused(tmp_path):
    def make(out):
        big = json.dumps({"type": "ValueError", "message": "x" * (1024 * 1024 + 1)})
        (out / "error.json").write_text(big)

    run, settings = _stub_run(tmp_path, _OutputRunner(1, make))
    _assert_refused(run, settings, tmp_path, "Error file exceeds the size limit.")
    assert run.exit_code == 1


def test_valid_result_parquet_still_completes(tmp_path):
    run, _ = _stub_run(tmp_path, _OutputRunner(0, _write_scores))
    assert run.status == "completed", run.error


def test_result_parquet_junction_is_refused(tmp_path):
    import sys

    if sys.platform != "win32":
        pytest.skip("junctions are Windows-only")
    import _winapi

    target = tmp_path / "elsewhere"
    target.mkdir()
    def make(out):
        _winapi.CreateJunction(str(target), str(out / "result.parquet"))

    run, settings = _stub_run(tmp_path, _OutputRunner(0, make))
    _assert_refused(run, settings, tmp_path, "Result file is not a regular file.")


def test_app_startup_fails_runs_left_queued_or_running(tmp_path):
    settings, store, service = _service(tmp_path)
    user, _ = store.create_user("alice")
    queued = store.create_run(user.user_id, "x", {}, {})
    running = store.create_run(user.user_id, "y", {}, {})
    store.update_run(running.run_id, status="running")
    done = store.create_run(user.user_id, "z", {}, {})
    store.update_run(done.run_id, status="completed")

    create_app(service, store)

    for run_id in (queued.run_id, running.run_id):
        run = store.get_run(run_id)
        assert run.status == "failed"
        assert run.error == "Interrupted by a service restart."
        assert run.finished_at is not None
    untouched = store.get_run(done.run_id)
    assert untouched.status == "completed" and untouched.error is None


class _BlockingRunner:
    def __init__(self):
        import threading

        self.entered = threading.Semaphore(0)
        self.release = threading.Event()

    def run(self, run_dir, limits):
        self.entered.release()
        assert self.release.wait(30)
        return _StubRunner(1).run(run_dir, limits)


def test_runs_beyond_the_concurrency_limit_stay_queued(tmp_path):
    import threading

    settings, store, service = _service(tmp_path)
    assert settings.max_concurrent_runs == 2
    settings = settings.model_copy(update={"max_concurrent_runs": 1})
    runner = _BlockingRunner()
    service = SandboxService(settings, store, service._source, runner)
    user, _ = store.create_user("alice")
    req = RunRequest(
        code=MOMENTUM,
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        backtest={"quantiles": 3, "rebalance": "daily"},
    )
    first = service.submit(user, req).run_id
    second = service.submit(user, req).run_id
    threads = [threading.Thread(target=service.execute, args=(rid,)) for rid in (first, second)]
    threads[0].start()
    assert runner.entered.acquire(timeout=30)
    threads[1].start()
    assert not runner.entered.acquire(timeout=1.0)
    assert store.get_run(first).status == "running"
    assert store.get_run(second).status == "queued"
    runner.release.set()
    for thread in threads:
        thread.join(30)
    assert {store.get_run(first).status, store.get_run(second).status} == {"failed"}


def test_header_discloses_weighting_and_return_basis(tmp_path):
    from viza_sandbox.evaluate import RETURN_BASIS, WEIGHTING_BASIS
    from viza_sandbox.runs import result_header

    assert WEIGHTING_BASIS == (
        "equal weight within each quantile, re-equalized every trading day at zero cost "
        "between rebalances"
    )
    assert RETURN_BASIS == "price return on close; dividends not included"
    settings, store, _ = _service(tmp_path)
    user, _ = store.create_user("alice")
    header = result_header(store.create_run(user.user_id, "x", {}, {}), settings)
    assert header["weighting_basis"] == WEIGHTING_BASIS
    assert header["return_basis"] == RETURN_BASIS


def test_header_rights_and_adjustment_come_from_recorded_manifest(tmp_path):
    from viza_sandbox.runs import result_header

    settings, store, _ = _service(tmp_path)
    user, _ = store.create_user("alice")
    run = store.create_run(user.user_id, "x", {}, {})
    header = result_header(run, settings)
    assert header["source_rights_state"] == settings.source_rights_state
    assert header["price_adjustment_status"] == settings.price_adjustment_status
    run = store.update_run(
        run.run_id,
        data_manifest={"source_rights_state": "licensed", "price_adjustment_status": "adjusted"},
    )
    header = result_header(run, settings)
    assert header["source_rights_state"] == "licensed"
    assert header["price_adjustment_status"] == "adjusted"


def test_get_run_does_not_expose_host_result_path(tmp_path):
    client, auth, _ = _client(tmp_path)
    run_id = client.post("/sandbox/runs", json=_request(), headers=auth).json()["run_id"]
    body = client.get(f"/sandbox/runs/{run_id}", headers=auth).json()
    assert body["run"]["status"] == "completed"
    assert "result_path" not in body["run"]
    assert not any(str(tmp_path) in str(value) for value in body["run"].values())
