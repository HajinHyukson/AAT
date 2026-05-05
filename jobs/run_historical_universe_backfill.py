from __future__ import annotations

import argparse
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable

from adapters.fred.client import FRED_SERIES, fetch_fred_csv_observations
from adapters.french.client import fetch_daily_5_factors
from adapters.sec_edgar.client import fetch_submissions
from adapters.source_policy import require_confirmed_production_source
from db import models
from db.session import session_scope
from engine.contracts import TimeWindow
from jobs.build_proxy_factor_returns import build_proxy_factor_returns
from jobs.generate_event_features import generate_event_features_for_source
from jobs.ingest_edgar_submissions import ensure_company, find_security as find_edgar_security, upsert_filings
from jobs.ingest_fred_macro import upsert_macro_series
from jobs.ingest_french_factors import upsert_factor_returns
from jobs.replay_lookahead_audit import run_replay_lookahead_audit
from jobs.run_attribution import find_security, run_attribution_for_ticker
from jobs.run_batch_attribution import build_windows, load_trading_dates
from jobs.run_mvp_proving_backfill import (
    backfill_fmp_prices,
    factor_return_coverage,
    mvp_universe_tickers,
    proving_price_tickers,
    run_alembic_upgrade,
)
from jobs.seed_mvp_mappings import seed_mappings
from jobs.seed_mvp_universe import load_config, seed_universe


DEFAULT_CONFIG = Path("config/mvp_universe.json")
VALID_CADENCES = ("daily", "weekly", "monthly")


@dataclass
class CadenceCoverage:
    expected: int = 0
    ran: int = 0
    skipped: int = 0


