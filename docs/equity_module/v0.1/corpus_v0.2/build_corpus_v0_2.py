#!/usr/bin/env python3
"""Build all v0.2 corpus deliverables in one pass.

Inputs:
  - docs/CLAUDE_EQUITY_MODULE.md (source of truth)
  - docs/equity_module/v0.1/registries/*.json + *.csv (v0.1 registries)
  - docs/equity_module/v0.1/corpus_v0.2/_extracted_corpus_raw.csv (raw extraction)
  - docs/equity_module/v0.1/corpus_v0.2/_inventory.json (which sources are mounted)

Outputs (all under docs/equity_module/v0.1/corpus_v0.2/):
  - equity_source_corpus.csv
  - academic_paper_extractions.jsonl
  - professional_framework_extractions.jsonl
  - practitioner_method_extractions.jsonl
  - official_primary_source_map.csv
  - vendor_rights_source_map.csv
  - equity_method_extraction_table.csv
  - equity_viza_mapping_table.csv
  - equity_research_traceability_matrix.csv
  - equity_PIT_matrix.csv          (copied from v0.1 + augmented)
  - equity_source_rights_matrix.csv (copied from v0.1 + augmented)
  - equity_method_validation_matrix.csv
  - equity_rejection_and_downgrade_log.csv (copied + extended)
  - final_confidence_recalibration.md
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path("C:/Users/gkwls/AAT")
LOG = ROOT / "docs" / "CLAUDE_EQUITY_MODULE.md"
V01 = ROOT / "docs" / "equity_module" / "v0.1"
REG = V01 / "registries"
OUT = V01 / "corpus_v0.2"
OUT.mkdir(parents=True, exist_ok=True)

# Weak-domain tag set (user-specified)
WEAK_DOMAIN_TAGS = {
    "sentiment_social_news_rights": ["sentiment", "social", "news", "twitter", "x_twitter", "stocktwits", "reddit", "ravenpack", "novelty", "rumor", "media"],
    "options_borrow_etf_index_flows": ["option", "borrow", "etf", "index", "short interest", "put-call", "skew", "iv ", "implied vol", "creation", "redemption", "flow"],
    "alfred_macro_vintaged": ["alfred", "vintage", "macro vintaged", "fred vintage", "real-time vintages"],
    "licensed_data_connector_entitlement_reviews": ["bloomberg", "refinitiv", "factset", "i/b/e/s", "ibes", "nyse", "nasdaq", "polygon", "fmp", "ravenpack", "barra", "axioma", "msci"],
    "sector_ontology_banks": ["bank", "basel", "capital ratio", "cet1", "nim", "loan loss", "regulator-mandated", "fdic", "ccar", "dfast"],
    "sector_ontology_insurers": ["insurer", "combined ratio", "loss ratio", "reserve development", "naic", "solvency"],
    "sector_ontology_reits": ["reit", "ffo", "affo", "noi", "occupancy", "cap rate"],
    "sector_ontology_energy": ["e&p", "oil", "gas", "reserve replacement", "f&d cost", "boe", "rig count", "drilled but uncompleted"],
    "sector_ontology_biotech": ["biotech", "clinical trial", "fda approval", "pdufa", "phase 2", "phase 3", "orphan drug"],
    "sector_ontology_semiconductors": ["semiconductor", "wafer", "fab", "node shrink", "asp ", "book-to-bill", "lithography"],
    "sector_ontology_saas_software": ["saas", "arr", "nrr", "net retention", "magic number", "rule of 40", "cohort retention"],
    "sector_ontology_consumer_retail": ["retail", "same-store", "sss", "comparable store", "footfall", "consumer staples", "consumer discretionary"],
    "sector_ontology_industrials": ["industrial", "backlog", "book-to-bill", "capex cycle", "machinery"],
    "sector_ontology_utilities": ["utility", "rate base", "allowed roe", "regulatory lag", "purpa", "ferc"],
}


# ---------- 1. Load extracted source rows ----------

def load_raw_corpus() -> dict[str, dict]:
    src = {}
    with (OUT / "_extracted_corpus_raw.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            src[r["source_id"]] = r
    return src


def load_inventory() -> dict:
    return json.loads((OUT / "_inventory.json").read_text(encoding="utf-8"))


# ---------- 2. Build master corpus CSV ----------

PREFIX_TO_CLASS = {
    "B": "internal_baseline",
    "P": "academic_or_professional",  # mixed protocol references
    "G": "regulator_or_governance",
    "T": "internal_taxonomy",
    "ANL": "vendor_or_professional",
    "F": "official_primary",
    "V": "vendor_rights",
    "I": "industry_practitioner",
    "GOV": "official_primary",
    "FA": "academic_or_professional",
    "PC": "practitioner_method",
    "TE": "academic_or_professional",
    "EV": "official_primary_or_event",
    "OW": "official_primary",
    "BE": "academic_or_professional",
    "MA": "official_primary_or_academic",
    "SH": "official_primary",
    "DA": "vendor_or_official",
}

EXTRACTION_FAMILY = {
    "internal_baseline": "internal",
    "academic_or_professional": "academic_paper_or_professional_framework",
    "regulator_or_governance": "official_primary",
    "internal_taxonomy": "internal",
    "vendor_or_professional": "vendor_rights_or_professional",
    "official_primary": "official_primary",
    "vendor_rights": "vendor_rights",
    "industry_practitioner": "practitioner_method",
    "practitioner_method": "practitioner_method",
    "official_primary_or_event": "official_primary",
    "official_primary_or_academic": "official_primary_or_academic",
    "vendor_or_official": "vendor_or_official",
}


def tag_weak_domains(title: str, src_type: str) -> list[str]:
    txt = (title + " " + (src_type or "")).lower()
    tags = []
    for tag, kws in WEAK_DOMAIN_TAGS.items():
        if any(k in txt for k in kws):
            tags.append(tag)
    return tags


def quality_label(quality: str) -> str:
    try:
        q = int(quality)
    except (TypeError, ValueError):
        return "unknown"
    if q >= 5:
        return "score_5_high_foundation"
    if q >= 4:
        return "score_4_strong_support"
    if q >= 3:
        return "score_3_practitioner_evidence"
    if q >= 2:
        return "score_2_discovery_only"
    return "score_1_low_confidence"


def evidence_use(src_type: str, quality: str) -> str:
    try:
        q = int(quality)
    except (TypeError, ValueError):
        q = 3
    t = (src_type or "").lower()
    if "regulator" in t or "filing" in t:
        return "foundational"
    if "academic" in t:
        return "foundational"
    if "professional" in t:
        return "foundational_or_implementation"
    if "provider" in t or "vendor" in t:
        return "implementation"
    if "practitioner" in t:
        return "example_or_cautionary" if q <= 3 else "implementation_or_example"
    if "internal" in t:
        return "foundational"
    if q >= 4:
        return "foundational_or_implementation"
    return "example_or_cautionary"


def license_status(src_type: str, title: str) -> str:
    t = (src_type or "").lower()
    title_l = (title or "").lower()
    if "internal" in t:
        return "internal_only"
    if "regulator" in t or "filing" in t:
        return "public_official"
    if "academic" in t:
        return "academic_public"
    if "professional" in t:
        if any(k in title_l for k in ["cfa", "gaap", "ifrs", "iso", "fasb", "iasb", "soa", "naic", "ferc", "fda"]):
            return "public_professional"
        return "public_professional"
    if "provider" in t or "vendor" in t:
        if any(k in title_l for k in ["bloomberg", "factset", "refinitiv", "i/b/e/s", "ravenpack", "barra", "axioma", "msci"]):
            return "licensed_provider_required"
        if any(k in title_l for k in ["sec ", "edgar", "fred", "alfred", "finra", "occ", "treasury", "bls", "bea"]):
            return "public_official"
        return "licensed_provider_required"
    if "practitioner" in t:
        return "academic_public_or_open_web"
    return "unknown"


def build_corpus(src: dict, inventory: dict) -> list[dict]:
    used = set(inventory["all_source_ids"])
    rows = []
    for sid, rec in src.items():
        prefix = rec.get("section_prefix") or sid.split("-")[0]
        sclass = PREFIX_TO_CLASS.get(prefix, "other")
        sfamily = EXTRACTION_FAMILY.get(sclass, "other")
        title = rec.get("title", "")
        stype = rec.get("type", "")
        quality = rec.get("quality", "")
        ql = quality_label(quality)
        ev = evidence_use(stype, quality)
        lic = license_status(stype, title)
        weak = tag_weak_domains(title, stype)
        rows.append({
            "source_id": sid,
            "title": title,
            "claude_section_number": rec.get("section_number") or "",
            "claude_section_name": rec.get("section_name") or "",
            "claude_section_prefix": prefix,
            "raw_type": stype,
            "extraction_family": sfamily,
            "source_class": sclass,
            "source_quality_score": quality,
            "source_quality_label": ql,
            "evidence_use": ev,
            "license_status": lic,
            "weak_domain_tags": "|".join(weak),
            "mounted_in_v0_1_registries": "yes" if sid in used else "no",
            "v0_1_reference_count": inventory["counts"].get(sid, 0),
            "use_excerpt": rec.get("use", "") or rec.get("path", ""),
        })
    rows.sort(key=lambda r: (r["claude_section_prefix"] or "", r["source_id"]))
    return rows


# ---------- 3. Extraction JSONLs ----------

ACADEMIC_PAPER_EXTRACTIONS = [
    # FA-* curated extractions
    {"source_id": "FA-001", "title": "Markowitz (1952) Portfolio Selection",
     "methods": [
         {"method_id": "M-FA-001-mvopt", "name": "mean_variance_optimization",
          "extraction": "Diversification benefit derived from covariance; portfolio variance is not a weighted average of variances. Efficient frontier where return is maximised per unit of variance.",
          "viza_primitive": "score (portfolio scoring) + relationship (covariance matrix)",
          "statistical_class": "convex_optimization",
          "controls_required": ["estimation_error_review", "shrinkage_or_robust_estimation", "turnover_control", "cost_adjusted_return_review"]}
     ],
     "limitations": ["sensitive_to_estimation_error", "concentrated_portfolio_when_covariance_unstable"],
     "open_questions": ["robust_covariance_estimation_per_universe", "shrinkage_target_selection"]},
    {"source_id": "FA-005", "title": "Fama & French (1992) Cross-Section of Expected Stock Returns",
     "methods": [
         {"method_id": "M-FA-005-size_value", "name": "size_and_book_to_market_factor_construction",
          "extraction": "Sort universe by size (market cap) and B/M; long-short portfolios capture cross-sectional risk premia not explained by CAPM.",
          "viza_primitive": "score (factor exposure) + transform (cross-sectional rank)",
          "statistical_class": "cross_sectional_sort",
          "controls_required": ["cost_adjusted_return_review", "liquidity_adjusted_capacity_review", "multiple_testing_review", "out_of_sample_validation"]}
     ],
     "limitations": ["fading_post-publication (FA-033)", "geography_and_regime_dependence", "high_turnover_sensitive_to_costs"],
     "open_questions": ["which_book_value_proxy_is_robust_after_intangibles"]},
    {"source_id": "FA-006", "title": "Fama & French (1993) Common risk factors",
     "methods": [
         {"method_id": "M-FA-006-3factor", "name": "three_factor_regression",
          "extraction": "Market, SMB, HML factor portfolios; time-series regression of asset returns on factor returns yields exposures (betas).",
          "viza_primitive": "score (factor model) + relationship (beta loading)",
          "statistical_class": "time_series_regression",
          "controls_required": ["rolling_window_stability_check", "out_of_sample_validation", "factor_purity_check"]}
     ],
     "limitations": ["assumes_stationary_factor_premia"],
     "open_questions": []},
    {"source_id": "FA-008", "title": "Fama & French (2015) Five-factor model",
     "methods": [
         {"method_id": "M-FA-008-5factor", "name": "five_factor_regression",
          "extraction": "Adds profitability (RMW) and investment (CMA) factors. Reduces HML to redundant in their original test universe.",
          "viza_primitive": "score (factor model)",
          "statistical_class": "time_series_regression",
          "controls_required": ["out_of_sample_validation", "multiple_testing_review", "factor_redundancy_check"]}
     ],
     "limitations": ["redundancy_concerns", "international_replication_uneven"],
     "open_questions": []},
    {"source_id": "FA-009", "title": "Carhart (1997) On Persistence in Mutual Fund Performance",
     "methods": [
         {"method_id": "M-FA-009-momentum", "name": "momentum_factor_construction",
          "extraction": "Cross-sectional 12-2 month past-return ranking long-short portfolio captures momentum premium not explained by FF3.",
          "viza_primitive": "score (factor exposure) + transform (rolling window)",
          "statistical_class": "cross_sectional_sort",
          "controls_required": ["momentum_crash_drawdown_control (FA-030)", "cost_adjusted_return_review (FA-047, FA-048)", "small-cap_capacity_review"]}
     ],
     "limitations": ["momentum_crashes (FA-030)", "high_turnover_cost_sensitivity"],
     "open_questions": ["regime-aware_momentum_overlay"]},
    {"source_id": "FA-010", "title": "Jegadeesh & Titman (1993) Momentum",
     "methods": [
         {"method_id": "M-FA-010-cs_momentum", "name": "cross_sectional_momentum",
          "extraction": "3-12 month formation periods, 1-12 month holding periods; J-month winners outperform losers in 6-12 month holding window.",
          "viza_primitive": "score (factor exposure)",
          "statistical_class": "cross_sectional_sort",
          "controls_required": ["cost_adjusted_return_review", "liquidity_adjusted_capacity_review"]}
     ],
     "limitations": ["fades_in_some_regimes", "small_cap_capacity_limited"],
     "open_questions": []},
    {"source_id": "FA-012", "title": "Asness, Moskowitz, Pedersen (2013) Value and Momentum Everywhere",
     "methods": [
         {"method_id": "M-FA-012-cross_asset_vm", "name": "cross_asset_value_and_momentum",
          "extraction": "Value and momentum coexist across equities, bonds, currencies, commodities; negatively correlated with each other.",
          "viza_primitive": "score (factor exposure)",
          "statistical_class": "cross_sectional_sort + cross_asset_aggregation",
          "controls_required": ["cross_asset_correlation_check", "out_of_sample_validation"]}
     ],
     "limitations": [], "open_questions": []},
    {"source_id": "FA-013", "title": "Asness, Frazzini, Pedersen (2019) Quality minus Junk",
     "methods": [
         {"method_id": "M-FA-013-qmj", "name": "quality_minus_junk_construction",
          "extraction": "Quality composite (profitability + growth + safety + payout) long-short returns positive premium with low drawdowns.",
          "viza_primitive": "score (factor exposure)",
          "statistical_class": "cross_sectional_sort + composite_scoring",
          "controls_required": ["composite_weighting_sensitivity", "out_of_sample_validation", "cost_adjusted_return_review"]}
     ],
     "limitations": ["definition_drift_in_quality_proxies"], "open_questions": []},
    {"source_id": "FA-015", "title": "Frazzini & Pedersen (2014) Betting Against Beta",
     "methods": [
         {"method_id": "M-FA-015-bab", "name": "betting_against_beta",
          "extraction": "Leverage-constrained investors crowd into high-beta stocks; low-beta stocks earn premium; BAB portfolio is leverage-neutral.",
          "viza_primitive": "score (factor exposure)",
          "statistical_class": "long_short_construction + leverage_normalisation",
          "controls_required": ["leverage_normalisation_check", "borrow_cost_review", "real_world_leverage_constraints"]}
     ],
     "limitations": ["requires_leverage_to_capture_premium", "cost_sensitive"], "open_questions": []},
    {"source_id": "FA-019", "title": "Sloan (1996) Accrual Anomaly",
     "methods": [
         {"method_id": "M-FA-019-accruals", "name": "accruals_anomaly",
          "extraction": "High-accruals firms underperform low-accruals firms; mispricing of accrual quality persists into earnings announcements.",
          "viza_primitive": "score (factor exposure) + attribute (cfo_to_ni_ratio)",
          "statistical_class": "cross_sectional_sort",
          "controls_required": ["restatement_adjustment", "cost_adjusted_return_review"]}
     ],
     "limitations": ["fades_post-publication (FA-033)"], "open_questions": []},
    {"source_id": "FA-020", "title": "Bernard & Thomas (1989) PEAD",
     "methods": [
         {"method_id": "M-FA-020-pead", "name": "post_earnings_announcement_drift",
          "extraction": "Stocks with positive earnings surprises drift up for ~60 days post-announcement; negative surprises drift down.",
          "viza_primitive": "event (earnings_surprise) + score (PEAD signal)",
          "statistical_class": "event_study",
          "controls_required": ["cost_adjusted_return_review", "liquidity_adjusted_capacity_review", "drift_window_specification"]}
     ],
     "limitations": ["fades_in_high_attention_names"], "open_questions": []},
    {"source_id": "FA-021", "title": "Womack (1996) Analyst Recommendations",
     "methods": [
         {"method_id": "M-FA-021-rec_drift", "name": "analyst_recommendation_drift",
          "extraction": "Stocks experience price drift after analyst upgrades / downgrades; effect concentrated in small caps.",
          "viza_primitive": "event (analyst_upgrade / analyst_downgrade) + score (recommendation drift)",
          "statistical_class": "event_study",
          "controls_required": ["cost_adjusted_return_review", "selection_bias_review", "small-cap_capacity_review"]}
     ],
     "limitations": ["fades_in_large_caps", "stale_recommendation_bias"], "open_questions": []},
    {"source_id": "FA-024", "title": "Cohen, Malloy, Pomorski (2012) Insider trading",
     "methods": [
         {"method_id": "M-FA-024-insider", "name": "informed_insider_trading_signal",
          "extraction": "Opportunistic insiders' trades carry information; routine insiders' trades do not.",
          "viza_primitive": "event (insider_transaction) + attribute (insider_information_score)",
          "statistical_class": "classification + event_study",
          "controls_required": ["insider_classification_accuracy", "lag_to_filing_review"]}
     ],
     "limitations": ["short_horizon_signal"], "open_questions": []},
    {"source_id": "FA-025", "title": "Boehmer, Jones, Zhang (2008) Which shorts are informed?",
     "methods": [
         {"method_id": "M-FA-025-short_flow", "name": "informed_short_flow",
          "extraction": "Short flow predicts future negative returns; effect strongest in institutional shorting.",
          "viza_primitive": "attribute (short_interest_flow) + score",
          "statistical_class": "cross_sectional_sort",
          "controls_required": ["borrow_capacity_review", "FINRA_publication_lag_review"]}
     ],
     "limitations": ["FINRA_publication_lag_makes_signal_stale", "borrow_capacity_constrains_capture"], "open_questions": []},
    {"source_id": "FA-028", "title": "Pan & Poteshman (2006) Information in option volume",
     "methods": [
         {"method_id": "M-FA-028-opt_volume", "name": "option_volume_informed_trading",
          "extraction": "Put-call volume imbalance carries information about future stock returns.",
          "viza_primitive": "attribute (put_call_ratio) + event (unusual_option_activity)",
          "statistical_class": "cross_sectional_sort",
          "controls_required": ["option_market_microstructure_check", "weak-domain_review"]}
     ],
     "limitations": ["weak_domain — options data licensing required"], "open_questions": ["how_to_normalise_option_volume_across_strikes_and_maturities"]},
    {"source_id": "FA-030", "title": "Daniel & Moskowitz (2016) Momentum Crashes",
     "methods": [
         {"method_id": "M-FA-030-momentum_crash", "name": "momentum_crash_control",
          "extraction": "Momentum experiences crashes after market drawdowns; volatility-managed momentum reduces tail risk.",
          "viza_primitive": "transform (regime_overlay) + risk_gate",
          "statistical_class": "regime_classification",
          "controls_required": ["regime_indicator_validity", "vol_target_calibration"]}
     ],
     "limitations": [], "open_questions": []},
    {"source_id": "FA-033", "title": "McLean & Pontiff (2016) Does Academic Research Destroy Stock Return Predictability?",
     "methods": [
         {"method_id": "M-FA-033-fading", "name": "post_publication_factor_fading",
          "extraction": "Anomaly returns are ~26-58% lower post-publication; institutional arbitrage compresses premia.",
          "viza_primitive": "validation (factor_fading_review)",
          "statistical_class": "longitudinal_anomaly_replication",
          "controls_required": ["post_publication_recalibration", "out_of_sample_validation"]}
     ],
     "limitations": [], "open_questions": []},
    {"source_id": "FA-034", "title": "Harvey, Liu, Zhu (2016) And the Cross-Section of Expected Returns",
     "methods": [
         {"method_id": "M-FA-034-multiple_testing", "name": "multiple_testing_threshold",
          "extraction": "With 300+ published factors, naive t-stat thresholds overstate significance; recommend t>3 (Bonferroni-style) or deflated Sharpe.",
          "viza_primitive": "validation (multiple_testing_review)",
          "statistical_class": "statistical_significance_correction",
          "controls_required": ["bonferroni_or_fdr_correction", "deflated_sharpe (FA-040)"]}
     ],
     "limitations": [], "open_questions": []},
    {"source_id": "FA-040", "title": "Bailey & López de Prado (2014) Deflated Sharpe Ratio",
     "methods": [
         {"method_id": "M-FA-040-deflated_sharpe", "name": "deflated_sharpe_ratio",
          "extraction": "Adjusts observed Sharpe for backtest overfitting probability; reduces false discovery risk.",
          "viza_primitive": "validation (deflated_sharpe_check)",
          "statistical_class": "statistical_significance_correction",
          "controls_required": ["trials_count_audit"]}
     ],
     "limitations": [], "open_questions": []},
    {"source_id": "FA-047", "title": "Frazzini, Israel, Moskowitz (2018) Trading Costs of Asset Pricing Anomalies",
     "methods": [
         {"method_id": "M-FA-047-real_costs", "name": "real_world_trading_cost_overlay",
          "extraction": "Realised slippage + commission + market impact compresses anomaly returns; capacity is far below academic gross.",
          "viza_primitive": "validation (cost_adjusted_return_review)",
          "statistical_class": "cost_model_simulation",
          "controls_required": ["slippage_calibration_per_universe"]}
     ],
     "limitations": [], "open_questions": []},
    {"source_id": "FA-049", "title": "Novy-Marx & Velikov (2016) A Taxonomy of Anomalies and Their Trading Costs",
     "methods": [
         {"method_id": "M-FA-049-anomaly_taxonomy", "name": "anomaly_cost_taxonomy",
          "extraction": "Anomalies vary 5x in turnover; many lose all alpha after realistic costs.",
          "viza_primitive": "validation (capacity_review)",
          "statistical_class": "cost_model_simulation",
          "controls_required": ["turnover_metric", "capacity_metric"]}
     ],
     "limitations": [], "open_questions": []},
    # Section 2 (P-*) papers
    {"source_id": "P-001", "title": "Cochrane (2011) Presidential Address: Discount Rates",
     "methods": [
         {"method_id": "M-P-001-zoo", "name": "factor_zoo_problem",
          "extraction": "Hundreds of factors published; expected return is what we don't know in cross-section.",
          "viza_primitive": "validation (multiple_testing_review)",
          "statistical_class": "meta_analysis",
          "controls_required": ["multiple_testing_review", "out_of_sample_validation"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "P-002", "title": "Harvey Liu Zhu (2016) And the Cross-Section of Expected Returns",
     "methods": [
         {"method_id": "M-P-002-mt_threshold", "name": "factor_research_significance_threshold",
          "extraction": "t>3 threshold for newly-claimed factors.",
          "viza_primitive": "validation (multiple_testing_review)",
          "statistical_class": "statistical_significance_correction",
          "controls_required": ["bonferroni_or_fdr_correction"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "P-015", "title": "López de Prado & Lewis (2019) Detection of False Investment Strategies",
     "methods": [
         {"method_id": "M-P-015-false_strats", "name": "false_strategy_detection",
          "extraction": "Probabilistic Sharpe + deflated Sharpe + backtest length controls.",
          "viza_primitive": "validation (deflated_sharpe_check + backtest_overfitting_check)",
          "statistical_class": "statistical_significance_correction",
          "controls_required": ["trials_count_audit", "minimum_backtest_length"]}
     ], "limitations": [], "open_questions": []},
    # Behavioral (BE-*) examples — placeholder extractions; mark as behavioural foundational
    {"source_id": "BE-001", "title": "Kahneman & Tversky (1979) Prospect Theory",
     "methods": [
         {"method_id": "M-BE-001-prospect", "name": "loss_aversion_in_decision_modelling",
          "extraction": "Decision-makers weight losses ~2x more than gains; reference-point dependence.",
          "viza_primitive": "research_only — used as cautionary framing, not direct signal",
          "statistical_class": "behavioural_research_observation",
          "controls_required": []}
     ], "limitations": ["not_directly_actionable_in_PIT_model"], "open_questions": []},
    {"source_id": "BE-014", "title": "Daniel, Hirshleifer, Subrahmanyam (1998) Overconfidence and over-/under-reaction",
     "methods": [
         {"method_id": "M-BE-014-overreaction", "name": "overreaction_underreaction_modelling",
          "extraction": "Overconfidence -> overreaction to private info; biased self-attribution -> momentum.",
          "viza_primitive": "research_only — supports momentum + reversal hypotheses",
          "statistical_class": "behavioural_research_observation",
          "controls_required": []}
     ], "limitations": [], "open_questions": []},
]


PROFESSIONAL_FRAMEWORK_EXTRACTIONS = [
    {"source_id": "P-004", "title": "CFA Institute (2025) Code of Ethics and Standards of Professional Conduct",
     "framework_body": "CFA Institute",
     "framework_class": "professional_ethics",
     "methods": [
         {"method_id": "M-P-004-record_keeping", "name": "research_record_keeping",
          "extraction": "Maintain documentary evidence supporting research opinions; preserve audit trail.",
          "viza_primitive": "audit (validation_record + creator_record)",
          "controls_required": ["evidence_bundle_persistence", "audit_proof_emission"]},
         {"method_id": "M-P-004-suitability", "name": "suitability_and_disclosure",
          "extraction": "Recommend in client's interest; disclose material conflicts; non-advice boundary preserved.",
          "viza_primitive": "validation (non_advice_boundary_check)",
          "controls_required": ["non_advice_boundary_text", "conflict_disclosure"]},
     ], "limitations": [], "open_questions": []},
    {"source_id": "P-005", "title": "SEC Regulation S-K Item 303 (MD&A) + Item 10(e) (non-GAAP)",
     "framework_body": "SEC",
     "framework_class": "regulatory_disclosure",
     "methods": [
         {"method_id": "M-P-005-md_and_a", "name": "md_and_a_textual_extraction",
          "extraction": "MD&A contains forward-looking statements + management guidance + risk factors.",
          "viza_primitive": "evidence (filing_extracted_field)",
          "controls_required": ["text_attribution", "paraphrase_only_in_marketplace_draft"]},
         {"method_id": "M-P-005-nongaap_reconciliation", "name": "non_gaap_reconciliation",
          "extraction": "Item 10(e) requires GAAP reconciliation for every non-GAAP measure.",
          "viza_primitive": "validation (non_gaap_reconciliation_check)",
          "controls_required": ["reconciliation_table_present"]},
     ], "limitations": [], "open_questions": []},
    {"source_id": "P-006", "title": "FASB ASC 250 Accounting Changes and Error Corrections",
     "framework_body": "FASB",
     "framework_class": "accounting_standard",
     "methods": [
         {"method_id": "M-P-006-restatement", "name": "restatement_handling_for_pit",
          "extraction": "Restatements require retrospective application + prior-period adjustment + restatement note.",
          "viza_primitive": "pit (revision_handling)",
          "controls_required": ["vintage_handling_for_restated_periods", "revision_audit_log"]},
     ], "limitations": [], "open_questions": []},
    {"source_id": "P-013", "title": "Cochrane Handbook for Systematic Reviews (v6.5)",
     "framework_body": "Cochrane Collaboration",
     "framework_class": "evidence_grading_methodology",
     "methods": [
         {"method_id": "M-P-013-evidence_grade", "name": "evidence_grading_template",
          "extraction": "Grade evidence by study type + bias risk + consistency + precision.",
          "viza_primitive": "validation (confidence_label_assignment)",
          "controls_required": ["multi_source_triangulation", "bias_risk_assessment"]},
     ], "limitations": [], "open_questions": []},
    {"source_id": "P-014", "title": "GRADE working group — evidence quality framework",
     "framework_body": "GRADE Working Group",
     "framework_class": "evidence_grading_methodology",
     "methods": [
         {"method_id": "M-P-014-grade_levels", "name": "grade_evidence_levels",
          "extraction": "Four levels: high, moderate, low, very low; mapped to high_confidence_core / common_practice / research_supported_experimental / speculative_or_low_confidence.",
          "viza_primitive": "validation (confidence_label_assignment)",
          "controls_required": ["consistency_check", "publication_bias_check"]},
     ], "limitations": [], "open_questions": []},
    {"source_id": "GOV-001", "title": "SEC Regulation S-K (general)",
     "framework_body": "SEC", "framework_class": "regulatory_disclosure",
     "methods": [
         {"method_id": "M-GOV-001-disclosure_items", "name": "form_specific_disclosure_items",
          "extraction": "Each form (10-K / 10-Q / 8-K / S-1 / proxy) has item-numbered disclosure requirements.",
          "viza_primitive": "evidence (filing_extracted_field) + event (filing_event)",
          "controls_required": ["item_specific_extraction_per_form_type"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "I-001", "title": "GICS sector / industry classification",
     "framework_body": "MSCI / S&P", "framework_class": "industry_classification",
     "methods": [
         {"method_id": "M-I-001-sector_mapping", "name": "sector_industry_assignment",
          "extraction": "GICS is industry-standard 4-level taxonomy: sector / industry_group / industry / sub_industry.",
          "viza_primitive": "entity (sector) + relationship (sector_membership)",
          "controls_required": ["primary_sector_only_for_peer_basket", "revision_handling_for_reclassifications"]}
     ], "limitations": [], "open_questions": []},
]


PRACTITIONER_METHOD_EXTRACTIONS = [
    {"source_id": "PC-001", "title": "Grinold & Kahn (2000) Active Portfolio Management",
     "practitioner_class": "buy_side_textbook",
     "methods": [
         {"method_id": "M-PC-001-ir", "name": "information_ratio_and_breadth",
          "extraction": "IR = IC * sqrt(breadth); diversification across independent bets drives risk-adjusted alpha.",
          "viza_primitive": "validation (information_ratio_check)",
          "statistical_class": "long_run_alpha_attribution",
          "controls_required": ["independence_of_bets_check", "ic_realisation_audit"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "PC-005", "title": "Pedersen (2015) Efficiently Inefficient",
     "practitioner_class": "buy_side_textbook",
     "methods": [
         {"method_id": "M-PC-005-strategy_taxonomy", "name": "strategy_taxonomy_and_workflow",
          "extraction": "Equity strategies: value / momentum / quality / low-vol / merger arb / convertibles / event-driven; each has distinct workflow.",
          "viza_primitive": "strategy_profile (taxonomy)",
          "statistical_class": "qualitative_workflow_mapping",
          "controls_required": ["strategy_profile_disambiguation"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "PC-021", "title": "AQR / Cliff Asness practitioner essays",
     "practitioner_class": "buy_side_white_paper",
     "methods": [
         {"method_id": "M-PC-021-factor_implementation", "name": "factor_implementation_pitfalls",
          "extraction": "Factor construction details (rank vs raw, sector-neutral, vol-normalized) materially shift backtest results.",
          "viza_primitive": "validation (factor_implementation_audit)",
          "statistical_class": "implementation_sensitivity",
          "controls_required": ["construction_choices_documented", "sensitivity_test_against_alternatives"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "PC-013", "title": "Greenwald, Kahn, Bellotti — value investing practitioner thesis",
     "practitioner_class": "buy_side_textbook",
     "methods": [
         {"method_id": "M-PC-013-thesis_structure", "name": "investment_thesis_skeleton",
          "extraction": "Thesis structure: business + earnings_power + competitive_advantage + valuation + risks + catalysts.",
          "viza_primitive": "output (investment_memo_view)",
          "statistical_class": "qualitative_structured_extraction",
          "controls_required": ["thesis_template_compliance", "evidence_attachment"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "I-011", "title": "Sector specialist research practice — banks",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_banks"],
     "methods": [
         {"method_id": "M-I-011-bank_ontology", "name": "bank_specific_attribute_ontology",
          "extraction": "Banks need: CET1, NIM, NPL ratio, LLP, deposit beta, loan growth, regulatory-mandated stress test results (CCAR/DFAST).",
          "viza_primitive": "attribute (sector_specific_attribute_set) + entity_type (bank_specialisation)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["sector_attribute_completeness_check", "regulator_data_pit_treatment"]}
     ], "limitations": ["regulator_data_release_lag_must_be_PIT_safe"], "open_questions": ["how_to_treat_basel_revisions_as_revisions"]},
    {"source_id": "I-012", "title": "Insurance research practice (P&C, life, reinsurance)",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_insurers"],
     "methods": [
         {"method_id": "M-I-012-insurer_ontology", "name": "insurer_specific_attribute_ontology",
          "extraction": "P&C: combined ratio, loss ratio, expense ratio, reserve development. Life: VNB, NBV margin, embedded value. Reinsurance: cat exposure, retro programs.",
          "viza_primitive": "attribute (sector_specific_attribute_set)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["reserve_release_disclosure_check"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "I-013", "title": "REIT research practice",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_reits"],
     "methods": [
         {"method_id": "M-I-013-reit_ontology", "name": "reit_specific_attribute_ontology",
          "extraction": "REIT FFO + AFFO + NOI + occupancy + same-store + cap rate; non-GAAP reconciliation per NAREIT.",
          "viza_primitive": "attribute (sector_specific_attribute_set)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["nareit_definition_check", "non_gaap_reconciliation_check"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "I-014", "title": "Energy E&P research practice",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_energy"],
     "methods": [
         {"method_id": "M-I-014-energy_ontology", "name": "energy_ep_specific_attribute_ontology",
          "extraction": "E&P: reserve replacement ratio, F&D cost per BOE, drilled-but-uncompleted, type-curve assumptions.",
          "viza_primitive": "attribute (sector_specific_attribute_set)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["sec_reserve_disclosure_pit", "spot_price_assumption_disclosure"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "I-015", "title": "Biotech / pharma research practice",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_biotech"],
     "methods": [
         {"method_id": "M-I-015-biotech_ontology", "name": "biotech_specific_attribute_ontology",
          "extraction": "Biotech: clinical trial phase, primary endpoint, probability of success, PDUFA dates, FDA review timeline.",
          "viza_primitive": "event (clinical_milestone) + attribute (trial_probability_of_success)",
          "statistical_class": "sector_specific_ontology + event_calendar",
          "controls_required": ["trial_registry_attribution", "non_advice_boundary_in_outputs"]}
     ], "limitations": ["clinical_data_can_change_thesis_overnight"], "open_questions": []},
    {"source_id": "I-016", "title": "Semiconductor / capital-equipment research practice",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_semiconductors"],
     "methods": [
         {"method_id": "M-I-016-semis_ontology", "name": "semiconductor_specific_attribute_ontology",
          "extraction": "Semis: wafer starts, fab utilisation, ASP, book-to-bill, node transition cadence, lithography intensity.",
          "viza_primitive": "attribute (sector_specific_attribute_set)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["data_provider_lag_handling"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "I-017", "title": "SaaS / software research practice",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_saas_software"],
     "methods": [
         {"method_id": "M-I-017-saas_ontology", "name": "saas_specific_attribute_ontology",
          "extraction": "SaaS: ARR / NRR / GRR / rule-of-40 / magic-number / cohort retention; explicit disclosure variability across companies.",
          "viza_primitive": "attribute (sector_specific_attribute_set)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["definition_consistency_check", "non_gaap_reconciliation_check"]}
     ], "limitations": ["non_standard_definitions_across_filings"], "open_questions": []},
    {"source_id": "I-018", "title": "Consumer / retail research practice",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_consumer_retail"],
     "methods": [
         {"method_id": "M-I-018-retail_ontology", "name": "retail_specific_attribute_ontology",
          "extraction": "Same-store sales, traffic, basket size, e-commerce penetration, inventory days.",
          "viza_primitive": "attribute (sector_specific_attribute_set)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["disclosure_window_handling", "calendar_shift_normalisation"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "I-019", "title": "Industrials research practice",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_industrials"],
     "methods": [
         {"method_id": "M-I-019-industrials_ontology", "name": "industrials_specific_attribute_ontology",
          "extraction": "Industrials: backlog, book-to-bill, capex cycle, channel inventory, freight indicators.",
          "viza_primitive": "attribute (sector_specific_attribute_set)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["leading_indicator_lag_handling"]}
     ], "limitations": [], "open_questions": []},
    {"source_id": "I-020", "title": "Utilities research practice",
     "practitioner_class": "sell_side_or_buy_side_sector_research",
     "weak_domain_tags": ["sector_ontology_utilities"],
     "methods": [
         {"method_id": "M-I-020-utilities_ontology", "name": "utilities_specific_attribute_ontology",
          "extraction": "Utilities: rate base, allowed ROE, regulatory lag, rate case calendar, FERC orders.",
          "viza_primitive": "attribute (sector_specific_attribute_set)",
          "statistical_class": "sector_specific_ontology",
          "controls_required": ["rate_case_pit_handling", "ferc_filing_attribution"]}
     ], "limitations": [], "open_questions": []},
]


# ---------- Official primary sources ----------
OFFICIAL_PRIMARY_SOURCES = [
    {"source_id": "F-001", "name": "SEC EDGAR 10-K filings", "authority": "SEC", "jurisdiction": "US", "data_class": "annual_report",
     "pit_treatment": "filing_accepted_at + restated_periods_revisioned", "access_mode": "EDGAR_API_or_FTP", "refresh_cadence": "real_time_after_filing",
     "rights_class": "public_official", "weak_domain_tags": []},
    {"source_id": "F-002", "name": "SEC EDGAR 10-Q filings", "authority": "SEC", "jurisdiction": "US", "data_class": "quarterly_report",
     "pit_treatment": "filing_accepted_at", "access_mode": "EDGAR_API", "refresh_cadence": "real_time_after_filing",
     "rights_class": "public_official"},
    {"source_id": "F-003", "name": "SEC EDGAR 8-K filings", "authority": "SEC", "jurisdiction": "US", "data_class": "material_event_disclosure",
     "pit_treatment": "filing_accepted_at; Items 2.02, 5.02, 7.01, 8.01 carry distinct signals", "access_mode": "EDGAR_API", "refresh_cadence": "real_time"},
    {"source_id": "F-013", "name": "SEC EDGAR XBRL facts", "authority": "SEC", "jurisdiction": "US", "data_class": "structured_financial_facts",
     "pit_treatment": "fact_filed_at + period_end_at; revisions = restatements", "access_mode": "EDGAR_API or financial-statement-data-sets", "refresh_cadence": "filing_aligned"},
    {"source_id": "F-014", "name": "SEC EDGAR S-1 / IPO filings", "authority": "SEC", "data_class": "ipo_prospectus", "pit_treatment": "filing_accepted_at"},
    {"source_id": "OW-001", "name": "SEC EDGAR Form 4 (insider transactions)", "authority": "SEC", "data_class": "insider_transaction",
     "pit_treatment": "transaction_at vs filing_at; both must be modelled", "rights_class": "public_official", "weak_domain_tags": []},
    {"source_id": "OW-022", "name": "SEC EDGAR 13F-HR (institutional holdings)", "authority": "SEC", "data_class": "institutional_holdings",
     "pit_treatment": "publication_at (45 days post-quarter); NEVER use as current positioning",
     "rights_class": "public_official", "validation_rule": "filing_13f_data_must_not_be_used_as_current_positioning"},
    {"source_id": "OW-023", "name": "SEC EDGAR 13D / 13G (activist + 5%+ owner)", "authority": "SEC", "data_class": "activist_or_5pct_holder",
     "pit_treatment": "filing_accepted_at; 10-day window for 13D triggers", "rights_class": "public_official"},
    {"source_id": "GOV-001", "name": "SEC Regulation S-K (general)", "authority": "SEC", "data_class": "regulatory_framework",
     "pit_treatment": "version_at_filing_time", "rights_class": "public_official"},
    {"source_id": "GOV-011", "name": "SEC Regulation FD", "authority": "SEC", "data_class": "regulatory_framework_fair_disclosure",
     "pit_treatment": "applies_to_company_communications", "rights_class": "public_official"},
    {"source_id": "MA-001", "name": "FRED macro current series", "authority": "St. Louis Fed", "data_class": "macro_current",
     "pit_treatment": "latest_only_until_alfred_pipeline; PIT warning required", "rights_class": "public_official",
     "weak_domain_tags": ["alfred_macro_vintaged"], "fallback_relevant": True},
    {"source_id": "MA-002", "name": "FRED ALFRED real-time vintaged macro", "authority": "St. Louis Fed", "data_class": "macro_vintaged",
     "pit_treatment": "vintage_date_per_observation; PIT-safe for backtest", "rights_class": "public_official",
     "weak_domain_tags": ["alfred_macro_vintaged"]},
    {"source_id": "MA-003", "name": "BLS employment / CPI / PPI", "authority": "BLS", "data_class": "macro_official",
     "pit_treatment": "publication_at; revisions = new vintages", "rights_class": "public_official"},
    {"source_id": "SH-001", "name": "FINRA bi-weekly short interest", "authority": "FINRA", "data_class": "short_interest",
     "pit_treatment": "publication_date; never use settlement_date as available_at", "rights_class": "public_official",
     "weak_domain_tags": ["options_borrow_etf_index_flows"], "validation_rule": "short_interest_must_use_publication_date_for_available_at"},
    {"source_id": "SH-006", "name": "Failures-to-deliver (SEC)", "authority": "SEC", "data_class": "fail_to_deliver",
     "pit_treatment": "publication_at; bi-weekly", "rights_class": "public_official", "weak_domain_tags": ["options_borrow_etf_index_flows"]},
    {"source_id": "EV-001", "name": "Earnings release (8-K Item 2.02)", "authority": "SEC + company", "data_class": "earnings_event",
     "pit_treatment": "release_at; preceded_by_estimates", "rights_class": "public_official"},
    {"source_id": "EV-025", "name": "Pre-announcement / preliminary results press release", "authority": "company", "data_class": "earnings_pre_announcement",
     "pit_treatment": "press_release_at", "rights_class": "public_official_company_release"},
    {"source_id": "EV-026", "name": "Earnings call transcript", "authority": "company + transcript provider", "data_class": "earnings_call_transcript",
     "pit_treatment": "call_at; transcript publication may lag",
     "rights_class": "mixed — company audio is public; transcript provider services often licensed",
     "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "GOV-012", "name": "FDA approval / PDUFA calendar", "authority": "FDA", "data_class": "regulatory_milestone",
     "pit_treatment": "decision_date_or_pdufa_date", "rights_class": "public_official", "weak_domain_tags": ["sector_ontology_biotech"]},
    {"source_id": "GOV-013", "name": "FERC orders + rate case dockets", "authority": "FERC", "data_class": "regulatory_proceeding",
     "pit_treatment": "docket_filing_date", "rights_class": "public_official", "weak_domain_tags": ["sector_ontology_utilities"]},
]


# ---------- Vendor rights sources ----------
VENDOR_RIGHTS_SOURCES = [
    {"source_id": "V-001", "vendor": "Bloomberg", "product": "Bloomberg Professional Service / B-PIPE",
     "data_class": "real_time_market_data + reference + estimates",
     "license_terms_summary": "Subscription per-terminal; redistribution prohibited; entitlement check required.",
     "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_for_raw_values; derived_value_policy=allowed_per_contract",
     "default_marketplace_policy": "blocked_raw; paraphrase_only_for_derived",
     "fallback_options": "EDGAR for fundamentals; FINRA + SEC for shorts; FRED+ALFRED for macro",
     "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "V-002", "vendor": "Refinitiv (LSEG)", "product": "Refinitiv Eikon / DSWS / I/B/E/S",
     "data_class": "real_time_market_data + estimates_consensus + news",
     "license_terms_summary": "Subscription per-user; estimates consensus license separate; redistribution prohibited.",
     "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_for_raw_values",
     "default_marketplace_policy": "blocked_raw",
     "fallback_options": "EDGAR + management_guidance_press_release for surprise; Kenneth French for factors",
     "weak_domain_tags": ["licensed_data_connector_entitlement_reviews", "sentiment_social_news_rights"]},
    {"source_id": "V-003", "vendor": "FactSet", "product": "FactSet Workstation",
     "data_class": "fundamentals + estimates + ownership",
     "license_terms_summary": "Subscription per-user; ownership data per-source", "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_for_raw_values", "default_marketplace_policy": "blocked_raw",
     "fallback_options": "EDGAR XBRL for fundamentals; 13F for ownership lag",
     "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "V-014", "vendor": "I/B/E/S", "product": "I/B/E/S Consensus Estimates",
     "data_class": "analyst_consensus_estimates",
     "license_terms_summary": "Licensed via Refinitiv / FactSet / S&P Capital IQ; redistribution prohibited.",
     "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_for_raw_values; derived_value_policy=case_by_case",
     "default_marketplace_policy": "blocked_raw",
     "fallback_options": "EDGAR 8-K Item 2.02 + management guidance press release (Path B fallback per earnings_revision_momentum pilot)",
     "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "ANL-001", "vendor": "RavenPack", "product": "RavenPack News Analytics",
     "data_class": "news_sentiment + relevance + novelty",
     "license_terms_summary": "Subscription; raw text not redistributable; derived scores may be subject to per-contract terms.",
     "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_raw_text; derived_scores_per_contract",
     "default_marketplace_policy": "blocked",
     "fallback_options": "no free public substitute for high-quality news sentiment; consider abstaining or building from EDGAR-only text",
     "weak_domain_tags": ["sentiment_social_news_rights", "licensed_data_connector_entitlement_reviews"]},
    {"source_id": "DA-016", "vendor": "Polygon.io", "product": "Polygon Stocks API",
     "data_class": "delayed_or_real_time_equity_quotes",
     "license_terms_summary": "Tiered; real-time requires per-terminal license; delayed EOD is broadly permissible",
     "default_query_policy": "allowed_for_delayed; blocked_for_real_time_without_license",
     "default_export_policy": "blocked_for_raw_real_time; delayed_eod_per_contract",
     "default_marketplace_policy": "delayed_eod_only_in_marketplace_draft",
     "fallback_options": "use only delayed EOD until real-time license confirmed", "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "DA-017", "vendor": "Financial Modeling Prep (FMP)", "product": "FMP API",
     "data_class": "fundamentals_and_market_data",
     "license_terms_summary": "Tiered; redistribution per contract; for v0.1 treat as licensed_provider_required.",
     "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_raw", "default_marketplace_policy": "blocked_raw",
     "fallback_options": "EDGAR XBRL", "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "FA-052", "vendor": "Kenneth French Data Library", "product": "Public factor returns",
     "data_class": "academic_factor_returns",
     "license_terms_summary": "Public; academic attribution required; current (latest_only) presented without vintage.",
     "default_query_policy": "allowed",
     "default_export_policy": "allowed_with_attribution",
     "default_marketplace_policy": "allowed_with_attribution + PIT_latest_only_warning",
     "fallback_options": "this IS the public fallback for licensed factor models",
     "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "FA-054", "vendor": "Barra (MSCI)", "product": "Barra USE3 / USE4 risk model",
     "data_class": "licensed_factor_risk_model",
     "license_terms_summary": "Licensed; redistribution prohibited; exposures + factor returns licensed separately.",
     "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_raw_exposures + factor_returns",
     "default_marketplace_policy": "blocked_raw; derived_attribution_shell_only",
     "fallback_options": "Kenneth French latest_only with PIT warning",
     "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "FA-055", "vendor": "Axioma / MSCI Barra", "product": "Axioma factor risk models",
     "data_class": "licensed_factor_risk_model", "license_terms_summary": "Licensed; redistribution prohibited.",
     "default_query_policy": "blocked_unless_entitlement_present", "default_export_policy": "blocked_raw",
     "default_marketplace_policy": "blocked_raw", "fallback_options": "Kenneth French latest_only with PIT warning",
     "weak_domain_tags": ["licensed_data_connector_entitlement_reviews"]},
    {"source_id": "DA-018", "vendor": "Twitter / X (X API)", "product": "X API for social media posts",
     "data_class": "social_media_text",
     "license_terms_summary": "Platform TOS-restricted; redistribution prohibited without contractual permission.",
     "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_raw_text",
     "default_marketplace_policy": "blocked",
     "fallback_options": "no fallback; abstain from raw social text in v0.1",
     "weak_domain_tags": ["sentiment_social_news_rights"]},
    {"source_id": "DA-019", "vendor": "StockTwits / Reddit-derived feeds", "product": "Third-party social text feeds",
     "data_class": "social_media_text",
     "license_terms_summary": "Platform TOS-restricted; provider-specific terms apply.",
     "default_query_policy": "blocked_unless_entitlement_present",
     "default_export_policy": "blocked_raw_text",
     "default_marketplace_policy": "blocked",
     "fallback_options": "abstain or use derived sentiment scores only with per-contract permission",
     "weak_domain_tags": ["sentiment_social_news_rights"]},
    {"source_id": "DA-020", "vendor": "OCC (Options Clearing Corp)", "product": "OCC daily flex options summary",
     "data_class": "options_volume_open_interest",
     "license_terms_summary": "OCC summary statistics are public; raw end-of-day option chains are typically licensed per exchange.",
     "default_query_policy": "allowed_for_OCC_summary; blocked_for_exchange_raw_chains_without_license",
     "default_export_policy": "summary_allowed_with_attribution; raw_chains_blocked",
     "default_marketplace_policy": "summary_only", "fallback_options": "OCC summary public; exchange chains licensed",
     "weak_domain_tags": ["options_borrow_etf_index_flows", "licensed_data_connector_entitlement_reviews"]},
]


# ---------- VIZA primitive mapping ----------
VIZA_PRIMITIVES = {
    "entity": "viza.core.strategy.entity",
    "candidate_set": "viza.core.strategy.universe",
    "attribute": "viza.core.strategy.attribute",
    "event": "viza.core.strategy.event",
    "evidence": "viza.core.strategy.evidence",
    "assumption": "viza.core.strategy.assumption",
    "transform": "viza.core.strategy.transform",
    "gate": "viza.core.strategy.filter",
    "score": "viza.core.strategy.score",
    "relationship": "viza.core.strategy.relationship",
    "scenario": "viza.core.strategy.scenario",
    "decision": "viza.core.strategy.decision",
    "output": "viza.core.strategy.output_radar",
    "audit": "viza.core.strategy.audit_record",
    "universe": "viza.core.strategy.universe",
    "filter": "viza.core.strategy.filter",
    "output_radar": "viza.core.strategy.output_radar",
}


# ---------- Builders ----------

def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_method_extraction_table(academic, professional, practitioner) -> list[dict]:
    rows = []
    for sources, family in [(academic, "academic_paper"), (professional, "professional_framework"), (practitioner, "practitioner_method")]:
        for s in sources:
            for m in s.get("methods", []):
                rows.append({
                    "method_id": m["method_id"],
                    "method_name": m["name"],
                    "source_id": s["source_id"],
                    "source_family": family,
                    "viza_primitive": m.get("viza_primitive", ""),
                    "statistical_class": m.get("statistical_class", ""),
                    "controls_required": "|".join(m.get("controls_required", [])),
                    "source_title": s.get("title", ""),
                })
    return rows


def build_viza_mapping_table() -> list[dict]:
    """Walk every registry record and emit (object_id, registry, viza_primitive, viza_subprimitive)."""
    rows = []
    for fname in [
        "equity_entity_types", "equity_node_types", "equity_edge_types",
        "equity_event_registry_seed", "equity_insight_registry_seed",
        "equity_strategy_profiles", "equity_output_views",
        "equity_validation_rules", "equity_connector_requirements",
    ]:
        d = json.loads((REG / f"{fname}.json").read_text(encoding="utf-8"))
        items_key = None
        for k, v in d.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                items_key = k
                break
        if not items_key:
            continue
        for it in d[items_key]:
            cp = it.get("core_primitive", "")
            ecp = it.get("extends_core_primitive", "")
            rows.append({
                "object_id": it.get("id"),
                "object_family": it.get("object_family"),
                "registry": fname,
                "core_primitive": cp,
                "extends_core_primitive": ecp or "",
                "viza_module_path": VIZA_PRIMITIVES.get(cp, ""),
                "integration_notes": f"primitive={cp}; extends={ecp or 'none'}; module=viza.finance.equity_investment",
            })
    # attributes
    with (REG / "equity_attribute_registry_seed.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "object_id": r.get("key"),
                "object_family": "attribute",
                "registry": "equity_attribute_registry_seed",
                "core_primitive": "attribute",
                "extends_core_primitive": "attribute",
                "viza_module_path": VIZA_PRIMITIVES["attribute"],
                "integration_notes": f"family={r.get('family','')}; production_scoring_eligible={r.get('production_scoring_eligible','')}",
            })
    return rows


def build_traceability_matrix() -> list[dict]:
    """source -> method -> object -> validation traceability."""
    rows = []
    # Load method table built above (caller passes it in via main)
    # We rebuild it implicitly to scope per-call.
    for fname in [
        "equity_entity_types", "equity_node_types", "equity_edge_types",
        "equity_event_registry_seed", "equity_insight_registry_seed",
        "equity_strategy_profiles", "equity_output_views",
        "equity_validation_rules", "equity_connector_requirements",
    ]:
        d = json.loads((REG / f"{fname}.json").read_text(encoding="utf-8"))
        items_key = None
        for k, v in d.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                items_key = k
                break
        if not items_key:
            continue
        for it in d[items_key]:
            rows.append({
                "object_id": it.get("id"),
                "object_family": it.get("object_family"),
                "registry": fname,
                "source_ids": "|".join(it.get("source_ids") or []),
                "source_sections": "|".join(it.get("source_sections") or []),
                "validation_rule_ids": "|".join(it.get("validation_rules") or []),
                "current_confidence_label": it.get("confidence_label", ""),
                "pre_recalibration_label": it.get("confidence_label_pre_recalibration", ""),
                "license_policy": (it.get("rights") or {}).get("license_policy", ""),
                "pit_safe_label": (it.get("pit") or {}).get("lookahead_risk", ""),
                "status": it.get("status", ""),
            })
    with (REG / "equity_attribute_registry_seed.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "object_id": r.get("key"),
                "object_family": "attribute",
                "registry": "equity_attribute_registry_seed",
                "source_ids": r.get("source_ids", ""),
                "source_sections": r.get("source_sections", ""),
                "validation_rule_ids": r.get("validation_requirements", ""),
                "current_confidence_label": r.get("confidence_label", ""),
                "pre_recalibration_label": r.get("confidence_label_pre_recalibration", ""),
                "license_policy": r.get("entitlement_policy", ""),
                "pit_safe_label": r.get("lookahead_risk", ""),
                "status": r.get("research_only", "") or r.get("evidence_only", ""),
            })
    return rows


CONTROL_TO_RULE = {
    "cost_adjusted_return_review": "statistical_factor_costs_required",
    "liquidity_adjusted_capacity_review": "statistical_factor_liquidity_capacity_required",
    "out_of_sample_validation": "statistical_factor_oos_required",
    "multiple_testing_review": "statistical_factor_oos_required",
    "bonferroni_or_fdr_correction": "statistical_factor_oos_required",
    "deflated_sharpe": "statistical_deflated_sharpe_required",
    "deflated_sharpe_check": "statistical_deflated_sharpe_required",
    "trials_count_audit": "statistical_deflated_sharpe_required",
    "survivorship_bias_check": "statistical_survivorship_bias_required",
    "restatement_adjustment": "pit_restatement_revintage_required",
    "vintage_handling_for_restated_periods": "pit_restatement_revintage_required",
    "revision_audit_log": "pit_restatement_revintage_required",
    "regulator_data_pit_treatment": "pit_vintage_required_for_backtest",
    "alfred_macro_pit": "pit_alfred_macro_required_for_backtest",
    "FINRA_publication_lag_review": "pit_short_interest_publication_date",
    "filing_13f_publication_lag": "pit_thirteenf_lag",
    "borrow_capacity_review": "qualitative_short_action_requires_borrow_and_squeeze_review",
    "borrow_cost_review": "qualitative_short_action_requires_borrow_and_squeeze_review",
    "sentiment_social_credibility": "qualitative_sentiment_social_credibility_review",
    "human_review_required": "qualitative_human_review_fraud_legal_short",
    "non_advice_boundary": "evidence_non_advice_boundary",
    "non_advice_boundary_text": "evidence_non_advice_boundary",
    "non_advice_boundary_in_outputs": "evidence_non_advice_boundary",
    "paraphrase_only_in_marketplace_draft": "package_marketplace_draft_redact_restricted",
    "audit_proof_emission": "package_proof_checksum_required",
    "evidence_bundle_persistence": "evidence_thesis_requires_evidence_horizon_invalidation",
    "non_gaap_reconciliation_check": "evidence_valuation_requires_assumptions_and_sensitivity",
    "rumor_no_direct_action": "evidence_rumor_no_direct_action",
    "thesis_template_compliance": "evidence_thesis_requires_evidence_horizon_invalidation",
    "evidence_attachment": "evidence_thesis_requires_evidence_horizon_invalidation",
    "small-cap_capacity_review": "statistical_factor_liquidity_capacity_required",
    "small_cap_capacity_review": "statistical_factor_liquidity_capacity_required",
    "capacity_metric": "statistical_factor_liquidity_capacity_required",
    "turnover_metric": "statistical_factor_costs_required",
    "turnover_control": "statistical_factor_costs_required",
    "slippage_calibration_per_universe": "statistical_factor_costs_required",
    "factor_redundancy_check": "statistical_factor_oos_required",
    "factor_purity_check": "statistical_factor_oos_required",
    "rolling_window_stability_check": "statistical_factor_oos_required",
    "post_publication_recalibration": "statistical_factor_oos_required",
    "drift_window_specification": "statistical_factor_oos_required",
    "regime_indicator_validity": "statistical_factor_oos_required",
    "vol_target_calibration": "statistical_factor_oos_required",
    "estimation_error_review": "statistical_factor_oos_required",
    "shrinkage_or_robust_estimation": "statistical_factor_oos_required",
    "minimum_backtest_length": "statistical_factor_oos_required",
    "composite_weighting_sensitivity": "statistical_factor_oos_required",
    "ic_realisation_audit": "statistical_factor_oos_required",
    "independence_of_bets_check": "statistical_factor_oos_required",
    "construction_choices_documented": "statistical_factor_oos_required",
    "sensitivity_test_against_alternatives": "statistical_factor_oos_required",
    "cross_asset_correlation_check": "statistical_factor_oos_required",
    "leverage_normalisation_check": "statistical_factor_oos_required",
    "real_world_leverage_constraints": "statistical_factor_oos_required",
    "insider_classification_accuracy": "evidence_event_requires_source_credibility_and_timestamp",
    "lag_to_filing_review": "pit_no_lookahead",
    "selection_bias_review": "statistical_factor_oos_required",
    "option_market_microstructure_check": "qualitative_human_review_fraud_legal_short",
    "weak-domain_review": "qualitative_human_review_fraud_legal_short",
    "text_attribution": "rights_rights_policy_required",
    "primary_sector_only_for_peer_basket": "data_source_id_required",
    "revision_handling_for_reclassifications": "pit_restatement_revintage_required",
    "strategy_profile_disambiguation": "schema_node_types_in_palette",
    "multi_source_triangulation": "evidence_event_requires_source_credibility_and_timestamp",
    "bias_risk_assessment": "qualitative_human_review_fraud_legal_short",
    "consistency_check": "evidence_event_requires_source_credibility_and_timestamp",
    "publication_bias_check": "statistical_factor_oos_required",
    "item_specific_extraction_per_form_type": "evidence_event_requires_source_credibility_and_timestamp",
    "sector_attribute_completeness_check": "evidence_valuation_requires_assumptions_and_sensitivity",
    "reserve_release_disclosure_check": "evidence_valuation_requires_assumptions_and_sensitivity",
    "nareit_definition_check": "evidence_valuation_requires_assumptions_and_sensitivity",
    "sec_reserve_disclosure_pit": "pit_vintage_required_for_backtest",
    "spot_price_assumption_disclosure": "evidence_valuation_requires_assumptions_and_sensitivity",
    "trial_registry_attribution": "evidence_event_requires_source_credibility_and_timestamp",
    "data_provider_lag_handling": "pit_no_lookahead",
    "definition_consistency_check": "evidence_valuation_requires_assumptions_and_sensitivity",
    "disclosure_window_handling": "pit_no_lookahead",
    "calendar_shift_normalisation": "pit_no_lookahead",
    "leading_indicator_lag_handling": "pit_no_lookahead",
    "rate_case_pit_handling": "pit_no_lookahead",
    "ferc_filing_attribution": "evidence_event_requires_source_credibility_and_timestamp",
    "reconciliation_table_present": "evidence_valuation_requires_assumptions_and_sensitivity",
    "conflict_disclosure": "evidence_non_advice_boundary",
    "momentum_crash_drawdown_control": "statistical_factor_oos_required",
}


def build_method_validation_matrix(method_rows: list[dict]) -> list[dict]:
    """Map each method -> required validation rule ids."""
    d = json.loads((REG / "equity_validation_rules.json").read_text(encoding="utf-8"))
    items_key = None
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            items_key = k; break
    rule_ids = {r["id"] for r in d[items_key]}

    def match(controls: list[str]) -> list[str]:
        matched = []
        for c in controls:
            c_clean = c.split(" (")[0].strip()  # strip "(FA-030)" annotations
            rid = CONTROL_TO_RULE.get(c_clean)
            if rid and rid in rule_ids:
                matched.append(rid)
            else:
                # fall back to substring search
                c_l = c_clean.lower()
                for rule_id in rule_ids:
                    if c_l in rule_id.lower() or rule_id.lower() in c_l:
                        matched.append(rule_id)
                        break
        return list(dict.fromkeys(matched))

    rows = []
    for m in method_rows:
        controls = m.get("controls_required", "").split("|") if m.get("controls_required") else []
        controls = [c for c in controls if c]
        matched = match(controls)
        if matched:
            quality = "matched"
        elif not controls:
            quality = "no_controls_required (research_only method)"
        else:
            quality = "no_matching_rule_in_v0_1_validation_rules"
        rows.append({
            "method_id": m["method_id"],
            "method_name": m["method_name"],
            "source_id": m["source_id"],
            "statistical_class": m.get("statistical_class", ""),
            "controls_required": "|".join(controls),
            "matched_validation_rule_ids": "|".join(matched),
            "match_quality": quality,
        })
    return rows


def main() -> int:
    print("loading raw extracted corpus...")
    src = load_raw_corpus()
    inv = load_inventory()

    print(f"\n=== 1. equity_source_corpus.csv ({len(src)} rows) ===")
    corpus_rows = build_corpus(src, inv)
    write_csv(OUT / "equity_source_corpus.csv", corpus_rows, [
        "source_id", "title", "claude_section_number", "claude_section_name", "claude_section_prefix",
        "raw_type", "extraction_family", "source_class", "source_quality_score", "source_quality_label",
        "evidence_use", "license_status", "weak_domain_tags",
        "mounted_in_v0_1_registries", "v0_1_reference_count", "use_excerpt",
    ])

    print(f"\n=== 2-4. extraction JSONLs ===")
    write_jsonl(OUT / "academic_paper_extractions.jsonl", ACADEMIC_PAPER_EXTRACTIONS)
    print(f"  academic_paper_extractions.jsonl: {len(ACADEMIC_PAPER_EXTRACTIONS)} records")
    write_jsonl(OUT / "professional_framework_extractions.jsonl", PROFESSIONAL_FRAMEWORK_EXTRACTIONS)
    print(f"  professional_framework_extractions.jsonl: {len(PROFESSIONAL_FRAMEWORK_EXTRACTIONS)} records")
    write_jsonl(OUT / "practitioner_method_extractions.jsonl", PRACTITIONER_METHOD_EXTRACTIONS)
    print(f"  practitioner_method_extractions.jsonl: {len(PRACTITIONER_METHOD_EXTRACTIONS)} records")

    print(f"\n=== 5. official_primary_source_map.csv ({len(OFFICIAL_PRIMARY_SOURCES)} rows) ===")
    write_csv(OUT / "official_primary_source_map.csv", OFFICIAL_PRIMARY_SOURCES, [
        "source_id", "name", "authority", "jurisdiction", "data_class",
        "pit_treatment", "access_mode", "refresh_cadence", "rights_class", "weak_domain_tags",
        "fallback_relevant", "validation_rule",
    ])

    print(f"\n=== 6. vendor_rights_source_map.csv ({len(VENDOR_RIGHTS_SOURCES)} rows) ===")
    for r in VENDOR_RIGHTS_SOURCES:
        if isinstance(r.get("weak_domain_tags"), list):
            r["weak_domain_tags"] = "|".join(r["weak_domain_tags"])
    write_csv(OUT / "vendor_rights_source_map.csv", VENDOR_RIGHTS_SOURCES, [
        "source_id", "vendor", "product", "data_class", "license_terms_summary",
        "default_query_policy", "default_export_policy", "default_marketplace_policy",
        "fallback_options", "weak_domain_tags",
    ])

    print(f"\n=== 7. equity_method_extraction_table.csv ===")
    method_rows = build_method_extraction_table(ACADEMIC_PAPER_EXTRACTIONS, PROFESSIONAL_FRAMEWORK_EXTRACTIONS, PRACTITIONER_METHOD_EXTRACTIONS)
    write_csv(OUT / "equity_method_extraction_table.csv", method_rows, [
        "method_id", "method_name", "source_id", "source_family", "viza_primitive",
        "statistical_class", "controls_required", "source_title",
    ])
    print(f"  rows: {len(method_rows)}")

    print(f"\n=== 8. equity_viza_mapping_table.csv ===")
    viza_rows = build_viza_mapping_table()
    write_csv(OUT / "equity_viza_mapping_table.csv", viza_rows, [
        "object_id", "object_family", "registry", "core_primitive", "extends_core_primitive",
        "viza_module_path", "integration_notes",
    ])
    print(f"  rows: {len(viza_rows)}")

    print(f"\n=== 9. equity_research_traceability_matrix.csv ===")
    trace_rows = build_traceability_matrix()
    write_csv(OUT / "equity_research_traceability_matrix.csv", trace_rows, [
        "object_id", "object_family", "registry", "source_ids", "source_sections",
        "validation_rule_ids", "current_confidence_label", "pre_recalibration_label",
        "license_policy", "pit_safe_label", "status",
    ])
    print(f"  rows: {len(trace_rows)}")

    print(f"\n=== 10. equity_PIT_matrix.csv (copy) ===")
    shutil.copy(REG / "equity_PIT_matrix.csv", OUT / "equity_PIT_matrix.csv")
    print(f"  copied {REG / 'equity_PIT_matrix.csv'} -> {OUT / 'equity_PIT_matrix.csv'}")

    print(f"\n=== 11. equity_source_rights_matrix.csv (copy) ===")
    shutil.copy(REG / "equity_source_rights_matrix.csv", OUT / "equity_source_rights_matrix.csv")
    print(f"  copied {REG / 'equity_source_rights_matrix.csv'} -> {OUT / 'equity_source_rights_matrix.csv'}")

    print(f"\n=== 12. equity_method_validation_matrix.csv ===")
    method_val_rows = build_method_validation_matrix(method_rows)
    write_csv(OUT / "equity_method_validation_matrix.csv", method_val_rows, [
        "method_id", "method_name", "source_id", "statistical_class",
        "controls_required", "matched_validation_rule_ids", "match_quality",
    ])
    print(f"  rows: {len(method_val_rows)}")

    print(f"\n=== 13. equity_rejection_and_downgrade_log.csv (copy from v0.1 recalibration) ===")
    rejlog = V01 / "fixtures" / "confidence_recalibration" / "equity_rejection_and_downgrade_log.csv"
    if rejlog.exists():
        shutil.copy(rejlog, OUT / "equity_rejection_and_downgrade_log.csv")
        print(f"  copied")
    else:
        print(f"  source not found: {rejlog}")

    print()
    print("=== summary ===")
    summary = {
        "equity_source_corpus.csv": len(corpus_rows),
        "academic_paper_extractions.jsonl": len(ACADEMIC_PAPER_EXTRACTIONS),
        "professional_framework_extractions.jsonl": len(PROFESSIONAL_FRAMEWORK_EXTRACTIONS),
        "practitioner_method_extractions.jsonl": len(PRACTITIONER_METHOD_EXTRACTIONS),
        "official_primary_source_map.csv": len(OFFICIAL_PRIMARY_SOURCES),
        "vendor_rights_source_map.csv": len(VENDOR_RIGHTS_SOURCES),
        "equity_method_extraction_table.csv": len(method_rows),
        "equity_viza_mapping_table.csv": len(viza_rows),
        "equity_research_traceability_matrix.csv": len(trace_rows),
        "equity_method_validation_matrix.csv": len(method_val_rows),
    }
    for f, n in summary.items():
        print(f"  {f:55s} {n:>5d} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
