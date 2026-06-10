from __future__ import annotations

import pytest
from fastapi import HTTPException

import api.main as api_main
from jobs.faustcalc_common import DEFAULT_FAUSTCALC_UNIVERSE_NAME, DEFAULT_FAUSTCALC_UNIVERSE_VERSION


def test_default_universe_falls_back_to_faustcalc(monkeypatch) -> None:
    monkeypatch.delenv("AAT_DEFAULT_UNIVERSE_NAME", raising=False)
    monkeypatch.delenv("AAT_DEFAULT_UNIVERSE_VERSION", raising=False)
    assert api_main.default_universe_name() == DEFAULT_FAUSTCALC_UNIVERSE_NAME
    assert api_main.default_universe_version() == DEFAULT_FAUSTCALC_UNIVERSE_VERSION


def test_default_universe_env_override(monkeypatch) -> None:
    monkeypatch.setenv("AAT_DEFAULT_UNIVERSE_NAME", "pilot_kospi_static")
    monkeypatch.setenv("AAT_DEFAULT_UNIVERSE_VERSION", "latest")
    assert api_main.default_universe_name() == "pilot_kospi_static"
    assert api_main.default_universe_version() == "latest"


class _VersionSession:
    def __init__(self, version: str | None):
        self._version = version
        self.executed = 0

    def execute(self, stmt):
        self.executed += 1
        session = self

        class Result:
            def scalar_one_or_none(self):
                return session._version

        return Result()


def test_resolve_universe_version_passthrough() -> None:
    session = _VersionSession("kospi_static_2026_06_01_v0")
    resolved = api_main.resolve_universe_version(
        session=session,
        universe_name="pilot_kospi_static",
        universe_version="explicit_v1",
    )
    assert resolved == "explicit_v1"
    assert session.executed == 0


def test_resolve_universe_version_latest() -> None:
    session = _VersionSession("kospi_static_2026_06_01_v0")
    resolved = api_main.resolve_universe_version(
        session=session,
        universe_name="pilot_kospi_static",
        universe_version="latest",
    )
    assert resolved == "kospi_static_2026_06_01_v0"
    assert session.executed == 1


def test_resolve_universe_version_latest_missing_universe() -> None:
    session = _VersionSession(None)
    with pytest.raises(HTTPException) as excinfo:
        api_main.resolve_universe_version(
            session=session,
            universe_name="missing_universe",
            universe_version="latest",
        )
    assert excinfo.value.status_code == 404
