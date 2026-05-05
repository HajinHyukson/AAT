from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from math import inf, nan

from jobs.faustcalc_common import (
    canonical_ticker,
    get_faustcalc_database_url,
    jsonable_mapping,
    normalize_cik,
)


def test_canonical_ticker_normalizes_share_class_aliases() -> None:
    assert canonical_ticker("brk-b") == "BRK.B"
    assert canonical_ticker("BRK/B") == "BRK.B"
    assert canonical_ticker("aapl") == "AAPL"


def test_normalize_cik_zero_pads_digits_only() -> None:
    assert normalize_cik("CIK 320193") == "0000320193"
    assert normalize_cik(None) is None
    assert normalize_cik("not available") is None


def test_jsonable_mapping_preserves_audit_payloads() -> None:
    payload = jsonable_mapping(
        {
            "as_of": date(2026, 1, 30),
            "seen_at": datetime(2026, 1, 30, 12, 5, tzinfo=timezone.utc),
            "amount": Decimal("12.34"),
            "not_a_number": nan,
            "infinite": inf,
            "decimal_nan": Decimal("NaN"),
            "nested": {"items": [Decimal("1.5")]},
        }
    )

    assert payload == {
        "as_of": "2026-01-30",
        "seen_at": "2026-01-30T12:05:00+00:00",
        "amount": 12.34,
        "not_a_number": None,
        "infinite": None,
        "decimal_nan": None,
        "nested": {"items": [1.5]},
    }


def test_faustcalc_database_url_does_not_reuse_aat_database_name(monkeypatch) -> None:
    monkeypatch.setenv("FAUSTCALC_DATABASE_URL", "")
    monkeypatch.setenv("FAUSTCALC_PGUSER", "faustcalc")
    monkeypatch.setenv("FAUSTCALC_PGPASSWORD", "secret")
    monkeypatch.setenv("FAUSTCALC_PGHOST", "localhost")
    monkeypatch.setenv("FAUSTCALC_PGPORT", "5432")
    monkeypatch.delenv("FAUSTCALC_PGDATABASE", raising=False)
    monkeypatch.setenv("PGDATABASE", "attribution")

    url = get_faustcalc_database_url()

    assert url.endswith("/faustcalc")


def test_faustcalc_database_url_can_use_faustcalc_env_file(tmp_path, monkeypatch) -> None:
    source_env = tmp_path / ".env"
    source_env.write_text(
        "\n".join(
            [
                "PGHOST=source-db",
                "PGPORT=6543",
                "PGDATABASE=faust_source",
                "PGUSER=faust_user",
                "PGPASSWORD=faust secret",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FAUSTCALC_DATABASE_URL", "")
    monkeypatch.setenv("FAUSTCALC_ENV_FILE", str(source_env))
    for key in [
        "FAUSTCALC_PGHOST",
        "FAUSTCALC_PGPORT",
        "FAUSTCALC_PGDATABASE",
        "FAUSTCALC_PGUSER",
        "FAUSTCALC_PGPASSWORD",
    ]:
        monkeypatch.delenv(key, raising=False)

    url = get_faustcalc_database_url()

    assert url == "postgresql+psycopg://faust_user:faust%20secret@source-db:6543/faust_source"
