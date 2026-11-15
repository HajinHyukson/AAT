from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from viza.file_format.container import read_viza_manifest, read_viza_section, write_viza_container
from viza.file_format.models import (
    CANONICAL_SECTION_NAMES,
    SectionStatus,
    VisibilityMode,
    VizaFileManifest,
    VizaModuleRequirement,
    VizaSectionDescriptor,
    VizaWriteResult,
)
from viza.modules.core_strategy import CORE_MODULE_ID
from viza.modules.real_estate_acquisition import REAL_ESTATE_MODULE_ID


REAL_ESTATE_GRAPH_SCHEMA = "viza.real_estate.acquisition.graph.experimental.v1"
REQUIRED_PROPERTY_FIELDS = [
    "property_id",
    "property_name",
    "market",
    "property_type",
    "units",
    "asking_price",
    "noi",
    "cap_rate",
    "rent_growth_assumption",
    "expense_growth_assumption",
    "debt_rate",
    "loan_to_value",
]


class RealEstateProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: str
    property_name: str
    market: str
    property_type: str
    units: int
    asking_price: float
    noi: float
    cap_rate: float
    rent_growth_assumption: float
    expense_growth_assumption: float
    debt_rate: float
    loan_to_value: float


class RealEstateRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.real_estate.acquisition.result.v1", alias="schema")
    run_id: str
    status: str
    deal_pipeline: list[dict[str, Any]] = Field(default_factory=list)
    investment_memo: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def load_property_universe(csv_path: str | Path) -> list[RealEstateProperty]:
    with Path(csv_path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_PROPERTY_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"property CSV missing required fields: {', '.join(missing)}")
        return [RealEstateProperty.model_validate(_normalize_property_row(row)) for row in reader]


def run_real_estate_acquisition_graph(graph_payload: dict[str, Any]) -> RealEstateRunResult:
    config = graph_payload.get("config") if isinstance(graph_payload.get("config"), dict) else {}
    csv_path = config.get("csv_path")
    if not isinstance(csv_path, str) or not csv_path:
        raise ValueError("real estate graph requires config.csv_path")
    min_dscr = _read_float(config.get("min_dscr"), 1.2)
    max_ltv = _read_float(config.get("max_loan_to_value"), 0.8)
    properties = load_property_universe(csv_path)
    pipeline = [_score_property(property_, min_dscr=min_dscr, max_ltv=max_ltv) for property_ in properties]
    pipeline.sort(key=lambda row: row["deal_score"], reverse=True)
    return RealEstateRunResult(
        run_id=f"real-estate-run-{uuid4()}",
        status="completed",
        deal_pipeline=pipeline,
        investment_memo=_investment_memo(pipeline),
        warnings=[],
    )


def export_real_estate_graph_to_viza(
    graph_payload: dict[str, Any],
    target_path: str | Path,
    *,
    display_name: str | None = None,
) -> tuple[VizaWriteResult, dict[str, Any]]:
    payload = {
        "schema": REAL_ESTATE_GRAPH_SCHEMA,
        **graph_payload,
        "experimental_runtime_support": True,
    }
    sections = {
        section_name: VizaSectionDescriptor(status=SectionStatus.ABSENT, reason="not_included")
        for section_name in CANONICAL_SECTION_NAMES
    }
    sections["methodology_graph"] = VizaSectionDescriptor(
        status=SectionStatus.INCLUDED,
        path="graph/methodology.json",
        schema=REAL_ESTATE_GRAPH_SCHEMA,
        reason="module_aware_experimental_graph",
    )
    timestamp = datetime.now(timezone.utc)
    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id=f"viza-file-{uuid4()}",
        display_name=display_name or _read_string(graph_payload.get("name"), "Real Estate Strategy"),
        object_kind="methodology",
        primary_mode="real_estate_acquisition",
        exchange_modes=["real_estate_acquisition"],
        visibility=VisibilityMode.WHITE_BOX,
        created_at=timestamp,
        updated_at=timestamp,
        required_modules=[
            VizaModuleRequirement(module_id=CORE_MODULE_ID, version_range=">=0.1.0"),
            VizaModuleRequirement(module_id=REAL_ESTATE_MODULE_ID, version_range=">=0.1.0"),
        ],
        sections=sections,
        permissions={
            "open_allowed": True,
            "run_allowed": True,
            "fork_allowed": True,
            "export_allowed": True,
            "redistribute_allowed": False,
        },
        integrity={"signature_status": "unsigned", "runtime_support": "experimental"},
    )
    result = write_viza_container(target_path, manifest, {"methodology_graph": payload})
    written_manifest = read_viza_manifest(target_path)
    return result, written_manifest.model_dump(mode="json", by_alias=True)


def import_real_estate_graph_from_viza(path: str | Path) -> dict[str, Any]:
    section = read_viza_section(path, "methodology_graph")
    payload = json.loads(section.content.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != REAL_ESTATE_GRAPH_SCHEMA:
        raise ValueError("not a real estate acquisition graph payload")
    return payload


def _score_property(
    property_: RealEstateProperty,
    *,
    min_dscr: float,
    max_ltv: float,
) -> dict[str, Any]:
    projected_noi = property_.noi * (
        1 + property_.rent_growth_assumption - property_.expense_growth_assumption
    )
    annual_debt_service = property_.asking_price * property_.loan_to_value * property_.debt_rate
    dscr = projected_noi / annual_debt_service if annual_debt_service else 0
    passes_dscr = dscr >= min_dscr
    passes_ltv = property_.loan_to_value <= max_ltv
    deal_score = (
        min(property_.cap_rate / 0.1, 1.5) * 0.4
        + min(dscr / 2.0, 1.5) * 0.4
        + max(property_.rent_growth_assumption - property_.expense_growth_assumption, -0.05) * 4
    )
    return {
        "property_id": property_.property_id,
        "property_name": property_.property_name,
        "market": property_.market,
        "property_type": property_.property_type,
        "units": property_.units,
        "asking_price": property_.asking_price,
        "projected_noi": round(projected_noi, 2),
        "cap_rate": property_.cap_rate,
        "dscr": round(dscr, 3),
        "passes_dscr": passes_dscr,
        "passes_ltv": passes_ltv,
        "deal_score": round(deal_score, 4),
    }


def _investment_memo(pipeline: list[dict[str, Any]]) -> dict[str, Any]:
    top = pipeline[0] if pipeline else {}
    markdown = (
        f"# {top.get('property_name', 'No property')}\n\n"
        f"Market: {top.get('market', 'n/a')}\n\n"
        f"Deal score: {top.get('deal_score', 'n/a')}\n\n"
        f"DSCR: {top.get('dscr', 'n/a')}\n"
    )
    return {
        "top_property_id": top.get("property_id"),
        "markdown": markdown,
        "summary": "Prototype real estate acquisition memo generated from local CSV inputs.",
    }


def _normalize_property_row(row: dict[str, str]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field in REQUIRED_PROPERTY_FIELDS:
        value = row.get(field)
        if field in {"property_id", "property_name", "market", "property_type"}:
            normalized[field] = value or ""
        elif field == "units":
            normalized[field] = int(float(value or 0))
        else:
            normalized[field] = float(value or 0)
    return normalized


def _read_float(value: Any, fallback: float) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else fallback


def _read_string(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback
