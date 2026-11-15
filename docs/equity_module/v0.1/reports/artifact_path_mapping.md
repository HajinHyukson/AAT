# Equity Module v0.1 Artifact Path Mapping

The generated v0.1 equity artifacts are loaded from `docs/equity_module/v0.1/registries/`.

| Requested artifact | Repository path | Notes |
|---|---|---|
| Shared metadata contract | `docs/equity_module/v0.1/schemas/shared_metadata_contract.md` | Root copy retained for compatibility. |
| Shared metadata schema | `docs/equity_module/v0.1/schemas/equity_registry_shared_metadata.schema.json` | Root copy retained for older links. |
| Module manifest | `docs/equity_module/v0.1/registries/viza.finance.equity_investment.manifest.json` | Root copy retained for compatibility. |
| Traceability matrix | `docs/equity_module/v0.1/registries/equity_research_traceability_matrix.csv` | Copied from expanded high-confidence corpus. |
| Downgrade log | `docs/equity_module/v0.1/registries/equity_rejection_and_downgrade_log.csv` | Copied from expanded high-confidence corpus and extended by recalibration report. |

The runtime loader is additive under `viza/equity/` and does not modify `viza.core.strategy`.
