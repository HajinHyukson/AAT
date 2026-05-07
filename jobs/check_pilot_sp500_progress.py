from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import distinct, func, select

from db import models
from db.session import session_scope
from jobs.evaluate_pilot_methodologies import MODEL_VERSION_BY_METHODOLOGY
from jobs.pilot_sp500_common import (
    DEFAULT_CONFIG,
    PILOT_DATABASE_NAME,
    PILOT_UNIVERSE_NAME,
    ensure_pilot_database_url,
    load_pilot_universe_config,
    pilot_securities,
)
from jobs.run_batch_attribution import build_windows, load_trading_dates
from jobs.run_pilot_sp500_attribution import VALID_CADENCES


@dataclass
class DataProgress:
    config_tickers: int
    universe_members: int
    eligible_members: int
    missing_price_members: int
    priced_members: int
    price_bar_rows: int
    latest_price_time: datetime | None
    factor_return_rows: int
    macro_series_rows: int
    peer_baskets: int
    peer_members: int
    events: int
    event_features: int


@dataclass
class CadenceProgress:
    cadence: str
    runs: int
    tickers_with_runs: int
    expected_windows: int | None
    remaining_windows: int | None
    percent_complete: float | None
    latest_created_at: datetime | None


@dataclass
class MethodologyProgress:
    methodology: str
    model_version: str
    cadences: list[CadenceProgress] = field(default_factory=list)


@dataclass
class PilotProgressReport:
    database_name: str
    universe_name: str
    universe_version: str
    analysis_start: date | None
    analysis_end: date | None
    data: DataProgress
    attribution: list[MethodologyProgress]

    def render(self) -> str:
        lines = [
            "pilot S&P 500 progress",
            f"  database={self.database_name}",
            f"  universe={self.universe_name} version={self.universe_version}",
            f"  analysis_window={self.analysis_start}->{self.analysis_end}",
            (
                "  data: "
                f"members={self.data.universe_members}/{self.data.config_tickers} "
                f"eligible={self.data.eligible_members} "
                f"priced={self.data.priced_members} "
                f"missing_prices={self.data.missing_price_members} "
                f"price_bar_rows={self.data.price_bar_rows} "
                f"latest_price={format_datetime(self.data.latest_price_time)}"
            ),
            (
                "  factors: "
                f"factor_return_rows={self.data.factor_return_rows} "
                f"macro_series_rows={self.data.macro_series_rows} "
                f"peer_baskets={self.data.peer_baskets} "
                f"peer_members={self.data.peer_members}"
            ),
            f"  events: events={self.data.events} event_features={self.data.event_features}",
        ]
        for methodology in self.attribution:
            lines.append(f"  methodology={methodology.methodology} model={methodology.model_version}")
            for cadence in methodology.cadences:
                expected = "n/a" if cadence.expected_windows is None else str(cadence.expected_windows)
                remaining = "n/a" if cadence.remaining_windows is None else str(cadence.remaining_windows)
                percent = "n/a" if cadence.percent_complete is None else f"{cadence.percent_complete:.1f}%"
                lines.append(
                    "    "
                    f"{cadence.cadence}: runs={cadence.runs}/{expected} "
                    f"remaining={remaining} pct={percent} "
                    f"tickers={cadence.tickers_with_runs} "
                    f"latest={format_datetime(cadence.latest_created_at)}"
                )
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local S&P 500 pilot DB population and attribution progress")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--from", dest="start", help="Analysis start date YYYY-MM-DD; enables expected-window estimates")
    parser.add_argument("--to", dest="end", help="Analysis end date YYYY-MM-DD; defaults to today when --from is set")
    parser.add_argument("--lookback-days", type=int, default=252)
    parser.add_argument("--cadences", nargs="+", choices=VALID_CADENCES, default=list(VALID_CADENCES))
    parser.add_argument("--methodologies", nargs="+", default=list(MODEL_VERSION_BY_METHODOLOGY))
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else date.today() if start else None
    report = check_pilot_sp500_progress(
        config_path=Path(args.config),
        start=start,
        end=end,
        lookback_days=args.lookback_days,
        cadences=tuple(args.cadences),
        methodologies=tuple(args.methodologies),
    )
    if args.json:
        print(json.dumps(asdict(report), default=json_default, indent=2))
    else:
        print(report.render())


def check_pilot_sp500_progress(
    *,
    config_path: Path = DEFAULT_CONFIG,
    start: date | None = None,
    end: date | None = None,
    lookback_days: int = 252,
    cadences: tuple[str, ...] = VALID_CADENCES,
    methodologies: tuple[str, ...] = tuple(MODEL_VERSION_BY_METHODOLOGY),
) -> PilotProgressReport:
    ensure_pilot_database_url()
    payload = load_pilot_universe_config(config_path)
    config_tickers = len(pilot_securities(payload))
    universe_version = str(payload["version"])
    with session_scope() as session:
        security_ids = list(
            session.execute(
                select(models.ModelUniverseMember.security_id)
                .where(models.ModelUniverseMember.universe_name == PILOT_UNIVERSE_NAME)
                .where(models.ModelUniverseMember.universe_version == universe_version)
            ).scalars()
        )
        expected_by_cadence = (
            expected_windows_by_cadence(
                session=session,
                security_ids=security_ids,
                start=start,
                end=end,
                lookback_days=lookback_days,
                cadences=cadences,
            )
            if start and end
            else {}
        )
        return PilotProgressReport(
            database_name=PILOT_DATABASE_NAME,
            universe_name=PILOT_UNIVERSE_NAME,
            universe_version=universe_version,
            analysis_start=start,
            analysis_end=end,
            data=load_data_progress(
                session=session,
                universe_version=universe_version,
                config_tickers=config_tickers,
            ),
            attribution=[
                load_methodology_progress(
                    session=session,
                    methodology=methodology,
                    universe_version=universe_version,
                    cadences=cadences,
                    expected_by_cadence=expected_by_cadence,
                )
                for methodology in methodologies
            ],
        )


