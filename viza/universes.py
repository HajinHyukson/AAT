from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.config_paths import display_config_path, resolve_config_path, source_root

REPO_ROOT = source_root()
UNIVERSE_CONFIG_FILES = ("mvp_universe.json", "pilot_sp500_universe.json")
UNIVERSE_CONFIG_PATHS = [resolve_config_path(name) for name in UNIVERSE_CONFIG_FILES]


def default_universe_config_paths() -> list[Path]:
    return [resolve_config_path(name) for name in UNIVERSE_CONFIG_FILES]


class UniverseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    universe_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    asset_count: int = Field(ge=0)
    timestamp_available: datetime | None = None
    config_path: str
    sample_tickers: list[str] = Field(default_factory=list)


class UniverseSecurity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    name: str = Field(min_length=1)
    exchange: str = ""
    sector: str = ""
    industry: str = ""
    subindustry: str = ""
    peers: list[str] = Field(default_factory=list)
    exposures: dict[str, float] = Field(default_factory=dict)


class UniverseDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    universe_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    timestamp_available: datetime | None = None
    config_path: str
    securities: list[UniverseSecurity] = Field(default_factory=list)


def load_universe_summaries(paths: list[Path] | None = None) -> list[UniverseSummary]:
    universe_paths = paths if paths is not None else default_universe_config_paths()
    summaries: list[UniverseSummary] = []
    for path in universe_paths:
        if not path.exists():
            continue
        summaries.append(_load_universe_summary(path))
    return summaries


def load_universe_definition(
    universe_name: str | None = None,
    version: str | None = None,
    paths: list[Path] | None = None,
) -> UniverseDefinition:
    universe_paths = paths if paths is not None else default_universe_config_paths()
    candidates = [_load_universe_definition(path) for path in universe_paths if path.exists()]
    if not candidates:
        raise ValueError("no local VIZA universe definitions are available")

    if universe_name:
        candidates = [item for item in candidates if item.universe_name == universe_name]
    if version:
        version_matches = [item for item in candidates if item.version == version]
        if version_matches:
            candidates = version_matches

    if not candidates:
        requested = ":".join(part for part in [universe_name or "", version or ""] if part)
        raise ValueError(f"unknown local VIZA universe: {requested or 'default'}")

    return candidates[0]


def _load_universe_summary(path: Path) -> UniverseSummary:
    definition = _load_universe_definition(path)

    return UniverseSummary(
        key=definition.key,
        universe_name=definition.universe_name,
        version=definition.version,
        display_name=definition.display_name,
        source=definition.source,
        asset_count=len(definition.securities),
        timestamp_available=definition.timestamp_available,
        config_path=definition.config_path,
        sample_tickers=[security.ticker for security in definition.securities[:8]],
    )


def _load_universe_definition(path: Path) -> UniverseDefinition:
    payload = json.loads(path.read_text(encoding="utf-8"))
    securities = _read_securities(payload)
    universe_name = _read_string(payload.get("universe_name")) or _name_from_path(path)
    version = _read_string(payload.get("version")) or "unknown"
    source = _read_string(payload.get("source")) or path.name
    timestamp = _read_datetime(payload.get("timestamp_available"))

    return UniverseDefinition(
        key=f"{universe_name}:{version}",
        universe_name=universe_name,
        version=version,
        display_name=_display_name(universe_name),
        source=source,
        timestamp_available=timestamp,
        config_path=display_config_path(path),
        securities=[_parse_security(row) for row in securities],
    )


def _read_securities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    securities = payload.get("securities")
    if not isinstance(securities, list):
        return []
    return [row for row in securities if isinstance(row, dict)]


def _read_string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _parse_security(row: dict[str, Any]) -> UniverseSecurity:
    return UniverseSecurity(
        ticker=_read_string(row.get("ticker")),
        name=_read_string(row.get("name")) or _read_string(row.get("company_name")),
        exchange=_read_string(row.get("exchange")),
        sector=_read_string(row.get("sector")),
        industry=_read_string(row.get("industry")),
        subindustry=_read_string(row.get("subindustry")),
        peers=_read_peers(row.get("peers")),
        exposures=_read_exposures(row.get("exposures")),
    )


def _read_peers(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _read_exposures(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}

    exposures: dict[str, float] = {}
    for key, raw_value in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw_value, int | float):
            exposures[key] = float(raw_value)
    return exposures


def _read_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _name_from_path(path: Path) -> str:
    if path.name == "mvp_universe.json":
        return "mvp_50"
    return path.stem


def _display_name(universe_name: str) -> str:
    return universe_name.replace("_", " ").title()
