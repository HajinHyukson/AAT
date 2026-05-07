from __future__ import annotations

import pytest

from jobs.pilot_sp500_common import (
    PILOT_DATABASE_NAME,
    PilotSecurity,
    assert_pilot_database_url,
    ensure_pilot_database_url,
    load_pilot_universe_config,
    peer_candidates,
    pilot_database_url,
    pilot_securities,
    ticker_fetch_attempts,
)


def test_static_sp500_config_contains_share_class_aliases() -> None:
    payload = load_pilot_universe_config()
    rows = {item.ticker: item for item in pilot_securities(payload)}

    assert len(rows) >= 500
    assert ticker_fetch_attempts(rows["BRK.B"])[:2] == ("BRK.B", "BRK-B")


def test_pilot_database_url_guard_rejects_non_pilot_database(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution")

    with pytest.raises(RuntimeError, match=PILOT_DATABASE_NAME):
        assert_pilot_database_url()


def test_pilot_database_url_guard_accepts_pilot_database(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        f"postgresql+psycopg://attribution:attribution@localhost:55432/{PILOT_DATABASE_NAME}",
    )

    assert_pilot_database_url()


def test_ensure_pilot_database_url_defaults_to_local_pilot(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST_PORT", "55432")

    database_url = ensure_pilot_database_url()

    assert database_url == pilot_database_url()
    assert database_url.endswith(f"/{PILOT_DATABASE_NAME}")


def test_peer_candidates_are_deterministic_and_exclude_target() -> None:
    target = pilot_security("AAA", sector="Tech", subindustry="Software")
    peers = [
        pilot_security("DDD", sector="Tech", subindustry="Software"),
        pilot_security("CCC", sector="Tech", subindustry="Software"),
        pilot_security("BBB", sector="Tech", subindustry="Hardware"),
    ]

    result = peer_candidates(target=target, securities=[target, *peers], max_peers=3)

    assert [item.ticker for item in result] == ["CCC", "DDD", "BBB"]


def pilot_security(ticker: str, *, sector: str, subindustry: str) -> PilotSecurity:
    return PilotSecurity(
        ticker=ticker,
        name=ticker,
        cik=None,
        exchange="NYSE",
        sector=sector,
        industry=subindustry,
        subindustry=subindustry,
        vendor_aliases=(),
        payload={},
    )