def load_data_progress(*, session, universe_version: str, config_tickers: int) -> DataProgress:
    base_member_stmt = (
        select(models.ModelUniverseMember)
        .where(models.ModelUniverseMember.universe_name == PILOT_UNIVERSE_NAME)
        .where(models.ModelUniverseMember.universe_version == universe_version)
    )
    universe_members = scalar_count(session, base_member_stmt.subquery())
    eligible_members = scalar_count(
        session,
        base_member_stmt.where(models.ModelUniverseMember.eligibility_status == "eligible").subquery(),
    )
    member_rows = base_member_stmt.subquery()
    priced_members = int(
        session.execute(
            select(func.count(distinct(member_rows.c.security_id))).select_from(
                member_rows.join(models.PriceBar, models.PriceBar.security_id == member_rows.c.security_id)
            )
        ).scalar_one()
        or 0
    )
    missing_price_members = max(universe_members - priced_members, 0)
    return DataProgress(
        config_tickers=config_tickers,
        universe_members=universe_members,
        eligible_members=eligible_members,
        missing_price_members=missing_price_members,
        priced_members=priced_members,
        price_bar_rows=session.execute(select(func.count(models.PriceBar.price_bar_id))).scalar_one(),
        latest_price_time=session.execute(select(func.max(models.PriceBar.event_time))).scalar_one_or_none(),
        factor_return_rows=session.execute(select(func.count(models.FactorReturn.factor_return_id))).scalar_one(),
        macro_series_rows=session.execute(select(func.count(models.MacroSeries.macro_series_id))).scalar_one(),
        peer_baskets=session.execute(select(func.count(models.PeerBasket.peer_basket_id))).scalar_one(),
        peer_members=session.execute(select(func.count(models.PeerBasketMember.peer_basket_member_id))).scalar_one(),
        events=session.execute(select(func.count(models.Event.event_id))).scalar_one(),
        event_features=session.execute(select(func.count(models.EventFeature.event_feature_id))).scalar_one(),
    )


def load_methodology_progress(
    *,
    session,
    methodology: str,
    universe_version: str,
    cadences: tuple[str, ...],
    expected_by_cadence: dict[str, int],
) -> MethodologyProgress:
    if methodology not in MODEL_VERSION_BY_METHODOLOGY:
        raise ValueError(f"unknown pilot methodology {methodology}")
    model_version = MODEL_VERSION_BY_METHODOLOGY[methodology]
    return MethodologyProgress(
        methodology=methodology,
        model_version=model_version,
        cadences=[
            load_cadence_progress(
                session=session,
                model_version=model_version,
                universe_version=universe_version,
                cadence=cadence,
                expected_windows=expected_by_cadence.get(cadence),
            )
            for cadence in cadences
        ],
    )


def load_cadence_progress(
    *,
    session,
    model_version: str,
    universe_version: str,
    cadence: str,
    expected_windows: int | None,
) -> CadenceProgress:
    base = (
        select(models.AttributionRun)
        .join(models.ModelUniverseMember, models.ModelUniverseMember.security_id == models.AttributionRun.security_id)
        .where(models.ModelUniverseMember.universe_name == PILOT_UNIVERSE_NAME)
        .where(models.ModelUniverseMember.universe_version == universe_version)
        .where(models.AttributionRun.model_version == model_version)
        .where(models.AttributionRun.cadence == cadence)
    )
    run_rows = base.subquery()
    runs = scalar_count(session, run_rows)
    tickers_with_runs = session.execute(
        select(func.count(distinct(run_rows.c.security_id))).select_from(run_rows)
    ).scalar_one()
    latest_created_at = session.execute(
        select(func.max(run_rows.c.created_at)).select_from(run_rows)
    ).scalar_one_or_none()
    remaining = max(expected_windows - runs, 0) if expected_windows is not None else None
    percent = progress_percent(runs=runs, expected=expected_windows)
    return CadenceProgress(
        cadence=cadence,
        runs=runs,
        tickers_with_runs=tickers_with_runs,
        expected_windows=expected_windows,
        remaining_windows=remaining,
        percent_complete=percent,
        latest_created_at=latest_created_at,
    )


def expected_windows_by_cadence(
    *,
    session,
    security_ids: list,
    start: date,
    end: date,
    lookback_days: int,
    cadences: tuple[str, ...],
) -> dict[str, int]:
    analysis_start = date_to_utc_datetime(start)
    analysis_end = date_to_utc_datetime(end)
    data_start = analysis_start - timedelta(days=lookback_days * 2)
    expected = {cadence: 0 for cadence in cadences}
    for security_id in security_ids:
        trading_dates = load_trading_dates(
            session=session,
            security_id=security_id,
            start=data_start,
            end=analysis_end,
        )
        for cadence in cadences:
            expected[cadence] += sum(
                1
                for window in build_windows(trading_dates=trading_dates, cadence=cadence)
                if window.start >= analysis_start
            )
    return expected


def scalar_count(session, subquery) -> int:
    return int(session.execute(select(func.count()).select_from(subquery)).scalar_one() or 0)


def progress_percent(*, runs: int, expected: int | None) -> float | None:
    if expected is None or expected <= 0:
        return None
    return min((runs / expected) * 100.0, 100.0)


def date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "None"
    return value.isoformat()


def json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


if __name__ == "__main__":
    main()
