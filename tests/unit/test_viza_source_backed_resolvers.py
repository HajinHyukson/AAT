from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from viza.assets import resolve_static_asset_identity
from viza.attribute_registry import load_attribute_registry
from viza.attribute_resolvers import resolve_attribute_values
from viza.diagnostics import collect_runtime_diagnostics
from viza.exports import ExportFormat, ExportRequest, export_payload
from viza.observations import (
    ObservationIngestRequest,
    calculate_rsi_14d,
    get_observation_store,
    ohlcv_rows_from_csv,
)
from viza.project_store import get_project_store
from viza.source_events import (
    extract_events_from_local_csv,
    extract_sec_filing_events_from_metadata_csv,
    unusual_volume_events_from_ohlcv,
)
from viza.universes import UniverseSecurity


def test_source_backed_rsi_from_sample_local_ohlcv_csv(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    csv_path = _write_ohlcv_csv(tmp_path / "aapl_ohlcv.csv")
    rows = ohlcv_rows_from_csv(csv_path)
    entity_id, asset_id = resolve_static_asset_identity("AAPL")

    get_observation_store().ingest(
        ObservationIngestRequest(
            entity_id=entity_id,
            asset_id=asset_id,
            ohlcv_rows=rows,
            source_record=csv_path.name,
            data_version="local_ohlcv_unit_v1",
        )
    )

    registry = load_attribute_registry()
    security = UniverseSecurity(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Information Technology",
        industry="Technology Hardware",
    )
    resolved = resolve_attribute_values(
        security,
        ["rsi_14d"],
        registry,
        timestamp_cutoff=(rows[-1].available_at or rows[-1].timestamp) + timedelta(minutes=1),
    )["rsi_14d"]

    assert resolved.value == calculate_rsi_14d([row.close for row in rows])
    assert resolved.is_prototype is False
    assert resolved.source == "local_ohlcv_csv"
    assert resolved.connector_id == "local_csv"
    assert resolved.data_version == "local_ohlcv_unit_v1"
    assert resolved.rights_policy["connector_id"] == "local_csv"
    assert resolved.rights_policy["source_id"] == "local_ohlcv_csv"
    assert resolved.rights_policy["display_policy"] == "derived_values_allowed"
    assert resolved.rights_policy["export_policy"] == "derived_values_allowed"
    assert resolved.rights_policy["derived_value_policy"] == "allowed"
    assert resolved.rights_policy["redistribution_policy"] == "restricted"
    assert resolved.rights_policy["retention_policy"] == "local_project_store"
    assert resolved.diagnostics["prototype_fallback"] is False


def test_volume_spike_observation_drives_unusual_volume_event(tmp_path) -> None:
    csv_path = _write_ohlcv_csv(tmp_path / "msft_ohlcv.csv", latest_volume=4_000_000)
    rows = ohlcv_rows_from_csv(csv_path)
    entity_id, asset_id = resolve_static_asset_identity("MSFT")

    events = unusual_volume_events_from_ohlcv(
        entity_id=entity_id,
        asset_id=asset_id,
        rows=rows,
        min_volume_spike=2.0,
    )

    assert len(events) == 1
    assert events[0].event_type == "unusual_volume"
    assert events[0].affected_entity_ids == [entity_id]
    assert events[0].affected_asset_ids == [asset_id]
    assert events[0].source["connector_id"] == "local_csv"
    assert events[0].rights_policy["source_id"] == "local_ohlcv_csv"
    assert events[0].rights_policy["export_policy"] == "derived_values_allowed"


def test_sec_filing_metadata_csv_extracts_source_backed_event(tmp_path) -> None:
    csv_path = tmp_path / "filings.csv"
    csv_path.write_text(
        "\n".join(
            [
                "entity_id,asset_id,accession_number,form_type,filed_at,available_at,materiality,novelty,confidence",
                "entity-us-equity-AAPL,asset-us-equity-AAPL,0000320193-26-000010,8-K,2026-02-01T14:30:00Z,2026-02-01T14:31:00Z,0.8,0.9,0.85",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    events = extract_sec_filing_events_from_metadata_csv(csv_path)

    assert len(events) == 1
    assert events[0].event_type == "sec_filing_novelty"
    assert events[0].source["connector_id"] == "sec_edgar"
    assert events[0].source["form_type"] == "8-K"
    assert events[0].evidence_refs == ["filing:0000320193-26-000010"]
    assert events[0].rights_policy["license_policy"] == "public_sec_edgar"


def test_local_events_csv_extracts_analyst_news_social_or_insider_events(tmp_path) -> None:
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "\n".join(
            [
                "event_type,entity_id,asset_id,observed_at,available_at,materiality,novelty,direction,confidence,evidence_ref,source_record",
                "insider_transaction,entity-us-equity-MSFT,asset-us-equity-MSFT,2026-02-02T15:00:00Z,2026-02-02T15:01:00Z,0.7,0.6,bullish,0.88,event:msft:insider,local-row-1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    events = extract_events_from_local_csv(csv_path)

    assert len(events) == 1
    assert events[0].event_type == "insider_transaction"
    assert events[0].direction_hint == "bullish"
    assert events[0].source["source_record"] == "local-row-1"
    assert events[0].rights_policy["connector_id"] == "local_csv"
    assert events[0].rights_policy["redistribution_policy"] == "restricted"


def test_export_redaction_respects_source_policy_even_when_entitlement_allows_export() -> None:
    result = {
        "run_id": "run-source-rights",
        "methodology_id": "methodology-source-rights",
        "rows": [
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "score": 0.9,
                "rank": 1,
                "attributes": {"momentum": 0.77},
            }
        ],
        "evidence": {
            "attr:AAPL:momentum": {
                "evidence_ref": "attr:AAPL:momentum",
                "attribute_key": "momentum",
                "value": 0.77,
                "source_record_id": "restricted-row",
                "source_timestamp": "2026-02-01T00:00:00+00:00",
                "entitlement_policy": "internal",
                "entitlement": {"export_allowed": True},
                "rights_policy": {"export_policy": "restricted"},
                "diagnostics": {},
            }
        },
    }

    exported = export_payload(
        ExportRequest(
            export_format=ExportFormat.JSON,
            result=result,
            include_evidence=True,
        )
    )
    payload = json.loads(exported.payload)

    assert payload["rows"][0]["attributes"]["momentum"] == "[redacted]"
    assert payload["evidence"]["attr:AAPL:momentum"]["value"] == "[redacted]"
    assert payload["evidence"]["attr:AAPL:momentum"]["source_record_id"] is None
    assert exported.redactions[0].policy == "restricted"


def test_missing_source_configuration_keeps_fallback_warning_explicit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    registry = load_attribute_registry()
    security = UniverseSecurity(ticker="AAPL", name="Apple Inc.")

    resolved = resolve_attribute_values(security, ["rsi_14d"], registry)["rsi_14d"]

    assert resolved.is_prototype is True
    assert resolved.value is None
    assert resolved.missing_reason == "missing_prototype_value"
    assert resolved.diagnostics["prototype_fallback"] is True
    assert resolved.source == "phase_4_prototype_fallback"


def test_runtime_diagnostics_include_source_backed_resolver_counts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    get_project_store().ensure_default_project()
    rows = ohlcv_rows_from_csv(_write_ohlcv_csv(tmp_path / "diag_ohlcv.csv"))
    entity_id, asset_id = resolve_static_asset_identity("NVDA")
    get_observation_store().ingest(
        ObservationIngestRequest(
            entity_id=entity_id,
            asset_id=asset_id,
            ohlcv_rows=rows,
            source_record="diag_ohlcv.csv",
        )
    )

    diagnostics = collect_runtime_diagnostics(engine_version="unit")

    assert diagnostics.source_backed_resolver_count >= 1
    assert diagnostics.prototype_fallback_count >= 0
    assert diagnostics.credential_ready_connector_count >= 1
    assert diagnostics.observation_store_status == "available"
    assert diagnostics.last_resolver_warning_count == 0


def _write_ohlcv_csv(path, *, latest_volume: int = 2_500_000):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    lines = ["timestamp,open,high,low,close,volume,available_at"]
    for index in range(30):
        day = start + timedelta(days=index)
        close = 100 + index + (index % 4) - (1 if index % 7 == 0 else 0)
        volume = latest_volume if index == 29 else 1_000_000 + index * 1_000
        lines.append(
            ",".join(
                [
                    day.isoformat(),
                    str(close - 0.5),
                    str(close + 1),
                    str(close - 1),
                    str(close),
                    str(volume),
                    (day + timedelta(minutes=15)).isoformat(),
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
