from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from engine.contracts import (
    ConfidenceLevel,
    ContributionStage,
    DriverType,
    FactorContributionInput,
    PriceBar as EnginePriceBar,
    TimeWindow,
)
from engine.events.taxonomy import classify_event
from engine.factors.baseline import build_factor_baseline_result
from engine.factors.french_model import FRENCH_FACTOR_NAMES, build_french_factor_inputs
from engine.factors.macro_model import (
    build_macro_factor_inputs,
    level_changes_by_date,
    percent_returns_by_date,
    spread_by_date,
)
from engine.factors.market_model import build_market_factor_input
from engine.factors.peer_model import PeerWeight, build_peer_basket_returns, build_peer_factor_input
from engine.factors.sector_model import build_sector_factor_inputs
from engine.factors.style_model import build_return_style_descriptors, descriptors_to_exposures
from engine.returns.accounting import close_to_close_return_bps


@dataclass(frozen=True)
class ActivePeerContext:
    target_security_id: uuid.UUID
    basket_name: str
    basket_version: str
    peer_weights: list[PeerWeight]
    peer_basket_returns: dict[datetime, float]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run baseline attribution for a ticker")
    parser.add_argument("ticker")
    parser.add_argument("--from", dest="start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--cutoff", help="Attribution cutoff ISO datetime; defaults to now UTC")
    parser.add_argument("--use-market-factor", action="store_true")
    parser.add_argument("--use-french-factors", action="store_true")
    parser.add_argument("--use-expanded-mvp", action="store_true")
    parser.add_argument("--include-event-evidence", action="store_true")
    parser.add_argument("--lookback-days", type=int, default=60)
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    window = TimeWindow(
        start=_date_to_utc_datetime(date.fromisoformat(args.start)),
        end=_date_to_utc_datetime(date.fromisoformat(args.end)),
    )
    cutoff = (
        datetime.fromisoformat(args.cutoff).astimezone(timezone.utc)
        if args.cutoff
        else datetime.now(timezone.utc)
    )

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        result = run_attribution_for_ticker(
            session=session,
            ticker=ticker,
            window=window,
            attribution_cutoff=cutoff,
            use_market_factor=args.use_market_factor,
            use_french_factors=args.use_french_factors,
            use_expanded_mvp=args.use_expanded_mvp,
            include_event_evidence=args.include_event_evidence,
            lookback_days=args.lookback_days,
        )

    print(
        "ran attribution "
        f"ticker={ticker} observed_return_bps={result.observed_return_bps:.2f} "
        f"unexplained_residual_bps={result.unexplained_residual_bps:.2f}"
    )


def run_attribution_for_ticker(
    *,
    session,
    ticker: str,
    window: TimeWindow,
    attribution_cutoff: datetime,
    use_market_factor: bool = False,
    use_french_factors: bool = False,
    use_expanded_mvp: bool = False,
    include_event_evidence: bool = False,
    lookback_days: int = 60,
    cadence: str = "daily",
    preloaded_price_bars: list[EnginePriceBar] | None = None,
    preloaded_factor_returns_by_name: dict[str, dict[datetime, float]] | None = None,
    preloaded_macro_values_by_name: dict[str, dict[datetime, float]] | None = None,
    preloaded_peer_context: ActivePeerContext | None = None,
):
    security = find_security(session=session, ticker=ticker)
    return run_attribution_for_security(
        session=session,
        security=security,
        window=window,
        attribution_cutoff=attribution_cutoff,
        use_market_factor=use_market_factor,
        use_french_factors=use_french_factors,
        use_expanded_mvp=use_expanded_mvp,
        include_event_evidence=include_event_evidence,
        lookback_days=lookback_days,
        cadence=cadence,
        preloaded_price_bars=preloaded_price_bars,
        preloaded_factor_returns_by_name=preloaded_factor_returns_by_name,
        preloaded_macro_values_by_name=preloaded_macro_values_by_name,
        preloaded_peer_context=preloaded_peer_context,
    )


