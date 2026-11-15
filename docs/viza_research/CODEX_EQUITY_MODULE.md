# VIZA Equity Investment Module Research Corpus + Ontology

Prepared by: Codex
Prepared on: 2026-05-14
Masterplan source: `C:\Users\gkwls\Downloads\masterplan_sections3_to_last_updated.md`
Masterplan date: 2026-05-13
Target module: `viza.finance.equity_investment`
Status: registry-ready research corpus v0.1

This document records the section-by-section research loop requested from the masterplan. It uses the current VIZA baseline and the methodology block through line 999, then completes Section 1 through Section 41 as registry-ready research and ontology seeds. "Registry-ready" here means the section has enough structured content to convert into VIZA registries, schemas, node definitions, validation rules, source-rights policies, or engineering backlog items. It does not mean every statistical signal is production-approved for live trading.

## Current VIZA Baseline

The masterplan defines the current implementation baseline as:

```text
Phase 35 + post-phase product/log alignment remediation + 2026-05-13 packaged-engine/runtime hardening
```

The practical baseline for this research is:

- VIZA already has an Electron + React/TypeScript desktop shell, Python FastAPI local engine, local SQLite project store, and React Flow methodology canvas.
- VIZA already supports `.viza` ZIP containers, manifest-first inspection, section checksums, manifest checksums, container checksums, redacted and entitlement-locked sections, import/export, exchange inbox, file viewer, and sidebar exchange panel.
- VIZA already has a module registry, `viza.core.strategy`, `viza.finance.securities`, legacy `viza_graph_v0` compatibility, a universal entity store, a finance security master seed, credential vault abstraction, connector configuration, entitlement metadata, and point-in-time observation store.
- VIZA already has event/catalyst objects, insight schemas and registry, strategy profiles, insight translation, strategy-fit radar, insight cards, universal relationship graph, insight reaction edges, validation ledger, proof objects, and package visibility modes.
- VIZA already has runtime jobs with polling, cancellation, cache diagnostics, saved radar schedules, sidecar-backed Windows packaging, NSIS installer path, packaged-engine config hardening, runtime job failure handling, packaged sidecar smoke tests, and 303 Python unit/look-ahead tests passing as of the latest masterplan log.
- AAT is not the whole equity module. AAT should be treated as `viza.aat.attribute_analysis` or a node family within `viza.finance.equity_investment` for point-in-time modeled drivers, residuals, factor contributions, event evidence, and attribution.

Research implication: do not re-prove that VIZA can store entities, observations, events, insights, translations, validation records, or `.viza` packages. Populate the implemented substrate with an equity decision grammar, strategy taxonomy, ontology objects, registry seeds, validation rules, and rights/PIT controls.

## Methodology Applied From Lines 231-999

Every section below follows the same control loop:

1. Define section scope, exclusions, VIZA relevance, affected primitives, and required outputs.
2. Collect multiple source classes where useful: academic, professional, official/primary, practitioner, and data/vendor documentation.
3. Score sources on the masterplan scale: 5 official/peer-reviewed/regulator foundation, 4 professional or established methodology, 3 practitioner evidence, 2 discovery-only, 1 low-confidence.
4. Extract structured methods instead of loose summaries.
5. Map methods into VIZA primitives: entity, candidate set, attribute, event, evidence, assumption, transform, gate, score, relationship, scenario, decision, output, audit.
6. Generate candidate entity, node, edge, attribute, event, insight, strategy profile, output view, and validation-rule seeds.
7. Review point-in-time feasibility for observed_at, available_at, retrieved_at, source_version, data_version, model_version, vintage_required, revised_after_publication, PIT_safe, and lookahead_risk.
8. Review rights for connector_role, source_type, license_policy, query/cache/display/export/derived/redistribution/marketplace policies, attribution, and retention.
9. Design validation with out-of-sample tests, walk-forward tests, cost and liquidity gates, survivorship-bias prevention, corporate-action handling, PIT evidence, regime sensitivity, multiple-testing controls, failure-mode tracking, and human review where needed.
10. Assign confidence labels: `high_confidence_core`, `common_practice`, `research_supported_experimental`, `practitioner_observed`, `speculative_or_low_confidence`, or `rejected_or_deferred`.
11. Record progress and acceptance status.

Default rights classifications used here:

- `public_official`: official public source; cite and verify usage terms before packaging raw content.
- `public_professional`: public professional material; paraphrase and cite; do not package long raw text.
- `academic_public`: public paper or bibliographic record; cite and paraphrase.
- `academic_paywalled`: use only when legally available; do not redistribute content.
- `user_entitled_provider`: available only through a configured connector and user entitlement.
- `licensed_provider_required`: production connector required.
- `restricted_or_unclear`: no export, redistribution, or marketplace packaging.
- `derived_only`: raw values restricted; derived values may be allowed if terms permit.
- `internal_research_only`: no export, redistribution, or package inclusion.

## Source Corpus

The corpus is intentionally compact but broad. Section 31 defines the larger full-corpus expansion plan. These source IDs are reused across sections and scored using the masterplan rubric.

| ID | Source | Class | Score | Used for | Rights/PIT note |
|---|---|---:|---:|---|---|
| S001 | SEC EDGAR APIs, https://www.sec.gov/edgar/sec-api-documentation | official | 5 | filings, company facts, entity evidence | `public_official`; filing accepted/filed timestamps are PIT anchors |
| S002 | SEC Financial Statement Data Sets, https://www.sec.gov/file/financial-statement-data-sets | official | 5 | fundamentals, XBRL, accounting attributes | `public_official`; use filing period and filing date, not restated hindsight |
| S003 | SEC Form 13F FAQ, https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f | official | 5 | institutional holdings | `public_official`; 13F has reporting lag |
| S004 | Investor.gov EDGAR guide, https://www.investor.gov/introduction-investing/getting-started/researching-investments/using-edgar-research-investments | official | 5 | filing navigation, primary evidence | `public_official`; educational only |
| S005 | Investor.gov Schedules 13D and 13G, https://www.investor.gov/introduction-investing/investing-basics/glossary/schedules-13d-and-13g | official | 5 | beneficial ownership, activism | `public_official`; event available when filed |
| S006 | FINRA Equity Short Interest, https://www.finra.org/finra-data/browse-catalog/equity-short-interest | official/self-regulatory | 5 | short interest | `public_official`; publication lag and settlement cycle matter |
| S007 | FINRA Rule 5310 Best Execution, https://www.finra.org/rules-guidance/rulebooks/finra-rules/5310 | official/self-regulatory | 5 | execution and order handling | regulatory standard, not alpha signal |
| S008 | FRED API docs, https://fred.stlouisfed.org/docs/api/fred/ | official | 5 | macro series | `public_official`; normal FRED series may be revised |
| S009 | ALFRED vintage data, https://alfred.stlouisfed.org/ | official | 5 | macro PIT vintages | `public_official`; use vintages for backtests |
| S010 | CFA Institute Equity Valuation Concepts, https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/equity-valuation-concepts-basic-tools | professional | 4 | valuation methods | `public_professional`; paraphrase |
| S011 | CFA Institute Corporate Governance, https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2025/corporate-governance-conflicts-mechanisms-risks-and-benefits | professional | 4 | governance ontology | `public_professional`; paraphrase |
| S012 | Morningstar Equity Research Methodology, https://www.morningstar.com/content/dam/marketing/shared/research/methodology/705988Morningstar_Equity_Research_Methodology.pdf | professional | 4 | analyst workflow, moat, uncertainty, valuation | `public_professional`; no raw redistribution |
| S013 | Morningstar Economic Moat, https://www.morningstar.com/investing-terms/economic-moat | professional | 4 | competitive advantage | `public_professional`; concept extraction only |
| S014 | Damodaran Online Valuation, https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valuation/val.htm | professional/academic | 4 | DCF, relative valuation, valuation data | public educational; cite and paraphrase |
| S015 | S&P/MSCI GICS Methodology, https://www.spglobal.com/spdji/en/documents/methodologies/methodology-gics.pdf | vendor methodology | 4 | sector/industry taxonomy | public PDF; redistribution rules require caution |
| S016 | MSCI Factor Models, https://www.msci.com/our-solutions/factor-investing/factor-models | vendor methodology | 4 | factor/risk-model taxonomy | `licensed_provider_required` for production data |
| S017 | AQR Investing with Style, https://www.aqr.com/Insights/Research/Journal-Article/Investing-With-Style | professional/academic | 4 | value, momentum, carry, defensive style families | public research; paraphrase |
| S018 | Fama and French, Common Risk Factors, https://doi.org/10.1016/0304-405X(93)90023-5 | academic | 5 | factor model, size/value | academic citation; data must be PIT-safe |
| S019 | Fama and French, Five-Factor Model, https://doi.org/10.1016/j.jfineco.2014.10.010 | academic | 5 | profitability/investment factors | academic citation |
| S020 | Jegadeesh and Titman Momentum, https://doi.org/10.1111/j.1540-6261.1993.tb04702.x | academic | 5 | price momentum | academic citation; cost/liquidity validation required |
| S021 | Markowitz Portfolio Selection, https://doi.org/10.1111/j.1540-6261.1952.tb01525.x | academic | 5 | mean-variance portfolio construction | academic citation |
| S022 | Sharpe CAPM, https://doi.org/10.1111/j.1540-6261.1964.tb02865.x | academic | 5 | beta, expected return, risk decomposition | academic citation |
| S023 | MacKinlay Event Studies, https://www.bu.edu/econ/files/2011/01/MacKinlay-1996-Event-Studies-in-Economics-and-Finance.pdf | academic | 5 | event study methodology | public academic PDF; paraphrase |
| S024 | Piotroski F-score, https://doi.org/10.1111/1475-679X.00029 | academic | 5 | accounting strength for value stocks | academic citation; PIT filings required |
| S025 | Sloan Accruals, https://doi.org/10.2307/2491046 | academic | 5 | accrual quality | academic citation; filings/PIT required |
| S026 | Novy-Marx Gross Profitability, https://doi.org/10.1016/j.jfineco.2013.01.003 | academic | 5 | profitability/quality | academic citation |
| S027 | Frazzini and Pedersen Betting Against Beta, https://doi.org/10.1016/j.jfineco.2013.10.005 | academic | 5 | low-beta/leverage-constrained anomaly | academic citation |
| S028 | Harvey, Liu, and Zhu factor zoo, https://doi.org/10.1093/rfs/hhv059 | academic | 5 | multiple testing and factor skepticism | academic citation |
| S029 | McLean and Pontiff anomaly decay, https://doi.org/10.1111/jofi.12365 | academic | 5 | post-publication decay | academic citation |
| S030 | Ball and Brown earnings information, https://doi.org/10.2307/2490232 | academic | 5 | earnings-event information content | academic citation |
| S031 | Bernard and Thomas PEAD, https://doi.org/10.2307/2491062 | academic | 5 | post-earnings-announcement drift | academic citation |
| S032 | Tetlock media sentiment, https://doi.org/10.1111/j.1540-6261.2007.01232.x | academic | 5 | media sentiment | text rights usually restricted |
| S033 | Baker and Wurgler investor sentiment, https://www.nber.org/papers/w10449 | academic | 4 | sentiment and limits to arbitrage | academic public working paper |
| S034 | Lo, Mamaysky, and Wang technical analysis, https://doi.org/10.1111/0022-1082.00265 | academic | 5 | technical pattern testing | academic citation |
| S035 | Brock, Lakonishok, and LeBaron technical rules, https://doi.org/10.1111/j.1540-6261.1992.tb04681.x | academic | 5 | moving-average/trading-rule validation | academic citation |
| S036 | Chen, Roll, and Ross macro factors, https://doi.org/10.1086/261426 | academic | 5 | macro risk factors | academic citation; vintages needed |
| S037 | Fama and French business conditions, https://doi.org/10.1016/0304-405X(89)90095-0 | academic | 5 | regime and expected returns | academic citation |
| S038 | Pastor and Stambaugh liquidity risk, https://doi.org/10.1086/374184 | academic | 5 | liquidity risk | academic citation; data licensing needed |
| S039 | Cboe VIX, https://www.cboe.com/tradable-products/vix/ | official/vendor methodology | 4 | volatility regime | production data rights may require license |
| S040 | Dechow, Sloan, and Sweeney earnings manipulation, https://doi.org/10.2307/2491427 | academic | 5 | accounting red flags | academic citation |
| S041 | Beneish M-score, https://doi.org/10.2469/faj.v55.n5.2296 | academic/professional | 5 | manipulation-risk screen | academic/professional citation |
| S042 | Altman Z-score, https://doi.org/10.1111/j.1540-6261.1968.tb00843.x | academic | 5 | distress risk | academic citation; model recalibration required |
| S043 | Miller short-sale constraints, https://doi.org/10.1111/j.1540-6261.1977.tb03317.x | academic | 5 | divergence of opinion and constraints | academic citation |
| S044 | Cboe DataShop options data, https://datashop.cboe.com/ | vendor documentation | 3 | options positioning availability | `licensed_provider_required` |
| S045 | Berkshire Hathaway letters archive, https://www.berkshirehathaway.com/letters/letters.html | practitioner | 3 | long-term ownership, capital allocation language | public; paraphrase |
| S046 | Pershing Square presentations, https://pershingsquareholdings.com/company-reports/letters-to-shareholders/ | practitioner | 3 | activism and thesis presentation | public; paraphrase |
| S047 | SEC XBRL structured disclosure, https://www.sec.gov/structureddata/osd-inline-xbrl.html | official | 5 | structured filing extraction | `public_official`; filing timestamp required |
| S048 | SEC Form 4 explanation, https://www.investor.gov/introduction-investing/investing-basics/glossary/form-4 | official | 5 | insider transactions | `public_official`; filed timestamp required |

## Completion Matrix

Status scale: 6 = registry-ready, 7 = implementation-ready. This pass targets Status 6 for all research/masterplan sections and identifies the implementation work needed for Status 7.

