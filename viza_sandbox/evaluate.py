"""Quantile backtest of a wide scores frame (execution: signal at D, earns D+1 -> D+2 close)."""

from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field
from scipy.stats import spearmanr

from viza_sandbox.trading_calendar import trading_day_mask

EXECUTION_CONVENTION = {"signal_lag_days": 1, "transaction_cost": 0.0, "benchmark": None}
# Disclosures for the run header: what the bucket mean and the close-to-close return model.
WEIGHTING_BASIS = (
    "equal weight within each quantile, re-equalized every trading day at zero cost "
    "between rebalances"
)
RETURN_BASIS = "price return on close; dividends not included"
# A held security-day whose close moved by this factor or more (up or down) in one day is
# counted and disclosed. It is never removed from the returns.
EXTREME_MOVE_RATIO = 10.0
_EXECUTION_DELAY = 2  # weights set at D earn r_t for t >= D + 2 trading days


class EvaluationError(ValueError):
    pass


class BacktestSettings(BaseModel):
    quantiles: int = Field(ge=2, le=20)
    rebalance: Literal["daily", "weekly", "monthly"]
    weighting: Literal["equal"] = "equal"
    top_n: int = Field(default=20, ge=1)


class ScoresEvaluation(BaseModel):
    quantile_daily_returns: dict[str, dict[str, float | None]]
    equity_curves: dict[str, dict[str, float]]
    long_short_daily: dict[str, float | None]
    rank_stability: dict[str, float | None]
    top_bottom: dict[str, dict[str, list[str]]]
    rebalance_dates: list[str]
    execution: dict
    settings: BacktestSettings
    warnings: list[str]
    securities_scored: int
    dates_scored: int
    extreme_moves: dict
    scores_outside_universe: int = 0
    non_trading_dates: list[str] = []


def rebalance_dates(index: pd.DatetimeIndex, rebalance: str) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(index).sort_values()
    if rebalance == "daily":
        return index
    if rebalance == "weekly":
        iso = index.isocalendar()
        key = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    elif rebalance == "monthly":
        key = (index.year * 100 + index.month).to_numpy()
    else:
        raise ValueError(f"Unknown rebalance: {rebalance}")
    last = pd.Series(index, index=index).groupby(key).max()
    return pd.DatetimeIndex(last.to_numpy())


