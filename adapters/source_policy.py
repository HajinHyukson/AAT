from __future__ import annotations

import os


def require_confirmed_production_source(*, source_name: str, env_var: str) -> None:
    if os.getenv("ENV", "development") != "production":
        return
    if os.getenv(env_var, "").lower() not in {"1", "true", "yes"}:
        raise RuntimeError(
            f"production use of {source_name} requires {env_var}=true to confirm source/license status"
        )