| Section | Status | Sources used | Methods/controls extracted | PIT reviewed | Rights reviewed | Registry-ready output |
|---|---:|---:|---:|---|---|---|
| 1 Current VIZA Baseline | 6 | 1 local masterplan | 1 baseline | Yes | Yes | baseline constraints |
| 2 Research Protocol and Quality System | 6 | masterplan + corpus | 12-step loop | Yes | Yes | protocol schemas |
| 3 Universal Equity Decision Grammar | 6 | 18 | 12 | Yes | Yes | grammar object seeds |
| 4 Equity Strategy Family Taxonomy | 6 | 27 | 20 | Yes | Yes | strategy family registry |
| 5 Professional Analyst Workflow | 6 | 18 | 10 | Yes | Yes | analyst workflow nodes |
| 6 Fundamental Analysis | 6 | 18 | 12 | Yes | Yes | fundamental attributes |
| 7 Valuation | 6 | 14 | 9 | Yes | Yes | valuation nodes/outputs |
| 8 Industry and Competitive Analysis | 6 | 11 | 8 | Yes | Yes | industry/moat objects |
| 9 Management, Governance, Capital Allocation | 6 | 12 | 9 | Yes | Yes | governance/capital allocation seeds |
| 10 Academic Factor and Anomaly | 6 | 22 | 14 | Yes | Yes | factor/anomaly registry |
| 11 Portfolio Construction | 6 | 12 | 10 | Yes | Yes | portfolio/risk nodes |
| 12 Technical, Market-Structure, Execution | 6 | 10 | 9 | Yes | Yes | technical/execution nodes |
| 13 Event-Driven and Special Situations | 6 | 16 | 12 | Yes | Yes | event registry expansion |
| 14 Ownership, Flows, Positioning | 6 | 11 | 8 | Yes | Yes | ownership/flow objects |
| 15 Behavioral, Sentiment, Narrative | 6 | 10 | 7 | Yes | Yes | sentiment/narrative objects |
| 16 Macro, Regime, Cross-Asset | 6 | 11 | 9 | Yes | Yes | macro regime nodes |
| 17 Short-Selling and Negative Research | 6 | 13 | 9 | Yes | Yes | short thesis ontology |
| 18 Data Architecture, Source Rights, PIT | 6 | 18 | 9 | Yes | Yes | rights/PIT matrix |
| 19 Validation Framework | 6 | 22 | 12 | Yes | Yes | validation rule registry |
| 20 VIZA Entity Types | 6 | corpus | 52 entity seeds | Yes | Yes | `equity_entity_types` |
| 21 VIZA Node Palette | 6 | corpus | 64 node seeds | Yes | Yes | `equity_node_types` |
| 22 Attribute Registry Expansion | 6 | corpus | 80 attribute seeds | Yes | Yes | `equity_attribute_registry_seed` |
| 23 Event Registry Expansion | 6 | corpus | 52 event seeds | Yes | Yes | `equity_event_registry_seed` |
| 24 Insight Registry Expansion | 6 | corpus | 46 insight seeds | Yes | Yes | `equity_insight_registry_seed` |
| 25 Strategy Profile Templates | 6 | corpus | 12 profile seeds | Yes | Yes | `equity_strategy_profiles` |
| 26 Output Views | 6 | corpus | 13 output views | Yes | Yes | `equity_output_views` |
| 27 Module Manifest Proposal | 6 | local baseline | 1 manifest seed | Yes | Yes | module manifest |
| 28 Engineering Backlog | 6 | section outputs | 31 backlog items | Yes | Yes | backlog |
| 29 Final Synthesis | 6 | section outputs | synthesis workflow | Yes | Yes | final corpus outline |
| 30 Registry Artifact and Handoff | 6 | section outputs | handoff method | Yes | Yes | artifact schemas |
| 31 Full Corpus Targeting | 6 | corpus | expansion controls | Yes | Yes | corpus lattice |
| 32 Academic Anchor Topics | 6 | academic corpus | 18 anchor topics | Yes | Yes | academic traceability |
| 33 Professional/Practitioner Anchors | 6 | professional/practitioner corpus | 14 anchors | Yes | Yes | professional traceability |
| 34 Rejection and Downgrade Criteria | 6 | methodology corpus | rejection flow | Yes | Yes | rejection schema |
| 35 Section Report Template | 6 | masterplan | template | Yes | Yes | report template |
| 36 Consolidated Report Assembly | 6 | section outputs | assembly flow | Yes | Yes | final assembly checklist |
| 37 Execution Order and Dependencies | 6 | section outputs | dependency graph | Yes | Yes | execution plan |
| 38 Effort Estimation | 6 | section outputs | sizing model | Yes | Yes | effort estimates |
| 39 AI Agent Operating Protocol | 6 | masterplan | agent loop | Yes | Yes | work-log protocol |
| 40 Success Criteria and Final Gate | 6 | section outputs | acceptance checklist | Yes | Yes | final gate |
| 41 Immediate Next Step and Launch Sequence | 6 | section outputs | launch sequence | Yes | Yes | workspace launch |

## Section 1 - Current VIZA Baseline

Objective: establish what the equity research task should build on, and what it should not duplicate.

Scope and exclusions:

- Include the Phase 35 plus packaged-engine/runtime hardening baseline described above.
- Include the role of `.viza` containers, module registry, strategy core, securities module, event/catalyst objects, insights, strategy profiles, translations, validation ledger, runtime jobs, and rights-aware packaging.
- Exclude re-arguing whether VIZA should have containers, events, insights, strategy profiles, translation, or validation. Those are accepted substrate.

Research finding:

The equity module is a domain module layered over `viza.core.strategy` and able to use `viza.finance.securities` and `viza.aat.attribute_analysis`. The module should define equity-specific objects while keeping VIZA core domain-neutral.

VIZA primitive mapping:

- Entity: company, security, listing, portfolio, position, filing, event, thesis, research artifact.
- Attribute: fundamentals, valuation inputs, factor exposures, governance measures, ownership measures, technical state, sentiment state, macro exposure.
- Event: earnings, guidance, filing, capital allocation, ownership, regulatory, financing, M&A, activism, insider, market-structure.
- Evidence: SEC filing, official macro data, provider observation, public professional method, user-provided memo.
- Transform: calculation, normalization, PIT alignment, factor construction, valuation calculation, scoring.
- Gate: evidence sufficiency, PIT safety, source rights, liquidity, valuation sanity, risk constraint, profile compatibility.
- Output: radar, memo, scorecard, thesis tracker, validation report, rights report, manifest.
- Audit: method ID, source IDs, retrieved_at, observed_at, available_at, model version, validation status, rights policy.

Registry-ready seeds:

- Module ID: `viza.finance.equity_investment`
- Dependency candidates: `viza.core.strategy`, `viza.finance.securities`, optional `viza.aat.attribute_analysis`
- Baseline acceptance rule: no equity concept may be added to VIZA core unless it is expressible as a domain-neutral primitive.

Progress recorded: Status 6, registry-ready baseline constraints.

## Section 2 - Research Protocol and Quality System

Objective: turn the masterplan methodology through line 999 into reusable quality controls for every section.

Protocol objects:

| Object | Fields | VIZA use |
|---|---|---|
| `source_record` | source_id, title, organization, class, publisher, date, retrieved_at, url, score, evidence_use, rights, PIT relevance, summary | source corpus and audit |
| `method_record` | method_id, name, family, decision_question, action, target_entity, horizon, data, signals, confirmations, gates, invalidations, constraints, outputs, validation, failure_modes, PIT, rights, sources, confidence | extraction table |
| `viza_mapping_record` | mapping_id, method_id, primitives, candidate nodes, attributes, events, insights, profiles, validation, rights, confidence | registry conversion |
| `rights_record` | connector_role, source_type, license_policy, query/cache/display/export/derived/redistribution/marketplace policies, attribution, retention | packaging and UI warnings |
| `pit_record` | observed_at, available_at, retrieved_at, source_version, data_version, model_version, vintage_required, revised_after_publication, PIT_safe, lookahead_risk | backtest and audit |
| `validation_record` | rule_id, target_object, validation_level, test_type, pass_condition, fail_condition, evidence_refs, warning_policy | validation ledger |

Quality gates:

- Source breadth: at least two strong source classes for core ontology entries when possible.
- Source quality: score 5 or 4 for production core; score 3 for practitioner examples; score 2 or 1 only for discovery or rejected/deferred records.
- Extraction rigor: every method must have actions, evidence, risk gates, invalidation, output, validation, PIT, rights, and confidence.
- VIZA mapping: every method must map to primitives and at least one registry family.
- PIT safety: any historical validation must use data available at the decision timestamp.
- Rights safety: raw provider data is not packageable unless terms explicitly allow.
- Validation awareness: statistical methods require out-of-sample and cost/liquidity review; qualitative workflows require evidence sufficiency and human-review states.

Registry-ready seeds:

- `source_quality_rubric_v0`
- `method_extraction_template_v0`
- `viza_mapping_template_v0`
- `pit_rights_template_v0`
- `section_completion_matrix_v0`

Progress recorded: Status 6, registry-ready protocol.

## Section 3 - Universal Equity Decision Grammar

Objective: define the reusable grammar by which VIZA represents how investors form, test, size, monitor, invalidate, and express equity decisions.

Scope and exclusions:

- Include decision objects, thesis objects, signals, evidence, catalysts, confirmations, invalidations, gates, scores, portfolio actions, outputs, and audits.
- Exclude final strategy-family taxonomy, full valuation, full factor model registry, and production trading signals.

Source basis: S001-S005, S010, S012, S014, S018-S023, S028-S029, S045.

Core definitions:

| Term | Definition | VIZA primitive |
|---|---|---|
| Decision object | A structured choice under mandate, evidence, constraints, uncertainty, and timestamp | decision |
| Thesis | A falsifiable claim about future value, risk, event outcome, or security behavior | insight plus evidence |
| Evidence | Observed source-backed information before or at decision time | evidence |
| Signal | A transformed observation used to update belief or score | attribute/score |
| Catalyst | An event expected to change information, valuation, ownership, flows, or constraints | event/scenario |
| Confirmation | Evidence that thesis mechanism is occurring | evidence/insight |
| Invalidation | Predefined condition that weakens or breaks the thesis | gate/event/decision |
| Mandate | Strategy-specific constraints and preferences | strategy_profile |
| Action | Research, portfolio, hedge, or avoidance command | decision |
| Audit | Trace of sources, timestamps, methods, rights, and validation | audit |

Decision lifecycle grammar:

1. Universe definition.
2. Candidate generation.
3. Evidence intake.
4. Method selection.
5. Signal construction.
6. Thesis formation.
7. Scenario and valuation construction.
8. Risk and rights gates.
9. Strategy-profile translation.
10. Decision action.
11. Monitoring.
12. Confirmation or invalidation.
13. Review, resize, exit, archive, or package.

Decision action taxonomy:

- Research actions: `watch`, `research_deeper`, `request_evidence`, `defer`, `reject`.
- Portfolio actions: `buy`, `add`, `trim`, `hold`, `sell`, `short`, `cover`, `hedge`, `rebalance`.
- Communication actions: `memo`, `alert`, `scorecard`, `validation_report`, `rights_warning`.
- Packaging actions: `package_public_summary`, `package_redacted`, `block_export`.

Extracted methods:

| Method ID | Method | Decision question | Evidence | Output |
|---|---|---|---|---|
| EQM-003-01 | Thesis formation | What claim explains expected return/risk? | filings, valuation, fundamentals, events | thesis card |
| EQM-003-02 | Evidence sufficiency gate | Is support strong enough for action? | source corpus, source scores | completeness warning |
| EQM-003-03 | Signal to insight conversion | Does a signal imply actionable meaning for this profile? | attribute, benchmark, profile | insight object |
| EQM-003-04 | Catalyst mapping | What event can close the value/information gap? | event calendar, filings, macro | catalyst board |
| EQM-003-05 | Confirmation tracking | Is thesis progressing? | updated observations | thesis tracker |
| EQM-003-06 | Invalidation policy | What breaks the thesis? | thresholds, events, failed assumptions | exit/review alert |
| EQM-003-07 | Scenario decisioning | How does action vary by scenario? | model assumptions | scenario tree |
| EQM-003-08 | Strategy-profile translation | How does the same evidence change under a different mandate? | profile weights/gates | fit radar |
| EQM-003-09 | PIT audit | Could the system have known this then? | observed/available/retrieved timestamps | PIT ledger |
| EQM-003-10 | Rights audit | Can VIZA query/cache/display/export/package this? | rights policy | package gate |
| EQM-003-11 | Validation promotion | Is the method ready for production, experimental, or reject? | validation record | promotion status |
| EQM-003-12 | Cross-domain stress test | Does grammar work outside equities? | non-equity analogs | core/domain boundary check |

VIZA mapping:

- Entities: security, company, portfolio, position, event, source, thesis, decision.
- Attributes: signal value, signal direction, confidence, horizon, source score, freshness, uncertainty, profile fit.
- Events: thesis_created, evidence_added, catalyst_detected, confirmation_observed, invalidation_triggered, decision_changed, package_blocked.
- Insights: thesis_strengthened, thesis_weakened, evidence_gap, catalyst_pending, profile_conflict, PIT_warning, rights_warning.
- Outputs: decision canvas, thesis card, evidence ledger, strategy-fit radar, validation report.
- Audit: all methods require source ID, method ID, timestamp fields, rights classification, validation status.

Candidate nodes:

`equity_decision`, `equity_thesis`, `evidence_bundle`, `signal_transform`, `catalyst_map`, `confirmation_tracker`, `invalidation_gate`, `scenario_tree`, `strategy_profile_adapter`, `pit_audit`, `rights_audit`, `validation_gate`.

Candidate attributes:

`decision.action`, `decision.horizon`, `thesis.claim`, `thesis.direction`, `thesis.horizon`, `signal.value`, `signal.z_score`, `signal.direction`, `evidence.source_score`, `evidence.available_at`, `rights.export_policy`, `validation.status`.

Validation rules:

- Reject decisions with no explicit target entity, action, timestamp, evidence, or audit record.
- Downgrade thesis objects without invalidation conditions.
- Block historical validation that lacks available_at or source vintage fields.
- Block `.viza` export of restricted raw data.
- Require profile compatibility before translating insight to action.

Cross-domain stress test:

- Real estate acquisition: target property, cap-rate thesis, due-diligence evidence, financing gate, closing catalyst.
- Hiring strategy: candidate entity, evidence bundle, score, reference checks, offer decision, acceptance/decline events.
- Product launch: product entity, demand thesis, market evidence, launch catalyst, adoption confirmation, kill criteria.

Acceptance result: same primitive grammar works without adding finance-specific objects to VIZA core.

Progress recorded: Status 6, registry-ready grammar.

## Section 4 - Equity Strategy Family Taxonomy

Objective: define strategy families with decision questions, evidence standards, actions, horizons, data, gates, outputs, validation, and VIZA object implications.

Scope and exclusions:

- Include long-only, value, quality, growth, GARP, income, quant factor, quantamental, event-driven, special situations, activism, technical, execution, ownership/flow, sentiment, macro, short, market-neutral, and portfolio/risk-overlay families.
- Exclude final runnable profiles and proprietary manager taxonomies.

Source basis: S010-S019, S020-S029, S030-S046.

Taxonomy axes:

- Decision horizon: intraday, days/weeks, quarter, multi-year.
- Return source: valuation gap, quality compounding, growth surprise, factor premium, event spread, sentiment/attention, flow/positioning, macro beta, execution alpha, short deterioration.
- Evidence type: filing, fundamentals, valuation, event, price/volume, ownership, estimates, text, macro, portfolio risk.
- Action set: buy, sell, hold, short, avoid, hedge, rebalance, watch, research.
- Validation mode: historical backtest, event study, fundamental review, valuation sanity, execution analysis, human-review checklist.
- Rights sensitivity: public official, licensed market data, licensed text, user memo, restricted sell-side.

