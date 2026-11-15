# Final Confidence Recalibration — `viza.finance.equity_investment` v0.1 corpus v0.2

**Pass ID:** `v0.2.0_corpus_upgrade_2026_05_14`
**Date:** 2026-05-14
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening
**Module:** `viza.finance.equity_investment@0.1.0`
**Scope:** upgrade from registry-seedable v0.1 to a fuller source-anchored corpus by adding source-to-object extraction depth, without rewriting prose.

## 1. Headline numbers

| Artefact | Rows |
|---|---:|
| `equity_source_corpus.csv` | 540 |
| `academic_paper_extractions.jsonl` | 26 |
| `professional_framework_extractions.jsonl` | 7 |
| `practitioner_method_extractions.jsonl` | 14 |
| `official_primary_source_map.csv` | 20 |
| `vendor_rights_source_map.csv` | 13 |
| `equity_method_extraction_table.csv` | 49 |
| `equity_viza_mapping_table.csv` | 1,035 |
| `equity_research_traceability_matrix.csv` | 1,035 |
| `equity_PIT_matrix.csv` | 29 (copied) |
| `equity_source_rights_matrix.csv` | 36 (copied) |
| `equity_method_validation_matrix.csv` | 49 |
| `equity_rejection_and_downgrade_log.csv` | 1,035 (copied from v0.1 recalibration) |

## 2. Source corpus structure

### 2.1 Section coverage (CLAUDE_EQUITY_MODULE.md §§1–18)

| Prefix | Section | Count | Mounted in v0.1 |
|---|---|---:|---:|
| `B` | 1 Baseline (in-repo) | 10 | 4 |
| `P` | 2 Protocol | 15 | 2 |
| `G` | 3 Grammar | 20 | 6 |
| `T` | 4 Taxonomy | 30 | 1 |
| `ANL` | 5 Analyst | 20 | 8 |
| `F` | 6 Fundamentals | 30 | 8 |
| `V` | 7 Valuation | 25 | 6 |
| `I` | 8 Industry | 25 | 10 |
| `GOV` | 9 Governance | 20 | 13 |
| `FA` | 10 Factors | 60 | 11 |
| `PC` | 11 Portfolio | 35 | 9 |
| `TE` | 12 Technical | 35 | 14 |
| `EV` | 13 Events | 50 | 28 |
| `OW` | 14 Ownership | 30 | 9 |
| `BE` | 15 Behavioral | 35 | 8 |
| `MA` | 16 Macro | 30 | 9 |
| `SH` | 17 Short | 30 | 6 |
| `DA` | 18 Data Architecture | 40 | 24 |
| **Total** | — | **540** | **176** |

364 sources sit in the corpus but are not yet mounted in registries — they form the expansion reserve. Every one carries source_quality_score, source_quality_label, evidence_use, license_status, and weak_domain_tags so future registry-seeding passes can reach for them without re-research.

### 2.2 Source class distribution

| Source class | Count | Notes |
|---|---:|---|
| academic_or_professional | 145 | Foundational evidence for factor / behavioural / portfolio methods |
| official_primary | 110 | SEC, FRED, FINRA, BLS, FDA, FERC primary releases |
| official_primary_or_event | 50 | Filing-coupled events (earnings, 8-K items, 13F windows) |
| vendor_or_official | 40 | Mixed: official + vendor-hosted distribution |
| practitioner_method | 35 | Buy-side textbooks, sell-side practitioner essays |
| official_primary_or_academic | 30 | Macro datasets with academic exposition |
| internal_taxonomy | 30 | T-* taxonomy anchors |
| industry_practitioner | 25 | I-* sector specialist practice |
| vendor_rights | 25 | V-*, DA-* commercial vendors with explicit license terms |
| vendor_or_professional | 20 | Mixed |
| regulator_or_governance | 20 | G-* governance / regulator |
| internal_baseline | 10 | B-* in-repo baseline docs |

### 2.3 License status distribution

| License status | Count |
|---|---:|
| `academic_public` | 282 |
| `public_official` | 78 |
| `licensed_provider_required` | 70 |
| `public_professional` | 63 |
| `academic_public_or_open_web` | 36 |
| `internal_only` | 11 |

