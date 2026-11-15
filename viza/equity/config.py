from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from config.env import load_dotenv
from viza.credentials import CredentialStore


TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class EquityRuntimeConfig:
    runtime_handlers_enabled: bool = False
    sec_wedge_enabled: bool = False
    fmp_enabled: bool = False
    fred_enabled: bool = False
    live_integration_tests_enabled: bool = False
    preview_persistence_enabled: bool = False
    preview_replay_refresh_enabled: bool = False

    sec_user_agent: str = "VIZA Equity Module dev@example.com"
    sec_max_rps: int = 5
    sec_cache_ttl_seconds: int = 86400

    fmp_api_key: str | None = field(default=None, repr=False)
    fmp_production_license_confirmed: bool = False
    fmp_max_rps: int = 2
    fmp_cache_ttl_seconds: int = 86400

    fred_api_key: str | None = field(default=None, repr=False)
    fred_max_rps: int = 2
    fred_cache_ttl_seconds: int = 86400
    fred_use_alfred_vintages: bool = False

    @classmethod
    def from_env(cls, *, load_local_dotenv: bool = True) -> "EquityRuntimeConfig":
        if load_local_dotenv:
            load_dotenv()

        return cls(
            runtime_handlers_enabled=_bool_env("VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED", False),
            sec_wedge_enabled=_bool_env("VIZA_EQUITY_SEC_WEDGE_ENABLED", False),
            fmp_enabled=_bool_env("VIZA_EQUITY_FMP_ENABLED", False),
            fred_enabled=_bool_env("VIZA_EQUITY_FRED_ENABLED", False),
            live_integration_tests_enabled=_bool_env(
                "VIZA_EQUITY_LIVE_INTEGRATION_TESTS", False
            ),
            preview_persistence_enabled=_bool_env(
                "VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED", False
            ),
            preview_replay_refresh_enabled=_bool_env(
                "VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED", False
            ),
            sec_user_agent=(
                os.getenv("VIZA_SEC_USER_AGENT")
                or os.getenv("EDGAR_USER_AGENT")
                or "VIZA Equity Module dev@example.com"
            ),
            sec_max_rps=min(_int_env("VIZA_SEC_MAX_RPS", 5), 5),
            sec_cache_ttl_seconds=_int_env("VIZA_SEC_CACHE_TTL_SECONDS", 86400),
            fmp_api_key=_runtime_secret("fmp", "fmp_credential", env_var="FMP_API_KEY"),
            fmp_production_license_confirmed=_bool_env(
                "FMP_PRODUCTION_LICENSE_CONFIRMED", False
            ),
            fmp_max_rps=_int_env("VIZA_FMP_MAX_RPS", 2),
            fmp_cache_ttl_seconds=_int_env("VIZA_FMP_CACHE_TTL_SECONDS", 86400),
            fred_api_key=_runtime_secret("fred", "fred_api_key", env_var="FRED_API_KEY"),
            fred_max_rps=_int_env("VIZA_FRED_MAX_RPS", 2),
            fred_cache_ttl_seconds=_int_env("VIZA_FRED_CACHE_TTL_SECONDS", 86400),
            fred_use_alfred_vintages=_bool_env("VIZA_FRED_USE_ALFRED_VINTAGES", False),
        )

    def masked_summary(self) -> dict[str, object]:
        return {
            "VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED": self.runtime_handlers_enabled,
            "VIZA_EQUITY_SEC_WEDGE_ENABLED": self.sec_wedge_enabled,
            "VIZA_EQUITY_FMP_ENABLED": self.fmp_enabled,
            "VIZA_EQUITY_FRED_ENABLED": self.fred_enabled,
            "VIZA_EQUITY_LIVE_INTEGRATION_TESTS": self.live_integration_tests_enabled,
            "VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED": self.preview_persistence_enabled,
            "VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED": self.preview_replay_refresh_enabled,
            "VIZA_SEC_USER_AGENT_configured": bool(self.sec_user_agent),
            "VIZA_SEC_MAX_RPS": self.sec_max_rps,
            "FMP_API_KEY_present": self.fmp_api_key is not None,
            "FMP_PRODUCTION_LICENSE_CONFIRMED": self.fmp_production_license_confirmed,
            "VIZA_FMP_MAX_RPS": self.fmp_max_rps,
            "FRED_API_KEY_present": self.fred_api_key is not None,
            "VIZA_FRED_MAX_RPS": self.fred_max_rps,
            "VIZA_FRED_USE_ALFRED_VINTAGES": self.fred_use_alfred_vintages,
        }


def equity_runtime_enabled_from_env() -> bool:
    name = "VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED"
    return _bool_value(os.getenv(name) or _dotenv_value(name), False)


def _bool_env(name: str, default: bool) -> bool:
    return _bool_value(os.getenv(name), default)


def _bool_value(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in TRUTHY:
        return True
    if normalized in FALSY:
        return False
    return default


def _dotenv_value(name: str, path: str | Path = ".env") -> str | None:
    env_path = Path(path)
    if not env_path.exists():
        return None
    prefix = f"{name}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw.strip()))
    except ValueError:
        return default


def _runtime_secret(connector_id: str, key: str, *, env_var: str) -> str | None:
    store = CredentialStore()
    try:
        return store.get_secret_for_runtime(connector_id, key, env_var=env_var)
    except KeyError:
        return None
