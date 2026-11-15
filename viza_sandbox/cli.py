"""Operator CLI for the VIZA quant sandbox: ``python -m viza_sandbox.cli <command>``."""

from __future__ import annotations

import argparse
import sys
from datetime import date

import polars as pl
from sqlalchemy.engine import make_url

from viza_sandbox.canonical import PostgresCanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.store import SandboxStore


def split_adjustment_verdict(bars: pl.DataFrame, threshold: float = 3.0) -> str:
    """``unadjusted`` if any consecutive close ratio is >= threshold or <= 1/threshold."""
    closes = bars.sort("event_date")["close"].to_list()
    for prev, cur in zip(closes, closes[1:]):
        if prev <= 0 or cur <= 0:
            continue
        ratio = cur / prev
        if ratio >= threshold or ratio <= 1 / threshold:
            return "unadjusted"
    return "no_split_signature"


def _init_db(args: argparse.Namespace) -> int:
    url = SandboxSettings().database_url
    SandboxStore(url).create_schema()
    print(f"schema ready: {make_url(url).render_as_string(hide_password=True)}")
    return 0


def _create_user(args: argparse.Namespace) -> int:
    store = SandboxStore(SandboxSettings().database_url)
    user, token = store.create_user(args.name, is_owner=args.owner)
    print(f"user_id={user.user_id}\ntoken={token}")
    return 0


def _check_split_adjustment(args: argparse.Namespace) -> int:
    settings = SandboxSettings()
    if not settings.canonical_database_url:
        print("VIZA_SANDBOX_CANONICAL_DATABASE_URL is required", file=sys.stderr)
        return 2
    source = PostgresCanonicalSource(settings.canonical_database_url)
    ticker = args.ticker.upper()
    securities = source.securities().filter(pl.col("ticker") == ticker)
    if securities.is_empty():
        print(f"ticker not found: {ticker}", file=sys.stderr)
        return 1
    security_id = securities["security_id"][0]
    kwargs = {"source": args.source} if args.source else {}
    bars = source.price_bars(
        date.fromisoformat(args.date_from), date.fromisoformat(args.date_to), **kwargs
    ).filter(pl.col("security_id") == security_id)
    bars = bars.sort("event_date")
    if bars.height < 2:
        print(
            f"cannot give a verdict for {ticker} from {args.date_from} to {args.date_to}: "
            f"{bars.height} bar(s) found, need at least 2",
            file=sys.stderr,
        )
        return 1
    for row in bars.iter_rows(named=True):
        print(f"{row['event_date']} {row['close']} {row['adjusted_close']}")
    print(f"verdict={split_adjustment_verdict(bars)}")
    return 0


def _build_attributes(args: argparse.Namespace) -> int:
    from viza_sandbox.attribute_store import build_attribute_store

    settings = SandboxSettings()
    if not settings.canonical_database_url:
        print("VIZA_SANDBOX_CANONICAL_DATABASE_URL is required", file=sys.stderr)
        return 2
    source = PostgresCanonicalSource(settings.canonical_database_url)
    kwargs = {"price_source": args.source} if args.source else {}
    manifest = build_attribute_store(
        source,
        settings,
        start=date.fromisoformat(args.date_from),
        end=date.fromisoformat(args.date_to),
        **kwargs,
    )
    print(f"store_id={manifest.store_id}")
    for year, rows in sorted(manifest.row_counts.items()):
        print(f"{year} rows={rows}")
    for day, bars in sorted(manifest.excluded_dates.items()):
        print(f"excluded non-trading date {day} bars={bars}")
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from viza_sandbox.api import build_default_app

    uvicorn.run(build_default_app(), host=args.host, port=args.port)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="viza_sandbox.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db").set_defaults(func=_init_db)
    create = sub.add_parser("create-user")
    create.add_argument("--name", required=True)
    create.add_argument("--owner", action="store_true")
    create.set_defaults(func=_create_user)
    split = sub.add_parser("check-split-adjustment")
    split.add_argument("--ticker", required=True)
    split.add_argument("--from", dest="date_from", required=True)
    split.add_argument("--to", dest="date_to", required=True)
    split.add_argument("--source")
    split.set_defaults(func=_check_split_adjustment)
    build = sub.add_parser("build-attributes")
    build.add_argument("--from", dest="date_from", required=True)
    build.add_argument("--to", dest="date_to", required=True)
    build.add_argument("--source")
    build.set_defaults(func=_build_attributes)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8781)
    serve.set_defaults(func=_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
