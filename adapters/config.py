from __future__ import annotations

import os

from pydantic import BaseModel

from adapters.protocol import LicenseTier


class AdapterConfig(BaseModel):
    name: str
    license_tier: LicenseTier
    enabled: bool = True
    credential_env_vars: tuple[str, ...] = ()


def validate_adapter_config(config: AdapterConfig, *, env: str | None = None) -> None:
    runtime_env = env or os.getenv("ENV", "development")
    if runtime_env != "production" or not config.enabled:
        return

    if config.license_tier not in {"licensed", "alt_data"}:
        return

    missing = [name for name in config.credential_env_vars if not os.getenv(name)]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"adapter {config.name!r} is {config.license_tier!r} but missing credentials: {names}"
        )
