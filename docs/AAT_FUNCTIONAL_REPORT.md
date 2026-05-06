# AAT Functional Report

Based on the repository state inspected on 2026-05-05.

## Executive Summary

AAT is an alpha-stage single-stock attribution system. Its job is to explain, for one stock over one time window, what portion of the move can be attributed to modeled market, factor, peer, macro, and evidence drivers, and what portion remains unexplained.

The core output is a reconciled driver table, not a trading signal and not a free-form news explanation. AAT first calculates the stock's actual adjusted close-to-close return. It then applies only point-in-time-visible attribution inputs. Finally, it reports the leftover amount as `unexplained_residual`.

In plain finance language:

```text
Observed stock move
  = modeled contributions
  + unexplained residual
```

The current implemented model is a working MVP scaffold, not a production-complete attribution model. It already supports deterministic return accounting, French five-factor attribution, sector and industry proxy factors, peer baskets, FRED macro factors, EDGAR filing evidence, deterministic narrative text, API endpoints, a Next.js dashboard, analyst feedback, and large backfill orchestration. However, event rows and return-style descriptors are currently evidence-only unless a calibrated production contribution method exists. The system deliberately refuses to pretend that a filing or headline caused a move until the methodology is calibrated.

## Current Local Snapshot

The project status file reports the following local state as of 2026-05-04:

- The latest local verification command was `python -m pytest tests/unit tests/lookahead_audit`, with 81 tests passing.
- Local TimescaleDB runs through Docker Compose, normally on host port `55432`.
- FaustCalc SEC filing import staged 2,009 deduped filings, promoted 576 canonical events, and generated 576 event features.
- FaustCalc feature-store import promoted 11,265,327 representable price rows into canonical `price_bar`.
- 2,520 staged price rows remain audit-only because they fall outside canonical precision or range limits.
- The FaustCalc active-US-equity universe contains 12,657 eligible active USD stock securities with FaustCalc price coverage.
- FaustCalc-generated sector and industry classifications, peer baskets, and macro exposure gates have been seeded without overwriting curated MVP mappings.
- The `/universe` endpoint has been optimized to use precomputed summaries with SQL pagination.
- A resumable FaustCalc full-history attribution backfill is available and can report DB-backed progress with `--status-only`.

## What AAT Is Trying To Answer

For any stock and attribution window, AAT tries to answer five questions:

1. What was the actual stock move?
2. Which modeled drivers explain part of that move?
3. How much did each modeled driver contribute, in basis points and as a share of the move?
4. What evidence supports each driver?
5. What part remains unexplained, and should any structural exposure profile be reviewed?

AAT is not a portfolio attribution model, not an optimizer, not a Bloomberg replacement, and not an unconstrained AI market commentator. Its design is intentionally accounting-first and evidence-first.

## Key Terms

| Term | Meaning |
|---|---|
| `security_id` | The internal permanent identifier for a tradable security. AAT does not rely on ticker alone because tickers change. |
| `company_id` | The internal permanent identifier for the company or issuer. |
| `ticker_history` | The history of ticker symbols attached to a security. |
| `event_time` | When the market event, price observation, factor observation, filing, or exposure fact happened. |
| `ingestion_time` | When AAT ingested the record. |
| `timestamp_available` | The earliest time AAT says the model was allowed to know the record. |
| `attribution_cutoff` | The information cutoff for a run. Rows available after this time are excluded. |
| `observed_return_bps` | The stock's measured adjusted close-to-close return in basis points. |
| `contribution_bps` | A modeled driver's contribution to the stock move, in basis points. |
| `share_of_move` | `contribution_bps / observed_return_bps`. |
| `unexplained_residual` | The part of the move not explained by production contribution rows. |
| `contribution_stage` | Whether a row is production, evidence-only, research, or shadow. |

## The Core Principle: Point-In-Time Truth

The most important research control in AAT is:

```text
timestamp_available <= attribution_cutoff
```

This means AAT does not use information that would not have been available at the time of the attribution run.

For example, suppose a stock moves on January 10, but a data vendor only delivered a relevant filing row to AAT on January 11. AAT excludes that filing from a January 10 cutoff, even if the filing's economic event time was January 10. This prevents look-ahead bias in historical attribution.

AAT applies this rule to prices, factor returns, macro observations, events, event features, sector classifications, peer baskets, company exposures, and contribution evidence.

## High-Level System Flow

The system works in six broad stages:

1. Fetch or import raw information.
2. Normalize that information into canonical database records.
3. Build point-in-time features and factor returns.
4. Run attribution for a stock and time window.
5. Store the run and contribution rows.
6. Display the result through the API and dashboard.

In simplified form:

```text
Data sources
  -> ingestion adapters and import jobs
  -> canonical database
  -> attribution engine
  -> attribution_run and attribution_contribution tables
  -> FastAPI
  -> Next.js dashboard
```

## Information Fetching And Import

### Price Data

AAT has two implemented price-data paths.

#### FMP historical prices

The FMP adapter fetches historical daily prices for a ticker using an API key. It parses open, high, low, close, adjusted close, volume, currency, source, event date, ingestion time, and availability time.

Important behavior:

- The source is stored as `fmp`.
- Adjusted close is used for return accounting.
- FMP rows are timestamped as available at ingestion time because the historical endpoint is not treated as a point-in-time vintage feed.
- Production use fails closed unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.
- FMP currently remains development-only unless the production license status is confirmed.

#### FaustCalc feature-store price snapshot

AAT can import a local FaustCalc feature-store snapshot. This path connects to a FaustCalc database and imports these source tables into AAT staging tables:

