from __future__ import annotations

import json
from pathlib import Path

from viza.equity.config import EquityRuntimeConfig
from viza.equity.preview import (
    EquityRuntimeWedgePreviewRequest,
    build_equity_runtime_wedge_preview,
    equity_runtime_wedge_status_payload,
)


def test_packaging_config_includes_equity_runtime_resources() -> None:
    builder_config = Path("apps/viza-desktop/electron-builder.yml").read_text(encoding="utf-8")

    assert "../../docs/equity_module/v0.1" in builder_config
    assert "engine/docs/equity_module/v0.1" in builder_config
    assert "registries/**/*" in builder_config
    assert "sec_fmp_fred_runtime_wedge_fixture.json" in builder_config


def test_packaged_smoke_script_checks_equity_preview_contract() -> None:
    smoke_script = Path("apps/viza-desktop/scripts/smokePackage.mjs").read_text(encoding="utf-8")

    assert "/viza/equity/runtime-wedge/status" in smoke_script
    assert "/viza/equity/runtime-wedge/preview" in smoke_script
    assert "/viza/equity/runtime-wedge/runs" in smoke_script
    assert "package-draft" in smoke_script
    assert "VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED" in smoke_script
    assert "VIZA_EQUITY_SEC_WEDGE_ENABLED" in smoke_script
    assert "VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED" in smoke_script
    assert "PACKAGED_SMOKE_FMP_SECRET_SHOULD_NOT_APPEAR" in smoke_script
    assert "PACKAGED_SMOKE_FRED_SECRET_SHOULD_NOT_APPEAR" in smoke_script
    assert "not personalized investment advice" in smoke_script
    assert "persist_run" in smoke_script


def test_packaged_preview_fixture_and_registries_exist_in_source_tree() -> None:
    fixture = Path(
        "docs/equity_module/v0.1/fixtures/first_wedge_sec_quality_value/sec_fmp_fred_runtime_wedge_fixture.json"
    )
    manifest = Path(
        "docs/equity_module/v0.1/registries/viza.finance.equity_investment.manifest.json"
    )

    assert fixture.exists()
    assert manifest.exists()


def test_status_payload_masks_runtime_secrets() -> None:
    config = EquityRuntimeConfig(
        runtime_handlers_enabled=True,
        sec_wedge_enabled=True,
        fmp_enabled=True,
        fred_enabled=True,
        fmp_api_key="TEST_FMP_SECRET_SHOULD_NOT_APPEAR",
        fred_api_key="TEST_FRED_SECRET_SHOULD_NOT_APPEAR",
    )

    status = equity_runtime_wedge_status_payload(config=config)
    serialized = json.dumps(status, sort_keys=True)

    assert status["enabled"] is True
    assert "TEST_FMP_SECRET_SHOULD_NOT_APPEAR" not in serialized
    assert "TEST_FRED_SECRET_SHOULD_NOT_APPEAR" not in serialized


def test_mock_packaged_preview_response_masks_runtime_secrets() -> None:
    config = EquityRuntimeConfig(
        runtime_handlers_enabled=True,
        sec_wedge_enabled=True,
        fmp_enabled=True,
        fred_enabled=True,
        fmp_api_key="TEST_FMP_SECRET_SHOULD_NOT_APPEAR",
        fred_api_key="TEST_FRED_SECRET_SHOULD_NOT_APPEAR",
    )
    request = EquityRuntimeWedgePreviewRequest(
        target={"cik": "320193", "ticker_alias": "AAPL"},
        profile_id="quality_value_long_only",
        package_mode="marketplace_draft",
        include_fmp=True,
        include_fred=True,
        use_live_connectors=False,
    )

    payload = build_equity_runtime_wedge_preview(request, config=config)
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["audit"]["fixture_mode"] is True
    assert payload["package_redaction_preview"]["blocked"]
    assert "TEST_FMP_SECRET_SHOULD_NOT_APPEAR" not in serialized
    assert "TEST_FRED_SECRET_SHOULD_NOT_APPEAR" not in serialized
