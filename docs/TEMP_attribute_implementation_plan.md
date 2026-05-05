# Temporary Attribute Implementation Plan

Status: temporary backlog and implementation scratchpad

Do not delete yet. Expanded MVP attribution paths are implemented, but the full attribute program is not complete. This file still tracks unresolved production-readiness work: source/license decisions, event-study calibration, validation reports, positioning/options data, and remaining integration tests.

Source report: `docs/aat_architecture_attribute_expansion_report.md`

Last updated: May 4, 2026

## Current State First

Implemented and documented in permanent docs:

- Expanded attribute metadata tables and Pydantic contracts.
- Sector/industry proxy factor support.
- Custom peer-basket factor support.
- Return-based style descriptors stored as evidence/exposures.
- FRED macro ingestion, transformations, and macro factor input generation.
- EDGAR event taxonomy/evidence rows.
- Contribution stages, evidence payloads, deterministic narrative, analyst feedback persistence, CSV export, and dashboard evidence display.
- Replay-style look-ahead audit helper, MVP proving backfill orchestration, and historical universe backfill orchestration.

Latest local verification:

```powershell
python -m pytest tests/unit tests/lookahead_audit
```

Result: 50 tests passed on 2026-05-04.

Still open before this temporary file can be deleted:

- Run the historical universe backfill with real local credentials and verify expanded daily/weekly/monthly runs in the dashboard/API.
- Confirm production source and license policy for price, classification, peer, estimates, short-interest, and options data.
- Add residual reduction analysis, out-of-sample validation, confidence calibration, missing-data reporting, source availability reporting, and model/factor-basket audit reporting.
- Keep event contributions evidence-only until event-study calibration exists.
- Keep fundamentals, licensed analyst data, short-interest ingestion, options data, borrow cost, and dealer gamma out of production until sources and timestamp policies are validated.

## Purpose

This temporary plan converts the architecture and attribute expansion report into an implementation sequence. It should guide the work needed to move AAT from a five-factor MVP baseline to a broader single-stock attribution model covering market, sector, industry, peer, style, macro, event, exposure, and positioning attributes.

The plan is intentionally staged. Some attributes can be implemented with existing tables and public/free data. Others require licensing, source confirmation, analyst-curated mappings, or event-study calibration before they should become production contribution rows.

## Historical Starting Point

At the start of this attribute expansion plan, AAT implemented:

- Deterministic adjusted close-to-close return accounting.
- Point-in-time filtering with `timestamp_available <= attribution_cutoff`.
- French five-factor attribution using `Mkt-RF`, `SMB`, `HML`, `RMW`, and `CMA`.
- Explicit `unexplained_residual`.
- SEC EDGAR event ingestion.
- Heuristic EDGAR event features.
- Conservative exposure update decisions.
- FastAPI endpoints and a Next.js dashboard for attribution runs, driver tables, run history, and exposure decisions.

The architecture supported more attributes, but several implementation prerequisites were needed before broad expansion. Many of those prerequisites are now complete; the current state is summarized at the top of this file.

## Remaining Source And Policy Decisions

### 1. Confirm Data Source And License Policy

Before adding production attributes, confirm which sources are legally usable.

| Decision | Needed For | Status |
|---|---|---|
| Confirm production price source | Sector, peer, style, liquidity, beta, volatility | Pending |
| Confirm FMP license status | Existing price ingestion and ETF proxies | Pending |
| Confirm FRED API access | Macro factors | Pending |
| Confirm sector/industry classification source | Sector and industry attribution | Pending |
| Confirm peer-basket source of truth | Peer attribution | Pending |
| Confirm estimates source | Earnings, guidance, estimate revision attributes | Pending |
| Confirm options source | IV, skew, open interest, gamma attributes | Pending |
| Confirm short-interest source | Short interest and days-to-cover attributes | Pending |

Minimum near-term assumption:

- Use existing FMP price data only for development until production license status is confirmed.
- Use Kenneth French data for current style baseline.
- Use FRED for public macro series where available.
- Use analyst-curated CSV/YAML mappings for sector, industry, and peer baskets until licensed classifications are available.

