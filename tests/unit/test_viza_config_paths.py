from __future__ import annotations

import shutil
import sys

from viza.attribute_registry import load_attribute_registry
from viza.config_paths import resolve_config_dir, source_config_dir
from viza.connectors import load_connector_catalog
from viza.universes import load_universe_summaries


def test_config_dir_env_override_is_used(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("VIZA_CONFIG_DIR", str(config_dir))
    monkeypatch.delenv("VIZA_ENGINE_ROOT", raising=False)

    assert resolve_config_dir() == config_dir.resolve()


def test_engine_root_env_config_dir_is_used(tmp_path, monkeypatch) -> None:
    engine_root = tmp_path / "engine"
    monkeypatch.delenv("VIZA_CONFIG_DIR", raising=False)
    monkeypatch.setenv("VIZA_ENGINE_ROOT", str(engine_root))

    assert resolve_config_dir() == (engine_root / "config").resolve()


def test_source_config_dir_is_default_without_packaged_env(monkeypatch) -> None:
    monkeypatch.delenv("VIZA_CONFIG_DIR", raising=False)
    monkeypatch.delenv("VIZA_ENGINE_ROOT", raising=False)
    monkeypatch.setattr(sys, "executable", str(source_config_dir().parent / "python.exe"))
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert resolve_config_dir() == source_config_dir()


def test_env_resolved_config_loads_catalog_universes_and_connectors(
    tmp_path,
    monkeypatch,
) -> None:
    config_dir = tmp_path / "engine" / "config"
    config_dir.mkdir(parents=True)
    for name in [
        "viza_attribute_registry.json",
        "mvp_universe.json",
        "pilot_sp500_universe.json",
    ]:
        shutil.copy2(source_config_dir() / name, config_dir / name)

    monkeypatch.setenv("VIZA_CONFIG_DIR", str(config_dir))

    registry = load_attribute_registry()
    universes = load_universe_summaries()
    connectors = load_connector_catalog(registry)

    assert len(registry.attributes) >= 70
    assert len(universes) == 2
    assert len(connectors) == 9
