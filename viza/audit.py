from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.graph_schema import MethodologyGraph


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    evidence_ref: str
    source: str = "unknown"
    source_record_id: str | None = None
    source_timestamp: str | None = None
    timestamp_available: str | None = None
    value: Any = None
    unit: str | None = None
    calculation: dict[str, Any] = Field(default_factory=dict)
    model_version: str | None = None
    data_version: str | None = None
    confidence: float | None = None
    limitations: list[str] = Field(default_factory=list)
    license_policy: str | None = None


class ReproducibilityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    expected: Any = None
    observed: Any = None
    message: str = ""


class PointInTimeEvidenceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_ref: str
    status: str
    cutoff: str
    timestamp_available: str | None = None
    message: str = ""


class ReproduceRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: MethodologyGraph
    baseline_manifest: dict[str, Any]
    project_id: str | None = None
    methodology_version_id: str | None = None


class ReproduceRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    matching: bool
    checks: list[ReproducibilityCheck] = Field(default_factory=list)
    result: dict[str, Any]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def stable_checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_evidence_records(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for evidence_ref, raw_record in evidence.items():
        record = dict(raw_record) if isinstance(raw_record, dict) else {"value": raw_record}
        record.setdefault("evidence_ref", evidence_ref)
        record.setdefault("source", _default_evidence_source(evidence_ref))
        record.setdefault("source_record_id", None)
        record.setdefault("source_timestamp", record.get("event_time"))
        record.setdefault("timestamp_available", None)
        record.setdefault("value", _default_evidence_value(evidence_ref, record))
        record.setdefault("unit", None)
        record.setdefault("calculation", {})
        record.setdefault("model_version", None)
        record.setdefault("data_version", None)
        record.setdefault("confidence", None)
        record.setdefault("limitations", [])
        record.setdefault("license_policy", None)
        normalized[evidence_ref] = EvidenceRecord.model_validate(record).model_dump(
            mode="json"
        )
    return normalized


def evidence_checksum(evidence: dict[str, Any]) -> str:
    return stable_checksum(normalize_evidence_records(evidence))


def result_checksum(
    *,
    rows: list[Any],
    relationships: list[Any],
    warnings: list[Any],
    evidence: dict[str, Any],
) -> str:
    return stable_checksum(
        {
            "rows": [_model_dump(row) for row in rows],
            "relationships": [_model_dump(edge) for edge in relationships],
            "warnings": [_model_dump(warning) for warning in warnings],
            "evidence_checksum": evidence_checksum(evidence),
        }
    )


def data_versions_from_evidence(evidence: dict[str, Any]) -> dict[str, list[str]]:
    versions: dict[str, set[str]] = {"data_versions": set(), "model_versions": set()}
    for record in normalize_evidence_records(evidence).values():
        data_version = record.get("data_version")
        model_version = record.get("model_version")
        if isinstance(data_version, str) and data_version:
            versions["data_versions"].add(data_version)
        if isinstance(model_version, str) and model_version:
            versions["model_versions"].add(model_version)
    return {
        key: sorted(values)
        for key, values in versions.items()
    }


def connector_states_from_manifest(manifest: dict[str, Any]) -> dict[str, str]:
    connectors = manifest.get("connectors")
    if not isinstance(connectors, dict):
        return {}
    states: dict[str, str] = {}
    for connector_id, raw_connector in connectors.items():
        if not isinstance(connector_id, str) or not isinstance(raw_connector, dict):
            continue
        status = raw_connector.get("status")
        states[connector_id] = status if isinstance(status, str) else "unknown"
    return states


def entitlement_states_from_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    connectors = manifest.get("connectors")
    if not isinstance(connectors, dict):
        return {}
    states: dict[str, dict[str, Any]] = {}
    for connector_id, raw_connector in connectors.items():
        if not isinstance(connector_id, str) or not isinstance(raw_connector, dict):
            continue
        entitlement = raw_connector.get("entitlement")
        states[connector_id] = entitlement if isinstance(entitlement, dict) else {}
    return states


def compare_manifests(
    baseline_manifest: dict[str, Any],
    observed_manifest: dict[str, Any],
) -> list[ReproducibilityCheck]:
    checks = [
        _compare_manifest_field("graph_hash", baseline_manifest, observed_manifest),
        _compare_manifest_field("result_checksum", baseline_manifest, observed_manifest),
        _compare_manifest_field("data_versions", baseline_manifest, observed_manifest),
        _compare_manifest_field("model_versions", baseline_manifest, observed_manifest),
        _compare_manifest_field("connector_states", baseline_manifest, observed_manifest),
        _compare_manifest_field("entitlement_states", baseline_manifest, observed_manifest),
        _compare_manifest_field("warning_codes", baseline_manifest, observed_manifest),
    ]
    return checks


def parse_point_in_time_cutoff(value: str) -> datetime:
    cutoff_text = value.strip()
    if not cutoff_text:
        raise ValueError("cutoff cannot be blank")

    if "T" not in cutoff_text and len(cutoff_text) == 10:
        parsed_date = date.fromisoformat(cutoff_text)
        return datetime.combine(parsed_date, time.max, tzinfo=timezone.utc)

    parsed = datetime.fromisoformat(cutoff_text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def point_in_time_evidence_checks(
    evidence: dict[str, Any],
    cutoff: str,
) -> list[PointInTimeEvidenceCheck]:
    cutoff_datetime = parse_point_in_time_cutoff(cutoff)
    normalized_cutoff = cutoff_datetime.isoformat()
    checks: list[PointInTimeEvidenceCheck] = []
    for evidence_ref, record in normalize_evidence_records(evidence).items():
        timestamp_available = record.get("timestamp_available")
        if not isinstance(timestamp_available, str) or not timestamp_available:
            checks.append(
                PointInTimeEvidenceCheck(
                    evidence_ref=evidence_ref,
                    status="not_applicable",
                    cutoff=normalized_cutoff,
                    timestamp_available=None,
                    message="Evidence record has no timestamp_available field.",
                )
            )
            continue

        try:
            available_at = _parse_evidence_timestamp(timestamp_available)
        except ValueError:
            checks.append(
                PointInTimeEvidenceCheck(
                    evidence_ref=evidence_ref,
                    status="invalid_timestamp",
                    cutoff=normalized_cutoff,
                    timestamp_available=timestamp_available,
                    message="Evidence timestamp_available could not be parsed.",
                )
            )
            continue

        if available_at <= cutoff_datetime:
            checks.append(
                PointInTimeEvidenceCheck(
                    evidence_ref=evidence_ref,
                    status="passed",
                    cutoff=normalized_cutoff,
                    timestamp_available=timestamp_available,
                    message="Evidence was available at or before the cutoff.",
                )
            )
        else:
            checks.append(
                PointInTimeEvidenceCheck(
                    evidence_ref=evidence_ref,
                    status="violated",
                    cutoff=normalized_cutoff,
                    timestamp_available=timestamp_available,
                    message="Evidence timestamp_available is after the cutoff.",
                )
            )
    return checks


def point_in_time_summary(
    checks: list[PointInTimeEvidenceCheck],
) -> dict[str, int | str]:
    counts = {
        "passed": 0,
        "violated": 0,
        "invalid_timestamp": 0,
        "not_applicable": 0,
    }
    for check in checks:
        if check.status in counts:
            counts[check.status] += 1
    status = (
        "failed"
        if counts["violated"] or counts["invalid_timestamp"]
        else "passed"
    )
    return {
        "status": status,
        "checked_count": len(checks),
        "passed_count": counts["passed"],
        "violation_count": counts["violated"],
        "invalid_timestamp_count": counts["invalid_timestamp"],
        "not_applicable_count": counts["not_applicable"],
    }


def _compare_manifest_field(
    field_name: str,
    baseline_manifest: dict[str, Any],
    observed_manifest: dict[str, Any],
) -> ReproducibilityCheck:
    expected = baseline_manifest.get(field_name)
    observed = observed_manifest.get(field_name)
    status = "match" if expected == observed else "mismatch"
    return ReproducibilityCheck(
        name=field_name,
        status=status,
        expected=expected,
        observed=observed,
        message=(
            f"{field_name} matched."
            if status == "match"
            else f"{field_name} changed between baseline and reproduced run."
        ),
    )


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _parse_evidence_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _default_evidence_source(evidence_ref: str) -> str:
    if evidence_ref == "graph":
        return "methodology_graph"
    if evidence_ref.startswith("universe:"):
        return "local_universe"
    if evidence_ref.startswith("company:"):
        return "radar_output"
    return "unknown"


def _default_evidence_value(evidence_ref: str, record: dict[str, Any]) -> Any:
    if "value" in record:
        return record["value"]
    if evidence_ref == "graph":
        return {
            "name": record.get("name"),
            "node_count": record.get("node_count"),
            "edge_count": record.get("edge_count"),
        }
    if evidence_ref.startswith("company:"):
        return {
            "ticker": record.get("ticker"),
            "rank": record.get("rank"),
            "score": record.get("score"),
        }
    return None
