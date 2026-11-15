# FinBERT Text Resolver — Repo Map (Stage A)

Last updated: 2026-05-16
Scope: Stage A of the `viza.finance.text.sentiment` resolver — foundation
(resolver interface, SEC iXBRL section parser, deterministic chunker, mocked
model, cache + replay, look-ahead audit gate). Stage B (real FinBERT), Stage C
(UI + packaging), and Stage D (active-scope prepopulation) are deferred to
subsequent commits.

## Backend files inspected

- `viza/__init__.py` — public API surface; new resolver is exposed via the
  equity subpackage, not pulled into the top-level VIZA namespace at this stage.
- `viza/equity/__init__.py` — equity module entry point; Stage A adds a new
  subpackage `viza/equity/text/` without touching this file.
- `viza/equity/config.py` — `EquityRuntimeConfig` dataclass + `from_env`
  pattern; new `EquityTextConfig` mirrors this pattern exactly so flag
  discipline is consistent.
- `viza/equity/runtime.py` — `run_sec_quality_value_wedge` and the SEC
  rights policy dict; Stage A reuses the rights policy shape and references
  the runtime conventions but does not call into the wedge.
- `viza/equity/preview.py`, `viza/equity/persistence.py` — packaged-preview
  surface and existing observation-persistence pattern; the new
  `SentimentObservationStore` follows the same SQLite-on-`project_store_path`
  convention.
- `viza/observations.py` — `VizaObservation` / `ObservationStore` for the
  generic `viza.observation.v1` schema; intentionally NOT extended with
  text-sentiment columns (the cache_key, chunk_id, model_governance columns
  belong in a dedicated table to keep the generic store unchanged).
- `viza/project_store.py` — `project_store_path()` helper used by every
  SQLite-backed VIZA component; the new table lives in the same file.
- `viza/equity/connectors.py` — `SecPublicClient` + `normalize_cik`; Stage C
  will wire this into the resolver so real filings replace
  `mock_parsed_sections`.
- `adapters/sec_edgar/client.py` — `fetch_submissions` for accession listings;
  reference for `acceptanceDateTime` precision handling (pin 4).
- `env.example` — feature-flag conventions (`VIZA_EQUITY_*`); new flags appended.

## Frontend files inspected

None modified in Stage A. The desktop UI surface (`apps/viza-desktop/src/`)
is Stage C scope.

## Existing patterns mirrored

- **Resolver / attribute registry pattern.** The existing module-registry
  approach (`viza/modules/`, `viza/equity/modules/equity_investment.py`)
  registers attribute and node families. Stage A registers the
  `viza.finance.text.sentiment` resolver under the same namespace convention.
  Full attribute-registry seed entries are deferred to Stage C alongside the
  UI palette additions to avoid surfacing attributes that have no UI yet.
- **Observation store pattern.** SQLite tables co-located in
  `project_store_path()` via additive `CREATE TABLE IF NOT EXISTS` statements.
  The Phase 16 baseline lock requires additive-only changes; new tables
  (`sec_text_sentiment_observations`, `_runs`, `_section_aggregates`,
  `_deltas`) satisfy that constraint without altering existing schemas.
- **Runtime/backfill pattern.** `attribution_backfill_task` advisory-lock +
  checkpoint plumbing is the reference implementation for Stage D's
  prepopulation jobs.
- **Package/redaction pattern.** `viza/equity/preview.py` and
  `viza/equity/package_redaction.py` define the white_box / output_only /
  marketplace_draft modes. Stage A surfaces the policy intent in the resolver
  response (`package_redaction_preview`); full redaction wiring is Stage C.
- **Validation/proof pattern.** `viza/equity/persistence.py` writes a
  `proof_checksum` for every persisted preview run. The sentiment resolver
  follows the same pattern: each `RunSnapshot` carries a checksum derived
  from observation/aggregate/delta IDs.
- **SEC adapter path.** The existing `adapters/sec_edgar/client.py` and
  `viza/equity/connectors.py:SecPublicClient` are the entry points; Stage A
  does not call them (mock-only) so flag-off behavior is byte-identical to
  the prior runtime.

## Chosen code paths (Stage A)

```
viza/equity/text/
├── __init__.py                    public exports
├── config.py                      EquityTextConfig (6 flags + runtime knobs, defaults off)
├── hashing.py                     pin-1 four-hash + cache_key, with key-set validation
├── human_review.py                pin-2 keyword pre-filter, frozen term set v1
├── release_dates.py               pin-5 MODEL_RELEASE_DATES table
├── types.py                       Pydantic models (Chunk, Observation, Aggregate, Delta, Request, Response, Snapshot, Ticket)
├── section_parser.py              pin-3 iXBRL extractor + 8-K item parser + pin-4 availability policy
├── chunker.py                     deterministic regex-sentence chunker
├── aggregation.py                 section aggregates + delta-vs-prior with metadata-match guard
├── persistence.py                 pin-6 cache_key + run_id store, four additive SQLite tables
├── resolver.py                    viza.finance.text.sentiment entry point; cold/hot/queued/replay paths
└── models/
    ├── __init__.py                ModelImplementation Protocol + registry
    └── mock_finbert.py            deterministic 3-class mock; same metadata shape as real models
```