282 of 540 sources are academic_public (the largest single class), which matches the v0.1 registry's heavy reliance on the Fama-French / Carhart / Asness / Pedersen factor canon.

## 3. Weak-domain coverage

The assignment listed five weak-domain priorities. Coverage in the v0.2 corpus:

| Weak domain | Sources tagged | Status |
|---|---:|---|
| `sentiment_social_news_rights` | 20 | tagged across V-*, DA-* (Bloomberg/Refinitiv/RavenPack/X/Reddit), captured in `vendor_rights_source_map.csv` |
| `options_borrow_etf_index_flows` | 35 | tagged across SH-* (FINRA), DA-* (OCC, exchange chains), FA-027/FA-028 (options-volume papers) |
| `alfred_macro_vintaged` | 4 | MA-002 + cross-references — fallback path documented in `official_primary_source_map.csv` |
| `licensed_data_connector_entitlement_reviews` | 33 | V-* + DA-* with explicit `default_query_policy=blocked_unless_entitlement_present` + documented fallback in `vendor_rights_source_map.csv` |
| sector ontologies | 19 | banks (1), insurers (1), REITs (2), energy (5), biotech (3), semis (1), SaaS (5), retail (auto-tagged via I-018), industrials, utilities — each with a dedicated practitioner extraction record under `practitioner_method_extractions.jsonl` (I-011..I-020) |

Per-sector ontologies are not yet mounted into the v0.1 registries — they are captured as practitioner_method_extractions ready for v0.2.x seeding (one strategy profile per sector or per sector-cluster).

## 4. Method extraction depth

49 methods extracted across academic, professional-framework, and practitioner-method records.

### 4.1 Method statistical classes

| Class | Methods | Notes |
|---|---:|---|
| `cross_sectional_sort` | 11 | Factor portfolios (size, value, momentum, quality, accruals) |
| `time_series_regression` | 2 | FF3, FF5 |
| `event_study` | 3 | PEAD, recommendation drift, insider |
| `cost_model_simulation` | 2 | Frazzini/Israel/Moskowitz (2018), Novy-Marx/Velikov (2016) |
| `statistical_significance_correction` | 4 | Harvey/Liu/Zhu, Bailey/López de Prado, deflated Sharpe, Bonferroni/FDR |
| `convex_optimization` | 1 | Markowitz |
| `behavioural_research_observation` | 2 | Prospect theory, overreaction — research_only |
| `qualitative_workflow_mapping` | 1 | Pedersen Efficiently Inefficient |
| `qualitative_structured_extraction` | 1 | Greenwald thesis template |
| `sector_specific_ontology` | 10 | All 10 sector ontologies |
| `implementation_sensitivity` | 1 | AQR / practitioner construction-choices |
| `meta_analysis` | 1 | Cochrane factor zoo |
| `event_calendar` | 1 | Clinical milestones (biotech) |
| `long_run_alpha_attribution` | 1 | Grinold-Kahn IR |
| Other | 9 | composite_scoring, longitudinal_anomaly_replication, regime_classification, etc. |

### 4.2 Method -> validation rule mapping

`equity_method_validation_matrix.csv` resolves each method's required controls to the v0.1 validation rule IDs:

| Match quality | Count |
|---|---:|
| matched | 47 |
| no_controls_required (research_only) | 2 |
| no_matching_rule | 0 |

All 47 matched methods now route to one or more of the 43 v0.1 validation rules. The 2 research-only methods (BE-001 Prospect Theory, BE-014 DHS overreaction) are intentionally research_only — they support framing, not direct signals.

## 5. Traceability matrix

`equity_research_traceability_matrix.csv` provides one row per registry record (1,035 rows) with the following columns:

- `object_id`, `object_family`, `registry`
- `source_ids` (pipe-delimited)
- `source_sections` (e.g. `§19.3|§29.1`)
- `validation_rule_ids` (pipe-delimited)
- `current_confidence_label` and `pre_recalibration_label` (from v0.1 recalibration)
- `license_policy`, `pit_safe_label`, `status`

This is the single source of truth for "which CLAUDE log section produced object X with which sources and which validation rules". It's the answer to questions 1, 2, 3, 4, 5, 6, 7 of the per-record audit assignment in a single CSV.

## 6. VIZA mapping table

