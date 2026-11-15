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


def _fake_source(bars):
    class FakeSource:
        def __init__(self, url):
            pass

        def securities(self):
            return pl.DataFrame({"security_id": ["s1"], "ticker": ["NVDA"]})

        def price_bars(self, start, end, **kwargs):
            return bars

    return FakeSource


def _bars(closes):
    return pl.DataFrame(
        {
            "security_id": ["s1"] * len(closes),
            "event_date": [date(2024, 6, 7 + i) for i in range(len(closes))],
            "close": closes,
            "adjusted_close": closes,
        },
        schema={
            "security_id": pl.Utf8,
            "event_date": pl.Date,
            "close": pl.Float64,
            "adjusted_close": pl.Float64,
        },
    )


def test_check_split_adjustment_refuses_verdict_on_fewer_than_two_bars(monkeypatch, capsys):
    from viza_sandbox import cli

    monkeypatch.setenv("VIZA_SANDBOX_CANONICAL_DATABASE_URL", "sqlite://")
    for closes in ([], [120.0]):
        monkeypatch.setattr(cli, "PostgresCanonicalSource", _fake_source(_bars(closes)))
        code = main(["check-split-adjustment", "--ticker", "NVDA", "--from", "2024-06-05",
                     "--to", "2024-06-12"])
        captured = capsys.readouterr()
        assert code != 0
        assert "verdict=" not in captured.out
        assert "NVDA" in captured.err and "2024-06-05" in captured.err
        assert f"{len(closes)} bar" in captured.err


def test_check_split_adjustment_prints_verdict_with_two_bars(monkeypatch, capsys):
    from viza_sandbox import cli

    monkeypatch.setenv("VIZA_SANDBOX_CANONICAL_DATABASE_URL", "sqlite://")
    monkeypatch.setattr(cli, "PostgresCanonicalSource", _fake_source(_bars([1208.88, 121.79])))
    code = main(["check-split-adjustment", "--ticker", "NVDA", "--from", "2024-06-05",
                 "--to", "2024-06-12"])
    assert code == 0
    assert "verdict=unadjusted" in capsys.readouterr().out
