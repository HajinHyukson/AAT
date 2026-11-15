#!/usr/bin/env python3
"""
Generator for:
  - docs/equity_module/v0.1/registries/equity_event_registry_seed.json
  - docs/equity_module/v0.1/registries/equity_insight_registry_seed.json

Source of truth: docs/CLAUDE_EQUITY_MODULE.md.
Primary sections: §23 (event registry), §24 (insight registry), §13 (event-driven), §3 (decision grammar), §19 (validation framework).
Conformance: docs/equity_module/v0.1/equity_registry_shared_metadata.schema.json.

Restrictive defaults:
  - Rumor / unverified events: max action watch/alert_only, never auto-action.
  - Fraud/legal/short insights: human_review_required=true.
  - Sentiment/social: confidence_label=research_supported_experimental.
  - Every insight has invalidation_templates (>=1) and a translation_rules.per_profile_translation entry.
  - License unknown / restricted_or_unclear -> export blocked + marketplace redacted.
"""

import json
from copy import deepcopy
from pathlib import Path


# ---------- shared helpers ----------
def _rights_public_official(connector_roles):
    return {
        "connector_roles": connector_roles,
        "license_policy": "public_official",
        "query_policy": "allowed",
        "cache_policy": "allowed",
        "display_policy": "allowed",
        "export_policy": "allowed",
        "derived_value_policy": "allowed",
        "redistribution_policy": "allowed",
        "marketplace_policy": "allowed",
        "attribution_required": False,
        "retention_policy": "indefinite",
        "redaction_required": False,
    }


def _rights_public_professional(connector_roles):
    return {
        "connector_roles": connector_roles,
        "license_policy": "public_professional",
        "query_policy": "allowed",
        "cache_policy": "allowed",
        "display_policy": "allowed",
        "export_policy": "conditional",
        "derived_value_policy": "allowed",
        "redistribution_policy": "conditional",
        "marketplace_policy": "conditional",
        "attribution_required": True,
        "retention_policy": "indefinite",
        "redaction_required": False,
    }


def _rights_licensed(connector_roles):
    return {
        "connector_roles": connector_roles,
        "license_policy": "licensed_provider_required",
        "query_policy": "user_entitled",
        "cache_policy": "conditional",
        "display_policy": "conditional",
        "export_policy": "blocked",
        "derived_value_policy": "conditional",
        "redistribution_policy": "blocked",
        "marketplace_policy": "redacted",
        "attribution_required": True,
        "retention_policy": "until_license_expires",
        "redaction_required": True,
    }


def _rights_restricted(connector_roles):
    return {
        "connector_roles": connector_roles,
        "license_policy": "restricted_or_unclear",
        "query_policy": "blocked",
        "cache_policy": "blocked",
        "display_policy": "conditional",
        "export_policy": "blocked",
        "derived_value_policy": "blocked",
        "redistribution_policy": "blocked",
        "marketplace_policy": "blocked",
        "attribution_required": True,
        "retention_policy": "delete_on_user_revocation",
        "redaction_required": True,
    }


def _pit_filing():
    return {
        "observed_at_policy": "filing_accepted_at",
        "available_at_policy": "filing_accepted_at",
        "retrieved_at_policy": "connector_ingest_at",
        "source_version_policy": "filing_amendment_chain",
        "data_version_policy": "event_pit",
        "model_version_policy": "not_applicable",
        "vintage_required": False,
        "lookahead_risk": "low",
    }


def _pit_event_provider():
    return {
        "observed_at_policy": "event_time",
        "available_at_policy": "vendor_publication_at",
        "retrieved_at_policy": "vendor_retrieval_at",
        "source_version_policy": "provider_version",
        "data_version_policy": "event_pit",
        "model_version_policy": "not_applicable",
        "vintage_required": False,
        "lookahead_risk": "medium",
    }


def _pit_release():
    return {
        "observed_at_policy": "release_date",
        "available_at_policy": "release_date",
        "retrieved_at_policy": "connector_ingest_at",
        "source_version_policy": "regulator_version",
        "data_version_policy": "event_pit",
        "model_version_policy": "not_applicable",
        "vintage_required": False,
        "lookahead_risk": "low",
    }


def _pit_creation():
    return {
        "observed_at_policy": "creation_time_only",
        "available_at_policy": "creation_time_only",
        "retrieved_at_policy": "user_upload_at",
        "source_version_policy": "not_applicable",
        "data_version_policy": "latest_revisable",
        "model_version_policy": "model_run_id_required",
        "vintage_required": False,
        "lookahead_risk": "low",
    }


# ---------- EVENT FAMILY DEFAULTS ----------
EFAM = {}


def _ef(family, source_origin, default_credibility, materiality_default, pit, rights,
        connector_roles, sections, sources, profiles, related_entities=None, horizon="weeks",
        confidence="high_confidence_core"):
    return {
        "event_family": family,
        "source_origin": source_origin,
        "default_source_credibility": default_credibility,
        "materiality_default": materiality_default,
        "pit": pit,
        "rights": rights,
        "connector_roles": connector_roles,
        "sections": sections,
        "sources": sources,
        "profiles": profiles,
        "related_entity_types": related_entities or ["equity_security", "company"],
        "horizon_hint": horizon,
        "confidence": confidence,
    }


EFAM["earnings"] = _ef("earnings", "filing", 5, "high", _pit_filing(),
                       _rights_public_official(["sec_filings", "earnings_releases"]),
                       ["sec_filings", "earnings_releases"], ["§13.4", "§13.5"],
                       ["EV-001", "EV-002", "EV-003"],
                       ["earnings_revision_momentum", "post_earnings_drift_radar", "rsi_swing_catalyst_confirmation"])
EFAM["guidance"] = _ef("guidance", "press_release", 4, "high", _pit_event_provider(),
                       _rights_public_professional(["company_press_releases"]),
                       ["company_press_releases", "earnings_releases"], ["§13.4"],
                       ["EV-001", "EV-046"],
                       ["earnings_revision_momentum", "growth_at_reasonable_price"])
EFAM["analyst_rating"] = _ef("analyst_rating", "provider", 4, "medium", _pit_event_provider(),
                             _rights_licensed(["analyst_ratings"]),
                             ["analyst_ratings"], ["§13.5"], ["ANL-009", "ANL-010", "ANL-011"],
                             ["earnings_revision_momentum", "growth_at_reasonable_price"])
EFAM["analyst_estimate_revision"] = _ef("analyst_estimate_revision", "provider", 4, "medium",
                                        _pit_event_provider(),
                                        _rights_licensed(["analyst_estimates"]),
                                        ["analyst_estimates"], ["§13.5", "§13.10"],
                                        ["ANL-016", "EV-032"],
                                        ["earnings_revision_momentum", "factor_neutral_quantamental_selector"])
EFAM["mna_rumor"] = _ef("mna_rumor", "wire", 2, "medium", _pit_event_provider(),
                        _rights_licensed(["news_events"]),
                        ["news_events"], ["§13.6"], ["EV-031", "EV-046"],
                        ["merger_arbitrage_watchlist", "event_risk_monitor", "rsi_swing_catalyst_confirmation"],
                        horizon="days_to_weeks")
EFAM["confirmed_mna"] = _ef("confirmed_mna", "filing", 5, "high", _pit_filing(),
                            _rights_public_official(["sec_filings"]),
                            ["sec_filings"], ["§13.4", "§13.7"],
                            ["EV-008", "EV-009", "EV-027"],
                            ["merger_arbitrage_watchlist", "special_situations_monitor"])
EFAM["merger_arbitrage"] = _ef("merger_arbitrage", "computed", 5, "high", _pit_event_provider(),
                               _rights_licensed(["news_events"]),
                               ["news_events", "sec_filings"], ["§13.7"], ["EV-008", "EV-009"],
                               ["merger_arbitrage_watchlist"],
                               horizon="days_to_deal_close")
EFAM["spin_off"] = _ef("spin_off", "filing", 5, "high", _pit_filing(),
                       _rights_public_official(["sec_filings"]),
                       ["sec_filings"], ["§13.4", "§13.7"], ["EV-011", "EV-012"],
                       ["special_situations_monitor"],
                       horizon="weeks_to_months")
EFAM["restructuring"] = _ef("restructuring", "filing", 5, "high", _pit_filing(),
                            _rights_public_official(["sec_filings"]),
                            ["sec_filings"], ["§13.4"], ["EV-025"],
                            ["special_situations_monitor", "valuation_trap_detector"],
                            horizon="quarters")
EFAM["activism"] = _ef("activism", "filing", 5, "high", _pit_filing(),
                       _rights_public_official(["ownership_filings"]),
                       ["ownership_filings"], ["§13.4", "§9"],
                       ["EV-013", "EV-014", "EV-041", "GOV-005"],
                       ["activism_vulnerability_radar"],
                       horizon="months")
EFAM["buyback"] = _ef("buyback", "filing", 5, "medium", _pit_filing(),
                      _rights_public_official(["sec_filings"]),
                      ["sec_filings"], ["§13.4", "§9.4"], ["GOV-007"],
                      ["quality_value_long_only", "cheap_compounder"])
EFAM["dividend"] = _ef("dividend", "press_release", 5, "medium", _pit_event_provider(),
                       _rights_public_professional(["company_press_releases", "corporate_actions"]),
                       ["company_press_releases", "corporate_actions"], ["§13.4"],
                       ["GOV-007", "GOV-008"], ["dividend_sustainability_radar"])
EFAM["equity_issuance"] = _ef("equity_issuance", "filing", 5, "medium", _pit_filing(),
                              _rights_public_official(["sec_filings"]),
                              ["sec_filings"], ["§13.4"], ["EV-026", "EV-027"],
                              ["valuation_trap_detector", "portfolio_risk_radar"])
EFAM["debt_refinancing"] = _ef("debt_refinancing", "filing", 5, "medium", _pit_filing(),
                               _rights_public_official(["sec_filings"]),
                               ["sec_filings"], ["§13.4"], ["EV-026"],
                               ["dividend_sustainability_radar", "short_red_flag_monitor"])
EFAM["insider_transaction"] = _ef("insider_transaction", "filing", 5, "medium", _pit_filing(),
                                  _rights_public_official(["insider_transactions"]),
                                  ["insider_transactions"], ["§9.5", "§13.4"],
                                  ["GOV-012", "GOV-013", "GOV-014"],
                                  ["insider_cluster_breakout", "activism_vulnerability_radar"])
EFAM["regulatory"] = _ef("regulatory", "regulator", 5, "high", _pit_release(),
                         _rights_public_official(["sec_filings"]),
                         ["sec_filings", "macro_official"], ["§13.4", "§17.5"],
                         ["EV-029", "EV-030", "EV-047", "EV-048"],
                         ["event_risk_monitor", "short_red_flag_monitor", "merger_arbitrage_watchlist"])
EFAM["fda_clinical"] = _ef("fda_clinical", "regulator", 5, "critical", _pit_release(),
                           _rights_public_official(["macro_official"]),
                           ["macro_official"], ["§13.4"], ["EV-015", "EV-016", "EV-030"],
                           ["event_risk_monitor"], related_entities=["equity_security", "company", "regulator"],
                           horizon="days_to_weeks")