### 2. Decide Attribute Adoption Stages

Each attribute should move through these stages:

| Stage | Behavior |
|---|---|
| Research | Compute offline diagnostics only. Not shown in production UI. |
| Evidence-only | Display as context, but do not allocate contribution. |
| Shadow contribution | Compute internally and compare residual reduction. |
| Production contribution | Display additive bps contribution with evidence and confidence. |
| Exposure-review integration | Use persistent evidence to suggest exposure profile review. |

No new attribute should jump directly from raw data to production contribution unless it is simple, transparent, and covered by tests.

### 3. Add Attribute Metadata Infrastructure

The current `factor_return` and `macro_series` tables can store many series, but AAT needs metadata to explain what each factor means and how it is transformed.

Required schema additions:

- `factor_definition`
- `factor_observation`
- `security_factor_exposure`
- `sector_classification_history`
- `peer_basket`
- `peer_basket_member`
- `event_taxonomy`
- `event_surprise`
- `analyst_feedback`

Recommended but lower priority:

- `positioning_observation`
- `options_observation`
- `company_exposure.review_status`
- `company_exposure.exposure_sign`
- `attribution_contribution.evidence_payload`

### 4. Establish Hierarchical Attribution Order

Before adding many attributes, create a central attribution hierarchy so factors are applied consistently and double counting is controlled.

Target order:

1. Market
2. Sector
3. Industry/subindustry
4. Peer basket
5. Style
6. Macro
7. Positioning/liquidity
8. Event
9. Unexplained residual

Implementation target:

- Add `engine/attribution/hierarchy.py`.
- Add tests proving residual reconciliation still holds.
- Add tests proving event contributions cannot be calculated before systematic factors are calculated.

### 5. Add Confidence Scoring Infrastructure

Confidence is currently attached to contributions, but scoring logic is local and simple. New attributes need shared penalties for sparse data, stale data, collinearity, source quality, proxy mismatch, unstable beta, and exposure mismatch.

Implementation target:

- Add `engine/confidence/scoring.py`.
- Encode confidence penalties.
- Keep the current five-level scale: High, Medium-High, Medium, Low-Medium, Low.

## Phase 0: Foundation Work

Goal: add the infrastructure that prevents later attribute work from becoming inconsistent.

### Tasks

- [x] Add `factor_definition` table and model.
- [x] Add `factor_observation` table and model for raw source values.
- [x] Add `security_factor_exposure` table and model.
- [x] Add `sector_classification_history` table and model.
- [x] Add `peer_basket` and `peer_basket_member` tables and models.
- [x] Add `event_taxonomy` and `event_surprise` tables and models.
- [x] Add `analyst_feedback` table and model.
- [x] Add Alembic migration for the new tables.
- [x] Add Pydantic contracts for factor definitions, observations, exposures, peer baskets, event surprise, and analyst feedback.
- [x] Add central attribution hierarchy module.
- [x] Add central confidence scoring module.
- [x] Add tests for point-in-time filtering on all new model-visible rows.
- [x] Add tests for one-basis-point reconciliation after hierarchical attribution.
- [x] Update `docs/attribution_methodology.md` with permanent methodology once Phase 0 is stable.

### Exit Criteria

- New schema migrates cleanly.
- Existing tests still pass.
- Look-ahead audit covers new timestamped tables.
- Existing French five-factor attribution behavior is unchanged.

## Phase 1: Core Market Structure Attributes

Goal: add sector, industry, subindustry, and peer attribution. This is the highest-credibility expansion.

### Attributes Covered

| Attribute | Initial Stage |
|---|---|
| Broad market | Already production through `Mkt-RF` |
| Sector return contribution | Shadow, then production |
| Industry return contribution | Shadow, then production |
| Subindustry basket contribution | Shadow, then production |
| Custom peer basket contribution | Shadow, then production |
| Peer residual spread | Evidence-only, then production diagnostic |
| Peer event read-through | Evidence-only first |

### Implementation Tasks