def run_attribution_for_security(
    *,
    session,
    security: models.Security,
    window: TimeWindow,
    attribution_cutoff: datetime,
    use_market_factor: bool = False,
    use_french_factors: bool = False,
    use_expanded_mvp: bool = False,
    include_event_evidence: bool = False,
    lookback_days: int = 60,
    cadence: str = "daily",
    preloaded_price_bars: list[EnginePriceBar] | None = None,
    preloaded_factor_returns_by_name: dict[str, dict[datetime, float]] | None = None,
    preloaded_macro_values_by_name: dict[str, dict[datetime, float]] | None = None,
    preloaded_peer_context: ActivePeerContext | None = None,
):
    estimation_window = TimeWindow(
        start=window.start - timedelta(days=lookback_days),
        end=window.start,
    )
    needs_estimation_bars = use_market_factor or use_french_factors or use_expanded_mvp
    price_window = estimation_window if needs_estimation_bars else window
    bars = (
        filter_engine_price_bars(
            bars=preloaded_price_bars,
            security_id=security.security_id,
            window=price_window,
            through=window.end,
            attribution_cutoff=attribution_cutoff,
        )
        if preloaded_price_bars is not None
        else load_engine_price_bars(
            session=session,
            security_id=security.security_id,
            window=price_window,
            through=window.end,
            attribution_cutoff=attribution_cutoff,
        )
    )
    observed_return_bps = close_to_close_return_bps(
        security_id=security.security_id,
        window=window,
        bars=bars,
        attribution_cutoff=attribution_cutoff,
    )
    factor_inputs = []
    factor_basket_version = "none"
    if use_expanded_mvp:
        use_french_factors = True
        factor_basket_version = "mvp_expanded_v0"

    if use_french_factors:
        factor_returns_by_name = factor_returns_for_window(
            session=session,
            preloaded_factor_returns_by_name=preloaded_factor_returns_by_name,
            factor_names=FRENCH_FACTOR_NAMES,
            window=TimeWindow(start=estimation_window.start, end=window.end),
            attribution_cutoff=attribution_cutoff,
        )
        factor_inputs.extend(
            build_french_factor_inputs(
                security_id=security.security_id,
                price_bars=bars,
                factor_returns_by_name=factor_returns_by_name,
                estimation_window=estimation_window,
                attribution_window=window,
                attribution_cutoff=attribution_cutoff,
            )
        )
        if not use_expanded_mvp:
            factor_basket_version = "french_5_v0"
    elif use_market_factor:
        market_returns = factor_returns_for_window(
            session=session,
            preloaded_factor_returns_by_name=preloaded_factor_returns_by_name,
            factor_names=("Mkt-RF",),
            window=TimeWindow(start=estimation_window.start, end=window.end),
            attribution_cutoff=attribution_cutoff,
        )["Mkt-RF"]
        market_input = build_market_factor_input(
            security_id=security.security_id,
            price_bars=bars,
            market_factor_returns=market_returns,
            estimation_window=estimation_window,
            attribution_window=window,
            attribution_cutoff=attribution_cutoff,
            preloaded_peer_context=preloaded_peer_context,
        )
        if market_input is not None:
            factor_inputs.append(market_input)
        factor_basket_version = "french_market_v0"

    if use_expanded_mvp:
        sector_factor_names = load_active_sector_factor_names(
            session=session,
            security_id=security.security_id,
            attribution_cutoff=attribution_cutoff,
        )
        if sector_factor_names:
            factor_returns_by_name = factor_returns_for_window(
                session=session,
                preloaded_factor_returns_by_name=preloaded_factor_returns_by_name,
                factor_names=tuple(sector_factor_names),
                window=TimeWindow(start=estimation_window.start, end=window.end),
                attribution_cutoff=attribution_cutoff,
            )
            factor_inputs.extend(
                build_sector_factor_inputs(
                    security_id=security.security_id,
                    price_bars=bars,
                    factor_returns_by_name=factor_returns_by_name,
                    estimation_window=estimation_window,
                    attribution_window=window,
                    attribution_cutoff=attribution_cutoff,
                )
            )

        peer_input = build_active_peer_input(
            session=session,
            security_id=security.security_id,
            target_bars=bars,
            estimation_window=estimation_window,
            attribution_window=window,
            attribution_cutoff=attribution_cutoff,
        )
        if peer_input is not None:
            factor_inputs.append(peer_input)

        descriptors = build_return_style_descriptors(
            security_id=security.security_id,
            price_bars=bars,
            as_of=attribution_cutoff,
        )
        persist_style_exposures(
            session=session,
            exposures=descriptors_to_exposures(
                security_id=security.security_id,
                descriptors=descriptors,
                as_of=attribution_cutoff,
            ),
        )
        factor_inputs.extend(
            style_descriptors_to_evidence_inputs(
                security_id=security.security_id,
                descriptors=descriptors,
                attribution_window=window,
                attribution_cutoff=attribution_cutoff,
            )
        )

        macro_inputs = build_mvp_macro_inputs(
            session=session,
            security=security,
            bars=bars,
            estimation_window=estimation_window,
            attribution_window=window,
            attribution_cutoff=attribution_cutoff,
            preloaded_macro_values_by_name=preloaded_macro_values_by_name,
        )
        factor_inputs.extend(macro_inputs)

        if include_event_evidence:
            factor_inputs.extend(
                load_event_evidence_inputs(
                    session=session,
                    security=security,
                    window=window,
                    attribution_cutoff=attribution_cutoff,
                )
            )

    result = build_factor_baseline_result(
        security_id=security.security_id,
        window=window,
        attribution_cutoff=attribution_cutoff,
        observed_return_bps=observed_return_bps,
        factor_inputs=factor_inputs,
    )
    persist_attribution_result(
        session=session,
        result=result,
        factor_basket_version=factor_basket_version,
        cadence=cadence,
    )
    return result


