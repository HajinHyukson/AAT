"""The precomputed attribute store: catalog attributes for every security-day, as Parquet.

One store per (catalog version, canonical snapshot, price source, adjustment status). It is
built by the operator (``python -m viza_sandbox.cli build-attributes``); panel materialization
only slices it. Layout: ``<data_dir>/attributes/<store_id>/{store.json, YYYY.parquet}``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
from pydantic import BaseModel

from viza_sandbox.attributes import compute_base, sector_zscore
from viza_sandbox.canonical import CanonicalSource
from viza_sandbox.catalog import CATALOG_VERSION, Catalog, catalog_digest, load_catalog
from viza_sandbox.config import SandboxSettings
from viza_sandbox.trading_calendar import trading_day_mask

# Calendar days of prices loaded before a chunk so the longest window (252 trading days) is
# complete on the chunk's first day.
LOOKBACK_CALENDAR_DAYS = 400
STORE_MANIFEST_FILENAME = "store.json"


class AttributeStoreError(ValueError):
    pass


class AttributeStoreManifest(BaseModel):
    store_id: str
    catalog_version: str
    canonical_snapshot_id: str
    price_source: str
    price_adjustment_status: str
    start: date
    end: date
    keys: list[str]
    row_counts: dict[str, int]
    # Dates left out of the trading calendar (too few securities had a bar), with bar counts.
    excluded_dates: dict[str, int] = {}
    built_at: datetime


def attribute_store_id(
    catalog_version: str,
    canonical_snapshot_id: str,
    price_source: str,
    price_adjustment_status: str,
    catalog_content_digest: str,
    sector_content_digest: str,
) -> str:
    payload = {
        "catalog_digest": catalog_content_digest,
        "sector_digest": sector_content_digest,
        "catalog_version": catalog_version,
        "canonical_snapshot_id": canonical_snapshot_id,
        "price_source": price_source,
        "price_adjustment_status": price_adjustment_status,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def sector_digest(securities: pl.DataFrame) -> str:
    """sha256 of every security's sector, so a reclassification invalidates the store."""
    pairs = sorted(
        zip(securities["security_id"].to_list(), securities["sector"].to_list()),
        key=lambda pair: pair[0],
    )
    return hashlib.sha256(json.dumps(pairs).encode("utf-8")).hexdigest()


def _store_dir(settings: SandboxSettings, store_id: str) -> Path:
    return settings.data_dir / "attributes" / store_id


def find_attribute_store(settings: SandboxSettings, store_id: str) -> AttributeStoreManifest | None:
    path = _store_dir(settings, store_id) / STORE_MANIFEST_FILENAME
    if not path.exists():
        return None
    return AttributeStoreManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _schema(keys: list[str]) -> dict[str, pl.DataType]:
    return {"security_id": pl.Utf8, "event_date": pl.Date, **{key: pl.Float64 for key in keys}}


def _chunk(
    bars: pl.DataFrame, sector: dict[str, str | None], catalog: Catalog, lo: date, hi: date
) -> tuple[pl.DataFrame, dict[str, int]]:
    """Attributes for dates in ``[lo, hi]``, computed from ``bars`` (which include lookback).

    Also returns the dates in ``[lo, hi]`` left out of the trading calendar, with bar counts.
    """
    keys = catalog.keys()
    if bars.is_empty():
        return pl.DataFrame(schema=_schema(keys)), {}
    if bars.select(["security_id", "event_date"]).is_duplicated().any():
        raise AttributeStoreError("duplicate price rows for one security and date")

    frame = bars.select(["security_id", "event_date", "close", "volume"]).to_pandas()
    frame["event_date"] = pd.to_datetime(frame["event_date"])
    close = frame.pivot(index="event_date", columns="security_id", values="close")
    volume = frame.pivot(index="event_date", columns="security_id", values="volume")
    volume = volume.astype("float64")

    trading = trading_day_mask(close)
    in_range = (close.index >= pd.Timestamp(lo)) & (close.index <= pd.Timestamp(hi))
    excluded = {
        day.strftime("%Y-%m-%d"): int(count)
        for day, count in close[~trading & in_range].notna().sum(axis=1).items()
    }
    close, volume = close[trading], volume[trading]

    rows = (close.index >= pd.Timestamp(lo)) & (close.index <= pd.Timestamp(hi))
    values = {key: value.loc[rows] for key, value in compute_base(close, volume, catalog).items()}
    for spec in catalog.sector_relative():
        values[spec.key] = sector_zscore(values[spec.inputs[0]], sector)

    dates = close.index[rows]
    securities = close.columns.to_numpy()
    data: dict[str, object] = {
        "security_id": np.tile(securities, len(dates)),
        "event_date": np.repeat(dates.to_numpy(), len(securities)),
    }
    for key in keys:
        data[key] = values[key].to_numpy(dtype="float64").ravel()
    frame = (
        pl.DataFrame(data)
        .with_columns(pl.col("event_date").cast(pl.Date), pl.col(keys).fill_nan(None))
        .filter(pl.any_horizontal(pl.col(keys).is_not_null()))
        .select(list(_schema(keys)))
    )
    return frame, excluded


