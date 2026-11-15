# Look-Ahead Audit Suite

This suite is intentionally separate from ordinary unit tests. It checks the project invariants that prevent future information from entering historical attribution runs.

Current probes:

- Feature-like database tables expose `event_time`, `ingestion_time`, and `timestamp_available`.
- Future-available price bars are excluded from deterministic return accounting.
- Future-available factor inputs are excluded from attribution.
- Replay audit helpers detect future-available contribution evidence payloads.

Later MVP hardening should run replay audits against persisted historical attribution runs from a real backfill sample.
