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


def derive_membership(prices: pl.DataFrame, lookback_trading_days: int) -> pl.DataFrame:
    """Universe membership pairs under a trailing trading-day lookback.

    A security is a member on calendar index ``i`` (trading days are the
    distinct ``event_date`` values present in ``prices``) iff it has a price
    row on some calendar index ``j`` with ``i - lookback + 1 <= j <= i``.
    """
    schema = {"event_date": pl.Date, "security_id": pl.Utf8}
    calendar = sorted(prices["event_date"].unique().to_list())
    n = len(calendar)
    if n == 0:
        return pl.DataFrame(schema=schema)
    index_of = {d: i for i, d in enumerate(calendar)}

    priced_by_security: dict[str, list[bool]] = {}
    for sid, event_date in zip(
        prices["security_id"].to_list(), prices["event_date"].to_list(), strict=True
    ):
        priced_by_security.setdefault(sid, [False] * n)[index_of[event_date]] = True

    rows: list[tuple[date, str]] = []
    for sid in sorted(priced_by_security):
        priced = priced_by_security[sid]
        window_count = 0
        for i in range(n):
            if priced[i]:
                window_count += 1
            drop_idx = i - lookback_trading_days
            if drop_idx >= 0 and priced[drop_idx]:
                window_count -= 1
            if window_count > 0:
                rows.append((calendar[i], sid))

    out = pl.DataFrame(rows, schema=schema, orient="row") if rows else pl.DataFrame(schema=schema)
    return out.sort(["event_date", "security_id"])


def materialize(
    source: CanonicalSource, spec: PanelSpec, settings: SandboxSettings
) -> MaterializedPanel:
    canonical_snapshot_id = source.snapshot_id(source=spec.price_source)
    manifest_id = _manifest_id(
        spec, EOD_POLICY_VERSION, canonical_snapshot_id, settings.price_adjustment_status
    )
    directory = settings.data_dir / "panels" / manifest_id
    manifest_path = directory / MANIFEST_FILENAME
    if manifest_path.exists():
        manifest = DataManifest.model_validate_json(manifest_path.read_text())
        return MaterializedPanel(directory=directory, manifest=manifest)

    prices = source.price_bars(spec.start, spec.end, source=spec.price_source)
    _assert_no_duplicate_price_rows(prices)

    currency_by_security = prices.group_by("security_id", maintain_order=True).agg(
        pl.col("currency").first()
    )

    prices_out = prices.with_columns(
        eod_available_at(pl.col("event_date")).alias("available_at")
    ).select(
        [
            "security_id",
            "event_date",
            "available_at",
            "close",
            "adjusted_close",
            "volume",
            "currency",
        ]
    )

    membership = derive_membership(prices, spec.membership_lookback_trading_days)
    universe_out = (
        membership.join(source.securities(), on="security_id", how="left")
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

    directory.mkdir(parents=True, exist_ok=True)
    prices_out.write_parquet(directory / PRICES_FILENAME)
    universe_out.write_parquet(directory / UNIVERSE_FILENAME)

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
    manifest_path.write_text(manifest.model_dump_json())

    return MaterializedPanel(directory=directory, manifest=manifest)
