"""User-facing SDK for strategy code running inside the sandbox.

Reads a materialized panel directory (``prices.parquet``, ``universe.parquet``,
``manifest.json``). Every accessor enforces point-in-time visibility: a row is
visible on its ``event_date`` D iff ``available_at <= end_of_day_utc(D)``, and,
when a cutoff is set, also ``available_at <= cutoff``. There is no bypass.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from viza_sandbox.pit import end_of_day_utc

__all__ = ["VizaData", "Scores", "scores", "coerce_return", "ReturnDeclarationError"]

_FLOAT_DF_MESSAGE = (
    "Return value is a float DataFrame; declare it with viza.scores(df) or viza.weights(df)."
)


class ReturnDeclarationError(ValueError):
    """The strategy returned a value that was not declared as scores."""


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
    """Last instant of each UTC calendar day, as tz-aware timestamps."""
    return (
        pd.to_datetime(dates).dt.tz_localize("UTC")
        + pd.Timedelta(days=1)
        - pd.Timedelta(microseconds=1)
    )


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

    def _read(self, name: str) -> pd.DataFrame:
        frame = pd.read_parquet(self._dir / name, engine="pyarrow")
        frame["event_date"] = pd.to_datetime(frame["event_date"])
        return frame

    @staticmethod
    def _in_range(frame: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
        if start is not None:
            frame = frame[frame["event_date"] >= pd.Timestamp(start)]
        if end is not None:
            frame = frame[frame["event_date"] <= pd.Timestamp(end)]
        return frame

    def _visible_prices(self, start: date | None, end: date | None) -> pd.DataFrame:
        frame = self._read("prices.parquet")
        available = pd.to_datetime(frame["available_at"], utc=True)
        keep = available <= _day_end(frame["event_date"])
        if self._cutoff is not None:
            keep &= available <= pd.Timestamp(self._cutoff)
        return self._in_range(frame[keep], start, end)

    def prices(
        self, field: str = "close", start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        frame = self._visible_prices(start, end)
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
        frame = self._visible_prices(start, end)
        return frame[["event_date", "security_id", *fields]].reset_index(drop=True)

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