EFAM["litigation"] = _ef("litigation", "filing", 4, "medium", _pit_filing(),
                         _rights_public_official(["sec_filings"]),
                         ["sec_filings"], ["§13.4", "§17"], ["EV-039"],
                         ["short_red_flag_monitor", "event_risk_monitor"])
EFAM["bankruptcy_distress"] = _ef("bankruptcy_distress", "filing", 5, "critical", _pit_filing(),
                                  _rights_public_official(["sec_filings"]),
                                  ["sec_filings"], ["§17.5", "§17.9"],
                                  ["SH-006", "SH-007", "SH-008"],
                                  ["short_red_flag_monitor", "valuation_trap_detector"])
EFAM["index_inclusion_deletion"] = _ef("index_inclusion_deletion", "provider", 4, "medium",
                                       _pit_release(),
                                       _rights_licensed(["index_membership"]),
                                       ["index_membership"], ["§13.4", "§14"],
                                       ["EV-017", "EV-018", "EV-038"],
                                       ["special_situations_monitor", "portfolio_risk_radar"],
                                       horizon="days_to_weeks")
EFAM["management_change"] = _ef("management_change", "filing", 5, "high", _pit_filing(),
                                _rights_public_official(["sec_filings"]),
                                ["sec_filings"], ["§9.3", "§13.4"],
                                ["GOV-011", "GOV-018"],
                                ["activism_vulnerability_radar", "quality_value_long_only"])
EFAM["product_launch"] = _ef("product_launch", "press_release", 4, "medium",
                             _pit_event_provider(),
                             _rights_public_professional(["company_press_releases"]),
                             ["company_press_releases", "news_events"], ["§13.4"],
                             ["EV-031", "EV-046"], ["growth_at_reasonable_price"])
EFAM["product_recall"] = _ef("product_recall", "press_release", 4, "high", _pit_event_provider(),
                             _rights_public_professional(["company_press_releases"]),
                             ["company_press_releases", "news_events"], ["§13.4"],
                             ["EV-031", "EV-046"],
                             ["short_red_flag_monitor", "event_risk_monitor"])
EFAM["supply_chain"] = _ef("supply_chain", "wire", 3, "medium", _pit_event_provider(),
                           _rights_licensed(["news_events"]),
                           ["news_events"], ["§13.4", "§8.3"], ["EV-046"],
                           ["event_risk_monitor", "growth_at_reasonable_price"],
                           confidence="common_practice")
EFAM["unusual_volume"] = _ef("unusual_volume", "computed", 4, "medium", _pit_event_provider(),
                             _rights_public_professional(["prices_ohlcv"]),
                             ["prices_ohlcv"], ["§12.3", "§12.9"], ["TE-002"],
                             ["rsi_swing_catalyst_confirmation"],
                             confidence="common_practice", horizon="days")
EFAM["unusual_options_activity"] = _ef("unusual_options_activity", "computed", 4, "medium",
                                       _pit_event_provider(),
                                       _rights_licensed(["options"]),
                                       ["options"], ["§12.4", "§14.10"],
                                       ["TE-021", "TE-022", "OW-027"],
                                       ["event_risk_monitor", "merger_arbitrage_watchlist"],
                                       confidence="research_supported_experimental",
                                       horizon="days")
EFAM["social_sentiment_spike"] = _ef("social_sentiment_spike", "computed", 1, "low",
                                     _pit_event_provider(),
                                     _rights_restricted(["social_data"]),
                                     ["social_data"], ["§15", "§15.5"],
                                     ["BE-028", "BE-030", "BE-033"],
                                     ["event_risk_monitor"],
                                     confidence="research_supported_experimental",
                                     horizon="days")
EFAM["news_sentiment_shift"] = _ef("news_sentiment_shift", "provider", 3, "low",
                                   _pit_event_provider(),
                                   _rights_licensed(["news_events"]),
                                   ["news_events"], ["§15", "§15.5"],
                                   ["BE-009", "BE-014", "BE-031"],
                                   ["earnings_revision_momentum", "event_risk_monitor"],
                                   confidence="common_practice")
EFAM["peer_contagion"] = _ef("peer_contagion", "computed", 3, "medium", _pit_event_provider(),
                             _rights_public_professional(["prices_ohlcv"]),
                             ["prices_ohlcv", "fundamentals_as_reported"], ["§8.3", "§13.4"],
                             ["I-013", "I-014"],
                             ["portfolio_risk_radar", "event_risk_monitor"],
                             confidence="common_practice")
EFAM["sector_contagion"] = _ef("sector_contagion", "computed", 3, "medium", _pit_event_provider(),
                               _rights_public_professional(["prices_ohlcv"]),
                               ["prices_ohlcv"], ["§8", "§16.6"], ["MA-024", "I-001"],
                               ["portfolio_risk_radar", "macro_regime_equity_selector"],
                               confidence="common_practice")
EFAM["macro_policy"] = _ef("macro_policy", "regulator", 5, "high", _pit_release(),
                           _rights_public_official(["macro_official"]),
                           ["macro_official"], ["§16.6"],
                           ["MA-004", "MA-005", "MA-015"],
                           ["macro_regime_equity_selector", "portfolio_risk_radar"],
                           related_entities=["macro_series", "regulator"])


# ---------- EVENT SPECS ----------
# Each spec is a tuple: (event_id, display_name, family, description, overrides_dict)
EVENT_SPECS = []


def E(eid, name, family, desc, overrides=None):
    EVENT_SPECS.append((eid, name, family, desc, overrides or {}))


# earnings (6)
E("earnings_release", "Earnings Release", "earnings", "Issuer earnings release (8-K Item 2.02) including reported EPS, revenue, margins.")
E("earnings_call_held", "Earnings Call Held", "earnings", "Live investor call following the earnings release.")
E("earnings_surprise_positive", "Earnings Surprise (Positive)", "earnings", "Reported EPS materially above PIT consensus.", {"materiality_default": "high"})
E("earnings_surprise_negative", "Earnings Surprise (Negative)", "earnings", "Reported EPS materially below PIT consensus.", {"materiality_default": "high"})
E("revenue_surprise_positive", "Revenue Surprise (Positive)", "earnings", "Reported revenue materially above consensus.")
E("revenue_surprise_negative", "Revenue Surprise (Negative)", "earnings", "Reported revenue materially below consensus.")
E("margin_surprise_positive", "Margin Surprise (Positive)", "earnings", "Reported operating margin materially above consensus.")
E("margin_surprise_negative", "Margin Surprise (Negative)", "earnings", "Reported operating margin materially below consensus.")

# guidance (5)
E("guidance_issued", "Guidance Issued", "guidance", "Management issues forward guidance (revenue/EPS/operating metrics).")
E("guidance_raised", "Guidance Raised", "guidance", "Management raises guidance midpoint.", {"materiality_default": "high"})
E("guidance_lowered", "Guidance Lowered", "guidance", "Management lowers guidance midpoint.", {"materiality_default": "high"})
E("guidance_withdrawn", "Guidance Withdrawn", "guidance", "Management withdraws guidance.", {"materiality_default": "high"})
E("guidance_reaffirmed", "Guidance Reaffirmed", "guidance", "Management reaffirms prior guidance.", {"materiality_default": "low"})

# analyst_rating (5)
E("analyst_upgrade", "Analyst Upgrade", "analyst_rating", "Provider analyst raises recommendation tier.")
E("analyst_downgrade", "Analyst Downgrade", "analyst_rating", "Provider analyst lowers recommendation tier.")
E("analyst_initiation", "Analyst Initiation of Coverage", "analyst_rating", "Provider analyst begins coverage with an initial rating.")
E("analyst_coverage_drop", "Analyst Coverage Drop", "analyst_rating", "Provider drops coverage of a name.")
E("analyst_target_price_change", "Analyst Target Price Change", "analyst_rating", "Provider analyst changes target price.")

# analyst_estimate_revision (4)
E("estimate_revision_up", "Estimate Revision (Up)", "analyst_estimate_revision", "Individual analyst raises EPS / revenue / margin estimate.")
E("estimate_revision_down", "Estimate Revision (Down)", "analyst_estimate_revision", "Individual analyst lowers estimate.")
E("estimate_dispersion_shift", "Estimate Dispersion Shift", "analyst_estimate_revision", "Cross-sectional dispersion of consensus estimates changes materially.", {"confidence": "common_practice"})
E("estimate_recommendation_change", "Estimate Recommendation Change", "analyst_estimate_revision", "Recommendation classification changes within a single analyst's coverage.")

# mna_rumor (2)
E("mna_rumor_target", "M&A Rumor (Target)", "mna_rumor", "Wire / news report identifies a candidate target. Always carries unverified flag.", {"horizon_hint": "days_to_weeks"})
E("mna_rumor_acquirer", "M&A Rumor (Acquirer)", "mna_rumor", "Wire / news report identifies a candidate acquirer. Always carries unverified flag.", {"horizon_hint": "days_to_weeks"})

# confirmed_mna (7)
E("mna_announced", "M&A Announced", "confirmed_mna", "8-K Item 1.01 confirms agreed deal terms.")
E("mna_terms_changed", "M&A Terms Changed", "confirmed_mna", "Acquirer or target restates deal terms; 8-K amendment or S-4 update.")
E("mna_regulatory_review_filed", "M&A Regulatory Review Filed", "confirmed_mna", "HSR / antitrust filing accepted.")
E("mna_regulatory_approval", "M&A Regulatory Approval", "confirmed_mna", "Antitrust / regulatory body clears the deal.")
E("mna_regulatory_block", "M&A Regulatory Block", "confirmed_mna", "Regulator blocks or files action against the deal.", {"materiality_default": "critical"})
E("mna_deal_break", "M&A Deal Break", "confirmed_mna", "Counterparty walks or terminates the agreement.", {"materiality_default": "critical"})
E("mna_completed", "M&A Completed", "confirmed_mna", "Deal closes; target ceases to trade as independent.")

# merger_arbitrage (4)
E("merger_arb_spread_widened", "Merger-Arb Spread Widened", "merger_arbitrage", "Deal spread increases materially against close probability.")
E("merger_arb_spread_narrowed", "Merger-Arb Spread Narrowed", "merger_arbitrage", "Deal spread decreases materially.")
E("merger_arb_break_event", "Merger-Arb Break Event", "merger_arbitrage", "Deal terminated; arb position must close.", {"materiality_default": "critical"})
E("merger_arb_regulatory_clearance", "Merger-Arb Regulatory Clearance", "merger_arbitrage", "All regulatory bars cleared; pre-close window opens.")

# spin_off (4)
E("spinoff_announced", "Spin-Off Announced", "spin_off", "Issuer announces spin-off of a segment / business.")
E("spinoff_record_date", "Spin-Off Record Date", "spin_off", "Record date set for distribution.")
E("spinoff_distribution_completed", "Spin-Off Distribution Completed", "spin_off", "Distribution complete; spun entity begins trading independently.")
E("spinoff_post_distribution_overhang", "Spin-Off Post-Distribution Overhang", "spin_off", "Forced-seller pressure on the spun entity post-distribution.")