Strategy-family registry seed:

| Family ID | Family | Decision question | Core evidence | Output | Confidence |
|---|---|---|---|---|---|
| EQF-LONG-VALUE | Fundamental value | Is price below conservative intrinsic value? | filings, valuation, quality, catalysts | valuation memo | high_confidence_core |
| EQF-LONG-QUALITY | Quality compounder | Can high returns and reinvestment persist? | ROIC, margins, moat, management | quality scorecard | common_practice |
| EQF-GROWTH | Growth/surprise | Is growth underestimated? | revenue drivers, TAM, estimates, guidance | growth bridge | common_practice |
| EQF-GARP | Growth at reasonable price | Is growth attractive relative to valuation? | growth, margins, multiples, risk | GARP radar | common_practice |
| EQF-INCOME | Dividend/income | Is payout durable and attractive? | FCF, leverage, payout, board policy | income safety card | common_practice |
| EQF-QUANT-FACTOR | Factor ranking | Does the security rank well on robust factors? | value, momentum, quality, size, low beta | factor dashboard | high_confidence_core |
| EQF-QUANTAMENTAL | Quantamental | Do factor signals and analyst thesis agree? | factors plus fundamentals | blended radar | common_practice |
| EQF-EVENT-EARNINGS | Earnings event | Is reaction/drift/catalyst tradable? | earnings, guidance, estimates, price reaction | event board | research_supported_experimental |
| EQF-EVENT-MA | Merger arbitrage | Is deal spread attractive for risk? | terms, regulatory, financing, timing | deal spread memo | common_practice |
| EQF-EVENT-SPIN | Spin/restructuring | Is forced selling or separation value present? | filings, pro forma, ownership | special-sit memo | practitioner_observed |
| EQF-ACTIVISM | Activism | Can governance/capital allocation change unlock value? | 13D/G, proxy, peer margins, capital allocation | activism map | practitioner_observed |
| EQF-TECH-MOMENTUM | Technical momentum | Is trend/price confirmation valid? | price, volume, volatility, liquidity | technical panel | research_supported_experimental |
| EQF-EXECUTION | Execution-aware trading | How should an approved action be implemented? | spread, volume, volatility, order constraints | trade plan | high_confidence_core |
| EQF-OWNERSHIP-FLOW | Ownership/flow | Are flows/positioning changing risk/reward? | 13F, 13D/G, short interest, ETF/index | positioning board | common_practice |
| EQF-SENTIMENT | Behavioral/sentiment | Is attention/narrative extreme or shifting? | news, text, sentiment, search/social where entitled | narrative monitor | research_supported_experimental |
| EQF-MACRO-REGIME | Macro/regime | Is equity exposure aligned to macro regime? | rates, inflation, FX, commodities, credit, volatility | regime dashboard | common_practice |
| EQF-SHORT-FUNDAMENTAL | Fundamental short | Is downside thesis supported and borrow feasible? | red flags, valuation, deterioration, borrow | short thesis memo | common_practice |
| EQF-PAIRS-RELATIVE | Relative value/pairs | Is spread mispriced relative to peer/factor risk? | pair history, cointegration, factor neutrality | pair trade plan | research_supported_experimental |
| EQF-RISK-OVERLAY | Portfolio/risk overlay | Does position improve portfolio objective? | covariance, exposures, liquidity, drawdown | portfolio impact report | high_confidence_core |
| EQF-WATCHLIST | Research queue | Should candidate be tracked, deferred, or rejected? | partial evidence and missing gates | watchlist | high_confidence_core |

Composition methodology:

- Families can stack as tags rather than rigid hierarchy.
- A strategy profile can reference multiple family IDs with priority weights.
- The profile resolves conflicts: e.g. value says buy but liquidity gate says size lower, rights gate says no package, validation gate says experimental.

Family-level VIZA mapping:

- Family -> `strategy_family` entity and profile compatibility tag.
- Evidence standard -> node inputs and validation gates.
- Action space -> decision action vocabulary.
- Horizon -> output cadence and stale evidence thresholds.
- Required data -> connector roles and rights policies.
- Failure modes -> validation warnings and rejection/downgrade rules.

Validation by family:

- Fundamental families: filing PIT, valuation sensitivity, peer comparability, evidence sufficiency.
- Factor families: out-of-sample, walk-forward, multiple-testing control, cost/liquidity/capacity.
- Event families: event timestamp integrity, spread attribution, stale event cancellation.
- Technical/execution: data frequency, slippage, bid/ask, survivorship, regime sensitivity.
- Sentiment/narrative: source rights, manipulation/rumor gate, stale text gate.
- Short: borrow, squeeze, asymmetry, legal language, human review.

Progress recorded: Status 6, registry-ready strategy-family taxonomy.

## Section 5 - Professional Analyst Workflow Ontology

Objective: map professional equity research workflow into VIZA nodes, outputs, completeness checks, validation rules, and registry seeds.

Scope and exclusions:

- Include research intake, company snapshot, business model, industry context, thesis, valuation, catalysts, risk/invalidation, recommendation, liquidity/float, governance, evidence bundle, memo, scorecard, and thesis tracker.
- Exclude paid sell-side report copying and proprietary rating systems.

Source basis: S001-S005, S010-S014, S015, S045-S048.

Analyst workflow stages:

1. Intake: ticker/company/entity resolution, mandate, research trigger, output purpose.
2. Company snapshot: business lines, segments, geography, listing, float, market cap, fiscal calendar.
3. Business model: revenue drivers, margins, unit economics, capital intensity, cyclicality.
4. Industry context: sector, peers, competitive position, regulation, supplier/customer power.
5. Thesis: claim, mechanism, evidence, horizon, catalyst, invalidation.
6. Forecast and valuation: operating forecast, DCF or multiples, scenario range, target/expected return.
7. Risk: thesis risks, balance sheet, liquidity, governance, macro, execution, rights.
8. Recommendation: action, sizing, horizon, confidence, profile compatibility.
9. Monitoring: earnings, KPIs, catalysts, estimate changes, price/valuation drift, invalidation events.

Extracted methods:

| Method ID | Method | Inputs | Candidate output |
|---|---|---|---|
| EQM-005-01 | Research intake | security, profile, trigger, requested output | intake card |
| EQM-005-02 | Company snapshot | filings, security master, market data | company overview |
| EQM-005-03 | Business model map | filings, segment data, KPIs | model canvas |
| EQM-005-04 | Analyst thesis | evidence bundle, valuation, catalysts | thesis card |
| EQM-005-05 | Recommendation bridge | thesis, valuation, risk, mandate | action summary |
| EQM-005-06 | Target-price range | valuation scenarios, assumptions | target range |
| EQM-005-07 | Catalyst calendar | filings, earnings dates, corporate events | catalyst board |
| EQM-005-08 | Risk/invalidation table | risk factors, thresholds, events | risk register |
| EQM-005-09 | Completeness gate | required sections and evidence scores | missing evidence report |
| EQM-005-10 | Analyst scorecard | facts, methods, outputs, validation | memo quality score |

Candidate nodes:

`research_intake`, `company_snapshot`, `business_model_map`, `industry_context`, `thesis_builder`, `recommendation_bridge`, `target_price_range`, `catalyst_calendar`, `risk_invalidation_table`, `analyst_memo_builder`, `analyst_scorecard`, `thesis_tracker`.

Candidate attributes:

`rating.action`, `rating.confidence`, `target_price.low/base/high`, `expected_return.base`, `evidence_coverage.percent`, `memo.completeness_score`, `risk.count_high`, `catalyst.next_date`, `thesis.staleness_days`.

Candidate events:

`research_initiated`, `memo_completed`, `recommendation_changed`, `target_price_changed`, `risk_added`, `thesis_invalidation_observed`, `memo_stale`.

Candidate insights:

`memo_evidence_gap`, `recommendation_valuation_mismatch`, `target_price_sensitivity_high`, `risk_gate_failed`, `thesis_requires_review`.

PIT and rights:

- Filing data must use filed/accepted timestamps.
- Market data, analyst estimates, and transcripts are generally `licensed_provider_required`.
- Sell-side reports are restricted; VIZA may store user notes only when legally supplied and should not export raw text unless entitled.

Validation:

- Require target entity, source-backed evidence, explicit thesis, valuation support, risk table, invalidation conditions, and rights status before memo can be marked complete.
- Warnings for stale memo, unsupported recommendation, missing valuation sensitivity, missing balance-sheet review, missing liquidity review, and unsupported catalyst.

Progress recorded: Status 6, registry-ready analyst workflow ontology.

## Section 6 - Fundamental Analysis Ontology

Objective: encode financial statement, business-quality, operating-driver, balance-sheet, cash-flow, and accounting-quality methods into VIZA attributes, nodes, insights, and validations.

Source basis: S001, S002, S010, S012, S014, S018-S019, S024-S026, S040-S042, S047.

Core methods:

| Method ID | Method | Required data | Output |
|---|---|---|---|
| EQM-006-01 | Revenue growth decomposition | revenue, segments, units, price/mix | growth bridge |
| EQM-006-02 | Margin analysis | gross/operating/net margins, peers | margin bridge |
| EQM-006-03 | ROIC and reinvestment | NOPAT, invested capital, capex, working capital | capital efficiency card |
| EQM-006-04 | Free cash flow conversion | CFO, capex, stock comp, working capital | FCF quality insight |
| EQM-006-05 | Balance-sheet strength | leverage, coverage, maturity, liquidity | solvency gate |
| EQM-006-06 | Working-capital diagnostics | DSO, DIO, DPO, accruals | quality warning |
| EQM-006-07 | Accounting quality/accruals | accrual ratio, cash conversion | accounting-quality score |
| EQM-006-08 | Piotroski-style financial strength | profitability, leverage/liquidity, efficiency | F-score node |
| EQM-006-09 | Profitability/quality factor | gross profitability, margins, stability | quality factor |
| EQM-006-10 | Distress risk | Z-score, leverage, liquidity, profitability | distress warning |
| EQM-006-11 | Restatement/filing change review | amended filings, XBRL changes | data quality event |
| EQM-006-12 | Operating KPI mapping | company-specific KPIs | KPI tracker |

VIZA primitive mapping:

- Entities: company, segment, fiscal_period, filing, KPI, peer_group.
- Attributes: revenue_growth, gross_margin, operating_margin, ROIC, ROE, invested_capital, FCF_margin, accrual_ratio, debt_to_EBITDA, interest_coverage, current_ratio, gross_profitability, Piotroski_F_score, Altman_Z_score.
- Events: filing_received, financial_statement_restated, guidance_issued, covenant_warning, accounting_red_flag.
- Insights: margin_expansion_confirmed, cash_conversion_weak, balance_sheet_risk_high, accounting_quality_low, quality_factor_positive, distress_risk_high.

PIT:

- Use filing accepted_at as available_at.
- Avoid using later restated values in historical decisions unless the restatement was available at that time.
- Corporate actions and fiscal-calendar changes must version observations.

Rights:

- SEC facts and filings are `public_official`.
- Provider-normalized fundamentals are `licensed_provider_required` or `derived_only`.
- VIZA may compute derived ratios from public filings, but must not package provider raw values unless rights allow.

Validation:

- Cross-foot statements where possible.
- Track data source and fiscal period version.
- Reject ratios with wrong denominator sign or stale period.
- Flag peers with fiscal year mismatch.
- Require sector-aware normalization for banks, insurers, REITs, and commodity producers.

Progress recorded: Status 6, registry-ready fundamental analysis ontology.

## Section 7 - Valuation Ontology

Objective: map valuation methods into VIZA nodes, assumptions, scenarios, outputs, PIT rules, rights rules, and validation gates.

Source basis: S010, S012-S014, S021-S022, S024-S026, S045.

Valuation methods:

| Method ID | Method | Core assumptions | Output |
|---|---|---|---|
| EQM-007-01 | DCF | revenue, margin, reinvestment, terminal growth, discount rate | intrinsic value range |
| EQM-007-02 | Dividend discount | payout, dividend growth, cost of equity | dividend value |
| EQM-007-03 | Residual income | book value, ROE, cost of equity, persistence | residual value |
| EQM-007-04 | Relative valuation | peer group, multiple, normalization, spread | peer multiple range |
| EQM-007-05 | Sum of parts | segment values, holdco adjustments, debt | SOTP value |
| EQM-007-06 | NAV/asset value | asset marks, liabilities, cap rates/commodity assumptions | NAV range |
| EQM-007-07 | Precedent transaction | comparable deals, control premium, cycle | transaction value |
| EQM-007-08 | Scenario valuation | bull/base/bear assumptions and probabilities | probability-weighted value |
| EQM-007-09 | Market-implied assumptions | reverse DCF, implied growth/margin/ROIC | expectation gap |

Candidate nodes:

`dcf_model`, `relative_valuation`, `residual_income_model`, `dividend_discount_model`, `sotp_model`, `nav_model`, `precedent_transaction_model`, `scenario_valuation`, `reverse_dcf`, `margin_of_safety_gate`, `valuation_sensitivity`.

Candidate attributes:

`valuation.method`, `valuation.base_value`, `valuation.low_value`, `valuation.high_value`, `valuation.implied_upside`, `valuation.margin_of_safety`, `dcf.discount_rate`, `dcf.terminal_growth`, `dcf.terminal_value_share`, `peer.multiple_selected`, `peer_group.quality_score`, `scenario.probability`.

Insights:

`undervalued_by_base_case`, `overvalued_by_reverse_dcf`, `valuation_sensitive_to_terminal_value`, `peer_multiple_outlier`, `margin_of_safety_insufficient`, `scenario_skew_positive`.

PIT:

- Use market price as of decision timestamp.
- Use filings, estimates, and peer multiples available at that timestamp.
- Forecasts are assumptions, not observations; version them by model_version.

Rights:

- Public filing-derived assumptions can be packaged as derived values.
- Analyst estimates, consensus, and provider multiples are licensed unless user-entitled.
- Deal databases may be restricted; use public deal filings or summarize from entitled sources only.

Validation:

- Block DCF with terminal growth above long-run economic plausibility without warning.
- Warn when terminal value dominates value.
- Require sensitivity table for discount rate and terminal growth.
- Require peer group rationale and peer exclusion log.
- Require negative/financial-sector special handling.

Progress recorded: Status 6, registry-ready valuation ontology.

## Section 8 - Industry and Competitive Analysis Ontology

Objective: encode industry structure, peer mapping, moat/competitive advantage, value-chain position, regulation, cyclicality, and competitive dynamics.

Source basis: S010, S012-S015, S036-S037, S045.

Methods:

| Method ID | Method | Inputs | Output |
|---|---|---|---|
| EQM-008-01 | Industry classification | GICS/sector, business description | industry entity |
| EQM-008-02 | Peer group construction | industry, size, geography, model, margins | peer set |
| EQM-008-03 | Five-force style structure | supplier/customer power, rivalry, substitutes, entry barriers | industry structure card |
| EQM-008-04 | Moat assessment | switching costs, network effects, cost advantage, intangible assets, efficient scale | moat insight |
| EQM-008-05 | Value-chain exposure | suppliers, customers, channels, inputs | dependency map |
| EQM-008-06 | Cyclicality/regulation review | economic sensitivity, policy, rates, commodity exposure | regime warning |
| EQM-008-07 | Competitive KPI benchmarking | margins, growth, retention, unit economics | benchmark panel |
| EQM-008-08 | Disruption risk screen | technology, entrants, substitutes, regulation | disruption warning |

VIZA mapping:

- Entities: industry, sector, peer_group, value_chain_node, competitor, supplier, customer, regulator.
- Relationships: competes_with, supplies_to, sells_to, substitutes_for, regulated_by, same_industry_as.
- Attributes: industry_growth, industry_margin_median, concentration_proxy, moat_source, switching_cost_score, regulatory_intensity, cyclicality_score, peer_similarity_score.
- Events: competitor_guidance, regulatory_change, industry_price_change, input_cost_shock, disruption_event.
- Insights: moat_supported, peer_group_weak, margin_outperformance, industry_headwind, value_chain_dependency_high.

PIT/rights:

- GICS-style classification and vendor industry tags may have licensing constraints; store provider source and rights policy.
- Company descriptions and segment disclosures from filings are `public_official`.
- Alternative datasets for supply chain/customer data require connector entitlement.

Validation:

- Require explicit peer inclusion/exclusion rules.
- Warn when peer group is too small or too heterogeneous.
- Require source-backed moat claim and invalidate if returns/margins deteriorate persistently.
- Track classification version.

Progress recorded: Status 6, registry-ready industry/competitive ontology.

## Section 9 - Management, Governance, and Capital Allocation Ontology

Objective: encode management quality, governance structures, incentives, shareholder rights, capital allocation, insider behavior, and stewardship evidence.

Source basis: S001, S004-S005, S011-S012, S045-S048.

Methods:

| Method ID | Method | Evidence | Output |
|---|---|---|---|
| EQM-009-01 | Governance structure review | DEF 14A, bylaws, board data | governance scorecard |
| EQM-009-02 | Incentive alignment | compensation metrics, ownership, TSR metrics | incentive alignment insight |
| EQM-009-03 | Capital allocation history | capex, M&A, buybacks, dividends, debt | capital allocation score |
| EQM-009-04 | Insider transaction review | Form 4, plan notes, role | insider activity event |
| EQM-009-05 | Related-party and control review | proxy, filings | governance risk warning |
| EQM-009-06 | Activist vulnerability | ownership, margins, valuation, governance | activism vulnerability |
| EQM-009-07 | Stewardship/culture evidence | letters, disclosures, long-term record | management quality thesis |
| EQM-009-08 | Dilution and SBC review | share count, options, SBC | dilution warning |
| EQM-009-09 | M&A discipline review | deal history, returns, impairments | acquisition discipline insight |

Candidate nodes:

`governance_scorecard`, `incentive_alignment`, `capital_allocation_history`, `insider_activity_monitor`, `activist_vulnerability`, `dilution_review`, `management_quality_thesis`.

Attributes:

`board_independence`, `dual_class_flag`, `insider_ownership_pct`, `comp_metric_quality`, `buyback_yield`, `dividend_payout_ratio`, `net_debt_change`, `share_count_growth`, `M&A_impairment_history`, `insider_net_buy_sell`.

Events:

`proxy_filed`, `director_change`, `executive_change`, `compensation_plan_changed`, `buyback_authorized`, `dividend_changed`, `insider_buy`, `insider_sell`, `activist_13d_filed`.

Insights:

`capital_allocation_accretive`, `dilution_risk_high`, `incentives_misaligned`, `governance_entrenchment_risk`, `insider_signal_positive`, `activist_pressure_rising`.

PIT/rights:

- SEC filings and Form 4 are public official but have filing lags.
- Governance vendor scores are licensed; VIZA should compute public-derived fields where possible and mark vendor scores as entitled.

Validation:

- Do not treat insider sales as bearish without plan/context review.
- Require capital allocation claims to link to measurable outcomes.
- Flag governance scores without source lineage.
- Require human review for serious misconduct or fraud language.

Progress recorded: Status 6, registry-ready governance/capital allocation ontology.

## Section 10 - Academic Factor and Anomaly Ontology

Objective: extract academic factor/anomaly streams into VIZA factor objects, attributes, validation rules, confidence labels, and rejection/downgrade controls.

Source basis: S017-S029, S034-S038, S043.

Factor taxonomy:

- Risk model factors: market, size, value, profitability, investment, momentum, beta, liquidity.
- Anomaly signals: accruals, gross profitability, quality, post-earnings drift, low beta, distress, net issuance, short interest, sentiment.
- Implementation overlays: costs, turnover, liquidity, capacity, crowding, decay, multiple-testing.

Extracted factor/anomaly methods:

| Method ID | Signal | Evidence | Confidence |
|---|---|---|---|
| EQM-010-01 | Market beta | CAPM/factor models | high_confidence_core |
| EQM-010-02 | Size | Fama-French | high_confidence_core as risk descriptor |
| EQM-010-03 | Value/book-to-market | Fama-French, style research | high_confidence_core as factor exposure |
| EQM-010-04 | Momentum | Jegadeesh-Titman, AQR | high_confidence_core but cost-sensitive |
| EQM-010-05 | Profitability | Fama-French five-factor, Novy-Marx | high_confidence_core |
| EQM-010-06 | Investment/conservative asset growth | Fama-French five-factor | high_confidence_core |
| EQM-010-07 | Low beta/BAB | Frazzini-Pedersen | research_supported_experimental |
| EQM-010-08 | Accruals | Sloan | high_confidence_core as accounting-quality warning |
| EQM-010-09 | Piotroski F-score | Piotroski | common_practice/high_confidence for value screen |
| EQM-010-10 | PEAD | Ball-Brown, Bernard-Thomas | research_supported_experimental |
| EQM-010-11 | Liquidity risk | Pastor-Stambaugh | high_confidence_core as risk descriptor |
| EQM-010-12 | Technical trend | Brock, Lo et al. | research_supported_experimental |
| EQM-010-13 | Sentiment/media | Tetlock, Baker-Wurgler | research_supported_experimental |
| EQM-010-14 | Short-sale constraints | Miller | common_practice risk mechanism |

VIZA mapping:

- Entities: factor_model, factor_signal, anomaly_signal, portfolio, security.
- Attributes: factor_exposure, factor_rank, factor_score, factor_return, factor_crowding_proxy, factor_decay_flag, turnover_estimate, capacity_estimate.
- Events: factor_rebalance, factor_regime_shift, signal_decay_detected, crowding_warning.
- Insights: factor_supports_thesis, factor_conflicts_with_thesis, anomaly_experimental, factor_crowding_high, multiple_testing_warning.

Promotion rules:

- Promote to `high_confidence_core` only if source quality is strong, signal definition is implementable with PIT data, validation can include costs/liquidity, and use is framed as exposure/risk or tested signal.
- Downgrade if sample mining, microcap dependence, high turnover, no cost treatment, weak economic rationale, or post-publication decay risk dominates.

Validation:

- Require walk-forward and out-of-sample.
- Include transaction costs, bid/ask, turnover, shorting constraints, borrow if short leg exists.
- Use delisting returns and corporate-action-adjusted data.
- Track publication date and signal decay.
- Apply multiple-testing warnings for factor combinations.

Progress recorded: Status 6, registry-ready factor/anomaly ontology.

## Section 11 - Portfolio Construction Ontology

Objective: encode portfolio-level constraints, sizing, risk, liquidity, capacity, rebalancing, hedging, tax/account constraints, and portfolio outputs.

Source basis: S017, S021-S022, S027, S038-S039, S045.

Methods:

| Method ID | Method | Inputs | Output |
|---|---|---|---|
| EQM-011-01 | Mandate and constraint definition | profile, benchmark, account | mandate object |
| EQM-011-02 | Position sizing | conviction, risk, liquidity, volatility | sizing recommendation |
| EQM-011-03 | Risk decomposition | beta, factor, sector, idiosyncratic | risk contribution |
| EQM-011-04 | Correlation/covariance | returns, factors, regime | correlation map |
| EQM-011-05 | Liquidity/capacity gate | ADV, spread, ownership, turnover | capacity warning |
| EQM-011-06 | Rebalancing | drift, signal decay, costs, taxes | rebalance plan |
| EQM-011-07 | Hedging | factor/sector/index/option hedge | hedge plan |
| EQM-011-08 | Drawdown/risk budget | portfolio losses, VaR-style limits | risk gate |
| EQM-011-09 | Tax/account constraints | holding period, wash-sale risk, account type | tax-aware warning |
| EQM-011-10 | Portfolio impact report | marginal contribution to risk/return | impact report |

VIZA mapping:

- Entities: portfolio, account, position, benchmark, hedge, risk_model, rebalance_event.
- Attributes: position_weight, active_weight, beta, volatility, tracking_error, factor_exposure, sector_exposure, liquidity_days_to_trade, ADV_pct, risk_contribution, expected_return, drawdown.
- Events: position_opened, position_resized, rebalance_triggered, limit_breached, hedge_added, thesis_exit.
- Insights: position_too_large_for_liquidity, factor_concentration_high, portfolio_fit_positive, hedge_needed, rebalance_due.

PIT/rights:

- Historical prices and volumes often require licensed data for production.
- User portfolio holdings are private/user-owned and should not be exported without explicit user action.
- Benchmark/risk model data may require vendor license.

Validation:

- Require mandate before sizing.
- Require liquidity and concentration gates.
- Require corporate-action-adjusted historical data.
- Validate covariance estimation window and regime sensitivity.
- For recommendations, present as decision support, not personalized advice.

Progress recorded: Status 6, registry-ready portfolio construction ontology.

## Section 12 - Technical, Market-Structure, and Execution Ontology

Objective: separate technical analysis, market-structure observations, and execution controls, then map each to VIZA nodes and validation rules.

Source basis: S007, S020, S034-S035, S039, S044.

Domain separation:

- Technical analysis: price/volume-derived state, trend, momentum, reversal, breakout, support/resistance candidates.
- Market structure: spread, depth, volume, volatility, auction/session effects, halt status, listing venue, borrow/short restrictions.
- Execution: order plan, urgency, slippage, liquidity, participation, best-execution constraints.

Methods:

| Method ID | Method | Inputs | Output |
|---|---|---|---|
| EQM-012-01 | Momentum/trend confirmation | returns, moving averages | trend insight |
| EQM-012-02 | Volatility regime | realized vol, VIX proxy | regime state |
| EQM-012-03 | Breakout/reversal screen | price levels, volume | technical event |
| EQM-012-04 | Liquidity/spread screen | bid/ask, ADV, spread | execution gate |
| EQM-012-05 | Market-impact estimate | order size, ADV, volatility | trade-cost estimate |
| EQM-012-06 | Execution plan | urgency, limit, participation | trade plan |
| EQM-012-07 | Halt/short-sale restriction check | venue/regulatory data | block/warning |
| EQM-012-08 | Technical catalyst confirmation | technical state plus fundamental event | confirmation insight |
| EQM-012-09 | Slippage review | fills, arrival price, VWAP/TWAP | execution quality report |

Candidate nodes:

`technical_signal`, `trend_state`, `volatility_regime`, `liquidity_gate`, `execution_plan`, `market_impact_estimator`, `slippage_review`, `venue_constraint_check`.

PIT/rights:

- Intraday/order book data is licensed; do not package raw data without rights.
- EOD public data may still have provider terms.
- Execution records are user-private and should be export-controlled.

Validation:

- Technical signals must be tested with costs, slippage, and survivorship controls.
- Execution outputs must distinguish analysis from order routing.
- Best-execution rules are compliance context, not a VIZA guarantee.
- Avoid lookahead from same-day close if decision occurred before close.

Progress recorded: Status 6, registry-ready technical/execution ontology.

## Section 13 - Event-Driven and Special Situations Ontology

Objective: encode event objects, event lifecycle, materiality, earnings/guidance, analyst revisions, M&A, spins, restructuring, activism, capital allocation, insider, regulatory, litigation, and product events.

Source basis: S001-S005, S010-S012, S023, S030-S031, S046-S048.

Event lifecycle:

`rumored_or_hypothesized -> announced -> filed/source_confirmed -> terms_updated -> effective/occurred -> completed/cancelled -> post_event_reviewed`

Methods:

| Method ID | Method | Event | Output |
|---|---|---|---|
| EQM-013-01 | Earnings surprise/drift | earnings, guidance, price reaction | earnings event board |
| EQM-013-02 | Guidance revision | guidance update | estimate/thesis update |
| EQM-013-03 | Analyst revision monitor | ratings/estimates where entitled | revision insight |
| EQM-013-04 | Merger-arbitrage spread | deal terms, price, timing, approvals | deal spread card |
| EQM-013-05 | Spin-off/restructuring | filing, distribution terms | special-sit memo |
| EQM-013-06 | Activism event | 13D, letter, proxy | activism board |
| EQM-013-07 | Buyback/dividend/debt issuance | board/filing/press release | capital allocation event |
| EQM-013-08 | Insider transaction | Form 4 | insider event |
| EQM-013-09 | Regulatory/litigation/product event | filing/news/official source | event risk card |
| EQM-013-10 | Event materiality scoring | price, size, source, thesis relevance | materiality score |
| EQM-013-11 | Event stale/cancelled state | elapsed time, update absence | stale event warning |
| EQM-013-12 | Event study validation | event window, abnormal return | validation report |

Candidate event types:

`earnings_reported`, `guidance_issued`, `guidance_withdrawn`, `analyst_rating_changed`, `estimate_revised`, `ma_announced`, `ma_terms_updated`, `ma_completed`, `ma_terminated`, `spin_announced`, `restructuring_announced`, `activist_13d_filed`, `proxy_contest_started`, `buyback_authorized`, `dividend_changed`, `debt_issued`, `equity_issued`, `insider_transaction_filed`, `regulatory_action`, `litigation_event`, `product_approval`, `product_recall`.

PIT/rights:

- Official filings provide strong PIT anchors.
- News/transcripts/estimate revisions require licensed connectors.
- Rumors should not become core event objects unless flagged as low-confidence and non-exportable.

Validation:

- Require source credibility and event timestamp.
- Event-driven methods need event-window validation and stale/cancelled states.
- Merger-arb requires deal terms, regulatory path, financing, shareholder votes, timing, downside case.
- Serious legal/fraud assertions require human review and cautious language.

Progress recorded: Status 6, registry-ready event-driven ontology.

## Section 14 - Ownership, Flows, and Positioning Ontology

