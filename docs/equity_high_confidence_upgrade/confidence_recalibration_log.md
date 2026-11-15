# Confidence Recalibration Log

Status: accepted for Status 6.5. Labels are object-level and remain non-production unless runtime validation and legal/product review pass.

| object_id | old_label | new_label | reason_for_change | supporting_sources | gates |
|---|---|---|---|---|---|
| `factor.momentum` | `high_confidence_core` | `research_supported_experimental` | Strong academic support but production scoring still needs costs, turnover, capacity, and decay review. | EQ_SRC_A0011, EQ_SRC_A0066, EQ_SRC_A0067 | PIT, rights, validation, traceability |
| `factor.value` | `high_confidence_core` | `high_confidence_core` | Strong factor/risk descriptor with traceability and validation; production alpha use still profile-gated. | EQ_SRC_A0006, EQ_SRC_A0007, EQ_SRC_A0065 | PIT, rights, validation, traceability |
| `sentiment.news_score` | `research_supported_experimental` | `research_supported_experimental` | Academic support exists; text rights, model drift, and source credibility keep it experimental. | EQ_SRC_A0045, EQ_SRC_A0046, EQ_SRC_O0024 | PIT, rights, validation, traceability |
| `social.raw_signal` | `common_practice` | `rejected_or_deferred` | Rights, manipulation, and raw-text/platform uncertainty fail promotion gates. | EQ_SRC_O0024, EQ_SRC_O0025 | PIT, rights, validation, traceability |
| `valuation.DCF_model` | `common_practice` | `common_practice` | Professional standard; assumptions require sensitivity and cannot be treated as observed facts. | EQ_SRC_P0001, EQ_SRC_P0008 | PIT, rights, validation, traceability |
| `PIT.available_at_policy` | `high_confidence_core` | `high_confidence_core` | Official filing and vintage-source support; required validation rule attached. | EQ_SRC_O0001, EQ_SRC_O0016, EQ_SRC_O0017 | PIT, rights, validation, traceability |
| `rights.restrictive_policy_wins` | `high_confidence_core` | `high_confidence_core` | Conservative VIZA packaging rule supported by product baseline and rights matrices. | VIZA baseline, EQ_SRC_V0001-EQ_SRC_V0025 | PIT, rights, validation, traceability |
| `short.borrow_squeeze_gate` | `common_practice` | `common_practice` | Implementation-critical; production requires licensed borrow connector. | EQ_SRC_O0012, EQ_SRC_V0020, EQ_SRC_V0021 | PIT, rights, validation, traceability |