# restructuring (3)
E("restructuring_announced", "Restructuring Announced", "restructuring", "Issuer announces operating / portfolio restructuring (8-K Item 2.05).")
E("restructuring_milestone", "Restructuring Milestone", "restructuring", "Milestone reached or missed in the restructuring plan.")
E("restructuring_completed", "Restructuring Completed", "restructuring", "Restructuring fully implemented.")

# activism (5)
E("activist_13d_filed", "Activist 13D Filed", "activism", "Activist crosses 5% threshold and files Schedule 13D.")
E("activist_proxy_contest_initiated", "Activist Proxy Contest Initiated", "activism", "Activist initiates proxy contest for board seats / governance change.")
E("activist_board_seat_won", "Activist Board Seat Won", "activism", "Activist secures board representation via settlement or vote.")
E("activist_settlement", "Activist Settlement", "activism", "Company settles with activist (board seats / governance changes / capital allocation).")
E("activist_withdrawal", "Activist Withdrawal", "activism", "Activist exits position or terminates campaign.")

# buyback (4)
E("buyback_authorized", "Buyback Authorized", "buyback", "Board authorizes new repurchase program.")
E("buyback_accelerated", "Buyback Accelerated", "buyback", "Issuer accelerates pace of repurchases (ASR or equivalent).")
E("buyback_suspended", "Buyback Suspended", "buyback", "Issuer pauses or suspends repurchases.", {"materiality_default": "high"})
E("buyback_completed", "Buyback Completed", "buyback", "Authorized program completed.")

# dividend (5)
E("dividend_initiation", "Dividend Initiation", "dividend", "Issuer initiates regular dividend.")
E("dividend_increase", "Dividend Increase", "dividend", "Issuer raises dividend.")
E("dividend_decrease", "Dividend Decrease", "dividend", "Issuer cuts dividend.", {"materiality_default": "high"})
E("dividend_suspension", "Dividend Suspension", "dividend", "Issuer suspends dividend.", {"materiality_default": "critical"})
E("dividend_special", "Special Dividend", "dividend", "Issuer declares one-time special dividend.")

# equity_issuance (3)
E("secondary_offering", "Secondary Equity Offering", "equity_issuance", "Issuer or insider sells new common equity.")
E("convertible_issuance", "Convertible Issuance", "equity_issuance", "Convertible debt / preferred issuance.")
E("atm_offering", "ATM (At-the-Market) Offering", "equity_issuance", "Continuous offering established via shelf registration.")

# debt_refinancing (3)
E("debt_issuance", "Debt Issuance", "debt_refinancing", "New debt issuance (notes / bonds / term loan).")
E("debt_repayment", "Debt Repayment", "debt_refinancing", "Material debt repayment / paydown.")
E("debt_refinanced", "Debt Refinanced", "debt_refinancing", "Existing debt refinanced (new pricing / terms / maturity).")

# insider_transaction (5)
E("insider_purchase", "Insider Purchase (Form 4 P)", "insider_transaction", "Open-market purchase by a Section 16 insider.")
E("insider_sale", "Insider Sale (Form 4 S)", "insider_transaction", "Open-market sale by a Section 16 insider.")
E("insider_grant", "Insider Grant (Form 4 A)", "insider_transaction", "Equity grant to a Section 16 insider.")
E("insider_exercise", "Insider Option Exercise (Form 4 M)", "insider_transaction", "Stock option exercise by a Section 16 insider.")
E("insider_cluster_purchase", "Insider Cluster Purchase (30d)", "insider_transaction", "Multiple insiders purchase within a 30-day rolling window.", {"materiality_default": "high"})

# regulatory (4)
E("regulatory_proposal", "Regulatory Proposal", "regulatory", "Agency publishes a notice of proposed rulemaking.")
E("regulatory_final_rule", "Regulatory Final Rule", "regulatory", "Agency finalizes a rule that materially affects the issuer or industry.")
E("regulatory_interpretive_release", "Regulatory Interpretive Release", "regulatory", "Interpretive release that changes compliance requirements.")
E("regulatory_enforcement_action", "Regulatory Enforcement Action", "regulatory", "SEC / DOJ / FTC / state-AG enforcement action initiated.", {"materiality_default": "critical"})

# fda_clinical (5)
E("fda_pdufa_date", "FDA PDUFA Date", "fda_clinical", "Statutory FDA review deadline for an approval decision.", {"materiality_default": "critical"})
E("fda_advisory_committee_meeting", "FDA Advisory Committee Meeting", "fda_clinical", "Independent advisory committee meets and votes on the application.", {"materiality_default": "high"})
E("fda_approval", "FDA Approval", "fda_clinical", "FDA approves the drug or device.", {"materiality_default": "critical"})
E("fda_complete_response_letter", "FDA Complete Response Letter", "fda_clinical", "FDA issues a CRL rejecting or deferring approval.", {"materiality_default": "critical"})
E("fda_boxed_warning_added", "FDA Boxed Warning Added", "fda_clinical", "FDA mandates a boxed warning on a product.", {"materiality_default": "high"})

# litigation (4)
E("litigation_filed", "Litigation Filed", "litigation", "Material lawsuit filed against the issuer.")
E("litigation_settled", "Litigation Settled", "litigation", "Material lawsuit settled.")
E("litigation_appellate_ruling", "Litigation Appellate Ruling", "litigation", "Appellate court ruling on a material case.")
E("class_action_certified", "Class Action Certified", "litigation", "Plaintiffs' class certified in a securities class action.", {"materiality_default": "high"})

# bankruptcy_distress (4)
E("covenant_breach", "Covenant Breach", "bankruptcy_distress", "Debt covenant breached; issuer notifies lenders.")
E("chapter_11_filing", "Chapter 11 Filing", "bankruptcy_distress", "Issuer files for Chapter 11 reorganization.", {"materiality_default": "critical"})
E("chapter_7_filing", "Chapter 7 Filing", "bankruptcy_distress", "Issuer files for Chapter 7 liquidation.", {"materiality_default": "critical"})
E("emergence_from_bankruptcy", "Emergence from Bankruptcy", "bankruptcy_distress", "Issuer emerges from Chapter 11 with new capital structure.")

# index_inclusion_deletion (4)
E("index_inclusion_announced", "Index Inclusion Announced", "index_inclusion_deletion", "Index provider announces upcoming inclusion.")
E("index_inclusion_effective", "Index Inclusion Effective", "index_inclusion_deletion", "Inclusion takes effect; passive demand realized.")
E("index_deletion", "Index Deletion", "index_inclusion_deletion", "Index provider deletes constituent; passive selling realized.")
E("index_rebalance_event", "Index Rebalance Event", "index_inclusion_deletion", "Scheduled rebalance of constituent weights.")

# management_change (5)
E("ceo_change_announced", "CEO Change Announced", "management_change", "Issuer discloses CEO departure / appointment.")
E("cfo_change_announced", "CFO Change Announced", "management_change", "Issuer discloses CFO departure / appointment.")
E("chair_change_announced", "Chair Change Announced", "management_change", "Issuer discloses board chair change.")
E("director_resignation", "Director Resignation", "management_change", "Independent director resigns mid-term; 8-K Item 5.02.")
E("succession_plan_disclosed", "Succession Plan Disclosed", "management_change", "Issuer publishes formal management succession plan.")

# product_launch / product_recall / supply_chain (6)
E("product_launch", "Product Launch", "product_launch", "Material new product launch.")
E("product_launch_delay", "Product Launch Delay", "product_launch", "Issuer postpones a previously announced launch.")
E("product_recall", "Product Recall", "product_recall", "Issuer recalls a product (regulatory or voluntary).", {"materiality_default": "high"})
E("product_quality_issue", "Product Quality Issue", "product_recall", "Disclosed product quality / safety issue not yet a formal recall.")
E("supply_chain_disruption", "Supply Chain Disruption", "supply_chain", "Material supply chain disruption (component shortage / sanctions).", {"materiality_default": "high"})
E("supply_chain_recovery", "Supply Chain Recovery", "supply_chain", "Issuer reports resolution of supply-chain disruption.")

# unusual_volume / unusual_options_activity (4)
E("unusual_volume_spike", "Unusual Volume Spike", "unusual_volume", "Volume z-score exceeds 3 stdev over 20-day window.")
E("unusual_volume_collapse", "Unusual Volume Collapse", "unusual_volume", "Volume drops well below typical range.")
E("unusual_options_call_activity", "Unusual Options Call Activity", "unusual_options_activity", "Abnormal call volume / open interest pattern.")
E("unusual_options_put_activity", "Unusual Options Put Activity", "unusual_options_activity", "Abnormal put volume / open interest pattern.")

# social_sentiment_spike / news_sentiment_shift (4)
E("social_sentiment_spike", "Social Sentiment Spike", "social_sentiment_spike", "Abnormal social-media mention volume + sentiment shift. Human review required.", {"materiality_default": "low"})
E("meme_stock_alert", "Meme Stock Alert", "social_sentiment_spike", "Composite social-volume + short-interest + abnormal-volume alert. Human review required.")
E("news_sentiment_shift_positive", "News Sentiment Shift (Positive)", "news_sentiment_shift", "Provider news sentiment turns materially positive.")
E("news_sentiment_shift_negative", "News Sentiment Shift (Negative)", "news_sentiment_shift", "Provider news sentiment turns materially negative.")

# peer_contagion / sector_contagion (4)
E("peer_event_contagion", "Peer Event Contagion", "peer_contagion", "Material event at a peer with cross-name return implications.")
E("peer_fundamental_drift", "Peer Fundamental Drift", "peer_contagion", "Peer-set fundamental metrics drift relative to the focal name.")
E("sector_event_contagion", "Sector Event Contagion", "sector_contagion", "Sector-wide event (regulatory, macro shock, technology shift) with cross-name implications.")
E("sector_regime_shift", "Sector Regime Shift", "sector_contagion", "Sector cycle position changes per macro overlay.")

# macro_policy (8)
E("fomc_decision", "FOMC Decision", "macro_policy", "Federal Open Market Committee monetary-policy decision.")
E("ecb_decision", "ECB Decision", "macro_policy", "European Central Bank decision.")
E("boj_decision", "BOJ Decision", "macro_policy", "Bank of Japan decision.")
E("boe_decision", "BOE Decision", "macro_policy", "Bank of England decision.")
E("cpi_release", "CPI Release", "macro_policy", "BLS CPI release.")
E("payrolls_release", "Nonfarm Payrolls Release", "macro_policy", "BLS nonfarm payrolls release.")
E("gdp_release", "GDP Release", "macro_policy", "BEA quarterly GDP release.")
E("ism_release", "ISM Release", "macro_policy", "ISM Manufacturing or Services PMI release.")


# ---------- INSIGHT FAMILY DEFAULTS ----------
IFAM = {}


def _if(family, direction, profiles, pit, rights, sections, sources, confidence="common_practice", non_advice=True, human_review=False, horizon="varies"):
    return {
        "insight_family": family,
        "direction_logic": direction,
        "profiles": profiles,
        "pit": pit,
        "rights": rights,
        "sections": sections,
        "sources": sources,
        "confidence": confidence,
        "non_advice": non_advice,
        "human_review": human_review,
        "horizon": horizon,
    }