Objective: encode institutional holdings, beneficial ownership, passive/index/ETF flows, short interest, options positioning, analyst coverage, crowding, and flow/crowding warnings.

Source basis: S003, S005-S006, S016-S017, S038, S043-S044, S046-S048.

Methods:

| Method ID | Method | Inputs | Output |
|---|---|---|---|
| EQM-014-01 | 13F holdings monitor | 13F filings | institutional ownership lagged view |
| EQM-014-02 | 13D/13G activist ownership | beneficial ownership filings | activist ownership event |
| EQM-014-03 | Insider ownership/trading | Form 4, proxy | insider positioning |
| EQM-014-04 | Short interest monitor | FINRA/exchange short interest | short interest insight |
| EQM-014-05 | Borrow/squeeze feasibility | borrow rate/availability where entitled | squeeze risk gate |
| EQM-014-06 | Options positioning | OI/volume/skew where licensed | options positioning card |
| EQM-014-07 | Index/ETF flow exposure | index membership, ETF ownership | flow pressure insight |
| EQM-014-08 | Crowding/compression | ownership concentration, factor crowding, liquidity | crowding warning |

Candidate attributes:

`institutional_ownership_pct`, `top_holder_concentration`, `13f_holding_change`, `beneficial_owner_pct`, `short_interest_pct_float`, `days_to_cover`, `borrow_rate`, `borrow_availability`, `option_open_interest`, `put_call_ratio`, `index_member_flag`, `ETF_ownership_proxy`, `crowding_score`.

PIT:

- 13F is lagged; use report_period and filed_at separately.
- Short interest is periodic and published after settlement/report dates.
- Options and borrow data are time-sensitive and usually licensed.

Rights:

- Public filings are public official.
- Borrow, options, ETF flows, and real-time positioning usually require licensed providers.
- User portfolio/crowding data may be private.

Validation:

- Never treat lagged 13F changes as current holdings without warning.
- Require float and split-adjusted share data for short interest.
- Borrow/squeeze signals require borrow availability and price/liquidity context.
- Options signals require expiration/moneyness normalization.

Progress recorded: Status 6, registry-ready ownership/flow ontology.

## Section 15 - Behavioral, Sentiment, and Narrative Ontology

Objective: represent behavioral mechanisms, investor attention, news/social sentiment, narrative, herding, limits to arbitrage, and misinformation/manipulation risk.

Source basis: S032-S033, S043, S012, S017, S039.

Methods:

| Method ID | Method | Inputs | Output |
|---|---|---|---|
| EQM-015-01 | News sentiment | news text where licensed | sentiment insight |
| EQM-015-02 | Media pessimism/attention | article volume, tone, abnormal attention | attention warning |
| EQM-015-03 | Investor sentiment regime | broad sentiment indicators | sentiment regime |
| EQM-015-04 | Narrative extraction | recurring themes, thesis claims | narrative map |
| EQM-015-05 | Herding/crowding | ownership, price momentum, flows | herding warning |
| EQM-015-06 | Limits-to-arbitrage gate | short constraints, liquidity, volatility | mispricing persistence gate |
| EQM-015-07 | Rumor/manipulation guard | source credibility, abnormal spread, unverifiable claims | rumor quarantine |

Candidate nodes:

`sentiment_signal`, `attention_signal`, `narrative_map`, `crowding_herding_monitor`, `limits_to_arbitrage_gate`, `rumor_quarantine`.

Attributes:

`sentiment_score`, `sentiment_direction`, `attention_z_score`, `news_count`, `narrative_topic`, `narrative_persistence`, `source_credibility_score`, `rumor_flag`, `manipulation_risk_flag`.

Insights:

`sentiment_extreme_positive`, `sentiment_extreme_negative`, `narrative_shift_detected`, `attention_spike_unconfirmed`, `rumor_quarantined`, `limits_to_arbitrage_high`.

PIT/rights:

- Text/news/social data is usually licensed or platform-restricted.
- Store derived sentiment only when allowed; raw text often cannot be packaged.
- Social/rumor sources are low-confidence unless triangulated.

Validation:

- Require timestamped documents and no future text leakage.
- Apply source credibility and manipulation-risk gates.
- Downgrade sentiment signals without out-of-sample validation.
- Do not convert rumor directly into investment action.

Progress recorded: Status 6, registry-ready behavioral/sentiment ontology.

## Section 16 - Macro, Regime, and Cross-Asset Ontology

Objective: encode macro evidence, regime objects, scenarios, rate/inflation/FX/commodity/credit exposure, policy events, volatility/liquidity regimes, and cross-asset context.

Source basis: S008-S009, S036-S039, S021-S022, S015-S017.

Macro evidence schema:

`series_id`, `source`, `observed_period`, `released_at`, `vintage`, `value`, `revision_flag`, `frequency`, `geography`, `asset_exposure`, `rights_policy`.

Methods:

| Method ID | Method | Inputs | Output |
|---|---|---|---|
| EQM-016-01 | Macro regime classification | growth, inflation, rates, credit, volatility | regime state |
| EQM-016-02 | Rate sensitivity | duration-like equity exposure, discount rate | rate exposure insight |
| EQM-016-03 | Inflation exposure | pricing power, input costs, margins | inflation sensitivity |
| EQM-016-04 | FX exposure | revenue/cost geography, currencies | FX risk map |
| EQM-016-05 | Commodity exposure | inputs, outputs, commodity prices | commodity sensitivity |
| EQM-016-06 | Credit/financial conditions | spreads, lending standards, leverage | credit regime warning |
| EQM-016-07 | Volatility/liquidity regime | VIX/realized vol/liquidity | risk regime |
| EQM-016-08 | Policy/geopolitical event mapping | central bank, fiscal, country risk | policy event card |
| EQM-016-09 | Scenario overlay | bull/base/bear macro assumptions | scenario valuation overlay |

Candidate nodes:

`macro_evidence`, `macro_regime_classifier`, `rate_sensitivity`, `inflation_exposure`, `FX_exposure`, `commodity_exposure`, `credit_conditions`, `volatility_regime`, `policy_event_mapper`, `macro_scenario_overlay`.

PIT:

- Use ALFRED vintages for historical macro validation.
- Release dates differ from observation periods; both are required.
- Revisions must be captured.

Rights:

- FRED/ALFRED public official data can support public-derived values.
- Vendor macro surprise indices, cross-asset data, and country-risk scores are licensed.

Validation:

- Require vintage data for backtests.
- Avoid overfitting regime thresholds.
- Validate sector/company exposure assumptions.
- Distinguish macro sensitivity from causal attribution.

Progress recorded: Status 6, registry-ready macro/regime ontology.

## Section 17 - Short-Selling and Negative Research Ontology

Objective: encode short thesis objects, negative evidence taxonomy, overvaluation, accounting red flags, deterioration, distress, governance/promotional behavior, borrow/squeeze, failed catalysts, and legal/product-safety guardrails.

Source basis: S006, S014, S020, S025, S040-S043, S048, S032-S033.

Negative thesis schema:

`target`, `negative_claim`, `evidence_bundle`, `horizon`, `borrow_requirements`, `catalyst`, `invalidation`, `asymmetry`, `squeeze_risk`, `legal_review_required`, `rights_policy`, `confidence`.

Methods:

| Method ID | Method | Evidence | Output |
|---|---|---|---|
| EQM-017-01 | Overvaluation short | reverse DCF, multiples, sentiment | overvaluation insight |
| EQM-017-02 | Accounting red-flag screen | accruals, Beneish, restatements | accounting warning |
| EQM-017-03 | Fundamental deterioration | revenue/margin/cash-flow decline | deterioration thesis |
| EQM-017-04 | Leverage/distress | Altman, coverage, maturities | distress risk |
| EQM-017-05 | Promotional/governance behavior | dilution, related-party, aggressive claims | governance warning |
| EQM-017-06 | Borrow/squeeze gate | borrow, short interest, liquidity, options | implementation gate |
| EQM-017-07 | Failed catalyst/broken thesis | expected catalyst did not occur | cover/review alert |
| EQM-017-08 | Fraud-risk guardrail | source credibility and legal review | restricted language gate |
| EQM-017-09 | Pair/hedged short | long/short relative valuation | pair plan |

Candidate nodes:

`negative_thesis`, `accounting_red_flag`, `deterioration_monitor`, `distress_risk`, `borrow_squeeze_gate`, `promotional_behavior_review`, `short_invalidation_gate`, `legal_language_review`.

PIT/rights:

- Borrow data is licensed.
- Public short reports can inform practitioner language but are not high-confidence core without triangulation.
- Defamatory/fraud assertions require human review and careful source-backed wording.

Validation:

- Require borrow and liquidity gates before any short action.
- Include asymmetric loss and squeeze risk.
- Require PIT filings for accounting signals.
- Downgrade weakly sourced accusations to warning/research_deeper, not action.

Progress recorded: Status 6, registry-ready short/negative research ontology.

## Section 18 - Data Architecture, Source Rights, and PIT Requirements

Objective: define the data architecture rules that let the equity module use public, licensed, user-entitled, derived, and restricted data without lookahead bias or rights leakage.

Source basis: S001-S009, S015-S016, S039, S044, S047-S048 plus the masterplan methodology.

Core principle:

Every observation must carry provenance, availability, rights, and version fields. VIZA should treat "data exists now" and "data was knowable then" as different facts.

Connector role taxonomy:

| Role | Examples | Default rights posture |
|---|---|---|
| `official_public_connector` | SEC, FRED, ALFRED, FINRA public pages | query/display generally allowed; verify export terms |
| `licensed_market_data_connector` | prices, intraday, order book, options, borrow | user entitlement required; raw export usually blocked |
| `licensed_fundamentals_connector` | normalized fundamentals, estimates, transcripts | user entitlement required; raw package blocked unless licensed |
| `licensed_text_connector` | news, transcripts, social/search | raw text often restricted; derived summary only if allowed |
| `user_document_connector` | user memos, spreadsheets, private notes | user-controlled; privacy and export controls required |
| `derived_calculation_engine` | VIZA ratios, factors, scores | export depends on source inputs and derivation terms |

Observation schema seed:

```json
{
  "observation_id": "obs_eq_...",
  "entity_id": "company_or_security_id",
  "attribute_key": "fundamental.revenue",
  "value": null,
  "unit": "USD",
  "period_start": null,
  "period_end": null,
  "observed_at": null,
  "available_at": null,
  "retrieved_at": null,
  "source_id": "S001",
  "source_version": null,
  "data_version": null,
  "model_version": null,
  "vintage_required": true,
  "revised_after_publication": null,
  "PIT_safe": null,
  "rights_policy_id": "rights_public_official_v0"
}
```

Rights policy matrix:

| Data type | PIT field emphasis | Default rights | VIZA packaging rule |
|---|---|---|---|
| SEC filings/XBRL | filed_at/accepted_at | public official | package links, metadata, derived values; avoid large raw reproduction |
| FRED macro | release date/vintage | public official | use ALFRED for backtests; cite source |
| Market prices/EOD | timestamp, adjustment version | provider-dependent | export only if terms allow; derived returns may be allowed |
| Intraday/order book | timestamp/venue | licensed | never package raw without explicit rights |
| Estimates/transcripts/news | publication timestamp | licensed/restricted | user-entitled connector; summary/derived only if allowed |
| User portfolio | user timestamp | private | export only under explicit user action |
| Social/search/alternative data | collection timestamp | restricted/unclear | default to non-exportable and discovery-only |

Candidate nodes:

`source_record`, `observation_store`, `rights_policy`, `PIT_audit`, `vintage_selector`, `connector_requirement`, `data_quality_warning`, `entity_resolution`, `corporate_action_adjuster`.

Candidate insights:

`PIT_safe`, `lookahead_risk`, `rights_export_blocked`, `data_revision_detected`, `connector_entitlement_missing`, `source_stale`.

Validation rules:

- Block backtest if required observations lack available_at.
- Block export/package when any included raw data has restricted or unclear rights.
- Require source_id and rights_policy_id for every data-dependent attribute.
- Require corporate-action-adjusted price series for return validation.
- Require source version and vintage for macro/fundamental history.

Failure modes:

- Restated fundamentals used as historical truth.
- Provider normalized field cached without license.
- Filing period mistaken for availability date.
- 13F holdings treated as current.
- News/social text redistributed without rights.

Progress recorded: Status 6, registry-ready data architecture and PIT/rights framework.

## Section 19 - Validation Framework

Objective: define validation objects, levels, warnings, promotion rules, and family-specific validation requirements for the equity module.

Source basis: S021-S029, S023, S028-S029, S034-S038, S001-S009, S040-S043.

Validation object schema:

```json
{
  "validation_rule_id": "eq_val_...",
  "target_type": "method | node | attribute | event | insight | profile | output | package",
  "target_id": "",
  "validation_level": "schema | data | PIT | rights | evidence | statistical | qualitative | output",
  "required_inputs": [],
  "test_method": "",
  "pass_condition": "",
  "warning_condition": "",
  "fail_condition": "",
  "failure_severity": "info | warning | block",
  "evidence_refs": [],
  "confidence_impact": "",
  "audit_fields": []
}
```

Validation levels:

- Schema validity: object has required fields, IDs, versions, and compatible connections.
- Data validity: observations are typed, units are correct, values are plausible, periods are aligned.
- PIT validity: no observation or text is used before available_at.
- Rights validity: output/package behavior respects rights policy.
- Evidence sufficiency: claims have source-backed evidence.
- Statistical validity: backtests use out-of-sample, walk-forward, costs, liquidity, survivorship and multiple-testing controls.
- Qualitative validity: analyst/LLM-assisted outputs preserve source lineage, uncertainty, and human-review flags.
- Output validity: memo/card/radar can be generated without unsupported claims or hidden restricted data.

Candidate validation rules:

| Rule ID | Target | Rule | Severity |
|---|---|---|---|
| EQ-VAL-001 | all observations | source_id, observed_at, available_at, retrieved_at required | block |
| EQ-VAL-002 | historical tests | reject future-revised or unavailable data | block |
| EQ-VAL-003 | packages | restricted raw data cannot be exported | block |
| EQ-VAL-004 | thesis | claim requires evidence, horizon, catalyst or mechanism, invalidation | warning/block by profile |
| EQ-VAL-005 | valuation | DCF requires sensitivity and terminal value warning | warning |
| EQ-VAL-006 | factor signal | require cost/liquidity and OOS review before production | block for production |
| EQ-VAL-007 | event | event needs source credibility, timestamp, lifecycle state | warning/block |
| EQ-VAL-008 | short thesis | borrow/squeeze/legal review required | block |
| EQ-VAL-009 | sentiment | rumor and low-credibility text cannot drive action | block |
| EQ-VAL-010 | portfolio sizing | mandate, liquidity, concentration, risk budget required | block |
| EQ-VAL-011 | output | unsupported or restricted claim redacted/warned | block |
| EQ-VAL-012 | profile | insight action must be compatible with profile family and risk gates | warning/block |

