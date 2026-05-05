from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from engine.contracts import ConfidenceLevel, DriverType, PriceBar, TimeWindow
from engine.factors.baseline import build_factor_baseline_result
from engine.factors.peer_model import PeerWeight
from jobs.run_attribution import ActivePeerContext, build_active_peer_input, load_engine_price_bars, persist_attribution_result


class FakeSession:
    def __init__(self) -> None:
        self.items = []
        self.executed = []

    def execute(self, statement):
        self.executed.append(statement)
        class Result:
            def scalar_one_or_none(self):
                return None

        return Result()

    def add(self, item) -> None:
        self.items.append(item)

    def flush(self) -> None:
        return None


def test_persist_attribution_result_writes_run_and_contributions() -> None:
    security_id = uuid4()
    result = build_factor_baseline_result(
        security_id=security_id,
        window=TimeWindow(
            start=datetime(2026, 1, 2, tzinfo=timezone.utc),
            end=datetime(2026, 1, 9, tzinfo=timezone.utc),
        ),
        attribution_cutoff=datetime(2026, 1, 10, tzinfo=timezone.utc),
        observed_return_bps=100,
        factor_inputs=[],
    )
    session = FakeSession()

    run = persist_attribution_result(session=session, result=result)

    assert run.security_id == security_id
    assert run.cadence == "daily"
    contribution = session.items[-1]
    assert contribution.driver == DriverType.UNEXPLAINED_RESIDUAL.value
    assert contribution.confidence == ConfidenceLevel.LOW.value


def test_persist_attribution_result_replaces_existing_cadence_run() -> None:
    security_id = uuid4()
    existing_run = build_existing_run(security_id=security_id)
    result = build_factor_baseline_result(
        security_id=security_id,
        window=TimeWindow(
            start=datetime(2026, 1, 2, tzinfo=timezone.utc),
            end=datetime(2026, 1, 9, tzinfo=timezone.utc),
        ),
        attribution_cutoff=datetime(2026, 1, 10, tzinfo=timezone.utc),
        observed_return_bps=100,
        factor_inputs=[],
    )

    class ExistingSession(FakeSession):
        def execute(self, statement):
            self.executed.append(statement)

            class Result:
                def scalar_one_or_none(self_inner):
                    return existing_run

            if len(self.executed) == 1:
                return Result()
            return super().execute(statement)

    session = ExistingSession()
    run = persist_attribution_result(session=session, result=result, cadence="weekly")

    assert run is existing_run
    assert run.cadence == "weekly"
    assert run.observed_return_bps == 100
    assert any(item.__class__.__name__ == "AttributionContribution" for item in session.items)


def test_load_engine_price_bars_keeps_latest_visible_bar_per_date() -> None:
    security_id = uuid4()
    day_1 = datetime(2026, 4, 1, tzinfo=timezone.utc)
    day_2 = datetime(2026, 4, 2, tzinfo=timezone.utc)
    cutoff = datetime(2026, 5, 5, tzinfo=timezone.utc)
    bars = [
        build_price_bar(
            security_id=security_id,
            event_time=day_1,
            timestamp_available=datetime(2026, 5, 4, 18, tzinfo=timezone.utc),
            adjusted_close=185.0,
            source="mock_chart",
        ),
        build_price_bar(
            security_id=security_id,
            event_time=day_1,
            timestamp_available=datetime(2026, 5, 4, 22, tzinfo=timezone.utc),
            adjusted_close=255.63,
            source="faustcalc_fmp_snapshot",
        ),
        build_price_bar(
            security_id=security_id,
            event_time=day_2,
            timestamp_available=datetime(2026, 5, 4, 22, tzinfo=timezone.utc),
            adjusted_close=255.92,
            source="faustcalc_fmp_snapshot",
        ),
        build_price_bar(
            security_id=security_id,
            event_time=day_2,
            timestamp_available=datetime(2026, 5, 6, tzinfo=timezone.utc),
            adjusted_close=999.0,
            source="future_revision",
        ),
    ]
    session = PriceBarSession(bars)

    loaded = load_engine_price_bars(
        session=session,
        security_id=security_id,
        window=TimeWindow(start=day_1, end=day_2),
        attribution_cutoff=cutoff,
    )

    assert [(bar.event_time, bar.adjusted_close) for bar in loaded] == [
        (day_1, 255.63),
        (day_2, 255.92),
    ]


def test_build_active_peer_input_uses_preloaded_context_without_querying() -> None:
    security_id = uuid4()
    peer_id = uuid4()
    days = [datetime(2026, 1, day, tzinfo=timezone.utc) for day in range(1, 14)]
    target_bars = [
        PriceBar(
            security_id=security_id,
            event_time=day,
            ingestion_time=day,
            timestamp_available=day,
            close=100 + index,
            adjusted_close=100 + index,
            volume=None,
            currency="USD",
        )
        for index, day in enumerate(days)
    ]
    peer_returns = {day: 10.0 + index for index, day in enumerate(days[1:], start=1)}
    context = ActivePeerContext(
        target_security_id=security_id,
        basket_name="default_peer_basket",
        basket_version="test-v0",
        peer_weights=[
            PeerWeight(
                peer_security_id=peer_id,
                weight=1.0,
                active_from=days[0],
                active_to=None,
                timestamp_available=days[0],
            )
        ],
        peer_basket_returns=peer_returns,
    )

    class QueryFailSession:
        def execute(self, _statement):
            raise AssertionError("preloaded peer context should avoid DB queries")

    result = build_active_peer_input(
        session=QueryFailSession(),
        security_id=security_id,
        target_bars=target_bars,
        estimation_window=TimeWindow(start=days[0], end=days[11]),
        attribution_window=TimeWindow(start=days[11], end=days[12]),
        attribution_cutoff=days[12],
        preloaded_peer_context=context,
    )

    assert result is not None
    assert result.driver == DriverType.PEER
    assert result.evidence_payload["basket_version"] == "test-v0"


def build_existing_run(*, security_id):
    return type(
        "ExistingRun",
        (),
        {
            "attribution_run_id": uuid4(),
            "security_id": security_id,
            "window_start": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "window_end": datetime(2026, 1, 9, tzinfo=timezone.utc),
            "model_version": "factor-baseline-v0",
            "factor_basket_version": "mvp_expanded_v0",
            "cadence": "weekly",
            "attribution_cutoff": datetime(2026, 1, 10, tzinfo=timezone.utc),
            "observed_return_bps": 0,
            "unexplained_residual_bps": 0,
            "data_version": "local-dev",
            "created_at": datetime(2026, 1, 10, tzinfo=timezone.utc),
        },
    )()


def build_price_bar(*, security_id, event_time, timestamp_available, adjusted_close, source):
    return type(
        "PriceBarRow",
        (),
        {
            "security_id": security_id,
            "event_time": event_time,
            "ingestion_time": timestamp_available,
            "timestamp_available": timestamp_available,
            "close": adjusted_close,
            "adjusted_close": adjusted_close,
            "volume": None,
            "currency": "USD",
            "source": source,
        },
    )()


class PriceBarSession:
    def __init__(self, bars):
        self.bars = bars

    def execute(self, statement):
        class Result:
            def __init__(self, bars):
                self.bars = sorted(
                    [
                        bar
                        for bar in bars
                        if bar.timestamp_available <= datetime(2026, 5, 5, tzinfo=timezone.utc)
                    ],
                    key=lambda bar: (bar.event_time, -bar.timestamp_available.timestamp(), bar.source),
                )

            def scalars(self):
                return self.bars

        return Result(self.bars)
