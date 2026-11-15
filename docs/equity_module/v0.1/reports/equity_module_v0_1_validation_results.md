# Equity Module v0.1 Validation Results

Status: pass for registry-loadable v0.1 artifacts and fixtures. This does not claim production hardening.

Commands and exact results:

- `python -m pytest tests\unit\test_equity_module_loader.py tests\unit\test_equity_module_fixtures.py`
  - Result: `10 passed in 0.53s`.
- `python docs\equity_module\v0.1\fixtures\first_wedge_sec_quality_value\verify_fixture.py`
  - Result: all first-wedge acceptance checks passed.
- `python docs\equity_module\v0.1\fixtures\portfolio_risk_radar_pilot\verify_fixture.py`
  - Result: portfolio_risk_radar pilot passed.
- `python docs\equity_module\v0.1\fixtures\earnings_revision_momentum_pilot\verify_fixture.py`
  - Result: earnings_revision_momentum pilot passed.
- `python docs\equity_module\v0.1\fixtures\package_redaction_tests\verify_package_redaction.py`
  - Result: package + redaction test matrix passed.
- `python -m pytest tests\unit tests\lookahead_audit`
  - Result: `313 passed in 170.25s (0:02:50)`.
- `node --test tests\dashboard\attribution-period-bars.test.mjs`
  - Result: `2 passed`; Node emitted the existing module-type warning for `dashboard/components/attribution-period-bars.ts`.
- `cd apps\viza-desktop; npm run typecheck`
  - Result: passed.
- `cd apps\viza-desktop; npm run test:desktop`
  - Result: `18 passed`.
- `cd dashboard; npx tsc --noEmit --project tsconfig.json`
  - Result: passed.

PIT summary: SEC filing facts use accepted/available timestamps; fixture checks verify no input `available_at` exceeds the decision timestamp; macro/factor vintage limitations remain warnings until true vintage pipelines exist.
