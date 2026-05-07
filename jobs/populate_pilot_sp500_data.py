from __future__ import annotations

import argparse
import os
import time as time_module
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from urllib.error import HTTPError

from adapters.fmp.client import fetch_historical_prices
from adapters.fred.client import FRED_SERIES, fetch_fred_csv_observations
from adapters.french.client import fetch_daily_5_factors
from adapters.sec_edgar.client import fetch_submissions
from config.env import get_required_env, load_dotenv
from db.session import session_scope
from engine.contracts import TimeWindow
from jobs.build_proxy_factor_returns import INDUSTRY_PROXY_TICKERS, SECTOR_PROXY_TICKERS, build_proxy_factor_returns
from jobs.generate_event_features import generate_event_features_for_source
from jobs.ingest_edgar_submissions import ensure_company, find_security as find_edgar_security, upsert_filings
from jobs.ingest_fmp_prices import ensure_security, upsert_price_bars
from jobs.ingest_fred_macro import upsert_macro_series
from jobs.ingest_french_factors import upsert_factor_returns
from jobs.pilot_sp500_common import (
    DEFAULT_CONFIG,
    PILOT_DATA_VERSION_PREFIX,
    assert_pilot_database_url,
    load_pilot_universe_config,
    pilot_securities,
    refresh_pilot_universe_price_coverage,
    seed_pilot_universe,
    ticker_fetch_attempts,
)


FMP_ENV_KEYS = {
    "FMP_API_KEY",
    "FMP_BASE_URL",
    "FMP_MIN_REQUEST_INTERVAL_SECONDS",
    "FMP_RATE_LIMIT_PER_MIN",
    "FMP_TIMEOUT_SECONDS",
}


@dataclass
class PilotPopulationReport:
    universe_version: str = ""
    seeded_securities: int = 0
    price_coverage: dict[str, int] = field(default_factory=dict)
    price_failures: dict[str, str] = field(default_factory=dict)
    french_factor_rows: int = 0
    fred_rows: int = 0
    fred_failures: dict[str, str] = field(default_factory=dict)
    proxy_factor_rows: int = 0
    edgar_filings: int = 0
    event_features: int = 0
    coverage_members_refreshed: int = 0

    def render(self) -> str:
        covered = sum(1 for count in self.price_coverage.values() if count > 0)
        return (
            "pilot S&P 500 population report\n"
            f"  universe_version={self.universe_version}\n"
            f"  seeded_securities={self.seeded_securities}\n"
            f"  price_coverage={covered}/{len(self.price_coverage)} tickers\n"
            f"  french_factor_rows={self.french_factor_rows}\n"
            f"  fred_rows={self.fred_rows}\n"
            f"  proxy_factor_rows={self.proxy_factor_rows}\n"
            f"  edgar_filings={self.edgar_filings}\n"
            f"  event_features={self.event_features}\n"
            f"  coverage_members_refreshed={self.coverage_members_refreshed}\n"
            f"  top_price_failures={Counter(self.price_failures.values()).most_common(5)}\n"
            f"  fred_failures={self.fred_failures}"
        )


@dataclass
class RequestPacer:
    min_interval_env_var: str
    rate_limit_env_var: str | None = None
    default_rate_limit_per_minute: float | None = None
    default_min_interval_seconds: float | None = None
    last_started_at: float | None = None

    def wait_for_slot(self) -> None:
        interval = self.min_interval_seconds()
        if interval <= 0:
            return
        now = time_module.monotonic()
        if self.last_started_at is not None:
            wait_seconds = self.last_started_at + interval - now
            if wait_seconds > 0:
                time_module.sleep(wait_seconds)
        self.last_started_at = time_module.monotonic()

    def min_interval_seconds(self) -> float:
        explicit = os.getenv(self.min_interval_env_var)
        if explicit is not None:
            return max(0.0, float(explicit))
        if self.rate_limit_env_var and self.default_rate_limit_per_minute:
            rate_limit = float(os.getenv(self.rate_limit_env_var, str(self.default_rate_limit_per_minute)))
            if rate_limit > 0:
                return 60.0 / rate_limit
        return max(0.0, float(self.default_min_interval_seconds or 0.0))


class FmpAuthorizationError(RuntimeError):
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate the local S&P 500 pilot database with fresh vendor/public data")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--from", dest="start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--price-limit", type=int, help="Limit price pulls for a smoke run")
    parser.add_argument("--include-edgar", action="store_true")
    parser.add_argument("--edgar-limit", type=int, default=25)
    parser.add_argument("--skip-prices", action="store_true")
    parser.add_argument("--skip-factors", action="store_true")
    args = parser.parse_args()

    report = populate_pilot_sp500_data(
        config_path=Path(args.config),
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        price_limit=args.price_limit,
        include_edgar=args.include_edgar,
        edgar_limit=args.edgar_limit,
        skip_prices=args.skip_prices,
        skip_factors=args.skip_factors,
    )
    print(report.render())


def populate_pilot_sp500_data(
    *,
    config_path: Path = DEFAULT_CONFIG,
    start: date,
    end: date,
    price_limit: int | None = None,
    include_edgar: bool = False,
    edgar_limit: int = 25,
    skip_prices: bool = False,
    skip_factors: bool = False,
) -> PilotPopulationReport:
    assert_pilot_database_url()
    payload = load_pilot_universe_config(config_path)
    report = PilotPopulationReport(universe_version=str(payload["version"]))
    with session_scope() as session:
        report.seeded_securities = seed_pilot_universe(session=session, payload=payload)

    securities = pilot_securities(payload)
    if not skip_prices:
        report.price_coverage, report.price_failures = backfill_pilot_prices(
            securities=securities,
            start=start,
            end=end,
            price_limit=price_limit,
        )

    if not skip_factors:
        report.french_factor_rows = ingest_pilot_french_factors(start=start, end=end)
        report.fred_rows, report.fred_failures = ingest_pilot_fred_series(start=start, end=end)
        with session_scope() as session:
            report.proxy_factor_rows = build_proxy_factor_returns(
                session=session,
                window=TimeWindow(start=_date_to_utc_datetime(start), end=_date_to_utc_datetime(end)),
            )

    if include_edgar:
        report.edgar_filings = ingest_pilot_edgar(securities=securities, limit=edgar_limit)
        with session_scope() as session:
            report.event_features = generate_event_features_for_source(session=session)

    with session_scope() as session:
        report.coverage_members_refreshed = refresh_pilot_universe_price_coverage(
            session=session,
            universe_version=report.universe_version,
        )
    return report


def backfill_pilot_prices(
    *,
    securities,
    start: date,
    end: date,
    price_limit: int | None,
) -> tuple[dict[str, int], dict[str, str]]:
    validate_fmp_configuration()
    ingestion_time = datetime.now(timezone.utc)
    data_source = f"{PILOT_DATA_VERSION_PREFIX}_{ingestion_time.date().isoformat().replace('-', '_')}"
    coverage: dict[str, int] = {}
    failures: dict[str, str] = {}
    price_targets = [*securities, *proxy_price_targets()]
    if price_limit is not None:
        price_targets = price_targets[:price_limit]
    fmp_pacer = RequestPacer(
        min_interval_env_var="FMP_MIN_REQUEST_INTERVAL_SECONDS",
        rate_limit_env_var="FMP_RATE_LIMIT_PER_MIN",
        default_rate_limit_per_minute=300.0,
    )
    for target in price_targets:
        ticker = target.ticker if hasattr(target, "ticker") else str(target)
        try:
            bars = fetch_prices_with_aliases(
                target=target,
                start=start,
                end=end,
                ingestion_time=ingestion_time,
                pacer=fmp_pacer,
            )
            for bar in bars:
                bar.source = data_source
            with session_scope() as session:
                security = ensure_security(
                    ticker=ticker,
                    company_name=target.name if hasattr(target, "name") else ticker,
                    exchange=target.exchange if hasattr(target, "exchange") else "ETF",
                    first_seen=ingestion_time,
                    session=session,
                )
                upsert_price_bars(session=session, security_id=security.security_id, bars=bars)
            coverage[ticker] = len(bars)
        except Exception as exc:
            if is_fmp_authorization_error(exc):
                raise FmpAuthorizationError(
                    "FMP authorization failed while pulling pilot prices. "
                    "Set a valid FMP_API_KEY in this PowerShell session or in .env, "
                    "and confirm that the key has access to historical-price-eod/full."
                ) from exc
            message = str(exc).splitlines()[0]
            coverage[ticker] = 0
            failures[ticker] = message
            print(f"pilot price pull skipped {ticker}: {message}")
    return coverage, failures