def _iso(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d")


def _num(value: float) -> float | None:
    return None if pd.isna(value) else float(value)


def evaluate_scores(
    scores: pd.DataFrame,
    close: pd.DataFrame,
    settings: BacktestSettings,
    universe: pd.DataFrame | None = None,
) -> ScoresEvaluation:
    """Quantile backtest of ``scores``.

    ``universe`` (columns ``event_date``, ``security_id``), when given, is the membership list:
    a score dated D for a security that is not a member on D is not ranked, and is counted.
    Realized returns always come from ``close``, whatever a security's later membership.
    """
    close = close.sort_index()
    scores = scores.sort_index()
    warnings: list[str] = []

    # Dates on which only a few securities have a bar (holidays, stray weekend bars) are not
    # trading days: as rows they would erase every other security's return across them.
    trading = trading_day_mask(close)
    non_trading = [_iso(day) for day in close.index[~trading]]
    close = close[trading]
    if non_trading:
        warnings.append(
            f"{len(non_trading)} dates had bars for fewer than half the usual number of "
            f"securities and were treated as non-trading days: {', '.join(non_trading[:5])}"
        )

    dropped = [c for c in scores.columns if c not in close.columns]
    if dropped:
        warnings.append(
            f"Dropped {len(dropped)} scored securities not in the universe: "
            f"{', '.join(str(c) for c in dropped[:5])}"
        )
    kept = [c for c in scores.columns if c in close.columns]
    scores = scores.loc[scores.index.isin(close.index), kept]
    if scores.empty:
        raise EvaluationError("No scores fall inside the panel date range.")

    outside = 0
    if universe is not None:
        member = (
            universe.assign(member=True, event_date=pd.to_datetime(universe["event_date"]))
            .pivot(index="event_date", columns="security_id", values="member")
            .reindex(index=scores.index, columns=scores.columns)
            .eq(True)
        )
        outside = int((scores.notna() & ~member).to_numpy().sum())
        scores = scores.where(member)
        if outside:
            warnings.append(
                f"{outside} scores were for securities outside the universe on their date "
                "and were not ranked."
            )

    # Plain ratio: a missing close yields NaN returns for that day and the next, never a fill.
    returns = close / close.shift(1) - 1
    positions = {ts: i for i, ts in enumerate(close.index)}
    k = settings.quantiles
    labels = [f"q{i + 1}" for i in range(k)]

    # Effective rebalances: (position of D, bucket label per security, ranked ids low->high).
    effective: list[tuple[pd.Timestamp, pd.Series, list[str]]] = []
    for date in rebalance_dates(scores.index, settings.rebalance):
        row = scores.loc[date].dropna()
        row = row[close.loc[date, row.index].notna()]
        if row.empty:
            continue
        if len(row) < k:
            warnings.append(
                f"Skipped rebalance {_iso(date)}: {len(row)} scored securities for {k} quantiles"
            )
            continue
        rank = row.rank(method="first")
        bucket = pd.qcut(rank, k, labels=False)
        effective.append((date, bucket, list(rank.sort_values().index)))

    buckets_by_date: dict[str, dict[str, float]] = {lab: {} for lab in labels}
    extreme_days = 0
    extreme_securities: set[str] = set()
    for n, (date, bucket, _) in enumerate(effective):
        start = positions[date] + _EXECUTION_DELAY
        end = (
            positions[effective[n + 1][0]] + _EXECUTION_DELAY
            if n + 1 < len(effective)
            else len(close.index)
        )
        window = returns.iloc[start:end]
        if window.empty:
            continue
        held = window[bucket.index]
        extreme = (held >= EXTREME_MOVE_RATIO - 1.0) | (held <= 1.0 / EXTREME_MOVE_RATIO - 1.0)
        extreme_days += int(extreme.to_numpy().sum())
        extreme_securities.update(str(c) for c in extreme.columns[extreme.any(axis=0)])
        for q, lab in enumerate(labels):
            members = bucket.index[bucket == q]
            mean = window[members].mean(axis=1)  # skipna: absent closes never count as zero
            for ts, value in mean.items():
                buckets_by_date[lab][_iso(ts)] = _num(value)

    if extreme_days:
        warnings.append(
            f"{extreme_days} scored security-days across {len(extreme_securities)} securities "
            f"had a one-day close move of {EXTREME_MOVE_RATIO:g}x or more; quantile returns "
            "include them unclipped."
        )

    quantile_daily = buckets_by_date
    equity: dict[str, dict[str, float]] = {}
    for lab, series in quantile_daily.items():
        level, curve = 1.0, {}
        for day, value in series.items():
            if value is not None:
                level *= 1.0 + value
            curve[day] = level
        equity[lab] = curve

    top_label, bottom_label = labels[-1], labels[0]
    long_short = {
        day: (
            None
            if quantile_daily[top_label][day] is None or quantile_daily[bottom_label][day] is None
            else quantile_daily[top_label][day] - quantile_daily[bottom_label][day]
        )
        for day in quantile_daily[top_label]
    }

    rank_stability: dict[str, float | None] = {}
    top_bottom: dict[str, dict[str, list[str]]] = {}
    for n, (date, _, ordered) in enumerate(effective):
        top_bottom[_iso(date)] = {
            "top": ordered[::-1][: settings.top_n],
            "bottom": ordered[: settings.top_n],
        }
        if n == 0:
            continue
        pair = scores.loc[[effective[n - 1][0], date]].dropna(axis=1)
        value = None
        if pair.shape[1] >= 3 and (pair.nunique(axis=1) > 1).all():
            corr = spearmanr(pair.iloc[0], pair.iloc[1]).statistic
            value = _num(corr)
        rank_stability[_iso(date)] = value

    return ScoresEvaluation(
        quantile_daily_returns=quantile_daily,
        equity_curves=equity,
        long_short_daily=long_short,
        rank_stability=rank_stability,
        top_bottom=top_bottom,
        rebalance_dates=[_iso(d) for d, _, _ in effective],
        execution=dict(EXECUTION_CONVENTION),
        settings=settings,
        warnings=warnings,
        securities_scored=int(scores.notna().any(axis=0).sum()),
        dates_scored=int(scores.notna().any(axis=1).sum()),
        scores_outside_universe=outside,
        non_trading_dates=non_trading,
        extreme_moves={
            "ratio": EXTREME_MOVE_RATIO,
            "security_days": extreme_days,
            "securities": len(extreme_securities),
        },
    )
