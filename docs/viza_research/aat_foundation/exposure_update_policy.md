# Exposure Update Policy

Exposure profiles describe structural business exposures. They should not update from one noisy trading day.

## MVP Policy

- Daily attribution can suggest candidate exposure changes.
- No automatic production exposure update ships in MVP.
- High-impact exposure changes require human review.
- Evidence should persist across multiple events or filings.

## Implemented Decision Logic

The MVP writes `exposure_update_decision` rows, not automatic profile mutations.

- `candidate_review`: a high-impact feature or persistent material features suggest a human should review the exposure profile.
- `no_update`: evidence is not material or persistent enough.

The implemented policy is intentionally conservative: even `candidate_review` does not update `company_exposure`.
