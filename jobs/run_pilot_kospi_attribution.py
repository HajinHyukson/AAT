"""Windowed attribution runner for the local KOSPI pilot.

Phase 1 runs market-factor attribution against the ``kospi_market`` proxy
factor (built from the staged KOSPI index) plus evidence-only investor-flow
inputs. Residuals are expected to be larger than US names — sector, peer,
style, and macro layers are not available until Phase 2 metadata enrichment.

Skips already-completed windows by default, mirroring the S&P 500 pilot.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from db import models
from db.session import session_scope
from jobs.acquin_flow_evidence import build_flow_evidence_inputs
from jobs.pilot_kospi_common import (
    DEFAULT_KOSPI_CONFIG,
    KOSPI_MARKET_FACTOR_NAME,
    assert_pilot_kospi_database_url,
    ensure_pilot_kospi_database_url,
    load_kospi_universe_config,
    normalize_kospi_ticker,
)
from jobs.run_attribution import (
    METHODOLOGY_LEGACY,
    METHODOLOGY_RESIDUAL_SAFETY,
    RESIDUAL_SAFETY_MODEL_VERSION,
    find_security,
    market_factor_basket_version,
    run_attribution_for_ticker,
)
from jobs.run_batch_attribution import build_windows, load_trading_dates


VALID_CADENCES = ("daily", "weekly", "monthly")
VALID_KOSPI_METHODOLOGIES = (METHODOLOGY_LEGACY, METHODOLOGY_RESIDUAL_SAFETY)


@dataclass
class PilotKospiAttributionReport:
    methodology: str
    tickers: int = 0
    expected_windows: int = 0
    already_completed_windows: int = 0
    ran_windows: int = 0
    skipped_windows: int = 0
    skip_reasons: list[str] = field(default_factory=list)

    def render(self) -> str:
        return (
            "pilot KOSPI attribution report\n"
            f"  methodology={self.methodology}\n"
            f"  tickers={self.tickers}\n"
            f"  expected_windows={self.expected_windows}\n"
            f"  already_completed_windows={self.already_completed_windows}\n"
            f"  ran_windows={self.ran_windows}\n"
            f"  skipped_windows={self.skipped_windows}\n"
            f"  top_skip_reasons={top_counts(self.skip_reasons)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run KOSPI pilot attribution on the local pilot DB")
    parser.add_argument("--config", default=str(DEFAULT_KOSPI_CONFIG))
    parser.add_argument("--tickers", nargs="*", help="Optional ticker subset; defaults to the full pilot universe")
    parser.add_argument("--from", dest="start", required=True, help="Analysis start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", default=date.today().isoformat(), help="Analysis end date YYYY-MM-DD")
    parser.add_argument("--cadences", nargs="+", choices=VALID_CADENCES, default=["daily"])
    parser.add_argument("--lookback-days", type=int, default=252)
    parser.add_argument("--methodology", choices=VALID_KOSPI_METHODOLOGIES, default=METHODOLOGY_RESIDUAL_SAFETY)
    parser.add_argument("--skip-flow-evidence", action="store_true")
    parser.add_argument("--window-limit", type=int, help="Per-ticker/cadence window cap for smoke runs")
    parser.add_argument("--rerun-existing", action="store_true", help="Recompute windows that already have runs")
    args = parser.parse_args()

    ensure_pilot_kospi_database_url()
    report = run_pilot_kospi_attribution(
        config_path=Path(args.config),
        tickers=args.tickers,
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        cadences=tuple(args.cadences),
        lookback_days=args.lookback_days,
        methodology=args.methodology,
        include_flow_evidence=not args.skip_flow_evidence,
        window_limit=args.window_limit,
        rerun_existing=args.rerun_existing,
    )
    print(report.render())


def run_pilot_kospi_attribution(
    *,
    config_path: Path = DEFAULT_KOSPI_CONFIG,
    tickers: list[str] | None,
    start: date,
    end: date,
    cadences: tuple[str, ...] = ("daily",),
    lookback_days: int = 252,
    methodology: str = METHODOLOGY_RESIDUAL_SAFETY,
    include_flow_evidence: bool = True,
    window_limit: int | None = None,
    rerun_existing: bool = False,
) -> PilotKospiAttributionReport:
    assert_pilot_kospi_database_url()
    if methodology not in VALID_KOSPI_METHODOLOGIES:
        raise ValueError(f"unsupported KOSPI pilot methodology {methodology}")
    payload = load_kospi_universe_config(config_path)
    universe_tickers = [item["ticker"] for item in payload["securities"]]
    selected_tickers = sorted(
        {normalize_kospi_ticker(ticker) for ticker in (tickers or universe_tickers)}
    )
    report = PilotKospiAttributionReport(methodology=methodology, tickers=len(selected_tickers))
    analysis_start = _date_to_utc_datetime(start)
    analysis_end = _date_to_utc_datetime(end) + timedelta(days=1)
    cutoff = datetime.now(timezone.utc)

    for ticker in selected_tickers:
        try:
            with session_scope() as session:
                security = find_security(session=session, ticker=ticker)
                security_id = security.security_id
        except Exception as exc:
            report.skipped_windows += 1
            report.skip_reasons.append(f"{ticker}: {str(exc).splitlines()[0]}")
            continue
        for cadence in cadences:
            with session_scope() as session:
                trading_dates = load_trading_dates(
                    session=session,
                    security_id=security_id,
                    start=analysis_start - timedelta(days=lookback_days * 2),
                    end=analysis_end,
                )
            windows = [
                window
                for window in build_windows(trading_dates=trading_dates, cadence=cadence)
                if window.start >= analysis_start
            ]
            if window_limit is not None:
                windows = windows[:window_limit]
            report.expected_windows += len(windows)
            if not rerun_existing:
                with session_scope() as session:
                    completed_keys = completed_window_keys(
                        session=session,
                        security_id=security_id,
                        cadence=cadence,
                        methodology=methodology,
                    )
                remaining_windows = [
                    window for window in windows if (window.start, window.end) not in completed_keys
                ]
                report.already_completed_windows += len(windows) - len(remaining_windows)
                windows = remaining_windows
            for window in windows:
                try:
                    with session_scope() as session:
                        extra_inputs = (
                            build_flow_evidence_inputs(
                                session=session,
                                security_id=security_id,
                                ticker=ticker,
                                window=window,
                                attribution_cutoff=cutoff,
                            )
                            if include_flow_evidence
                            else None
                        )
                        run_attribution_for_ticker(
                            session=session,
                            ticker=ticker,
                            window=window,
                            attribution_cutoff=cutoff,
                            use_market_factor=True,
                            market_factor_name=KOSPI_MARKET_FACTOR_NAME,
                            lookback_days=lookback_days,
                            cadence=cadence,
                            methodology=methodology,
                            extra_factor_inputs=extra_inputs,
                        )
                    report.ran_windows += 1
                except Exception as exc:
                    report.skipped_windows += 1
                    report.skip_reasons.append(f"{ticker}:{cadence}: {str(exc).splitlines()[0]}")
    return report


def completed_window_keys(*, session, security_id, cadence: str, methodology: str) -> set[tuple[datetime, datetime]]:
    rows = session.execute(
        select(models.AttributionRun.window_start, models.AttributionRun.window_end)
        .where(models.AttributionRun.security_id == security_id)
        .where(models.AttributionRun.cadence == cadence)
        .where(models.AttributionRun.model_version == model_version_for_methodology(methodology))
        .where(
            models.AttributionRun.factor_basket_version
            == market_factor_basket_version(KOSPI_MARKET_FACTOR_NAME)
        )
    )
    return {(row.window_start, row.window_end) for row in rows}


def model_version_for_methodology(methodology: str) -> str:
    if methodology == METHODOLOGY_LEGACY:
        return "factor-baseline-v0"
    if methodology == METHODOLOGY_RESIDUAL_SAFETY:
        return RESIDUAL_SAFETY_MODEL_VERSION
    raise ValueError(f"unsupported KOSPI pilot methodology {methodology}")


def top_counts(values: list[str], limit: int = 5) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()
