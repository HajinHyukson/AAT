# Agent Start Here

Use this file at the beginning of a new coding-agent session. It tells you which VIZA docs are current, which docs are historical, and where generated artifact trees still live.

## Read First

1. [viza_end_product/VIZA_PRODUCT_SPEC.md](viza_end_product/VIZA_PRODUCT_SPEC.md) - current product direction.
2. [viza_changelog/implementationlog.md](viza_changelog/implementationlog.md) - factual implementation history and latest implemented baseline.
3. [viza_end_product/VIZA_KR_COMPLIANCE_REPORT.md](viza_end_product/VIZA_KR_COMPLIANCE_REPORT.md) - knowledge-representation compliance gaps and target discipline.
4. [viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md](viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md) - current command/compliance implementation plan.
5. [viza_end_product/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md](viza_end_product/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md) - decisions output plan and simulator framing.

## Current Baseline

- VIZA is beyond the original Phase 0-15 prototype.
- Phase 35 marketplace-readiness guardrails are implemented and verified in the changelog.
- The May 20 decisions docs and May 21 compliance/command docs are newer than the legacy product and prototype plans.
- Older Phase 0-15 docs are historical unless the changelog or current product docs explicitly point back to them.
- `VIZA_PRODUCT_SPEC_LEGACY.md` is not canonical; it is archived under `viza_research/legacy_plans/`.

## Folder Roles

- [viza_end_product/](viza_end_product/) contains intended direction, active product/compliance plans, release readiness, packaging, and compatibility posture.
- [viza_changelog/](viza_changelog/) contains implementation history and phase-delivery detail.
- [viza_research/](viza_research/) contains research logs, AAT background, and archived/legacy plans.

## Operational Artifact Trees

These remain at their original paths because packaging, scripts, and tests reference them:

- [equity_module/v0.1/](equity_module/v0.1/) - registry-loadable equity module artifacts, fixtures, reports, and proofs.
- [equity_high_confidence_upgrade/](equity_high_confidence_upgrade/) - generated high-confidence equity research upgrade package.

Top-level Markdown files with old names are compatibility pointers. Follow their links to the organized source files.