def load_active_sector_factor_names(*, session, security_id: uuid.UUID, attribution_cutoff: datetime) -> list[str]:
    classification = session.execute(
        select(models.SectorClassificationHistory)
        .where(models.SectorClassificationHistory.security_id == security_id)
        .where(models.SectorClassificationHistory.timestamp_available <= attribution_cutoff)
        .order_by(models.SectorClassificationHistory.event_time.desc())
        .limit(1)
    ).scalar_one_or_none()
    if classification is None:
        return []
    names = [f"sector:{classification.sector}"]
    if classification.industry:
        names.append(f"industry:{classification.industry}")
    return names


def build_active_peer_input(
    *,
    session,
    security_id: uuid.UUID,
    target_bars: list[EnginePriceBar],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
    preloaded_peer_context: ActivePeerContext | None = None,
) -> FactorContributionInput | None:
    if preloaded_peer_context is not None:
        if preloaded_peer_context.target_security_id != security_id:
            return None
        return build_peer_factor_input(
            security_id=security_id,
            basket_name=preloaded_peer_context.basket_name,
            basket_version=preloaded_peer_context.basket_version,
            price_bars=target_bars,
            peer_basket_returns=preloaded_peer_context.peer_basket_returns,
            estimation_window=estimation_window,
            attribution_window=attribution_window,
            attribution_cutoff=attribution_cutoff,
        )

    context = load_active_peer_context(
        session=session,
        security_id=security_id,
        price_window=estimation_window,
        through=attribution_window.end,
        attribution_cutoff=attribution_cutoff,
    )
    if context is None:
        return None
    return build_peer_factor_input(
        security_id=security_id,
        basket_name=context.basket_name,
        basket_version=context.basket_version,
        price_bars=target_bars,
        peer_basket_returns=context.peer_basket_returns,
        estimation_window=estimation_window,
        attribution_window=attribution_window,
        attribution_cutoff=attribution_cutoff,
    )


def load_active_peer_context(
    *,
    session,
    security_id: uuid.UUID,
    price_window: TimeWindow,
    through: datetime,
    attribution_cutoff: datetime,
) -> ActivePeerContext | None:
    basket = session.execute(
        select(models.PeerBasket)
        .where(models.PeerBasket.target_security_id == security_id)
        .where(models.PeerBasket.timestamp_available <= attribution_cutoff)
        .where(models.PeerBasket.active_from <= attribution_cutoff)
        .where((models.PeerBasket.active_to.is_(None)) | (models.PeerBasket.active_to > attribution_cutoff))
        .order_by(models.PeerBasket.event_time.desc())
        .limit(1)
    ).scalar_one_or_none()
    if basket is None:
        return None
    members = list(
        session.execute(
            select(models.PeerBasketMember)
            .where(models.PeerBasketMember.peer_basket_id == basket.peer_basket_id)
            .where(models.PeerBasketMember.peer_security_id != security_id)
            .where(models.PeerBasketMember.timestamp_available <= attribution_cutoff)
        ).scalars()
    )
    if len(members) < 3:
        return None
    peer_weights = [
        PeerWeight(
            peer_security_id=item.peer_security_id,
            weight=float(item.weight),
            active_from=item.active_from,
            active_to=item.active_to,
            timestamp_available=item.timestamp_available,
        )
        for item in members
    ]
    price_bars_by_security = {
        item.peer_security_id: load_engine_price_bars(
            session=session,
            security_id=item.peer_security_id,
            window=price_window,
            through=through,
            attribution_cutoff=attribution_cutoff,
        )
        for item in members
    }
    peer_returns = build_peer_basket_returns(
        peer_weights=peer_weights,
        price_bars_by_security=price_bars_by_security,
        attribution_cutoff=attribution_cutoff,
    )
    return ActivePeerContext(
        target_security_id=security_id,
        basket_name=basket.basket_name,
        basket_version=basket.basket_version,
        peer_basket_returns=peer_returns,
        peer_weights=peer_weights,
    )


