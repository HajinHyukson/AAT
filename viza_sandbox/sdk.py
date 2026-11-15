"""User-facing SDK for strategy code running inside the sandbox.

Reads a materialized panel directory (``prices.parquet``, ``universe.parquet``,
``manifest.json``, and, when the panel has catalog attributes, ``attributes.parquet`` and
``catalog.json``). Every accessor enforces point-in-time visibility: a row is
visible on its ``event_date`` D iff ``available_at <= end_of_day_utc(D)``, and,
when a cutoff is set, also ``available_at <= cutoff``. There is no bypass.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from viza_sandbox.pit import end_of_day_utc

__all__ = [
    "VizaData",
    "Scores",
    "scores",
    "coerce_return",
    "ReturnDeclarationError",
    "AttributeUnavailableError",
]

_ATTRIBUTES_FILE = "attributes.parquet"
_CATALOG_FILE = "catalog.json"
_ATTRIBUTE_INDEX_COLUMNS = ("security_id", "event_date", "available_at")

_FLOAT_DF_MESSAGE = (
    "Return value is a float DataFrame; declare it with viza.scores(df) or viza.weights(df)."
)


class ReturnDeclarationError(ValueError):
    """The strategy returned a value that was not declared as scores."""


class AttributeUnavailableError(LookupError):
    """A catalog attribute was requested that this panel cannot serve."""


class Scores:
    """Declared score output: wide frame, date index, security columns, float."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame


def scores(frame: pd.DataFrame) -> Scores:
    if not isinstance(frame, pd.DataFrame):
        raise ReturnDeclarationError("viza.scores expects a pandas DataFrame.")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ReturnDeclarationError("viza.scores requires a datetime-like index.")
    if not all(pd.api.types.is_numeric_dtype(t) and not pd.api.types.is_bool_dtype(t)
               for t in frame.dtypes):
        raise ReturnDeclarationError("viza.scores requires numeric columns.")
    return Scores(frame)


def coerce_return(value: object) -> Scores:
    if isinstance(value, Scores):
        return value
    if isinstance(value, pd.DataFrame):
        if len(value.columns) and all(pd.api.types.is_bool_dtype(t) for t in value.dtypes):
            raise ReturnDeclarationError(
                "Boolean signals are not supported in this version; return viza.scores(df)."
            )
        if any(pd.api.types.is_float_dtype(t) for t in value.dtypes):
            raise ReturnDeclarationError(_FLOAT_DF_MESSAGE)
    if isinstance(value, dict):
        raise ReturnDeclarationError(
            "Report returns are not supported in this version; return viza.scores(df)."
        )
    raise ReturnDeclarationError(f"Unsupported return type {type(value).__name__}.")


def _day_end(dates: pd.Series) -> pd.Series:
    """``end_of_day_utc`` of each date (computed once per distinct date), as UTC timestamps."""
    days = pd.to_datetime(dates)
    ends = {day: end_of_day_utc(day.date()) for day in days.unique()}
    return pd.to_datetime(days.map(ends), utc=True)


class VizaData:
    def __init__(self, panel_dir: Path, cutoff: datetime | None = None) -> None:
        self._dir = Path(panel_dir)
        self._cutoff = cutoff

    @property
    def manifest(self) -> dict:
        return json.loads((self._dir / "manifest.json").read_text())

    def as_of(self, on: date) -> VizaData:
        cutoff = end_of_day_utc(on)
        if self._cutoff is not None:
            cutoff = min(self._cutoff, cutoff)
        return VizaData(self._dir, cutoff=cutoff)

    def _read(self, name: str, columns: Sequence[str] | None = None) -> pd.DataFrame:
        frame = pd.read_parquet(
            self._dir / name, engine="pyarrow", columns=list(columns) if columns else None
        )
        frame["event_date"] = pd.to_datetime(frame["event_date"])
        return frame

    @staticmethod
    def _in_range(frame: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
        if start is not None:
            frame = frame[frame["event_date"] >= pd.Timestamp(start)]
        if end is not None:
            frame = frame[frame["event_date"] <= pd.Timestamp(end)]
        return frame

    def _visible(
        self,
        name: str,
        start: date | None,
        end: date | None,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Rows of a dated panel file that are visible under the point-in-time rule."""
        frame = self._read(name, columns)
        available = pd.to_datetime(frame["available_at"], utc=True)
        keep = available <= _day_end(frame["event_date"])
        if self._cutoff is not None:
            keep &= available <= pd.Timestamp(self._cutoff)
        return self._in_range(frame[keep], start, end)

    def prices(
        self, field: str = "close", start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        frame = self._visible("prices.parquet", start, end)
        if frame.empty:
            return pd.DataFrame(index=pd.DatetimeIndex([], name="event_date"))
        wide = frame.pivot(index="event_date", columns="security_id", values=field)
        wide.columns.name = None
        return wide.sort_index()

    def prices_long(
        self,
        fields: Sequence[str] = ("close", "volume"),
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        frame = self._visible("prices.parquet", start, end)
        return frame[["event_date", "security_id", *fields]].reset_index(drop=True)

    def _attribute_keys(self) -> list[str]:
        path = self._dir / _ATTRIBUTES_FILE
        if not path.exists():
            reason = self.manifest.get("attributes_unavailable_reason")
            raise AttributeUnavailableError(reason or "This panel has no catalog attributes.")
        names = pq.read_schema(path).names
        return [name for name in names if name not in _ATTRIBUTE_INDEX_COLUMNS]

    def attribute(
        self, key: str, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        """A VIZA-precomputed catalog attribute as a wide frame, like ``prices``."""
        keys = self._attribute_keys()
        if key not in keys:
            raise AttributeUnavailableError(
                f"Unknown attribute {key!r}. Available: {', '.join(keys)}"
            )
        frame = self._visible(
            _ATTRIBUTES_FILE, start, end, columns=[*_ATTRIBUTE_INDEX_COLUMNS, key]
        )
        if frame.empty:
            return pd.DataFrame(index=pd.DatetimeIndex([], name="event_date"))
        wide = frame.pivot(index="event_date", columns="security_id", values=key)
        wide.columns.name = None
        return wide.sort_index()

    def catalog(self) -> pd.DataFrame:
        """The attributes this panel serves: key, name, description, unit, snapshot flag."""
        keys = self._attribute_keys()
        columns = ["key", "display_name", "description", "unit", "classification_snapshot"]
        entries = json.loads((self._dir / _CATALOG_FILE).read_text(encoding="utf-8"))
        rows = [
            {column: entry.get(column) for column in columns}
            for entry in entries["attributes"]
            if entry["key"] in keys
        ]
        return pd.DataFrame(rows, columns=columns)

    def universe(self, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        frame = self._read("universe.parquet")
        if self._cutoff is not None:
            frame = frame[frame["event_date"] <= pd.Timestamp(self._cutoff.date())]
        frame = self._in_range(frame, start, end)
        columns = [
            "event_date", "security_id", "ticker", "exchange", "currency",
            "sector", "industry", "classification_as_of",
        ]
        return frame[columns].reset_index(drop=True)
