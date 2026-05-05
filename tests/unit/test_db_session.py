from __future__ import annotations

from db.session import make_engine, make_session_factory


def test_session_factory_reuses_cached_engine(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
    make_engine.cache_clear()
    make_session_factory.cache_clear()

    first = make_session_factory(prefer_compose_port=False)
    second = make_session_factory(prefer_compose_port=False)

    assert first is second
    assert first.kw["bind"] is second.kw["bind"]
