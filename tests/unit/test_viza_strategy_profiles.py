from __future__ import annotations

import zipfile
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from viza.file_format.container import write_viza_container
from viza.file_format.models import SectionStatus, VisibilityMode, VizaFileManifest, VizaSectionDescriptor
from viza.modules import get_module_registry
from viza.service import app
from viza.strategy_profiles import (
    StrategyProfileCloneRequest,
    StrategyProfileCreateRequest,
    StrategyProfileUpdateRequest,
    get_strategy_profile_store,
    load_strategy_profile_templates,
    strategy_profile_hash,
)


client = TestClient(app)


def test_strategy_profile_template_loads() -> None:
    catalog = load_strategy_profile_templates()
    template = catalog.templates[0]

    assert catalog.schema_name == "viza.strategy_profile_templates.v1"
    assert template.display_name == "RSI Swing + Catalyst Confirmation"
    assert "rsi_14d" in template.preferred_indicators
    assert "acquisition_rumor" in template.catalyst_types


def test_create_update_clone_profile_and_version_hash(tmp_path) -> None:
    store = get_strategy_profile_store(tmp_path / "viza_projects.sqlite3")
    template = load_strategy_profile_templates().templates[0]

    profile = store.create_profile(
        StrategyProfileCreateRequest(
            display_name=template.display_name,
            template_id=template.strategy_profile_id,
            label="Initial",
        )
    )
    first_version = store.latest_version(profile.strategy_profile_id)
    updated = store.update_profile(
        profile.strategy_profile_id,
        StrategyProfileUpdateRequest(
            action_thresholds={"review": 0.5, "watchlist": 0.65},
            label="Threshold update",
        ),
    )
    second_version = store.latest_version(profile.strategy_profile_id)
    clone = store.clone_profile(
        profile.strategy_profile_id,
        StrategyProfileCloneRequest(display_name="Forked RSI Catalyst"),
    )

    assert profile.display_name == template.display_name
    assert updated.action_thresholds["review"] == 0.5
    assert first_version is not None
    assert second_version is not None
    assert second_version.parent_version_id == first_version.version_id
    assert strategy_profile_hash(updated) == strategy_profile_hash(
        updated.model_copy(update={"created_at": datetime.now(timezone.utc)})
    )
    assert clone.strategy_profile_id != profile.strategy_profile_id
    assert clone.display_name == "Forked RSI Catalyst"


def test_strategy_profile_endpoints_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    templates_response = client.get("/viza/strategy-profile-templates")
    template = templates_response.json()["templates"][0]

    create_response = client.post(
        "/viza/strategy-profiles",
        json={
            "display_name": template["display_name"],
            "template_id": template["strategy_profile_id"],
        },
    )
    profile_id = create_response.json()["strategy_profile_id"]
    update_response = client.put(
        f"/viza/strategy-profiles/{profile_id}",
        json={"preferred_indicators": ["rsi_14d", "momentum"], "label": "Narrowed"},
    )
    clone_response = client.post(
        f"/viza/strategy-profiles/{profile_id}/clone",
        json={"display_name": "Endpoint Clone"},
    )
    list_response = client.get("/viza/strategy-profiles")
    get_response = client.get(f"/viza/strategy-profiles/{profile_id}")

    assert templates_response.status_code == 200
    assert create_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["preferred_indicators"] == ["rsi_14d", "momentum"]
    assert clone_response.status_code == 200
    assert clone_response.json()["display_name"] == "Endpoint Clone"
    assert list_response.status_code == 200
    assert get_response.json()["strategy_profile_id"] == profile_id


def test_strategy_profile_node_config_validates() -> None:
    finance_module = get_module_registry().get_module("viza.finance.securities")
    node = finance_module.node_types["viza.finance.securities.strategy_profile"]

    assert node.display_name == "Strategy Profile"
    assert node.inspector_schema["properties"]["strategy_profile_id"]["type"] == "string"


def test_strategy_profile_exports_into_viza(tmp_path) -> None:
    template = load_strategy_profile_templates().templates[0]
    profile = get_strategy_profile_store(tmp_path / "store.sqlite3").create_profile(
        StrategyProfileCreateRequest(
            display_name=template.display_name,
            template_id=template.strategy_profile_id,
        )
    )
    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id="file-profile-test",
        display_name="Profile Test",
        object_kind="strategy_package",
        visibility=VisibilityMode.WHITE_BOX,
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        sections={"strategy_profile": VizaSectionDescriptor(status=SectionStatus.INCLUDED)},
    )
    target = tmp_path / "profile.viza"

    write_viza_container(
        target,
        manifest,
        {"strategy_profile": profile.model_dump(mode="json", by_alias=True)},
    )

    with zipfile.ZipFile(target) as archive:
        assert "strategies/strategy_profile.json" in archive.namelist()


def test_imported_profile_can_be_forked(tmp_path) -> None:
    store = get_strategy_profile_store(tmp_path / "viza_projects.sqlite3")
    template = load_strategy_profile_templates().templates[0]
    imported = store.create_profile(
        StrategyProfileCreateRequest(
            strategy_profile_id="imported-profile",
            display_name=template.display_name,
            template_id=template.strategy_profile_id,
            message="Imported from .viza",
        )
    )
    fork = store.clone_profile(
        imported.strategy_profile_id,
        StrategyProfileCloneRequest(display_name="Forked Imported Profile"),
    )

    assert fork.strategy_profile_id != imported.strategy_profile_id
    assert fork.preferred_indicators == imported.preferred_indicators
