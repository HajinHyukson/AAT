from __future__ import annotations

import os

from jobs.populate_pilot_sp500_data import RequestPacer, load_fmp_dotenv_overrides


def test_fmp_request_pacer_defaults_to_300_calls_per_minute(monkeypatch) -> None:
    monkeypatch.delenv("FMP_MIN_REQUEST_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("FMP_RATE_LIMIT_PER_MIN", raising=False)
    pacer = RequestPacer(
        min_interval_env_var="FMP_MIN_REQUEST_INTERVAL_SECONDS",
        rate_limit_env_var="FMP_RATE_LIMIT_PER_MIN",
        default_rate_limit_per_minute=300,
    )

    assert pacer.min_interval_seconds() == 0.2


def test_fmp_request_pacer_uses_configured_rate_limit(monkeypatch) -> None:
    monkeypatch.delenv("FMP_MIN_REQUEST_INTERVAL_SECONDS", raising=False)
    monkeypatch.setenv("FMP_RATE_LIMIT_PER_MIN", "120")
    pacer = RequestPacer(
        min_interval_env_var="FMP_MIN_REQUEST_INTERVAL_SECONDS",
        rate_limit_env_var="FMP_RATE_LIMIT_PER_MIN",
        default_rate_limit_per_minute=300,
    )

    assert pacer.min_interval_seconds() == 0.5


def test_fmp_request_pacer_allows_explicit_override(monkeypatch) -> None:
    monkeypatch.setenv("FMP_MIN_REQUEST_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("FMP_RATE_LIMIT_PER_MIN", "120")
    pacer = RequestPacer(
        min_interval_env_var="FMP_MIN_REQUEST_INTERVAL_SECONDS",
        rate_limit_env_var="FMP_RATE_LIMIT_PER_MIN",
        default_rate_limit_per_minute=300,
    )

    assert pacer.min_interval_seconds() == 0.0


def test_fmp_dotenv_overrides_stale_process_env(monkeypatch, tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "FMP_API_KEY=good-key-from-dotenv",
                "FMP_RATE_LIMIT_PER_MIN=300",
                "DATABASE_URL=postgresql+psycopg://server-db",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FMP_API_KEY", "stale-key-from-shell")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://pilot-db")

    load_fmp_dotenv_overrides(env_path)

    assert os.environ["FMP_API_KEY"] == "good-key-from-dotenv"
    assert os.environ["FMP_RATE_LIMIT_PER_MIN"] == "300"
    assert os.environ["DATABASE_URL"] == "postgresql+psycopg://pilot-db"