IFAM["fundamental_state"] = _if("fundamental_state", "long_supportive",
                                ["quality_value_long_only", "cheap_compounder", "growth_at_reasonable_price"],
                                _pit_filing(), _rights_public_official(["sec_filings"]),
                                ["§6", "§22"], ["F-001", "F-003", "F-013"], confidence="high_confidence_core")
IFAM["valuation_state"] = _if("valuation_state", "long_supportive",
                              ["quality_value_long_only", "cheap_compounder", "valuation_trap_detector"],
                              _pit_filing(), _rights_public_official(["sec_filings"]),
                              ["§7"], ["V-001", "V-003", "V-014"], confidence="high_confidence_core")
IFAM["industry_state"] = _if("industry_state", "conditional",
                             ["quality_value_long_only", "cheap_compounder", "macro_regime_equity_selector"],
                             _pit_filing(), _rights_licensed(["security_master"]),
                             ["§8"], ["I-001", "I-005", "I-011"], confidence="common_practice")
IFAM["governance_state"] = _if("governance_state", "long_supportive",
                               ["quality_value_long_only", "cheap_compounder", "activism_vulnerability_radar"],
                               _pit_filing(), _rights_public_official(["sec_filings"]),
                               ["§9"], ["GOV-001", "GOV-002", "GOV-011"], confidence="high_confidence_core")
IFAM["factor_state"] = _if("factor_state", "profile_dependent",
                           ["factor_neutral_quantamental_selector", "earnings_revision_momentum", "portfolio_risk_radar"],
                           _pit_release(), _rights_public_official(["factor_data"]),
                           ["§10"], ["FA-005", "FA-009", "FA-052"], confidence="common_practice")
IFAM["event_state"] = _if("event_state", "profile_dependent",
                          ["earnings_revision_momentum", "post_earnings_drift_radar", "merger_arbitrage_watchlist", "event_risk_monitor"],
                          _pit_event_provider(),
                          _rights_public_professional(["sec_filings", "news_events"]),
                          ["§13"], ["EV-001", "EV-008", "EV-013"], confidence="high_confidence_core")
IFAM["ownership_state"] = _if("ownership_state", "conditional",
                              ["activism_vulnerability_radar", "portfolio_risk_radar", "insider_cluster_breakout"],
                              _pit_filing(), _rights_public_official(["ownership_filings"]),
                              ["§14"], ["OW-001", "OW-022", "OW-023"], confidence="high_confidence_core")
IFAM["sentiment_state"] = _if("sentiment_state", "conditional",
                              ["earnings_revision_momentum", "event_risk_monitor"],
                              _pit_event_provider(),
                              _rights_licensed(["news_events"]),
                              ["§15"], ["BE-009", "BE-011", "BE-014"], confidence="research_supported_experimental")
IFAM["macro_state"] = _if("macro_state", "conditional",
                          ["macro_regime_equity_selector", "portfolio_risk_radar", "dividend_sustainability_radar"],
                          _pit_release(), _rights_public_official(["macro_official"]),
                          ["§16"], ["MA-001", "MA-002", "MA-014"], confidence="common_practice")
IFAM["short_state"] = _if("short_state", "short_supportive",
                          ["short_red_flag_monitor", "valuation_trap_detector"],
                          _pit_filing(), _rights_public_official(["sec_filings"]),
                          ["§17"], ["SH-001", "SH-006", "SH-018"],
                          confidence="common_practice", human_review=True)
IFAM["portfolio_state"] = _if("portfolio_state", "risk_only",
                              ["portfolio_risk_radar"],
                              _pit_creation(),
                              {"connector_roles": [], "license_policy": "internal_research_only",
                               "query_policy": "user_entitled", "cache_policy": "allowed",
                               "display_policy": "allowed", "export_policy": "blocked",
                               "derived_value_policy": "conditional", "redistribution_policy": "blocked",
                               "marketplace_policy": "blocked", "attribution_required": False,
                               "retention_policy": "delete_on_user_revocation", "redaction_required": True},
                              ["§11"], ["PC-001", "PC-005", "PC-021"], confidence="high_confidence_core")
IFAM["decision_state"] = _if("decision_state", "profile_dependent",
                             ["quality_value_long_only", "earnings_revision_momentum", "portfolio_risk_radar"],
                             _pit_creation(),
                             {"connector_roles": [], "license_policy": "internal_research_only",
                              "query_policy": "user_entitled", "cache_policy": "allowed",
                              "display_policy": "allowed", "export_policy": "blocked",
                              "derived_value_policy": "conditional", "redistribution_policy": "blocked",
                              "marketplace_policy": "blocked", "attribution_required": False,
                              "retention_policy": "delete_on_user_revocation", "redaction_required": True},
                             ["§3"], ["G-001", "G-003", "G-015"], confidence="high_confidence_core")
IFAM["validation_state"] = _if("validation_state", "risk_only",
                               ["quality_value_long_only", "portfolio_risk_radar", "factor_neutral_quantamental_selector"],
                               _pit_creation(),
                               {"connector_roles": [], "license_policy": "internal_research_only",
                                "query_policy": "user_entitled", "cache_policy": "allowed",
                                "display_policy": "allowed", "export_policy": "conditional",
                                "derived_value_policy": "allowed", "redistribution_policy": "conditional",
                                "marketplace_policy": "redacted", "attribution_required": False,
                                "retention_policy": "indefinite", "redaction_required": True},
                               ["§19"], ["P-013", "P-014", "FA-040"], confidence="high_confidence_core")
IFAM["rights_state"] = _if("rights_state", "risk_only",
                           ["quality_value_long_only", "portfolio_risk_radar"],
                           _pit_creation(),
                           {"connector_roles": [], "license_policy": "internal_research_only",
                            "query_policy": "user_entitled", "cache_policy": "allowed",
                            "display_policy": "allowed", "export_policy": "blocked",
                            "derived_value_policy": "conditional", "redistribution_policy": "blocked",
                            "marketplace_policy": "blocked", "attribution_required": False,
                            "retention_policy": "indefinite", "redaction_required": True},
                           ["§18"], ["DA-007", "DA-020"], confidence="high_confidence_core")
IFAM["pit_state"] = _if("pit_state", "risk_only",
                        ["factor_neutral_quantamental_selector", "portfolio_risk_radar"],
                        _pit_creation(),
                        {"connector_roles": [], "license_policy": "internal_research_only",
                         "query_policy": "user_entitled", "cache_policy": "allowed",
                         "display_policy": "allowed", "export_policy": "conditional",
                         "derived_value_policy": "allowed", "redistribution_policy": "conditional",
                         "marketplace_policy": "redacted", "attribution_required": False,
                         "retention_policy": "indefinite", "redaction_required": True},
                        ["§18.6", "§19"], ["DA-003", "DA-040"], confidence="high_confidence_core")


# ---------- INSIGHT SPECS ----------
INSIGHT_SPECS = []


def I(iid, name, family, desc, req_attrs=None, req_events=None,
      opt_conf=None, profile_trans=None, overrides=None):
    INSIGHT_SPECS.append((iid, name, family, desc, req_attrs or [], req_events or [],
                           opt_conf or [], profile_trans or [], overrides or {}))


# --- fundamental_state (11) ---
I("cash_conversion_strength", "Cash Conversion Strength", "fundamental_state",
  "Cash from operations and free cash flow track or exceed reported net income; quality indicator.",
  req_attrs=["cfo_to_ni_ttm", "fcf_to_ni_ttm"], req_events=[],
  opt_conf=["balance_sheet_health", "margin_expansion_signal"],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "primary thesis support"},
      {"profile_id": "cheap_compounder", "interpretation": "primary thesis support"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "contradicts short thesis"},
  ])
I("margin_expansion_signal", "Margin Expansion Signal", "fundamental_state",
  "Operating margin expanded year-over-year with stable or rising revenue.",
  req_attrs=["operating_margin_expansion_yoy"], req_events=["earnings_release"],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
      {"profile_id": "growth_at_reasonable_price", "interpretation": "primary signal"},
  ])
I("revenue_growth_acceleration", "Revenue Growth Acceleration", "fundamental_state",
  "Year-over-year revenue growth accelerated vs prior quarter.",
  req_attrs=["revenue_growth_yoy_q"], req_events=["earnings_release"],
  profile_trans=[
      {"profile_id": "growth_at_reasonable_price", "interpretation": "primary signal"},
      {"profile_id": "earnings_revision_momentum", "interpretation": "confirmation"},
  ])
I("revenue_growth_deceleration", "Revenue Growth Deceleration", "fundamental_state",
  "Year-over-year revenue growth decelerated materially.",
  req_attrs=["revenue_growth_yoy_q"], req_events=["earnings_release"],
  profile_trans=[
      {"profile_id": "growth_at_reasonable_price", "interpretation": "risk flag"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports negative thesis"},
  ])
I("balance_sheet_fragility", "Balance Sheet Fragility", "fundamental_state",
  "Leverage above sector p80 and interest coverage below 2x; near-term maturities heavy.",
  req_attrs=["net_debt_to_ebitda_ttm", "interest_coverage_ttm", "debt_maturity_1y_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "blocking risk gate"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
      {"profile_id": "valuation_trap_detector", "interpretation": "primary signal"},
  ])
I("accounting_quality_red_flag", "Accounting Quality Red Flag", "fundamental_state",
  "Composite signal: high accruals + low cash conversion + non-GAAP add-back inflation. Evidence-only; never auto-action.",
  req_attrs=["sloan_accruals_zscore", "cfo_to_ni_ttm"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "quality_value_long_only", "interpretation": "blocking risk gate"},
  ],
  overrides={"human_review": True, "confidence": "common_practice"})
I("fundamental_deterioration", "Fundamental Deterioration", "fundamental_state",
  "Multi-quarter trend of margin compression + revenue deceleration + cash-conversion decline.",
  req_attrs=["operating_margin_expansion_yoy", "revenue_growth_yoy_q", "cfo_to_ni_ttm"],
  req_events=["earnings_release"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
  ])
I("revenue_quality_warning", "Revenue Quality Warning", "fundamental_state",
  "Rising DSO with revenue acceleration; possible channel-stuffing or aggressive recognition.",
  req_attrs=["dso_days", "revenue_growth_yoy_q"], req_events=["earnings_release"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
  ],
  overrides={"human_review": True})
I("non_gaap_addback_inflation", "Non-GAAP Add-Back Inflation", "fundamental_state",
  "Recurring add-backs inflate non-GAAP measures relative to GAAP.",
  req_attrs=["sbc_to_revenue_ttm"], req_events=["earnings_release"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
  ])
I("restatement_downgrade", "Restatement Downgrade", "fundamental_state",
  "Issuer filed 10-K/A or 10-Q/A; downgrade quality flag and re-vintage dependent attributes.",
  req_attrs=["restatement_flag"], req_events=["earnings_release"],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "blocking risk gate"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
  ],
  overrides={"human_review": True, "confidence": "high_confidence_core"})
