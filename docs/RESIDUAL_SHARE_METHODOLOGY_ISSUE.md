# Residual Share Methodology Issue

## Summary

The current AAT attribution method can produce unexplained residual shares above 7,000% on many daily windows. This is usually not a 7,000% stock return or a direct arithmetic failure. It is a warning that the current residual-share display and expanded attribution methodology are unstable for small observed moves and overlapping factor models.

The core residual accounting is:

```text
observed_return_bps = ((end_adjusted_close / start_adjusted_close) - 1) * 10,000
explained_bps = sum(non_residual contribution_bps)
unexplained_residual_bps = observed_return_bps - explained_bps
share_of_move = contribution_bps / observed_return_bps
```

This means residual share can explode when `observed_return_bps` is close to zero.

Example:

```text
observed_return_bps = +1
explained_bps = -69
unexplained_residual_bps = +70
residual_share = 70 / 1 = 70x = 7,000%
```

The residual basis-point value may be ordinary, but the percentage is unstable because the denominator is tiny.

## Current Methodology Risk

The current residual is an accounting residual after modeled rows. It is not yet a clean idiosyncratic residual.

French five-factor rows are estimated jointly, but expanded MVP rows are currently layered on as separate beta relationships:

- sector and industry proxy factors
- peer basket factors
- transformed macro factors

These factors often overlap with each other. A sector ETF contains market exposure. A peer basket contains market and sector exposure. Macro factors can be strongly correlated with market and sector moves. Because these rows are not yet fully residualized or estimated in one hierarchical multivariate model, the same movement can be counted more than once.

That creates cases like:

```text
observed stock move = +5 bps
market/style contribution = -20 bps
sector contribution = -25 bps
peer contribution = -15 bps
macro contribution = -10 bps
residual = +75 bps
residual share = 1,500%
```

The accounting reconciles, but the explanation is not economically reliable.

## What Can Go Wrong

- Tiny observed moves make `share_of_move` mathematically unstable.
- Separate beta models can double count overlapping factor movement.
- Sector, peer, and macro factors are not yet residualized against earlier hierarchy layers.
- The model does not yet use one regularized multivariate regression for expanded factors.
- Low observation thresholds can admit noisy beta estimates.
- There are no production beta shrinkage, winsorization, or contribution caps.
- Collinear factors can create unstable or sign-flipping contributions.
- Daily single-stock attribution is naturally noisy.
- Event rows and return-style descriptors are evidence-only, so company-specific drivers do not reduce residual.

## Interpretation Guidance

Residual basis points should be treated as the primary accounting value. Residual share should be treated as a secondary diagnostic and should not be interpreted literally when the observed move is small.

A 7,000% residual share means:

```text
abs(unexplained_residual_bps) is 70x abs(observed_return_bps)
```

It does not mean the stock had a 7,000% unexplained return.

## Recommended Fixes

1. Show residual bps as the primary value.
2. Suppress or label residual share as unstable when `abs(observed_return_bps)` is below a threshold, for example 10 to 25 bps.
3. Avoid ranking or averaging raw `share_of_move` across windows without filtering tiny observed moves.
4. Add residual-share diagnostics:

```text
residual_share_is_stable = abs(observed_return_bps) >= threshold_bps
```

5. Residualize sector, peer, and macro factors against prior hierarchy layers before estimating contribution.
6. Consider replacing the expanded additive stack with one regularized multivariate model.
7. Add beta stability gates before a factor can reduce residual.
8. Track residual quality using basis-point error and weighted residual share, not raw average percentage share.

## Related Implementation Points

- Residual construction: `engine/factors/baseline.py`
- Observed return accounting: `engine/returns/accounting.py`
- French five-factor model: `engine/factors/french_model.py`
- Sector, peer, and macro expanded rows: `engine/factors/sector_model.py`, `engine/factors/peer_model.py`, `engine/factors/macro_model.py`
- Dashboard share display: `dashboard/components/driver-table.tsx`

