# VIZA Attribute Implementation Checklist

Use this checklist before promoting any Phase 13 attribute beyond deterministic prototype status.

## Required Metadata

- Attribute key, display name, family, unit, source, source type, and owner are defined.
- Contribution stage is one of research, evidence-only, shadow, production, or production contribution.
- Timestamp policy states whether the value uses `timestamp_available`, source event time, or latest snapshot semantics.
- License policy, entitlement policy, and cache policy are explicit.
- Model version and data version are stable and changed whenever resolver behavior or source inputs change.
- Limitations explain prototype status, source restrictions, and known comparability issues.

## Source And PIT Validation

- Source table or connector is documented.
- Every source row used for backtests has `timestamp_available`.
- Backtests filter source rows with `timestamp_available <= cutoff`.
- Resolver evidence includes source record ID, source timestamp, timestamp availability, and confidence.
- Point-in-time tests cover at least one visible row and one future/unavailable row.

## Resolver Promotion

- Research: deterministic or source-backed value is visible with limitations.
- Evidence-only: value can be displayed and exported only when entitlement allows it.
- Shadow: value can be computed in runs but should not drive production decisions yet.
- Production scoring: value is point-in-time safe, versioned, tested, and allowed by entitlement policy.
- Production contribution: contribution math, factor return, exposure, and residual handling are documented.

## Export And Compliance

- Raw values from restricted sources are redacted by `viza.exports`.
- Derived values are exportable only when `derived_value_allowed` and `export_allowed` are true.
- Public source exports retain attribution requirements in evidence and manifest metadata.
- User-supplied source exports do not include credentials or local filesystem secrets.
