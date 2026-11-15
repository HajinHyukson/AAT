from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import models


METHODOLOGY_LEGACY = "legacy"
METHODOLOGY_RESIDUAL_SAFETY = "residual_safety_v1"
METHODOLOGY_HIERARCHICAL_MARKET_FIRST = "hierarchical_market_first_v1"

HIERARCHICAL_BASELINE_MODEL_VERSION = "factor-baseline-hierarchical-market-v1"
HIERARCHICAL_FACTOR_BASKET_VERSION = "mvp_expanded_hierarchical_market_v1"
RESIDUAL_SAFETY_MODEL_VERSION = "factor-baseline-residual-safety-v1"
RESIDUAL_SAFETY_FACTOR_BASKET_VERSION = "mvp_expanded_residual_safety_v1"
LEGACY_MODEL_VERSION = "factor-baseline-v0"
LEGACY_FACTOR_BASKET_VERSION = "mvp_expanded_v0"

VALID_ATTRIBUTION_METHODOLOGIES = (
    METHODOLOGY_LEGACY,
    METHODOLOGY_RESIDUAL_SAFETY,
    METHODOLOGY_HIERARCHICAL_MARKET_FIRST,
)
DEFAULT_ATTRIBUTION_METHODOLOGY = METHODOLOGY_RESIDUAL_SAFETY
VALID_CADENCES = ("daily", "weekly", "monthly")


@dataclass(frozen=True)
class MethodologyDefinition:
    methodology: str
    display_name: str
    status: str
    is_default: bool
    model_version: str
    factor_basket_version: str
    runner_config: dict

    @property
    def supported_cadences(self) -> list[str]:
        return list(VALID_CADENCES)


DEFAULT_RUNNER_CONFIG = {
    "use_expanded_mvp": True,
    "include_event_evidence": True,
    "lookback_days": 252,
}

METHODOLOGY_DEFINITIONS = {
    METHODOLOGY_LEGACY: MethodologyDefinition(
        methodology=METHODOLOGY_LEGACY,
        display_name="Legacy Baseline",
        status="archived",
        is_default=False,
        model_version=LEGACY_MODEL_VERSION,
        factor_basket_version=LEGACY_FACTOR_BASKET_VERSION,
        runner_config=DEFAULT_RUNNER_CONFIG,
    ),
    METHODOLOGY_RESIDUAL_SAFETY: MethodologyDefinition(
        methodology=METHODOLOGY_RESIDUAL_SAFETY,
        display_name="Residual Safety v1",
        status="active",
        is_default=True,
        model_version=RESIDUAL_SAFETY_MODEL_VERSION,
        factor_basket_version=RESIDUAL_SAFETY_FACTOR_BASKET_VERSION,
        runner_config=DEFAULT_RUNNER_CONFIG,
    ),
    METHODOLOGY_HIERARCHICAL_MARKET_FIRST: MethodologyDefinition(
        methodology=METHODOLOGY_HIERARCHICAL_MARKET_FIRST,
        display_name="Hierarchical Market First v1",
        status="active",
        is_default=False,
        model_version=HIERARCHICAL_BASELINE_MODEL_VERSION,
        factor_basket_version=HIERARCHICAL_FACTOR_BASKET_VERSION,
        runner_config=DEFAULT_RUNNER_CONFIG,
    ),
}


def methodology_definition(methodology: str) -> MethodologyDefinition:
    try:
        return METHODOLOGY_DEFINITIONS[methodology]
    except KeyError as exc:
        raise ValueError(f"unsupported attribution methodology {methodology}") from exc


def model_version_for_methodology(methodology: str) -> str:
    return methodology_definition(methodology).model_version


def factor_basket_version_for_methodology(methodology: str) -> str:
    return methodology_definition(methodology).factor_basket_version


def methodology_for_versions(*, model_version: str, factor_basket_version: str) -> str:
    for definition in METHODOLOGY_DEFINITIONS.values():
        if (
            definition.model_version == model_version
            and definition.factor_basket_version == factor_basket_version
        ):
            return definition.methodology
    return METHODOLOGY_LEGACY


def ensure_methodology_seed_rows(*, session) -> None:
    now = datetime.now(timezone.utc)
    for definition in METHODOLOGY_DEFINITIONS.values():
        stmt = insert(models.AttributionMethodology).values(
            methodology=definition.methodology,
            display_name=definition.display_name,
            status=definition.status,
            is_default=definition.is_default,
            model_version=definition.model_version,
            factor_basket_version=definition.factor_basket_version,
            supported_cadences=definition.supported_cadences,
            runner_config=definition.runner_config,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[models.AttributionMethodology.methodology],
            set_={
                "display_name": stmt.excluded.display_name,
                "status": stmt.excluded.status,
                "is_default": stmt.excluded.is_default,
                "model_version": stmt.excluded.model_version,
                "factor_basket_version": stmt.excluded.factor_basket_version,
                "supported_cadences": stmt.excluded.supported_cadences,
                "runner_config": stmt.excluded.runner_config,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        session.execute(stmt)


def load_methodology(*, session, methodology: str) -> models.AttributionMethodology | None:
    row = session.execute(
        select(models.AttributionMethodology).where(
            models.AttributionMethodology.methodology == methodology
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    if methodology in METHODOLOGY_DEFINITIONS:
        definition = METHODOLOGY_DEFINITIONS[methodology]
        return models.AttributionMethodology(
            methodology=definition.methodology,
            display_name=definition.display_name,
            status=definition.status,
            is_default=definition.is_default,
            model_version=definition.model_version,
            factor_basket_version=definition.factor_basket_version,
            supported_cadences=definition.supported_cadences,
            runner_config=definition.runner_config,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    return None
