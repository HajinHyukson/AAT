# Equity Confidence Recalibration Report

Result: no `high_confidence_core` object is promoted to production-hardened. All v0.1 artifacts remain registry-seedable until full runtime integration, legal/source-rights review, and connector entitlement review complete.

Downgrades applied or preserved:

- Licensed-data-dependent identity and provider records remain `common_practice` or `research_supported_experimental` where no entitlement exists.
- Sentiment, social, rumor, and text-derived records remain experimental or blocked for action unless credibility/manipulation guards pass.
- AAT/factor/macro objects that need true vintages remain warning-bearing and are not backtest-safe until ALFRED-style vintages exist.
- Short-interest nodes now require human review and EQ-VAL-008 gates.

Registry-seedable means the artifact can load and validate. Implementation-ready requires runtime handlers and integrated validation execution. Production-hardened requires a separate production, legal/source-rights, entitlement, and runtime review cycle.
