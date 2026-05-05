from __future__ import annotations

from datetime import datetime
from uuid import UUID

from engine.contracts import EventTaxonomyRecord


MODEL_VERSION = "event-taxonomy-v0"


FORM_TAXONOMY = {
    "8-K": ("corporate_event", "current_report", "mixed", 0.70),
    "10-K": ("periodic_results", "annual_report", "mixed", 0.65),
    "10-Q": ("periodic_results", "quarterly_report", "mixed", 0.55),
    "13D": ("ownership", "activist_or_large_holder", "mixed", 0.75),
    "SC 13D": ("ownership", "activist_or_large_holder", "mixed", 0.75),
    "13G": ("ownership", "passive_large_holder", "mixed", 0.50),
    "SCHEDULE 13G": ("ownership", "passive_large_holder", "mixed", 0.50),
    "4": ("insider_activity", "form_4", "mixed", 0.35),
    "144": ("insider_activity", "planned_sale", "negative", 0.25),
}


EIGHT_K_ITEM_TAXONOMY = {
    "2.02": ("earnings", "results_of_operations", "mixed", 0.90),
    "2.05": ("restructuring", "exit_or_disposal", "mixed", 0.75),
    "2.06": ("accounting", "material_impairment", "negative", 0.85),
    "5.02": ("management", "officer_or_director_change", "mixed", 0.65),
    "7.01": ("disclosure", "reg_fd", "mixed", 0.50),
    "8.01": ("corporate_event", "other_event", "mixed", 0.55),
    "9.01": ("disclosure", "financial_statements_exhibits", "mixed", 0.35),
}


def classify_event(
    *,
    event_id: UUID,
    event_type: str,
    event_time: datetime,
    ingestion_time: datetime,
    timestamp_available: datetime,
    structured_payload: dict | None = None,
) -> EventTaxonomyRecord:
    item_code = _extract_8k_item_code(structured_payload or {})
    if event_type.upper() == "8-K" and item_code in EIGHT_K_ITEM_TAXONOMY:
        category, subtype, direction, materiality = EIGHT_K_ITEM_TAXONOMY[item_code]
    else:
        category, subtype, direction, materiality = FORM_TAXONOMY.get(
            event_type.upper(),
            ("general_disclosure", "unclassified", "mixed", 0.25),
        )

    return EventTaxonomyRecord(
        event_id=event_id,
        event_category=category,
        event_subtype=subtype,
        event_direction=direction,
        materiality=materiality,
        taxonomy_version=MODEL_VERSION,
        evidence_payload={
            "event_type": event_type,
            "eight_k_item_code": item_code,
            "model_version": MODEL_VERSION,
        },
        event_time=event_time,
        ingestion_time=ingestion_time,
        timestamp_available=timestamp_available,
    )


def _extract_8k_item_code(payload: dict) -> str | None:
    for key in ("item", "item_code", "eight_k_item", "8k_item"):
        value = payload.get(key)
        if value is not None:
            return str(value).strip()
    return None
