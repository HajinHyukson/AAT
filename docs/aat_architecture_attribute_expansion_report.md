# AAT Architecture and Attribute Expansion Report

Last updated: May 4, 2026

## Executive Summary

AAT is an alpha-stage single-stock attribution engine. Its current architecture is correctly built around a conservative attribution contract: compute the observed return, allocate point-in-time visible factor contributions, and reconcile everything to an explicit `unexplained_residual`. This is the right foundation for a research-grade product because it avoids the common failure mode of forcing a convenient narrative onto every stock move.

The current implemented factor model uses the Kenneth French five-factor framework:

- `Mkt-RF`
- `SMB`
- `HML`
- `RMW`
- `CMA`

That is a credible academic baseline, but it is too narrow for institutional single-stock attribution. A realistic analyst-facing model needs sector, industry, peer, macro, liquidity, positioning, and event attributes. AAT does not need thousands of risk factors like Bloomberg MAC3, but it should expand from 5 factors toward roughly 40-80 high-signal attributes before it will feel robust to an analyst or PM.

The recommended next architecture target is:

```text
Observed single-stock return
  = market contribution
  + sector contribution
  + industry contribution
  + peer-basket contribution
  + style contribution
  + macro contribution
  + positioning/liquidity contribution
  + event contribution
  + unexplained residual
```

## Current Product Intent

AAT is designed to answer five questions for one stock over one attribution window:

1. What drove the move?
2. How much did each driver contribute, in basis points and share of move?
3. What evidence supports each attribution?
4. How confident should the user be?
5. Should the company's structural exposure profile be reviewed or updated?

The project is explicitly not a trading system, not a black-box news explainer, and not a Bloomberg or FactSet replacement. Its moat is disciplined attribution: deterministic accounting first, statistical attribution second, structured event intelligence third, constrained narrative last.

## Current Architecture

### Layer 1: Deterministic Return Accounting

The return layer computes adjusted close-to-close returns from point-in-time visible price bars. This is the accounting foundation of the entire system.

Important properties:

- Uses adjusted close.
- Filters records by `timestamp_available <= attribution_cutoff`.
- Produces observed return in basis points.
- Does not make causal claims.

Implemented data model support:

- `price_bar`
- `security`
- `security_ticker_history`
- `company`

### Layer 2: Statistical Factor Attribution

The current statistical layer estimates factor sensitivities using prior stock returns and daily Kenneth French factor returns. Contributions are computed as:

```text
factor_contribution_bps = estimated_beta * attribution_window_factor_return_bps
```

Implemented factors:

| Current Attribute | Driver Type | Current Role |
|---|---|---|
| `Mkt-RF` | Market | Broad equity market contribution |
| `SMB` | Style | Size contribution |
| `HML` | Style | Value contribution |
| `RMW` | Style | Profitability contribution |
| `CMA` | Style | Investment contribution |

The model currently lowers confidence when factor multicollinearity appears through a high condition number.

Implemented code support:

- `engine/factors/french_model.py`
- `engine/factors/baseline.py`
- `engine/contracts.py`
- `factor_return`
- `attribution_run`
- `attribution_contribution`

### Layer 3: Event Intelligence

The event layer currently converts SEC EDGAR filing metadata into structured event features. It does not assign causal return contribution yet, which is the correct MVP behavior.

Implemented event features:

| Feature | Meaning |
|---|---|
| `relevance` | How relevant the event is likely to be for attribution |
| `novelty` | How new or unusual the event is |
| `sentiment` | Directional tone, currently neutral for EDGAR metadata |
| `magnitude` | Estimated materiality |
| `source_credibility` | Source quality |
| `exposure_match` | Match to known company exposure |
| `surprise` | Directional surprise, currently neutral for EDGAR metadata |
| `evidence_span` | Structured evidence reference |

Implemented event types are based mostly on filing forms, including `8-K`, `10-K`, `10-Q`, `13G`, `Form 4`, and `144`.

Implemented code support:

- `engine/events/features.py`
- `jobs/generate_event_features.py`
- `event`
- `event_feature`

### Layer 4: Exposure Update Decisions

AAT has a conservative exposure update policy. Daily attribution can suggest that a structural exposure deserves human review, but the MVP does not automatically mutate company exposure profiles.

Implemented decisions:

| Decision | Meaning |
|---|---|
| `candidate_review` | Material or persistent evidence suggests analyst review |
| `no_update` | Evidence is not strong enough to review or update exposure |

Implemented code support:

- `engine/exposures/update_policy.py`
- `jobs/evaluate_exposure_updates.py`
- `company_exposure`
- `exposure_update_decision`

### API and Dashboard

The backend exposes attribution data through FastAPI, and the dashboard displays run history, driver tables, and exposure update decisions.

Implemented support:

- `api/main.py`
- `api/schemas.py`
- `dashboard/app/page.tsx`
- `dashboard/components/driver-table.tsx`
- `dashboard/components/run-history.tsx`
- `dashboard/components/exposure-decisions.tsx`

### Data Adapters

Current adapters include:

| Adapter | Purpose | License Position |
|---|---|---|
| FMP | Historical daily prices | Requires `FMP_API_KEY`; production license must be confirmed |
| Kenneth French | Daily five-factor returns | Public data |
| SEC EDGAR | Filing metadata | Public official source |

The adapter config has fail-closed licensing checks, which is important for production credibility.

### Point-In-Time Controls

AAT has the right invariant for attribution research:

```text
timestamp_available <= attribution_cutoff
```

Every model-visible row must carry:

- `event_time`
- `ingestion_time`
- `timestamp_available`

This is a major design strength. It should remain non-negotiable as more attributes are added.

## Current State Assessment

### What Is Strong

- The attribution result reconciles to observed return within one basis point.
- The residual is explicit and cannot disappear.
- Public contracts are typed with Pydantic.
- The database schema already anticipates macro series, event features, company exposures, and attribution contributions.
- Data licensing is treated as an engineering constraint, not an afterthought.
- The event layer is structured and evidence-oriented rather than an unconstrained LLM explanation layer.
- Exposure updates are conservative and human-review oriented.

### What Is Still Thin

- The active factor model only covers five French factors.
- There is no implemented sector attribution yet.
- There is no implemented industry or subindustry attribution yet.
- There is no implemented custom peer-basket attribution yet.
- Macro data infrastructure exists in the schema, but macro factor attribution is not yet implemented.
- Positioning and options drivers are not implemented.
- Event features are currently heuristic metadata scores, not event-study calibrated return contributions.
- There is no analyst feedback persistence yet.
- The entity resolver still needs hardening for ticker changes, share classes, and M&A.

## Recommended Attribute Expansion

The goal should not be maximum factor count. The goal should be a defensible set of attributes that analysts recognize, that can be computed point-in-time, and that reduce residuals without overfitting.

Recommended sequence:

1. Add sector, industry, and peer-basket factors.
2. Add missing style factors such as momentum, volatility, liquidity, leverage, and growth.
3. Add macro factors through `macro_series`.
4. Add positioning and options attributes after data licensing is settled.
5. Upgrade event attributes from filing-form heuristics to event-specific surprise and materiality measures.

## Priority 1 Attributes: Core Market Structure

These should be added first because they are the most important gap between AAT's current MVP and a real single-stock attribution tool.

| Attribute | Driver Type | Suggested Proxy | Why It Needs To Be Added |
|---|---|---|---|
| Broad market | Market | `SPY`, `IVV`, or `Mkt-RF` | Already implemented through French `Mkt-RF`; keep it as the first attribution layer. |
| Sector return | Sector | Sector ETF such as `XLK`, `XLF`, `XLE`, `XLV` | Single stocks often move with sector flows that are not captured by broad market beta. |
| Industry return | Sector | Industry ETF such as `SMH`, `KBE`, `XBI`, `IYT` | More precise than sector; many moves are industry-specific rather than sector-wide. |
| Subindustry basket | Sector | Curated subindustry index | Helps avoid over-attributing to company-specific events when the whole niche moved. |
| Custom peer basket | Peer | Weighted basket of 5-15 direct peers | Essential for single-stock attribution; PMs naturally ask whether peers moved too. |
| Peer residual spread | Peer | Target return minus peer-basket-adjusted return | Separates company-specific move from peer sympathy move. |
| Peer event read-through | Peer/Event | Peer event score weighted by exposure similarity | Captures cases where another company reports news that reprices the target. |

## Priority 2 Attributes: Additional Style Factors

French five-factor coverage is useful, but institutional equity risk models usually include more style descriptors.

| Attribute | Driver Type | Suggested Proxy | Why It Needs To Be Added |
|---|---|---|---|
| Momentum | Style | 12-month return excluding most recent month | One of the most persistent equity style effects and missing from French five-factor. |
| Short-term reversal | Style | 1-week or 1-month prior return | Helps explain bounce/fade behavior after sharp moves. |
| Volatility | Style | 60-day or 252-day realized volatility | High-vol names react differently in risk-on/risk-off regimes. |
| Market beta descriptor | Style | Rolling beta to market | Useful as a stable descriptor distinct from daily market contribution. |
| Liquidity | Style | Dollar volume, bid-ask spread where available | Liquidity shocks can explain outsized single-name moves. |
| Size | Style | Log market cap | More interpretable and company-specific than `SMB` alone. |
| Value / earnings yield | Style | Forward or trailing earnings yield | More intuitive to analysts than `HML` alone. |
| Growth | Style | Revenue growth, EPS growth, or sales CAGR | Needed for growth-vs-value attribution, especially in tech and consumer. |
| Quality | Style | ROE, gross margin, accruals, earnings stability | Complements `RMW` with analyst-friendly descriptors. |
| Leverage | Style/Macro | Debt/EBITDA, debt/assets, interest coverage | Rate and credit spread moves affect levered companies differently. |
| Dividend yield | Style | Dividend yield | Helps explain defensive and income-stock moves. |
| Investment intensity | Style | Capex/sales or asset growth | Gives a company-level version of the `CMA` concept. |

## Priority 3 Attributes: Macro Factors

The database already has `macro_series`, so this category fits the current architecture. Macro factors should be gated by company exposure profiles. For example, WTI should matter for energy and airlines, but not every software stock.

| Attribute | Driver Type | Suggested Proxy | Why It Needs To Be Added |
|---|---|---|---|
| 2Y Treasury yield change | Macro | FRED Treasury 2-year yield | Captures Fed policy and front-end rate sensitivity. |
| 10Y Treasury yield change | Macro | FRED Treasury 10-year yield | Captures valuation-duration sensitivity, especially for growth equities. |
| 2s10s curve change | Macro | 10Y minus 2Y yield | Important for banks, cyclicals, recession pricing, and net-interest-margin narratives. |
| Fed funds expectations | Macro | Fed funds futures or SOFR futures | Useful when equities move on policy expectation changes rather than realized yields. |
| Dollar index | Macro | DXY or broad dollar index | Multinationals, commodities, exporters, and ADRs can have material FX sensitivity. |
| WTI crude | Macro | WTI spot or front-month futures | Needed for energy, airlines, chemicals, transports, and inflation-sensitive names. |
| Natural gas | Macro | Henry Hub natural gas | Important for utilities, chemicals, LNG, energy producers, and some industrials. |
| Gold | Macro | Gold spot or futures | Useful for miners and risk-off attribution. |
| Copper | Macro | Copper spot or futures | Industrial cycle and China demand proxy. |
| High-yield credit spread | Macro | ICE BofA HY OAS | Captures risk appetite and financing stress. |
| Investment-grade credit spread | Macro | ICE BofA IG OAS | Useful for large-cap balance-sheet and credit-condition sensitivity. |
| VIX change | Macro | CBOE VIX | Captures volatility regime and risk-off shocks. |
| Inflation expectations | Macro | 5Y breakeven or 5Y5Y forward | Relevant for staples, utilities, real assets, and duration-sensitive sectors. |
| Mortgage rate | Macro | 30-year mortgage rate | Important for homebuilders, housing suppliers, banks, and consumer finance. |
| Crypto factor | Macro/Peer | Bitcoin or crypto equity basket | Needed for crypto-linked equities and some fintech names. |

## Priority 4 Attributes: Positioning, Options, and Flow

These are powerful but require more careful licensing and interpretation. They should probably be v2 rather than immediate MVP work.

| Attribute | Driver Type | Suggested Proxy | Why It Needs To Be Added |
|---|---|---|---|
| Short interest | Positioning | FINRA or exchange short-interest data | Explains squeeze risk and asymmetric reactions to positive news. |
| Days to cover | Positioning | Short interest divided by average daily volume | More useful than raw short interest for squeeze mechanics. |
| Borrow cost | Positioning | Securities lending data | High borrow cost can indicate crowded shorts or special situations. |
| Options implied volatility | Positioning | ATM IV or vendor IV surface | Explains repricing around earnings, litigation, FDA, and macro events. |
| IV change | Positioning | Daily change in ATM IV | Separates equity price move from uncertainty repricing. |
| Put-call skew | Positioning | 25-delta put IV minus call IV | Captures downside-demand and hedging pressure. |
| Options volume/open interest | Positioning | OCC/OPRA or vendor feed | Useful for event-driven and retail-heavy names. |
| Dealer gamma exposure | Positioning | Estimated from options open interest | Can explain pinning, squeezes, and nonlinear intraday behavior. |
| ETF flow exposure | Positioning | ETF ownership and ETF flow data | Single names can move because sector/theme ETFs receive flows. |

## Priority 5 Attributes: Event-Specific Drivers

The current event layer has general scoring fields. It should next add explicit event categories and event-specific surprise measures.

| Attribute | Driver Type | Suggested Proxy | Why It Needs To Be Added |
|---|---|---|---|
| Earnings EPS surprise | Event | Reported EPS vs consensus | Core single-stock driver. |
| Revenue surprise | Event | Reported revenue vs consensus | Often more important than EPS quality. |
| Gross margin surprise | Event | Actual margin vs consensus/prior | Explains quality of revenue and operating leverage. |
| Operating margin surprise | Event | Actual margin vs consensus/prior | Important for software, industrials, consumer, and semis. |
| Guidance raise/cut | Event | Company guidance vs consensus | Often the dominant earnings-day driver. |
| Estimate revision | Event | Consensus EPS/revenue estimate change | Explains multi-day post-event drift and analyst reaction. |
| Price target revision | Event | Change in sell-side target price | Useful evidence, though lower purity than estimate revisions. |
| Rating change | Event | Upgrade/downgrade/initiation | Can matter, especially when unexpected or from a high-credibility analyst. |
| Management change | Event | CEO/CFO/board change | Can change perceived execution risk. |
| M&A announcement | Event | Deal announcement terms | Acquirer and target returns have different attribution logic. |
| Buyback announcement | Event | Authorization size as percent of market cap | Capital return can explain positive residuals. |
| Dividend change | Event | Dividend raise/cut/suspension | Important for income and defensive equities. |
| Insider activity | Event | Form 4 buys/sells, 10b5-1 context | Useful when filtered by size, role, and novelty. |
| Activist filing | Event | 13D/G ownership and activist identity | Explains governance or strategic optionality repricing. |
| Regulatory/legal event | Event | Lawsuit, settlement, agency action | Crucial for healthcare, financials, big tech, energy, and industrials. |
| Product launch | Event | Product announcement or launch date | Important for tech, consumer, autos, and healthcare. |
| FDA/clinical event | Event | Trial result, PDUFA, approval, CRL | Essential for biotech and pharma attribution. |
| Contract win/loss | Event | Announced contract value/duration | Important for defense, industrials, SaaS, and infrastructure. |
| Cyber/security incident | Event | Breach announcement and severity | Increasingly material for software, finance, and consumer firms. |
| Accounting/restatement | Event | Restatement, auditor change, controls issue | High-impact credibility and risk-premium driver. |

## Priority 6 Attributes: Company Exposure Profile

Company exposures should not be treated as daily return drivers by themselves. They should be used as weights or gates that determine which macro, peer, sector, and event factors are relevant.

| Attribute | Role | Why It Needs To Be Added |
|---|---|---|
| Geographic revenue exposure | Factor gating | Determines sensitivity to USD, China, Europe, emerging markets, and tariffs. |
| Segment revenue exposure | Factor gating | Maps company business lines to industry and commodity drivers. |
| Customer concentration | Event/materiality gating | One customer event can matter enormously for a supplier. |
| Supplier concentration | Event/materiality gating | Supply disruptions can drive stock-specific moves. |
| Commodity input exposure | Macro gating | Separates commodity producers from commodity consumers. |
| Interest-rate exposure | Macro gating | Banks, insurers, REITs, utilities, and growth companies have different rate channels. |
| Credit exposure | Macro gating | Levered companies and financials should react more to credit stress. |
| Regulatory exposure | Event gating | Prevents regulatory events from being over- or underweighted. |
| Product-cycle exposure | Event gating | Important for semis, hardware, autos, gaming, and pharma. |
| Foreign-exchange exposure | Macro gating | Helps decide whether dollar moves should receive attribution weight. |

## Detailed Calculation And Application Methodologies For Priority 1-6 Attributes

This section replaces the high-level interpretation notes with implementation-ready calculation methodology. It is written as a pre-development contract for AAT: each attribute must have a source, timestamp policy, transformation, exposure estimate or gate, contribution rule, evidence payload, and validation rule before it can move from research to production.