def persist_style_exposures(*, session, exposures) -> None:
    for exposure in exposures:
        stmt = insert(models.SecurityFactorExposure).values(
            security_id=exposure.security_id,
            factor_name=exposure.factor_name,
            exposure_value=exposure.exposure_value,
            exposure_unit=exposure.exposure_unit,
            exposure_method=exposure.exposure_method,
            confidence=exposure.confidence.value,
            model_version=exposure.model_version,
            diagnostics=exposure.diagnostics,
            event_time=exposure.event_time,
            ingestion_time=exposure.ingestion_time,
            timestamp_available=exposure.timestamp_available,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_security_factor_exposure_model_time",
            set_={
                "exposure_value": stmt.excluded.exposure_value,
                "confidence": stmt.excluded.confidence,
                "diagnostics": stmt.excluded.diagnostics,
                "ingestion_time": stmt.excluded.ingestion_time,
                "timestamp_available": stmt.excluded.timestamp_available,
            },
        )
        session.execute(stmt)


def style_descriptors_to_evidence_inputs(
    *,
    security_id: uuid.UUID,
    descriptors,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
) -> list[FactorContributionInput]:
    return [
        FactorContributionInput(
            security_id=security_id,
            driver=DriverType.STYLE,
            name=f"Style descriptor ({descriptor.name})",
            contribution_bps=0.0,
            confidence=descriptor.confidence,
            contribution_stage=ContributionStage.EVIDENCE_ONLY,
            exposure_value=descriptor.value,
            exposure_unit=descriptor.unit,
            evidence=[
                f"value={descriptor.value:.4f}",
                f"unit={descriptor.unit}",
                f"model={descriptor.diagnostics.get('model_version')}",
            ],
            evidence_payload={
                "descriptor_name": descriptor.name,
                "value": descriptor.value,
                "unit": descriptor.unit,
                **descriptor.diagnostics,
            },
            event_time=attribution_window.end,
            ingestion_time=attribution_cutoff,
            timestamp_available=attribution_cutoff,
        )
        for descriptor in descriptors
    ]


def build_mvp_macro_inputs(
    *,
    session,
    security: models.Security,
    bars: list[EnginePriceBar],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
    preloaded_macro_values_by_name: dict[str, dict[datetime, float]] | None = None,
) -> list[FactorContributionInput]:
    values_by_name = {
        name: series_for_window(
            series=preloaded_macro_values_by_name.get(name, {})
            if preloaded_macro_values_by_name is not None
            else load_macro_values(
                session=session,
                series_name=name,
                window=TimeWindow(start=estimation_window.start, end=attribution_window.end),
                attribution_cutoff=attribution_cutoff,
            ),
            window=TimeWindow(start=estimation_window.start, end=attribution_window.end),
        )
        for name in ("DGS2", "DGS10", "BAMLH0A0HYM2", "BAMLC0A0CM", "VIXCLS", "T5YIE")
    }
    factor_moves = {}
    if values_by_name["DGS2"]:
        factor_moves["macro:2y_yield_change"] = level_changes_by_date(values_by_name["DGS2"], multiplier=100)
    if values_by_name["DGS10"]:
        factor_moves["macro:10y_yield_change"] = level_changes_by_date(values_by_name["DGS10"], multiplier=100)
    if values_by_name["DGS10"] and values_by_name["DGS2"]:
        factor_moves["macro:2s10s_curve_change"] = level_changes_by_date(
            spread_by_date(long_values_by_date=values_by_name["DGS10"], short_values_by_date=values_by_name["DGS2"]),
            multiplier=100,
        )
    if values_by_name["BAMLH0A0HYM2"]:
        factor_moves["macro:hy_spread_change"] = level_changes_by_date(values_by_name["BAMLH0A0HYM2"], multiplier=100)
    if values_by_name["BAMLC0A0CM"]:
        factor_moves["macro:ig_spread_change"] = level_changes_by_date(values_by_name["BAMLC0A0CM"], multiplier=100)
    if values_by_name["VIXCLS"]:
        factor_moves["macro:vix_return"] = percent_returns_by_date(values_by_name["VIXCLS"])
    if values_by_name["T5YIE"]:
        factor_moves["macro:inflation_expectation_change"] = level_changes_by_date(values_by_name["T5YIE"], multiplier=100)

    gates = load_macro_exposure_gates(
        session=session,
        company_id=security.company_id,
        attribution_cutoff=attribution_cutoff,
    )
    return build_macro_factor_inputs(
        security_id=security.security_id,
        price_bars=bars,
        macro_factor_moves_by_name={name: moves for name, moves in factor_moves.items() if moves},
        estimation_window=estimation_window,
        attribution_window=attribution_window,
        attribution_cutoff=attribution_cutoff,
        exposure_gate_by_name=gates,
    )


