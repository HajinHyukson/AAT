from __future__ import annotations

import csv
import io
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.connectors import entitlement_from_policy
from viza.graph_schema import MethodologyGraph


class ExportFormat(StrEnum):
    CSV = "csv"
    JSON = "json"
    METHODOLOGY = "methodology"
    MANIFEST = "manifest"


class ExportRedaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    evidence_ref: str | None = None
    policy: str = "unknown"
    reason: str


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_format: ExportFormat
    result: dict[str, Any] | None = None
    graph: MethodologyGraph | None = None
    manifest: dict[str, Any] | None = None
    selected_columns: list[str] = Field(default_factory=list)
    include_evidence: bool = False
    filename: str | None = None

    @model_validator(mode="after")
    def validate_export_payload(self) -> ExportRequest:
        if self.export_format in {ExportFormat.CSV, ExportFormat.JSON} and self.result is None:
            raise ValueError("csv and json exports require a result payload")
        if self.export_format == ExportFormat.METHODOLOGY and self.graph is None:
            raise ValueError("methodology export requires a graph payload")
        if self.export_format == ExportFormat.MANIFEST and self.manifest is None:
            raise ValueError("manifest export requires a manifest payload")
        return self


class ExportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_format: ExportFormat
    content_type: str
    filename: str
    payload: str
    redactions: list[ExportRedaction] = Field(default_factory=list)
    blocked: bool = False


def export_payload(request: ExportRequest) -> ExportResult:
    if request.export_format == ExportFormat.CSV:
        return _export_csv(request)
    if request.export_format == ExportFormat.JSON:
        return _export_json(request)
    if request.export_format == ExportFormat.METHODOLOGY:
        return ExportResult(
            export_format=request.export_format,
            content_type="application/json",
            filename=request.filename or "methodology.viza.json",
            payload=_json_dump(request.graph.model_dump(mode="json") if request.graph else {}),
        )
    return ExportResult(
        export_format=request.export_format,
        content_type="application/json",
        filename=request.filename or "run-manifest.viza.json",
        payload=_json_dump(request.manifest or {}),
    )


def _export_csv(request: ExportRequest) -> ExportResult:
    result = request.result or {}
    rows = _rows(result)
    redactions: list[ExportRedaction] = []
    restricted = _restricted_attributes(result)
    columns = _selected_columns(request.selected_columns, rows)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row_index, row in enumerate(rows):
        ticker = _read_string(row.get("ticker"))
        attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
        export_row: dict[str, Any] = {}
        for column in columns:
            if column in {"ticker", "company_name", "score", "rank"}:
                export_row[column] = row.get(column)
                continue
            if column in row and column != "attributes":
                if column == "translated_summary" and _derived_output_restricted(row):
                    redactions.append(
                        _redaction(
                            path=f"rows[{row_index}].translated_summary",
                            evidence_ref=_first_evidence_ref(row),
                            policy="derived_output_restricted",
                            reason="Derived translation policy does not allow export.",
                        )
                    )
                    export_row[column] = "[redacted]"
                else:
                    export_row[column] = _export_value(row.get(column))
                continue
            evidence_ref = f"attr:{ticker}:{column}"
            if evidence_ref in restricted:
                redactions.append(
                    _redaction(
                        path=f"rows[{row_index}].attributes.{column}",
                        evidence_ref=evidence_ref,
                        policy=restricted[evidence_ref],
                    )
                )
                export_row[column] = "[redacted]"
            else:
                export_row[column] = attributes.get(column)
        writer.writerow(export_row)

    return ExportResult(
        export_format=request.export_format,
        content_type="text/csv",
        filename=request.filename or "viza-radar.csv",
        payload=output.getvalue(),
        redactions=redactions,
    )


def _export_json(request: ExportRequest) -> ExportResult:
    result = request.result or {}
    redactions: list[ExportRedaction] = []
    restricted = _restricted_attributes(result)
    payload = {
        "run_id": result.get("run_id"),
        "methodology_id": result.get("methodology_id"),
        "timestamp_cutoff": result.get("timestamp_cutoff"),
        "result_checksum": result.get("result_checksum"),
        "rows": _redacted_rows(result, restricted, redactions),
        "relationships": result.get("relationships", []),
        "insights": result.get("insights", []),
        "translations": _redacted_translations(result, redactions),
        "warnings": result.get("warnings", []),
        "manifest": result.get("manifest", {}),
    }
    if request.include_evidence:
        payload["evidence"] = _redacted_evidence(result, restricted, redactions)

    return ExportResult(
        export_format=request.export_format,
        content_type="application/json",
        filename=request.filename or "viza-radar.json",
        payload=_json_dump(payload),
        redactions=redactions,
    )


def _redacted_rows(
    result: dict[str, Any],
    restricted: dict[str, str],
    redactions: list[ExportRedaction],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(_rows(result)):
        copied = dict(row)
        ticker = _read_string(copied.get("ticker"))
        attributes = copied.get("attributes")
        if _derived_output_restricted(copied) and copied.get("translated_summary") is not None:
            redactions.append(
                _redaction(
                    path=f"rows[{row_index}].translated_summary",
                    evidence_ref=_first_evidence_ref(copied),
                    policy="derived_output_restricted",
                    reason="Derived translation policy does not allow export.",
                )
            )
            copied["translated_summary"] = "[redacted]"
        if isinstance(attributes, dict):
            copied_attributes = dict(attributes)
            for key in list(copied_attributes):
                evidence_ref = f"attr:{ticker}:{key}"
                if evidence_ref not in restricted:
                    continue
                redactions.append(
                    _redaction(
                        path=f"rows[{row_index}].attributes.{key}",
                        evidence_ref=evidence_ref,
                        policy=restricted[evidence_ref],
                    )
                )
                copied_attributes[key] = "[redacted]"
            copied["attributes"] = copied_attributes
        rows.append(copied)
    return rows


def _redacted_translations(
    result: dict[str, Any],
    redactions: list[ExportRedaction],
) -> list[dict[str, Any]]:
    translations = result.get("translations")
    if not isinstance(translations, list):
        return []
    rows_by_entity = {
        _read_string(row.get("entity_id")): row
        for row in _rows(result)
        if isinstance(row, dict)
    }
    copied_translations: list[dict[str, Any]] = []
    for translation_index, translation in enumerate(translations):
        if not isinstance(translation, dict):
            continue
        copied = dict(translation)
        row = rows_by_entity.get(_read_string(copied.get("entity_id")), {})
        if row and _derived_output_restricted(row) and copied.get("translated_summary") is not None:
            redactions.append(
                _redaction(
                    path=f"translations[{translation_index}].translated_summary",
                    evidence_ref=_first_evidence_ref(copied),
                    policy="derived_output_restricted",
                    reason="Derived translation policy does not allow export.",
                )
            )
            copied["translated_summary"] = "[redacted]"
        copied_translations.append(copied)
    return copied_translations


def _redacted_evidence(
    result: dict[str, Any],
    restricted: dict[str, str],
    redactions: list[ExportRedaction],
) -> dict[str, Any]:
    evidence = result.get("evidence")
    if not isinstance(evidence, dict):
        return {}
    copied: dict[str, Any] = {}
    for evidence_ref, raw_record in evidence.items():
        if not isinstance(evidence_ref, str):
            continue
        if not isinstance(raw_record, dict):
            copied[evidence_ref] = raw_record
            continue
        record = dict(raw_record)
        if evidence_ref in restricted:
            redactions.append(
                _redaction(
                    path=f"evidence.{evidence_ref}.value",
                    evidence_ref=evidence_ref,
                    policy=restricted[evidence_ref],
                )
            )
            record["value"] = "[redacted]"
            record["source_record_id"] = None
            record["source_timestamp"] = None
            record["diagnostics"] = {
                **(record.get("diagnostics") if isinstance(record.get("diagnostics"), dict) else {}),
                "export_redacted": True,
            }
        copied[evidence_ref] = record
    return copied


def _restricted_attributes(result: dict[str, Any]) -> dict[str, str]:
    evidence = result.get("evidence")
    if not isinstance(evidence, dict):
        return {}
    restricted: dict[str, str] = {}
    for evidence_ref, raw_record in evidence.items():
        if not isinstance(evidence_ref, str):
            continue
        if not isinstance(raw_record, dict):
            continue
        policy_label = _read_string(raw_record.get("entitlement_policy"), "internal")
        entitlement = raw_record.get("entitlement")
        export_allowed = None
        rights_policy = raw_record.get("rights_policy")
        if isinstance(rights_policy, dict):
            policy_export_allowed = _export_allowed_from_source_policy(rights_policy)
            if policy_export_allowed is not None:
                export_allowed = policy_export_allowed
                policy_label = _read_string(rights_policy.get("export_policy"), policy_label)
        if isinstance(entitlement, dict) and isinstance(entitlement.get("export_allowed"), bool):
            export_allowed = export_allowed if export_allowed is not None else entitlement["export_allowed"]
        if export_allowed is None:
            export_allowed = entitlement_from_policy(policy_label).export_allowed
        if not export_allowed:
            restricted[evidence_ref] = policy_label
    return restricted


def _selected_columns(selected_columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    if selected_columns:
        return list(dict.fromkeys(selected_columns))
    columns = ["ticker", "company_name", "score", "rank"]
    if rows:
        attributes = rows[0].get("attributes")
        if isinstance(attributes, dict):
            columns.extend(key for key in attributes if isinstance(key, str))
    return list(dict.fromkeys(columns))


def _rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _redaction(
    path: str,
    evidence_ref: str | None,
    policy: str,
    reason: str = "Evidence entitlement policy does not allow export.",
) -> ExportRedaction:
    return ExportRedaction(
        path=path,
        evidence_ref=evidence_ref,
        policy=policy,
        reason=reason,
    )


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"


def _read_string(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) else fallback


def _export_allowed_from_source_policy(rights_policy: dict[str, Any]) -> bool | None:
    if isinstance(rights_policy.get("export_allowed"), bool):
        return rights_policy["export_allowed"]
    export_policy = _read_string(rights_policy.get("export_policy")).lower().replace(" ", "_")
    if not export_policy:
        return None
    restricted_tokens = {
        "blocked",
        "derived_output_restricted",
        "export_blocked",
        "export_restricted",
        "license_required",
        "no_export",
        "raw_source_restricted",
        "restricted",
    }
    if export_policy in restricted_tokens or any(token in export_policy for token in restricted_tokens):
        return False
    return True


def _export_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _first_evidence_ref(row: dict[str, Any]) -> str | None:
    evidence_refs = row.get("evidence_refs")
    if isinstance(evidence_refs, list):
        for evidence_ref in evidence_refs:
            if isinstance(evidence_ref, str):
                return evidence_ref
    return None


def _derived_output_restricted(row: dict[str, Any]) -> bool:
    restrictions = row.get("source_restrictions")
    if not isinstance(restrictions, list):
        return False
    restricted_tokens = {
        "derived_output_restricted",
        "export_blocked",
        "export_restricted",
        "license_required",
        "raw_source_restricted",
        "restricted",
    }
    return any(
        isinstance(restriction, str)
        and restriction.lower().replace(" ", "_") in restricted_tokens
        for restriction in restrictions
    )
