from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from viza.events import ManualEventRequest, VizaEvent, event_from_manual_request
from viza.observations import OHLCVRow


SOURCE_BACKED_EVENT_RIGHTS = {
    "connector_id": "local_csv",
    "source_id": "local_events_csv",
    "license_policy": "user_provided",
    "cache_policy": "local_project_store",
    "display_policy": "derived_values_allowed",
    "export_policy": "derived_values_allowed",
    "derived_value_policy": "allowed",
    "redistribution_policy": "restricted",
    "attribution_required": False,
    "retention_policy": "local_project_store",
}


def extract_events_from_local_csv(path: str | Path) -> list[VizaEvent]:
    events: list[VizaEvent] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            event = event_from_manual_request(
                ManualEventRequest(
                    event_type=_read_string(row.get("event_type"), "news_sentiment_shift"),
                    affected_entity_ids=[_read_string(row.get("entity_id"))],
                    affected_asset_ids=_optional_list(row.get("asset_id")),
                    observed_at=_parse_datetime(row.get("observed_at")),
                    available_at=_parse_datetime(row.get("available_at")),
                    materiality=_read_float(row.get("materiality"), 0.5),
                    novelty=_read_float(row.get("novelty"), 0.5),
                    direction_hint=_read_string(row.get("direction"), "neutral"),
                    confidence=_read_float(row.get("confidence"), 0.75),
                    evidence_refs=[_read_string(row.get("evidence_ref"), f"event:{row.get('event_type')}")],
                    rights_policy={**SOURCE_BACKED_EVENT_RIGHTS, "source_id": "local_events_csv"},
                    source={
                        "connector_id": "local_csv",
                        "source_id": "local_events_csv",
                        "source_record": _read_string(row.get("source_record"), ""),
                    },
                )
            )
            events.append(event)
    return events


def extract_sec_filing_events_from_metadata_csv(path: str | Path) -> list[VizaEvent]:
    events: list[VizaEvent] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            entity_id = _read_string(row.get("entity_id"))
            accession = _read_string(row.get("accession_number"), "unknown")
            events.append(
                event_from_manual_request(
                    ManualEventRequest(
                        event_type="sec_filing_novelty",
                        affected_entity_ids=[entity_id],
                        affected_asset_ids=_optional_list(row.get("asset_id")),
                        observed_at=_parse_datetime(row.get("filed_at")),
                        available_at=_parse_datetime(row.get("available_at") or row.get("filed_at")),
                        materiality=_read_float(row.get("materiality"), 0.6),
                        novelty=_read_float(row.get("novelty"), 0.7),
                        direction_hint="watch",
                        confidence=_read_float(row.get("confidence"), 0.8),
                        evidence_refs=[f"filing:{accession}"],
                        rights_policy={
                            **SOURCE_BACKED_EVENT_RIGHTS,
                            "source_id": "sec_filing_metadata",
                            "license_policy": "public_sec_edgar",
                            "export_policy": "derived_values_allowed",
                        },
                        source={
                            "connector_id": "sec_edgar",
                            "source_id": "sec_filing_metadata",
                            "accession_number": accession,
                            "form_type": _read_string(row.get("form_type"), "unknown"),
                        },
                    )
                )
            )
    return events


def unusual_volume_events_from_ohlcv(
    *,
    entity_id: str,
    asset_id: str | None,
    rows: list[OHLCVRow],
    min_volume_spike: float = 1.5,
) -> list[VizaEvent]:
    if len(rows) < 20:
        return []
    rows = sorted(rows, key=lambda row: row.timestamp)
    volumes = [row.volume for row in rows if row.volume is not None]
    if len(volumes) < 20:
        return []
    baseline = sum(volumes[-20:-1]) / 19
    latest = volumes[-1]
    if baseline <= 0 or latest / baseline < min_volume_spike:
        return []
    latest_row = rows[-1]
    return [
        event_from_manual_request(
            ManualEventRequest(
                event_type="unusual_volume",
                affected_entity_ids=[entity_id],
                affected_asset_ids=[asset_id] if asset_id else [],
                observed_at=latest_row.timestamp,
                available_at=latest_row.available_at or latest_row.timestamp,
                materiality=min(latest / baseline / 3, 1.0),
                novelty=min(latest / baseline / 3, 1.0),
                direction_hint="watch",
                confidence=0.82,
                evidence_refs=[f"ohlcv:{entity_id}:volume_spike"],
                rights_policy={
                    **SOURCE_BACKED_EVENT_RIGHTS,
                    "source_id": "local_ohlcv_csv",
                },
                source={"connector_id": "local_csv", "source_id": "local_ohlcv_csv"},
            )
        )
    ]


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_string(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) and value else fallback


def _read_float(value: Any, fallback: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value:
        return float(value)
    return fallback


def _optional_list(value: Any) -> list[str]:
    return [value] if isinstance(value, str) and value else []