def load_macro_values(
    *,
    session,
    series_name: str,
    window: TimeWindow,
    attribution_cutoff: datetime,
) -> dict[datetime, float]:
    rows = session.execute(
        select(models.MacroSeries)
        .where(models.MacroSeries.series_name == series_name)
        .where(models.MacroSeries.event_time >= window.start)
        .where(models.MacroSeries.event_time <= window.end)
        .where(models.MacroSeries.timestamp_available <= attribution_cutoff)
        .order_by(models.MacroSeries.event_time)
    ).scalars()
    return {row.event_time: float(row.value) for row in rows}


def load_macro_exposure_gates(*, session, company_id: uuid.UUID, attribution_cutoff: datetime) -> dict[str, float]:
    rows = session.execute(
        select(models.CompanyExposure)
        .where(models.CompanyExposure.company_id == company_id)
        .where(models.CompanyExposure.timestamp_available <= attribution_cutoff)
    ).scalars()
    gate_by_exposure = {row.exposure_name: float(row.exposure_value) for row in rows}
    rate_gate = gate_by_exposure.get("rates", 1.0)
    credit_gate = gate_by_exposure.get("credit", 1.0)
    return {
        "macro:2y_yield_change": rate_gate,
        "macro:10y_yield_change": rate_gate,
        "macro:2s10s_curve_change": rate_gate,
        "macro:hy_spread_change": credit_gate,
        "macro:ig_spread_change": credit_gate,
        "macro:vix_return": 1.0,
        "macro:inflation_expectation_change": gate_by_exposure.get("inflation", 0.5),
    }


def load_event_evidence_inputs(
    *,
    session,
    security: models.Security,
    window: TimeWindow,
    attribution_cutoff: datetime,
) -> list[FactorContributionInput]:
    events = list(
        session.execute(
            select(models.Event)
            .where(models.Event.company_id == security.company_id)
            .where(models.Event.event_time >= window.start)
            .where(models.Event.event_time <= window.end)
            .where(models.Event.timestamp_available <= attribution_cutoff)
            .order_by(models.Event.event_time)
        ).scalars()
    )
    inputs = []
    for event in events:
        taxonomy = classify_event(
            event_id=event.event_id,
            event_type=event.event_type,
            structured_payload=event.structured_payload,
            event_time=event.event_time,
            ingestion_time=attribution_cutoff,
            timestamp_available=event.timestamp_available,
        )
        upsert_event_taxonomy(session=session, taxonomy=taxonomy)
        inputs.append(
            FactorContributionInput(
                security_id=security.security_id,
                driver=DriverType.EVENT,
                name=f"Event evidence ({taxonomy.event_category}/{taxonomy.event_subtype})",
                contribution_bps=0.0,
                confidence=ConfidenceLevel.MEDIUM,
                contribution_stage=ContributionStage.EVIDENCE_ONLY,
                evidence=[
                    f"source={event.source}",
                    f"source_id={event.source_id}",
                    f"category={taxonomy.event_category}",
                    f"subtype={taxonomy.event_subtype}",
                    "causal_contribution=not_assigned",
                ],
                evidence_payload={
                    "event_id": str(event.event_id),
                    "source": event.source,
                    "source_id": event.source_id,
                    "event_type": event.event_type,
                    "event_category": taxonomy.event_category,
                    "event_subtype": taxonomy.event_subtype,
                    "event_direction": taxonomy.event_direction,
                    "materiality": taxonomy.materiality,
                    "contribution_policy": "evidence_only_until_event_study_calibration",
                },
                event_time=event.event_time,
                ingestion_time=attribution_cutoff,
                timestamp_available=event.timestamp_available,
            )
        )
    return inputs