- [x] Create curated sector mapping file for initial MVP universe.
- [x] Create curated industry/subindustry mapping file for initial MVP universe.
- [x] Create curated peer-basket file with basket version, peer tickers, weights, and active dates.
- [x] Add ingestion job for sector/industry classifications.
- [x] Add ingestion job for peer baskets.
- [x] Add ETF or basket price ingestion for sector and industry proxies.
- [x] Implement `engine/factors/sector_model.py`.
- [x] Implement `engine/factors/peer_model.py`.
- [x] Generate `FactorContributionInput` rows for sector, industry, and peer drivers.
- [x] Add evidence strings with beta, proxy return, observations, basket version, and source timestamp.
- [x] Add confidence penalties for stale classifications, stale peer baskets, sparse observations, and high collinearity.
- [x] Update `jobs/run_attribution.py` to include sector and peer inputs after market and before style/event analysis.
- [x] Update batch attribution path.
- [ ] Update API schemas only if new evidence payloads require frontend support.
- [ ] Update dashboard driver table to display sector and peer rows cleanly.

### Tests

- [x] Unit test sector contribution calculation.
- [x] Unit test industry/proxy contribution path through sector factor inputs.
- [x] Unit test peer basket weighted return calculation.
- [x] Unit test point-in-time visibility for sector classification history through timestamp-policy coverage.
- [x] Unit test point-in-time visibility for peer basket membership through visible active weights.
- [ ] Unit test no contribution is produced when peer basket data is unavailable.
- [ ] Integration test attribution run with market, sector, peer, style, and residual rows.

### Exit Criteria

- Sector and peer contributions reconcile with residual.
- Contributions are versioned by `factor_basket_version`.
- No event attribution is allowed to absorb sector or peer movement before these factors are applied.

## Phase 2: Additional Style Attributes

Goal: extend the current French style baseline with analyst-recognizable style descriptors.

### Attributes Covered

| Attribute | Initial Stage |
|---|---|
| Size | Existing via `SMB`; add descriptor evidence |
| Value | Existing via `HML`; add earnings-yield descriptor later |
| Profitability | Existing via `RMW`; add quality descriptor later |
| Investment | Existing via `CMA`; add investment-intensity descriptor later |
| Momentum | Shadow, then production |
| Short-term reversal | Shadow |
| Realized volatility | Shadow, then production |
| Liquidity | Shadow, then production |
| Growth | Research until fundamentals source confirmed |
| Quality | Research until fundamentals source confirmed |
| Leverage | Research until fundamentals source confirmed |
| Dividend yield | Research until fundamentals source confirmed |

### Implementation Tasks

- [x] Implement `engine/factors/style_model.py`.
- [x] Add return-based descriptors from existing price bars: momentum, short-term reversal, realized volatility, and liquidity/dollar-volume where volume is available.
- [x] Add descriptor calculation contracts.
- [x] Add factor exposure estimation for style descriptors.
- [x] Store descriptor exposures in `security_factor_exposure`.
- [ ] Decide whether return-based descriptors become contribution rows or confidence/evidence modifiers.
- [ ] Add source requirements for fundamentals-based descriptors: market cap, earnings yield, revenue growth, ROE, leverage, dividend yield, capex/sales.
- [ ] Keep fundamentals-based descriptors research-only until point-in-time fundamentals are available.

### Tests

- [x] Unit test momentum calculation.
- [x] Unit test short-term reversal calculation.
- [x] Unit test realized volatility calculation.
- [x] Unit test liquidity calculation from volume and adjusted close.
- [ ] Unit test confidence downgrade for insufficient lookback.
- [ ] Integration test style descriptors do not break French five-factor attribution.

### Exit Criteria

- Momentum, volatility, and liquidity are available as shadow or production factors.
- Fundamentals-based descriptors are explicitly blocked from production until licensed point-in-time fundamentals are available.

## Phase 3: Macro Attributes

Goal: activate the existing `macro_series` pathway and add exposure-gated macro attribution.

### Attributes Covered