def validate_fmp_configuration() -> None:
    load_fmp_dotenv_overrides()
    get_required_env("FMP_API_KEY")


def load_fmp_dotenv_overrides(path: Path = Path(".env")) -> None:
    load_dotenv(path)
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key in FMP_ENV_KEYS:
            os.environ[key] = value.strip().strip('"').strip("'")


def is_fmp_authorization_error(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in {401, 403}
    cause = exc.__cause__
    while cause is not None:
        if isinstance(cause, HTTPError):
            return cause.code in {401, 403}
        cause = cause.__cause__
    return False


def fetch_prices_with_aliases(
    *,
    target,
    start: date,
    end: date,
    ingestion_time: datetime,
    pacer: RequestPacer | None = None,
):
    last_error: Exception | None = None
    for ticker in ticker_fetch_attempts(target):
        try:
            if pacer is not None:
                pacer.wait_for_slot()
            bars = fetch_historical_prices(
                ticker=ticker,
                start=start,
                end=end,
                ingestion_time=ingestion_time,
            )
            if bars:
                return bars
            last_error = ValueError(f"empty historical price response for {ticker}")
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return []


def proxy_price_targets() -> list[str]:
    return sorted(set(SECTOR_PROXY_TICKERS.values()) | set(INDUSTRY_PROXY_TICKERS.values()))


def ingest_pilot_french_factors(*, start: date, end: date) -> int:
    ingestion_time = datetime.now(timezone.utc)
    records = fetch_daily_5_factors(
        window=TimeWindow(start=_date_to_utc_datetime(start), end=_date_to_utc_datetime(end)),
        ingestion_time=ingestion_time,
    )
    with session_scope() as session:
        upsert_factor_returns(session=session, records=records)
    return len(records)


def ingest_pilot_fred_series(*, start: date, end: date) -> tuple[int, dict[str, str]]:
    ingestion_time = datetime.now(timezone.utc)
    records = []
    failures = {}
    for series_name in FRED_SERIES:
        try:
            records.extend(
                fetch_fred_csv_observations(
                    series_name=series_name,
                    start=start,
                    end=end,
                    ingestion_time=ingestion_time,
                )
            )
        except Exception as exc:
            failures[series_name] = str(exc).splitlines()[0]
        pace("FRED_MIN_REQUEST_INTERVAL_SECONDS", default_seconds=0.55)
    with session_scope() as session:
        upsert_macro_series(session=session, records=records)
    return len(records), failures


def ingest_pilot_edgar(*, securities, limit: int) -> int:
    count = 0
    for security in securities:
        if not security.cik:
            continue
        try:
            filings = fetch_submissions(cik=security.cik)[:limit]
            if not filings:
                continue
            with session_scope() as session:
                company = ensure_company(session=session, filing=filings[0], ticker=security.ticker)
                db_security = find_edgar_security(session=session, ticker=security.ticker)
                upsert_filings(session=session, company=company, security=db_security, filings=filings)
            count += len(filings)
        except Exception as exc:
            print(f"pilot EDGAR pull skipped {security.ticker}: {str(exc).splitlines()[0]}")
        pace("EDGAR_MIN_REQUEST_INTERVAL_SECONDS", default_seconds=0.12)
    return count


def pace(env_var: str, *, default_seconds: float) -> None:
    seconds = float(os.getenv(env_var, str(default_seconds)))
    if seconds > 0:
        time_module.sleep(seconds)


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()