### Common Calculation Contract For All Attributes

#### Attribution accounting baseline

Every attribution run starts with deterministic adjusted close-to-close accounting:

```text
observed_return_bps = 10000 * (adjusted_close_end / adjusted_close_start - 1)
```

All factor and event rows must reconcile to observed return:

```text
observed_return_bps
  = sum(production_contribution_bps)
  + unexplained_residual_bps
```

The production reconciliation tolerance remains one basis point.

#### Point-in-time eligibility

A row is model-visible only when:

```text
timestamp_available <= attribution_cutoff
```

For every new attribute, store:

```text
event_time
source_publication_time
ingestion_time
timestamp_available
source_name
source_license_status
data_version
model_version
factor_basket_version when applicable
```

If the exact source publication timestamp is unknown, use a conservative availability timestamp, normally the next trading session open, and downgrade confidence.

#### Factor-backed contribution formula

For market, sector, industry, peer, style, macro, positioning, and flow factors, the default contribution formula is:

```text
contribution_bps = exposure_beta * factor_move
```

Where `factor_move` can be a return, a spread change, an index-point change, or a standardized style factor return. Unit examples:

```text
stock bps per 1 bp Treasury yield change
stock bps per 1 VIX point change
stock bps per 100 bps commodity return
stock bps per one z-score style factor return
```

#### Exposure estimation standard

Estimate exposures using only observations available before the attribution window begins:

```text
stock_return_t = alpha + beta_1 * factor_1_t + ... + beta_k * factor_k_t + error_t
```

Minimum recommended settings:

```text
lookback_default = 252 trading days
lookback_minimum_production = 126 trading days
lookback_minimum_shadow = 63 trading days
winsorization = 1st/99th percentile unless factor-specific rule overrides
regression = OLS with intercept; robust or ridge option when diagnostics require
```

Store `beta`, `standard_error`, `t_stat`, `r_squared`, `n_obs`, `lookback_days`, `estimation_start`, `estimation_end`, and `estimation_timestamp_available` in `security_factor_exposure`.

#### Hierarchical residualization standard

To reduce double counting, systematic factors should be applied in this order:

```text
1. Market
2. Sector
3. Industry
4. Subindustry
5. Peer basket
6. Style
7. Macro
8. Positioning/liquidity/flow
9. Event
10. Unexplained residual
```

When a factor overlaps with an earlier layer, residualize it against earlier layers:

```text
candidate_factor_t = a + b1 * prior_factor_1_t + ... + bn * prior_factor_n_t + residualized_candidate_factor_t
```

Use `residualized_candidate_factor_t` for beta estimation and contribution unless the selected model uses a single multivariate regression that already includes earlier layers.

#### Event contribution standard

Event rows must not absorb systematic movement that should have been explained by market, sector, peer, style, macro, or positioning factors. The event layer works from the post-systematic residual:

```text
residual_after_systematic_bps
  = observed_return_bps - sum(non_event_production_contribution_bps)
```

Before event-study calibration, event attributes are evidence-only. After calibration, event rows can allocate residual using:

```text
raw_event_bps = calibrated_expected_abnormal_return_bps(event_type, sector, size_bucket, surprise_bucket)
weighted_event_bps = raw_event_bps * event_strength * exposure_match
production_event_contribution_bps = residual_allocator(weighted_event_bps, residual_after_systematic_bps)
```

Recommended residual allocator for first production version:

```text
if sign(weighted_event_bps) == sign(residual_after_systematic_bps):
    event_contribution_bps = sign(residual_after_systematic_bps) * min(abs(weighted_event_bps), abs(residual_after_systematic_bps))
else:
    event_contribution_bps = 0 or shadow-only
```

This prevents unsupported event rows from increasing the unexplained residual in the opposite direction.

#### Company exposure standard

Priority 6 attributes are not daily contribution rows. They are gates, weights, priors, and review triggers:

```text
eligible_factor = exposure_gate_weight >= configured_threshold
adjusted_factor_confidence = base_confidence * exposure_gate_weight * source_quality_weight
```

If regression evidence is strong but a structural exposure gate is missing, AAT may show the factor as shadow contribution with a confidence penalty and a `missing_exposure_profile` flag.

#### Confidence scoring baseline

Start every attribute at a numeric score of 1.00 and subtract penalties:

```text
score = 1.00
score -= sparse_data_penalty
score -= stale_data_penalty
score -= source_quality_penalty
score -= proxy_mismatch_penalty
score -= unstable_beta_penalty
score -= collinearity_penalty
score -= exposure_mismatch_penalty
score -= parser_or_mapping_penalty
```

Map numeric score to display confidence:

```text
score >= 0.85: High
0.70 - 0.84: Medium-High
0.55 - 0.69: Medium
0.40 - 0.54: Low-Medium
< 0.40: Low
```

#### Source reference map for development

These references should be turned into adapter-level configuration, not hard-coded logic:

| Source family | Development use | Notes |
|---|---|---|
| SEC EDGAR/data.sec.gov | Filings, submissions, XBRL company facts, Form 4, 13D/G, 8-K, 10-Q, 10-K | Public official source; use fair-access compliant headers and rate limits. |
| FRED/ALFRED | Treasury yields, spreads, VIX daily close, inflation, mortgage rates, commodity public series | Use real-time/vintage parameters when historical revision timing matters. |
| GICS/RBICS/industry classification vendors | Sector, industry, subindustry hierarchy | Production use requires license confirmation; MVP can use curated mappings. |
| FINRA/exchange short interest | Short interest and days to cover | Use publication timestamp, not settlement date, for model visibility. |
| OPRA/options vendors/OCC | Options quotes, trades, implied volatility, volume, open interest | Production options attribution requires licensed data and validated surface methodology. |
| Cboe VIX | Official VIX methodology/data source where licensed | FRED `VIXCLS` can support daily development use. |
| FDA/openFDA/ClinicalTrials.gov | FDA, clinical, product/regulatory healthcare events | Useful for evidence and healthcare event taxonomy. |

---

## Priority 1 Calculation Methodologies: Core Market Structure

Priority 1 attributes should become production candidates first because they directly address the largest systematic gaps in single-stock attribution. They should be calculated before style, macro, positioning, and event rows.

#### Broad market

- **Initial adoption stage:** Production; already covered by French `Mkt-RF`, with ETF/index proxy optional for analyst display.
- **Interpretation:** Measures the portion of the target stock return explained by broad equity-market movement before any sector, peer, style, macro, or event allocation.
- **Data sourcing:** Use Kenneth French `Mkt-RF` for continuity with the current model. Add SPY, IVV, or a licensed S&P 500 total-return index as an analyst-facing proxy once licensing is confirmed. Use adjusted prices from `price_bar` and risk-free rate from French factors or Treasury bill series when calculating excess returns.
- **Calculation methodology:**

```text
observed_return_bps = 10000 * (adj_close_end / adj_close_start - 1)

market_factor_move_bps = sum(daily_Mkt_RF_bps over attribution window)
  or
market_factor_move_bps = 10000 * (market_proxy_adj_close_end / market_proxy_adj_close_start - 1)

Estimate beta on pre-window data only:
stock_excess_return_t = alpha + beta_market * market_excess_return_t + error_t

market_contribution_bps = beta_market * market_factor_move_bps
```

- **Application inside AAT:** Run first in `engine/attribution/hierarchy.py`. Store beta and contribution as the first systematic row. Downstream sector, industry, peer, style, macro, positioning, and event calculations should use either residualized factors or a multivariate design that keeps this market component from being counted again.
- **Evidence payload:** `driver_type=market`, `factor_id`, `proxy_symbol`, `beta_market`, `beta_window_days`, `market_factor_move_bps`, `r_squared`, `n_obs`, `timestamp_available`.
- **Confidence and validation rules:** Require at least 126 usable daily observations for production, 63 for shadow. Downgrade if beta standard error is high, beta changes sign across 63/126/252-day windows, proxy data is stale, or reconciliation error exceeds 1 bp.


#### Sector return

- **Initial adoption stage:** Shadow, then production after classification and proxy versioning are stable.
- **Interpretation:** Captures movement shared by companies in the same broad economic sector that is not already explained by the broad market.
- **Data sourcing:** Use licensed GICS, RBICS, FactSet, Bloomberg, or another production-approved classification source. For MVP, use analyst-curated `sector_classification_history`. Use sector ETF/index proxies such as XLK, XLF, XLE, XLV, XLI, XLP, XLY, XLU, XLB, XLRE, or licensed sector total-return indices.
- **Calculation methodology:**

```text
sector_proxy_return_bps = 10000 * (sector_proxy_adj_close_end / sector_proxy_adj_close_start - 1)

Residualize sector proxy against market using pre-window data:
sector_proxy_return_t = a + beta_sector_to_market * market_return_t + sector_residual_t

sector_factor_move_bps = sector_proxy_return_bps
                       - beta_sector_to_market * market_factor_move_bps

Estimate stock sensitivity on pre-window data:
stock_return_t = a + beta_market * market_return_t
                   + beta_sector * sector_residual_t + error_t

sector_contribution_bps = beta_sector * sector_factor_move_bps
```

- **Application inside AAT:** Apply immediately after broad market. Use the point-in-time sector classification active at `window_start` or `attribution_cutoff`, depending on AAT’s selected policy; do not use current classification for historical runs. If a stock changed sectors during the window, use the classification active at window start for a single-window run and flag the change in evidence.
- **Evidence payload:** `sector_code`, `sector_name`, `classification_source`, `classification_version`, `proxy_symbol`, `sector_factor_move_bps`, `beta_sector`, `classification_timestamp_available`.
- **Confidence and validation rules:** No production contribution if classification is missing, unversioned, or after cutoff. Downgrade when sector proxy is an ETF with concentrated holdings, when sector beta is unstable, or when sector residual is highly collinear with the market factor.


#### Industry return

- **Initial adoption stage:** Shadow, then production after industry proxy coverage is validated.
- **Interpretation:** Captures industry-specific movement, such as semiconductors, banks, biotech, airlines, trucking, homebuilders, or software, beyond the broader sector.
- **Data sourcing:** Use licensed industry classifications where available; otherwise use analyst-curated mappings. Use industry ETFs, licensed industry indices, or AAT-built constituent baskets excluding the target stock. Examples include SMH, KBE, XBI, IYT, ITB, XRT, IBB, KRE, and sector-specific custom baskets.
- **Calculation methodology:**

```text
industry_proxy_return_bps = 10000 * (industry_proxy_end / industry_proxy_start - 1)

Residualize industry against earlier hierarchy layers:
industry_proxy_return_t = a
                        + b_mkt * market_return_t
                        + b_sector * sector_residual_t
                        + industry_residual_t

industry_factor_move_bps = industry_proxy_return_bps
                         - b_mkt * market_factor_move_bps
                         - b_sector * sector_factor_move_bps

stock_return_t = a + beta_market * market_t
                   + beta_sector * sector_residual_t
                   + beta_industry * industry_residual_t + error_t

industry_contribution_bps = beta_industry * industry_factor_move_bps
```

- **Application inside AAT:** Apply after sector and before subindustry or peer baskets. Prefer an AAT-built industry basket when ETF proxy composition is materially different from the target’s economics. Exclude the target from baskets to avoid circular attribution.
- **Evidence payload:** `industry_code`, `industry_name`, `proxy_method=ETF|index|basket`, `basket_constituents`, `target_excluded=true`, `industry_factor_move_bps`, `beta_industry`.
- **Confidence and validation rules:** Require at least five liquid constituents for an AAT-built industry basket, or a licensed/index proxy. Downgrade when basket concentration exceeds 40% in one name, when the target is a large ETF constituent, or when fewer than 126 regression observations are available.


#### Subindustry basket

- **Initial adoption stage:** Shadow first; production only for subindustries with stable constituent coverage.
- **Interpretation:** Explains movement in a narrow niche where the target’s direct economics differ materially from the broad industry, such as GPU semiconductors, GLP-1 obesity drugs, regional banks, LNG exporters, or EV suppliers.
- **Data sourcing:** Use licensed subindustry classifications if available; otherwise use analyst-curated subindustry membership. Build basket returns from adjusted prices and point-in-time constituent membership. Avoid ETF proxies unless the ETF is a close economic match.
- **Calculation methodology:**

```text
For each active constituent k, excluding the target:
  constituent_return_k_bps = 10000 * (price_k_end / price_k_start - 1)

Weight policy:
  equal_weight_k = 1 / N
  or
  capped_float_mcap_weight_k = min(raw_weight_k, cap) / sum(capped_weights)

subindustry_basket_return_bps = sum(weight_k * constituent_return_k_bps)

Residualize basket against market, sector, and industry:
  subindustry_factor_move_bps = residualized_subindustry_basket_move_bps

subindustry_contribution_bps = beta_subindustry * subindustry_factor_move_bps
```

- **Application inside AAT:** Apply after industry. Use as a more granular systematic driver before custom peer baskets. If subindustry and peer basket are nearly identical, keep the subindustry row as evidence-only or merge it into peer attribution to avoid double counting.
- **Evidence payload:** `basket_id`, `basket_version`, `members`, `weights`, `weight_method`, `active_start`, `active_end`, `subindustry_factor_move_bps`, `beta_subindustry`.
- **Confidence and validation rules:** Require versioned membership and target exclusion. Downgrade if fewer than four non-target members, if any member has stale price data, if one member weight exceeds the cap, or if correlation with peer basket exceeds the configured threshold.


#### Custom peer basket

- **Initial adoption stage:** Shadow, then production; highest Priority 1 addition after sector/industry.
- **Interpretation:** Measures whether direct peers moved in the same direction, which helps distinguish company-specific moves from sympathy or competitive revaluation.
- **Data sourcing:** Use analyst-curated peer baskets as the initial source of truth. Supplement with filings, business descriptions, GICS/RBICS tags, revenue segment similarity, ETF holdings, and benchmark constituents. Store all peer definitions in `peer_basket` and `peer_basket_member` with active dates and versions.
- **Calculation methodology:**

```text
For each active peer p, excluding the target:
  peer_return_p_bps = 10000 * (peer_price_end / peer_price_start - 1)

peer_basket_return_bps = sum(peer_weight_p * peer_return_p_bps)

Residualize peer basket against market, sector, industry, and subindustry:
  peer_factor_move_bps = residual(peer_basket_return_bps | prior hierarchy factors)

Estimate target peer beta on pre-window data:
  stock_residual_after_industry_t = a + beta_peer * peer_factor_t + error_t

peer_contribution_bps = beta_peer * peer_factor_move_bps
```

- **Application inside AAT:** Apply after subindustry and before style. Peer contribution should be the main guardrail against overclaiming target-specific events. Store basket version in every attribution row so historical results remain reproducible.
- **Evidence payload:** `peer_basket_id`, `peer_basket_version`, `peer_count`, `peer_weights`, `excluded_target=true`, `peer_factor_move_bps`, `beta_peer`, `peer_return_distribution`.
- **Confidence and validation rules:** No contribution if the peer basket is missing, unapproved, stale, or has fewer than three usable peers. Downgrade for high concentration, stale membership, mismatched peers, or large corporate actions during the estimation window.


#### Peer residual spread

- **Initial adoption stage:** Evidence-only first; production as a diagnostic residual row, not a normal systematic factor.
- **Interpretation:** Measures how much the target moved relative to what its peer basket would imply after market, sector, and industry effects. It is a company-specific spread diagnostic rather than an independent causal driver.
- **Data sourcing:** Use the same peer basket, prices, and residualized factor moves used for custom peer basket attribution. Do not source this separately.
- **Calculation methodology:**

```text
target_systematic_residual_before_events_bps
  = observed_return_bps
  - market_contribution_bps
  - sector_contribution_bps
  - industry_contribution_bps
  - subindustry_contribution_bps
  - style_contribution_bps
  - macro_contribution_bps
  - positioning_contribution_bps

peer_expected_move_bps = beta_peer * peer_factor_move_bps

peer_residual_spread_bps = target_residual_after_market_sector_industry_bps
                         - peer_expected_move_bps
```

- **Application inside AAT:** Display as a diagnostic line or evidence panel. It can help users see whether the remaining move is idiosyncratic. Do not subtract it from observed return as both peer contribution and residual spread unless it is explicitly modeled as a residual allocation row.
- **Evidence payload:** `peer_residual_spread_bps`, `peer_expected_move_bps`, `target_residual_before_peer_bps`, `target_residual_after_peer_bps`, `basket_version`.
- **Confidence and validation rules:** Validate that peer residual spread is algebraically consistent with peer contribution. Downgrade if peer beta is low-confidence or if peer basket constituents had major target-relevant events that should be handled as read-through instead.


#### Peer event read-through

- **Initial adoption stage:** Evidence-only, then shadow after event-study calibration by sector/event type.
- **Interpretation:** Captures cases where an event at a peer reprices the target, such as a competitor earnings warning, FDA decision, product launch, pricing change, supply-chain issue, or regulatory action.
- **Data sourcing:** Source peer events from SEC EDGAR, company investor-relations releases, earnings feeds, FDA/openFDA/ClinicalTrials.gov for healthcare, regulator websites, and licensed news/estimates feeds. Link events through the active peer basket and exposure-similarity mappings.
- **Calculation methodology:**