def upsert_event_taxonomy(*, session, taxonomy) -> None:
    stmt = insert(models.EventTaxonomy).values(
        event_id=taxonomy.event_id,
        event_category=taxonomy.event_category,
        event_subtype=taxonomy.event_subtype,
        event_direction=taxonomy.event_direction,
        materiality=taxonomy.materiality,
        taxonomy_version=taxonomy.taxonomy_version,
        evidence_payload=taxonomy.evidence_payload,
        event_time=taxonomy.event_time,
        ingestion_time=taxonomy.ingestion_time,
        timestamp_available=taxonomy.timestamp_available,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_event_taxonomy_version",
        set_={
            "event_category": stmt.excluded.event_category,
            "event_subtype": stmt.excluded.event_subtype,
            "event_direction": stmt.excluded.event_direction,
            "materiality": stmt.excluded.materiality,
            "evidence_payload": stmt.excluded.evidence_payload,
            "ingestion_time": stmt.excluded.ingestion_time,
            "timestamp_available": stmt.excluded.timestamp_available,
        },
    )
    session.execute(stmt)


def find_security(*, session, ticker: str) -> models.Security:
    security = session.execute(
        select(models.Security)
        .join(
            models.SecurityTickerHistory,
            models.Security.security_id == models.SecurityTickerHistory.security_id,
        )
        .where(models.SecurityTickerHistory.ticker == ticker)
        .where(models.SecurityTickerHistory.active_to.is_(None))
        .order_by(models.SecurityTickerHistory.active_from.desc())
        .limit(1)
    ).scalar_one_or_none()
    if security is None:
        raise RuntimeError(f"no active security found for ticker {ticker}")
    return security


def load_engine_price_bars(
    *,
    session,
    security_id: uuid.UUID,
    window: TimeWindow,
    through: datetime | None = None,
    attribution_cutoff: datetime | None = None,
) -> list[EnginePriceBar]:
    end = through or window.end
    ranked_rows = (
        select(
            models.PriceBar.price_bar_id.label("price_bar_id"),
            func.row_number()
            .over(
                partition_by=models.PriceBar.event_time,
                order_by=(models.PriceBar.timestamp_available.desc(), models.PriceBar.source.asc()),
            )
            .label("row_number"),
        )
        .where(models.PriceBar.security_id == security_id)
        .where(models.PriceBar.event_time >= window.start)
        .where(models.PriceBar.event_time <= end)
    )
    if attribution_cutoff is not None:
        ranked_rows = ranked_rows.where(models.PriceBar.timestamp_available <= attribution_cutoff)
    ranked_rows = ranked_rows.subquery()
    stmt = (
        select(models.PriceBar)
        .join(ranked_rows, ranked_rows.c.price_bar_id == models.PriceBar.price_bar_id)
        .where(ranked_rows.c.row_number == 1)
        .order_by(models.PriceBar.event_time)
    )
    db_bars = session.execute(
        stmt
    ).scalars()

    return db_price_bars_to_engine_bars(list(db_bars))


def db_price_bars_to_engine_bars(db_bars) -> list[EnginePriceBar]:
    latest_by_time = {}
    for bar in db_bars:
        latest_by_time.setdefault(bar.event_time, bar)
    return [
        EnginePriceBar(
            security_id=bar.security_id,
            event_time=bar.event_time,
            ingestion_time=bar.ingestion_time,
            timestamp_available=bar.timestamp_available,
            close=float(bar.close),
            adjusted_close=float(bar.adjusted_close),
            volume=bar.volume,
            currency=bar.currency,
        )
        for bar in latest_by_time.values()
    ]


def filter_engine_price_bars(
    *,
    bars: list[EnginePriceBar],
    security_id: uuid.UUID,
    window: TimeWindow,
    through: datetime | None = None,
    attribution_cutoff: datetime | None = None,
) -> list[EnginePriceBar]:
    end = through or window.end
    filtered = [
        bar
        for bar in bars
        if bar.security_id == security_id
        and window.start <= bar.event_time <= end
        and (attribution_cutoff is None or bar.timestamp_available <= attribution_cutoff)
    ]
    return sorted(filtered, key=lambda bar: bar.event_time)


