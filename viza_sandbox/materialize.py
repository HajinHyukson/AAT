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
from datetime import date, datetime, timezone
from pathlib import Path

import polars as pl
from pydantic import BaseModel

from viza_sandbox.canonical import CanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.pit import EOD_POLICY_VERSION, eod_available_at, end_of_day_utc

PRICES_FILENAME = "prices.parquet"
UNIVERSE_FILENAME = "universe.parquet"
MANIFEST_FILENAME = "manifest.json"


class PanelSpec(BaseModel):
    start: date
    end: date
    price_source: str = "faustcalc_fmp_snapshot"
    membership_lookback_trading_days: int = 5


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
) -> str:
    payload = {
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


def _load_cached(directory: Path) -> MaterializedPanel:
    manifest = DataManifest.model_validate_json((directory / MANIFEST_FILENAME).read_text())
    return MaterializedPanel(directory=directory, manifest=manifest)


def materialize(
    source: CanonicalSource, spec: PanelSpec, settings: SandboxSettings
) -> MaterializedPanel:
    canonical_snapshot_id = source.snapshot_id(source=spec.price_source)
    manifest_id = _manifest_id(
        spec, EOD_POLICY_VERSION, canonical_snapshot_id, settings.price_adjustment_status
    )
    directory = settings.data_dir / "panels" / manifest_id
    if (directory / MANIFEST_FILENAME).exists():
        return _load_cached(directory)

    prices = source.price_bars(spec.start, spec.end, source=spec.price_source)
    _assert_no_duplicate_price_rows(prices)

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

    securities = source.securities()
    _assert_no_duplicate_securities(securities)
    membership = derive_membership(prices, spec.membership_lookback_trading_days)
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

    manifest = DataManifest(
        manifest_id=manifest_id,
        spec=spec,
        availability_policy_version=EOD_POLICY_VERSION,
        canonical_snapshot_id=canonical_snapshot_id,
        price_adjustment_status=settings.price_adjustment_status,
        source_rights_state=settings.source_rights_state,
        cutoff_available_at=end_of_day_utc(spec.end),
        row_counts={"prices": prices_out.height, "universe": universe_out.height},
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