| Attribute | Initial Stage |
|---|---|
| 2Y Treasury yield change | Shadow, then production |
| 10Y Treasury yield change | Shadow, then production |
| 2s10s curve change | Shadow, then production |
| Fed funds expectations | Research until source confirmed |
| Dollar index | Shadow if source confirmed |
| WTI crude | Shadow, then production for exposed companies |
| Natural gas | Shadow, then production for exposed companies |
| Gold | Shadow |
| Copper | Shadow |
| High-yield credit spread | Shadow, then production |
| Investment-grade credit spread | Shadow, then production |
| VIX change | Shadow, then production |
| Inflation expectations | Shadow |

### Implementation Tasks

- [x] Add FRED adapter for macro series if not already present.
- [x] Add macro series config mapping AAT factor names to source series IDs.
- [x] Add ingestion job for FRED macro series.
- [x] Add transformation logic for level changes, spread changes, and returns.
- [x] Implement `engine/factors/macro_model.py`.
- [x] Add macro sensitivity estimation using historical stock returns and transformed macro factor moves.
- [x] Gate macro factors by exposure weights where available.
- [ ] Allow regression-stable macro factors to appear even when explicit exposure profile is missing, but lower confidence.
- [ ] Add confidence penalties for stale macro data, missing vintages, unstable beta sign, and proxy mismatch.
- [ ] Add evidence strings with beta, factor move, source series, vintage, observations, and exposure gate.

### Suggested Initial FRED Series

| AAT Attribute | Possible FRED Series |
|---|---|
| 2Y Treasury yield | `DGS2` |
| 10Y Treasury yield | `DGS10` |
| 2s10s curve | Derived from `DGS10 - DGS2` |
| High-yield credit spread | `BAMLH0A0HYM2` or similar HY OAS series |
| Investment-grade credit spread | ICE BofA IG OAS series |
| VIX | `VIXCLS` |
| Inflation expectations | 5Y breakeven or 5Y5Y forward series |

Source IDs should be verified before coding production mappings.

### Tests

- [x] Unit test macro level-change transformation.
- [x] Unit test macro spread-change transformation.
- [x] Unit test point-in-time filtering for macro vintages through timestamp-policy coverage.
- [x] Unit test macro contribution calculation.
- [ ] Unit test exposure-gated inclusion/exclusion.
- [ ] Integration test attribution run with market, sector, peer, style, macro, and residual rows.

### Exit Criteria

- Macro factors can be ingested, transformed, attributed, and displayed with confidence.
- Macro factors only appear when data coverage and exposure logic justify them.

## Phase 4: Event Taxonomy And Surprise Attributes

Goal: upgrade EDGAR heuristic event features into a richer event intelligence layer while still avoiding unsupported causal claims.

### Attributes Covered

| Attribute | Initial Stage |
|---|---|
| Earnings EPS surprise | Research until estimates source confirmed |
| Revenue surprise | Research until estimates source confirmed |
| Margin surprise | Research until estimates source confirmed |
| Guidance raise/cut | Research until estimates/source parsing confirmed |
| Estimate revision | Research until estimates source confirmed |
| Rating change | Research until licensed analyst source confirmed |
| Price target revision | Research until licensed analyst source confirmed |
| M&A event | Evidence-only, then shadow |
| Buyback/dividend event | Evidence-only, then shadow |
| Insider activity | Evidence-only with existing EDGAR Form 4 |
| Activist filing | Evidence-only with existing 13D/G support |
| Regulatory/legal event | Evidence-only |
| Product/FDA/contract event | Evidence-only until source-specific adapters exist |

### Implementation Tasks

- [x] Implement `engine/events/taxonomy.py`.
- [x] Add event categories and subtypes for current EDGAR forms.
- [x] Add `event_taxonomy` persistence.
- [x] Implement `engine/events/surprise.py`.
- [x] Add `event_surprise` persistence.
- [x] Extend EDGAR feature generation to populate event category/subtype.
- [ ] Add structured parsing for 8-K item codes where available.
- [ ] Add event materiality fields by event subtype.
- [ ] Add event evidence payloads that include source, accession, item code, event category, and timestamp.
- [ ] Keep event contribution evidence-only until event-study calibration exists.
- [ ] Design event-study calibration framework for historical windows.

### Event-Study Calibration Tasks