```text
peer_event_abnormal_return_bps
  = peer_observed_return_bps
  - peer_market_contribution_bps
  - peer_sector_contribution_bps
  - peer_industry_contribution_bps
  - peer_style_macro_positioning_contribution_bps

exposure_similarity = cosine_similarity(target_exposure_vector, peer_exposure_vector)
  bounded to [0, 1]

readthrough_factor_move_bps = peer_event_abnormal_return_bps
                            * peer_weight
                            * exposure_similarity
                            * timing_decay
                            * source_credibility

readthrough_contribution_bps = beta_readthrough * readthrough_factor_move_bps
  where beta_readthrough is calibrated by event category and sector
```

- **Application inside AAT:** Apply after peer-basket return attribution and before target-specific event attribution. Until calibrated, attach the read-through score to residual evidence rather than allocating contribution. Use next-trading-window logic for after-close peer events.
- **Evidence payload:** `peer_event_id`, `peer_accession_or_source_id`, `peer_event_category`, `peer_event_time`, `exposure_similarity`, `peer_weight`, `readthrough_score`, `calibration_version`.
- **Confidence and validation rules:** Block production contribution if the peer event was not visible by cutoff, if exposure similarity is below threshold, if historical sample size is insufficient, or if target has its own stronger same-window event.


## Priority 2 Calculation Methodologies: Additional Style Factors

Style attributes are either traded factor returns, cross-sectional descriptors, or both. The production target is an internal AAT cross-sectional style model; the MVP may continue to map some descriptors to French factors where the mapping is transparent.

### Cross-sectional style factor construction standard

For internal AAT style factors, compute prior-day descriptors, then estimate or construct daily factor returns:

```text
exposure_z_i,k,t_minus_1 = zscore(winsorized_descriptor_i,k,t_minus_1)

Daily cross-sectional regression option:
  stock_residual_return_i,t = alpha_t + sum_k exposure_z_i,k,t_minus_1 * style_factor_return_k,t + error_i,t

Portfolio option:
  style_factor_return_k,t = return(top_quintile_by_exposure_k)_t - return(bottom_quintile_by_exposure_k)_t
```

Use sector-neutralization for descriptors that differ structurally by sector, including value, growth, quality, leverage, dividend yield, and investment intensity.

#### Momentum

- **Initial adoption stage:** Shadow, then production once an AAT momentum factor return exists.
- **Interpretation:** Captures intermediate-term price continuation. It should not duplicate the most recent month, which is reserved for reversal and event effects.
- **Data sourcing:** Use adjusted daily prices from `price_bar`. No external data is needed for the descriptor. For production contribution, construct a sector-neutral AAT high-minus-low momentum factor from the coverage universe or use a licensed style factor return.
- **Calculation methodology:**

```text
momentum_12_1 = (adj_close_t_minus_22 / adj_close_t_minus_252) - 1

winsorized_momentum = winsorize(momentum_12_1, p1, p99 by universe/date)
momentum_exposure_z = zscore(winsorized_momentum by universe/date)

Internal factor return option:
  momentum_factor_return_bps_t = return(top_momentum_quintile)_t
                               - return(bottom_momentum_quintile)_t
  sector-neutralized before portfolio construction

contribution_bps = momentum_exposure_z_at_window_start * momentum_factor_return_bps_window
```

- **Application inside AAT:** Store descriptor in `security_factor_exposure`. In MVP, display as exposure evidence. In production, apply after peer factors using the cross-sectional style factor return. Exclude recent 21 trading days from the descriptor to reduce overlap with reversal and event windows.
- **Evidence payload:** `momentum_12_1`, `momentum_exposure_z`, `factor_return_source`, `quintile_breakpoints`, `lookback_days=252`, `skip_days=21`.
- **Confidence and validation rules:** Require at least 252 adjusted price observations. Downgrade for IPOs, trading halts, major corporate actions, or if momentum factor return is not sector-neutral.


#### Short-term reversal

- **Initial adoption stage:** Shadow initially; production only if out-of-sample residual reduction is proven.
- **Interpretation:** Captures bounce/fade behavior after recent price pressure and prevents AAT from treating every snapback as a company-specific event.
- **Data sourcing:** Use adjusted prices from `price_bar`. Optional future enhancement can use intraday returns when licensed.
- **Calculation methodology:**

```text
prior_return_5d = adj_close_t_minus_1 / adj_close_t_minus_6 - 1
prior_return_21d = adj_close_t_minus_1 / adj_close_t_minus_22 - 1

reversal_descriptor = -1 * prior_return_5d
  or composite = -0.6 * prior_return_5d - 0.4 * prior_return_21d

reversal_exposure_z = zscore(winsorize(reversal_descriptor))

reversal_factor_return_bps = return(high_reversal_exposure_portfolio)
                           - return(low_reversal_exposure_portfolio)

contribution_bps = reversal_exposure_z * reversal_factor_return_bps_window
```

- **Application inside AAT:** Use as a style contribution only when a daily reversal factor return is maintained. Otherwise display as a residual diagnostic after large prior moves. Do not let reversal consume event residual when a same-day event is visible and material.
- **Evidence payload:** `prior_return_5d`, `prior_return_21d`, `reversal_exposure_z`, `factor_return_window`, `lookback_variant`.
- **Confidence and validation rules:** Downgrade if recent returns include a split/corporate-action adjustment error, trading halt, or event day that should be excluded from style estimation.


#### Volatility / realized volatility

- **Initial adoption stage:** Shadow, then production for a high-minus-low volatility factor; immediate use as confidence modifier.
- **Interpretation:** Measures whether the target behaves like a high-volatility or low-volatility stock and whether a move is unusual relative to its normal behavior.
- **Data sourcing:** Use adjusted daily returns from `price_bar`. Add intraday realized volatility only after intraday market data licensing is resolved.
- **Calculation methodology:**

```text
daily_return_t = adj_close_t / adj_close_t_minus_1 - 1

realized_vol_60d = stdev(daily_return over last 60 trading days) * sqrt(252)
realized_vol_252d = stdev(daily_return over last 252 trading days) * sqrt(252)

volatility_exposure_z = zscore(winsorize(log(realized_vol_60d)))

volatility_factor_return_bps = return(high_vol_portfolio) - return(low_vol_portfolio)

contribution_bps = volatility_exposure_z * volatility_factor_return_bps_window

move_z_score = observed_return_bps / (realized_vol_60d / sqrt(252) * 10000)
```

- **Application inside AAT:** Use `move_z_score` to calibrate confidence and event materiality. Use volatility contribution only when an AAT or vendor volatility style factor return exists. High-vol names should receive lower confidence on small residuals; low-vol names should flag smaller residuals as unusual.
- **Evidence payload:** `realized_vol_60d`, `realized_vol_252d`, `volatility_exposure_z`, `move_z_score`, `factor_return_source`.
- **Confidence and validation rules:** Require at least 60 observations for descriptor, 252 for production-grade stability. Downgrade for halted trading, stale prices, extreme outlier days, or missing corporate-action adjustments.


#### Market beta descriptor

- **Initial adoption stage:** Production as metadata/confidence input; separate contribution only if a beta style factor is implemented.
- **Interpretation:** Stores the target’s structural market sensitivity. It is distinct from the daily market contribution, which is beta multiplied by the actual market move in the attribution window.
- **Data sourcing:** Use target adjusted returns and market proxy returns from Kenneth French `Mkt-RF`, SPY/IVV, or licensed market index return series.
- **Calculation methodology:**

```text
rolling_beta_63d  = cov(stock_return, market_return, 63d)  / var(market_return, 63d)
rolling_beta_126d = cov(stock_return, market_return, 126d) / var(market_return, 126d)
rolling_beta_252d = cov(stock_return, market_return, 252d) / var(market_return, 252d)

beta_stability_score = 1 - min(1, stdev([beta_63d, beta_126d, beta_252d]) / beta_scale)

beta_descriptor_z = zscore(rolling_beta_252d by universe/date)

Optional beta-style contribution:
  contribution_bps = beta_descriptor_z * beta_style_factor_return_bps
```

- **Application inside AAT:** Feed market attribution, confidence scoring, and exposure-review decisions. Do not create a second `market beta descriptor` contribution unless AAT has a beta style factor return distinct from the broad market row.
- **Evidence payload:** `rolling_beta_63d`, `rolling_beta_126d`, `rolling_beta_252d`, `beta_stderr`, `beta_r_squared`, `beta_stability_score`.
- **Confidence and validation rules:** Downgrade if beta changes sign, R-squared is very low, or major event days dominate the estimate. Trigger exposure review when beta drift exceeds configured thresholds over multiple windows.


#### Liquidity

- **Initial adoption stage:** Shadow, then production; immediate use as flow/liquidity evidence and confidence modifier.
- **Interpretation:** Captures whether trading frictions, limited depth, or volume shocks may have magnified the stock move.
- **Data sourcing:** Use adjusted price and volume for MVP. Add bid/ask quotes, effective spread, depth, and market-center data from licensed market-data vendors for production microstructure support.
- **Calculation methodology:**

```text
dollar_volume_t = adj_close_t * volume_t
adv_20d = mean(volume over last 20 trading days)
average_dollar_volume_20d = mean(dollar_volume over last 20 trading days)

relative_volume = current_volume / adv_20d
amihud_illiquidity_20d = mean(abs(daily_return_t) / dollar_volume_t over 20d)

liquidity_descriptor = -1 * log(average_dollar_volume_20d)
  plus optional amihud z-score composite

liquidity_exposure_z = zscore(winsorize(liquidity_descriptor by market-cap bucket))

liquidity_factor_return_bps = return(illiquid_portfolio) - return(liquid_portfolio)
contribution_bps = liquidity_exposure_z * liquidity_factor_return_bps_window
```

- **Application inside AAT:** Apply after macro or within positioning/liquidity layer. Use relative volume as evidence for flow-driven moves. Contribution requires a maintained liquidity factor return; otherwise use as confidence modifier and dashboard flag.
- **Evidence payload:** `average_dollar_volume_20d`, `relative_volume`, `amihud_illiquidity`, `liquidity_exposure_z`, `quote_spread` when available.
- **Confidence and validation rules:** Downgrade if volume is missing, stale, or vendor-adjusted inconsistently. Do not compare raw liquidity z-scores across microcap and mega-cap universes without market-cap bucketing.


#### Size

- **Initial adoption stage:** Production descriptor using French `SMB`; production contribution when mapping is validated.
- **Interpretation:** Captures small-cap versus large-cap behavior using an analyst-readable company-level descriptor rather than only an abstract `SMB` factor.
- **Data sourcing:** Use adjusted price and point-in-time shares outstanding from price vendor fundamentals, SEC XBRL company facts, or a licensed fundamentals vendor. Continue using Kenneth French `SMB` as the initial factor return.
- **Calculation methodology:**

```text
market_cap = adjusted_price * shares_outstanding_point_in_time
size_descriptor = log(market_cap)

small_size_exposure_z = -1 * zscore(winsorize(size_descriptor by universe/date))
  because smaller companies should load positively on SMB

size_contribution_bps = small_size_exposure_z * SMB_factor_return_bps_window
  or beta_SMB * SMB_factor_return_bps_window under the existing French regression
```

- **Application inside AAT:** Display `large-cap`, `mid-cap`, or `small-cap` using buckets, but calculate contribution with continuous exposure or the existing French beta. Store shares timestamp to avoid look-ahead from current shares outstanding.
- **Evidence payload:** `market_cap`, `shares_outstanding`, `shares_source`, `size_exposure_z`, `SMB_factor_return_bps`, `beta_SMB` if regression-based.
- **Confidence and validation rules:** Downgrade for stale shares outstanding, dual-share classes, recent IPOs, spin-offs, ADRs with ratio complications, or market cap affected by unresolved corporate actions.


#### Value / earnings yield

- **Initial adoption stage:** Research to shadow for point-in-time fundamentals; production can initially map to French `HML`.
- **Interpretation:** Measures whether the stock behaves like a cheaper or more expensive equity relative to earnings, book value, or sales.
- **Data sourcing:** Use SEC XBRL company facts for trailing fundamentals where available. Use licensed consensus estimates for forward earnings yield. Kenneth French `HML` can serve as the initial factor return; internal value factor can be built later.
- **Calculation methodology:**

```text
trailing_earnings_yield = trailing_12m_eps / price
forward_earnings_yield = consensus_forward_eps / price
book_to_market = book_equity / market_cap
sales_to_price = trailing_12m_revenue / market_cap

value_composite = average(zscore(earnings_yield), zscore(book_to_market), zscore(sales_to_price))
  with negative earnings handled by fallback weights

value_contribution_bps = value_exposure_z * value_factor_return_bps_window
  or beta_HML * HML_factor_return_bps_window
```

- **Application inside AAT:** Use HML mapping for MVP evidence. Move to an internal composite factor only when point-in-time fundamentals are complete. Evidence must state whether earnings yield, book-to-market, or sales-to-price was active.
- **Evidence payload:** `trailing_eps`, `forward_eps`, `book_equity`, `value_exposure_z`, `negative_earnings_flag`, `factor_mapping=HML|internal_value`.
- **Confidence and validation rules:** Downgrade for negative earnings, stale fundamentals, non-comparable accounting, financial companies where book value has special interpretation, or consensus data without a confirmed license.


#### Growth

- **Initial adoption stage:** Research until point-in-time fundamentals and/or estimates source is confirmed.
- **Interpretation:** Measures exposure to companies priced on revenue growth, EPS growth, or long-duration earnings expansion.
- **Data sourcing:** Use SEC filings/XBRL for historical revenue and EPS growth. Use licensed consensus estimates for forward growth. Investor presentations may be stored as evidence but should not be the primary numeric source.
- **Calculation methodology:**

```text
revenue_growth_yoy = revenue_ttm / revenue_ttm_one_year_ago - 1
revenue_cagr_3y = (revenue_ttm / revenue_ttm_three_years_ago)^(1/3) - 1
forward_revenue_growth = consensus_next_year_revenue / consensus_current_year_revenue - 1
forward_eps_growth = consensus_next_year_eps / consensus_current_year_eps - 1

growth_exposure_z = sector_relative_zscore(winsorize(growth_composite))

growth_factor_return_bps = return(high_growth_portfolio) - return(low_growth_portfolio)
contribution_bps = growth_exposure_z * growth_factor_return_bps_window
```

- **Application inside AAT:** Keep evidence-only until point-in-time growth metrics are reliable. In production, use sector-relative growth exposures because structurally normal growth differs by industry.
- **Evidence payload:** `revenue_growth_yoy`, `revenue_cagr_3y`, `forward_revenue_growth`, `forward_eps_growth`, `growth_exposure_z`, `source_fiscal_period`.
- **Confidence and validation rules:** Block production if fundamentals are not point-in-time visible. Downgrade for acquisitions/divestitures that distort growth, negative base values, or inconsistent fiscal calendars.


#### Quality

- **Initial adoption stage:** Research until point-in-time fundamentals are reliable; maps partially to French `RMW`.
- **Interpretation:** Captures profitability, margin strength, balance-sheet quality, and earnings stability using descriptors analysts recognize.
- **Data sourcing:** Use SEC XBRL and licensed fundamentals for ROE, ROA, gross margin, operating margin, accruals, and earnings variability. Use French `RMW` as initial profitability factor return where appropriate.
- **Calculation methodology:**

```text
roe = net_income_ttm / average_book_equity
gross_margin = gross_profit_ttm / revenue_ttm
operating_margin = operating_income_ttm / revenue_ttm
accruals = (net_income_ttm - operating_cash_flow_ttm) / average_total_assets
earnings_stability = -1 * stdev(quarterly_eps over 12 quarters)

quality_composite_z = average(
  zscore(roe), zscore(gross_margin), zscore(operating_margin),
  -zscore(accruals), zscore(earnings_stability)
)

quality_contribution_bps = quality_composite_z * quality_factor_return_bps_window
  or beta_RMW * RMW_factor_return_bps_window
```

- **Application inside AAT:** Use as descriptor/evidence first. Production contribution can map to `RMW` for profitability, but a broader quality composite requires its own internal factor return.
- **Evidence payload:** `roe`, `gross_margin`, `operating_margin`, `accruals`, `earnings_stability`, `quality_exposure_z`, `RMW_mapping_flag`.
- **Confidence and validation rules:** Downgrade for banks/insurers where generic margins are not meaningful, restatements, missing cash-flow data, or one-time charges that distort trailing metrics.


#### Leverage

- **Initial adoption stage:** Research/shadow; production only when point-in-time debt metrics are stable. Also used as macro gate.
- **Interpretation:** Measures financial leverage and refinancing sensitivity. It helps explain why credit spreads or rates affect some companies more than others.
- **Data sourcing:** Use SEC filings/XBRL or licensed fundamentals for total debt, net debt, EBITDA, interest expense, cash, maturity schedule, and floating-rate debt percentage when disclosed.
- **Calculation methodology:**

```text
debt_to_assets = total_debt / total_assets
net_debt_to_ebitda = (total_debt - cash_and_equivalents) / EBITDA_ttm
interest_coverage = EBIT_ttm / interest_expense_ttm
leverage_composite = average(zscore(debt_to_assets), zscore(net_debt_to_ebitda), -zscore(interest_coverage))

leverage_exposure_z = sector_relative_zscore(winsorize(leverage_composite))

leverage_style_contribution_bps = leverage_exposure_z * leverage_factor_return_bps_window
credit_gate_weight = sigmoid(leverage_exposure_z) adjusted by maturity_wall and interest_coverage
```

