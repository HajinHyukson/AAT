from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from adapters.fmp.client import fetch_historical_prices
from adapters.fred.client import FRED_SERIES, fetch_fred_csv_observations
from adapters.french.client import fetch_daily_5_factors
from db import models
from db.session import session_scope
from engine.contracts import TimeWindow
from jobs.build_proxy_factor_returns import (
    INDUSTRY_PROXY_TICKERS,
    SECTOR_PROXY_TICKERS,
    build_proxy_factor_returns,
)
from jobs.generate_event_features import generate_event_features_for_source
from jobs.ingest_fmp_prices import ensure_security, upsert_price_bars
from jobs.ingest_fred_macro import upsert_macro_series
from jobs.ingest_french_factors import upsert_factor_returns
from jobs.replay_lookahead_audit import run_replay_lookahead_audit
from jobs.run_attribution import run_attribution_for_ticker
from jobs.run_batch_attribution import load_trading_dates
from jobs.seed_mvp_mappings import seed_mappings
from jobs.seed_mvp_universe import load_config, seed_universe


DEFAULT_CONFIG = Path("config/mvp_universe.json")
SUCCESS_THRESHOLD = 10
FMP_SYMBOL_ALIASES = {
    "BRK.B": ("BRK-B", "BRK/B"),
}


@dataclass
class StepResult:
    name: str
    status: str = "ok"
    count: int = 0
    message: str = ""


