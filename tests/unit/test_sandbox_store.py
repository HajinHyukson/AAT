from __future__ import annotations

from viza_sandbox.config import SandboxSettings
from viza_sandbox.store import SandboxStore, hash_token


def test_settings_defaults_and_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv("VIZA_SANDBOX_WALL_CLOCK_SECONDS", "30")
    s = SandboxSettings()
    assert s.wall_clock_seconds == 30
    assert s.memory_gb == 8 and s.cpus == 2 and s.runner == "docker"
    assert s.price_adjustment_status == "unverified"


def test_create_user_returns_token_once_and_resolves(tmp_path):
    store = SandboxStore(f"sqlite:///{tmp_path/'s.db'}")
    store.create_schema()
    user, token = store.create_user("alice", is_owner=True)
    assert user.token_hash == hash_token(token)
    assert store.user_for_token(token).user_id == user.user_id
    assert store.user_for_token("wrong") is None


def test_run_lifecycle(tmp_path):
    store = SandboxStore(f"sqlite:///{tmp_path/'s.db'}")
    store.create_schema()
    user, _ = store.create_user("bob")
    run = store.create_run(
        user.user_id, "def strategy(data): ...", {"start": "2024-01-01"}, {"cpus": 2}
    )
    assert run.status == "queued" and len(run.code_hash) == 64
    updated = store.update_run(run.run_id, status="completed", exit_code=0)
    assert updated.status == "completed"
    assert [r.run_id for r in store.list_runs(user.user_id)] == [run.run_id]