def load_factor_returns(
    *,
    session,
    factor_name: str,
    window: TimeWindow,
    attribution_cutoff: datetime,
) -> dict[datetime, float]:
    rows = session.execute(
        select(models.FactorReturn)
        .where(models.FactorReturn.factor_name == factor_name)
        .where(models.FactorReturn.event_time >= window.start)
        .where(models.FactorReturn.event_time <= window.end)
        .where(models.FactorReturn.timestamp_available <= attribution_cutoff)
    ).scalars()
    return {row.event_time: float(row.return_bps) for row in rows}


def load_factor_returns_by_name(
    *,
    session,
    factor_names: tuple[str, ...],
    window: TimeWindow,
    attribution_cutoff: datetime,
) -> dict[str, dict[datetime, float]]:
    return {
        factor_name: load_factor_returns(
            session=session,
            factor_name=factor_name,
            window=window,
            attribution_cutoff=attribution_cutoff,
        )
        for factor_name in factor_names
    }


def factor_returns_for_window(
    *,
    session,
    preloaded_factor_returns_by_name: dict[str, dict[datetime, float]] | None,
    factor_names: tuple[str, ...],
    window: TimeWindow,
    attribution_cutoff: datetime,
) -> dict[str, dict[datetime, float]]:
    if preloaded_factor_returns_by_name is None:
        return load_factor_returns_by_name(
            session=session,
            factor_names=factor_names,
            window=window,
            attribution_cutoff=attribution_cutoff,
        )
    return {
        factor_name: series_for_window(
            series=preloaded_factor_returns_by_name.get(factor_name, {}),
            window=window,
        )
        for factor_name in factor_names
    }


def series_for_window(*, series: dict[datetime, float], window: TimeWindow) -> dict[datetime, float]:
    return {
        event_time: value
        for event_time, value in series.items()
        if window.start <= event_time <= window.end
    }


def persist_attribution_result(
    *,
    session,
    result,
    factor_basket_version: str = "none",
    cadence: str = "daily",
) -> models.AttributionRun:
    if cadence not in {"daily", "weekly", "monthly"}:
        raise ValueError(f"unsupported attribution cadence {cadence}")
    run = session.execute(
        select(models.AttributionRun)
        .where(models.AttributionRun.security_id == result.security_id)
        .where(models.AttributionRun.window_start == result.window.start)
        .where(models.AttributionRun.window_end == result.window.end)
        .where(models.AttributionRun.model_version == result.model_version)
        .where(models.AttributionRun.factor_basket_version == factor_basket_version)
        .where(models.AttributionRun.cadence == cadence)
    ).scalar_one_or_none()

    if run is None:
        run = models.AttributionRun(
            attribution_run_id=uuid.uuid4(),
            security_id=result.security_id,
            window_start=result.window.start,
            window_end=result.window.end,
            attribution_cutoff=result.attribution_cutoff,
            observed_return_bps=result.observed_return_bps,
            unexplained_residual_bps=result.unexplained_residual_bps,
            model_version=result.model_version,
            data_version="local-dev",
            factor_basket_version=factor_basket_version,
            cadence=cadence,
            created_at=datetime.now(timezone.utc),
        )
        session.add(run)
    else:
        run.attribution_cutoff = result.attribution_cutoff
        run.observed_return_bps = result.observed_return_bps
        run.unexplained_residual_bps = result.unexplained_residual_bps
        run.data_version = "local-dev"
        run.created_at = datetime.now(timezone.utc)
        session.execute(
            delete(models.AttributionContribution).where(
                models.AttributionContribution.attribution_run_id == run.attribution_run_id
            )
        )
    session.flush()

    for contribution in result.contributions:
        session.add(
            models.AttributionContribution(
                attribution_contribution_id=uuid.uuid4(),
                attribution_run_id=run.attribution_run_id,
                driver=contribution.driver.value,
                name=contribution.name,
                contribution_bps=contribution.contribution_bps,
                share_of_move=contribution.share_of_move,
                confidence=contribution.confidence.value,
                evidence=contribution.evidence,
                contribution_stage=contribution.contribution_stage.value,
                evidence_payload=contribution.evidence_payload,
            )
        )
    session.flush()
    return run


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()