Warning taxonomy:

`missing_evidence`, `PIT_unknown`, `lookahead_risk`, `rights_unknown`, `connector_missing`, `stale_observation`, `unsupported_claim`, `statistical_overfit`, `costs_missing`, `liquidity_capacity_missing`, `source_credibility_low`, `human_review_required`, `package_redaction_required`.

Promotion methodology:

- Candidate -> accepted when schema, sources, mapping, PIT, rights, and basic validation pass.
- Accepted -> registry-ready when validation rules and failure modes exist.
- Registry-ready -> implementation-ready when fixtures and runtime tests load in module registry.
- Downgrade or reject when any block-level rule fails.

Progress recorded: Status 6, registry-ready validation framework.

## Section 20 - VIZA Entity Types

Objective: define equity module entity types and required fields while preserving VIZA core as domain-neutral.

Source basis: corpus-wide, especially S001-S009, S015-S016, S047-S048.

Base entity schema:

```json
{
  "entity_type_id": "equity.company",
  "label": "Company",
  "module": "viza.finance.equity_investment",
  "core_primitive": "entity",
  "required_identifiers": [],
  "required_fields": [],
  "relationships": [],
  "default_rights_policy": "",
  "PIT_fields_required": true,
  "confidence_label": "high_confidence_core"
}
```

Entity type registry seed:

| Family | Entity types |
|---|---|
| Tradable/security | `equity.security`, `equity.common_stock`, `equity.ADR`, `equity.listing`, `equity.exchange`, `equity.index_member`, `equity.option_contract`, `equity.borrow_instrument` |
| Issuer/company | `equity.company`, `equity.segment`, `equity.subsidiary`, `equity.business_line`, `equity.peer_group`, `equity.industry`, `equity.sector` |
| Portfolio | `equity.portfolio`, `equity.account`, `equity.position`, `equity.trade_intent`, `equity.order_plan`, `equity.benchmark`, `equity.hedge` |
| Evidence/document | `equity.filing`, `equity.financial_statement`, `equity.proxy_statement`, `equity.press_release`, `equity.presentation`, `equity.transcript`, `equity.news_document`, `equity.user_memo`, `equity.source_record` |
| Event/catalyst | `equity.event`, `equity.catalyst`, `equity.earnings_event`, `equity.MA_deal`, `equity.spin_event`, `equity.activism_event`, `equity.regulatory_event`, `equity.insider_transaction` |
| Research/decision | `equity.thesis`, `equity.decision`, `equity.scenario`, `equity.assumption`, `equity.evidence_bundle`, `equity.validation_record`, `equity.rights_policy` |
| Analyst/estimate | `equity.analyst_estimate`, `equity.consensus_snapshot`, `equity.rating_change`, `equity.target_price_record` |
| Ownership/governance | `equity.institutional_holder`, `equity.beneficial_owner`, `equity.insider`, `equity.board_member`, `equity.executive`, `equity.share_class`, `equity.compensation_plan` |
| Macro/cross-asset | `equity.macro_series`, `equity.macro_vintage`, `equity.rate_curve`, `equity.FX_pair`, `equity.commodity`, `equity.credit_spread`, `equity.volatility_index` |
| Relationship | `equity.supplier_relationship`, `equity.customer_relationship`, `equity.competitor_relationship`, `equity.ownership_relationship`, `equity.factor_exposure_relationship` |

Identifier methodology:

- Company: CIK where US issuer, LEI where available, internal VIZA entity ID, ticker history relationship.
- Security/listing: ticker plus exchange MIC plus effective date range, ISIN/CUSIP when available and rights allow.
- Filing/document: accession number, filed_at, accepted_at, source URL.
- Portfolio/position: user/project scoped IDs with privacy policy.

Validation:

- Entity IDs must be stable across ticker/name changes.
- Security/listing lifecycle must track effective date ranges.
- Document entities require source and rights policy.
- User-private entities require export controls.

Progress recorded: Status 6, registry-ready entity type seeds.

## Section 21 - VIZA Node Palette

Objective: define the equity module node palette for methodology canvas use.

Source basis: all prior sections.

Node schema:

```json
{
  "node_type_id": "equity.valuation.dcf_model",
  "label": "DCF Model",
  "family": "valuation",
  "inputs": [],
  "outputs": [],
  "required_evidence": [],
  "PIT_required": true,
  "rights_sensitive": true,
  "validation_rules": [],
  "confidence_label": "common_practice"
}
```

Palette groups and seed nodes:

| Group | Node seeds |
|---|---|
| Decision grammar | `equity_decision`, `equity_thesis`, `evidence_bundle`, `signal_transform`, `catalyst_map`, `confirmation_tracker`, `invalidation_gate`, `strategy_profile_adapter` |
| Analyst workflow | `research_intake`, `company_snapshot`, `business_model_map`, `industry_context`, `recommendation_bridge`, `analyst_memo_builder`, `analyst_scorecard`, `thesis_tracker` |
| Fundamentals | `financial_statement_loader`, `revenue_bridge`, `margin_bridge`, `ROIC_calculator`, `FCF_conversion`, `balance_sheet_strength`, `accrual_quality`, `Piotroski_F_score`, `distress_risk` |
| Valuation | `dcf_model`, `relative_valuation`, `residual_income_model`, `dividend_discount_model`, `SOTP_model`, `NAV_model`, `precedent_transaction_model`, `scenario_valuation`, `reverse_dcf`, `margin_of_safety_gate` |
| Industry/governance | `peer_group_builder`, `moat_assessment`, `value_chain_map`, `industry_regime`, `governance_scorecard`, `capital_allocation_history`, `insider_activity_monitor`, `activist_vulnerability` |
| Factors/quant | `factor_model`, `factor_exposure`, `factor_ranker`, `momentum_signal`, `quality_signal`, `value_signal`, `low_beta_signal`, `multiple_testing_gate`, `factor_decay_monitor` |
| Portfolio/risk | `mandate_context`, `position_sizing`, `risk_decomposition`, `correlation_map`, `liquidity_capacity_gate`, `rebalance_planner`, `hedge_planner`, `portfolio_impact` |
| Technical/execution | `trend_state`, `volatility_regime`, `technical_signal`, `liquidity_gate`, `execution_plan`, `market_impact_estimator`, `slippage_review`, `venue_constraint_check` |
| Events | `event_detector`, `event_materiality`, `earnings_event`, `guidance_event`, `MA_deal_monitor`, `spin_restructuring`, `activism_event`, `regulatory_litigation_event`, `event_study_validator` |
| Ownership/flows | `13F_monitor`, `13D_13G_monitor`, `short_interest_monitor`, `borrow_squeeze_gate`, `options_positioning`, `index_ETF_flow`, `crowding_monitor` |
| Sentiment/macro/short | `sentiment_signal`, `narrative_map`, `rumor_quarantine`, `macro_regime_classifier`, `rate_sensitivity`, `inflation_exposure`, `negative_thesis`, `accounting_red_flag`, `short_invalidation_gate` |
| Trust/package | `PIT_audit`, `rights_audit`, `validation_gate`, `source_rights_report`, `package_visibility_gate` |

Connection methodology:

- Evidence/document nodes feed transforms, gates, and insights.
- Strategy profiles consume insights and output decisions.
- Validation and rights nodes can block outputs or package sections.
- Portfolio nodes must receive mandate context before sizing decisions.

Progress recorded: Status 6, registry-ready node palette.

## Section 22 - Attribute Registry Expansion

Objective: seed the equity attribute registry with typed raw, normalized, derived, and interpreted attributes.

Source basis: all prior sections, especially S001-S009, S014, S018-S029, S047.

Attribute schema:

```json
{
  "attribute_key": "fundamental.revenue_growth_yoy",
  "entity_types": ["equity.company"],
  "value_type": "number",
  "unit": "percent",
  "tier": "derived",
  "PIT_required": true,
  "rights_policy": "inherits_from_inputs",
  "validation_rules": ["EQ-VAL-001", "EQ-VAL-002"],
  "confidence_label": "high_confidence_core"
}
```

Seed attribute families:

| Family | Attribute seeds |
|---|---|
| Identity/security | `security.ticker`, `security.exchange`, `security.currency`, `security.primary_listing`, `security.free_float`, `security.market_cap`, `security.ADV`, `security.spread` |
| Fundamentals | `fundamental.revenue`, `fundamental.revenue_growth_yoy`, `fundamental.gross_margin`, `fundamental.operating_margin`, `fundamental.EBITDA_margin`, `fundamental.net_margin`, `fundamental.EPS`, `fundamental.CFO`, `fundamental.capex`, `fundamental.FCF`, `fundamental.ROIC`, `fundamental.ROE`, `fundamental.invested_capital`, `fundamental.working_capital` |
| Quality/accounting | `quality.accrual_ratio`, `quality.cash_conversion`, `quality.gross_profitability`, `quality.Piotroski_F`, `quality.Beneish_M`, `quality.Altman_Z`, `quality.restatement_flag`, `quality.SBC_percent_revenue` |
| Balance sheet | `balance.net_debt`, `balance.debt_to_EBITDA`, `balance.interest_coverage`, `balance.current_ratio`, `balance.quick_ratio`, `balance.maturity_wall`, `balance.covenant_flag` |
| Valuation | `valuation.EV_sales`, `valuation.EV_EBITDA`, `valuation.PE`, `valuation.PB`, `valuation.FCF_yield`, `valuation.DCF_value`, `valuation.SOTP_value`, `valuation.margin_of_safety`, `valuation.implied_growth`, `valuation.terminal_value_share` |
| Industry/competitive | `industry.GICS_sector`, `industry.GICS_industry`, `peer.similarity_score`, `moat.source`, `moat.score`, `cyclicality.score`, `regulatory_intensity`, `value_chain_dependency` |
| Governance/capital allocation | `governance.board_independence`, `governance.dual_class_flag`, `governance.insider_ownership`, `capital.buyback_yield`, `capital.dividend_yield`, `capital.payout_ratio`, `capital.share_count_growth`, `capital.MA_spend` |
| Factors | `factor.market_beta`, `factor.size`, `factor.value`, `factor.momentum`, `factor.profitability`, `factor.investment`, `factor.low_beta`, `factor.liquidity`, `factor.rank`, `factor.crowding` |
| Portfolio | `portfolio.weight`, `portfolio.active_weight`, `portfolio.risk_contribution`, `portfolio.tracking_error_contribution`, `portfolio.liquidity_days`, `portfolio.tax_lot_age`, `portfolio.thesis_exposure` |
| Technical/execution | `technical.return_12_1`, `technical.moving_average_state`, `technical.realized_volatility`, `technical.volume_z`, `execution.estimated_slippage`, `execution.participation_rate`, `execution.arrival_price_slippage` |
| Events/ownership | `event.materiality_score`, `event.confidence`, `ownership.institutional_pct`, `ownership.13f_change`, `ownership.short_interest_pct_float`, `ownership.days_to_cover`, `ownership.borrow_rate`, `options.put_call_ratio` |
| Sentiment/macro/rights | `sentiment.score`, `sentiment.attention_z`, `narrative.topic`, `macro.rate_sensitivity`, `macro.inflation_exposure`, `macro.FX_exposure`, `rights.export_policy`, `PIT.lookahead_risk` |

Validation:

- Attributes inherit PIT and rights from source observations.
- Derived attributes require formula version.
- Interpreted attributes require evidence and confidence label.
- Sector-specific attributes must declare applicability.

Progress recorded: Status 6, registry-ready attribute seeds.

## Section 23 - Event Registry Expansion

Objective: define event types, runtime event object schema, lifecycle states, materiality, source credibility, PIT, rights, and validation rules.

Source basis: S001-S006, S023, S030-S031, S046-S048, section outputs.

Runtime event schema:

```json
{
  "event_id": "evt_eq_...",
  "event_type": "equity.earnings.reported",
  "entities": [],
  "event_state": "announced | filed | updated | occurred | completed | cancelled | stale",
  "occurred_at": null,
  "announced_at": null,
  "available_at": null,
  "source_refs": [],
  "materiality_score": null,
  "thesis_relevance": null,
  "rights_policy_id": "",
  "validation_status": ""
}
```

Event registry seeds:

| Family | Event types |
|---|---|
| Research lifecycle | `research_initiated`, `thesis_created`, `evidence_added`, `decision_changed`, `invalidation_triggered`, `memo_stale` |
| Filing/disclosure | `10K_filed`, `10Q_filed`, `8K_filed`, `proxy_filed`, `S1_filed`, `amended_filing_filed`, `restatement_filed` |
| Earnings/guidance | `earnings_reported`, `earnings_surprise_detected`, `guidance_issued`, `guidance_raised`, `guidance_lowered`, `guidance_withdrawn`, `earnings_call_available` |
| Analyst/estimates | `rating_changed`, `target_price_changed`, `estimate_revised`, `coverage_initiated`, `coverage_dropped` |
| Capital allocation | `buyback_authorized`, `buyback_executed`, `dividend_increased`, `dividend_cut`, `dividend_suspended`, `debt_issued`, `equity_issued`, `acquisition_announced` |
| M&A/special sits | `MA_announced`, `MA_terms_updated`, `MA_approval_received`, `MA_completed`, `MA_terminated`, `spin_announced`, `spin_completed`, `restructuring_announced` |
| Ownership/governance | `13F_filed`, `13D_filed`, `13G_filed`, `activist_letter_released`, `proxy_contest_started`, `insider_buy_filed`, `insider_sell_filed`, `executive_change`, `director_change` |
| Technical/execution | `price_breakout`, `volume_spike`, `volatility_spike`, `liquidity_deteriorated`, `trading_halt`, `short_sale_restriction`, `order_plan_created`, `slippage_review_completed` |
| Macro/regulatory | `rate_decision`, `inflation_release`, `credit_spread_shock`, `regulatory_action`, `litigation_filed`, `product_approval`, `product_recall`, `geopolitical_shock` |
| Validation/package | `validation_failed`, `rights_export_blocked`, `PIT_warning_created`, `package_redacted`, `package_published_for_review` |

Validation:

- Events require source_refs and available_at.
- Rumor/unconfirmed events require low confidence and quarantine.
- Materiality score must not imply causality without attribution evidence.
- Licensed event feeds cannot be exported raw unless rights permit.

Progress recorded: Status 6, registry-ready event registry expansion.

## Section 24 - Insight Registry Expansion

Objective: define insight types that translate evidence, methods, scores, and events into VIZA-readable meaning.

Source basis: all prior sections.

Runtime insight schema:

```json
{
  "insight_id": "ins_eq_...",
  "insight_type": "equity.valuation.undervalued",
  "target_entity_id": "",
  "direction": "positive | negative | mixed | neutral",
  "confidence_label": "",
  "horizon": "",
  "evidence_refs": [],
  "source_rights_policy": "",
  "PIT_status": "",
  "strategy_profile_compatibility": [],
  "recommended_actions": [],
  "validation_status": ""
}
```