`equity_viza_mapping_table.csv` maps every registry record (1,035 rows) to the canonical `viza.core.strategy` primitive it extends, plus the `viza.finance.equity_investment` module-specific subprimitive notes. Every record carries `core_primitive` (the universal primitive) + `extends_core_primitive` (the legal extension axis declared by `viza.core.strategy`) + `viza_module_path` (the importable module path the runtime resolves at load time).

## 7. PIT + rights + rejection log

| File | Purpose | Source |
|---|---|---|
| `equity_PIT_matrix.csv` | 29 data-type rows: observed_at_policy, available_at_policy, retrieved_at_policy, revision_risk, vintage_required, lookahead_risk, safe_for_backtest | copied from `registries/equity_PIT_matrix.csv` |
| `equity_source_rights_matrix.csv` | 36 data-type rows: license_policy, query_policy, cache_policy, display_policy, export_policy, derived_value_policy, redistribution_policy | copied from `registries/equity_source_rights_matrix.csv` |
| `equity_rejection_and_downgrade_log.csv` | 1,035-row v0.1 recalibration audit log (158 downgrades, 0 rejections) | copied from `fixtures/confidence_recalibration/equity_rejection_and_downgrade_log.csv` |

The v0.1 → v0.2 corpus expansion did not introduce new rejections; the audit-driven downgrade log from the v0.1 recalibration pass is the authoritative record.

## 8. Confidence label state (after v0.1 recalibration; unchanged here)

| Label | Count | Share |
|---|---:|---:|
| `high_confidence_core` | 552 | 53.3% |
| `common_practice` | 426 | 41.2% |
| `research_supported_experimental` | 54 | 5.2% |
| `practitioner_observed` | 1 | 0.1% |
| `speculative_or_low_confidence` | 2 | 0.2% |
| `rejected_or_deferred` | 0 | 0.0% |

v0.2 corpus expansion does NOT relabel any record. The corpus extends the source base so future registry-seeding can promote records with new evidence (e.g. attaching a Path B public fallback to a licensed event upgrades it from `common_practice` to `high_confidence_core` after the next audit pass).

## 9. Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Every high-confidence object has traceability | **MET** | `equity_research_traceability_matrix.csv` lists source_ids + source_sections + validation_rule_ids for every record; 552 `high_confidence_core` records all carry non-empty source_ids and validation_rule_ids (verified by v0.1 recalibration audit) |
| Every data-dependent object has PIT and rights treatment | **MET** | `equity_PIT_matrix.csv` (29 data types) + `equity_source_rights_matrix.csv` (36 data types) cover every connector role referenced in v0.1; per-record `pit` and `rights` blocks are present on all 1,035 records (verified by v0.1 schema validation) |
| Every statistical method has validation and cost/liquidity/capacity controls | **MET** | `equity_method_validation_matrix.csv` matches 47/49 methods to validation rules; the 2 unmatched are research_only behavioural methods; `controls_required` on every statistical method includes cost / liquidity / multiple-testing / OOS controls |
| Every source class has source-quality scores | **MET** | `equity_source_corpus.csv` carries `source_quality_score` (1–5) and `source_quality_label` (score_1..score_5) on every one of 540 rows |
| Every low-confidence or restricted method is downgraded, quarantined, or rejected | **MET** | The v0.1 recalibration pass (see `equity_rejection_and_downgrade_log.csv`) downgraded 158 records; no record was rejected outright (every one remains audit-available) |
| Corpus can still generate the registry artifacts without redoing research | **MET** | `_extracted_corpus_raw.csv` + `equity_source_corpus.csv` allow re-running `fixtures/generate_*.py` against the existing CLAUDE log without re-research; `build_corpus_v0_2.py` regenerates every deliverable from the same inputs |

## 10. Weak-domain explicit gap log

The five weak domains have explicit documented status — not silently "missing".

### 10.1 sentiment_social_news_rights

- 20 sources tagged (V-002 Refinitiv, ANL-001 RavenPack, DA-018 X API, DA-019 StockTwits/Reddit, etc.).
- `vendor_rights_source_map.csv` records `default_marketplace_policy=blocked` and `fallback_options="no fallback; abstain from raw social text in v0.1"` for X/StockTwits/Reddit-derived feeds.
- `qualitative_sentiment_social_credibility_review` validation rule is mounted in v0.1.
- v0.1 module ships **without** a runtime social-text intake; this is intentional fail-closed posture given platform TOS uncertainty.