- **Application inside AAT:** Use leverage as both a style descriptor and a gate for credit-spread/rate macro factors. Contribution requires a leverage factor return; gating can be active earlier with conservative confidence.
- **Evidence payload:** `total_debt`, `cash`, `EBITDA`, `interest_expense`, `debt_to_assets`, `net_debt_to_ebitda`, `interest_coverage`, `leverage_exposure_z`.
- **Confidence and validation rules:** Downgrade if EBITDA is negative, debt classifications are missing, lease liabilities distort comparability, or financial-sector balance sheets require sector-specific treatment.


#### Dividend yield

- **Initial adoption stage:** Research/shadow; production after dividend data source and factor return are validated.
- **Interpretation:** Captures income/defensive stock behavior and sensitivity to rate moves and dividend announcements.
- **Data sourcing:** Use corporate actions/dividend history from a licensed market-data vendor. SEC filings can validate dividend declarations but are not ideal as the sole daily data source.
- **Calculation methodology:**

```text
annualized_regular_dividend = sum(last four regular quarterly dividends)
  or indicated_annual_dividend from vendor

dividend_yield = annualized_regular_dividend / adjusted_price

dividend_exposure_z = sector_relative_zscore(winsorize(dividend_yield))

dividend_factor_return_bps = return(high_dividend_yield_portfolio)
                           - return(low_dividend_yield_portfolio)

contribution_bps = dividend_exposure_z * dividend_factor_return_bps_window
```

- **Application inside AAT:** Use as style descriptor and rate-sensitivity evidence. Keep special dividends separate from regular dividend yield. Dividend change events should be handled in the event layer, not as a style descriptor update alone.
- **Evidence payload:** `regular_dividend_amounts`, `indicated_annual_dividend`, `dividend_yield`, `special_dividend_flag`, `dividend_exposure_z`.
- **Confidence and validation rules:** Downgrade when dividend history contains specials, suspensions, spinoff-related dividends, ADR withholding complexity, or stale corporate-action data.


#### Investment intensity

- **Initial adoption stage:** Production can map to French `CMA`; expanded descriptor remains research until fundamentals are reliable.
- **Interpretation:** Measures asset growth and capital intensity, giving an analyst-readable version of the conservative-minus-aggressive investment factor.
- **Data sourcing:** Use SEC XBRL or licensed fundamentals for capex, revenue, total assets, PP&E, R&D where relevant, and asset growth. Existing French `CMA` can provide a factor return.
- **Calculation methodology:**

```text
capex_to_sales = capital_expenditures_ttm / revenue_ttm
asset_growth_yoy = total_assets_current_fy / total_assets_prior_fy - 1
rnd_to_sales = research_and_development_ttm / revenue_ttm

investment_intensity_composite = average(zscore(capex_to_sales), zscore(asset_growth_yoy))
  optionally include rnd_to_sales for technology/healthcare if methodology approves

investment_exposure_z = sector_relative_zscore(winsorize(investment_intensity_composite))

contribution_bps = investment_exposure_z * investment_factor_return_bps_window
  or beta_CMA * CMA_factor_return_bps_window
```

- **Application inside AAT:** Use French `CMA` contribution in the current model. Add descriptor evidence so analysts can see whether the stock is capex-heavy, asset-growth-heavy, or R&D-heavy. Do not mix R&D and capex without sector-specific calibration.
- **Evidence payload:** `capex_to_sales`, `asset_growth_yoy`, `rnd_to_sales`, `investment_exposure_z`, `CMA_factor_return_bps`, `beta_CMA`.
- **Confidence and validation rules:** Downgrade for acquisitive companies, accounting changes, missing capex, financials where asset growth means something different, or stale fundamentals.


## Priority 3 Calculation Methodologies: Macro Factors

Macro attributes must be exposure-gated. AAT should not display every macro factor for every stock. A macro factor can become a production contribution when the company has a plausible structural exposure or the estimated sensitivity is stable, point-in-time, and statistically credible.

### Macro transformation standard

For rates and spreads:

```text
factor_move = level_end_bps - level_start_bps
```

For commodities, FX, crypto, and tradable proxies:

```text
factor_move_bps = 10000 * (proxy_end / proxy_start - 1)
```

For index levels such as VIX:

```text
factor_move = index_end - index_start
```

Estimate macro sensitivity on stock residual returns after market, sector, industry, peer, and style factors. Store unit labels explicitly because macro factors are not all measured in return bps.

#### 2Y Treasury yield change

- **Initial adoption stage:** Shadow, then production for rate-sensitive names.
- **Interpretation:** Captures front-end rate/Fed-policy sensitivity.
- **Data sourcing:** Use FRED `DGS2` for public development, with ALFRED/vintage support where revision timing matters. Licensed Treasury or futures data may be used for intraday or exact close alignment.
- **Calculation methodology:**

```text
y2_bps_t = DGS2_percent_t * 100
delta_2y_bps = y2_bps_end - y2_bps_start

Estimate on pre-window residual stock returns:
  stock_residual_t = a + beta_2y * delta_2y_bps_t + error_t

contribution_bps = beta_2y_bps_per_1bp * delta_2y_bps_window
```

- **Application inside AAT:** Apply in macro layer after style. Gate by interest-rate exposure or allow if regression sensitivity is stable and statistically meaningful. Use daily close-to-close alignment; for missing holiday values, carry forward only if source methodology approves and mark lower confidence.
- **Evidence payload:** `series_id=DGS2`, `start_value`, `end_value`, `delta_2y_bps`, `beta_2y`, `exposure_gate`, `vintage_date`.
- **Confidence and validation rules:** Downgrade for stale FRED observations, low regression observations, unstable beta sign, high collinearity with 10Y/curve factors, or missing interest-rate exposure profile.


#### 10Y Treasury yield change

- **Initial adoption stage:** Shadow, then production for duration-sensitive equities.
- **Interpretation:** Captures long-rate and equity-duration sensitivity, especially for growth equities, housing, utilities, REITs, and long-duration assets.
- **Data sourcing:** Use FRED `DGS10`, licensed Treasury curves, or Treasury futures where better timestamp alignment is required.
- **Calculation methodology:**

```text
y10_bps_t = DGS10_percent_t * 100
delta_10y_bps = y10_bps_end - y10_bps_start

stock_residual_t = a + beta_10y * delta_10y_bps_t + error_t
contribution_bps = beta_10y_bps_per_1bp * delta_10y_bps_window
```

- **Application inside AAT:** Apply in macro layer. When 2Y and 10Y are both included, run multivariate estimation or orthogonalize 10Y into level/curve components to avoid double counting.
- **Evidence payload:** `series_id=DGS10`, `delta_10y_bps`, `beta_10y`, `rate_exposure_gate`, `duration_sensitivity_note`.
- **Confidence and validation rules:** Downgrade if the 10Y move is highly collinear with broad market or growth factor moves, or if the company has no plausible duration/rate channel and regression is weak.


#### 2s10s curve change

- **Initial adoption stage:** Shadow, then production for banks, cyclicals, and recession-sensitive names.
- **Interpretation:** Measures yield-curve steepening or flattening beyond simple rate-level moves.
- **Data sourcing:** Use FRED `DGS10` and `DGS2`, or a licensed Treasury curve source. Store the derived series in `factor_observation`/`factor_return` as an AAT-derived macro factor.
- **Calculation methodology:**

```text
curve_2s10s_bps_t = (DGS10_percent_t - DGS2_percent_t) * 100
delta_curve_bps = curve_2s10s_bps_end - curve_2s10s_bps_start

If level/curve decomposition is used:
  rate_level_t = (delta_2y_bps_t + delta_10y_bps_t) / 2
  curve_t = delta_10y_bps_t - delta_2y_bps_t

contribution_bps = beta_curve_bps_per_1bp * delta_curve_bps_window
```

- **Application inside AAT:** Apply after or jointly with 2Y/10Y. Gate heavily for banks, insurers, brokers, cyclicals, and rate-sensitive balance-sheet businesses. For software or biotech, include only if regression evidence is strong and confidence is downgraded.
- **Evidence payload:** `derived_series_id=AAT_2S10S`, `delta_curve_bps`, `beta_curve`, `rate_level_curve_model_version`.
- **Confidence and validation rules:** Downgrade when 2Y and 10Y source timestamps differ, when curve beta is unstable, or when curve inclusion increases condition number beyond threshold.


#### Fed funds expectations

- **Initial adoption stage:** Research until source/license and contract-selection methodology are confirmed.
- **Interpretation:** Captures changes in expected policy path that may not be fully represented by observed Treasury yields.
- **Data sourcing:** Use CME Fed Funds futures, SOFR futures, OIS curves, or a licensed policy-expectations vendor. Public FRED effective Fed Funds is not enough for expectations because it is realized, not forward-looking.
- **Calculation methodology:**

```text
implied_policy_rate_bps_contract = (100 - futures_price) * 100

Select contract by event horizon:
  near_meeting_contract for FOMC-specific window
  3m_to_12m strip for broader policy expectations

delta_policy_expectation_bps = implied_rate_end - implied_rate_start

contribution_bps = beta_policy_expectation * delta_policy_expectation_bps
```

- **Application inside AAT:** Keep research-only until AAT defines contract roll rules, FOMC meeting mapping, holiday handling, and licensing. Apply only to windows where policy expectation movement is timestamp-aligned.
- **Evidence payload:** `contract_symbol`, `contract_month`, `implied_rate_start`, `implied_rate_end`, `delta_policy_expectation_bps`, `roll_rule_version`.
- **Confidence and validation rules:** Block production if futures source is unlicensed, contract selection is ambiguous, or attribution window crosses a contract roll without a versioned rule.


#### Dollar index

- **Initial adoption stage:** Shadow if source is confirmed; production for FX-exposed companies.
- **Interpretation:** Captures USD strength/weakness effects on multinationals, commodity names, exporters, importers, ADRs, and companies with foreign revenue/cost mismatch.
- **Data sourcing:** Use DXY from a licensed market-data source, FRED broad dollar indices such as `DTWEXBGS` where appropriate, or currency baskets matched to company exposure.
- **Calculation methodology:**

```text
dollar_return_bps = 10000 * (dollar_index_end / dollar_index_start - 1)
  or
dollar_level_change = dollar_index_end - dollar_index_start

contribution_bps = beta_usd * dollar_factor_move

For exposure prior:
  net_fx_exposure = foreign_revenue_pct - foreign_cost_pct - hedged_pct
  expected_sign = -1 for U.S. exporter revenue translation, +1 for import-cost benefit when applicable
```

- **Application inside AAT:** Gate by foreign-exchange exposure. Use company-specific currency baskets when available; DXY may be a poor proxy for non-G10 or China-heavy revenue. Evidence must state proxy choice.
- **Evidence payload:** `dollar_proxy`, `dollar_return_bps`, `beta_usd`, `net_fx_exposure`, `currency_basket_version`.
- **Confidence and validation rules:** Downgrade for proxy mismatch, missing foreign revenue/cost split, hedging disclosures that are stale, or mixed currency exposures.


#### WTI crude

- **Initial adoption stage:** Shadow, then production for commodity-exposed names.
- **Interpretation:** Captures crude-oil price sensitivity. Expected sign differs for producers, refiners, airlines, chemicals, transports, and consumers.
- **Data sourcing:** Use FRED WTI spot series for public development, licensed NYMEX front-month futures for production, or sector-specific oil product proxies such as jet fuel or crack spreads when appropriate.
- **Calculation methodology:**

```text
wti_return_bps = 10000 * (WTI_end / WTI_start - 1)

beta_wti estimated on stock residual returns:
  stock_residual_t = a + beta_wti * WTI_return_bps_t + error_t

contribution_bps = beta_wti * wti_return_bps_window

Optional structural prior:
  signed_commodity_exposure = producer_revenue_share - consumer_input_cost_share
```

- **Application inside AAT:** Gate by commodity input or producer exposure. Let regression beta determine contribution sign when stable; use exposure sign as a prior and confidence check. Do not apply WTI to all companies by default.
- **Evidence payload:** `wti_source`, `wti_return_bps`, `beta_wti`, `commodity_exposure_sign`, `producer_consumer_flag`.
- **Confidence and validation rules:** Downgrade for spot/futures mismatch, stale commodity exposure, hedging programs, or cases where refined product spreads are better than crude.


#### Natural gas

- **Initial adoption stage:** Shadow, then production for utilities, chemicals, LNG, energy producers, and gas-sensitive industrials.
- **Interpretation:** Captures Henry Hub/natural-gas sensitivity.
- **Data sourcing:** Use FRED Henry Hub series for public development, NYMEX gas futures for production, or regional gas basis data where material.
- **Calculation methodology:**

```text
natgas_return_bps = 10000 * (natgas_price_end / natgas_price_start - 1)
contribution_bps = beta_natgas * natgas_return_bps_window

signed_exposure = gas_production_revenue_share - gas_input_cost_share
```

- **Application inside AAT:** Gate by segment and commodity exposure. Use regional basis proxies for companies with localized exposure where Henry Hub is inadequate.
- **Evidence payload:** `natgas_proxy`, `natgas_return_bps`, `beta_natgas`, `regional_basis_flag`, `commodity_exposure_sign`.
- **Confidence and validation rules:** Downgrade for high seasonality, regional proxy mismatch, and hedged producers/utilities with pass-through regulation.


#### Gold

- **Initial adoption stage:** Shadow; production mainly for miners and risk-off sensitive baskets.
- **Interpretation:** Captures gold-price sensitivity for miners and, secondarily, broad risk-off behavior.
- **Data sourcing:** Use licensed gold spot/futures, GLD adjusted return as a development proxy, or FRED gold-related series if approved.
- **Calculation methodology:**

```text
gold_return_bps = 10000 * (gold_price_end / gold_price_start - 1)
contribution_bps = beta_gold * gold_return_bps_window
```

- **Application inside AAT:** Gate to miners, precious-metals royalty companies, and explicitly gold-linked companies. For non-miners, VIX/credit/rates should usually capture risk-off before gold is considered.
- **Evidence payload:** `gold_proxy`, `gold_return_bps`, `beta_gold`, `gold_revenue_exposure_pct`.
- **Confidence and validation rules:** Downgrade for companies with mixed metals, hedged production, or weak regression evidence.


#### Copper

- **Initial adoption stage:** Shadow; production for miners, industrial cyclicals, electrical equipment, and China-demand proxies.
- **Interpretation:** Captures industrial-cycle and copper-price sensitivity.
- **Data sourcing:** Use licensed copper futures/spot prices, CPER ETF proxy for development, or LME/COMEX vendor data.
- **Calculation methodology:**

```text
copper_return_bps = 10000 * (copper_price_end / copper_price_start - 1)
contribution_bps = beta_copper * copper_return_bps_window
```

- **Application inside AAT:** Gate by metals revenue exposure, input-cost exposure, or sector mapping. Distinguish producers from consumers with exposure sign.
- **Evidence payload:** `copper_proxy`, `copper_return_bps`, `beta_copper`, `producer_consumer_flag`, `china_demand_exposure`.
- **Confidence and validation rules:** Downgrade for proxy mismatch, mixed-commodity miners, or companies whose copper exposure is indirect and better captured by sector/peer factors.


#### High-yield credit spread

- **Initial adoption stage:** Shadow, then production for levered/cyclical names.
- **Interpretation:** Captures risk appetite, financing stress, and default-risk repricing.
- **Data sourcing:** Use FRED ICE BofA U.S. High Yield OAS series where licensing permits, or licensed credit-spread data. Store as a spread level and transformed spread change.
- **Calculation methodology:**

```text
hy_oas_bps_t = HY_OAS_percent_t * 100
delta_hy_oas_bps = hy_oas_bps_end - hy_oas_bps_start

contribution_bps = beta_hy_spread * delta_hy_oas_bps
  where beta is stock bps per 1bp spread change
```

- **Application inside AAT:** Gate by leverage, credit exposure, cyclicality, and refinancing risk. Usually a widening spread should hurt levered/risky equities, but beta should be estimated rather than hard-coded.
- **Evidence payload:** `hy_oas_series_id`, `delta_hy_oas_bps`, `beta_hy_spread`, `credit_exposure_gate`, `leverage_exposure_z`.
- **Confidence and validation rules:** Downgrade if spread data is stale, if daily source is not available at cutoff, or if HY spread is highly collinear with VIX/market residuals.


#### Investment-grade credit spread

- **Initial adoption stage:** Shadow, then production for large-cap balance-sheet and credit-condition sensitivity.
- **Interpretation:** Captures financing conditions for investment-grade borrowers and broader corporate credit risk.
- **Data sourcing:** Use FRED ICE BofA investment-grade OAS series where permissible, or licensed corporate spread curves. Select broad IG OAS for general use and sector curves where licensed.
- **Calculation methodology:**

```text
ig_oas_bps_t = IG_OAS_percent_t * 100
delta_ig_oas_bps = ig_oas_bps_end - ig_oas_bps_start

contribution_bps = beta_ig_spread * delta_ig_oas_bps
```