## Chosen test files (Stage A)

```
tests/unit/test_equity_text_hashing.py            pin-1 byte-level guarantees + cache_key field sensitivity
tests/unit/test_equity_text_human_review.py       pin-2 term-set v1 + whitespace + case
tests/unit/test_equity_text_section_parser.py     pin-3 iXBRL extraction + pin-4 availability precision
tests/unit/test_equity_text_chunker.py            determinism + policy-hash invalidation
tests/unit/test_equity_text_resolver.py           happy path + retrospective label + human-review propagation
tests/unit/test_equity_text_cache_and_replay.py   pin-6: cache hit/miss, model bump, replay, replay cutoff
tests/unit/test_equity_text_aggregation.py        dispersion + negative-ratio + delta metadata-match
tests/unit/test_equity_text_feature_flags.py      defaults off + disabled response shape
tests/lookahead_audit/test_finbert_observation_pit.py   pin-5 PIT gate; CI-blocking
```

## Limitations discovered

1. **iXBRL parsing is a narrow scope by design.** Filings without iXBRL
   section tags (mostly pre-2009) produce `section_unparseable` with a
   warning. The Stage A regex extractor recognizes only the three TextBlock
   element names in `IXBRL_SECTION_ELEMENT_MAP`; broader coverage will be
   added in Stage C alongside the live SEC connector wiring.
2. **`MODEL_RELEASE_DATES` is hand-curated.** Stage A ships only the
   `ProsusAI/finbert v1.0` entry. Stage B adds real model versions; until
   then `live_historical_PIT` against pinned models will block with
   `model_release_date_unknown`.
3. **No FinBERT weights are downloaded or loaded.** The mock implementation
   replaces real inference. Stage B introduces the transformers/ONNX paths
   with secret-safety sentinel tests.
4. **No FastAPI endpoints, no desktop UI panel.** Stage C scope.
5. **No prepopulation jobs.** Stage D scope. Pin-7 queue tickets are emitted
   but no worker fulfills them yet.

## Acceptance criteria status (Stage A)

- [x] Repo inspected and repo map written.
- [x] Feature flags added and default off.
- [x] Feature flag off leaves existing runtime/UI unchanged (no calls into
      existing wedge, no schema migrations, no new top-level imports).
- [x] Model-agnostic resolver `viza.finance.text.sentiment` registered.
- [x] FinBERT implemented as one resolver implementation (mock in Stage A),
      not the interface itself.
- [x] SEC filing text parser supports mocked 10-K/10-Q/8-K section extraction.
- [x] Text chunking is deterministic and hash-based.
- [x] Resolver returns per-section sentiment distributions, not a single
      whole-document scalar.
- [x] Resolver persists `model_version`, `tokenizer_hash`,
      `chunking_policy_hash`, `parser_version`, text hashes,
      `filing_accession`, `section_id`, `observed_at`, `available_at`,
      `retrieved_at`.
- [x] Cache key prevents silent model/parser/chunking changes.
- [x] On-call compute works with mocked model.
- [x] Cached/hot path works and is invisible to methodology graph.
- [x] Replay from stored observations works without live API/model calls.
- [x] Section aggregation works.
- [x] Tone delta vs prior filing works with clear constraints.
- [x] Human-review gate triggers for severe negative/fraud/legal/short-relevant
      language.
- [x] FinBERT output cannot directly create buy/sell/short recommendation
      (response carries non-advice boundary; resolver emits no such fields).
- [ ] Active-scope prepopulation supported — DEFERRED TO STAGE D (queue
      tickets emitted, no worker yet).
- [x] Full-market prepopulation is not default and is blocked/warned (Stage D
      will enforce; Stage A does not support prepopulation at all).
- [ ] UI shows filing-reading card, etc. — DEFERRED TO STAGE C.
- [ ] Package-redaction preview redacts bulk raw filing text in
      `marketplace_draft` — partial (intent surfaced in response; full
      redaction in Stage C).
- [x] No API keys/secrets appear in any new module, table, or test artifact.
- [x] New backend tests pass.
- [x] Existing unit/lookahead/desktop/typecheck tests not modified.

## Next backlog items

- Stage B: real local FinBERT + secret-safety sentinel sweep + ONNX path.
- Stage C: FastAPI router + desktop panel + full redaction modes + register
  attributes in the equity attribute registry seed.
- Stage D: prepopulation jobs for watchlist/portfolio/saved-thesis scopes,
  reusing `attribution_backfill_task` advisory-lock infrastructure.
