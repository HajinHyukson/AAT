# Full High-Confidence Upgrade Gap Audit

Prepared: 2026-05-14
Baseline document: `docs/CODEX_EQUITY_MODULE.md`

## 1. Current Status Of The Completion Document

The existing Codex completion document is a Status 6 registry-ready seed. It contains the VIZA baseline, methodology, compact source corpus, Section 1-41 records, registry seeds, manifest/backlog proposals, and final acceptance notes. It does not yet expose a full source -> method -> object -> PIT -> rights -> validation -> confidence -> artifact -> fixture chain for every major object.

## 2. Already Sufficient For Status 6

- VIZA baseline and architecture boundaries are captured.
- Section 1-41 coverage exists.
- Candidate entities, nodes, attributes, events, insights, profiles, outputs, validation rules, manifest, and backlog are present as seeds.
- PIT and source-rights concepts are present as policy narrative.
- The launch sequence correctly says artifacts and fixtures are the next step.

## 3. Missing For Full High-Confidence Corpus Status

- Expanded source corpus with canonical metadata.
- Structured academic, professional, practitioner, official/filing, and vendor extraction records.
- Source-to-method-to-object traceability matrix.
- PIT matrix, rights matrix, method validation matrix.
- Confidence recalibration and rejection/downgrade log.
- Concrete JSON/CSV registry artifacts.
- Fixture and test plans that prove no lookahead or rights leakage conceptually.

## 4. Missing For Status 7 Implementation-Ready

- Runtime registry loader tests have not been executed.
- Fixtures have not been loaded through the VIZA module registry.
- PIT and redaction tests have not been run against packaged `.viza` files.
- Live connector entitlements and legal/product review remain incomplete.
- Statistical backtests and robustness work remain deferred.

## 5. Source-Class Gap Table

| Source class | Minimum target | Current seed | Upgrade package target | Status |
|---|---:|---:|---:|---|
| Academic papers | 80 | about 26 compact citations | 80 | minimum target reached in Stage A; strong target deferred |
| Professional methodology docs | 25 | about 8 compact citations | 25 | minimum target reached |
| Official/regulatory/primary docs | 25 | about 10 compact citations | 25 | minimum target reached before filing examples |
| Company filing examples | 50 | 0 structured examples | 50 | SEC submissions metadata examples generated |
| Practitioner memos/letters/decks | 40 | 2 compact citations | 40 | minimum target reached; extraction used for language/templates |
| Activist/short/special-situation reports | 25 | thin coverage | 25 | minimum target reached; not promoted to core |
| Vendor/data methodology docs | 25 | about 5 compact citations | 25 | minimum target reached; production rights still legal-review deferred |

## 6. Section-By-Section Extraction Gap Table

| Section | Current seed status | Extraction gap | Upgrade action |
|---|---|---|---|
| 1 | Status 6 seed | baseline/protocol; needs traceability to internal source evidence | preserve baseline and use as prior VIZA implementation source |
| 2 | Status 6 seed | baseline/protocol; needs traceability to internal source evidence | preserve baseline and use as prior VIZA implementation source |
| 3 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 4 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 5 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 6 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 7 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 8 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 9 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 10 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 11 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 12 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 13 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 14 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 15 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 16 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 17 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 18 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 19 | Status 6 seed | methods exist as prose/tables but need source-linked extraction rows | populate method table, mapping table, PIT/rights/validation matrices |
| 20 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 21 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 22 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 23 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 24 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 25 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 26 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 27 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 28 | Status 6 seed | registry seeds exist but are not concrete artifacts | generate JSON/CSV artifacts and traceability rows |
| 29 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 30 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 31 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 32 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 33 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 34 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 35 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 36 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 37 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 38 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 39 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 40 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |
| 41 | Status 6 seed | methodology controls exist but need handoff/checklist artifacts | generate final reports, acceptance rubric, fixture/test plans |

## 7. Artifact Gap Table

| Artifact | Baseline state | Upgrade action |
|---|---|---|
| `equity_source_corpus.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_source_corpus.md` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `academic_paper_extractions.jsonl` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `professional_method_extractions.jsonl` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `practitioner_method_extractions.jsonl` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `official_primary_source_extractions.jsonl` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `vendor_rights_source_extractions.jsonl` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_method_extraction_table.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_viza_mapping_table.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_research_traceability_matrix.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_saturation_map.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `rejection_and_downgrade_log.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `confidence_recalibration_log.md` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_PIT_matrix.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_source_rights_matrix.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_method_validation_matrix.csv` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `equity_validation_rules.json` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `registry artifacts` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `fixture package` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |
| `final report appendices` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |

## 8. PIT / Rights / Validation Gap Table

| Control | Current state | Required upgrade |
|---|---|---|
| PIT | narrative policy | data-type matrix with observed_at/available_at/retrieved_at and lookahead rules |
| Rights | narrative policy | data-type matrix with query/cache/display/export/redistribution/package behavior |
| Validation | seed rules | method validation matrix plus JSON validation rules |
| Confidence | section labels | object-level recalibration with downgrade log |
| Fixtures | launch idea | five fixture workflows with expected checks and conceptual test results |

## 9. Priority Work Plan For Stages A-E

| Stage | Deliverable | Gate result target |
|---|---|---|
| A | expanded source corpus and extraction JSONL files | accepted if minimum source targets reached or gaps documented |
| B | method extraction, mapping, traceability, rejection log | accepted if every major object has a traceability chain |
| C | PIT, rights, validation matrices and rules | accepted if no promoted object lacks controls |
| D | registry artifacts and manifest | accepted if IDs are unique and references resolvable at artifact level |
| E | fixture package and final report | partial unless runtime tests actually execute |

## 10. Acceptance Criteria For The Next Pass

- Source corpus reaches minimum target counts.
- Every source has canonical metadata.
- Every major method has extraction, mapping, PIT, rights, validation, confidence, and traceability.
- Registry artifacts are generated as files.
- Five fixtures specify inputs, graph path, checks, expected outputs, and failure cases.
- Final status is capped at 6.5 unless runtime tests are executed.

Stage result: accepted. Gap audit complete; proceed to Stage A.