### 10.2 options_borrow_etf_index_flows

- 35 sources tagged (SH-* FINRA, DA-020 OCC summary, FA-027/FA-028 academic, exchange chains).
- OCC summary statistics are public; per-exchange raw chains require licensing.
- v0.1 registries seed `put_call_ratio_attribute` and `unusual_option_activity_event` as `common_practice` (taxonomy seeded; runtime blocked until license + connector lands).

### 10.3 alfred_macro_vintaged

- 4 sources tagged (MA-002 ALFRED, MA-001 FRED current, MA-003 BLS, others).
- v0.1 PIT matrix marks FRED current as `latest_only_until_alfred_pipeline`; ALFRED pipeline implementation deferred to v0.2.
- `pit_alfred_macro_required_for_backtest` validation rule already mounted in v0.1; warns when backtest uses non-ALFRED macro.

### 10.4 licensed_data_connector_entitlement_reviews

- 33 sources tagged (Bloomberg, Refinitiv, FactSet, I/B/E/S, Barra, Axioma, RavenPack, FMP, Polygon, etc.).
- `vendor_rights_source_map.csv` documents `default_query_policy=blocked_unless_entitlement_present` for each.
- `rights_production_connector_fail_closed` validation rule already mounted in v0.1; runtime blocks when license_status=missing.

### 10.5 Sector-specific ontologies

- 10 sector practitioner-method extractions seeded (banks, insurers, REITs, energy, biotech, semis, SaaS, retail, industrials, utilities).
- Each is documented in `practitioner_method_extractions.jsonl` with attribute set + statistical class + controls required.
- v0.1 registries currently mount sector-specific attributes only at the GICS-aggregate level; sector-specific strategy profiles are deferred to v0.2.x (one strategy profile per sector or sector-cluster).

## 11. Files (consolidated paths)

All deliverables under `docs/equity_module/v0.1/corpus_v0.2/`:

```
equity_source_corpus.csv                       540 rows  (master source list)
academic_paper_extractions.jsonl                26 rows  (FA-*, P-*, BE-* extractions)
professional_framework_extractions.jsonl         7 rows  (P-*, GOV-*, I-* frameworks)
practitioner_method_extractions.jsonl           14 rows  (PC-*, I-* practitioner)
official_primary_source_map.csv                 20 rows  (SEC EDGAR, FRED, FINRA, BLS, FDA, FERC)
vendor_rights_source_map.csv                    13 rows  (Bloomberg, Refinitiv, FactSet, I/B/E/S, etc.)
equity_method_extraction_table.csv              49 rows  (method_id, source_id, viza_primitive, controls)
equity_viza_mapping_table.csv                1,035 rows  (every registry record -> viza.core.strategy primitive)
equity_research_traceability_matrix.csv      1,035 rows  (source_ids + source_sections + validation_rule_ids per object)
equity_PIT_matrix.csv                           29 rows  (copy of v0.1 registries/equity_PIT_matrix.csv)
equity_source_rights_matrix.csv                 36 rows  (copy of v0.1 registries/equity_source_rights_matrix.csv)
equity_method_validation_matrix.csv             49 rows  (method -> validation rule mapping)
equity_rejection_and_downgrade_log.csv       1,035 rows  (copy of v0.1 recalibration audit log)
final_confidence_recalibration.md                       (this file)
```

Helper scripts under the same folder:

```
_extract_corpus.py                                       (parser: CLAUDE_EQUITY_MODULE.md -> _extracted_corpus_raw.csv)
build_corpus_v0_2.py                                     (master builder: emits all 13 CSV/JSONL deliverables)
_extracted_corpus_raw.csv                                (raw extraction; 540 rows)
_inventory.json                                          (which source_ids are mounted in v0.1)
verify_corpus_v0_2.py                                    (acceptance verifier)
```

## 12. Non-advice boundary

This corpus catalogs research evidence supporting the equity module's taxonomy. It does NOT constitute investment advice. All issuer / portfolio / user identities referenced via the pilot fixtures are fictional. Past performance does not predict future results.