I("late_filing_warning", "Late Filing Warning", "fundamental_state",
  "NT 10-K / NT 10-Q filed; potential accounting / disclosure issue.",
  req_attrs=[], req_events=["earnings_release"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
  ])

# --- valuation_state (10) ---
I("valuation_discount", "Valuation Discount", "valuation_state",
  "Multiple compressed vs peer median and historical range; supports value thesis.",
  req_attrs=["pe_ttm", "peer_multiple_zscore"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "primary signal"},
      {"profile_id": "cheap_compounder", "interpretation": "primary signal"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "neutral evidence"},
  ])
I("valuation_premium", "Valuation Premium", "valuation_state",
  "Multiple expanded materially above peer median and historical range.",
  req_attrs=["pe_ttm", "peer_multiple_zscore"], req_events=[],
  profile_trans=[
      {"profile_id": "valuation_trap_detector", "interpretation": "risk flag"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "growth_at_reasonable_price", "interpretation": "risk flag"},
  ])
I("margin_of_safety_present", "Margin of Safety Present", "valuation_state",
  "Computed margin_of_safety_pct exceeds profile threshold (typically 25-40%).",
  req_attrs=["margin_of_safety_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "primary signal"},
      {"profile_id": "cheap_compounder", "interpretation": "primary signal"},
  ])
I("margin_of_safety_absent", "Margin of Safety Absent", "valuation_state",
  "Computed margin_of_safety_pct below profile threshold.",
  req_attrs=["margin_of_safety_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "blocking gate"},
      {"profile_id": "cheap_compounder", "interpretation": "blocking gate"},
  ])
I("implied_growth_too_high", "Implied Growth Too High", "valuation_state",
  "Reverse-DCF implied growth exceeds achievable rate given history and industry.",
  req_attrs=["implied_growth_perpetual", "reverse_dcf_growth_required"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "valuation_trap_detector", "interpretation": "primary signal"},
  ])
I("implied_growth_too_low", "Implied Growth Too Low", "valuation_state",
  "Reverse-DCF implied growth below realistic baseline; supports long thesis.",
  req_attrs=["implied_growth_perpetual"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "supports long thesis"},
      {"profile_id": "cheap_compounder", "interpretation": "supports long thesis"},
  ])
I("peer_overhang", "Peer Overhang", "valuation_state",
  "Focal multiple materially above peer set median; mean-reversion risk.",
  req_attrs=["peer_multiple_zscore"], req_events=[],
  profile_trans=[
      {"profile_id": "valuation_trap_detector", "interpretation": "risk flag"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
  ])
I("peer_underhang", "Peer Underhang", "valuation_state",
  "Focal multiple materially below peer set median; potential value opportunity.",
  req_attrs=["peer_multiple_zscore"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "primary signal"},
      {"profile_id": "cheap_compounder", "interpretation": "primary signal"},
  ])
I("sensitivity_asymmetric_downside", "Asymmetric Downside Sensitivity", "valuation_state",
  "Bear-case scenario shows large downside relative to bull-case upside.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
      {"profile_id": "merger_arbitrage_watchlist", "interpretation": "risk flag"},
  ])
I("value_trap_warning", "Value Trap Warning", "valuation_state",
  "Low multiple + declining cash conversion + balance-sheet fragility composite.",
  req_attrs=["pe_ttm", "cfo_to_ni_ttm", "net_debt_to_ebitda_ttm"], req_events=[],
  profile_trans=[
      {"profile_id": "valuation_trap_detector", "interpretation": "primary signal"},
      {"profile_id": "quality_value_long_only", "interpretation": "blocking gate"},
  ])

# --- industry_state (8) ---
I("moat_widening", "Moat Widening", "industry_state",
  "ROIC-WACC spread expanding; durable competitive advantage evidence.",
  req_attrs=["roic_ttm", "moat_trend"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "primary signal"},
      {"profile_id": "cheap_compounder", "interpretation": "primary signal"},
  ])
I("moat_narrowing", "Moat Narrowing", "industry_state",
  "ROIC trending toward WACC; competitive position deteriorating.",
  req_attrs=["roic_ttm", "moat_trend"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "valuation_trap_detector", "interpretation": "supports trap warning"},
  ])
I("moat_unclear", "Moat Unclear", "industry_state",
  "Evidence ambiguous; no durable advantage demonstrable.",
  req_attrs=["moat_score_qualitative"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "downgrade signal"},
  ],
  overrides={"confidence": "common_practice"})
I("market_share_gain", "Market Share Gain", "industry_state",
  "Multi-period market share expansion vs industry growth.",
  req_attrs=["market_share_pct", "market_share_change_3y"], req_events=[],
  profile_trans=[
      {"profile_id": "growth_at_reasonable_price", "interpretation": "primary signal"},
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
  ])
I("market_share_loss", "Market Share Loss", "industry_state",
  "Multi-period market share contraction.",
  req_attrs=["market_share_change_3y"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "valuation_trap_detector", "interpretation": "supports trap warning"},
  ])
I("industry_consolidation", "Industry Consolidation", "industry_state",
  "Industry HHI rising via M&A; pricing power increases for surviving players.",
  req_attrs=["industry_concentration_hhi"], req_events=["mna_announced"],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
      {"profile_id": "growth_at_reasonable_price", "interpretation": "confirmation"},
  ])
I("regulatory_overhang", "Regulatory Overhang", "industry_state",
  "Material pending regulatory exposure affecting profitability or business model.",
  req_attrs=["industry_regulation_exposure_score"], req_events=["regulatory_proposal", "regulatory_final_rule"],
  profile_trans=[
      {"profile_id": "event_risk_monitor", "interpretation": "primary signal"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("disruption_threat", "Disruption Threat", "industry_state",
  "Christensen-style disruption pattern emerging; experimental signal.",
  req_attrs=["industry_disruption_risk_score"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "valuation_trap_detector", "interpretation": "risk flag"},
  ],
  overrides={"confidence": "research_supported_experimental"})

# --- governance_state (10) ---
I("governance_strong", "Governance Strong", "governance_state",
  "Independent board majority, aligned incentives, clawback policy, no material related-party transactions.",
  req_attrs=["board_independent_pct", "performance_metric_alignment_score", "clawback_policy_flag"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
      {"profile_id": "cheap_compounder", "interpretation": "confirmation"},
  ])
I("governance_weak", "Governance Weak", "governance_state",
  "Low board independence, misaligned compensation, material related-party transactions.",
  req_attrs=["board_independent_pct", "related_party_transactions_count"], req_events=[],
  profile_trans=[
      {"profile_id": "activism_vulnerability_radar", "interpretation": "primary signal"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "quality_value_long_only", "interpretation": "blocking gate"},
  ])
I("incentive_misalignment", "Incentive Misalignment", "governance_state",
  "CEO pay decoupled from performance metrics; pay-for-performance score weak.",
  req_attrs=["performance_metric_alignment_score", "ceo_total_comp_usd"], req_events=[],
  profile_trans=[
      {"profile_id": "activism_vulnerability_radar", "interpretation": "supporting signal"},
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
  ])
I("insider_cluster_buying_signal", "Insider Cluster Buying Signal", "governance_state",
  "Multiple Section 16 insiders open-market purchase within 30 days.",
  req_attrs=["insider_cluster_purchase_30d_flag", "insider_net_buy_value_90d_usd"], req_events=["insider_cluster_purchase"],
  profile_trans=[
      {"profile_id": "insider_cluster_breakout", "interpretation": "primary signal"},
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
  ])
I("insider_heavy_selling_warning", "Insider Heavy Selling Warning", "governance_state",
  "Cluster of insider sales not attributable to scheduled 10b5-1 plans; price weakness present.",
  req_attrs=["insider_net_buy_value_90d_usd"], req_events=["insider_sale"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
  ])
I("buyback_above_intrinsic_warning", "Buyback Above Intrinsic Warning", "governance_state",
  "Issuer repurchasing at prices materially above intrinsic-value estimate.",
  req_attrs=["buyback_quality_score", "margin_of_safety_pct"], req_events=["buyback_authorized"],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
      {"profile_id": "valuation_trap_detector", "interpretation": "supports trap warning"},
  ])
I("buyback_below_intrinsic_value_creation", "Buyback Below Intrinsic Value Creation", "governance_state",
  "Issuer repurchases at material discount to intrinsic value; capital allocation positive.",
  req_attrs=["buyback_quality_score", "margin_of_safety_pct"], req_events=["buyback_authorized"],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
      {"profile_id": "cheap_compounder", "interpretation": "confirmation"},
  ])
I("dividend_unsustainable_warning", "Dividend Unsustainable Warning", "governance_state",
  "Payout ratio above 80% of FCF + near-term debt maturities heavy.",
  req_attrs=["dividend_payout_to_fcf", "debt_maturity_1y_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "dividend_sustainability_radar", "interpretation": "primary signal"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
  ])
I("ma_value_creation_pattern", "M&A Value Creation Pattern", "governance_state",
  "Track record of accretive acquisitions; ROIC stable or rising post-deal.",
  req_attrs=["m_a_value_creation_score"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
      {"profile_id": "cheap_compounder", "interpretation": "confirmation"},
  ])
I("ma_overpay_pattern", "M&A Overpay Pattern", "governance_state",
  "Track record of dilutive acquisitions + write-downs; capital allocation risk.",
  req_attrs=["m_a_value_creation_score"], req_events=[],
  profile_trans=[
      {"profile_id": "activism_vulnerability_radar", "interpretation": "supporting signal"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
  ])

# --- factor_state (8) ---
I("factor_signal_strong", "Factor Signal Strong", "factor_state",
  "Composite factor score in top decile vs investable universe.",
  req_attrs=["factor_score_composite", "factor_decile_value", "factor_decile_momentum", "factor_decile_quality"], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "primary signal"},
  ])
I("factor_signal_weak", "Factor Signal Weak", "factor_state",
  "Composite factor score in bottom decile vs investable universe.",
  req_attrs=["factor_score_composite"], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "primary signal (short side)"},
  ])
I("factor_signal_decayed", "Factor Signal Decayed", "factor_state",
  "Post-publication decay detected (McLean-Pontiff style monitor).",
  req_attrs=["factor_score_composite"], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "downgrade signal"},
  ],
  overrides={"confidence": "research_supported_experimental"})
I("factor_crowded_warning", "Factor Crowded Warning", "factor_state",
  "Provider crowding score above threshold; cohort risk elevated.",
  req_attrs=["factor_crowding_score"], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "risk flag"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ],
  overrides={"confidence": "research_supported_experimental"})
I("factor_capacity_warning", "Factor Capacity Warning", "factor_state",
  "Implied AUM exceeds factor-strategy capacity estimate (Frazzini-Israel-Moskowitz).",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "risk flag"},
  ])
I("factor_orthogonal_alpha", "Factor Orthogonal Alpha", "factor_state",
  "Residual return after factor regression remains positive across windows.",
  req_attrs=["factor_residual_252d"], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "primary signal"},
      {"profile_id": "earnings_revision_momentum", "interpretation": "confirmation"},
  ])