Insight registry seeds:

| Family | Insight types |
|---|---|
| Decision state | `thesis_strengthened`, `thesis_weakened`, `evidence_gap`, `profile_conflict`, `confirmation_observed`, `invalidation_observed` |
| Fundamentals | `growth_accelerating`, `margin_expansion_confirmed`, `cash_conversion_weak`, `balance_sheet_risk_high`, `accounting_quality_low`, `distress_risk_high` |
| Valuation | `undervalued_by_base_case`, `overvalued_by_base_case`, `margin_of_safety_insufficient`, `reverse_dcf_expectations_high`, `valuation_sensitive_to_terminal_value`, `peer_multiple_outlier` |
| Industry/governance | `moat_supported`, `moat_eroding`, `industry_tailwind`, `industry_headwind`, `governance_entrenchment_risk`, `capital_allocation_accretive`, `dilution_risk_high` |
| Factors/technical | `factor_supports_thesis`, `factor_conflicts_with_thesis`, `momentum_positive`, `momentum_reversal_risk`, `factor_crowding_high`, `multiple_testing_warning` |
| Portfolio/execution | `portfolio_fit_positive`, `position_too_large`, `risk_budget_breached`, `liquidity_capacity_low`, `hedge_needed`, `rebalance_due`, `execution_cost_high` |
| Events/ownership | `catalyst_pending`, `event_material_positive`, `event_material_negative`, `short_interest_high`, `activist_pressure_rising`, `ownership_crowding_high`, `insider_signal_positive` |
| Sentiment/macro/short | `sentiment_extreme_positive`, `sentiment_extreme_negative`, `narrative_shift_detected`, `macro_regime_supportive`, `macro_regime_adverse`, `negative_thesis_supported`, `squeeze_risk_high` |
| Trust | `PIT_safe`, `lookahead_risk`, `rights_export_blocked`, `connector_missing`, `human_review_required`, `validation_failed` |

Insight-to-action methodology:

- Insights do not directly force trades.
- Strategy profiles translate insights into candidate actions after gates.
- Conflicting insights must be displayed as conflicts, not averaged away.
- Low-confidence or rights-restricted insights may appear in private analysis but should not be packaged publicly.

Progress recorded: Status 6, registry-ready insight registry expansion.

## Section 25 - Strategy Profile Templates

Objective: define executable VIZA lenses with thresholds, weights, gates, outputs, validation needs, and rights requirements.

Source basis: section outputs and corpus.

Profile schema seed:

```json
{
  "profile_id": "eq_profile_long_value_v0",
  "families": ["EQF-LONG-VALUE"],
  "horizon": "multi_year",
  "required_nodes": [],
  "required_gates": [],
  "score_weights": {},
  "action_thresholds": {},
  "output_views": [],
  "PIT_requirements": [],
  "rights_requirements": [],
  "validation_rules": []
}
```

Initial profile templates:

| Profile ID | Families | Primary outputs | Hard gates |
|---|---|---|---|
| `eq_profile_long_value_v0` | value, quality, catalyst | valuation memo, thesis tracker | PIT filings, valuation sensitivity, margin of safety |
| `eq_profile_quality_compounder_v0` | quality, moat, governance | quality scorecard | ROIC/FCF support, moat evidence, governance review |
| `eq_profile_growth_surprise_v0` | growth, event, sentiment | growth bridge, catalyst board | estimate/data rights, revenue driver evidence |
| `eq_profile_income_safety_v0` | income, fundamentals | income safety card | payout/FCF/leverage gate |
| `eq_profile_quant_factor_v0` | factor | factor dashboard | OOS/cost/liquidity/multiple-testing |
| `eq_profile_quantamental_v0` | factor plus analyst | blended radar | factor validation plus thesis evidence |
| `eq_profile_event_earnings_v0` | event earnings | earnings event board | event timestamps, estimate/news rights |
| `eq_profile_merger_arb_v0` | M&A event | deal spread memo | terms, approvals, timing, downside |
| `eq_profile_special_situations_v0` | spin/restructuring/activism | special-sit memo | filing evidence and event lifecycle |
| `eq_profile_technical_execution_v0` | technical/execution | trade plan | market data rights, slippage/liquidity |
| `eq_profile_macro_regime_v0` | macro regime | regime dashboard | vintage macro and exposure rationale |
| `eq_profile_short_fundamental_v0` | short/negative | short thesis memo | borrow/squeeze/legal/evidence gate |

Profile compatibility rules:

- Fundamental long profiles can consume valuation, quality, industry, governance, event, portfolio insights.
- Quant profiles can consume factor and risk insights but must show validation warnings.
- Event profiles prioritize event lifecycle state and materiality.
- Short profiles require extra implementation, legal, and squeeze warnings.

Progress recorded: Status 6, registry-ready strategy profile templates.

## Section 26 - Output Views

Objective: define user-facing output views that VIZA can generate without hiding evidence, rights, PIT, or validation state.

Source basis: section outputs and current VIZA substrate.

Universal output schema:

```json
{
  "output_view_id": "equity.investment_memo",
  "label": "Investment Memo",
  "compatible_profiles": [],
  "sections": [],
  "required_evidence": [],
  "redaction_policy": "",
  "PIT_status_display": true,
  "rights_status_display": true,
  "validation_status_display": true
}
```

Output view seeds:

| Output ID | Purpose | Compatible profiles |
|---|---|---|
| `equity.strategy_fit_radar` | compare security against profile weights/gates | all |
| `equity.insight_card` | compact evidence-backed insight | all |
| `equity.investment_memo` | full analyst memo | fundamental, quantamental, short |
| `equity.thesis_tracker` | monitor confirmations/invalidation | all thesis-driven |
| `equity.watchlist` | candidate queue and missing evidence | all |
| `equity.valuation_matrix` | DCF/multiples/scenarios/reverse DCF | valuation profiles |
| `equity.factor_dashboard` | factor ranks/exposures/validation | factor/quantamental |
| `equity.event_catalyst_board` | event lifecycle and materiality | event/special sits |
| `equity.risk_dashboard` | portfolio, factor, liquidity, concentration | portfolio/risk |
| `equity.trade_plan` | execution-aware implementation | technical/execution |
| `equity.portfolio_impact_report` | marginal risk/return and constraints | portfolio |
| `equity.source_rights_report` | rights and redaction state | all/package |
| `equity.validation_report` | method/object validation status | all/package |

Output validation:

- Every claim links to evidence or shows a missing-evidence warning.
- Restricted data is redacted or summarized according to rights policy.
- PIT and validation status are visible.
- Output-only packages include enough audit metadata to establish trust without exposing restricted internals.

Progress recorded: Status 6, registry-ready output views.

## Section 27 - Module Manifest Proposal

Objective: propose a manifest for `viza.finance.equity_investment` that declares dependencies, registries, connector roles, validation rules, output views, and package behavior.

Manifest seed:

```json
{
  "module_id": "viza.finance.equity_investment",
  "module_version": "0.1.0-research",
  "display_name": "VIZA Equity Investment",
  "description": "Equity decision grammar, strategy families, ontology registries, outputs, validation, and PIT/source-rights controls.",
  "depends_on": [
    "viza.core.strategy",
    "viza.finance.securities"
  ],
  "optional_modules": [
    "viza.aat.attribute_analysis"
  ],
  "registry_artifacts": {
    "entity_types": "equity_entity_types.json",
    "node_types": "equity_node_types.json",
    "edge_types": "equity_edge_types.json",
    "attributes": "equity_attribute_registry_seed.csv",
    "events": "equity_event_registry_seed.json",
    "insights": "equity_insight_registry_seed.json",
    "strategy_profiles": "equity_strategy_profiles.json",
    "output_views": "equity_output_views.json",
    "validation_rules": "equity_validation_rules.json"
  },
  "connector_roles": [
    "official_public_connector",
    "licensed_market_data_connector",
    "licensed_fundamentals_connector",
    "licensed_text_connector",
    "user_document_connector",
    "derived_calculation_engine"
  ],
  "package_visibility_modes": [
    "white_box",
    "gray_box",
    "black_box",
    "output_only",
    "preview"
  ],
  "rights_policy": {
    "default_raw_provider_export": "blocked",
    "default_public_official_export": "metadata_and_derived_allowed",
    "default_unknown_rights_export": "blocked"
  },
  "validation_policy": {
    "PIT_required_for_backtests": true,
    "rights_required_for_packages": true,
    "human_review_required_for_fraud_or_legal_claims": true
  }
}
```

Manifest validation rules:

- Module dependency IDs must resolve.
- Every registry reference must include artifact checksum in package.
- Output views must declare rights and PIT display policy.
- Connector roles must exist before nodes requiring them are runnable.
- Missing optional AAT should degrade gracefully.

Progress recorded: Status 6, registry-ready manifest proposal.

## Section 28 - Engineering Backlog

Objective: convert research outputs into prioritized implementation work.

Backlog item schema:

`item_id`, `title`, `priority`, `workstream`, `description`, `source_sections`, `acceptance_criteria`, `dependencies`, `risk`.

P0 backlog seeds:

| ID | Title | Workstream | Acceptance |
|---|---|---|---|
| EQ-P0-001 | Add equity module manifest loader fixture | registry/runtime | manifest loads with dependencies and optional AAT |
| EQ-P0-002 | Create entity/node/attribute/event/insight seed artifacts | registry | artifacts validate against shared metadata contract |
| EQ-P0-003 | Implement PIT/rights schema extensions for equity observations | data | available_at and rights_policy required |
| EQ-P0-004 | Add validation rules EQ-VAL-001 through EQ-VAL-012 | validation | rules produce warning/block states |
| EQ-P0-005 | Build source-rights report output view | output/package | restricted data redacts in package preview |
| EQ-P0-006 | Build thesis/evidence/invalidation fixture | fixtures | sample security produces thesis tracker |
| EQ-P0-007 | Add SEC public connector adapter fixture | connector | resolves sample filing metadata and company facts |
| EQ-P0-008 | Add strategy profile compatibility validator | profile | insights translate only after gates |

P1 backlog seeds:

| ID | Title | Workstream |
|---|---|---|
| EQ-P1-001 | Analyst memo builder output |
| EQ-P1-002 | Valuation matrix nodes and fixture |
| EQ-P1-003 | Fundamental attribute calculators |
| EQ-P1-004 | Factor signal registry and validation harness |
| EQ-P1-005 | Event/catalyst board |
| EQ-P1-006 | Portfolio impact report |
| EQ-P1-007 | Ownership and short interest monitors |
| EQ-P1-008 | Macro vintage selector using ALFRED-style vintages |
| EQ-P1-009 | Short thesis legal/human review gate |
| EQ-P1-010 | Package redaction preview tests |

P2/P3 backlog seeds:

`technical_signal_nodes`, `execution_slippage_report`, `sentiment_narrative_map`, `macro_regime_dashboard`, `activism_special_sit_memo`, `profile_template_UI`, `artifact_export_wizard`, `cross-domain_stress_fixture`, `research_corpus_manager`, `confidence_recalibration_tool`, `duplicate_registry_object_merger`, `deferred_item_dashboard`, `marketplace_draft_review_checklist`.

Definition of done:

- Registry artifact loads.
- Fixture exercises node/profile/output.
- PIT and rights warnings visible.
- Validation rules produce pass/warn/block.
- Package preview respects redaction.

Progress recorded: Status 6, registry-ready backlog.

## Section 29 - Final Synthesis

Objective: synthesize completed section research into a coherent corpus and ontology.

Synthesis workflow:

1. Inventory all section outputs.
2. Normalize IDs and naming.
3. Merge duplicate nodes, attributes, events, insights, and profiles.
4. Resolve conflicts by source quality, PIT feasibility, rights, and validation burden.
5. Recalibrate confidence labels.
6. Build dependency matrix.
7. Run strategy-family coverage test.
8. Run validation coverage test.
9. Run core/domain boundary stress test.
10. Prepare registry artifact handoff.

Traceability matrix columns:

`artifact_id`, `artifact_type`, `source_sections`, `supporting_sources`, `methods_supported`, `VIZA_primitives`, `PIT_policy`, `rights_policy`, `validation_rules`, `confidence_label`, `status`.

Gap register:

- Full source corpus should be expanded beyond this compact v0.1 seed.
- Vendor-specific rights require legal/product review before packaging raw provider data.
- Live implementation requires fixtures and runtime validation.
- Statistical factor signals require full backtesting before production scoring.

Progress recorded: Status 6, registry-ready synthesis methodology.

## Section 30 - Registry Artifact and Handoff Methodology

Objective: define final artifact inventory, schemas, generation order, QA checks, fixture package, versioning, and handoff.

Artifact inventory:

```text
equity_entity_types.json
equity_node_types.json
equity_edge_types.json
equity_attribute_registry_seed.csv
equity_event_registry_seed.json
equity_insight_registry_seed.json
equity_strategy_profiles.json
equity_output_views.json
equity_validation_rules.json
equity_connector_requirements.json
equity_source_rights_matrix.csv
equity_PIT_matrix.csv
equity_fixture_package/
```

Generation order:

1. Shared metadata contract.
2. Entity and edge types.
3. Attribute registry.
4. Event registry.
5. Insight registry.
6. Node palette.
7. Strategy profiles.
8. Output views.
9. Validation rules.
10. Connector requirements and rights/PIT matrices.
11. Fixture package.
12. Manifest checksums and changelog.

QA checks:

- All IDs unique.
- All referenced entities/nodes/attributes/events/insights exist.
- All data-dependent objects have PIT and rights policy.
- All output views have redaction policy.
- All profiles reference valid family IDs.
- All validation rules have severity and target.

Progress recorded: Status 6, registry handoff methodology complete.

## Section 31 - Full Corpus Targeting and Coverage Methodology

Objective: define how to expand this v0.1 corpus into a full high-confidence research corpus.

Coverage lattice:

`section -> strategy family -> source class -> method -> VIZA object -> PIT -> rights -> validation -> output`

Source-class targets for full corpus:

- Academic: 120+ papers across valuation, factors, event studies, portfolio construction, market microstructure, sentiment, accounting quality, short constraints, macro, and validation.
- Professional: 50+ methodology sources across CFA, valuation, risk models, industry frameworks, governance, and asset-manager research.
- Official/primary: SEC, FINRA, FRED/ALFRED, exchanges, filings, company disclosures, central banks, regulators.
- Practitioner: 40+ public memos/letters/presentations for language and workflow only.
- Vendor/methodology: 25+ docs for data availability, field definitions, and rights.

Saturation rule:

A domain reaches corpus saturation when new sources no longer add material method objects, registry objects, validation rules, failure modes, or rights/PIT constraints.

Undercoverage warnings:

- Sentiment/social data rights remain high risk.
- Options/borrow/ETF flow data likely requires paid connectors.
- International equity coverage needs country-specific filings and rights analysis.
- Sector-specific ontologies need specialist expansion for banks, insurers, REITs, energy, biotech, and semiconductors.

