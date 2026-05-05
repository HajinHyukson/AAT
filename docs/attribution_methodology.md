# Attribution Methodology

## Current State First

The implemented model is an expanded MVP scaffold. It computes observed return first, applies point-in-time visible factor contributions, and always reports the remaining move as `unexplained_residual`.

Current production-style contribution sources:

- French five-factor baseline: `Mkt-RF`, `SMB`, `HML`, `RMW`, and `CMA`.
- Expanded MVP systematic factors when data is available: sector/industry proxy factors, custom peer baskets, and transformed FRED macro factors.

Current evidence-only sources:

- Return-based style descriptors such as momentum, short-term reversal, realized volatility, and liquidity.
- EDGAR event taxonomy/evidence rows.

Evidence-only rows must not reduce residual. Event contribution remains disabled until event-study calibration exists. Return-based style descriptors remain evidence-only unless a calibrated production factor return is added.

Latest local verification:

```powershell
python -m pytest tests/unit tests/lookahead_audit
```

Result: 50 tests passed on 2026-05-04.

## MVP Baseline

The MVP computes observed return first, then allocates known factor contributions, then reports the remainder as `unexplained_residual`.

The implemented factor model estimates French five-factor sensitivities using prior stock returns and Kenneth French daily factor returns:

```text
factor_contribution_bps = estimated_beta * attribution_window_factor_return_bps
```

The current production baseline factors are `Mkt-RF`, `SMB`, `HML`, `RMW`, and `CMA`. `Mkt-RF` is reported as market; the other four are reported as style factors.

The expanded MVP mode can add additional point-in-time visible rows after the French baseline:

- Sector and industry factors from ETF/index proxy returns stored in `factor_return`.
- Custom peer-basket factors from curated `peer_basket` and `peer_basket_member` rows.
- Return-based style descriptors as evidence-only rows and `security_factor_exposure` records.
- Macro factors from transformed `macro_series` observations, gated by curated company exposures when available.
- EDGAR event taxonomy rows as evidence-only event rows.

Event evidence and style descriptors do not allocate production return contribution unless a calibrated production factor return exists.

The reconciliation identity is:

```text
observed_return_bps = sum(non_residual_contribution_bps) + unexplained_residual_bps
```

The engine must reconcile within one basis point.

Attribution runs are persisted with a cadence:

- `daily`: adjacent trading-day close-to-close windows.
- `weekly`: first-to-last trading date within each ISO week.
- `monthly`: first-to-last trading date within each calendar month.

Idempotency is scoped by `(security_id, window_start, window_end, model_version, factor_basket_version, cadence)`.

## Point-In-Time Rule

Any row used by an attribution run must satisfy:

```text
timestamp_available <= attribution_cutoff
```

Rows available after the cutoff are excluded, even if their `event_time` is inside the return window.

## Confidence

The MVP exposes the project-standard five-level confidence scale:

- High
- Medium-High
- Medium
- Low-Medium
- Low

Later versions will map confidence to evidence coverage, model stability, calibration quality, and residual size.

## Event Features

The MVP event layer converts EDGAR filing metadata into structured feature rows. It does not make causal claims and does not assign return contribution. It outputs relevance, novelty, sentiment, magnitude, source credibility, exposure match, surprise, and an evidence span.

The expanded MVP also classifies visible EDGAR events into `event_taxonomy` rows. These rows can appear in the driver table as evidence-only `event` rows with zero contribution. This keeps the residual honest until event-study calibration exists.

## Deterministic Narrative

The MVP narrative is deterministic and constrained. It is generated only from structured attribution outputs, names the observed move, lists the largest modeled drivers when available, reports residual size, and notes visible event evidence without assigning causal contribution.
