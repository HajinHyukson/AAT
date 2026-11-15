"""Point-in-time panel materialization: canonical frames -> cached Parquet panels.

Applies the availability policy from ``viza_sandbox.pit`` to canonical price
bars, derives universe membership, and writes immutable Parquet panels keyed
by a content-addressed ``manifest_id``. A later run with the same spec,
canonical snapshot, and settings is served from the on-disk cache without
touching the canonical source again.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import polars as pl
from pydantic import BaseModel, Field

from viza_sandbox.attribute_store import (
    AttributeStoreManifest,
    attribute_store_id,
    find_attribute_store,
    sector_digest,
    read_attributes,
)
from viza_sandbox.canonical import CanonicalSource
from viza_sandbox.catalog import CATALOG_VERSION, DEFAULT_CATALOG_PATH, catalog_digest
from viza_sandbox.config import SandboxSettings
from viza_sandbox.trading_calendar import trading_day_mask
from viza_sandbox.pit import EOD_POLICY_VERSION, eod_available_at, end_of_day_utc

PRICES_FILENAME = "prices.parquet"
UNIVERSE_FILENAME = "universe.parquet"
MANIFEST_FILENAME = "manifest.json"
ATTRIBUTES_FILENAME = "attributes.parquet"
CATALOG_FILENAME = "catalog.json"
# Bumped when the files in a panel change shape, so older cached panels are not reused.
PANEL_SCHEMA_VERSION = 2
# Liquidity floor: a member's median close * volume over the trailing LIQUIDITY_WINDOW trading
# days (at least LIQUIDITY_MIN_OBSERVATIONS of them present) must reach the spec's floor. The
# median, not the mean, so that isolated bad-tick days cannot lift a shell ticker over it.
LIQUIDITY_WINDOW = 21
LIQUIDITY_MIN_OBSERVATIONS = 15
LIQUIDITY_LOOKBACK_CALENDAR_DAYS = 45
NO_ATTRIBUTE_STORE_REASON = (
    "No attribute store is built for this data snapshot. Run build-attributes."
)


class PanelSpec(BaseModel):
    start: date
    end: date
    price_source: str = "faustcalc_fmp_snapshot"
    membership_lookback_trading_days: int = 5
    min_median_dollar_volume: float = Field(default=0.0, ge=0)


class DataManifest(BaseModel):
    manifest_id: str
    spec: PanelSpec
    availability_policy_version: str
    canonical_snapshot_id: str
    price_adjustment_status: str
    source_rights_state: str
    cutoff_available_at: datetime
    series: list[str] = ["prices", "universe"]
    row_counts: dict[str, int]
    currencies: list[str]
    created_at: datetime
    panel_schema_version: int = 1
    catalog_version: str | None = None
    attribute_store_id: str | None = None
    attributes_unavailable_reason: str | None = None


class MaterializedPanel(BaseModel):
    directory: Path
    manifest: DataManifest


class MaterializationError(ValueError):
    pass


def _manifest_id(
    spec: PanelSpec,
    availability_policy_version: str,
    canonical_snapshot_id: str,
    price_adjustment_status: str,
    attribute_store_id: str | None,
) -> str:
    payload = {
        "panel_schema_version": PANEL_SCHEMA_VERSION,
        "catalog_version": CATALOG_VERSION if attribute_store_id else None,
        "attribute_store_id": attribute_store_id,
        "spec": spec.model_dump(mode="json"),
        "availability_policy_version": availability_policy_version,
        "canonical_snapshot_id": canonical_snapshot_id,
        "price_adjustment_status": price_adjustment_status,
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _assert_no_duplicate_price_rows(prices: pl.DataFrame) -> None:
    dupes = (
        prices.group_by(["security_id", "event_date"])
        .agg(pl.len().alias("n"))
        .filter(pl.col("n") > 1)
        .sort(["security_id", "event_date"])
    )
    if not dupes.is_empty():
        row = dupes.row(0, named=True)
        raise MaterializationError(
            f"Duplicate price rows for security_id={row['security_id']} "
            f"event_date={row['event_date']}"
        )


def _assert_no_duplicate_securities(securities: pl.DataFrame) -> None:
    dupes = (
        securities.group_by("security_id")
        .agg(pl.len().alias("n"))
        .filter(pl.col("n") > 1)
        .sort("security_id")
    )
    if not dupes.is_empty():
        sid = dupes["security_id"][0]
        raise MaterializationError(f"Duplicate securities rows for security_id={sid}")


def derive_membership(prices: pl.DataFrame, lookback_trading_days: int) -> pl.DataFrame:
    """Universe membership pairs under a trailing trading-day lookback.

    A security is a member on calendar index ``i`` (trading days are the
    distinct ``event_date`` values present in ``prices``) iff it has a price
    row on some calendar index ``j`` with ``i - lookback + 1 <= j <= i``.
    Equivalently each priced index ``j`` makes the security a member on
    ``j .. j + lookback - 1``, clipped to the calendar.
    """
    schema = {"event_date": pl.Date, "security_id": pl.Utf8}
    calendar = prices.select(pl.col("event_date").unique().sort()).with_row_index("i")
    n = calendar.height
    if n == 0:
        return pl.DataFrame(schema=schema)
    lookback = max(lookback_trading_days, 0)
    return (
        prices.select("security_id", "event_date")
        .join(calendar, on="event_date", how="inner")
        .select(
            "security_id",
            pl.int_ranges(
                pl.col("i"), pl.min_horizontal(pl.col("i") + lookback, pl.lit(n)), dtype=pl.UInt32
            ).alias("i"),
        )
        .explode("i")
        .drop_nulls("i")
        .unique()
        .join(calendar, on="i", how="inner")
        .select(pl.col("event_date"), pl.col("security_id").cast(pl.Utf8))
        .sort(["event_date", "security_id"])
    )


def liquid_pairs(prices: pl.DataFrame, floor: float) -> pl.DataFrame:
    """(event_date, security_id) pairs whose trailing median dollar volume reaches ``floor``.

    ``prices`` should start ``LIQUIDITY_LOOKBACK_CALENDAR_DAYS`` before the first date of
    interest. Windows count trading days (see ``trading_calendar``); days without a bar or a
    volume are not observations. Sparse dates are not trading days and yield no pairs.
    """
    schema = {"event_date": pl.Date, "security_id": pl.Utf8}
    if prices.is_empty():
        return pl.DataFrame(schema=schema)
    frame = prices.select(
        "security_id", "event_date", (pl.col("close") * pl.col("volume")).alias("dollar_volume")
    ).to_pandas()
    wide = frame.pivot(index="event_date", columns="security_id", values="dollar_volume")
    wide = wide[trading_day_mask(wide)]
    median = wide.astype("float64").rolling(
        LIQUIDITY_WINDOW, min_periods=LIQUIDITY_MIN_OBSERVATIONS
    ).median()
    passing = (median >= floor).stack()
    pairs = passing[passing].index.to_frame(index=False)
    pairs["event_date"] = pd.to_datetime(pairs["event_date"]).dt.date
    return pl.from_pandas(pairs[["event_date", "security_id"]], schema_overrides=schema)


def _load_cached(directory: Path) -> MaterializedPanel:
    manifest = DataManifest.model_validate_json((directory / MANIFEST_FILENAME).read_text())
    return MaterializedPanel(directory=directory, manifest=manifest)


def _resolve_attribute_store(
    spec: PanelSpec,
    settings: SandboxSettings,
    canonical_snapshot_id: str,
    securities: pl.DataFrame,
) -> tuple[AttributeStoreManifest | None, str | None]:
    """The attribute store usable for this panel, or the reason there is none.

    A store is used only if it was built from this exact data snapshot, catalog file and
    sector assignment, and covers the whole requested range; a partial or stale store would
    be a silent gap.
    """
    store = find_attribute_store(
        settings,
        attribute_store_id(
            CATALOG_VERSION,
            canonical_snapshot_id,
            spec.price_source,
            settings.price_adjustment_status,
            catalog_digest(),
            sector_digest(securities),
        ),
    )
    if store is None:
        return None, NO_ATTRIBUTE_STORE_REASON
    if store.start > spec.start or store.end < spec.end:
        return None, (
            f"The attribute store covers {store.start.isoformat()} to {store.end.isoformat()}, "
            "not the requested range."
        )
    return store, None


def materialize(
    source: CanonicalSource, spec: PanelSpec, settings: SandboxSettings
) -> MaterializedPanel:
    canonical_snapshot_id = source.snapshot_id(source=spec.price_source)
    securities = source.securities()
    _assert_no_duplicate_securities(securities)
    store, attributes_unavailable_reason = _resolve_attribute_store(
        spec, settings, canonical_snapshot_id, securities
    )
    store_id = store.store_id if store is not None else None
    manifest_id = _manifest_id(
        spec,
        EOD_POLICY_VERSION,
        canonical_snapshot_id,
        settings.price_adjustment_status,
        store_id,
    )
    directory = settings.data_dir / "panels" / manifest_id
    if (directory / MANIFEST_FILENAME).exists():
        return _load_cached(directory)

    floor = spec.min_median_dollar_volume
    lookback = timedelta(days=LIQUIDITY_LOOKBACK_CALENDAR_DAYS if floor > 0 else 0)
    loaded = source.price_bars(spec.start - lookback, spec.end, source=spec.price_source)
    _assert_no_duplicate_price_rows(loaded)
    prices = loaded.filter(pl.col("event_date") >= spec.start)

    # Universe currency = currency of each security's earliest event_date price row.
    currency_by_security = (
        prices.sort(["security_id", "event_date"])
        .group_by("security_id", maintain_order=True)
        .agg(pl.col("currency").first())
    )

    prices_out = prices.with_columns(
        eod_available_at(pl.col("event_date")).alias("available_at")
    ).select(
        [
            "security_id",
            "event_date",
            "available_at",
            "ingestion_time",
            "close",
            "adjusted_close",
            "volume",
            "currency",
        ]
    )

    membership = derive_membership(prices, spec.membership_lookback_trading_days)
    if floor > 0:
        membership = membership.join(
            liquid_pairs(loaded, floor), on=["event_date", "security_id"], how="inner"
        )
    universe_out = (
        membership.join(securities.drop("currency"), on="security_id", how="left")
        .join(currency_by_security, on="security_id", how="left")
        .select(
            [
                "event_date",
                "security_id",
                "ticker",
                "exchange",
                "currency",
                "sector",
                "industry",
                "classification_as_of",
            ]
        )
    )

    attributes_out = None
    row_counts = {"prices": prices_out.height, "universe": universe_out.height}
    series = ["prices", "universe"]
    if store_id is not None:
        attributes = read_attributes(settings, store_id, spec.start, spec.end)
        keys = [c for c in attributes.columns if c not in ("security_id", "event_date")]
        attributes_out = attributes.with_columns(
            eod_available_at(pl.col("event_date")).alias("available_at")
        ).select(["security_id", "event_date", "available_at", *keys])
        row_counts["attributes"] = attributes_out.height
        series.append("attributes")

    manifest = DataManifest(
        manifest_id=manifest_id,
        spec=spec,
        availability_policy_version=EOD_POLICY_VERSION,
        canonical_snapshot_id=canonical_snapshot_id,
        price_adjustment_status=settings.price_adjustment_status,
        source_rights_state=settings.source_rights_state,
        cutoff_available_at=end_of_day_utc(spec.end),
        series=series,
        row_counts=row_counts,
        panel_schema_version=PANEL_SCHEMA_VERSION,
        catalog_version=CATALOG_VERSION if store_id is not None else None,
        attribute_store_id=store_id,
        attributes_unavailable_reason=attributes_unavailable_reason,
        currencies=sorted(prices_out["currency"].unique().to_list()),
        created_at=datetime.now(timezone.utc),
    )

    # Build the panel in a unique sibling directory and rename it into place, so readers only
    # ever see a complete panel. If another run renamed its copy first, use that one.
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{manifest_id}.tmp-", dir=directory.parent))
    try:
        prices_out.write_parquet(staging / PRICES_FILENAME)
        universe_out.write_parquet(staging / UNIVERSE_FILENAME)
        if attributes_out is not None:
            attributes_out.write_parquet(staging / ATTRIBUTES_FILENAME)
            shutil.copyfile(DEFAULT_CATALOG_PATH, staging / CATALOG_FILENAME)
        (staging / MANIFEST_FILENAME).write_text(manifest.model_dump_json())
        try:
            os.replace(staging, directory)
        except OSError:
            if (directory / MANIFEST_FILENAME).exists():
                return _load_cached(directory)
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    return MaterializedPanel(directory=directory, manifest=manifest)
