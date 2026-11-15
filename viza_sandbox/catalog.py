"""The sandbox attribute catalog: which precomputed attributes exist and how they are defined."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

CATALOG_VERSION = "viza_sandbox_catalog_v1"
DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "viza_sandbox_attribute_catalog.json"
)
RAW_INPUTS = ("close", "volume")
SECTOR_ZSCORE = "sector_zscore"


class AttributeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    display_name: str
    description: str
    unit: str
    formula: Literal[
        "simple_return",
        "rolling_std",
        "rolling_mean",
        "rsi_cutler",
        "rolling_mean_dollar_volume",
        "sector_zscore",
    ]
    params: dict[str, int]
    inputs: list[str]
    availability_rule: Literal["eod_of_latest_input"]
    source_type: Literal["viza_computed"]
    rights_class: Literal["viza_computed"]
    classification_snapshot: bool = False


class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    attributes: list[AttributeSpec]

    @model_validator(mode="after")
    def _validate(self) -> Catalog:
        keys = [spec.key for spec in self.attributes]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"duplicate attribute keys: {', '.join(duplicates)}")
        known = set(keys) | set(RAW_INPUTS)
        for spec in self.attributes:
            for name in spec.inputs:
                if name not in known:
                    raise ValueError(f"unknown input: {name}")
        return self

    def keys(self) -> list[str]:
        return [spec.key for spec in self.attributes]

    def base(self) -> list[AttributeSpec]:
        return [spec for spec in self.attributes if spec.formula != SECTOR_ZSCORE]

    def sector_relative(self) -> list[AttributeSpec]:
        return [spec for spec in self.attributes if spec.formula == SECTOR_ZSCORE]


def load_catalog(path: Path | None = None) -> Catalog:
    source = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    return Catalog.model_validate(json.loads(source.read_text(encoding="utf-8")))