- `assets`
- `companies`
- `prices`
- `fundamentals`
- `price_features`
- `theme_scores`
- `filing_analysis`
- `peer_analysis`

The import process then promotes eligible identities and price rows into the canonical AAT tables.

Important behavior:

- Assets become canonical companies, securities, and ticker-history rows.
- Price rows become canonical `price_bar` rows with source `faustcalc_fmp_snapshot`.
- The FaustCalc price source supplies close prices; AAT promotes these as both `close` and `adjusted_close`.
- Non-positive or unreasonably large price rows are excluded from canonical promotion and remain audit-only in staging.
- Ticker aliases are normalized, for example `BRK-B` and `BRK/B` become `BRK.B`.
- The imported timestamp becomes the availability timestamp for promoted price rows.

### Factor Data

#### Kenneth French five-factor data

AAT downloads or reads the Kenneth French daily five-factor zip file. It parses the daily CSV and stores each factor return in basis points.

Implemented factors:

| Factor | Finance interpretation | AAT driver family |
|---|---|---|
| `Mkt-RF` | Broad equity market excess return | Market |
| `SMB` | Size factor | Style |
| `HML` | Value factor | Style |
| `RMW` | Profitability factor | Style |
| `CMA` | Investment factor | Style |

Important behavior:

- French returns are published as percent returns and converted to basis points.
- The source is stored as `kenneth_french`.
- The current source is not a point-in-time vintage feed, so rows are timestamped as available at ingestion time.

#### Sector and industry proxy factors

AAT can build factor returns from ETF or proxy-security price bars. The job reads proxy ticker prices, calculates their adjusted close-to-close returns, and writes those returns into `factor_return`.

Implemented sector proxies include:

| Sector | Proxy |
|---|---|
| Information Technology | `XLK` |
| Communication Services | `XLC` |
| Consumer Discretionary | `XLY` |
| Consumer Staples | `XLP` |
| Financials | `XLF` |
| Health Care | `XLV` |
| Energy | `XLE` |

Implemented industry proxies include:

| Industry | Proxy |
|---|---|
| Semiconductors | `SMH` |
| Banks | `KBE` |
| Biotechnology | `XBI` |
| Pharmaceuticals | `XLV` |
| Software | `IGV` |
| Broadline Retail | `XRT` |
| Specialty Retail | `XRT` |

The factor names are stored as `sector:<sector name>` and `industry:<industry name>`.

### Macro Data

AAT ingests public FRED CSV series and stores them in `macro_series`.

Implemented FRED series:

| Series | Meaning |
|---|---|
| `DGS2` | 2-year Treasury yield |
| `DGS10` | 10-year Treasury yield |
| `BAMLH0A0HYM2` | High-yield credit spread |
| `BAMLC0A0CM` | Investment-grade credit spread |
| `VIXCLS` | VIX close |
| `T5YIE` | 5-year breakeven inflation |

Important behavior:

- The FRED adapter uses CSV download, retries, and rate limiting.
- Observations are timestamped as available at ingestion time unless a future vintage-aware source is added.
- Macro series are later transformed into factor moves such as yield changes, curve changes, spread changes, VIX returns, and inflation-expectation changes.

### SEC EDGAR Filings And Event Data

AAT has two implemented SEC-related paths.

#### Direct SEC EDGAR submissions

The SEC adapter fetches company submission data using the official SEC submissions endpoint and a required `EDGAR_USER_AGENT`.

It parses:

- CIK
- company name
- form type
- accession number
- filing date
- report date
- primary document
- acceptance timestamp

Important behavior:

- The source is stored as `sec_edgar`.
- The event time is the SEC acceptance timestamp when available; otherwise it falls back to the filing date.
- The availability timestamp is the acceptance timestamp when available; otherwise ingestion time.
- Filings are stored as canonical `event` rows.

#### FaustCalc SEC filing snapshot

AAT can import cleaned SEC filing data from a local FaustCalc snapshot.

The import process:

- Scans normalized SEC JSONL files.
- Verifies filename ticker and accession number against payload fields.
- Requires non-empty filing text.
- Cleans line endings and null bytes.
- Computes a SHA-256 hash of cleaned text.
- Deduplicates by accession number.
- Handles duplicate accessions with audit issues.
- Chooses a canonical ticker, preferring ordinary common-share tickers over preferred-share-like aliases.
- Stores full filing text separately as cleaned text files and omits raw text from the JSON payload.
- Promotes valid staged filings into canonical `event` rows.
- Optionally generates event features immediately after promotion.

The source is stored as `faustcalc_sec_edgar_snapshot`.

### Universe, Sector, Peer, And Exposure Inputs

AAT supports two universe construction modes.

#### Curated 50-name MVP universe

The curated universe is defined in `config/mvp_universe.json`. It includes large US stocks with:

- ticker
- company name
- CIK
- exchange
- sector
- industry
- subindustry
- peer list
- curated exposure gates

The seed jobs create:

- `company`
- `security`
- `security_ticker_history`
- `sector_classification_history`
- `peer_basket`
- `peer_basket_member`
- `company_exposure`

Peer baskets in this curated file use equal weights across available seeded peers.

#### FaustCalc active-US-equity universe

AAT can build a larger universe from FaustCalc staging data. The current default universe name is `faustcalc_active_us_equities`.

Eligibility rules:

- Asset type must be stock.
- Currency must be USD.
- Asset must be active.
- Security must have at least the configured minimum number of price bars, default 2.

The universe builder creates `model_universe_member` rows and then refreshes frontend-ready summaries.

#### Generated FaustCalc mappings

For the larger FaustCalc universe, AAT can generate mappings when curated mappings do not already exist.

Generated classifications:

- Sector and industry are taken from FaustCalc company metadata when available.

Generated peer baskets:

- Prefer companies in the same industry.
- Fall back to same sector if too few industry peers exist.
- Rank peers by price-bar coverage, then ticker.
- Cap the peer count, default 20.
- Require a minimum peer count, default 3.
- Assign equal weights across selected peers.

Generated macro gates:

- Rates, credit, and inflation exposure gates are inferred from sector and industry text.
- For financials, banks, real estate, insurance, utilities, mortgage names: rates and credit gates are higher.
- For consumer discretionary, retail, autos, airlines, hotels: rates and credit are raised.
- For energy, oil, gas, materials, metals, and chemicals: inflation and credit are raised.
- For technology, software, semiconductors, and communication services: credit is lowered.
- For health care, pharma, and biotech: rates and credit are lowered.

Curated mappings are not overwritten by generated FaustCalc mappings.

## Canonical Storage Model

AAT uses PostgreSQL with TimescaleDB for time-series tables.

Core identity tables:

- `company`
- `security`
- `security_ticker_history`

Core market and factor tables:

- `price_bar`
- `factor_return`
- `macro_series`
- `factor_definition`
- `factor_observation`
- `security_factor_exposure`

Classification, peer, and exposure tables:

- `sector_classification_history`
- `peer_basket`
- `peer_basket_member`
- `company_exposure`
- `exposure_update_decision`

Event tables:

- `event`
- `event_feature`
- `event_taxonomy`
- `event_surprise`

Attribution and feedback tables:

- `attribution_run`
- `attribution_contribution`
- `analyst_feedback`
- `backfill_run`
- `attribution_backfill_task`
- `security_attribution_summary`

FaustCalc staging and audit tables:

- `faustcalc_import_run`
- `faustcalc_validation_issue`
- `faustcalc_asset`
- `faustcalc_company`
- `faustcalc_price`
- `faustcalc_fundamental`
- `faustcalc_price_feature`
- `faustcalc_theme_score`
- `faustcalc_filing_analysis`
- `faustcalc_peer_analysis`
- `faustcalc_sec_filing`

`price_bar`, `factor_return`, `factor_observation`, and `macro_series` are time-series style tables with time indexes.

## Data Transformation Methodologies

### Entity Normalization

AAT separates company identity from tradable security identity.

This matters because:

- One company can have multiple share classes.
- Tickers can change.
- Tickers can be reused.
- Historical attribution should not break when a ticker changes.

AAT therefore resolves attribution by `security_id`, not by ticker alone. Ticker is treated as an access path into ticker history.

### Price Normalization

Prices are normalized into `price_bar`.

Key fields:

- `open`
- `high`
- `low`
- `close`
- `adjusted_close`
- `volume`
- `currency`
- `source`
- `event_time`
- `ingestion_time`
- `timestamp_available`

When multiple same-day rows exist for the same security from overlapping sources, the attribution loader chooses one point-in-time-visible row per event date. It ranks by latest `timestamp_available` at or before the cutoff, then by source name as a deterministic tie-breaker.

### Return Transformation

The observed stock return is computed from adjusted close:

```text
observed_return_bps = ((ending_adjusted_close / starting_adjusted_close) - 1) * 10,000
```

AAT requires at least two visible price bars in the selected window. If it cannot see both the start and end price by the attribution cutoff, it does not fabricate the move.

### Factor Return Transformation

Factor returns are stored in basis points where possible.

Examples:

- Kenneth French percent returns are multiplied by 100 to become basis points.
- ETF proxy factor returns are computed from adjusted close-to-close returns.
- FRED macro levels are transformed into changes or returns before attribution.

### Macro Transformations

AAT currently transforms FRED macro series as follows:

| Macro factor | Transformation |
|---|---|
| `macro:2y_yield_change` | Daily change in `DGS2`, multiplied by 100 |
| `macro:10y_yield_change` | Daily change in `DGS10`, multiplied by 100 |
| `macro:2s10s_curve_change` | Daily change in `DGS10 - DGS2`, multiplied by 100 |
| `macro:hy_spread_change` | Daily change in `BAMLH0A0HYM2`, multiplied by 100 |
| `macro:ig_spread_change` | Daily change in `BAMLC0A0CM`, multiplied by 100 |
| `macro:vix_return` | Percent return of `VIXCLS`, in basis-point units |
| `macro:inflation_expectation_change` | Daily change in `T5YIE`, multiplied by 100 |

The `* 100` conversion expresses yield or spread percentage-point moves in basis-point-like units.

### Style Descriptor Transformation

AAT calculates several return-based style descriptors. These are stored as exposures and displayed as evidence-only rows.

Implemented descriptors:

| Descriptor | Calculation | Current attribution role |
|---|---|---|
| Momentum | Compounded return over roughly the prior 12 months excluding the most recent month; shorter fallback when less history exists | Evidence-only |
| Short-term reversal | Negative of compounded return over the last 21 trading returns | Evidence-only |
| Realized volatility | Population standard deviation of the last 60 daily returns times square root of 252 | Evidence-only |
| Liquidity | Natural log of 1 plus average daily dollar volume over the last 60 bars | Evidence-only |

These rows do not reduce the residual today because they are descriptors, not calibrated production factor returns.

### Event Feature Transformation

EDGAR filing rows are converted into structured event features.

Implemented feature fields:

- relevance
- novelty
- sentiment
- magnitude
- source credibility
- exposure match
- surprise
- evidence span

The current feature builder is heuristic and form-type based. For example:

- `8-K` receives high relevance, high novelty, and high magnitude.
- `10-K` and `10-Q` receive high relevance but lower novelty.
- `13G` and Schedule 13G receive ownership-related relevance and novelty.
- Form `4` and Form `144` receive lower materiality scores.
- Official SEC sources receive higher source credibility.

These event features are useful evidence, but they are not causal contribution estimates.

### Event Taxonomy Transformation

Visible events can also be classified into an event taxonomy.

Examples:

| Filing or item | Category | Subtype | Direction | Materiality |
|---|---|---|---|---|
| `8-K` item `2.02` | earnings | results of operations | mixed | high |
| `8-K` item `2.05` | restructuring | exit or disposal | mixed | high |
| `8-K` item `2.06` | accounting | material impairment | negative | high |
| `8-K` item `5.02` | management | officer or director change | mixed | medium |
| `10-K` | periodic results | annual report | mixed | medium-high |
| `10-Q` | periodic results | quarterly report | mixed | medium |
| `13D` | ownership | activist or large holder | mixed | high |
| `13G` | ownership | passive large holder | mixed | medium |
| Form `4` | insider activity | form 4 | mixed | low-medium |
| Form `144` | insider activity | planned sale | negative | low |

The event taxonomy is used for evidence display and future event methodology. It does not currently assign return contribution.

### Event Surprise Transformation

AAT has a generic helper for numeric surprises:

```text
surprise_value = (actual_value - expected_value) / denominator
```

The denominator is either a provided scale or the absolute expected value with a small floor to avoid division by zero.

Direction is classified as:

- positive if surprise is above the neutral band
- negative if below the negative neutral band
- neutral otherwise

This is implemented infrastructure for future event-specific surprise methods. It is not yet used as a production event attribution engine.

### Exposure Gate Transformation

Exposure gates determine whether a factor should matter for a company and how strongly it should be allowed into attribution.

Current active macro gates in attribution:

- `rates`
- `credit`
- `inflation`

These gates are loaded from `company_exposure` and mapped to macro factors:

| Company exposure | Macro factors affected |
|---|---|
| `rates` | 2Y yield, 10Y yield, 2s10s curve |
| `credit` | HY spread, IG spread |
| `inflation` | 5Y breakeven inflation |
| VIX | Always allowed with gate 1.0 |

If no curated gate exists:

- rate gate defaults to 1.0
- credit gate defaults to 1.0
- inflation gate defaults to 0.5
- VIX gate is 1.0

The engine also includes helper formulas for more detailed gates:

```text
commodity signed exposure = producer exposure - consumer input exposure
commodity gate = abs(hedge-adjusted signed exposure) / threshold
```

```text
FX net exposure = foreign revenue percent - foreign cost percent
FX gate = abs(hedge-adjusted FX exposure) / threshold
```

```text
rate exposure score = average(
  floating-rate debt percent,
  net debt percent of market cap,
  interest expense percent of EBIT,
  duration or NII sensitivity
)
```

```text
credit exposure score = average(
  net debt to EBITDA z-score,
  negative interest coverage z-score,
  debt maturity wall z-score,
  negative rating score z-score
)
```

These detailed helpers are scaffolded for future expansion. The active MVP run path currently uses the simpler company-exposure gate values described above.

## Attribution Determination Methodology

### Attribution Windows

AAT supports daily, weekly, and monthly attribution windows.

| Cadence | Window construction |
|---|---|
| Daily | Consecutive trading dates in `price_bar` |
| Weekly | First and last trading date in each ISO week |
| Monthly | First and last trading date in each calendar month |

For historical backfills, AAT also requires enough lookback history before the window. The FaustCalc full-history backfill excludes windows that start before `first_price_time + lookback_days`.

### Estimation Window

Most factor attribution uses a lookback window ending at the attribution window start.

```text
estimation_window_start = attribution_window_start - lookback_days
estimation_window_end   = attribution_window_start
```

Defaults vary by command:

- Simple CLI default: 60 calendar days.
- MVP daily and large backfill workflows: typically 252 calendar days.

The estimation window is used to estimate a stock's sensitivity, or beta, to a factor.

### Observed Return

The first step is always the actual stock return:

```text
observed_return_bps = ((end_adjusted_close / start_adjusted_close) - 1) * 10,000
```

This is deterministic accounting. No model judgment is involved.

### Market-Only Attribution

The older market-only path estimates a simple beta between the stock's daily returns and the `Mkt-RF` factor.

```text
beta = covariance(stock_return, market_factor_return)
       / variance(market_factor_return)
```

Then:

```text
market_contribution_bps = beta * market_factor_return_over_attribution_window
```

This path is available, but the main expanded MVP workflow normally uses the French five-factor model instead.

### French Five-Factor Attribution

The French five-factor method estimates multiple factor betas simultaneously.

In finance terms, AAT regresses the stock's prior daily returns on:

- `Mkt-RF`
- `SMB`
- `HML`
- `RMW`
- `CMA`

The regression includes an intercept. The factor coefficients are the stock's estimated factor sensitivities.

The model requires enough paired stock and factor observations:

```text
minimum observations = max(10, 2 * number_of_factors)
```

With five factors, that means at least 10 paired observations.

For each factor:

```text
factor_contribution_bps
  = estimated_beta * sum(factor_return_bps during attribution window)
```

The attribution window includes factor dates:

```text
attribution_window_start < factor_date <= attribution_window_end
```

Driver assignment:

- `Mkt-RF` becomes a market contribution.
- `SMB`, `HML`, `RMW`, and `CMA` become style contributions.

Confidence:

- Medium by default.
- Low-Medium if the factor matrix has a high condition number above 30, which indicates collinearity risk.

### Sector And Industry Proxy Attribution

In expanded MVP mode, AAT looks up the stock's latest visible sector classification. It then tries to load factor returns named:

```text
sector:<sector name>
industry:<industry name>
```

For each available sector or industry proxy factor, AAT estimates a simple beta using the stock's prior daily returns and the proxy factor's prior daily returns.

```text
beta = covariance(stock_return, proxy_factor_return)
       / variance(proxy_factor_return)
```

Then:

```text
sector_or_industry_contribution_bps
  = beta * proxy_factor_return_over_attribution_window
```

Minimum observations:

```text
10 paired observations
```

Evidence payload includes:

- factor name
- estimated beta
- factor move in basis points
- observation count
- model version

Current implementation note:

- Sector and industry proxy rows are both stored under the `sector` driver family, with names such as `Sector/industry factor (...)`.
- The dashboard can order and color a separate `industry` family if present, but the current engine driver enum treats these proxy rows as sector-family rows.

### Peer Basket Attribution

Peer attribution asks: how much of the target stock's move looks like a peer-group move?

AAT loads the active visible peer basket for the target security. A peer basket is valid only if:

- the basket is visible by the attribution cutoff
- the basket is active at the cutoff
- its members are visible by the cutoff
- at least 3 peer members are available
- member weights are positive

Weights are normalized to sum to 1.

For each peer, AAT computes daily adjusted close-to-close returns. It then calculates the peer basket return on dates common to all selected peers:

```text
peer_basket_return_on_date
  = sum(peer_weight * peer_return_on_date)
```

Then it estimates the target stock's beta to that peer basket:

```text
peer_beta = covariance(target_stock_return, peer_basket_return)
            / variance(peer_basket_return)
```

Contribution:

```text
peer_contribution_bps
  = peer_beta * peer_basket_return_over_attribution_window
```

Minimum observations:

```text
10 paired observations
```

Evidence payload includes:

- basket name
- basket version
- beta
- peer basket move
- observation count
- model version

### Macro Attribution

Macro attribution uses transformed FRED series and company exposure gates.

For each macro factor:

1. Transform the raw macro series into daily factor moves.
2. Estimate the stock's beta to the macro factor over the estimation window.
3. Sum the macro factor move over the attribution window.
4. Apply the company exposure gate.

Formula:

```text
macro_contribution_bps
  = beta * macro_factor_move * exposure_gate
```

Minimum observations:

```text
20 paired observations
```

If the exposure gate is zero, AAT skips the macro factor entirely.

Evidence payload includes:

- macro factor name
- beta
- factor move
- exposure gate
- observation count
- model version

Important interpretation:

- A macro contribution is not saying "rates caused the move" with certainty.
- It says the stock historically co-moved with that macro factor, the factor moved during the attribution window, and the company had a nonzero gate for that macro exposure.

### Style Descriptor Evidence

Return-style descriptors are calculated in expanded MVP mode:

- momentum
- short-term reversal
- realized volatility
- liquidity

They are stored as `security_factor_exposure` rows and displayed as style evidence rows with:

```text
contribution_bps = 0
contribution_stage = evidence_only
```

They do not reduce the residual.

### Event Evidence

When event evidence is included, AAT loads visible company events whose event time falls inside the attribution window.

For each event:

1. Classify the event into taxonomy category and subtype.
2. Upsert the taxonomy row.
3. Add an evidence-only contribution row.

Event evidence rows have:

```text
contribution_bps = 0
contribution_stage = evidence_only
```

They do not reduce the residual.

This is a deliberate methodology guardrail. AAT does not yet have calibrated event-study sensitivities, so it does not assign causal basis points to filings or events.

### Positioning And Options

The current codebase includes a small positioning helper for short interest:

```text
days_to_cover = short_interest / average_daily_volume
```

```text
short_interest_pct_float = short_interest / float_shares
```

This helper is not currently integrated into the production attribution run. Positioning, options, borrow cost, implied volatility, dealer gamma, and flow data remain future or research-stage categories until data rights and point-in-time handling are confirmed.

### Attribution Hierarchy

AAT sorts contribution inputs in this order:

1. Market
2. Sector
3. Peer
4. Style
5. Macro
6. Positioning
7. Event
8. Unexplained residual

The point of this order is to show systematic and peer effects before event evidence. This reduces the common analyst error of seeing a filing or headline and immediately assigning the entire stock move to that event.

Current implementation note:

- The hierarchy controls ordering and presentation.
- Expanded MVP factor rows are not yet fully orthogonalized in a single hierarchical multivariate model.
- French factors are estimated jointly with each other, but sector, peer, and macro factors are currently estimated as separate simple beta relationships.
- Therefore, the residual is an accounting residual after current modeled rows, not a guaranteed pure idiosyncratic causal residual.

### Residual Calculation

After visible contribution inputs are converted to contribution rows, AAT calculates:

```text
explained_bps = sum(non_residual_contribution_bps)
```

```text
unexplained_residual_bps = observed_return_bps - explained_bps
```

Then AAT appends exactly one residual row:

```text
driver = unexplained_residual
name = Unexplained residual
contribution_bps = unexplained_residual_bps
```

Residual confidence:

- Low if absolute residual is more than 50% of the absolute observed move.
- Medium otherwise.

The result must reconcile:

```text
observed_return_bps
  = sum(all contribution_bps, including residual)
```

AAT validates this within one basis point. It also validates that exactly one residual row exists.

### Share Of Move

For each contribution:

```text
share_of_move = contribution_bps / observed_return_bps
```

If the observed return is zero, share of move is left blank because division would not be meaningful.

Important finance interpretation:

- A contribution can be larger than 100% of the move if other drivers offset it.
- A negative share on a positive move means that driver worked against the stock move.
- Residual share shows how much of the move remains unmodeled.

### Confidence Methodology

AAT uses a five-level confidence ladder:

1. High
2. Medium-High
3. Medium
4. Low-Medium
5. Low

The confidence scoring infrastructure starts from a base confidence and applies penalties.

Standard penalty reasons include:

- insufficient observations
- high collinearity
- stale source
- proxy mismatch
- unstable beta sign

Current confidence is useful as a coarse data-quality and model-quality label. It is not yet a calibrated probability.

### Contribution Stages

Every contribution row has a stage:

| Stage | Meaning |
|---|---|
| `production` | Counts toward explained return and reduces residual. |
| `evidence_only` | Displayed for analyst context, but does not reduce residual. |
| `research` | Intended for research-only rows. |
| `shadow` | Intended for rows tracked in parallel before production promotion. |

In the current MVP:

- French factors are production-style rows.
- Sector and industry proxy factors are production-style rows when available.
- Peer basket factors are production-style rows when available.
- Macro factors are production-style rows when available.
- Return-style descriptors are evidence-only.
- EDGAR event rows are evidence-only.

## Persistence, Idempotency, And Backfills

### Attribution Run Persistence

AAT writes each completed run to `attribution_run` and its rows to `attribution_contribution`.

Attribution runs are idempotent by:

```text
security_id
window_start
window_end
model_version
factor_basket_version
cadence
```

If the same run is executed again, AAT updates the existing run and replaces its contribution rows instead of appending duplicates.

### Model Versions And Basket Versions

Current examples:

- Baseline result model: `factor-baseline-v0`
- French basket version: `french_5_v0`
- Expanded MVP basket version: `mvp_expanded_v0`
- Sector model: `sector-factor-v0`
- Peer model: `peer-basket-v0`
- Macro model: `macro-factor-v0`
- Style descriptor model: `return-style-descriptor-v0`
- EDGAR event feature model: `edgar-feature-heuristic-v0`
- Event taxonomy model: `event-taxonomy-v0`

The persisted `data_version` is currently `local-dev`.

### MVP Proving Backfill

The MVP proving workflow is designed to run the controlled 50-name system end to end.

It can:

- Run migrations.
- Seed the MVP universe.
- Seed sector, peer, and exposure mappings.
- Backfill FMP prices for stocks and proxy ETFs.
- Ingest Kenneth French factors.
- Ingest FRED macro series.
- Build proxy factor returns.
- Ingest or refresh EDGAR event evidence.
- Run expanded MVP attribution.
- Run look-ahead audit checks.
- Print coverage diagnostics.

### Historical Universe Backfill

The historical universe workflow creates daily, weekly, and monthly expanded attribution runs across a multi-year period. It stores aggregate coverage in `backfill_run`.

### FaustCalc Full-Universe Backfill

The FaustCalc backfill is built for large local execution.

It:

- Resolves the universe analysis date range from eligible members.
- Creates a `backfill_run`.
- Creates one task per security and cadence.
- Tracks task status as pending, running, completed, skipped, or failed.
- Preloads price bars, factor returns, macro series, and peer context for each task.
- Processes windows in chunks.
- Checkpoints the last completed window.
- Supports resumability with `--backfill-run-id`.
- Supports `--status-only` progress checks.
- Refreshes frontend summaries after processing.

Progress is tracked in `attribution_backfill_task` and summarized with counts such as:

- total tasks
- completed tasks
- pending tasks
- running tasks
- failed tasks
- expected windows
- ran windows
- skipped windows
- current ticker and cadence

## Look-Ahead Audit Controls

AAT includes tests and helpers that enforce point-in-time behavior.

Implemented controls:

- Feature-like tables must include `event_time`, `ingestion_time`, and `timestamp_available`.
- Future-available price bars are excluded.
- Future-available factor inputs are excluded.
- Contribution evidence payloads can be checked for future availability.
- Historical replay audit helpers verify that evidence payloads do not leak information after the cutoff.

These controls are central to the system's credibility.

## How AAT Displays The Information

### FastAPI Backend

The API serves attribution data to the dashboard.

Implemented endpoints:

| Endpoint | Purpose |
|---|---|
| `/health` | Service health check |
| `/version` | API version |
| `/universe` | Paginated, filterable universe summary |
| `/attribution-runs/latest` | Latest run for a ticker and cadence |
| `/attribution-runs` | Recent runs for a ticker |
| `/attribution-runs/{run_id}` | A specific attribution run |
| `/attribution-chart` | Price and contribution time series for charting |
| `/analyst-feedback` | Persists analyst feedback |
| `/exposure-update-decisions` | Shows exposure review decisions |

### Universe View

The dashboard opens with the model universe.

It shows:

- ticker
- company name
- exchange
- sector
- latest run date
- latest observed move
- latest residual
- top modeled driver
- top-driver confidence
- whether evidence exists
- run availability status

The user can:

- search by ticker or company
- filter by sector, industry, exchange, or run status
- sort columns
- page through the universe
- display move and residual as basis points or approximate USD price change

Residual USD is calculated from the latest price change:

```text
residual_usd
  = residual_bps / observed_return_bps * price_change_usd
```

This is only a display translation, not a separate model.

### Attribution Detail Panel

When a ticker is selected, the dashboard shows:

- selected ticker
- attribution window start and end
- observed move
- residual
- cadence
- model version
- attribution chart
- driver table
- run history
- exposure review decisions

### Attribution Chart

The chart displays the stock's cumulative adjusted-close return and cumulative modeled contribution bands.

Supported ranges:

- 10 days
- 1 month
- 3 months
- 6 months
- 1 year
- maximum available history

Cadence selection:

- 10-day, 1-month, and 3-month charts use daily attribution.
- 6-month, 1-year, and max charts use weekly attribution.

Display modes:

- basis points
- USD display mode for price change in hover summaries

The chart stacks contributions by driver family and shows an opposite-side border when modeled negative contributions offset a positive price move, or vice versa. A user can drag across a period to summarize the selected period's price change and average attribution shares.

### Driver Table

The driver table is the main analyst product.

It shows:

- driver name
- contribution in basis points
- share of move
- confidence
- contribution stage
- evidence
- evidence payload
- analyst feedback controls

It supports:

- sorting
- filtering by driver family
- evidence expansion
- CSV export
- one-click analyst feedback

Driver filters include:

- all
- market
- sector
- peer
- style
- macro
- positioning
- event
- unexplained residual

Evidence display includes two levels:

- human-readable evidence chips, such as beta, factor move, observations, model version
- structured evidence payload fields, such as factor name, exposure gate, basket version, event id, source id, taxonomy, materiality

Residual display:

- The residual row is visually emphasized if its absolute contribution is more than 50% of the absolute observed move.
- This is intentional. A large residual means AAT is telling the analyst the model did not explain most of the move.

### Analyst Feedback

For each contribution row, the dashboard allows:

- Correct
- Partial
- Wrong
- Missing

Feedback is persisted through the API in `analyst_feedback`.

For missing-driver feedback, the user is prompted to enter the missing driver name. This creates a future labeled-data loop for improving attribution coverage.

### Deterministic Narrative

AAT generates a short deterministic narrative from structured attribution output.

It can state:

- observed move
- largest modeled drivers
- residual size
- whether visible event evidence rows were attached

It does not invent causes. It does not use raw web access. It does not assign causal event contribution when event rows are evidence-only.

### Run History

The dashboard shows recent runs for the selected ticker, including:

- cadence
- window start and end
- observed move
- selected active run

This lets a user compare current and historical attribution windows.

### Exposure Review

The dashboard shows exposure update decisions.

Implemented decisions:

| Decision | Meaning |
|---|---|
| `candidate_review` | A high-impact or persistent event feature suggests a human should review the exposure profile. |
| `no_update` | Evidence is not material or persistent enough to review or update exposure. |

Important: even `candidate_review` does not automatically mutate `company_exposure`. The MVP is intentionally conservative.

## Exposure Update Methodology

AAT groups event features by exposure name.

The event type is mapped to exposure names:

| Event type | Exposure name |
|---|---|
| `10-K`, `10-Q` | periodic financial reporting |
| `8-K` | corporate event disclosure |
| `13G`, Schedule 13G, `13D`, Schedule 13D | ownership structure |
| Form `4`, Form `144` | insider activity |
| Other | general disclosure |

A feature counts toward review if:

```text
relevance >= 0.80
magnitude >= 0.50
novelty >= 0.45
```

A feature is high impact if:

```text
relevance >= 0.90
magnitude >= 0.65
```

Review is required if:

```text
at least 2 review features
or at least 1 high-impact feature
```

Decision:

- `candidate_review` if review is required.
- `no_update` otherwise.

Confidence:

- Medium for `candidate_review`.
- Medium-High for `no_update`.

Again, the output is a review decision, not an automatic exposure change.

## Source Licensing And Production Boundary

AAT treats data rights as an engineering control.

Implemented source policy:

- Public and free sources can be used in development.
- Licensed or alternative-data adapters must declare required credentials.
- Production use of FMP price data fails closed unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.

Current source status:

| Source | Current use | Production note |
|---|---|---|
| SEC EDGAR | Filing metadata and event evidence | Official public source |
| FRED | Macro series | Public source, but current rows are not vintage-aware |
| Kenneth French | Five-factor returns | Public academic data, not point-in-time vintage in current ingestion |
| FMP | Historical prices | Development-only unless production license confirmed |
| FaustCalc snapshot | Local imported feature-store and SEC snapshot | Depends on the underlying source rights of the snapshot |

## Current Implemented Capabilities

AAT currently implements:

- deterministic adjusted close-to-close return accounting
- point-in-time filtering
- French five-factor attribution
- sector and industry proxy factor attribution
- peer basket attribution
- macro attribution from FRED series
- return-style descriptor evidence
- SEC EDGAR event evidence
- event taxonomy rows
- event feature scores
- event surprise helper infrastructure
- exposure gates and exposure review decisions
- explicit unexplained residual
- idempotent run persistence
- daily, weekly, and monthly attribution cadences
- MVP proving backfill
- historical universe backfill
- FaustCalc import, universe construction, and resumable large-universe attribution backfill
- frontend-ready attribution summaries
- API endpoints
- dashboard universe view
- attribution chart
- driver table with evidence drawer
- CSV export
- deterministic narrative
- run history
- analyst feedback persistence

## Current Non-Production Or Evidence-Only Areas

These areas exist but should not be mistaken for fully calibrated production attribution:

- EDGAR event rows are evidence-only.
- Event-study contribution calibration is not implemented.
- Return-style descriptors are evidence-only.
- Positioning and options data are not integrated into production attribution.
- FRED and French data are not vintage-aware in the current ingestion path.
- FMP requires production license confirmation before production use.
- Confidence labels are not yet statistically calibrated probabilities.
- Expanded sector, peer, and macro rows are separate beta estimates, not yet one fully residualized hierarchical multivariate model.
- Entity resolution exists through security IDs and ticker history, but production-grade handling of all ticker changes, share classes, ADRs, delistings, and M&A remains a hardening area.
- The system still needs real-data proving, residual-reduction analysis, out-of-sample validation, confidence calibration, and source/license confirmation before production use.

## A Finance Expert's Interpretation Guide

### What A Production Contribution Means Today

A production contribution means:

1. A point-in-time-visible factor or proxy moved during the window.
2. The stock had an estimated historical sensitivity to that factor.
3. AAT multiplied that sensitivity by the factor move.
4. The row reduced the residual.

It does not mean AAT has proven causal truth. It means the contribution is methodologically allowed in the current model.

### What An Evidence-Only Row Means

An evidence-only row means:

1. The information was visible by the cutoff.
2. It is relevant for analyst context.
3. AAT is not assigning basis-point causality to it.
4. It does not reduce the residual.

This is especially important for events. If an 8-K appears on the same day as a stock move, AAT can show the filing as evidence. It does not yet say the filing caused 150 bps of the move.

### What A Large Residual Means

A large residual means:

- the model did not explain most of the move with currently active production rows
- the stock may have moved for company-specific reasons not yet modeled
- factor coverage may be missing
- event contribution may be uncalibrated
- the move may be noisy or idiosyncratic

A large residual is not a failure of accounting. It is the system preserving honesty.

### What Confidence Means

Confidence currently reflects evidence and model quality conditions such as observation count and collinearity. It is a qualitative label, not a probability that the attribution is correct.

### What The Dashboard Is Best Used For

The dashboard is best used as a structured morning-meeting tool:

- Which names moved?
- How much of each move is modeled?
- What are the top modeled drivers?
- Where is residual large?
- What evidence is attached?
- What should an analyst review?
- Which attribution rows were judged correct, partial, wrong, or missing?

## End-To-End Example

Suppose AAT runs daily attribution for a stock from Monday close to Tuesday close.

1. It loads visible adjusted close prices for Monday and Tuesday.
2. It computes the observed return, for example `+320 bps`.
3. It looks back over the estimation window to estimate factor sensitivities.
4. It calculates the French factor contributions.
5. In expanded mode, it calculates sector or industry proxy contribution if classification and proxy factor returns exist.
6. It calculates peer basket contribution if at least 3 visible peers have usable common-date returns.
7. It calculates macro contributions if macro series and gates are available.
8. It adds style descriptor evidence rows with zero contribution.
9. It adds visible EDGAR event evidence rows with zero contribution.
10. It sums production contribution rows, for example `+180 bps`.
11. It calculates residual: `+320 - +180 = +140 bps`.
12. It stores the run and all contribution rows.
13. The API serves the run to the dashboard.
14. The dashboard shows the move, drivers, confidence, evidence, residual, chart, narrative, run history, exposure decisions, and feedback controls.

## Practical Bottom Line

AAT currently does the hard, audit-friendly part first: it measures the move exactly, restricts itself to point-in-time-visible information, estimates factor sensitivities, calculates contribution rows, and refuses to hide the residual.

Its strongest current uses are:

- factor-first single-stock move explanation
- residual triage
- analyst workflow support
- historical attribution backfills
- evidence collection
- feedback capture

Its main next credibility jumps are:

- production price-source confirmation
- real-data validation
- residual-reduction analysis
- out-of-sample testing
- calibrated confidence
- event-study contribution methodology
- fuller hierarchical factor orthogonalization
- production-grade entity and source governance

## Implementation Reference

For readers who want to trace the implementation, the main files are:

| Area | Files |
|---|---|
| Engine contracts | `engine/contracts.py` |
| Point-in-time rule | `engine/time.py`, `tests/lookahead_audit/` |
| Return accounting | `engine/returns/accounting.py` |
| Baseline and residual reconciliation | `engine/factors/baseline.py` |
| French factor model | `engine/factors/french_model.py` |
| Sector and industry proxy model | `engine/factors/sector_model.py`, `jobs/build_proxy_factor_returns.py` |
| Peer basket model | `engine/factors/peer_model.py` |
| Style descriptors | `engine/factors/style_model.py` |
| Macro transforms and attribution | `engine/factors/macro_model.py` |
| Event features and taxonomy | `engine/events/features.py`, `engine/events/taxonomy.py`, `engine/events/surprise.py` |
| Exposure gates and review policy | `engine/exposures/gates.py`, `engine/exposures/update_policy.py` |
| Attribution orchestration | `jobs/run_attribution.py`, `jobs/run_batch_attribution.py` |
| FaustCalc imports and universe | `jobs/import_faustcalc_feature_store.py`, `jobs/import_faustcalc_sec_filings.py`, `jobs/build_faustcalc_universe.py`, `jobs/seed_faustcalc_auto_mappings.py` |
| Large backfill | `jobs/run_faustcalc_attribution_backfill.py` |
| Summary refresh | `jobs/refresh_attribution_summaries.py` |
| API | `api/main.py`, `api/schemas.py` |
| Dashboard | `dashboard/app/page.tsx`, `dashboard/components/` |
| Database models | `db/models.py`, `alembic/versions/` |
