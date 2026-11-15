"""Formulas for the price-based catalog attributes.

Inputs are wide frames on the full trading calendar: index = every trading date, columns =
``security_id``, NaN where a security has no bar. Windows are counted in calendar rows, so a
gap inside a window makes the value null. Nothing here fills, clips or winsorizes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

import numpy as np
import pandas as pd

from viza_sandbox.catalog import AttributeSpec, Catalog

MIN_SECTOR_MEMBERS = 3


def _simple_return(close: pd.DataFrame, window: int) -> pd.DataFrame:
    return close / close.shift(window) - 1.0


def _rolling_mean(frame: pd.DataFrame, window: int) -> pd.DataFrame:
    return frame.rolling(window, min_periods=window).mean()


def _rolling_std(frame: pd.DataFrame, window: int) -> pd.DataFrame:
    return frame.rolling(window, min_periods=window).std(ddof=1)


def _rsi_cutler(close: pd.DataFrame, window: int) -> pd.DataFrame:
    change = close.diff()
    gain = _rolling_mean(change.clip(lower=0.0), window)
    loss = _rolling_mean((-change).clip(lower=0.0), window)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100.0 - 100.0 / (1.0 + gain / loss)
    rsi = rsi.mask((loss == 0.0) & (gain > 0.0), 100.0)
    return rsi.mask((loss == 0.0) & (gain == 0.0), 50.0)


def _compute(
    spec: AttributeSpec, close: pd.DataFrame, volume: pd.DataFrame, done: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    window = spec.params.get("window", 0)
    if spec.formula == "simple_return":
        return _simple_return(close, window)
    if spec.formula == "rolling_mean":
        return _rolling_mean(close, window)
    if spec.formula == "rolling_std":
        return _rolling_std(done[spec.inputs[0]], window)
    if spec.formula == "rsi_cutler":
        return _rsi_cutler(close, window)
    if spec.formula == "rolling_mean_dollar_volume":
        return _rolling_mean(close * volume, window)
    raise ValueError(f"compute_base does not handle formula {spec.formula!r} ({spec.key})")


def compute_base(
    close: pd.DataFrame, volume: pd.DataFrame, catalog: Catalog
) -> dict[str, pd.DataFrame]:
    """Every non-sector-relative catalog attribute, keyed by attribute key, in catalog order."""
    done: dict[str, pd.DataFrame] = {}
    for spec in catalog.base():
        done[spec.key] = _compute(spec, close, volume, done)
    return done


def sector_zscore(values: pd.DataFrame, sector: Mapping[str, str | None]) -> pd.DataFrame:
    """Per-date z-score of each security's value within its sector (sample std).

    Null without a sector, with fewer than three valued members on the date, or when the
    members' values do not differ.
    """
    members: dict[str, list[str]] = defaultdict(list)
    for security_id in values.columns:
        name = sector.get(security_id)
        if name is not None:
            members[name].append(security_id)

    out = pd.DataFrame(np.nan, index=values.index, columns=values.columns)
    for columns in members.values():
        if len(columns) < MIN_SECTOR_MEMBERS:
            continue
        group = values[columns]
        std = group.std(axis=1, ddof=1)
        usable = (group.notna().sum(axis=1) >= MIN_SECTOR_MEMBERS) & (std > 0.0)
        centered = group.sub(group.mean(axis=1), axis=0).div(std.where(usable), axis=0)
        out[columns] = centered
    return out

