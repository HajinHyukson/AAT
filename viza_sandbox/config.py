from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class SandboxSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIZA_SANDBOX_")

    database_url: str = "sqlite:///./data/viza_sandbox/sandbox.db"
    canonical_database_url: str | None = None
    data_dir: Path = Path("data/viza_sandbox")
    runs_dir: Path = Path("data/viza_sandbox/runs")
    runner: Literal["docker", "local"] = "docker"
    docker_image: str = "viza-sandbox-runtime:latest"
    wall_clock_seconds: int = 600
    memory_gb: int = 8
    cpus: int = 2
    price_adjustment_status: Literal["unverified", "adjusted", "unadjusted"] = "unverified"
    source_rights_state: str = "development_proving"
    max_result_bytes: int = 268435456
    max_concurrent_runs: int = 2
