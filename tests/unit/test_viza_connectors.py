from __future__ import annotations

import json

from viza.attribute_registry import AttributeRegistry, load_attribute_registry
from viza.connectors import (
    EnvironmentCredentialStore,
    entitlement_from_policy,
    list_connector_fields,
    load_connector_catalog,
    preview_connector,
    redact_connector_settings,
    test_connector_connection as check_connector_connection,
)
from viza.execution import validate_executable_graph
from viza.graph_schema import MethodologyGraph, load_methodology_graph
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH


def test_connector_catalog_includes_local_and_external_sources(monkeypatch) -> None:
    monkeypatch.delenv("FMP_API_KEY", raising=False)

    connectors = load_connector_catalog()
    connectors_by_id = {connector.connector_id: connector for connector in connectors}

    assert connectors_by_id["local_viza_workspace"].status == "available"
    assert connectors_by_id["local_csv"].status == "not_configured"
    assert connectors_by_id["aat_postgres"].status == "credential_required"
    assert connectors_by_id["fmp"].status == "credential_required"
    assert {"kenneth_french", "sec_edgar", "fred"}.issubset(connectors_by_id)


def test_local_csv_connector_lists_fields_and_preview(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "custom_attributes.csv"
    csv_path.write_text(
        "ticker,custom_score,source_note\nAAPL,0.91,local\nMSFT,0.84,local\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VIZA_LOCAL_CSV_PATH", str(csv_path))

    health = check_connector_connection("local_csv")
    fields = list_connector_fields("local_csv")
    preview = preview_connector("local_csv", limit=1)

    assert health.status == "available"
    assert {field.field_key for field in fields} == {
        "ticker",
        "custom_score",
        "source_note",
    }
    assert preview.rows == [{"ticker": "AAPL", "custom_score": "0.91", "source_note": "local"}]


def test_entitlement_policy_parses_rights_and_credentials() -> None:
    entitlement = entitlement_from_policy("query_only_no_export_credential_required")

    assert entitlement.query_allowed is True
    assert entitlement.local_cache_allowed is False
    assert entitlement.raw_snapshot_allowed is False
    assert entitlement.export_allowed is False
    assert entitlement.user_credential_required is True
    assert entitlement.limitations


def test_credential_store_reports_presence_without_returning_secret(monkeypatch) -> None:
    monkeypatch.setenv("FMP_API_KEY", "super-secret-key")
    credential = EnvironmentCredentialStore().describe_requirement(
        "fmp_api_key",
        "FMP API key",
        required=True,
        env_var="FMP_API_KEY",
    )

    assert credential.configured is True
    assert credential.secret_available is True
    assert "super-secret-key" not in json.dumps(credential.model_dump(mode="json"))


def test_connector_settings_redaction_removes_secret_values() -> None:
    redacted = redact_connector_settings(
        {
            "api_key": "abc123",
            "nested": {"password": "secret", "safe": "kept"},
        }
    )

    assert redacted == {
        "api_key": "[redacted]",
        "nested": {"password": "[redacted]", "safe": "kept"},
    }


def test_runtime_warns_for_unconfigured_connector_and_entitlement_limits(monkeypatch) -> None:
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    payload = graph.model_dump(mode="json")
    attribute_node = next(node for node in payload["nodes"] if node["id"] == "attribute-momentum")
    attribute_node["config"]["attribute_key"] = "paid_sentiment_score"
    attribute_node["label"] = "Paid Sentiment Score"

    paid_attribute = registry.attributes[0].model_copy(
        update={
            "key": "paid_sentiment_score",
            "display_name": "Paid Sentiment Score",
            "source": "fmp",
            "source_type": "fmp_paid_api",
            "unit": "score",
            "entitlement_policy": "query_only_no_export_credential_required",
            "license_policy": "paid_api_terms",
            "cache_policy": "provider_terms_required",
            "production_scoring_allowed": True,
            "evidence_only": False,
            "allowed_transforms": ["percentile_rank"],
        }
    )
    limited_registry = AttributeRegistry.model_validate(
        {
            **registry.model_dump(mode="json"),
            "attributes": [
                *[attribute.model_dump(mode="json") for attribute in registry.attributes],
                paid_attribute.model_dump(mode="json"),
            ],
        }
    )

    warnings = validate_executable_graph(
        MethodologyGraph.model_validate(payload),
        limited_registry,
    )
    warning_codes = {warning.code for warning in warnings}

    assert "attribute_connector_not_configured" in warning_codes
    assert "attribute_credential_required" in warning_codes
    assert "attribute_export_limited" in warning_codes