- [ ] Define event windows and clean windows.
- [ ] Define peer/sector-adjusted abnormal return calculation.
- [ ] Build historical event sample by category.
- [ ] Estimate distribution of abnormal returns by category, sector, and market-cap bucket.
- [ ] Map calibrated event evidence to contribution ranges.
- [ ] Add confidence rules based on sample size and event ambiguity.

### Tests

- [x] Unit test event taxonomy mapping.
- [x] Unit test 8-K item classification when item metadata is present.
- [x] Unit test event surprise calculation.
- [x] Unit test event features remain point-in-time through timestamp-policy coverage.
- [ ] Unit test event contribution is blocked until systematic factors are applied.

### Exit Criteria

- Event taxonomy and surprise rows exist.
- Current EDGAR events are classified more precisely.
- Event rows can be displayed as evidence.
- Additive event contributions remain disabled or shadow-only until calibration passes validation.

## Phase 5: Company Exposure Profiles

Goal: make macro, peer, and event attributes smarter by using structural company exposures as gates and weights.

### Attributes Covered

| Exposure | Use |
|---|---|
| Geographic revenue exposure | Gate FX, tariff, and regional macro factors |
| Segment revenue exposure | Gate peer, industry, product, and commodity factors |
| Customer concentration | Gate customer read-through events |
| Supplier concentration | Gate supplier read-through and supply disruption events |
| Commodity input exposure | Gate commodity factors and expected sign |
| Interest-rate exposure | Gate rates and curve factors |
| Credit exposure | Gate credit spread factors |
| Regulatory exposure | Gate regulatory/legal events |
| Product-cycle exposure | Gate product, FDA, clinical, and launch events |
| Foreign-exchange exposure | Gate USD and regional currency factors |

### Implementation Tasks

- [ ] Extend `company_exposure` schema or add companion table for exposure type, numeric value, bucket, sign, source span, review status, and exposure version.
- [x] Add exposure gate calculators for commodity, FX, rate, and credit exposure.
- [x] Add manual/curated exposure seed file for MVP universe.
- [x] Add ingestion job for curated exposures.
- [x] Connect exposure gates to macro model.
- [ ] Connect exposure gates to peer/event read-through.
- [ ] Connect persistent event evidence to existing exposure update policy.
- [ ] Keep automatic exposure mutation disabled.

### Tests

- [ ] Unit test exposure bucket normalization.
- [x] Unit test exposure sign handling for commodity, FX, and credit gates.
- [ ] Unit test macro gate uses exposure correctly.
- [x] Unit test commodity producer vs consumer sign.
- [x] Unit test exposure update policy remains conservative.

### Exit Criteria

- Company exposures can gate factors without automatically changing production exposure profiles.
- Exposure evidence triggers review decisions only under conservative policy.

## Phase 6: Positioning, Options, And Flow Attributes

Goal: add high-value but data-sensitive attributes after licensing is resolved.

### Attributes Covered

| Attribute | Initial Stage |
|---|---|
| Short interest | Shadow, then production |
| Days to cover | Shadow, then production |
| Borrow cost | Research until source confirmed |
| Options implied volatility | Research until source confirmed |
| IV change | Research until source confirmed |
| Put-call skew | Research until source confirmed |
| Options volume/open interest | Research until source confirmed |
| Dealer gamma exposure | Research only until methodology is validated |
| ETF flow exposure | Research until source confirmed |

### Implementation Tasks

- [ ] Confirm FINRA short-interest publication timing and license terms.
- [ ] Add short-interest ingestion.
- [ ] Add `positioning_observation` table and model.
- [x] Calculate short interest as percent of float if float source exists.
- [x] Calculate days to cover using average daily volume.
- [ ] Add confidence downgrade when float data is missing or stale.
- [ ] Confirm OPRA/OCC/vendor source for options data.
- [ ] Add `options_observation` table and model.
- [ ] Add IV, skew, volume, and open-interest transforms.
- [ ] Keep dealer gamma research-only until model is validated.

### Tests

- [x] Unit test days-to-cover calculation.
- [ ] Unit test publication-date point-in-time handling.
- [ ] Unit test options observation bounds.
- [ ] Unit test positioning confidence penalties.

