from __future__ import annotations

from typing import Iterator, Literal, Protocol

from pydantic import BaseModel

from engine.contracts import TimeWindow, TimestampedRecord


LicenseTier = Literal["public", "free_api", "licensed", "alt_data"]


class AdapterHealth(BaseModel):
    name: str
    healthy: bool
    message: str = ""


class NormalizedEvent(TimestampedRecord):
    source: str
    source_id: str
    payload: dict


class Adapter(Protocol):
    name: str
    license_tier: LicenseTier

    def fetch(self, window: TimeWindow) -> Iterator[NormalizedEvent]: ...

    def health_check(self) -> AdapterHealth: ...