- **Application inside AAT:** Gate by debt profile, financial-sector exposure, and credit sensitivity. Use IG spread before HY for high-quality large caps; use HY for distressed or lower-quality balance sheets.
- **Evidence payload:** `ig_oas_series_id`, `delta_ig_oas_bps`, `beta_ig_spread`, `issuer_quality_bucket`, `credit_gate_weight`.
- **Confidence and validation rules:** Downgrade when IG and HY factors are too collinear or when a company-specific bond event should be handled as an event instead.


#### VIX change

- **Initial adoption stage:** Shadow, then production as risk-off/volatility-regime factor.
- **Interpretation:** Captures changes in implied equity-market volatility and risk appetite.
- **Data sourcing:** Use FRED `VIXCLS` for daily close or official/licensed Cboe VIX data for production and intraday alignment.
- **Calculation methodology:**

```text
delta_vix_points = VIX_end - VIX_start

stock_residual_t = a + beta_vix * delta_vix_points_t + error_t
contribution_bps = beta_vix_bps_per_vix_point * delta_vix_points_window
```

- **Application inside AAT:** Apply in macro/positioning boundary layer after rates/credit or jointly with them. Use carefully because VIX is often collinear with market selloffs; residualize VIX against market when appropriate.
- **Evidence payload:** `series_id=VIXCLS`, `delta_vix_points`, `beta_vix`, `vix_residualized_flag`, `source_close_time`.
- **Confidence and validation rules:** Downgrade for high collinearity with market/credit factors, stale VIX observations, or single-stock moves dominated by target-specific event evidence.


#### Inflation expectations

- **Initial adoption stage:** Shadow; production for inflation/rate-sensitive sectors after calibration.
- **Interpretation:** Captures changes in market-implied inflation expectations, relevant to real assets, staples, utilities, consumer names, and duration-sensitive equities.
- **Data sourcing:** Use FRED breakeven inflation series such as 5-year breakeven or 5y5y forward inflation expectations, or licensed inflation swap data.
- **Calculation methodology:**

```text
inflation_expectation_bps_t = inflation_series_percent_t * 100
delta_inflation_expectation_bps = end_bps - start_bps

contribution_bps = beta_inflation_expectation * delta_inflation_expectation_bps
```

- **Application inside AAT:** Gate by sector and exposure profile. Use jointly with nominal rates to distinguish real-rate versus inflation-break-even moves when possible.
- **Evidence payload:** `inflation_series_id`, `delta_inflation_expectation_bps`, `beta_inflation`, `real_rate_decomposition_flag`.
- **Confidence and validation rules:** Downgrade for stale or revised series, low-frequency updates, or high collinearity with 10Y yield changes.


#### Mortgage rate

- **Initial adoption stage:** Shadow; production for housing-linked names after weekly-to-daily alignment is defined.
- **Interpretation:** Captures housing affordability and mortgage-credit sensitivity for homebuilders, building products, banks, mortgage originators, title insurers, and consumer finance.
- **Data sourcing:** Use FRED 30-year fixed mortgage rate series or licensed daily mortgage-rate data. Weekly public series must be timestamped by release date rather than period date.
- **Calculation methodology:**

```text
mortgage_rate_bps_t = mortgage_rate_percent_t * 100
delta_mortgage_rate_bps = latest_available_rate_bps_at_cutoff
                          - prior_available_rate_bps_at_window_start

contribution_bps = beta_mortgage_rate * delta_mortgage_rate_bps
```

- **Application inside AAT:** Gate by housing exposure. Because many public mortgage series are weekly, daily attribution should use only the latest value actually available by cutoff and should often remain evidence-only for one-day windows.
- **Evidence payload:** `mortgage_series_id`, `release_date`, `latest_available_value`, `delta_mortgage_rate_bps`, `housing_exposure_gate`.
- **Confidence and validation rules:** Downgrade for low-frequency data, stale observations, or when Treasury yields already capture most of the rate move.


#### Crypto factor

- **Initial adoption stage:** Research/shadow; production only for crypto-linked equities with confirmed data source.
- **Interpretation:** Captures bitcoin/crypto-market sensitivity for miners, crypto exchanges, fintechs, balance-sheet crypto holders, and crypto-adjacent equities.
- **Data sourcing:** Use licensed BTC/USD and ETH/USD spot prices, regulated exchange data, or a curated crypto-equity basket. Do not rely on unlicensed website prices for production.
- **Calculation methodology:**

```text
btc_return_bps = 10000 * (BTCUSD_end / BTCUSD_start - 1)
crypto_basket_return_bps = sum(weight_k * crypto_equity_return_k_bps)

crypto_factor_move_bps = selected_proxy_return_bps
contribution_bps = beta_crypto * crypto_factor_move_bps
```

- **Application inside AAT:** Gate by explicit crypto exposure. Use BTC for balance-sheet/miner exposure and a crypto-equity basket for broker/exchange/platform exposure if it better matches economics.
- **Evidence payload:** `crypto_proxy`, `btc_return_bps`, `crypto_basket_return_bps`, `beta_crypto`, `crypto_exposure_type`.
- **Confidence and validation rules:** Downgrade for 24/7 versus equity-market close alignment, high volatility, source licensing uncertainty, or indirect exposure.


## Priority 4 Calculation Methodologies: Positioning, Options, And Flow

Positioning and options attributes are high-value but data-sensitive. They should generally start as evidence-only or shadow contributions. Production use requires strong timestamp discipline because many positioning observations are published with delays.

#### Short interest

- **Initial adoption stage:** Shadow, then production once publication timing and source license are confirmed.
- **Interpretation:** Measures short crowding and squeeze vulnerability. It should be treated as a slowly updated positioning attribute, not a daily price factor unless change data is visible.
- **Data sourcing:** Use FINRA/exchange short-interest data or a licensed vendor. Use float shares from a licensed fundamentals/market-data source or point-in-time company data. Use publication date, not settlement date, for `timestamp_available`.
- **Calculation methodology:**

```text
short_interest_shares = reported_shares_short
short_interest_pct_float = short_interest_shares / float_shares_point_in_time
short_interest_pct_shares_out = short_interest_shares / shares_outstanding

delta_short_interest_pct_float = current_pct_float - prior_pct_float

Optional contribution model:
  contribution_bps = beta_short_interest * delta_short_interest_pct_float

Squeeze evidence score:
  squeeze_score = zscore(short_interest_pct_float)
                * zscore(relative_volume)
                * positive_return_indicator
                * event_positive_surprise_indicator
```

- **Application inside AAT:** Use as positioning evidence and confidence modifier. Production contribution should use change in short interest only when the change was public before the attribution cutoff. High short interest can amplify positive event residuals but should not by itself explain same-day moves if the data was published later.
- **Evidence payload:** `settlement_date`, `publication_date`, `shares_short`, `float_shares`, `short_interest_pct_float`, `delta_short_interest_pct_float`, `squeeze_score`.
- **Confidence and validation rules:** Block look-ahead by using publication timestamp. Downgrade if float is stale, if short-interest source is only bi-monthly, if securities lending data conflicts, or if price move occurs before publication.


#### Days to cover

- **Initial adoption stage:** Shadow, then production with short-interest data.
- **Interpretation:** Measures how many trading days of average volume would be needed for shorts to cover, making it more directly tied to squeeze mechanics than raw short interest.
- **Data sourcing:** Use reported shares short and adjusted volume from `price_bar`. Use 20-day or 30-day ADV; choose one standard and version it.
- **Calculation methodology:**

```text
average_daily_volume_20d = mean(volume over last 20 trading days before cutoff)
days_to_cover = shares_short / average_daily_volume_20d

delta_days_to_cover = current_days_to_cover - prior_days_to_cover

contribution_bps = beta_days_to_cover * delta_days_to_cover
  only if delta was public by cutoff
```

- **Application inside AAT:** Use in positioning layer and squeeze evidence. For daily attribution, days-to-cover often changes because volume changes even if short-interest shares are stale; evidence must state whether the move came from new short data or volume normalization.
- **Evidence payload:** `shares_short`, `adv_20d`, `days_to_cover`, `delta_days_to_cover`, `short_publication_timestamp`, `volume_window`.
- **Confidence and validation rules:** Downgrade if recent volume is distorted by an event day, halted trading, index rebalance, or low float.


#### Borrow cost

- **Initial adoption stage:** Research until securities-lending source is confirmed.
- **Interpretation:** Captures the cost and scarcity of borrow, which can indicate crowded shorts, specials, and squeeze risk.
- **Data sourcing:** Use a licensed securities-lending data vendor for borrow fee, utilization, lendable supply, and rebate rate. Public data is usually insufficient for production.
- **Calculation methodology:**

```text
borrow_fee_annualized_pct = source_borrow_fee
utilization_pct = borrowed_shares / lendable_shares
lendable_supply_pct_float = lendable_shares / float_shares

borrow_pressure_score = zscore(borrow_fee_annualized_pct)
                      + zscore(utilization_pct)
                      - zscore(lendable_supply_pct_float)

contribution_bps = beta_borrow_pressure * change_in_borrow_pressure_score
```

- **Application inside AAT:** Keep research-only until source is licensed and timestamped. Use as a modifier on short-interest and squeeze interpretations rather than a standalone daily contribution at first.
- **Evidence payload:** `borrow_fee`, `utilization`, `lendable_supply`, `borrow_pressure_score`, `source_timestamp`.
- **Confidence and validation rules:** Block production if borrow data is not point-in-time or has insufficient coverage. Downgrade for vendor methodology changes or thin securities-lending availability.


#### Options implied volatility

- **Initial adoption stage:** Research until options source and IV methodology are confirmed.
- **Interpretation:** Measures market-implied uncertainty for the single name. It is especially relevant around earnings, litigation, FDA, M&A, and macro events.
- **Data sourcing:** Use OPRA or a licensed options vendor for quotes/trades and a validated IV surface. OCC data can support volume/open-interest context but is not a full quote surface.
- **Calculation methodology:**

```text
Select near-30-calendar-day expiry pair bracketing 30 days.
Calculate option mid = (bid + ask) / 2 using valid NBBO quotes.
Interpolate implied volatility to 30-day tenor and ATM forward moneyness.

atm_iv_30d = interpolated_ATM_IV
delta_atm_iv_points = atm_iv_30d_end - atm_iv_30d_start

contribution_bps = beta_atm_iv * delta_atm_iv_points
```

- **Application inside AAT:** Initially show as evidence of uncertainty repricing. Do not conflate IV contribution with stock return contribution unless a validated equity-return sensitivity to IV changes exists. Align quote timestamps to equity close.
- **Evidence payload:** `atm_iv_30d`, `expiry_selection`, `quote_timestamp`, `mid_quote_filters`, `delta_atm_iv_points`, `iv_model_version`.
- **Confidence and validation rules:** Downgrade for wide spreads, stale quotes, low option volume, hard-to-borrow distortions, earnings-term-structure effects, or unlicensed data.


#### IV change

- **Initial adoption stage:** Research/shadow; production only as a separately validated positioning factor.
- **Interpretation:** Captures the change in uncertainty premium over the attribution window.
- **Data sourcing:** Same source as options implied volatility. Use a stable tenor/moneyness definition such as 30-day ATM IV.
- **Calculation methodology:**

```text
iv_change_points = atm_iv_30d_end - atm_iv_30d_start
iv_change_pct = atm_iv_30d_end / atm_iv_30d_start - 1

contribution_bps = beta_iv_change * iv_change_points
```

- **Application inside AAT:** Use as event context. For example, a stock falling while IV rises may indicate risk-premium repricing; a stock rising while IV collapses may indicate event relief. Treat as evidence unless calibrated.
- **Evidence payload:** `iv_start`, `iv_end`, `iv_change_points`, `iv_change_pct`, `event_window_flag`.
- **Confidence and validation rules:** Downgrade when quote surfaces are sparse, the attribution window crosses earnings, or calendar interpolation is unstable.


#### Put-call skew

- **Initial adoption stage:** Research until options surface quality is validated.
- **Interpretation:** Measures relative demand for downside versus upside options and can flag hedging pressure or crash-risk repricing.
- **Data sourcing:** Use OPRA/vendor options surface with delta and maturity interpolation.
- **Calculation methodology:**

```text
put_25d_iv = interpolated_IV(delta=-25, tenor=30d)
call_25d_iv = interpolated_IV(delta=+25, tenor=30d)
skew_25d_points = put_25d_iv - call_25d_iv
delta_skew_points = skew_25d_points_end - skew_25d_points_start

contribution_bps = beta_skew * delta_skew_points
```

- **Application inside AAT:** Display as downside-risk evidence. Production contribution should require strong validation because skew changes often reflect hedging flow rather than fundamental return drivers.
- **Evidence payload:** `put_25d_iv`, `call_25d_iv`, `skew_25d_points`, `delta_skew_points`, `surface_quality_score`.
- **Confidence and validation rules:** Downgrade for sparse strikes, stale quotes, nonstandard expiries, or earnings/event term-structure distortions.


#### Options volume/open interest

- **Initial adoption stage:** Research/shadow after source confirmation.
- **Interpretation:** Captures option-market activity that may indicate positioning, hedging, or speculative flow.
- **Data sourcing:** Use OPRA/vendor trade data for volume and OCC/vendor data for open interest. Use timestamped data; open interest is generally end-of-day/next-day and must not be treated as intraday visible before publication.
- **Calculation methodology:**

```text
call_volume = sum(call_contract_volume over window)
put_volume = sum(put_contract_volume over window)
put_call_volume_ratio = put_volume / max(call_volume, epsilon)

call_oi = sum(call_open_interest)
put_oi = sum(put_open_interest)
put_call_oi_ratio = put_oi / max(call_oi, epsilon)

option_activity_score = zscore(total_option_volume / avg_option_volume_20d)
                      + zscore(abs(delta_open_interest) / float_shares)

contribution_bps = beta_option_activity * option_activity_score_change
```

- **Application inside AAT:** Use primarily as evidence. Open interest should affect same-day attribution only if its publication timestamp is before cutoff; otherwise it can support next-day or post-event analysis.
- **Evidence payload:** `call_volume`, `put_volume`, `put_call_volume_ratio`, `call_oi`, `put_oi`, `put_call_oi_ratio`, `option_activity_score`.
- **Confidence and validation rules:** Downgrade for complex multi-leg trades, data latency, corporate-action adjusted options, or if volume is high but economically small relative to market cap.


#### Dealer gamma exposure

- **Initial adoption stage:** Research only until methodology is validated.
- **Interpretation:** Estimates whether options dealer hedging could dampen or amplify stock moves. This is model-sensitive and should not be production until validated.
- **Data sourcing:** Use full option chain, open interest, Greeks, implied volatility surface, and assumptions about customer/dealer positioning from a licensed options source.
- **Calculation methodology:**

```text
For each option contract c:
  dollar_gamma_c = option_gamma_c * open_interest_c * contract_multiplier * spot_price^2 * 0.01

Dealer sign assumption:
  signed_gamma_c = dollar_gamma_c * assumed_dealer_position_sign_c

total_gex = sum(signed_gamma_c across contracts)
gex_pct_adv = total_gex / average_daily_dollar_volume
gamma_flip_level = spot level where estimated total_gex changes sign

contribution_bps = beta_gex * change_in_gex_pct_adv
  research only
```

- **Application inside AAT:** Keep out of production contribution. Use as research evidence with clear methodology labels and assumptions. Avoid showing false precision in dashboard until validation proves predictive/residual value.
- **Evidence payload:** `total_gex`, `gex_pct_adv`, `gamma_flip_level`, `dealer_sign_method`, `greeks_source`, `model_version`.
- **Confidence and validation rules:** Block production if dealer sign cannot be validated, open interest is stale, Greeks are vendor-black-box without audit, or assumptions dominate results.


#### ETF flow exposure

- **Initial adoption stage:** Research until ETF holdings/flow source is confirmed.
- **Interpretation:** Captures single-stock pressure from ETF creations/redemptions and sector/theme fund flows.
- **Data sourcing:** Use licensed ETF holdings, daily creation/redemption or fund-flow data, and point-in-time ETF constituent weights. Use public ETF holdings only where redistribution and historical access are allowed.
- **Calculation methodology:**

```text
For each ETF e holding stock i:
  stock_flow_dollars_i_e = ETF_net_flow_dollars_e * stock_weight_i_e

total_stock_flow_dollars_i = sum(stock_flow_dollars_i_e across ETFs)
flow_pct_adv = total_stock_flow_dollars_i / average_daily_dollar_volume_i
flow_pct_market_cap = total_stock_flow_dollars_i / market_cap_i

contribution_bps = price_impact_coefficient_i * flow_pct_adv
  or beta_etf_flow * ETF_flow_factor_move
```

- **Application inside AAT:** Use after market/sector factors because ETF flows often operate through sectors/themes. Evidence should show top contributing ETFs and whether flows are creations/redemptions or estimated secondary-market demand.
- **Evidence payload:** `top_etfs`, `etf_weights`, `etf_net_flows`, `total_stock_flow_dollars`, `flow_pct_adv`, `holdings_timestamp`.
- **Confidence and validation rules:** Downgrade for stale holdings, synthetic/derivative ETF exposure, overlapping ETF holdings, missing creation-redemption data, or unlicensed flow estimates.


## Priority 5 Calculation Methodologies: Event-Specific Drivers

