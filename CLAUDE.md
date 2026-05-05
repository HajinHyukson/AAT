# Single-Stock Attribution Engine

This repo builds a research-grade single-stock attribution engine. The source of truth is `PROJECT_SPEC.md`; keep this file lean and link out to deeper docs.

## Project Rules

- Factor attribution runs before event attribution.
- Every feature-like row must carry `event_time`, `ingestion_time`, and `timestamp_available`.
- Backtests and attribution runs may only use rows with `timestamp_available <= attribution_cutoff`.
- Use immutable `company_id` and `security_id`; never use ticker as a primary key.
- Every attribution result reports `unexplained_residual`.
- Production must fail closed if a licensed adapter is enabled without credentials.

## Key Docs

- `PROJECT_SPEC.md` - product and engineering contract
- `SUBAGENTS.md` - specialist agent guide
- `ARCHITECTURE.md` - current implementation map
- `PROJECT_STATUS.md` - current status and next work
- `CHANGELOG.md` - append-only project changes
- `docs/attribution_methodology.md` - attribution math and reconciliation
- `docs/data_licensing.md` - adapter licensing policy
- `docs/exposure_update_policy.md` - exposure profile update rules
- `docs/compliance_checklist.md` - release and data-use checks