@dataclass
class CoverageReport:
    seeded_securities: int = 0
    price_coverage: dict[str, int] = field(default_factory=dict)
    factor_return_coverage: dict[str, int] = field(default_factory=dict)
    macro_series_coverage: dict[str, int] = field(default_factory=dict)
    macro_fetch_failures: dict[str, str] = field(default_factory=dict)
    usable_peer_baskets: int = 0
    attribution_ran: int = 0
    attribution_skipped: int = 0
    skip_reasons: list[str] = field(default_factory=list)
    example_ticker: str | None = None
    example_run_id: str | None = None
    dashboard_url: str = "http://127.0.0.1:3000"
    steps: list[StepResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.attribution_ran >= SUCCESS_THRESHOLD

    def top_skip_reasons(self, limit: int = 5) -> list[tuple[str, int]]:
        return Counter(self.skip_reasons).most_common(limit)

    def render(self) -> str:
        lines = [
            "MVP proving run coverage report",
            f"  seeded_securities={self.seeded_securities}",
            f"  price_coverage_tickers={len([v for v in self.price_coverage.values() if v > 0])}",
            f"  factor_families={self.factor_return_coverage}",
            f"  macro_series={self.macro_series_coverage}",
            f"  macro_fetch_failures={self.macro_fetch_failures}",
            f"  usable_peer_baskets={self.usable_peer_baskets}",
            f"  attribution_ran={self.attribution_ran}",
            f"  attribution_skipped={self.attribution_skipped}",
            f"  success={self.success}",
        ]
        if self.example_ticker:
            lines.append(f"  example={self.dashboard_url}?ticker={self.example_ticker}")
        if self.example_run_id:
            lines.append(f"  example_run_id={self.example_run_id}")
        if self.skip_reasons:
            lines.append(f"  top_skip_reasons={self.top_skip_reasons()}")
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MVP trailing-1-year proving backfill")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--to", dest="end", default=date.today().isoformat())
    parser.add_argument("--lookback-days", type=int, default=252)
    parser.add_argument("--min-success", type=int, default=SUCCESS_THRESHOLD)
    parser.add_argument("--prefer-compose-port", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-alembic", action="store_true")
    args = parser.parse_args()

    end = date.fromisoformat(args.end)
    start = default_backfill_start(end=end, lookback_days=args.lookback_days)
    report = run_proving_backfill(
        config_path=Path(args.config),
        start=start,
        end=end,
        lookback_days=args.lookback_days,
        min_success=args.min_success,
        prefer_compose_port=args.prefer_compose_port,
        dry_run=args.dry_run,
        skip_alembic=args.skip_alembic,
    )
    print(report.render())
    if not report.success and not args.dry_run:
        raise SystemExit(1)


def run_proving_backfill(
    *,
    config_path: Path,
    start: date,
    end: date,
    lookback_days: int,
    min_success: int = SUCCESS_THRESHOLD,
    prefer_compose_port: bool = False,
    dry_run: bool = False,
    skip_alembic: bool = False,
    step_runner: Callable[[str], None] | None = None,
) -> CoverageReport:
    global SUCCESS_THRESHOLD
    old_threshold = SUCCESS_THRESHOLD
    SUCCESS_THRESHOLD = min_success
    try:
        payload = load_config(config_path)
        mvp_tickers = mvp_universe_tickers(payload)
        all_price_tickers = proving_price_tickers(payload)
        report = CoverageReport()

        def mark(name: str, count: int = 0, message: str = "") -> None:
            report.steps.append(StepResult(name=name, count=count, message=message))
            if step_runner:
                step_runner(name)

        if dry_run:
            for name in [
                "alembic_upgrade",
                "seed_universe",
                "seed_mappings",
                "backfill_prices",
                "ingest_french",
                "ingest_fred",
                "build_proxy_returns",
                "generate_event_features",
                "run_expanded_attribution",
                "replay_audit",
            ]:
                mark(name)
            report.seeded_securities = len(mvp_tickers)
            return report

        if not skip_alembic:
            run_alembic_upgrade()
            mark("alembic_upgrade")

        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            report.seeded_securities = seed_universe(session=session, payload=payload)
            classifications, baskets, exposures = seed_mappings(session=session, payload=payload)
            mark("seed_universe", report.seeded_securities)
            mark("seed_mappings", classifications + baskets + exposures)

        report.price_coverage = backfill_fmp_prices(
            tickers=all_price_tickers,
            start=start,
            end=end,
            prefer_compose_port=prefer_compose_port,
        )
        mark("backfill_prices", sum(report.price_coverage.values()))

        ingestion_time = datetime.now(timezone.utc)
        french_records = fetch_daily_5_factors(
            window=TimeWindow(start=_date_to_utc_datetime(start), end=_date_to_utc_datetime(end)),
            ingestion_time=ingestion_time,
        )
        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            upsert_factor_returns(session=session, records=french_records)
        mark("ingest_french", len(french_records))

        fred_records = []
        for series_name in FRED_SERIES:
            try:
                fred_records.extend(
                    fetch_fred_csv_observations(
                        series_name=series_name,
                        start=start,
                        end=end,
                        ingestion_time=ingestion_time,
                    )
                )
            except Exception as exc:
                report.macro_fetch_failures[series_name] = str(exc)
                print(f"FRED macro fetch skipped {series_name}: {exc}")
        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            upsert_macro_series(session=session, records=fred_records)
        mark("ingest_fred", len(fred_records))

        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            proxy_rows = build_proxy_factor_returns(
                session=session,
                window=TimeWindow(start=_date_to_utc_datetime(start), end=_date_to_utc_datetime(end)),
            )
            report.factor_return_coverage = factor_return_coverage(session=session, start=start, end=end)
            report.macro_series_coverage = macro_series_coverage(session=session, start=start, end=end)
            report.usable_peer_baskets = usable_peer_basket_count(session=session)
        mark("build_proxy_returns", proxy_rows)

        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            generated = generate_event_features_for_source(session=session)
        mark("generate_event_features", generated)

        report = run_latest_expanded_attributions(
            report=report,
            tickers=mvp_tickers,
            run_end=end,
            lookback_days=lookback_days,
            prefer_compose_port=prefer_compose_port,
        )
        mark("run_expanded_attribution", report.attribution_ran)

        checked = run_replay_lookahead_audit(prefer_compose_port=prefer_compose_port)
        mark("replay_audit", checked)
        return report
    finally:
        SUCCESS_THRESHOLD = old_threshold


def proving_price_tickers(payload: dict) -> list[str]:
    return sorted(set(mvp_universe_tickers(payload)) | proxy_tickers())


def mvp_universe_tickers(payload: dict) -> list[str]:
    return [item["ticker"].upper() for item in payload["securities"]]


def proxy_tickers() -> set[str]:
    return set(SECTOR_PROXY_TICKERS.values()) | set(INDUSTRY_PROXY_TICKERS.values())


def default_backfill_start(*, end: date, lookback_days: int) -> date:
    return end - timedelta(days=365 + lookback_days * 2)


def run_alembic_upgrade() -> None:
    script = Path("scripts/run_alembic.ps1")
    if sys.platform.startswith("win"):
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "upgrade", "head"], check=True)
    else:
        subprocess.run(["alembic", "upgrade", "head"], check=True)


