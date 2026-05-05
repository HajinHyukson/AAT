from __future__ import annotations

import hashlib
import math
import os
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config.env import load_dotenv


FAUSTCALC_FEATURE_STORE_SOURCE = "faustcalc_feature_store"
FAUSTCALC_PRICE_SOURCE = "faustcalc_fmp_snapshot"
FAUSTCALC_SEC_SOURCE = "faustcalc_sec_edgar_snapshot"
DEFAULT_FAUSTCALC_UNIVERSE_NAME = "faustcalc_active_us_equities"
DEFAULT_FAUSTCALC_UNIVERSE_VERSION = "faustcalc_active_us_equities_v0"
FAUSTCALC_AUTO_MAPPING_SOURCE = "faustcalc_auto_mapping"
FAUSTCALC_AUTO_MAPPING_VERSION = "faustcalc_auto_mapping_v0"
DEFAULT_FAUSTCALC_DATA_ROOT = Path.home() / "FaustCalc" / "data"
DEFAULT_FAUSTCALC_ENV_FILE = Path.home() / "FaustCalc" / ".env"
NAMESPACE = uuid.UUID("fba2b46e-fdf6-4f7d-822f-3ef01a8cf4cc")

TICKER_ALIASES = {
    "BRK-B": "BRK.B",
    "BRK/B": "BRK.B",
}


def stable_uuid(value: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, value)


def canonical_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper()
    return TICKER_ALIASES.get(ticker, ticker)


def normalize_cik(value: Any) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    return digits.zfill(10)


def get_faustcalc_data_root(value: str | None = None) -> Path:
    configured = value or os.getenv("FAUSTCALC_DATA_ROOT")
    if configured:
        return Path(configured)
    return DEFAULT_FAUSTCALC_DATA_ROOT


def get_faustcalc_database_url(value: str | None = None) -> str:
    load_dotenv()
    configured = value or os.getenv("FAUSTCALC_DATABASE_URL")
    if configured:
        return normalize_sqlalchemy_url(configured)

    source_env = load_env_file_values(
        Path(os.getenv("FAUSTCALC_ENV_FILE") or DEFAULT_FAUSTCALC_ENV_FILE)
    )
    user = os.getenv("FAUSTCALC_PGUSER") or source_env.get("FAUSTCALC_PGUSER") or source_env.get("PGUSER")
    password = (
        os.getenv("FAUSTCALC_PGPASSWORD")
        or source_env.get("FAUSTCALC_PGPASSWORD")
        or source_env.get("PGPASSWORD")
    )
    host = (
        os.getenv("FAUSTCALC_PGHOST")
        or source_env.get("FAUSTCALC_PGHOST")
        or source_env.get("PGHOST")
        or "localhost"
    )
    port = (
        os.getenv("FAUSTCALC_PGPORT")
        or source_env.get("FAUSTCALC_PGPORT")
        or source_env.get("PGPORT")
        or "5432"
    )
    database = (
        os.getenv("FAUSTCALC_PGDATABASE")
        or source_env.get("FAUSTCALC_PGDATABASE")
        or source_env.get("PGDATABASE")
        or "faustcalc"
    )
    if not user:
        raise RuntimeError(
            "FAUSTCALC_DATABASE_URL is required, or set FAUSTCALC_PGUSER/FAUSTCALC_PGPASSWORD. "
            f"Checked FaustCalc env file at {DEFAULT_FAUSTCALC_ENV_FILE}."
        )
    auth = quote(user, safe="")
    if password is not None:
        auth += f":{quote(password, safe='')}"
    return f"postgresql+psycopg://{auth}@{host}:{port}/{database}"


def load_env_file_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def make_faustcalc_engine(source_database_url: str | None = None) -> Engine:
    return create_engine(get_faustcalc_database_url(source_database_url))


def normalize_sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def fingerprint_database_url(database_url: str) -> str:
    return hashlib.sha256(database_url.encode("utf-8")).hexdigest()


def redact_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if "@" not in parsed.netloc:
        return database_url
    host = parsed.netloc.rsplit("@", 1)[1]
    return urlunsplit((parsed.scheme, f"***@{host}", parsed.path, parsed.query, parsed.fragment))


def parse_optional_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return ensure_utc(value)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return ensure_utc(parsed)


def parse_required_datetime(value: Any) -> datetime:
    parsed = parse_optional_datetime(value)
    if parsed is None:
        raise ValueError("datetime value is required")
    return parsed


def parse_optional_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    if "T" in text:
        return parse_required_datetime(text).date()
    return date.fromisoformat(text)


def parse_required_date(value: Any) -> date:
    parsed = parse_optional_date(value)
    if parsed is None:
        raise ValueError("date value is required")
    return parsed


def date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def jsonable_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: jsonable_value(value) for key, value in row.items()}


def jsonable_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        return float(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, Mapping):
        return jsonable_mapping(value)
    if isinstance(value, list | tuple):
        return [jsonable_value(item) for item in value]
    return value
