# VIZA Equity Investment Module v0.1

Status: artifact-generated, registry-loadable, fixture-tested, feature-flag runtime-wired, packaged-preview integrated, preview-run persisted, replayable, package-preview/export ready, Windows packaged smoke-tested candidate.

This directory contains registry-seedable artifacts for `viza.finance.equity_investment`. The module provides equity decision grammar, entity/node/edge/attribute/event/insight registries, strategy profiles, output views, validation rules, PIT controls, and source-rights controls.

Architecture boundaries:

- `viza.core.strategy` remains domain-neutral.
- `viza.finance.securities` provides the security/finance substrate.
- `viza.aat.attribute_analysis` is optional/subordinate.
- `viza.finance.equity_investment` provides the equity decision layer and conservative package/redaction controls.

Production posture: this is not production-hardened. It is registry-seedable and loadable for engineering fixtures. Legal/source-rights review, connector entitlement review, and full runtime integration remain required before production promotion.

Non-advice boundary: outputs are research workflow artifacts and must not be rendered as personal investment advice, guaranteed alpha, or adviser activity.

Runtime wedge: `viza/equity/` includes a default-off SEC public first-wedge path with optional FMP market snapshot support and optional FRED macro context. SEC filings/XBRL are the primary evidence source. FMP is marked dev-only/export-blocked unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`. FRED macro context is latest-only/not true PIT for backtests unless ALFRED-style vintage cutoff enforcement is implemented and tested. Marketplace draft package previews redact restricted, unknown, private, or unconfirmed-license data and remain non-monetized.

Packaged desktop preview: the Windows Electron prototype can expose a default-off `Equity Runtime Wedge Preview` panel in the result sidebar. The panel calls the local FastAPI sidecar endpoint, uses the mocked SEC-first fixture by default, and renders target identity, SEC evidence, profile compatibility, PIT status, rights status, validation status, source-rights status, package-redaction preview, audit identifiers, and the non-advice boundary. The packaged build copies equity registries and the mock fixture into `resources/engine/docs/equity_module/v0.1`.

Persistence and replay: when `VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED=true`, preview runs can be saved into the existing local project SQLite store and linked to normalized observations in the existing observation store. Persisted runs include target identity, input, feature flags, connector modes, evidence bundle, PIT status, rights status, validation report, source-rights report, package-redaction preview, audit hashes, and proof checksum. Replay from stored observations is available without live connector calls. Replay with refresh is explicit and remains behind `VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED=true`.

MVP package/export flow: persisted preview runs can prepare local `.viza` draft packages through the existing VIZA container writer. The package-draft path supports `white_box`, `output_only`, and `marketplace_draft` modes, preserves proof checksum, PIT summary, rights summary, validation report, source-rights report, package-redaction preview, and the non-advice boundary. Marketplace draft remains non-monetized and redacts restricted, unclear, private, or unconfirmed-license data.

This preview is not a production equity workstation. Live SEC/FMP/FRED calls remain opt-in only, FMP production rights require legal/source-rights review, FRED true PIT backtesting requires ALFRED-style cutoff enforcement, ticker alias resolution remains non-primary-key, and no output should be read as personal investment advice.