### Exit Criteria

- Short interest and days-to-cover can be used with correct publication timestamps.
- Options attributes remain blocked from production until licensed data and methodology are validated.

## Phase 7: API, Dashboard, And Analyst Feedback

Goal: expose the new attributes in a usable analyst workflow and collect feedback for calibration.

### Tasks

- [x] Add richer contribution evidence payload to API response.
- [x] Add driver grouping by market, sector, peer, style, macro, positioning, event, and residual.
- [x] Add factor diagnostics view or evidence drawer.
- [x] Add analyst feedback API endpoint.
- [x] Add dashboard controls for correct, partially correct, wrong, and missing-driver feedback.
- [x] Persist feedback in `analyst_feedback`.
- [x] Add CSV export with new attributes and evidence fields.
- [x] Add UI handling for shadow/evidence-only attributes if shown.

### Tests

- [ ] API schema tests for expanded contribution payload.
- [ ] Dashboard component tests where available.
- [x] Unit test feedback validation and persistence path.
- [ ] Integration test feedback linked to attribution contribution.

### Exit Criteria

- Analysts can inspect why each contribution appeared.
- Analyst feedback can be stored and used later for calibration.

## Phase 8: Validation And Backtesting

Goal: prove that new attributes improve attribution quality without introducing leakage or false precision.

### Tasks

- [x] Add replay-style look-ahead audit over historical attribution runs.
- [x] Add MVP proving backfill command with coverage report and 10-run success threshold.
- [ ] Add residual reduction analysis by phase.
- [ ] Add out-of-sample validation for factor additions.
- [ ] Add collinearity diagnostics.
- [ ] Add confidence calibration diagnostics.
- [ ] Add per-driver missing data report.
- [ ] Add source availability report.
- [ ] Add model version and factor basket version audit report.

### Validation Metrics

| Metric | Target |
|---|---|
| Reconciliation error | Within 1 bp |
| Residual reduction | Improves out of sample, not just in sample |
| Large residual rate | Should decline after sector/peer/macro factors |
| Confidence calibration | Low confidence should correlate with larger residuals or unstable evidence |
| Look-ahead audit | Must pass for every model-visible row |
| Missing data rate | Reported by factor and security |

### Exit Criteria

- Expanded attribution improves residual quality out of sample.
- No new look-ahead failures.
- Confidence levels are directionally meaningful.

## Proposed Attribute Rollout Summary

| Phase | Production Candidates | Shadow Candidates | Research/Evidence-Only |
|---|---|---|---|
| Phase 1 | Sector, industry, peer basket | Subindustry, peer residual spread | Peer event read-through |
| Phase 2 | Momentum, volatility, liquidity | Reversal, rolling beta | Growth, quality, leverage, dividend yield |
| Phase 3 | 2Y, 10Y, curve, HY spread, IG spread, VIX | WTI, natural gas, dollar, inflation | Fed funds expectations, gold, copper, crypto |
| Phase 4 | None initially | Calibrated common events later | Earnings, guidance, revisions, M&A, buybacks, legal, product/FDA/contract |
| Phase 5 | Exposure gates | Exposure-weighted factors | Automatic exposure mutation |
| Phase 6 | Short interest, days to cover | Options volume/OI later | Borrow cost, IV, skew, gamma, ETF flows |

## Permanent Documentation Updates Needed

When each phase exits, move stable content from this temporary plan into:

- `docs/attribution_methodology.md`
- `docs/exposure_update_policy.md`
- `docs/data_licensing.md`
- `ARCHITECTURE.md`
- `PROJECT_STATUS.md`
- `CHANGELOG.md`

This temporary file should not become the long-term source of truth.

## Deletion Criteria

Delete this file only after:

- All completed phases are represented in permanent docs.
- Remaining incomplete phases are tracked as issues, roadmap items, or project status entries.
- Schema migrations and model versions are documented.
- Attribute source and license decisions are documented.
- Look-ahead audit covers all implemented attributes.
- The dashboard and API behavior are documented.

Until then, this file is the implementation scratchpad.