I("factor_loading_consistent_with_thesis", "Factor Loading Consistent with Thesis", "factor_state",
  "Factor exposures align with stated investment thesis (e.g., quality / value / momentum).",
  req_attrs=["beta_qmj", "beta_hml", "beta_umd_mom"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "neutral"},
  ])
I("factor_loading_contradicts_thesis", "Factor Loading Contradicts Thesis", "factor_state",
  "Factor exposures contradict stated investment thesis.",
  req_attrs=["beta_qmj", "beta_hml", "beta_umd_mom"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])

# --- event_state (12) ---
I("earnings_beat_with_guidance_raise", "Earnings Beat + Guidance Raise", "event_state",
  "Positive surprise on EPS and revenue + management raises guidance.",
  req_attrs=["earnings_surprise_pct", "revenue_surprise_pct"],
  req_events=["earnings_release", "guidance_raised"],
  profile_trans=[
      {"profile_id": "earnings_revision_momentum", "interpretation": "primary signal"},
      {"profile_id": "post_earnings_drift_radar", "interpretation": "primary signal"},
  ])
I("earnings_beat_with_guidance_cut", "Earnings Beat + Guidance Cut", "event_state",
  "Positive surprise on this quarter but management lowers forward guidance.",
  req_attrs=["earnings_surprise_pct"],
  req_events=["earnings_release", "guidance_lowered"],
  profile_trans=[
      {"profile_id": "earnings_revision_momentum", "interpretation": "risk flag"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
  ])
I("earnings_miss_with_guidance_raise", "Earnings Miss + Guidance Raise", "event_state",
  "Negative surprise this quarter but management raises forward guidance.",
  req_attrs=["earnings_surprise_pct"],
  req_events=["earnings_release", "guidance_raised"],
  profile_trans=[
      {"profile_id": "earnings_revision_momentum", "interpretation": "neutral evidence"},
  ])
I("earnings_miss_with_guidance_cut", "Earnings Miss + Guidance Cut", "event_state",
  "Negative surprise plus management lowers guidance; double-downgrade event.",
  req_attrs=["earnings_surprise_pct"],
  req_events=["earnings_release", "guidance_lowered"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
      {"profile_id": "post_earnings_drift_radar", "interpretation": "primary signal (short)"},
  ])
I("analyst_revision_momentum", "Analyst Revision Momentum", "event_state",
  "30-day revision balance materially positive (up minus down).",
  req_attrs=["revision_count_30d_up", "revision_count_30d_down"], req_events=["estimate_revision_up"],
  profile_trans=[
      {"profile_id": "earnings_revision_momentum", "interpretation": "primary signal"},
      {"profile_id": "growth_at_reasonable_price", "interpretation": "confirmation"},
  ])
I("deal_spread_attractive", "Deal Spread Attractive", "event_state",
  "Merger-arb spread > probability-adjusted downside.",
  req_attrs=["deal_spread_pct", "deal_probability"], req_events=["mna_announced"],
  profile_trans=[
      {"profile_id": "merger_arbitrage_watchlist", "interpretation": "primary signal"},
  ])
I("deal_break_risk_high", "Deal Break Risk High", "event_state",
  "Regulatory exposure + financing risk + spread widening pattern.",
  req_attrs=["deal_spread_pct"], req_events=["mna_regulatory_block"],
  profile_trans=[
      {"profile_id": "merger_arbitrage_watchlist", "interpretation": "risk flag"},
      {"profile_id": "event_risk_monitor", "interpretation": "primary signal"},
  ])
I("spinoff_forced_selling_observed", "Spin-Off Forced Selling Observed", "event_state",
  "Post-distribution price weakness on heavy volume; forced sellers exiting.",
  req_attrs=["abnormal_volume_z"], req_events=["spinoff_distribution_completed"],
  profile_trans=[
      {"profile_id": "special_situations_monitor", "interpretation": "primary signal"},
  ])
I("index_inclusion_premium_observed", "Index Inclusion Premium Observed", "event_state",
  "Pre-inclusion abnormal return on inclusion announcement.",
  req_attrs=["abnormal_return_event_window_3d"], req_events=["index_inclusion_announced"],
  profile_trans=[
      {"profile_id": "special_situations_monitor", "interpretation": "confirmation"},
  ])
I("fda_binary_pending", "FDA Binary Pending", "event_state",
  "PDUFA / advisory committee within the next 30 days; size accordingly.",
  req_attrs=["binary_event_within_30d_flag"], req_events=["fda_pdufa_date", "fda_advisory_committee_meeting"],
  profile_trans=[
      {"profile_id": "event_risk_monitor", "interpretation": "primary signal"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ],
  overrides={"human_review": True})
I("activist_engagement_observed", "Activist Engagement Observed", "event_state",
  "Activist 13D filing + public engagement plan.",
  req_attrs=["activist_present_flag"], req_events=["activist_13d_filed"],
  profile_trans=[
      {"profile_id": "activism_vulnerability_radar", "interpretation": "primary signal"},
  ])
I("litigation_material_overhang", "Litigation Material Overhang", "event_state",
  "Material class action certified or appellate ruling pending.",
  req_attrs=[], req_events=["class_action_certified", "litigation_appellate_ruling"],
  profile_trans=[
      {"profile_id": "event_risk_monitor", "interpretation": "primary signal"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
  ],
  overrides={"human_review": True})

# --- ownership_state (10) ---
I("institutional_quality_high", "Institutional Quality High", "ownership_state",
  "High dedicated + low transient ownership (Bushee).",
  req_attrs=["dedicated_pct", "transient_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
  ])
I("institutional_quality_weak", "Institutional Quality Weak", "ownership_state",
  "High transient + low dedicated ownership; trading-flow risk.",
  req_attrs=["transient_pct", "dedicated_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("crowded_long_warning", "Crowded Long Warning", "ownership_state",
  "Provider crowding score elevated on long side.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "risk flag"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ],
  overrides={"confidence": "research_supported_experimental"})
I("crowded_short_warning", "Crowded Short Warning", "ownership_state",
  "Short interest > 25% float + high DTC + provider crowding alert.",
  req_attrs=["short_interest_pct_float", "days_to_cover"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "risk flag"},
      {"profile_id": "rsi_swing_catalyst_confirmation", "interpretation": "squeeze risk"},
  ],
  overrides={"human_review": True})
I("squeeze_risk_elevated", "Squeeze Risk Elevated", "ownership_state",
  "DTC + SI%float + provider crowding composite indicates squeeze conditions.",
  req_attrs=["short_interest_pct_float", "days_to_cover"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "risk flag"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ],
  overrides={"human_review": True})
I("ownership_concentration_warning", "Ownership Concentration Warning", "ownership_state",
  "Top holder share >25% or holdings HHI elevated; overhang risk.",
  req_attrs=["top1_holder_pct", "holdings_concentration_hhi"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("passive_overhang_high", "Passive Overhang High", "ownership_state",
  "Passive / ETF ownership share elevated; index-driven flow risk.",
  req_attrs=["passive_ownership_pct", "etf_ownership_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("activist_presence_disclosed", "Activist Presence Disclosed", "ownership_state",
  "13D filed or known activist on the cap table.",
  req_attrs=["activist_present_flag"], req_events=["activist_13d_filed"],
  profile_trans=[
      {"profile_id": "activism_vulnerability_radar", "interpretation": "primary signal"},
  ])
I("fund_redemption_risk", "Fund Redemption Risk", "ownership_state",
  "Concentrated holdings by funds experiencing redemptions; forced-selling risk.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ],
  overrides={"confidence": "research_supported_experimental"})
I("analyst_coverage_thin", "Analyst Coverage Thin", "ownership_state",
  "Two or fewer analysts; revision signals less reliable.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "earnings_revision_momentum", "interpretation": "downgrade signal"},
  ])

# --- sentiment_state (8) ---
I("overreaction_detected", "Overreaction Detected", "sentiment_state",
  "Post-news abnormal-return reversal pattern detected.",
  req_attrs=["abnormal_return_event_window_3d"], req_events=["news_sentiment_shift_negative", "news_sentiment_shift_positive"],
  profile_trans=[
      {"profile_id": "event_risk_monitor", "interpretation": "primary signal"},
  ])
I("underreaction_detected", "Underreaction Detected", "sentiment_state",
  "Post-earnings drift pattern indicating slow incorporation of news.",
  req_attrs=["abnormal_return_event_window_3d"], req_events=["earnings_surprise_positive", "earnings_surprise_negative"],
  profile_trans=[
      {"profile_id": "post_earnings_drift_radar", "interpretation": "primary signal"},
      {"profile_id": "earnings_revision_momentum", "interpretation": "confirmation"},
  ])
I("investor_inattention_setup", "Investor Inattention Setup", "sentiment_state",
  "Low news coverage + thin analyst attention; mispricing window.",
  req_attrs=["news_sentiment_count_30d"], req_events=[],
  profile_trans=[
      {"profile_id": "post_earnings_drift_radar", "interpretation": "primary signal"},
      {"profile_id": "earnings_revision_momentum", "interpretation": "confirmation"},
  ])
I("narrative_shift_constructive", "Narrative Shift (Constructive)", "sentiment_state",
  "News + transcripts polarity turn materially positive.",
  req_attrs=["news_sentiment_score", "news_polarity_lm_pos"], req_events=["news_sentiment_shift_positive"],
  profile_trans=[
      {"profile_id": "event_risk_monitor", "interpretation": "confirmation"},
  ])
I("narrative_shift_negative", "Narrative Shift (Negative)", "sentiment_state",
  "News + transcripts polarity turn materially negative.",
  req_attrs=["news_sentiment_score", "news_polarity_lm_neg"], req_events=["news_sentiment_shift_negative"],
  profile_trans=[
      {"profile_id": "event_risk_monitor", "interpretation": "primary signal"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
  ])
I("crowded_narrative_warning", "Crowded Narrative Warning", "sentiment_state",
  "Narrative concentration + premium valuation + crowded ownership.",
  req_attrs=["peer_multiple_zscore", "transient_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "valuation_trap_detector", "interpretation": "supports trap warning"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ],
  overrides={"confidence": "research_supported_experimental"})
I("manipulation_risk_warning", "Manipulation Risk Warning", "sentiment_state",
  "Pump-and-dump / coordinated posting pattern detected; human review mandatory.",
  req_attrs=["manipulation_alert_flag"], req_events=["meme_stock_alert"],
  profile_trans=[
      {"profile_id": "event_risk_monitor", "interpretation": "blocking gate"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "blocking gate (legal)"},
  ],
  overrides={"human_review": True, "confidence": "research_supported_experimental"})
I("meme_stock_risk_warning", "Meme Stock Risk Warning", "sentiment_state",
  "Composite of abnormal social + abnormal volume + abnormal short interest.",
  req_attrs=["meme_stock_alert_flag", "short_interest_pct_float"], req_events=["meme_stock_alert"],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "risk flag"},
  ],
  overrides={"human_review": True, "confidence": "research_supported_experimental"})

# --- macro_state (10) ---
I("recession_regime_overlay", "Recession Regime Overlay", "macro_state",
  "Macro classifier indicates recession regime; downgrade cyclical sizing.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "macro_regime_equity_selector", "interpretation": "primary signal"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("late_cycle_overlay", "Late Cycle Overlay", "macro_state",
  "Late-cycle regime indicators triggered (yield curve, leading indicators).",
  req_attrs=["ust_2s10s_bps", "ism_manufacturing_pmi"], req_events=[],
  profile_trans=[
      {"profile_id": "macro_regime_equity_selector", "interpretation": "primary signal"},
  ])
I("rate_shock_overlay", "Rate Shock Overlay", "macro_state",
  "Material rate move; duration-sensitive equities at risk.",
  req_attrs=["ust_10y"], req_events=["fomc_decision"],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
      {"profile_id": "dividend_sustainability_radar", "interpretation": "risk flag"},
  ])
I("credit_widening_overlay", "Credit Widening Overlay", "macro_state",
  "HY OAS widening + leverage on focal name elevated.",
  req_attrs=["hy_oas_bps", "net_debt_to_ebitda_ttm"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supporting signal"},
  ])
I("inflation_pricing_power_signal", "Inflation Pricing Power Signal", "macro_state",
  "Inflation regime + firm pricing power supports margin durability.",
  req_attrs=["core_cpi_yoy"], req_events=["cpi_release"],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "confirmation"},
      {"profile_id": "macro_regime_equity_selector", "interpretation": "primary signal"},
  ])
I("fx_translation_warning", "FX Translation Warning", "macro_state",
  "Material FX translation exposure exposed by USD move.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("commodity_input_warning", "Commodity Input Warning", "macro_state",
  "Material commodity input exposure exposed by commodity move.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("sector_cycle_fit_match", "Sector Cycle Fit Match", "macro_state",
  "Sector aligns with macro regime per Ilmanen-style cycle map.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "macro_regime_equity_selector", "interpretation": "primary signal"},
  ])
I("sector_cycle_fit_mismatch", "Sector Cycle Fit Mismatch", "macro_state",
  "Sector misaligned with macro regime; cyclical risk.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "macro_regime_equity_selector", "interpretation": "risk flag"},
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("policy_event_pending", "Policy Event Pending", "macro_state",
  "Material policy event scheduled in the next 30 days.",
  req_attrs=[], req_events=["fomc_decision", "ecb_decision", "boj_decision"],
  profile_trans=[
      {"profile_id": "event_risk_monitor", "interpretation": "primary signal"},
      {"profile_id": "macro_regime_equity_selector", "interpretation": "primary signal"},
  ])

# --- short_state (10) ---
I("overvaluation_with_deterioration_pattern", "Overvaluation + Deterioration Pattern", "short_state",
  "Premium valuation + fundamental deterioration composite.",
  req_attrs=["peer_multiple_zscore", "revenue_growth_yoy_q"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
  ])
I("distress_risk_elevated", "Distress Risk Elevated", "short_state",
  "Composite distress score (Altman/Ohlson/Merton/CHS) in distress zone.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
      {"profile_id": "valuation_trap_detector", "interpretation": "supporting signal"},
  ])
I("fraud_risk_flag", "Fraud Risk Flag", "short_state",
  "Accounting red flags + governance failures + disclosure-quality concerns. LEGAL REVIEW MANDATORY.",
  req_attrs=["beneish_m_score", "sloan_accruals_zscore"], req_events=["restatement_downgrade"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal (legal-sensitive)"},
  ],
  overrides={"human_review": True, "confidence": "research_supported_experimental"})
I("borrow_unavailable", "Borrow Unavailable", "short_state",
  "Hard-to-borrow or unavailable; short candidate blocked.",
  req_attrs=["borrow_availability_status", "borrow_fee_bps"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "blocking gate"},
  ])
