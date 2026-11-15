# Runtime Wedge Repo Map

Date: 2026-05-14

Module: `viza.finance.equity_investment v0.1`

## Files inspected

- `config/env.py`
- `viza/credentials.py`
- `viza/connectors.py`
- `adapters/sec_edgar/client.py`
- `adapters/fmp/client.py`
- `adapters/fred/client.py`
- `viza/modules/registry.py`
- `viza/modules/core_strategy.py`
- `viza/modules/finance_securities.py`
- `viza/modules/models.py`
- `viza/file_format/export.py`
- `viza/file_format/packaging.py`
- `viza/file_format/models.py`
- `viza/marketplace.py`
- `viza/validation_ledger.py`
- `viza/equity/registry.py`
- `tests/unit/test_viza_real_estate_module.py`
- `tests/unit/test_viza_file_security.py`
- `tests/unit/test_viza_connectors.py`
- `tests/unit/test_equity_module_loader.py`
- `docs/equity_module/v0.1/registries/viza.finance.equity_investment.manifest.json`
- `docs/equity_module/v0.1/fixtures/first_wedge_sec_quality_value/fixture.json`
- `env.example`

## Config/env loading path

The repository uses `config.env.load_dotenv()` for local `.env` hydration and `viza.credentials.CredentialStore` / `EnvironmentCredentialStore` for credential presence checks without returning secrets in public schemas. The equity runtime config now lives in `viza/equity/config.py` and reads:

- feature flags from `os.environ`
- `.env` through `config.env.load_dotenv()`
- `FMP_API_KEY` through `CredentialStore.get_secret_for_runtime(..., env_var="FMP_API_KEY")`
- `FRED_API_KEY` through `CredentialStore.get_secret_for_runtime(..., env_var="FRED_API_KEY")`

Secret values are held only in runtime config fields marked `repr=False` and are not serialized by `masked_summary()`.

## Runtime handlers

Runtime handlers live in `viza/equity/runtime.py`. The smallest useful first-wedge surface is:

- `load_equity_module_manifest()`
- `load_equity_registries()`
- `resolve_equity_identity()`
- `resolve_sec_company()`
- `fetch_sec_submissions()`
- `fetch_sec_companyfacts()`
- `build_sec_filing_evidence_bundle()`
- `derive_sec_public_fundamental_attributes()`
- `fetch_fmp_market_snapshot_optional()`
- `fetch_fred_macro_context_optional()`
- `run_quality_value_profile_compatibility()`
- `render_equity_radar_preview()`
- `render_validation_report()`
- `render_source_rights_report()`
- `preview_package_redaction()`
- `run_sec_quality_value_wedge()`

The module registry builder lives in `viza/modules/equity_investment.py` and is wired into `viza/modules/registry.py` only when `VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED=true`.

## Module manifest loading

Generated artifacts remain under `docs/equity_module/v0.1/registries/`. The runtime loader reuses `viza.equity.registry.load_equity_module()` and requires the existing validator to pass before the feature-flagged runtime module is registered.

## Package preview/redaction logic

Existing `.viza` packaging and marketplace draft logic remains in:

- `viza/file_format/packaging.py`
- `viza/file_format/export.py`
- `viza/marketplace.py`
- `viza/file_format/models.py`

The equity wedge adds a preview-only policy function in `viza/equity/runtime.py` for `white_box`, `output_only`, and `marketplace_draft`. It does not redesign `.viza` and does not enable marketplace monetization.

## Tests added

Mocked runtime tests live in `tests/unit/test_equity_runtime_wedge.py`. They cover feature flags, manifest loading, invalid manifest fail-closed behavior, SEC CIK padding and mocked payload parsing, SEC evidence PIT/rights labels, FMP/FRED disabled and missing-key behavior, mocked FMP/FRED parsing, quality-value compatibility, output rendering, package-redaction preview, and API-key non-serialization.
