# SEC/FMP/FRED Runtime Wedge Report

Date: 2026-05-14

Status: feature-flagged runtime wedge, manifest-loadable, profile-compatibility-tested with mocks, PIT-labeled, rights-redaction-previewed, not production-hardened.

## Implementation

- Added `viza/equity/config.py` for default-off feature flags and runtime config.
- Added `viza/equity/connectors.py` for small SEC public, FMP market snapshot, and FRED macro context wrappers with cache, retry/backoff, and request pacing.
- Added `viza/equity/runtime.py` for the SEC public quality-value first-wedge handlers and output previews.
- Added `viza/modules/equity_investment.py` and gated module registration in `viza/modules/registry.py`.
- Added `tests/unit/test_equity_runtime_wedge.py` with offline mock coverage.
- Updated `env.example` with the default-off equity runtime flags and connector limits.

## Feature flags

Defaults are off:

- `VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED=false`
- `VIZA_EQUITY_SEC_WEDGE_ENABLED=false`
- `VIZA_EQUITY_FMP_ENABLED=false`
- `VIZA_EQUITY_FRED_ENABLED=false`
- `VIZA_EQUITY_LIVE_INTEGRATION_TESTS=false`

When `VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED=true`, the equity module builder validates the generated v0.1 registries before adding `viza.finance.equity_investment` to the module registry.

## Connector posture

SEC is the primary evidence source. The runtime sends a configured User-Agent, pads CIK values to 10 digits, applies a maximum 5 rps default cap, caches repeated requests, and uses mocked responses in unit tests.

FMP is optional. If disabled, no calls are made. If enabled without `FMP_API_KEY`, the runtime returns a warning and no observations. If enabled with a key, runtime outputs do not serialize the key. Unless `FMP_PRODUCTION_LICENSE_CONFIRMED=true`, FMP observations are labeled `dev_only_unconfirmed`, `export_policy=blocked`, `marketplace_policy=redacted`, and `production_scoring_eligible=false`.

FRED is optional. If disabled, no calls are made. If enabled without `FRED_API_KEY`, the runtime returns a warning and no observations. Current FRED pulls are labeled latest-only/ingestion-timestamped and `PIT_safe=false` unless a future vintage-aware cutoff path is implemented and tested.

## Profile and outputs

The runtime implements `quality_value_long_only` compatibility only. It checks CIK-backed identity, SEC evidence, basic fundamentals, PIT labels, rights labels, optional FMP market snapshot, optional FRED macro context, output availability, and the non-advice boundary.

Output previews include:

- `equity_radar`
- `validation_report`
- `source_rights_report`
- `package_redaction_preview`

Outputs are research previews only. They do not emit personal investment advice, buy/sell instructions, guaranteed alpha claims, or adviser claims.

## Package redaction preview

Preview modes:

- `white_box`: may include public SEC metadata/derived values and dev-local FMP warnings.
- `output_only`: includes output summary and proof state; FMP dev-only values are redacted.
- `marketplace_draft`: non-monetized, redacts or blocks restricted, unknown, private, or unconfirmed-license data.

SEC public official data is metadata/derived allowed. FMP dev-only data blocks marketplace draft. FRED current macro data carries a PIT warning and is not promoted to historical backtest proof.

## Known limitations

- No live integration tests were added to default CI; live calls remain opt-in through `VIZA_EQUITY_LIVE_INTEGRATION_TESTS=true`.
- No full DCF, analyst estimates, transcripts, options, borrow, social/news, or trading workflow was implemented.
- Ticker input is accepted only as an alias; durable runtime identity is CIK-backed. Unresolved ticker-only input fails closed for SEC evidence.
- FRED vintage metadata is not enough by itself for true PIT macro backtesting; decision-cutoff enforcement remains future work.
- FMP redistribution/display rights remain unconfirmed unless separately reviewed and `FMP_PRODUCTION_LICENSE_CONFIRMED=true`.

## Verification

- `python -m pytest tests\unit\test_equity_runtime_wedge.py -q`: `12 passed in 5.60s`.
- `python -m pytest tests\unit\test_equity_runtime_wedge.py tests\unit\test_equity_module_loader.py tests\unit\test_equity_module_fixtures.py -q`: `22 passed in 5.95s`.
- `python -m pytest tests\unit tests\lookahead_audit`: `325 passed in 136.14s`.
- `node --test tests\dashboard\attribution-period-bars.test.mjs`: `2 passed in 117.4326ms`; Node emitted the existing `MODULE_TYPELESS_PACKAGE_JSON` warning.
- `npm run typecheck` in `apps\viza-desktop`: passed.
- `npm run test:desktop` in `apps\viza-desktop`: `18 passed in 109.6645ms`.
- `npx tsc --noEmit --project tsconfig.json` in `dashboard`: passed.