Event-specific drivers should explain post-systematic residuals, not broad market or peer movement. They require event taxonomy, surprise metrics, materiality scoring, and historical event-study calibration before they become production contribution rows.

### Event-study calibration framework

For each event category:

```text
raw_stock_return_bps_event_window
  = 10000 * (price_after_event_window / price_before_event_window - 1)

expected_systematic_return_bps
  = market + sector + industry + peer + style + macro + positioning contributions

abnormal_return_bps = raw_stock_return_bps_event_window - expected_systematic_return_bps
```

Calibrate distributions by:

```text
event_category
event_subtype
sector/industry
market_cap_bucket
surprise_bucket
pre-event volatility bucket
clean-window flag
```

Only promote an event category to production contribution when the historical sample has enough observations, the sign and magnitude are stable out of sample, and event timestamps are reliable.

#### Earnings EPS surprise

- **Initial adoption stage:** Research/evidence-only until estimates source is licensed; production contribution after event-study calibration.
- **Interpretation:** Measures whether reported EPS beat or missed market expectations.
- **Data sourcing:** Use reported EPS from company release/8-K/10-Q/10-K and consensus EPS from a licensed estimates vendor. Store estimate vintage visible immediately before the earnings release.
- **Calculation methodology:**

```text
eps_surprise = reported_eps - consensus_eps
eps_surprise_pct = eps_surprise / max(abs(consensus_eps), eps_floor)
eps_surprise_std = eps_surprise / max(consensus_eps_dispersion, dispersion_floor)

event_strength = abs(eps_surprise_std) * relevance * source_credibility * novelty

calibrated_event_bps = f_event_study("earnings_eps", sector, market_cap_bucket, surprise_bucket)
                     * sign(eps_surprise)

event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Apply only after systematic factors. If revenue/guidance surprises conflict with EPS surprise, aggregate through an earnings-event composite instead of separate overclaiming rows.
- **Evidence payload:** `reported_eps`, `consensus_eps`, `estimate_vintage_time`, `eps_surprise_pct`, `eps_surprise_std`, `earnings_event_id`.
- **Confidence and validation rules:** Downgrade for non-GAAP/GAAP mismatch, one-time items, stale consensus, thin estimate count, or after-hours timing ambiguity.


#### Revenue surprise

- **Initial adoption stage:** Research/evidence-only until estimates source is licensed; production after calibration.
- **Interpretation:** Measures whether reported revenue exceeded or missed consensus expectations.
- **Data sourcing:** Use reported revenue from company release/filings and consensus revenue from licensed estimates. Use point-in-time consensus as of before release.
- **Calculation methodology:**

```text
revenue_surprise = reported_revenue - consensus_revenue
revenue_surprise_pct = revenue_surprise / max(abs(consensus_revenue), revenue_floor)
revenue_surprise_std = revenue_surprise / max(consensus_revenue_dispersion, dispersion_floor)

calibrated_event_bps = f_event_study("revenue_surprise", sector, growth_bucket, surprise_bucket)
                     * sign(revenue_surprise)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Treat as part of earnings composite when same event includes EPS, margin, and guidance. For companies valued on revenue growth, revenue surprise should often receive higher materiality weight than EPS.
- **Evidence payload:** `reported_revenue`, `consensus_revenue`, `revenue_surprise_pct`, `revenue_surprise_std`, `estimate_count`.
- **Confidence and validation rules:** Downgrade for acquisitions/divestitures, FX translation effects, fiscal period mismatch, or low consensus coverage.


#### Gross margin surprise

- **Initial adoption stage:** Research/evidence-only; production after calibration by sector.
- **Interpretation:** Measures whether revenue quality and input-cost/price realization were better or worse than expected.
- **Data sourcing:** Use reported revenue and COGS/gross profit from filings/releases. Use consensus gross margin where licensed; otherwise compare to prior period/year but mark lower confidence.
- **Calculation methodology:**

```text
actual_gross_margin_pct = gross_profit / revenue
expected_gross_margin_pct = consensus_gross_margin_pct
  or prior_year_gross_margin_pct if no consensus is available

gross_margin_surprise_pp = (actual_gross_margin_pct - expected_gross_margin_pct) * 100

calibrated_event_bps = f_event_study("gross_margin_surprise", sector, surprise_bucket)
                     * sign(gross_margin_surprise_pp)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Use inside the earnings-event composite. Margin surprises are especially important for software, semis, consumer, industrials, restaurants, and retailers.
- **Evidence payload:** `actual_gross_margin`, `expected_gross_margin`, `gross_margin_surprise_pp`, `comparison_type=consensus|prior`.
- **Confidence and validation rules:** Downgrade when consensus margin is missing, COGS classification differs, revenue includes unusual items, or prior-period comparison is used instead of consensus.


#### Operating margin surprise

- **Initial adoption stage:** Research/evidence-only; production after calibration.
- **Interpretation:** Measures whether operating leverage, expense discipline, or cost pressure differed from expectations.
- **Data sourcing:** Use reported operating income and revenue from filings/releases. Use consensus operating margin/EBIT margin where licensed.
- **Calculation methodology:**

```text
actual_operating_margin_pct = operating_income / revenue
expected_operating_margin_pct = consensus_operating_margin_pct
  or prior_year_operating_margin_pct if no consensus exists

operating_margin_surprise_pp = (actual_operating_margin_pct - expected_operating_margin_pct) * 100

calibrated_event_bps = f_event_study("operating_margin_surprise", sector, surprise_bucket)
                     * sign(operating_margin_surprise_pp)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Apply within earnings composite. Use higher materiality when revenue surprise is small but margin surprise is large because the event explains quality of earnings.
- **Evidence payload:** `actual_operating_margin`, `expected_operating_margin`, `operating_margin_surprise_pp`, `expense_line_items`.
- **Confidence and validation rules:** Downgrade for restructuring charges, stock-based compensation adjustments, GAAP/non-GAAP mismatch, or segment reclassifications.


#### Guidance raise/cut

- **Initial adoption stage:** Research/evidence-only until guidance parsing and estimates source are validated; likely high-value production event after calibration.
- **Interpretation:** Measures whether management changed forward outlook relative to prior guidance or consensus.
- **Data sourcing:** Use company release/transcript/8-K for guidance. Use licensed consensus estimates immediately before guidance. Store parsed metric, period, range low/high, midpoint, and units.
- **Calculation methodology:**

```text
guidance_midpoint = (guidance_low + guidance_high) / 2
consensus_forward_metric = consensus_value_for_same_metric_period

guidance_surprise_pct = (guidance_midpoint - consensus_forward_metric)
                      / max(abs(consensus_forward_metric), metric_floor)

guidance_change_vs_prior_pct = (new_guidance_midpoint - prior_guidance_midpoint)
                              / max(abs(prior_guidance_midpoint), metric_floor)

guidance_direction = sign(weighted_average(guidance_surprise_pct, guidance_change_vs_prior_pct))

calibrated_event_bps = f_event_study("guidance", metric_type, sector, direction_bucket, magnitude_bucket)
                     * guidance_direction
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Guidance should often dominate EPS/revenue surprise if it conflicts with backward-looking results. Combine revenue, EPS, margin, and guidance into one earnings-event package when they share the same timestamp.
- **Evidence payload:** `guidance_metric`, `period`, `low`, `high`, `midpoint`, `consensus_value`, `prior_guidance`, `guidance_surprise_pct`, `parser_confidence`.
- **Confidence and validation rules:** Downgrade for ambiguous text, incomparable metric definitions, annual versus quarterly mismatch, withdrawn guidance, or low parser confidence.


#### Estimate revision

- **Initial adoption stage:** Research until licensed estimates source is confirmed; production for multi-day drift after calibration.
- **Interpretation:** Measures sell-side consensus changes after new information, often explaining post-event drift rather than just the event-day move.
- **Data sourcing:** Use licensed consensus estimate histories with vintage timestamps and estimate counts. Track EPS, revenue, EBITDA, FCF, and target-period revisions.
- **Calculation methodology:**

```text
consensus_before = latest_consensus_value before event_time
consensus_after = latest_consensus_value as of attribution_cutoff

estimate_revision_pct = (consensus_after - consensus_before)
                      / max(abs(consensus_before), metric_floor)

estimate_revision_breadth = number_of_upward_revisions - number_of_downward_revisions
                           divided by active_analyst_count

contribution_bps = beta_estimate_revision * estimate_revision_pct
  or calibrated_event_bps from revision buckets
```

- **Application inside AAT:** Use in event layer for windows after the initial event. Avoid using revisions published after cutoff. For same-day attribution, include only if revision timestamp is before the cutoff.
- **Evidence payload:** `metric`, `period`, `consensus_before`, `consensus_after`, `revision_pct`, `revision_breadth`, `estimate_vintage_times`.
- **Confidence and validation rules:** Downgrade for low analyst count, delayed vendor timestamps, stale consensus, or revisions caused by mechanical roll-forward rather than new information.


#### Price target revision

- **Initial adoption stage:** Research/evidence-only until licensed analyst source is confirmed.
- **Interpretation:** Measures analyst target-price changes, useful as evidence but less pure than estimate revisions because targets include valuation-multiple judgment.
- **Data sourcing:** Use licensed analyst research/estimate vendor. Store analyst, firm, previous target, new target, timestamp, and whether the note was published before cutoff.
- **Calculation methodology:**

```text
target_revision_pct = (new_price_target - old_price_target) / max(abs(old_price_target), target_floor)
target_implied_upside_after = new_price_target / prior_stock_price - 1
consensus_target_change_pct = (consensus_target_after - consensus_target_before) / consensus_target_before

evidence_score = abs(target_revision_pct) * analyst_credibility_weight * novelty

calibrated_event_bps = f_event_study("price_target_revision", direction_bucket, magnitude_bucket)
                     * sign(target_revision_pct)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Usually show as supporting evidence, not a standalone contribution, unless the target revision is the main visible event and calibration supports attribution.
- **Evidence payload:** `analyst_firm`, `old_target`, `new_target`, `target_revision_pct`, `consensus_target_change_pct`, `publication_timestamp`.
- **Confidence and validation rules:** Downgrade for stale analyst, low credibility, target revision without estimate change, or source licensing limits.


#### Rating change

- **Initial adoption stage:** Research/evidence-only until licensed analyst source is confirmed.
- **Interpretation:** Captures upgrades, downgrades, initiations, and coverage drops that can move stocks, especially when unexpected.
- **Data sourcing:** Use licensed analyst ratings feed. Normalize ratings to a vendor-independent ordinal scale.
- **Calculation methodology:**

```text
rating_ordinal: sell=1, underperform=2, hold=3, buy=4, strong_buy=5
rating_delta = new_rating_ordinal - old_rating_ordinal

rating_event_score = rating_delta * analyst_credibility_weight * novelty * coverage_importance

calibrated_event_bps = f_event_study("rating_change", rating_delta_bucket, firm_credibility_bucket)
                     * sign(rating_delta)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Display as event evidence. Production contribution should require high-quality timestamp and historical calibration. Initiations need separate treatment because `old_rating` is missing.
- **Evidence payload:** `old_rating`, `new_rating`, `rating_delta`, `analyst_firm`, `initiation_flag`, `publication_timestamp`.
- **Confidence and validation rules:** Downgrade for rating scale mismatches, rumor-based data, bundled rating/target/estimate changes, or timestamp uncertainty.


#### Management change

- **Initial adoption stage:** Evidence-only, then shadow after category calibration.
- **Interpretation:** Captures CEO, CFO, board, founder, or key executive changes that alter execution risk or strategic expectations.
- **Data sourcing:** Use 8-K item codes, company releases, proxy filings, and licensed news feeds. Parse role, departure type, successor status, effective date, and reason language.
- **Calculation methodology:**

```text
role_weight = CEO:1.00, CFO:0.80, COO:0.50, board_chair:0.50, other:0.25
departure_type_weight = sudden:1.00, planned:0.35, retirement:0.25, for_cause:1.00, unknown:0.60
successor_weight = no_successor:1.00, interim:0.75, permanent_internal:0.35, permanent_external:0.50

management_change_score = role_weight * departure_type_weight * successor_weight * source_credibility

event_direction = analyst_curated or taxonomy-derived; default unknown
calibrated_event_bps = f_event_study("management_change", role, departure_type, direction_bucket)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Keep evidence-only unless direction is clear or calibrated. Trigger exposure/profile review when management change affects stated strategy or business mix.
- **Evidence payload:** `role`, `departure_type`, `successor_status`, `effective_date`, `8k_item`, `management_change_score`, `direction_confidence`.
- **Confidence and validation rules:** Downgrade for routine retirements, vague reasons, no return reaction in clean historical samples, or low parser confidence.


#### M&A announcement

- **Initial adoption stage:** Evidence-only, then shadow; production requires separate target/acquirer methodology.
- **Interpretation:** Captures deal announcements, rumors confirmed by filings/releases, merger termination, revised terms, and regulatory deal outcomes.
- **Data sourcing:** Use 8-K, merger agreements, press releases, regulatory filings, and licensed news. Parse acquirer/target role, consideration, deal value, offer price, cash/stock mix, collars, expected close, and conditions.
- **Calculation methodology:**

```text
For target:
  deal_premium_pct = offer_price_per_share / unaffected_price - 1
  deal_spread_pct = offer_price_per_share / target_current_price - 1

For acquirer:
  relative_deal_size = enterprise_value_of_target / acquirer_market_cap
  stock_consideration_pct = stock_value / total_consideration
  pro_forma_leverage_change = pro_forma_net_debt_to_ebitda - current_net_debt_to_ebitda

mna_materiality_score = relative_deal_size or deal_premium_pct adjusted by completion_probability

calibrated_event_bps = f_event_study("mna", role, consideration_type, materiality_bucket)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Use different logic for acquirer, target, and peer read-through. Do not mix target deal premium with acquirer synergy/leverage logic. Deal rumors should remain evidence-only unless confirmed and timestamped.
- **Evidence payload:** `deal_role`, `deal_value`, `offer_price`, `unaffected_price`, `deal_premium_pct`, `consideration_mix`, `completion_probability`, `source_doc_id`.
- **Confidence and validation rules:** Downgrade for rumor-only events, unclear unaffected price, competing bids, collars, regulatory uncertainty, or late-day announcement timing.


#### Buyback announcement

- **Initial adoption stage:** Evidence-only, then shadow; production after calibration by size and sector.
- **Interpretation:** Measures capital-return authorization or acceleration that can support equity value or signal management confidence.
- **Data sourcing:** Use 8-K, 10-Q/10-K, press releases, and board authorization disclosures. Actual repurchase execution can be sourced from filings but is delayed.
- **Calculation methodology:**

```text
authorization_pct_market_cap = authorized_buyback_amount / market_cap_prior_close
incremental_authorization_pct = max(0, new_authorization - remaining_prior_authorization) / market_cap
expected_execution_intensity = authorization_pct_market_cap / stated_execution_months

calibrated_event_bps = f_event_study("buyback_announcement", size_bucket, sector)
                     * positive_direction
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Apply in event layer after systematic factors. Treat announcement separately from actual buybacks. For financials, check regulatory capital constraints before assigning high materiality.
- **Evidence payload:** `authorized_amount`, `market_cap`, `authorization_pct_market_cap`, `remaining_prior_authorization`, `execution_period`, `board_approval_date`.
- **Confidence and validation rules:** Downgrade for small authorizations, no execution commitment, stale authorization refreshes, or simultaneous negative earnings guidance.


#### Dividend change

- **Initial adoption stage:** Evidence-only, then shadow; production after calibration.
- **Interpretation:** Captures dividend raises, cuts, suspensions, initiations, and special dividends.
- **Data sourcing:** Use corporate actions/dividend feed and company announcements. Separate regular and special dividends.
- **Calculation methodology:**

```text
regular_dividend_change_pct = (new_regular_dividend - prior_regular_dividend)
                            / max(abs(prior_regular_dividend), dividend_floor)
dividend_yield_change_pp = (new_annualized_dividend / prior_price
                          - prior_annualized_dividend / prior_price) * 100

event_direction = sign(regular_dividend_change_pct)
  except special dividends handled separately

calibrated_event_bps = f_event_study("dividend_change", event_type, yield_bucket, magnitude_bucket)
                     * event_direction
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Apply as event, not just style. For dividend cuts/suspensions, materiality should be high for income stocks and financial distress contexts.
- **Evidence payload:** `prior_dividend`, `new_dividend`, `regular_or_special`, `dividend_change_pct`, `yield_change_pp`, `declaration_timestamp`.
- **Confidence and validation rules:** Downgrade for special dividends, spinoff-related payouts, currency effects for ADRs, or unclear regular dividend baseline.


#### Insider activity

- **Initial adoption stage:** Evidence-only with existing EDGAR Form 4; shadow after filters/calibration.
- **Interpretation:** Captures insider purchases/sales that may signal management confidence or liquidity/compensation behavior.
- **Data sourcing:** Use SEC Form 4 filings from EDGAR. Parse transaction code, role, amount, price, ownership after transaction, 10b5-1 indication where available, and derivative/non-derivative status.
- **Calculation methodology:**

```text
transaction_value = shares_transacted * transaction_price
transaction_pct_market_cap = transaction_value / market_cap
ownership_change_pct = shares_transacted / shares_owned_before