Progress recorded: Status 6, full-corpus targeting methodology complete.

## Section 32 - Minimum Academic Anchor Topic Methodology

Objective: define academic streams that anchor the equity module without promoting unvalidated academic anomalies into production signals.

Academic anchor inventory:

| Topic | Anchor sources | VIZA mapping |
|---|---|---|
| Portfolio theory | S021, S022 | portfolio risk, sizing, beta, benchmark |
| Factor models | S018, S019 | factor exposure and risk |
| Momentum | S020 | factor signal with costs |
| Value/profitability/investment | S018, S019, S026 | factor and fundamental attributes |
| Accrual/accounting quality | S025, S040, S041 | accounting-quality warnings |
| Financial strength/distress | S024, S042 | quality/distress scores |
| Event studies | S023, S030, S031 | event validation |
| Multiple testing/factor zoo | S028 | validation downgrade |
| Publication decay | S029 | factor decay warning |
| Technical analysis | S034, S035 | experimental technical nodes |
| Macro factors/regimes | S036, S037 | macro exposure/regime |
| Liquidity risk | S038 | liquidity factor and capacity |
| Sentiment | S032, S033 | sentiment/narrative nodes |
| Short constraints | S043 | short/squeeze risk |

Academic confidence rules:

- Academic support is necessary but not sufficient for production.
- Promote as risk descriptor faster than as alpha signal.
- Require implementability, PIT availability, costs, capacity, and source rights for production scoring.

Progress recorded: Status 6, academic anchor methodology complete.

## Section 33 - Minimum Professional and Practitioner Anchor Topic Methodology

Objective: define professional and practitioner source anchors for analyst workflow, valuation, governance, activism, short research, risk models, and real-world language.

Anchor matrix:

| Topic | Source IDs | VIZA outputs |
|---|---|---|
| Analyst workflow | S010, S012 | memo, scorecard, recommendation bridge |
| Valuation | S010, S014 | valuation matrix, sensitivity |
| Moat/competitive advantage | S012, S013 | moat assessment |
| Governance | S011, S047-S048 | governance scorecard |
| Capital allocation | S045 | capital allocation history |
| Activism | S005, S046 | activism board |
| Factor/risk models | S016, S017 | factor dashboard |
| Industry classification | S015 | sector/industry entities |
| Short/investigative language | practitioner sources plus academic red flags | short thesis memo with guardrails |

Practitioner confidence rules:

- Use practitioner materials for vocabulary, thesis patterns, and examples.
- Do not promote practitioner claims to core without academic/official/professional triangulation.
- Avoid raw reproduction; paraphrase and cite.

Progress recorded: Status 6, professional/practitioner anchor methodology complete.

## Section 34 - Rejection and Downgrade Criteria Methodology

Objective: define how VIZA rejects, downgrades, quarantines, or rescues methods and ontology entries.

Decision flow:

1. Can it be expressed in VIZA primitives?
2. Is there source support above discovery-only?
3. Is the required data observable and PIT-safe?
4. Are source rights compatible with the intended output/package?
5. Can it be validated?
6. Does it create product, legal, or advice risk?
7. If weak but useful, can it be downgraded to warning, research_deeper, or private-only?

Hard rejection criteria:

- Not expressible as VIZA primitive.
- No credible source or only rumor.
- Requires unavailable future or revised data.
- Requires restricted data for intended package.
- Cannot be validated and would drive action.
- Makes unsupported fraud/legal claims.
- Violates core/domain boundary by pushing equity concepts into VIZA core.

Downgrade criteria:

- PIT unknown -> experimental or warning.
- Rights unclear -> no export/package.
- Source weak -> practitioner_observed or speculative.
- High turnover/no costs -> research_supported_experimental.
- Sentiment/rumor -> quarantine until corroborated.

Rejection record schema:

`rejection_id`, `object_id`, `object_type`, `reason_category`, `source_refs`, `failed_gate`, `rescue_path`, `confidence_after_review`, `reviewer`, `reviewed_at`.

Progress recorded: Status 6, rejection/downgrade methodology complete.

## Section 35 - Section Report Template Methodology

Objective: standardize future section reports.

Required section report structure:

1. Section objective.
2. Scope.
3. Exclusions.
4. Source corpus.
5. Source scoring notes.
6. Key research findings.
7. Extracted methods.
8. VIZA primitive mapping.
9. Candidate entity/node/edge types.
10. Candidate attributes.
11. Candidate events.
12. Candidate insights.
13. Strategy profile implications.
14. Output view implications.
15. PIT requirements.
16. Source-rights requirements.
17. Validation rules.
18. Failure modes.
19. Confidence labels.
20. Implementation backlog items.
21. Rejected/deferred items.
22. Open questions.
23. Registry-ready artifact seeds.
24. Acceptance gate result.

Acceptance record template:

`section_id`, `status`, `sources_collected`, `methods_extracted`, `VIZA_mapping_complete`, `PIT_reviewed`, `rights_reviewed`, `confidence_labels_assigned`, `registry_ready`, `implementation_ready`, `notes`.

Progress recorded: Status 6, report template methodology complete.

## Section 36 - Final Consolidated Report Assembly Methodology

Objective: assemble section reports into the final corpus without losing traceability or weakening confidence labels.

Assembly stages:

1. Freeze section outputs.
2. Normalize IDs.
3. Merge duplicates.
4. Resolve conflicts.
5. Build final source corpus.
6. Build final method extraction table.
7. Build final primitive map.
8. Build artifact registries.
9. Run PIT/rights synthesis.
10. Run validation synthesis.
11. Produce appendices and handoff.

Duplicate merge rules:

- Prefer higher source quality.
- Prefer broader applicability only if validation and rights remain explicit.
- Preserve aliases.
- Never merge distinct concepts solely because labels are similar.

Conflict resolution:

- PIT conflict -> choose safer historical interpretation or block.
- Rights conflict -> restrictive policy wins.
- Confidence conflict -> lower confidence unless stronger source/validation justifies promotion.
- Strategy conflict -> show profile-specific interpretation.

Progress recorded: Status 6, consolidated assembly methodology complete.

## Section 37 - Recommended Execution Order and Dependency Methodology

Objective: define sequencing and dependencies for research and implementation.

Execution order:

1. Baseline and protocol.
2. Universal decision grammar.
3. Strategy-family taxonomy.
4. Professional analyst workflow.
5. Fundamental/valuation/industry/governance core.
6. Factor, portfolio, event, technical/execution, ownership, sentiment, macro, short ontologies.
7. Data architecture and validation.
8. Entity/node/attribute/event/insight/profile/output registries.
9. Manifest and backlog.
10. Synthesis, handoff, corpus expansion, acceptance gates.

Dependency graph:

- Sections 3 and 4 feed all later ontology.
- Sections 18 and 19 gate every implementation artifact.
- Sections 20-26 consume sections 3-19.
- Section 27 consumes 20-26.
- Section 28 consumes all implementation candidates.
- Sections 29-41 govern synthesis and operation.

Regression rule:

If a later section discovers PIT, rights, validation, or source-quality problems, earlier artifacts must be downgraded and the completion matrix updated.

Progress recorded: Status 6, dependency methodology complete.

## Section 38 - Research Effort Estimation and Resource Planning Methodology

Objective: estimate effort for moving from v0.1 registry-ready seed to full implementation-ready corpus.

Quality levels:

- L1 seed: registry-ready outline with credible sources and object seeds.
- L2 robust: expanded source corpus, extracted method tables, complete validation.
- L3 implementation-ready: runtime fixtures, artifact files, module load tests.
- L4 production-hardened: connectors, rights review, legal/product review, broad validation.

Effort classification:

| Workstream | Current level | Target next level | Effort |
|---|---|---|---|
| Decision grammar and taxonomy | L1 | L2/L3 | medium |
| Fundamental/valuation core | L1 | L3 | high |
| Factors and validation | L1 | L3/L4 | very high |
| Events/ownership/short | L1 | L3 | high |
| Sentiment/alternative data | L1 | L2 | high due to rights |
| Registry artifacts | L1 | L3 | medium |
| Runtime fixtures | L0/L1 | L3 | medium-high |
| Legal/source-rights review | L1 | L4 | high |

Completion metrics:

- Source coverage by section.
- Methods extracted.
- Objects mapped.
- Validation rules attached.
- PIT/right policies attached.
- Fixtures passing.
- Package redaction tests passing.

Progress recorded: Status 6, effort methodology complete.

## Section 39 - AI Agent Operating Protocol Methodology

Objective: define how future AI research agents should execute and log this research loop.

Startup checklist:

1. Read current VIZA baseline.
2. Read methodology through line 999.
3. Identify section objective, scope, exclusions.
4. Build source plan.
5. Collect and score sources.
6. Extract methods.
7. Map to VIZA primitives.
8. Review PIT and rights.
9. Design validation.
10. Record progress immediately after section completion.

Evidence-to-object protocol:

For every source-backed claim, ask:

- What method does this support?
- What VIZA primitive does it extend?
- What object or registry entry should be created?
- What data fields are required?
- Could VIZA know it at decision time?
- Can VIZA query/cache/display/export/package it?
- How should it be validated?
- What failure mode does it introduce?

Work-log schema:

`timestamp`, `section_id`, `action`, `source_ids`, `methods_added`, `objects_added`, `PIT_notes`, `rights_notes`, `validation_notes`, `status_before`, `status_after`.

Progress recorded: Status 6, AI operating protocol complete.

## Section 40 - Success Criteria and Final Acceptance Gate Methodology

Objective: define success criteria for architecture alignment, equity coverage, traceability, PIT/rights, validation, registry readiness, and implementation readiness.

Architecture success:

- VIZA core remains domain-neutral.
- Equity concepts live in `viza.finance.equity_investment`.
- AAT is optional submodule/capability, not the whole equity module.
- `.viza` packaging respects rights/redaction.

Equity coverage success:

- Major strategy families are represented.
- Professional workflow, fundamentals, valuation, industry, governance, factors, portfolio, events, technical/execution, ownership, sentiment, macro, and short research are covered.
- Each coverage area has entities, nodes, attributes, events, insights, profiles, outputs, validations, and failure modes.

Traceability success:

- Every registry seed links to source sections and source IDs.
- Every data-dependent object has PIT and rights policy.
- Every actionable insight has validation and strategy-profile compatibility.

Final acceptance checklist:

- Status 6 for Sections 1-41.
- Source corpus present.
- Method and mapping summaries present.
- PIT and rights matrices present.
- Validation rules present.
- Registry artifact inventory present.
- Backlog present.
- Gaps and deferred items identified.

Progress recorded: Status 6, final acceptance methodology complete.

## Section 41 - Immediate Next Step and Launch Sequence Methodology

Objective: define the immediate launch sequence after this research pass.

Updated interpretation:

This document is the registry-ready research seed. The next launch step is not more generic brainstorming; it is artifact generation and fixture implementation.

Launch sequence:

1. Create artifact directory, e.g. `docs/equity_module_artifacts/` or runtime registry fixture path.
2. Convert Section 20 into `equity_entity_types.json`.
3. Convert Section 21 into `equity_node_types.json`.
4. Convert Section 22 into `equity_attribute_registry_seed.csv`.
5. Convert Section 23 into `equity_event_registry_seed.json`.
6. Convert Section 24 into `equity_insight_registry_seed.json`.
7. Convert Section 25 into `equity_strategy_profiles.json`.
8. Convert Section 26 into `equity_output_views.json`.
9. Convert Section 19 into `equity_validation_rules.json`.
10. Convert Section 27 into module manifest fixture.
11. Build a first-wedge fixture: public SEC filing -> fundamental attributes -> valuation/thesis -> insight -> profile -> output -> validation -> package rights report.
12. Add tests that load the module and execute the fixture without lookahead or rights leakage.

First research session deliverables completed here:

- Current baseline captured.
- Methodology captured.
- Compact source map captured.
- Section 1-41 progress recorded.
- Registry-ready seeds captured.
- Backlog and launch sequence captured.

Immediate execution principle:

Move from markdown to artifact fixtures. The research loop has produced the map; the next work should make the map loadable.

Progress recorded: Status 6, launch sequence complete.

## Registry Artifact Seed Summary

The following registry artifacts can be generated directly from this document:

| Artifact | Source sections |
|---|---|
| `equity_entity_types.json` | Section 20 |
| `equity_node_types.json` | Section 21 |
| `equity_edge_types.json` | Sections 8, 14, 20 |
| `equity_attribute_registry_seed.csv` | Section 22 |
| `equity_event_registry_seed.json` | Section 23 |
| `equity_insight_registry_seed.json` | Section 24 |
| `equity_strategy_profiles.json` | Section 25 |
| `equity_output_views.json` | Section 26 |
| `equity_validation_rules.json` | Section 19 |
| `equity_connector_requirements.json` | Section 18 |
| `equity_source_rights_matrix.csv` | Section 18 |
| `equity_PIT_matrix.csv` | Section 18 |
| `viza.finance.equity_investment.manifest.json` | Section 27 |
| `equity_module_backlog.md` | Section 28 |

## Final Acceptance Result

All sections from the masterplan's post-line-999 section plan through Section 41 have been completed to Status 6, registry-ready research seed. The file now contains:

- the current VIZA baseline;
- the research methodology extracted through line 999;
- a source corpus with quality and rights/PIT notes;
- a completion matrix;
- section-by-section outputs for Sections 1-41;
- VIZA primitive mappings;
- candidate entities, nodes, attributes, events, insights, profiles, outputs, validations, manifest, backlog, handoff, and launch controls.

Remaining work for Status 7 implementation-ready:

- Generate concrete JSON/CSV artifacts from the seeds.
- Add module-registry fixtures.
- Add runtime validation tests.
- Add package/redaction tests.
- Expand source corpus to the full targets in Section 31.
- Perform legal/product review for source-rights policies before any marketplace-style package distribution.

## Status 6.5 High-Confidence Upgrade Package

Prepared on 2026-05-14, the Status 6.5 upgrade package is available at:

```text
docs/equity_high_confidence_upgrade/
```

The package treats this document as the Status 6 baseline and adds the structured evidence system required for high-confidence handoff:

- expanded source corpus;
- academic, professional, practitioner, official/filing, and vendor extraction records;
- source-to-method-to-object traceability;
- PIT, source-rights, and method-validation matrices;
- confidence recalibration and rejection/downgrade log;
- concrete registry JSON/CSV artifacts;
- five fixture specifications and static PIT/rights/redaction expected results;
- final acceptance rubric.

Result: Status 6.5, full high-confidence research corpus / implementation-handoff ready.

Not claimed: Status 7 implementation-ready or Status 8 production-grade. Runtime module loading, PIT/lookahead tests, package redaction tests, live connector entitlements, legal/product review, and robust statistical validations remain required.