I("short_thesis_invalidation_trigger_observed", "Short Thesis Invalidation Triggered", "short_state",
  "Material invalidation event for short thesis (cover trigger).",
  req_attrs=[], req_events=["earnings_beat_with_guidance_raise", "buyback_authorized"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "invalidation"},
  ])
I("governance_red_flag_severe", "Governance Red Flag (Severe)", "short_state",
  "Material weakness OR going-concern OR auditor change in last 24 months.",
  req_attrs=["material_weakness_flag", "going_concern_flag"], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "blocking gate"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
  ],
  overrides={"human_review": True})
I("disclosure_quality_warning", "Disclosure Quality Warning", "short_state",
  "Vague segment reporting, delayed filings, promotional management language.",
  req_attrs=[], req_events=["late_filing_warning"],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
  ])
I("auditor_change_warning", "Auditor Change Warning", "short_state",
  "Auditor change within last 24 months; governance + accounting risk.",
  req_attrs=["auditor_change_recent_flag"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
      {"profile_id": "quality_value_long_only", "interpretation": "risk flag"},
  ])
I("material_weakness_warning", "Material Weakness Warning", "short_state",
  "SOX 404 material-weakness disclosure.",
  req_attrs=["material_weakness_flag"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
      {"profile_id": "quality_value_long_only", "interpretation": "blocking gate"},
  ],
  overrides={"human_review": True})
I("going_concern_warning", "Going Concern Warning", "short_state",
  "Auditor going-concern opinion present.",
  req_attrs=["going_concern_flag"], req_events=[],
  profile_trans=[
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
      {"profile_id": "quality_value_long_only", "interpretation": "blocking gate"},
  ],
  overrides={"human_review": True})

# --- portfolio_state (10) ---
I("position_concentration_warning", "Position Concentration Warning", "portfolio_state",
  "Position weight at or above max_position_pct.",
  req_attrs=["position_weight"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "blocking gate"},
  ])
I("sector_concentration_warning", "Sector Concentration Warning", "portfolio_state",
  "Sector weight at or above max_sector_pct.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "blocking gate"},
  ])
I("liquidity_capacity_warning", "Liquidity Capacity Warning", "portfolio_state",
  "Days-to-unwind exceeds profile threshold.",
  req_attrs=["days_to_unwind_at_20pct_adv_portfolio"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "blocking gate"},
  ])
I("factor_overexposure_warning", "Factor Overexposure Warning", "portfolio_state",
  "Portfolio factor exposure > 2 std relative to mandate.",
  req_attrs=["factor_exposure_total"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "primary signal"},
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "risk flag"},
  ])
I("tracking_error_breach", "Tracking Error Breach", "portfolio_state",
  "Tracking error exceeds budget.",
  req_attrs=["tracking_error_total_bps"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "primary signal"},
  ])
I("factor_diversification_low", "Factor Diversification Low", "portfolio_state",
  "Effective number of bets below diversification threshold.",
  req_attrs=["effective_number_of_bets"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "risk flag"},
  ])
I("hedge_recommendation", "Hedge Recommendation", "portfolio_state",
  "Exposure quantified; hedge candidate with cost-vs-alpha gate.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "primary signal"},
  ])
I("rebalance_recommendation", "Rebalance Recommendation", "portfolio_state",
  "Threshold breach + favorable cost vs expected alpha.",
  req_attrs=["expected_alpha_bps", "expected_cost_bps"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "primary signal"},
  ])
I("drawdown_risk_elevated", "Drawdown Risk Elevated", "portfolio_state",
  "Stress / drawdown simulation indicates elevated downside.",
  req_attrs=["drawdown_historical_max_pct", "cvar95_pct"], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "primary signal"},
  ])
I("exit_rule_triggered", "Exit Rule Triggered", "portfolio_state",
  "Profile exit rule triggered (thesis broken / invalidation / drawdown threshold).",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "primary signal"},
      {"profile_id": "quality_value_long_only", "interpretation": "primary signal"},
  ])

# --- decision_state (8) ---
I("thesis_supported", "Thesis Supported", "decision_state",
  "Evidence supports stated thesis; no major contradictions.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "neutral evidence"},
  ])
I("thesis_partially_supported", "Thesis Partially Supported", "decision_state",
  "Mixed evidence; some claims supported, others contradicted.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "downgrade signal"},
  ])
I("thesis_contradicted", "Thesis Contradicted", "decision_state",
  "Material contradictory evidence accumulated.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "primary signal"},
  ])
I("thesis_invalidated", "Thesis Invalidated", "decision_state",
  "Invalidation condition triggered.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "primary signal"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "primary signal"},
  ])
I("signal_without_confirmation", "Signal Without Confirmation", "decision_state",
  "Primary signal observed but required confirmation missing.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "rsi_swing_catalyst_confirmation", "interpretation": "downgrade to watch"},
  ])
I("catalyst_without_confirmation", "Catalyst Without Confirmation", "decision_state",
  "Catalyst observed but required confirmation missing.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "merger_arbitrage_watchlist", "interpretation": "downgrade to watch"},
  ])
I("risk_gate_blocks_action", "Risk Gate Blocks Action", "decision_state",
  "One or more risk gates failed; action blocked.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "blocking gate"},
  ])
I("action_downgraded_to_watch", "Action Downgraded to Watch", "decision_state",
  "Conditions not yet sufficient for full action; profile downgrades to watch.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "rsi_swing_catalyst_confirmation", "interpretation": "primary action"},
  ])

# --- validation_state, rights_state, pit_state (10) ---
I("validation_warning", "Validation Warning", "validation_state",
  "One or more validation domains flagged warnings.",
  req_attrs=["data_quality_warning_count"], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "downgrade signal"},
  ])
I("validation_blocked", "Validation Blocked", "validation_state",
  "Validation gate failed at error/block severity; promotion blocked.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "blocking gate"},
  ])
I("statistical_validation_pass", "Statistical Validation Pass", "validation_state",
  "Deflated Sharpe + walk-forward + cost-aware backtest passed.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "confirmation"},
  ])
I("rights_restriction_blocks_export", "Rights Restriction Blocks Export", "rights_state",
  "Restricted source evidence detected; export blocked / redaction required.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "blocking gate (export)"},
  ])
I("marketplace_draft_redaction_required", "Marketplace Draft Redaction Required", "rights_state",
  "Restricted evidence present in package; redaction required for marketplace_draft.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "blocking gate (marketplace)"},
  ])
I("license_missing_for_connector", "License Missing for Connector", "rights_state",
  "Production-required connector running without confirmed credential.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "portfolio_risk_radar", "interpretation": "blocking gate"},
  ])
I("pit_warning_blocks_backtest", "PIT Warning Blocks Backtest", "pit_state",
  "Inputs lack vintaged source; backtest cannot be marked PIT-safe.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "blocking gate"},
  ])
I("lookahead_risk_elevated", "Lookahead Risk Elevated", "pit_state",
  "Lookahead risk elevated for one or more scoring inputs.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "risk flag"},
  ])
I("vintage_unavailable_warning", "Vintage Unavailable Warning", "pit_state",
  "Vintaged data required but current connector ingest is latest-only.",
  req_attrs=[], req_events=[],
  profile_trans=[
      {"profile_id": "macro_regime_equity_selector", "interpretation": "downgrade signal"},
      {"profile_id": "factor_neutral_quantamental_selector", "interpretation": "downgrade signal"},
  ])