def backfill_fmp_prices(
    *,
    tickers: list[str],
    start: date,
    end: date,
    prefer_compose_port: bool,
) -> dict[str, int]:
    coverage = {}
    ingestion_time = datetime.now(timezone.utc)
    for ticker in tickers:
        try:
            bars = fetch_prices_with_aliases(
                ticker=ticker,
                start=start,
                end=end,
                ingestion_time=ingestion_time,
            )
            with session_scope(prefer_compose_port=prefer_compose_port) as session:
                security = ensure_security(
                    ticker=ticker,
                    company_name=ticker,
                    exchange="UNKNOWN",
                    first_seen=ingestion_time,
                    session=session,
                )
                upsert_price_bars(session=session, security_id=security.security_id, bars=bars)
            coverage[ticker] = len(bars)
        except Exception as exc:
            coverage[ticker] = 0
            print(f"price backfill skipped {ticker}: {exc}")
    return coverage


def fetch_prices_with_aliases(*, ticker: str, start: date, end: date, ingestion_time: datetime):
    attempts = (ticker, *FMP_SYMBOL_ALIASES.get(ticker, ()))
    last_error: Exception | None = None
    for fetch_ticker in attempts:
        try:
            return fetch_historical_prices(
                ticker=fetch_ticker,
                start=start,
                end=end,
                ingestion_time=ingestion_time,
            )
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return []


def run_latest_expanded_attributions(
    *,
    report: CoverageReport,
    tickers: list[str],
    run_end: date,
    lookback_days: int,
    prefer_compose_port: bool,
) -> CoverageReport:
    cutoff = datetime.now(timezone.utc)
    run_end_datetime = _date_to_utc_datetime(run_end)
    for ticker in tickers:
        try:
            with session_scope(prefer_compose_port=prefer_compose_port) as session:
                security = _find_security(session=session, ticker=ticker)
                if security is None:
                    raise ValueError("missing_active_security")
                dates = load_trading_dates(
                    session=session,
                    security_id=security.security_id,
                    start=run_end_datetime - timedelta(days=10),
                    end=run_end_datetime,
                )
                if len(dates) < 2:
                    dates = load_trading_dates(
                        session=session,
                        security_id=security.security_id,
                        start=run_end_datetime - timedelta(days=30),
                        end=run_end_datetime,
                    )
                if len(dates) < 2:
                    raise ValueError("missing_recent_trading_dates")
                result = run_attribution_for_ticker(
                    session=session,
                    ticker=ticker,
                    window=TimeWindow(start=dates[-2], end=dates[-1]),
                    attribution_cutoff=cutoff,
                    use_expanded_mvp=True,
                    include_event_evidence=True,
                    lookback_days=lookback_days,
                )
                report.attribution_ran += 1
                if report.example_ticker is None:
                    report.example_ticker = ticker
                    run = session.query(models.AttributionRun).filter_by(
                        security_id=result.security_id,
                        window_start=result.window.start,
                        window_end=result.window.end,
                        model_version=result.model_version,
                    ).order_by(models.AttributionRun.created_at.desc()).first()
                    report.example_run_id = str(run.attribution_run_id) if run else None
        except Exception as exc:
            report.attribution_skipped += 1
            report.skip_reasons.append(str(exc).splitlines()[0])
    return report


def factor_return_coverage(*, session, start: date, end: date) -> dict[str, int]:
    rows = session.query(models.FactorReturn.factor_family, models.FactorReturn.factor_return_id).filter(
        models.FactorReturn.event_time >= _date_to_utc_datetime(start),
        models.FactorReturn.event_time <= _date_to_utc_datetime(end),
    ).all()
    counter: Counter[str] = Counter()
    for family, _ in rows:
        counter[str(family)] += 1
    return dict(counter)


def macro_series_coverage(*, session, start: date, end: date) -> dict[str, int]:
    rows = session.query(models.MacroSeries.series_name, models.MacroSeries.macro_series_id).filter(
        models.MacroSeries.event_time >= _date_to_utc_datetime(start),
        models.MacroSeries.event_time <= _date_to_utc_datetime(end),
    ).all()
    counter: Counter[str] = Counter()
    for series_name, _ in rows:
        counter[str(series_name)] += 1
    return dict(counter)


def usable_peer_basket_count(*, session) -> int:
    count = 0
    baskets = session.query(models.PeerBasket).all()
    for basket in baskets:
        members = session.query(models.PeerBasketMember).filter_by(peer_basket_id=basket.peer_basket_id).count()
        if members >= 3:
            count += 1
    return count


def _find_security(*, session, ticker: str):
    return session.query(models.Security).join(
        models.SecurityTickerHistory,
        models.Security.security_id == models.SecurityTickerHistory.security_id,
    ).filter(
        models.SecurityTickerHistory.ticker == ticker,
        models.SecurityTickerHistory.active_to.is_(None),
    ).order_by(models.SecurityTickerHistory.active_from.desc()).first()


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)


if __name__ == "__main__":
    main()
