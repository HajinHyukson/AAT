import polars as pl
import pytest
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from viza_sandbox.api import create_app
from viza_sandbox.canonical import InMemoryCanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.runner import LocalProcessRunner
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