I("restatement_revintage_required", "Restatement Re-Vintage Required", "pit_state",
  "Filed amendment requires re-vintaging dependent attributes.",
  req_attrs=["restatement_flag"], req_events=["restatement_downgrade"],
  profile_trans=[
      {"profile_id": "quality_value_long_only", "interpretation": "downgrade signal"},
      {"profile_id": "short_red_flag_monitor", "interpretation": "supports short thesis"},
  ])


# ---------- BUILDERS ----------
def build_event(eid, name, family, desc, overrides):
    f = EFAM[family]
    materiality = overrides.get("materiality_default", f["materiality_default"])
    confidence = overrides.get("confidence", f["confidence"])
    horizon = overrides.get("horizon_hint", f["horizon_hint"])
    direction_hint_rules = overrides.get("direction_hint_rules", [
        "profile_dependent: see compatible_strategy_profiles for interpretation",
        "rumor_status_requires_unverified_flag",
    ])
    risk_factors = overrides.get("risk_factors", [
        "rumor_credibility_below_3",
        "binary_event_sizing_required" if "fda" in eid or "pdufa" in eid else "event_clock_management",
        "source_credibility_drift",
    ])
    materiality_rules = [
        "abnormal_return_event_window_3d_brown_warner",
        "earnings_impact_estimate_required_when_consensus_available",
        "regulator_severity_classification_when_applicable",
    ]
    if "rumor" in eid:
        materiality_rules.append("rumor_max_materiality_capped_at_medium_unless_triangulated")
    src_cred_rules = [
        "credibility_5_for_filings_and_regulator_releases",
        "credibility_4_for_company_press_releases_and_major_wires",
        "credibility_3_for_single_source_news",
        "credibility_2_for_unverified_wire_or_blue_check_social",
        "credibility_1_for_anonymous_social_or_rumor",
    ]
    if "rumor" in eid:
        src_cred_rules.append("rumor_max_action_is_watch_or_alert_only_never_auto_action")
    invalidation_templates = overrides.get("invalidation_templates", [
        "event_credibility_falls_below_threshold",
        "event_status_changes_to_failed_or_cancelled",
        "event_clock_expires_without_confirmation",
    ])
    if eid.startswith("mna_"):
        invalidation_templates += ["deal_break_event", "terms_renegotiated_unfavorably"]
    if family == "fda_clinical":
        invalidation_templates += ["complete_response_letter_received", "advisory_committee_negative_vote"]
    record = {
        "id": eid,
        "display_name": name,
        "description": desc,
        "module_id": "viza.finance.equity_investment",
        "schema_version": "v1",
        "object_family": "event_type",
        "source_sections": list(f["sections"]),
        "source_ids": list(f["sources"]),
        "confidence_label": confidence,
        "status": "registry-seedable",
        "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
        "core_primitive": "event",
        "extends_core_primitive": "transform",
        "compatible_entity_types": ["event", "equity_security", "company"],
        "compatible_strategy_profiles": list(f["profiles"]),
        "evidence_requirements": [
            {"evidence_type": "event_source_record", "required": True, "source_quality_minimum": min(5, max(3, f["default_source_credibility"]))},
        ],
        "audit_requirements": ["source_refs", "pit_timestamps", "rights_state"],
        "source_quality_minimum": min(5, max(3, f["default_source_credibility"])),
        "human_review_required": overrides.get("human_review", False),
        "pit": deepcopy(f["pit"]),
        "rights": deepcopy(f["rights"]),
        "validation_rules": [
            "event_type_must_be_in_registry",
            "event_must_carry_credibility_score",
            "event_must_carry_materiality_assessment",
            "event_must_carry_pit_and_rights_fields",
        ] + (["rumor_must_carry_unverified_flag"] if "rumor" in eid or family in ("mna_rumor", "social_sentiment_spike") else []),
        "failure_modes": [
            "rumor_treated_as_confirmed_event" if family in ("mna_rumor", "social_sentiment_spike") else "event_used_before_available_at",
            "materiality_assumed_without_evidence",
            "provider_load_time_used_as_available_at",
        ],
        "downgrade_conditions": [
            {"condition": "credibility_below_3", "from_label": confidence, "to_label": "practitioner_observed" if confidence != "research_supported_experimental" else "research_supported_experimental"},
        ],
        "rejection_conditions": [],
        "family_specific": {
            "event_family": family,
            "source_origin": f["source_origin"],
            "default_source_credibility": f["default_source_credibility"],
            "materiality_default": materiality,
            "observed_at_policy": f["pit"]["observed_at_policy"],
            "available_at_policy": f["pit"]["available_at_policy"],
            "source_types": list(f["connector_roles"]),
            "related_entity_types": list(f["related_entity_types"]),
            "source_credibility_rules": src_cred_rules,
            "materiality_rules": materiality_rules,
            "direction_hint_rules": direction_hint_rules,
            "horizon_hint": horizon,
            "risk_factors": risk_factors,
            "monitoring_triggers": overrides.get("monitoring_triggers", ["credibility_change", "materiality_change", "event_status_change"]),
            "invalidation_templates": invalidation_templates,
            "event_type_id": eid,
        },
    }
    return record


def build_insight(iid, name, family, desc, req_attrs, req_events, opt_conf, profile_trans, overrides):
    f = IFAM[family]
    confidence = overrides.get("confidence", f["confidence"])
    human_review = overrides.get("human_review", f["human_review"])
    profiles = list(f["profiles"])
    # Ensure each profile_trans entry has a known profile_id we list as compatible:
    for p in profile_trans:
        if p["profile_id"] not in profiles:
            profiles.append(p["profile_id"])
    record = {
        "id": iid,
        "display_name": name,
        "description": desc,
        "module_id": "viza.finance.equity_investment",
        "schema_version": "v1",
        "object_family": "insight_type",
        "source_sections": list(f["sections"]),
        "source_ids": list(f["sources"]),
        "confidence_label": confidence,
        "status": "registry-seedable",
        "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
        "core_primitive": "score",
        "extends_core_primitive": "score",
        "compatible_entity_types": ["equity_security", "company", "thesis", "decision"],
        "compatible_strategy_profiles": profiles,
        "candidate_attribute_keys": list(req_attrs),
        "candidate_event_types": list(req_events),
        "evidence_requirements": [
            {"evidence_type": "supporting_attribute_or_event", "required": True, "source_quality_minimum": 3},
        ],
        "audit_requirements": ["source_refs", "strategy_profile_hash", "validation_record_ids"],
        "source_quality_minimum": 3 if confidence == "research_supported_experimental" else 4,
        "human_review_required": human_review,
        "pit": deepcopy(f["pit"]),
        "rights": deepcopy(f["rights"]),
        "validation_rules": [
            "insight_must_link_to_evidence_refs",
            "insight_must_carry_strategy_profile_id_when_emitted",
            "profile_dependent_insights_must_list_per_profile_translation",
        ] + (["short_thesis_insights_require_legal_review_if_classified"] if family == "short_state" else [])
          + (["manipulation_state_insight_requires_human_review"] if "manipulation" in iid else []),
        "failure_modes": [
            "insight_emitted_without_evidence",
            "profile_translation_missing",
            "rumor_or_unverified_evidence_treated_as_confirmed",
        ],
        "downgrade_conditions": [
            {"condition": "evidence_below_source_quality_minimum", "from_label": confidence, "to_label": "research_supported_experimental"},
        ],
        "rejection_conditions": [],
        "family_specific": {
            "insight_family": family,
            "direction_logic": f["direction_logic"],
            "translation_rules": {"per_profile_translation": profile_trans or [{"profile_id": profiles[0] if profiles else "portfolio_risk_radar", "interpretation": "neutral evidence"}]},
            "invalidation_templates": [
                "underlying_evidence_revoked_or_revised",
                "thesis_invalidation_condition_triggered",
            ] + (["restatement_revintage_triggered"] if family in ("fundamental_state", "valuation_state", "short_state") else []),
            "confirmation_templates": opt_conf or [],
            "non_advice_boundary_required": f["non_advice"],
            "required_attributes": list(req_attrs),
            "required_events": list(req_events),
            "optional_confirmations": list(opt_conf or []),
            "confidence_logic": overrides.get("confidence_logic", "downgrade_when_evidence_below_source_quality_minimum_or_pit_warning"),
            "horizon_defaults": overrides.get("horizon_defaults", f["horizon"]),
            "risk_factors": overrides.get("risk_factors", ["evidence_revision_risk", "pit_warning_propagation"]),
            "output_templates": overrides.get("output_templates", ["equity_radar_renderer", "investment_memo_renderer_output", "risk_dashboard_renderer"]),
            "insight_type_key": iid,
        },
    }
    return record


# ---------- BUILD + WRITE ----------
event_records = []
seen_e = set()
for eid, name, fam, desc, ovr in EVENT_SPECS:
    if eid in seen_e:
        raise SystemExit(f"duplicate event id: {eid}")
    seen_e.add(eid)
    event_records.append(build_event(eid, name, fam, desc, ovr))

insight_records = []
seen_i = set()
for iid, name, fam, desc, ra, re_, oc, pt, ovr in INSIGHT_SPECS:
    if iid in seen_i:
        raise SystemExit(f"duplicate insight id: {iid}")
    seen_i.add(iid)
    insight_records.append(build_insight(iid, name, fam, desc, ra, re_, oc, pt, ovr))

OUT_EVT = Path("C:/Users/gkwls/AAT/docs/equity_module/v0.1/registries/equity_event_registry_seed.json")
OUT_INS = Path("C:/Users/gkwls/AAT/docs/equity_module/v0.1/registries/equity_insight_registry_seed.json")

evt_doc = {
    "$schema": "../equity_registry_shared_metadata.schema.json",
    "registry_name": "equity_event_registry_seed",
    "module_id": "viza.finance.equity_investment",
    "module_version": "0.1.0",
    "registry_version": "v1",
    "baseline": "Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening",
    "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
    "notes": "Event-type records. Each record conforms to docs/equity_module/v0.1/equity_registry_shared_metadata.schema.json (object_family=event_type). Rumor-class events (mna_rumor, social_sentiment_spike) carry mandatory unverified_flag handling and max-action=watch/alert_only.",
    "records": event_records,
}
ins_doc = {
    "$schema": "../equity_registry_shared_metadata.schema.json",
    "registry_name": "equity_insight_registry_seed",
    "module_id": "viza.finance.equity_investment",
    "module_version": "0.1.0",
    "registry_version": "v1",
    "baseline": "Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening",
    "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
    "notes": "Insight-type records. Each record conforms to docs/equity_module/v0.1/equity_registry_shared_metadata.schema.json (object_family=insight_type). Every insight carries invalidation_templates (>=1) + per-profile translation (>=1) + output_templates. Sentiment/social/short/fraud insights ship at research_supported_experimental and require human review.",
    "records": insight_records,
}

OUT_EVT.write_text(json.dumps(evt_doc, indent=2, ensure_ascii=False), encoding="utf-8")
OUT_INS.write_text(json.dumps(ins_doc, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(event_records)} event records to {OUT_EVT}")
print(f"wrote {len(insight_records)} insight records to {OUT_INS}")