open_market_purchase_flag = transaction_code in [P]
open_market_sale_flag = transaction_code in [S] and not purely tax/option exercise if identifiable

role_weight = CEO:1.0, CFO:0.8, director:0.5, other_officer:0.4
insider_signal = direction_sign * role_weight * log1p(transaction_value)
               * novelty * open_market_quality_weight

calibrated_event_bps = f_event_study("insider_activity", buy_sell, role_bucket, size_bucket)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Show as evidence. Insider selling should usually have lower negative weight than open-market buying because many sales are routine. Filter planned, tax, option-exercise, and small transactions.
- **Evidence payload:** `form4_accession`, `transaction_code`, `insider_role`, `transaction_value`, `ownership_change_pct`, `10b5_1_flag`, `open_market_quality_weight`.
- **Confidence and validation rules:** Downgrade for derivative transactions, planned sales, small size, delayed filing, clustered routine sales, or unclear beneficial ownership.


#### Activist filing

- **Initial adoption stage:** Evidence-only with 13D/G support; shadow after calibration.
- **Interpretation:** Captures activist ownership, governance pressure, strategic optionality, or passive ownership changes.
- **Data sourcing:** Use SEC Schedule 13D/13G and amendments. Store holder identity, ownership percentage, amendment type, purpose language, and prior ownership.
- **Calculation methodology:**

```text
ownership_pct = shares_beneficially_owned / shares_outstanding
ownership_change_pct = ownership_pct - prior_reported_ownership_pct
activist_flag = filing_type == "13D" or known_activist_holder == true

activist_score = ownership_pct * activist_credibility_weight * activist_flag_weight * novelty

calibrated_event_bps = f_event_study("activist_filing", filing_type, ownership_bucket, credibility_bucket)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Apply as event evidence. 13G passive filings should usually have lower materiality than 13D activist filings. Amendments should be evaluated by ownership change and stated purpose.
- **Evidence payload:** `accession`, `filing_type`, `holder`, `ownership_pct`, `ownership_change_pct`, `activist_flag`, `purpose_text_span`.
- **Confidence and validation rules:** Downgrade for passive/index holders, stale ownership due to reporting lag, ambiguous group formation, or amendments with no material ownership change.


#### Regulatory/legal event

- **Initial adoption stage:** Evidence-only, then shadow by sector-specific calibration.
- **Interpretation:** Captures lawsuits, settlements, investigations, consent orders, antitrust actions, environmental penalties, rate-case outcomes, and agency actions.
- **Data sourcing:** Use 8-K, 10-Q/10-K legal contingencies, regulator websites, court filings, press releases, and licensed legal/news feeds. Healthcare regulatory events may use FDA/openFDA sources.
- **Calculation methodology:**

```text
known_penalty_pct_market_cap = penalty_amount / market_cap
reserve_change_pct_equity = legal_reserve_change / book_equity
revenue_at_risk_pct = affected_product_or_region_revenue / total_revenue

severity_score = weighted_average(
  penalty_pct_market_cap_z,
  revenue_at_risk_pct_z,
  stage_weight,
  regulator_credibility_weight,
  novelty
)

calibrated_event_bps = f_event_study("regulatory_legal", sector, subtype, severity_bucket)
                     * direction_sign
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Gate by regulatory exposure. Separate financial penalties, conduct restrictions, product bans, approvals, and litigation milestones because return distributions differ.
- **Evidence payload:** `regulator`, `case_id`, `subtype`, `penalty_amount`, `revenue_at_risk_pct`, `stage`, `severity_score`, `source_url_or_accession`.
- **Confidence and validation rules:** Downgrade for unquantified allegations, rumor-only litigation, duplicative filings, unclear jurisdiction, or low exposure match.


#### Product launch

- **Initial adoption stage:** Evidence-only until source-specific adapters and calibration are available.
- **Interpretation:** Captures announced product launches, launch delays, pricing, availability, early demand, or competitive product updates.
- **Data sourcing:** Use company releases, investor presentations, product pages, regulatory product notices, app/store data where licensed, and news feeds. For autos/tech/consumer, source specificity matters.
- **Calculation methodology:**

```text
product_revenue_opportunity_pct = expected_product_revenue / current_revenue
product_margin_delta = expected_product_margin - company_average_margin
launch_timing_score = on_time_or_accelerated ? positive : delayed ? negative : neutral
competitive_intensity_score = competitor_launch_overlap_adjustment

product_event_score = product_revenue_opportunity_pct
                    * margin_relevance
                    * launch_timing_score
                    * source_credibility
                    * novelty

calibrated_event_bps = f_event_study("product_launch", sector, product_materiality_bucket, direction_bucket)
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Gate by product-cycle exposure and segment revenue. Use as evidence unless expected revenue or product materiality is quantified and calibrated.
- **Evidence payload:** `product_name`, `launch_date`, `segment`, `expected_revenue`, `revenue_opportunity_pct`, `launch_timing_score`, `source_span`.
- **Confidence and validation rules:** Downgrade for marketing-only announcements, unquantified product claims, low segment exposure, or source credibility below threshold.


#### FDA/clinical event

- **Initial adoption stage:** Evidence-only, then shadow for biotech/pharma after event taxonomy and calibration.
- **Interpretation:** Captures trial results, approvals, complete response letters, PDUFA outcomes, label changes, safety warnings, and clinical holds.
- **Data sourcing:** Use FDA press releases/databases, openFDA, company releases/8-Ks, ClinicalTrials.gov, and licensed healthcare event/estimates sources. Store product, indication, phase, endpoint, and regulatory milestone.
- **Calculation methodology:**

```text
asset_materiality_pct = estimated_asset_NPV / company_market_cap
  or affected_product_revenue / total_revenue for marketed products

clinical_outcome_score = endpoint_met_weight * safety_weight * statistical_strength * comparator_relevance
regulatory_outcome_score = approval:positive, CRL:negative, hold:negative, label_expansion:positive

event_surprise = actual_outcome_probability_adjusted - pre_event_expected_probability
  where pre_event probability may come from analyst consensus/manual healthcare model

calibrated_event_bps = f_event_study("fda_clinical", phase_or_regulatory_type, asset_materiality_bucket, outcome_bucket)
                     * direction_sign
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Gate by product-cycle and healthcare exposure. Biotech/pharma event returns can dominate daily attribution, but AAT must still remove market/sector/peer biotech moves first.
- **Evidence payload:** `drug_or_device`, `indication`, `phase`, `nct_id`, `pdufa_date`, `endpoint_result`, `asset_materiality_pct`, `clinical_outcome_score`.
- **Confidence and validation rules:** Downgrade for ambiguous endpoints, small samples, non-controlled trials, company-only interpretation without underlying data, or missing asset materiality.


#### Contract win/loss

- **Initial adoption stage:** Evidence-only, then shadow for sectors with disclosed contract economics.
- **Interpretation:** Captures announced customer wins/losses, renewals, backlog changes, and awarded contracts.
- **Data sourcing:** Use company releases, 8-Ks, government procurement portals, defense contract databases, customer announcements, and licensed news. Parse customer, value, duration, margin relevance, and whether contract is new or renewal.
- **Calculation methodology:**

```text
annualized_contract_value = total_contract_value / contract_duration_years
contract_value_pct_revenue = annualized_contract_value / revenue_ttm
contract_value_pct_market_cap = total_contract_value / market_cap
margin_adjusted_contract_value = annualized_contract_value * expected_margin

contract_event_score = contract_value_pct_revenue * margin_confidence * novelty * customer_quality_weight

calibrated_event_bps = f_event_study("contract_win_loss", sector, size_bucket, win_loss_flag)
                     * direction_sign
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Gate by customer concentration and segment exposure. Avoid high contribution for framework agreements with no committed value.
- **Evidence payload:** `customer`, `contract_value`, `duration`, `annualized_value`, `contract_value_pct_revenue`, `win_loss_flag`, `source_doc`.
- **Confidence and validation rules:** Downgrade for undisclosed value, non-binding awards, recompete renewals, low margin visibility, or government protest risk.


#### Cyber/security incident

- **Initial adoption stage:** Evidence-only initially; shadow after severity taxonomy and calibration.
- **Interpretation:** Captures data breaches, ransomware, operational outages, cyber disclosure, and related regulatory/customer impacts.
- **Data sourcing:** Use company 8-K cybersecurity disclosures, regulator notices, company statements, trusted incident databases, and licensed cyber/news feeds. Parse incident date, discovery date, disclosure date, affected records/systems, downtime, and financial impact.
- **Calculation methodology:**

```text
affected_records_score = log1p(affected_records) if known
downtime_score = downtime_hours / sector_relevant_threshold
estimated_cost_pct_market_cap = estimated_incident_cost / market_cap
revenue_at_risk_pct = affected_customer_or_product_revenue / total_revenue

cyber_severity_score = weighted_average(
  affected_records_score,
  downtime_score,
  estimated_cost_pct_market_cap_z,
  revenue_at_risk_pct_z,
  regulatory_exposure_weight
)

calibrated_event_bps = f_event_study("cyber_incident", sector, severity_bucket)
                     * negative_direction
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Apply as event evidence. Also trigger exposure review if cyber risk is persistent or materially affects product/customer trust.
- **Evidence payload:** `incident_type`, `disclosure_timestamp`, `affected_records`, `downtime_hours`, `estimated_cost`, `cyber_severity_score`.
- **Confidence and validation rules:** Downgrade for rumor-only incidents, unconfirmed record counts, third-party vendor incidents with unclear exposure, or delayed disclosure ambiguity.


#### Accounting/restatement

- **Initial adoption stage:** Evidence-only, then shadow; likely high-materiality event once parsed.
- **Interpretation:** Captures restatements, auditor changes, internal-control weaknesses, delayed filings, and accounting irregularities.
- **Data sourcing:** Use 8-K items, 10-K/10-Q amendments, auditor letters, NT filings, SEC comment letters where available, and company disclosures.
- **Calculation methodology:**

```text
restated_income_pct = abs(restated_net_income_change) / max(abs(previous_net_income), income_floor)
restated_revenue_pct = abs(restated_revenue_change) / revenue
equity_impact_pct = abs(restatement_equity_change) / book_equity
filing_delay_days = actual_filing_date - expected_filing_date

accounting_severity_score = weighted_average(
  restated_income_pct_z,
  restated_revenue_pct_z,
  equity_impact_pct_z,
  material_weakness_flag,
  auditor_resignation_flag,
  filing_delay_days_z
)

calibrated_event_bps = f_event_study("accounting_restatement", severity_bucket, market_cap_bucket)
                     * negative_direction
event_contribution_bps = residual_allocator(calibrated_event_bps, residual_after_systematic_bps)
```

- **Application inside AAT:** Apply after systematic factors; often a direct explanation for negative residuals. Trigger exposure/profile review if accounting issue changes quality or risk profile.
- **Evidence payload:** `filing_type`, `restatement_flag`, `auditor_change_flag`, `material_weakness_flag`, `restated_amounts`, `accounting_severity_score`.
- **Confidence and validation rules:** Downgrade for immaterial amendments, taxonomy-only filing corrections, unclear amounts, or duplicated announcements across filings.


## Priority 6 Calculation Methodologies: Company Exposure Profile

Company exposure attributes are gates and weights. They should control factor eligibility, materiality, expected sign, confidence, and exposure-review decisions. They should not appear as standalone daily return contributions.

#### Geographic revenue exposure

- **Initial adoption stage:** Production as gate after curated/PIT source exists; not a standalone daily contribution.
- **Interpretation:** Determines whether FX, regional macro, tariff, geopolitical, or country-specific peer/event factors should be considered.
- **Data sourcing:** Use SEC segment/geographic disclosures, 10-K/10-Q notes, XBRL where available, company annual reports, and licensed fundamentals. Use analyst-curated mappings for MVP with source spans.
- **Calculation methodology:**

```text
region_revenue_pct = revenue_region / total_revenue
country_revenue_pct = revenue_country / total_revenue

Map countries to macro/FX regions:
  USD, EUR, CNY, JPY, EM, China, Europe, North America, etc.

geo_gate_weight_region = min(1, region_revenue_pct / gate_threshold_pct)
  default gate_threshold_pct = 10%

net_region_exposure = region_revenue_pct - region_cost_pct - hedged_region_pct if costs/hedges are available
```

- **Application inside AAT:** Use as a gate/weight for dollar index, local currency baskets, regional macro factors, tariff events, and regional regulatory events. Do not display as a return contribution by itself.
- **Evidence payload:** `region`, `country`, `revenue_pct`, `cost_pct`, `hedge_pct`, `source_filing`, `fiscal_period`, `geo_gate_weight`.
- **Confidence and validation rules:** Downgrade if geographic disclosure is stale, broad region only, totals do not reconcile to revenue, or segment definitions changed.


#### Segment revenue exposure

- **Initial adoption stage:** Production as gate after segment taxonomy is approved.
- **Interpretation:** Maps the company’s business lines to relevant industries, peers, commodities, products, and events.
- **Data sourcing:** Use company segment disclosures, 10-K/10-Q, XBRL, investor presentations as supporting evidence, and licensed fundamentals for standardized segments. Store analyst-curated segment-to-factor mappings.
- **Calculation methodology:**

```text
segment_revenue_pct = segment_revenue / total_revenue
segment_profit_pct = segment_operating_income / total_operating_income if available

segment_factor_weight = weighted_average(segment_revenue_pct, segment_profit_pct, weights=[0.7, 0.3])
  if profit data is available; otherwise use revenue_pct

factor_gate_weight = sum(segment_factor_weight for segments mapped to factor)
```

- **Application inside AAT:** Use to weight peer baskets, industry factors, commodity factors, product-cycle events, and customer/contract materiality. A multi-segment company may receive multiple gates with weights.
- **Evidence payload:** `segment_name`, `segment_revenue`, `segment_profit`, `segment_revenue_pct`, `mapped_factor_ids`, `gate_weight`.
- **Confidence and validation rules:** Downgrade when segment disclosures are qualitative, renamed, restated, or do not reconcile. Require source spans for manual mappings.


#### Customer concentration

- **Initial adoption stage:** Production as event/read-through gate when disclosed; otherwise curated research.
- **Interpretation:** Determines whether a customer’s news, contract win/loss, bankruptcy, supply-chain issue, or demand change should affect the target.
- **Data sourcing:** Use SEC major-customer disclosures, 10-K/10-Q notes, customer concentration tables, supplier/customer mapping vendors, and analyst-curated data. Many disclosures only identify customers above 10% or anonymize them.
- **Calculation methodology:**

```text
customer_revenue_pct = revenue_from_customer / total_revenue
known_customer_flag = customer_name_disclosed is not null
concentration_score = max_customer_revenue_pct + sum(top_customer_revenue_pct) * diversification_adjustment

customer_event_gate_weight = min(1, customer_revenue_pct / gate_threshold_pct)
  default gate_threshold_pct = 5% for named customers, 10% for unnamed concentration
```

- **Application inside AAT:** Gate customer event read-through and contract loss/win materiality. If a named customer has a material event, multiply read-through score by customer revenue percentage and source credibility.
- **Evidence payload:** `customer_name`, `customer_revenue_pct`, `named_or_anonymous`, `source_filing`, `fiscal_period`, `customer_event_gate_weight`.
- **Confidence and validation rules:** Downgrade for anonymous customers, stale annual-only disclosure, customer name changes, or if exposure may have changed after filing.


#### Supplier concentration

- **Initial adoption stage:** Research/curated gate; production only for sectors with reliable supply-chain data.
- **Interpretation:** Determines whether supplier disruptions, shortages, bankruptcies, or price changes should matter for the target.
- **Data sourcing:** Use company filings, supplier disclosures, customs/supply-chain vendors, procurement databases, industry knowledge, and analyst-curated mappings. Public filings often do not quantify supplier percentage.
- **Calculation methodology:**

```text
supplier_cost_pct = purchases_from_supplier / total_cogs_or_procurement
  if disclosed

supplier_dependency_score = supplier_cost_pct
                          * substitutability_weight
                          * critical_component_weight
                          * geographic_risk_weight

supplier_event_gate_weight = min(1, supplier_dependency_score / threshold)
```

- **Application inside AAT:** Gate supplier read-through events and supply-disruption narratives. Use as evidence if numeric cost share is unknown; require lower confidence.
- **Evidence payload:** `supplier_name`, `supplier_cost_pct`, `component`, `substitutability`, `criticality`, `supplier_event_gate_weight`, `source_span`.
- **Confidence and validation rules:** Downgrade for unquantified relationships, outdated supplier lists, diversified supplier bases, or low criticality.


#### Commodity input exposure

- **Initial adoption stage:** Production gate for commodity macro factors once signed exposure is curated.
- **Interpretation:** Separates commodity producers from consumers and determines expected sign for WTI, natural gas, gold, copper, agricultural commodities, or refined-product proxies.
- **Data sourcing:** Use segment revenue, COGS disclosures, hedging notes, sensitivity tables, commodity reserves/production data, and analyst-curated exposure maps.
- **Calculation methodology:**

```text
producer_exposure_pct = commodity_linked_revenue / total_revenue
consumer_input_pct = commodity_input_cost / total_cogs
hedge_coverage_pct = hedged_volume_or_cost / exposed_volume_or_cost

signed_commodity_exposure = producer_exposure_pct - consumer_input_pct
hedge_adjusted_exposure = signed_commodity_exposure * (1 - hedge_coverage_pct)

commodity_gate_weight = min(1, abs(hedge_adjusted_exposure) / gate_threshold_pct)
expected_sign = sign(hedge_adjusted_exposure)
```