@dataclass
class HistoricalBackfillReport:
    backfill_run_id: str | None = None
    config_version: str = ""
    analysis_start: date | None = None
    analysis_end: date | None = None
    data_start: date | None = None
    data_end: date | None = None
    seeded_securities: int = 0
    price_coverage: dict[str, int] = field(default_factory=dict)
    factor_return_coverage: dict[str, int] = field(default_factory=dict)
    macro_series_coverage: dict[str, int] = field(default_factory=dict)
    macro_fetch_failures: dict[str, str] = field(default_factory=dict)
    edgar_filings_ingested: int = 0
    event_features_generated: int = 0
    proxy_factor_rows: int = 0
    attribution_coverage: dict[str, CadenceCoverage] = field(default_factory=dict)
    replay_audit_checked: int = 0
    skip_reasons: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        if not self.attribution_coverage:
            return False
        for coverage in self.attribution_coverage.values():
            if coverage.expected == 0:
                return False
            if coverage.ran / coverage.expected < 0.95:
                return False
        return True

    def coverage_payload(self) -> dict:
        return {
            "seeded_securities": self.seeded_securities,
            "price_coverage": self.price_coverage,
            "factor_return_coverage": self.factor_return_coverage,
            "macro_series_coverage": self.macro_series_coverage,
            "macro_fetch_failures": self.macro_fetch_failures,
            "edgar_filings_ingested": self.edgar_filings_ingested,
            "event_features_generated": self.event_features_generated,
            "proxy_factor_rows": self.proxy_factor_rows,
            "attribution_coverage": {
                cadence: {
                    "expected": coverage.expected,
                    "ran": coverage.ran,
                    "skipped": coverage.skipped,
                }
                for cadence, coverage in self.attribution_coverage.items()
            },
            "replay_audit_checked": self.replay_audit_checked,
            "top_skip_reasons": Counter(self.skip_reasons).most_common(10),
            "success": self.success,
        }

    def render(self) -> str:
        lines = [
            "Historical universe backfill coverage report",
            f"  backfill_run_id={self.backfill_run_id}",
            f"  config_version={self.config_version}",
            f"  analysis_window={self.analysis_start}->{self.analysis_end}",
            f"  data_window={self.data_start}->{self.data_end}",
            f"  seeded_securities={self.seeded_securities}",
            f"  price_coverage_tickers={len([value for value in self.price_coverage.values() if value > 0])}",
            f"  factor_families={self.factor_return_coverage}",
            f"  macro_series={self.macro_series_coverage}",
            f"  macro_fetch_failures={self.macro_fetch_failures}",
            f"  edgar_filings_ingested={self.edgar_filings_ingested}",
            f"  event_features_generated={self.event_features_generated}",
            f"  proxy_factor_rows={self.proxy_factor_rows}",
            f"  replay_audit_checked={self.replay_audit_checked}",
            f"  success={self.success}",
        ]
        for cadence, coverage in self.attribution_coverage.items():
            lines.append(
                f"  {cadence}: expected={coverage.expected} ran={coverage.ran} skipped={coverage.skipped}"
            )
        if self.skip_reasons:
            lines.append(f"  top_skip_reasons={Counter(self.skip_reasons).most_common(10)}")
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate the universe with historical data and expanded attribution")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--to", dest="end", default=date.today().isoformat())
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--cadences", nargs="+", choices=VALID_CADENCES, default=list(VALID_CADENCES))
    parser.add_argument("--lookback-days", type=int, default=252)
    parser.add_argument("--edgar-limit", type=int, default=200)
    parser.add_argument("--prefer-compose-port", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-alembic", action="store_true")
    args = parser.parse_args()

    report = run_historical_universe_backfill(
        config_path=Path(args.config),
        end=date.fromisoformat(args.end),
        years=args.years,
        cadences=tuple(args.cadences),
        lookback_days=args.lookback_days,
        edgar_limit=args.edgar_limit,
        prefer_compose_port=args.prefer_compose_port,
        dry_run=args.dry_run,
        skip_alembic=args.skip_alembic,
    )
    print(report.render())
    if not report.success and not args.dry_run:
        raise SystemExit(1)


def run_historical_universe_backfill(
    *,
    config_path: Path,
    end: date,
    years: int = 3,
    cadences: tuple[str, ...] = VALID_CADENCES,
    lookback_days: int = 252,
    edgar_limit: int = 200,
    prefer_compose_port: bool = False,
    dry_run: bool = False,
    skip_alembic: bool = False,
    step_runner: Callable[[str], None] | None = None,
) -> HistoricalBackfillReport:
    payload = load_config(config_path)
    analysis_start = subtract_years(end=end, years=years)
    data_start = analysis_start - timedelta(days=lookback_days * 2)
    report = HistoricalBackfillReport(
        config_version=str(payload.get("version", "")),
        analysis_start=analysis_start,
        analysis_end=end,
        data_start=data_start,
        data_end=end,
        attribution_coverage={cadence: CadenceCoverage() for cadence in cadences},
    )

    def mark(name: str) -> None:
        report.steps.append(name)
        if step_runner:
            step_runner(name)

    if dry_run:
        for name in [
            "alembic_upgrade",
            "create_backfill_run",
            "seed_universe",
            "seed_mappings",
            "backfill_prices",
            "ingest_french",
            "ingest_fred",
            "build_proxy_returns",
            "ingest_edgar",
            "generate_event_features",
            "run_historical_attribution",
            "replay_audit",
            "complete_backfill_run",
        ]:
            mark(name)
        report.seeded_securities = len(mvp_universe_tickers(payload))
        return report

    if not skip_alembic:
        run_alembic_upgrade()
        mark("alembic_upgrade")

    backfill_run_id = create_backfill_run(
        config_version=report.config_version,
        analysis_start=analysis_start,
        analysis_end=end,
        data_start=data_start,
        data_end=end,
        cadences=cadences,
        lookback_days=lookback_days,
        prefer_compose_port=prefer_compose_port,
    )
    report.backfill_run_id = str(backfill_run_id)
    mark("create_backfill_run")

    try:
        run_historical_backfill_steps(
            report=report,
            payload=payload,
            analysis_start=analysis_start,
            end=end,
            data_start=data_start,
            cadences=cadences,
            lookback_days=lookback_days,
            edgar_limit=edgar_limit,
            prefer_compose_port=prefer_compose_port,
            mark=mark,
        )
    except Exception as exc:
        finish_backfill_run(
            backfill_run_id=backfill_run_id,
            status="failed",
            coverage_payload=report.coverage_payload(),
            error_payload={"error": str(exc)},
            prefer_compose_port=prefer_compose_port,
        )
        raise

    finish_backfill_run(
        backfill_run_id=backfill_run_id,
        status="completed" if report.success else "failed",
        coverage_payload=report.coverage_payload(),
        error_payload=None if report.success else {"error": "coverage_threshold_not_met"},
        prefer_compose_port=prefer_compose_port,
    )
    mark("complete_backfill_run")
    return report


def run_historical_backfill_steps(
    *,
    report: HistoricalBackfillReport,
    payload: dict,
    analysis_start: date,
    end: date,
    data_start: date,
    cadences: tuple[str, ...],
    lookback_days: int,
    edgar_limit: int,
    prefer_compose_port: bool,
    mark: Callable[[str], None],
) -> None:
    require_confirmed_production_source(
        source_name="FMP price data",
        env_var="FMP_PRODUCTION_LICENSE_CONFIRMED",
    )
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        report.seeded_securities = seed_universe(session=session, payload=payload)
        seed_mappings(session=session, payload=payload)
    mark("seed_universe")
    mark("seed_mappings")

    report.price_coverage = backfill_fmp_prices(
        tickers=proving_price_tickers(payload),
        start=data_start,
        end=end,
        prefer_compose_port=prefer_compose_port,
    )
    mark("backfill_prices")

    ingestion_time = datetime.now(timezone.utc)
    french_records = fetch_daily_5_factors(
        window=TimeWindow(start=_date_to_utc_datetime(data_start), end=_date_to_utc_datetime(end)),
        ingestion_time=ingestion_time,
    )
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        upsert_factor_returns(session=session, records=french_records)
    mark("ingest_french")

    fred_records = []
    for series_name in FRED_SERIES:
        try:
            fred_records.extend(
                fetch_fred_csv_observations(
                    series_name=series_name,
                    start=data_start,
                    end=end,
                    ingestion_time=ingestion_time,
                )
            )
        except Exception as exc:
            report.macro_fetch_failures[series_name] = str(exc)
            print(f"FRED macro fetch skipped {series_name}: {exc}")
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        upsert_macro_series(session=session, records=fred_records)
    mark("ingest_fred")

    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        report.proxy_factor_rows = build_proxy_factor_returns(
            session=session,
            window=TimeWindow(start=_date_to_utc_datetime(data_start), end=_date_to_utc_datetime(end)),
        )
        report.factor_return_coverage = factor_return_coverage(session=session, start=data_start, end=end)
        report.macro_series_coverage = macro_series_coverage(session=session, start=data_start, end=end)
    mark("build_proxy_returns")

    report.edgar_filings_ingested = ingest_recent_edgar_for_universe(
        payload=payload,
        limit=edgar_limit,
        prefer_compose_port=prefer_compose_port,
    )
    mark("ingest_edgar")

    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        report.event_features_generated = generate_event_features_for_source(session=session)
    mark("generate_event_features")

    run_historical_attributions(
        report=report,
        tickers=mvp_universe_tickers(payload),
        analysis_start=analysis_start,
        end=end,
        cadences=cadences,
        lookback_days=lookback_days,
        prefer_compose_port=prefer_compose_port,
    )
    mark("run_historical_attribution")

    report.replay_audit_checked = run_replay_lookahead_audit(prefer_compose_port=prefer_compose_port)
    mark("replay_audit")


def run_historical_attributions(
    *,
    report: HistoricalBackfillReport,
    tickers: list[str],
    analysis_start: date,
    end: date,
    cadences: tuple[str, ...],
    lookback_days: int,
    prefer_compose_port: bool,
) -> None:
    cutoff = datetime.now(timezone.utc)
    analysis_start_datetime = _date_to_utc_datetime(analysis_start)
    end_datetime = _date_to_utc_datetime(end)
    for ticker in tickers:
        for cadence in cadences:
            try:
                with session_scope(prefer_compose_port=prefer_compose_port) as session:
                    security = find_security(session=session, ticker=ticker)
                    trading_dates = load_trading_dates(
                        session=session,
                        security_id=security.security_id,
                        start=analysis_start_datetime,
                        end=end_datetime,
                    )
                    windows = build_windows(trading_dates=trading_dates, cadence=cadence)
                    report.attribution_coverage[cadence].expected += len(windows)
                    for window in windows:
                        try:
                            run_attribution_for_ticker(
                                session=session,
                                ticker=ticker,
                                window=window,
                                attribution_cutoff=cutoff,
                                use_expanded_mvp=True,
                                include_event_evidence=True,
                                lookback_days=lookback_days,
                                cadence=cadence,
                            )
                            report.attribution_coverage[cadence].ran += 1
                        except (RuntimeError, ValueError) as exc:
                            report.attribution_coverage[cadence].skipped += 1
                            report.skip_reasons.append(f"{ticker} {cadence}: {str(exc).splitlines()[0]}")
            except (RuntimeError, ValueError) as exc:
                report.attribution_coverage[cadence].skipped += 1
                report.skip_reasons.append(f"{ticker} {cadence}: {str(exc).splitlines()[0]}")


def ingest_recent_edgar_for_universe(*, payload: dict, limit: int, prefer_compose_port: bool) -> int:
    if limit <= 0:
        return 0
    count = 0
    for item in payload["securities"]:
        cik = item.get("cik")
        ticker = item.get("ticker")
        if not cik or not ticker:
            continue
        try:
            filings = fetch_submissions(cik=cik)[:limit]
            if not filings:
                continue
            with session_scope(prefer_compose_port=prefer_compose_port) as session:
                company = ensure_company(session=session, filing=filings[0], ticker=ticker)
                security = find_edgar_security(session=session, ticker=ticker)
                upsert_filings(session=session, company=company, security=security, filings=filings)
            count += len(filings)
        except Exception as exc:
            print(f"EDGAR ingest skipped {ticker}: {exc}")
    return count


def create_backfill_run(
    *,
    config_version: str,
    analysis_start: date,
    analysis_end: date,
    data_start: date,
    data_end: date,
    cadences: tuple[str, ...],
    lookback_days: int,
    prefer_compose_port: bool,
) -> uuid.UUID:
    backfill_run_id = uuid.uuid4()
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        session.add(
            models.BackfillRun(
                backfill_run_id=backfill_run_id,
                config_version=config_version,
                analysis_start=_date_to_utc_datetime(analysis_start),
                analysis_end=_date_to_utc_datetime(analysis_end),
                data_start=_date_to_utc_datetime(data_start),
                data_end=_date_to_utc_datetime(data_end),
                cadences=list(cadences),
                lookback_days=lookback_days,
                status="running",
                started_at=datetime.now(timezone.utc),
                finished_at=None,
                coverage_payload={},
                error_payload=None,
            )
        )
    return backfill_run_id


def finish_backfill_run(
    *,
    backfill_run_id: uuid.UUID,
    status: str,
    coverage_payload: dict,
    error_payload: dict | None,
    prefer_compose_port: bool,
) -> None:
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        run = session.get(models.BackfillRun, backfill_run_id)
        if run is None:
            return
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.coverage_payload = coverage_payload
        run.error_payload = error_payload


def macro_series_coverage(*, session, start: date, end: date) -> dict[str, int]:
    rows = session.query(models.MacroSeries.series_name, models.MacroSeries.macro_series_id).filter(
        models.MacroSeries.event_time >= _date_to_utc_datetime(start),
        models.MacroSeries.event_time <= _date_to_utc_datetime(end),
    ).all()
    counter: Counter[str] = Counter()
    for series_name, _ in rows:
        counter[str(series_name)] += 1
    return dict(counter)


def subtract_years(*, end: date, years: int) -> date:
    try:
        return end.replace(year=end.year - years)
    except ValueError:
        return end.replace(year=end.year - years, day=28)


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()
