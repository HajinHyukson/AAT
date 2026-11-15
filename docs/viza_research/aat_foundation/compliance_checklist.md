# Compliance Checklist

Before any pilot or production run:

- `.env` is not committed.
- No unlicensed production adapter is enabled.
- Every attribution feature has `event_time`, `ingestion_time`, and `timestamp_available`.
- Backtests filter on `timestamp_available <= attribution_cutoff`.
- Every output includes `unexplained_residual`.
- Narrative generation uses only structured engine output.
- Event and style evidence rows remain evidence-only unless a calibrated production contribution method exists.
- During the live FaustCalc backfill, no server deployment requires schema, loader, or persisted-attribution contract changes unless the stop-backup-test-resume process is followed.
