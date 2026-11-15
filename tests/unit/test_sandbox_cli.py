from datetime import date

import polars as pl

from viza_sandbox.cli import main, split_adjustment_verdict


def test_create_user_prints_token_once(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VIZA_SANDBOX_DATABASE_URL", f"sqlite:///{tmp_path/'s.db'}")
    assert main(["init-db"]) == 0
    assert main(["create-user", "--name", "alice", "--owner"]) == 0
    out = capsys.readouterr().out
    assert "user_id=" in out and "token=" in out


def test_split_verdict_detects_ten_for_one():
    bars = pl.DataFrame(
        {
            "event_date": [date(2024, 6, 7), date(2024, 6, 10)],
            "close": [1208.88, 121.79],
            "adjusted_close": [1208.88, 121.79],
        }
    )
    assert split_adjustment_verdict(bars) == "unadjusted"
    flat = pl.DataFrame(
        {
            "event_date": [date(2024, 6, 7), date(2024, 6, 10)],
            "close": [120.89, 121.79],
            "adjusted_close": [120.89, 121.79],
        }
    )
    assert split_adjustment_verdict(flat) == "no_split_signature"


def test_init_db_redacts_password(monkeypatch, capsys):
    from viza_sandbox import cli

    class FakeStore:
        def __init__(self, url):
            pass

        def create_schema(self):
            pass

    monkeypatch.setattr(cli, "SandboxStore", FakeStore)
    monkeypatch.setenv("VIZA_SANDBOX_DATABASE_URL", "postgresql+psycopg://u:secret@host/db")
    assert main(["init-db"]) == 0
    out = capsys.readouterr().out
    assert "secret" not in out and "u:***@host/db" in out


def test_check_split_adjustment_fails_closed_without_canonical_url(monkeypatch, capsys):
    monkeypatch.delenv("VIZA_SANDBOX_CANONICAL_DATABASE_URL", raising=False)
    code = main(["check-split-adjustment", "--ticker", "NVDA", "--from", "2024-06-05",
                 "--to", "2024-06-12"])
    assert code != 0
    assert "VIZA_SANDBOX_CANONICAL_DATABASE_URL is required" in capsys.readouterr().err
