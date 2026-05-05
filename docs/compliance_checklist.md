# Compliance Checklist

Before any pilot or production run:

- `.env` is not committed.
- No unlicensed production adapter is enabled.
- Every attribution feature has `event_time`, `ingestion_time`, and `timestamp_available`.
- Backtests filter on `timestamp_available <= attribution_cutoff`.
- Every output includes `unexplained_residual`.
- Narrative generation, once implemented, uses only structured engine output.