- **Application inside AAT:** Use to gate WTI, gas, gold, copper, and sector-specific commodity factors. Expected sign is evidence only; estimated beta remains the contribution coefficient unless unstable.
- **Evidence payload:** `commodity`, `producer_exposure_pct`, `consumer_input_pct`, `hedge_coverage_pct`, `expected_sign`, `commodity_gate_weight`.
- **Confidence and validation rules:** Downgrade for pass-through contracts, regulated cost recovery, hedges, mixed producer/consumer exposure, or absent cost disclosures.


#### Interest-rate exposure

- **Initial adoption stage:** Production gate after balance-sheet metrics are stable.
- **Interpretation:** Determines relevance and expected channel for 2Y, 10Y, curve, mortgage-rate, and policy-expectation factors.
- **Data sourcing:** Use debt footnotes, floating/fixed-rate debt disclosures, cash/debt levels, bank net-interest-income sensitivity, REIT duration data, and licensed fundamentals.
- **Calculation methodology:**

```text
floating_rate_debt_pct = floating_rate_debt / total_debt
net_debt_pct_market_cap = (total_debt - cash) / market_cap
interest_expense_pct_ebit = interest_expense / max(abs(EBIT), ebit_floor)

For banks:
  nii_sensitivity_score = disclosed_NII_change_per_100bp / tangible_equity

rate_exposure_score = weighted_average(
  floating_rate_debt_pct,
  net_debt_pct_market_cap,
  interest_expense_pct_ebit,
  duration_or_nii_sensitivity
)

rate_gate_weight = min(1, abs(rate_exposure_score) / threshold)
```

- **Application inside AAT:** Gate rate and curve factors. For banks/insurers, curve and NII may have positive sensitivity; for levered companies and long-duration equities, higher rates often have negative sensitivity. Use beta estimates to resolve sign.
- **Evidence payload:** `floating_rate_debt_pct`, `net_debt`, `interest_coverage`, `nii_sensitivity`, `rate_exposure_score`, `rate_gate_weight`.
- **Confidence and validation rules:** Downgrade for missing debt maturity data, financial-sector metrics that require special treatment, or stale balance-sheet disclosures.


#### Credit exposure

- **Initial adoption stage:** Production gate for credit-spread factors after leverage data is stable.
- **Interpretation:** Determines whether HY/IG spread moves should affect the stock and whether credit stress is a plausible residual driver.
- **Data sourcing:** Use debt, EBITDA, interest coverage, ratings, bond spreads/CDS where licensed, maturity schedule, and financial-sector credit asset exposure.
- **Calculation methodology:**

```text
net_debt_to_ebitda = (total_debt - cash) / EBITDA
interest_coverage = EBIT / interest_expense
debt_maturity_wall_pct = debt_due_next_3y / total_debt
rating_score = normalized_credit_rating if available

credit_exposure_score = average(
  zscore(net_debt_to_ebitda),
  -zscore(interest_coverage),
  zscore(debt_maturity_wall_pct),
  -zscore(rating_score)
)

credit_gate_weight = min(1, sigmoid(credit_exposure_score))
```

- **Application inside AAT:** Gate HY/IG spread factors and credit-related event materiality. For financials, use asset credit quality and funding spread indicators rather than generic debt/EBITDA.
- **Evidence payload:** `net_debt_to_ebitda`, `interest_coverage`, `maturity_wall`, `rating`, `credit_exposure_score`, `credit_gate_weight`.
- **Confidence and validation rules:** Downgrade for negative EBITDA, no rating, stale maturities, financial-sector mismatch, or off-balance-sheet liabilities not captured.


#### Regulatory exposure

- **Initial adoption stage:** Production gate after taxonomy/source spans are curated.
- **Interpretation:** Determines whether regulatory/legal events should be relevant and how much weight they receive.
- **Data sourcing:** Use industry taxonomy, geographic revenue, licenses/permits, regulated segment revenue, agency jurisdiction, filings, and analyst-curated mappings.
- **Calculation methodology:**

```text
regulated_revenue_pct = revenue_under_regulated_activity / total_revenue
jurisdiction_weight = revenue_in_jurisdiction / total_revenue
agency_relevance_weight = taxonomy_mapping(company_activity, regulator)

regulatory_exposure_score = regulated_revenue_pct * jurisdiction_weight * agency_relevance_weight
regulatory_event_gate_weight = min(1, regulatory_exposure_score / threshold)
```

- **Application inside AAT:** Gate regulatory/legal events, rate-case events, antitrust events, FDA/clinical events, environmental actions, and financial enforcement actions. Use sector-specific subtypes.
- **Evidence payload:** `regulator`, `jurisdiction`, `regulated_activity`, `regulated_revenue_pct`, `agency_relevance_weight`, `regulatory_gate_weight`.
- **Confidence and validation rules:** Downgrade for qualitative-only exposure, multiple jurisdictions, outdated licenses, or broad industry regulation without company-specific materiality.


#### Product-cycle exposure

- **Initial adoption stage:** Production gate for product/FDA/contract events after product taxonomy is created.
- **Interpretation:** Determines whether product launches, product delays, FDA milestones, model cycles, game releases, semiconductor ramps, or hardware refreshes should matter.
- **Data sourcing:** Use segment/product revenue disclosures, pipeline disclosures, PDUFA calendars, ClinicalTrials.gov, product release calendars, investor presentations as evidence, and analyst-curated product mappings.
- **Calculation methodology:**

```text
product_revenue_pct = product_or_franchise_revenue / total_revenue
pipeline_asset_materiality_pct = estimated_asset_NPV / market_cap
launch_window_weight = exp(-days_to_or_since_launch / decay_half_life_days)

product_cycle_gate_weight = min(1,
  max(product_revenue_pct, pipeline_asset_materiality_pct) * launch_window_weight / threshold
)
```

- **Application inside AAT:** Gate product launch, FDA/clinical, contract, and competitive read-through events. Also determines event materiality when product revenue share is known.
- **Evidence payload:** `product`, `franchise`, `product_revenue_pct`, `pipeline_asset_materiality_pct`, `launch_or_milestone_date`, `product_cycle_gate_weight`.
- **Confidence and validation rules:** Downgrade for unquantified product exposure, broad platform products, unclear launch dates, or stale pipeline assumptions.


#### Foreign-exchange exposure

- **Initial adoption stage:** Production gate after geographic revenue/cost/hedging data is curated.
- **Interpretation:** Determines whether USD or currency-specific factors should be included and what sign is economically expected.
- **Data sourcing:** Use geographic revenue/cost disclosures, hedging notes, transaction/translation exposure disclosures, ADR reporting currency, and licensed fundamentals where available.
- **Calculation methodology:**

```text
foreign_revenue_pct = non_reporting_currency_revenue / total_revenue
foreign_cost_pct = non_reporting_currency_cost / total_cost
hedge_coverage_pct = hedged_fx_exposure / gross_fx_exposure

net_fx_exposure = foreign_revenue_pct - foreign_cost_pct
hedge_adjusted_fx_exposure = net_fx_exposure * (1 - hedge_coverage_pct)

fx_gate_weight = min(1, abs(hedge_adjusted_fx_exposure) / gate_threshold_pct)
expected_usd_sign = -sign(hedge_adjusted_fx_exposure) for USD-reporting companies
  because stronger USD reduces translated foreign revenue more than foreign costs
```

- **Application inside AAT:** Gate dollar index and currency-basket factors. Use currency-specific baskets when the company is concentrated in EUR, CNY, JPY, GBP, EM, or another region. Do not use DXY for all FX exposure.
- **Evidence payload:** `foreign_revenue_pct`, `foreign_cost_pct`, `hedge_coverage_pct`, `currency_basket`, `fx_gate_weight`, `expected_usd_sign`.
- **Confidence and validation rules:** Downgrade for missing cost split, undisclosed hedges, natural hedges, ADR/local listing complexity, or region rather than currency disclosure.


## Developer Implementation Checklist For Each Attribute

Before an attribute can move beyond research, create or verify the following artifacts:

| Artifact | Required Content |
|---|---|
| `factor_definition` or `event_taxonomy` row | Name, family, units, source, transform, active dates, license tier, owner. |
| Raw observation adapter | Source ID, timestamp parser, retry policy, license guard, field validation. |
| Processing function | Deterministic transformation from raw observations to factor move, descriptor, surprise, or gate. |
| Point-in-time test | Proves `timestamp_available <= attribution_cutoff` for all model-visible rows. |
| Exposure estimator or gate calculator | Beta/exposure/gate logic, lookback, sample minimum, confidence diagnostics. |
| Attribution integration | Correct position in hierarchy and no double counting with earlier factors. |
| Evidence payload | Human-readable values plus machine-readable source IDs and calculation fields. |
| Confidence rule | Source, staleness, sparse data, proxy mismatch, collinearity, stability, parser penalties. |
| Validation notebook/test | Residual reduction, out-of-sample check, reconciliation, edge cases. |

## Minimum Output Contract For `FactorContributionInput`

Every production or shadow contribution should be reducible to this structure:

```text
security_id
attribution_run_id
attribute_id
attribute_family
contribution_stage = research | evidence_only | shadow | production
factor_move
factor_move_unit
exposure_value
exposure_unit
contribution_bps
confidence_score
confidence_label
evidence_payload
model_version
data_version
factor_basket_version nullable
timestamp_available
```

For evidence-only rows, `contribution_bps` must be null or zero with `contribution_stage=evidence_only`; the dashboard should not add it to total contribution.

## Practical Development Sequence Implied By The Methodologies

1. Implement shared metadata, point-in-time, confidence, and hierarchy infrastructure.
2. Add Priority 1 sector, industry, subindustry, and peer calculations first.
3. Add return-based Priority 2 descriptors: momentum, reversal, volatility, beta, liquidity.
4. Add fundamentals-backed Priority 2 descriptors only after point-in-time fundamentals are confirmed.
5. Add Priority 3 macro transformations and exposure gates.
6. Keep Priority 4 options/flow in research until licensing and timestamp handling are settled.
7. Upgrade Priority 5 event taxonomy and surprises, but hold production event contribution until event-study calibration passes.
8. Build Priority 6 exposure profiles continuously because they improve macro, event, and peer gating even before they become fully automated.

## Recommended Implementation Order

### Phase A: Make the Factor Baseline Institutionally Recognizable

Add:

1. Sector factor
2. Industry factor
3. Custom peer basket factor
4. Momentum
5. Volatility
6. Liquidity

This phase should materially reduce residuals while remaining simple to explain.

### Phase B: Activate Macro Attribution

Use the existing `macro_series` table to add:

1. 2Y yield
2. 10Y yield
3. 2s10s curve
4. DXY or broad dollar
5. WTI
6. Natural gas
7. High-yield spread
8. Investment-grade spread
9. VIX
10. Inflation expectations

These should be exposure-gated. A macro factor should only appear as a contribution when the company has a defensible exposure or the regression estimates a stable sensitivity.

### Phase C: Upgrade Event Intelligence

Add event-type-specific fields:

```text
event_category
event_subtype
event_direction
event_surprise
event_materiality
event_relevance
event_novelty
source_credibility
exposure_match
evidence_span
```

Then add event-study calibration so event rows can eventually receive return contributions rather than only feature scores.

### Phase D: Add Positioning and Options

Add after licensing is clear:

1. Short interest
2. Days to cover
3. Borrow cost
4. ATM implied volatility
5. IV change
6. Put-call skew
7. Options volume/open interest
8. Dealer gamma exposure

These are high-value, but they should not be rushed because they can create false precision if data quality is poor.

## Attribute Count Target

AAT should not try to copy MAC3 factor count. For the current product scope, a good medium-term target is:

| Category | Target Count |
|---|---:|
| Market | 1-2 |
| Sector/industry | 10-25 |
| Peer baskets | 1-3 per company |
| Style | 10-15 |
| Macro | 10-20 |
| Positioning/options | 8-12 |
| Event attributes | 20-40 |
| Company exposure attributes | 10-20 |

The practical target for the next credible version is about 45 attributes, not 3,000.

## Suggested First 45 Attributes

| # | Attribute | Category |
|---:|---|---|
| 1 | Market beta contribution | Market |
| 2 | Sector return contribution | Sector |
| 3 | Industry return contribution | Sector |
| 4 | Subindustry basket contribution | Sector |
| 5 | Custom peer basket contribution | Peer |
| 6 | Peer residual spread | Peer |
| 7 | Peer event read-through | Peer/Event |
| 8 | Size | Style |
| 9 | Value | Style |
| 10 | Profitability | Style |
| 11 | Investment | Style |
| 12 | Momentum | Style |
| 13 | Short-term reversal | Style |
| 14 | Realized volatility | Style |
| 15 | Liquidity | Style |
| 16 | Growth | Style |
| 17 | Quality | Style |
| 18 | Leverage | Style |
| 19 | Dividend yield | Style |
| 20 | 2Y Treasury yield change | Macro |
| 21 | 10Y Treasury yield change | Macro |
| 22 | 2s10s curve change | Macro |
| 23 | Fed funds expectations | Macro |
| 24 | Dollar index | Macro |
| 25 | WTI crude | Macro |
| 26 | Natural gas | Macro |
| 27 | Gold | Macro |
| 28 | Copper | Macro |
| 29 | High-yield credit spread | Macro |
| 30 | Investment-grade credit spread | Macro |
| 31 | VIX change | Macro |
| 32 | Earnings EPS surprise | Event |
| 33 | Revenue surprise | Event |
| 34 | Margin surprise | Event |
| 35 | Guidance raise/cut | Event |
| 36 | Estimate revision | Event |
| 37 | Rating change | Event |
| 38 | Price target revision | Event |
| 39 | M&A event | Event |
| 40 | Buyback/dividend event | Event |
| 41 | Insider activity | Event |
| 42 | Activist filing | Event |
| 43 | Regulatory/legal event | Event |
| 44 | Product/FDA/contract event | Event |
| 45 | Short interest / days to cover | Positioning |

## Methodology Guardrails For New Attributes

Every new attribute should satisfy these conditions before it is allowed into production attribution:

1. It must have a clear driver type: market, sector, peer, style, macro, event, or positioning.
2. It must be point-in-time visible at the attribution cutoff.
3. It must have a stable source and license status.
4. It must produce evidence strings that an analyst can inspect.
5. It must degrade confidence when data is sparse, stale, unstable, or collinear.
6. It must not remove the explicit residual.
7. It must reconcile within the existing one-basis-point tolerance.
8. It must be versioned through `model_version`, `data_version`, and `factor_basket_version`.

## Recommended Near-Term Schema Additions

The current schema can already store many new factor returns and macro series. The main missing pieces are metadata and mapping tables.

Recommended additions:

| Table | Purpose |
|---|---|
| `factor_definition` | Defines factor name, family, source, unit, transform, license tier, and active dates. |
| `security_factor_exposure` | Stores estimated beta/exposure by security, factor, model version, and timestamp. |
| `peer_basket` | Defines peer baskets and basket versions. |
| `peer_basket_member` | Stores peer weights and active dates. |
| `sector_classification_history` | Stores point-in-time sector/industry/subindustry classifications. |
| `event_taxonomy` | Defines event categories and subtypes. |
| `event_surprise` | Stores event-type-specific surprise metrics. |
| `analyst_feedback` | Stores correct/partial/wrong/missing-driver feedback per contribution. |

## Recommended Near-Term Code Additions

| Module | Purpose |
|---|---|
| `engine/factors/sector_model.py` | Sector and industry factor attribution. |
| `engine/factors/peer_model.py` | Custom peer-basket attribution. |
| `engine/factors/style_model.py` | Momentum, volatility, liquidity, and descriptor-based style attribution. |
| `engine/factors/macro_model.py` | Macro sensitivity estimation and macro contribution generation. |
| `engine/events/taxonomy.py` | Event category and subtype normalization. |
| `engine/events/surprise.py` | Event-specific surprise calculation. |
| `engine/attribution/hierarchy.py` | Enforces attribution order to reduce double counting. |
| `engine/confidence/scoring.py` | Central confidence calibration across factor and event drivers. |

## Recommended Attribution Order

To reduce double counting, AAT should allocate drivers hierarchically:

1. Market
2. Sector
3. Industry/subindustry
4. Peer basket
5. Style
6. Macro
7. Positioning/liquidity
8. Event
9. Unexplained residual

This order matters because an event often affects an entire peer group or sector. If peer and sector effects are not removed first, the event layer will overclaim.

## Conclusion

AAT has a strong foundation. The current five-factor model is not wrong; it is simply too small to support the product promise by itself. The next credibility jump comes from adding sector, industry, and peer-basket attribution, not from adding dozens of obscure academic descriptors.

The most valuable next build slice is:

```text
sector attribution
+ industry attribution
+ custom peer baskets
+ momentum
+ volatility
+ liquidity
+ macro_series-based rates, dollar, oil, credit, and VIX factors
```

After that, event attribution can become much more meaningful because the residual will be cleaner. That is the core architectural idea: explain the systematic move first, then ask whether company-specific events explain what remains.
