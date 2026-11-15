from __future__ import annotations

import os
import sys
from pathlib import Path


CONFIG_DIR_ENV_VAR = "VIZA_CONFIG_DIR"
ENGINE_ROOT_ENV_VAR = "VIZA_ENGINE_ROOT"

REQUIRED_CONFIG_FILES = (
    "viza_attribute_registry.json",
    "mvp_universe.json",
    "pilot_sp500_universe.json",
    "viza_event_registry.json",
    "viza_insight_registry.json",
    "viza_strategy_profile_templates.json",
    "viza_modules/viza.real_estate.acquisition.json",
    "viza_concepts.json",
    "viza_command_taxonomy.json",
    "viza_command_conflicts.json",
    "viza_command_language_gate.json",
    "viza_bkm_registry.json",
    "viza_fibo_mappings.json",
)


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def source_config_dir() -> Path:
    return source_root() / "config"


def resolve_config_dir() -> Path:
    explicit_config_dir = os.getenv(CONFIG_DIR_ENV_VAR)
    if explicit_config_dir:
        return Path(explicit_config_dir).expanduser().resolve()

    explicit_engine_root = os.getenv(ENGINE_ROOT_ENV_VAR)
    if explicit_engine_root:
        return Path(explicit_engine_root).expanduser().resolve() / "config"

    sidecar_config_dir = Path(sys.executable).resolve().parent / "config"
    if getattr(sys, "frozen", False) or sidecar_config_dir.exists():
        return sidecar_config_dir

    return source_config_dir()


def resolve_config_path(*parts: str) -> Path:
    return resolve_config_dir().joinpath(*parts)


def display_config_path(path: Path) -> str:
    resolved_path = path.resolve()
    for root in (resolve_config_dir(), source_root()):
        try:
            return str(resolved_path.relative_to(root.resolve()))
        except ValueError:
            continue
    return str(resolved_path)


def required_config_file_status(
    required_files: tuple[str, ...] = REQUIRED_CONFIG_FILES,
) -> list[dict[str, str | bool]]:
    config_dir = resolve_config_dir()
    return [
        {
            "path": relative_path,
            "resolved_path": str((config_dir / relative_path).resolve()),
            "exists": (config_dir / relative_path).exists(),
        }
        for relative_path in required_files
    ]