def build_attribute_store(
    source: CanonicalSource,
    settings: SandboxSettings,
    *,
    start: date,
    end: date,
    price_source: str = "faustcalc_fmp_snapshot",
) -> AttributeStoreManifest:
    if end < start:
        raise AttributeStoreError("end must not be before start")
    catalog = load_catalog()
    canonical_snapshot_id = source.snapshot_id(source=price_source)
    securities = source.securities()
    store_id = attribute_store_id(
        CATALOG_VERSION,
        canonical_snapshot_id,
        price_source,
        settings.price_adjustment_status,
        catalog_digest(),
        sector_digest(securities),
    )
    existing = find_attribute_store(settings, store_id)
    if existing is not None and (existing.start, existing.end) == (start, end):
        return existing

    sector = dict(zip(securities["security_id"].to_list(), securities["sector"].to_list()))

    directory = _store_dir(settings, store_id)
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{store_id}.tmp-", dir=directory.parent))
    try:
        row_counts: dict[str, int] = {}
        excluded_dates: dict[str, int] = {}
        for year in range(start.year, end.year + 1):
            lo, hi = max(date(year, 1, 1), start), min(date(year, 12, 31), end)
            bars = source.price_bars(
                lo - timedelta(days=LOOKBACK_CALENDAR_DAYS), hi, source=price_source
            )
            chunk, excluded = _chunk(bars, sector, catalog, lo, hi)
            excluded_dates.update(excluded)
            chunk.write_parquet(staging / f"{year}.parquet")
            row_counts[str(year)] = chunk.height
        manifest = AttributeStoreManifest(
            store_id=store_id,
            catalog_version=CATALOG_VERSION,
            canonical_snapshot_id=canonical_snapshot_id,
            price_source=price_source,
            price_adjustment_status=settings.price_adjustment_status,
            start=start,
            end=end,
            keys=catalog.keys(),
            row_counts=row_counts,
            excluded_dates=excluded_dates,
            built_at=datetime.now(timezone.utc),
        )
        (staging / STORE_MANIFEST_FILENAME).write_text(
            manifest.model_dump_json(), encoding="utf-8"
        )
        if directory.exists():
            shutil.rmtree(directory)
        os.replace(staging, directory)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return manifest


def read_attributes(
    settings: SandboxSettings, store_id: str, start: date, end: date
) -> pl.DataFrame:
    manifest = find_attribute_store(settings, store_id)
    if manifest is None:
        raise AttributeStoreError(f"attribute store not found: {store_id}")
    directory = _store_dir(settings, store_id)
    files = [
        directory / f"{year}.parquet"
        for year in range(
            max(start.year, manifest.start.year), min(end.year, manifest.end.year) + 1
        )
    ]
    if not files:
        return pl.DataFrame(schema=_schema(manifest.keys))
    # Lazy scan: only the rows in range are read into memory, not whole year files.
    return (
        pl.scan_parquet(files)
        .filter((pl.col("event_date") >= start) & (pl.col("event_date") <= end))
        .collect()
    )
