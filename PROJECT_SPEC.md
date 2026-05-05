# Single-Stock Attribution Engine — Project Spec

> Format follows the **PSB system** (Plan → Setup → Build) from Avthar Sewrathan's
> *"How I Start EVERY Claude Code Project."* This file covers **Phase 1 (Plan)**:
> the two anchor questions, milestones, product requirements, and engineering design.
> Setup steps and Build workflows live in `SETUP.md` and `BUILD.md` after this is locked.

Last updated: April 30, 2026
Source brief: `single_stock_attribution_project_report.pdf` (project design report)

---

## 0. The Two Anchor Questions

### Q1. What are we actually trying to do?
We are building an **alpha version of a research-grade product** — not a prototype, not a learning toy, and not a trading system. The output of an attribution run will be read by analysts and PMs whose job is to make money. That standard pulls us toward auditability, look-ahead-bias controls, and licensed data from day one. It also pushes us *away* from cute-but-unverified AI features.

Concretely, the system answers, for one stock over one window:
1. What drove the move?
2. How much did each driver contribute (in basis points and as share of move)?
3. What evidence supports each attribution?
4. How confident should the user be?
5. Should the company's exposure profile be updated?

### Q2. What are the milestones?

| Milestone | Definition of done | Universe / scope |
|---|---|---|
| **MVP (v0)** | Daily close-to-close attribution for 50 liquid US large-caps. Output = ranked driver table + short narrative + confidence score + explicit residual. Factor baseline runs before event attribution. Look-ahead audit passes. | 50 names, daily, post-close |
| **v1** | Add event-NLP layer (8-K classification, news relevance/novelty, earnings transcript tone, analyst revisions). Add weekly view. Analyst feedback capture. | Same 50 names |
| **v2** | Add positioning & options (short interest, IV, gamma), peer read-through graph, calibrated confidence ranges. Expand to 100 names. | 100 names |
| **v3** | Adaptive exposure profile updates with half-life. Custom peer baskets. Exposure-change alerts. | 100 names |
| **v4** | Decision-support layer — thesis monitoring, anomaly alerts, scenario tools. Optional intraday. | 100+ names |

**Hard MVP exclusions** (per the report's section 14.3): no global universe, no real-time intraday, no unconstrained-LLM attribution judge, no unlicensed news/research feeds, no auto-updating of structural exposures from a single noisy day.

---

## 1. Product Requirements

### 1.1 Who is it for?
Primary: equity analyst, sector PM, risk analyst at a hedge fund, asset manager, or family office. Secondary: independent research shops and buy-side teams that already pay for Bloomberg/FactSet but lack a dedicated single-stock attribution layer.

### 1.2 What problems does it solve?
The morning-meeting problem: an analyst stares at a +4% close on a name they cover and has 20 minutes to figure out *why* before the PM asks. Today they triangulate across Bloomberg, the news tape, FactSet estimates, and a Slack channel of peer covers. The output is a verbal hand-wave. Our system replaces the hand-wave with a reconcilable table: market beta took +0.5%, sector took +0.7%, guidance raise took +1.8%, residual is +0.1%, here is the evidence, here is the confidence.

It also kills the *narrative-error* problem — the lazy "stock up because [headline that happened to print today]" reasoning that shows up in sell-side morning notes and chat commentary.

### 1.3 What should the product do?

The system must, for any (ticker, window) pair:

**1. Compute returns deterministically.** Pull adjusted close, handle corporate actions, splits, dividends, share-class differences. No magic. This part is exact and reproducible or it is wrong.

**2. Run factor baseline FIRST.** Decompose the move into market beta, sector beta, peer-basket effect, style factors (growth/value/momentum/quality/size/vol), macro (rates, FX, commodities, credit, vol regime), and a leftover residual. The residual is the object of further analysis — *not* the headline of the day.

**3. Pull and score events against the residual.** Earnings, guidance, 8-Ks, Form 4 insider trades, 13D/G activist filings, analyst revisions, peer read-through events, regulatory/legal news. Each event gets scored on relevance × novelty × sentiment × magnitude × source credibility × exposure match × timing weight.

**4. Allocate residual to events with confidence.** Use historical event-study sensitivities and analyst-calibrated weights. Output contribution as a range when uncertainty is high. Reconcile contributions to the observed return; show what's left as `unexplained_residual` rather than forcing a fit.

**5. Generate a constrained narrative.** An LLM writes the human-readable explanation, but it can ONLY use the engine's structured outputs. It does not invent attributions. Every claim links back to evidence with a timestamp.

**6. Decide whether to update the company's exposure profile.** Most daily moves do not change structural exposure. A single analyst downgrade should not. A new multi-year supply contract or a major acquisition should. The decision rule is conservative, evidence-persistent, and human-reviewed for high-impact cases.

**7. Show what it does not know.** A visible `unexplained_residual` and a calibrated confidence score are features, not bugs. Forced explanations destroy trust.

### 1.4 Specific user-experience requirements (the journaling-app lesson)

- **The driver table is the product.** Not a chat box. A table with columns: driver, contribution_bps, share_of_move, confidence, evidence_links. Sortable, exportable to CSV/Excel.
- **Every contribution row has an "Evidence" expand.** Click → shows the underlying events/features/factor returns that produced the attribution, with timestamps and sources.
- **Residual is shown in red when it exceeds 50% of the absolute move.** The system is telling the user "I'm not sure" and that needs to be visually loud.
- **Confidence is a 5-level scale**, not a continuous score. Levels: High, Medium-High, Medium, Low-Medium, Low. Mapped to evidence conditions in the report's section 6.5.
- **Narrative is at most 4 sentences.** Long prose hides ambiguity. Short prose forces precision.
- **Analyst feedback is one-click per driver.** Correct / partially correct / wrong / missing-driver. This becomes the labeled-data flywheel.
- **Date-pickable backfill.** User can run attribution for any historical date and the system enforces point-in-time features (no look-ahead).

### 1.5 Non-goals (what we explicitly do NOT do)

- Not a trading-signal generator.
- Not a Bloomberg/FactSet replacement.
- Not a black-box "AI explains the market" chatbot.
- Not a real-time intraday tape-reader (in MVP).
- Not a system that scrapes paywalled content for production use.
- Not a portfolio-level performance attribution tool (MSCI Barra / Axioma already do that well).

---

## 2. Engineering Requirements

### 2.1 Tech stack

> Note: the user's preference specified `yeslanguage` which I could not resolve to a known
> language. The defaults below are the conventional hedge-fund quant stack. If you want
> Rust for the engine, Julia for the factor models, or anything else, swap it here and
> the agents will follow.

**Core engine — Python 3.12**
- `polars` for tabular data (faster than pandas at this scale; lazy execution helps backtests)
- `numpy`, `scipy.stats` for math
- `statsmodels` for rolling-window factor regressions
- `scikit-learn` for the event-scoring models
- `pydantic v2` for all data contracts (every event, feature, contribution is a typed model)
- `polars-talib` or `ta-lib` for technical indicators

**Storage**
- `PostgreSQL 16` for the relational data model (companies, securities, attribution_runs, contributions, exposures)
- `TimescaleDB` extension for the price_bar / factor_return / macro_series time-series tables
- `MinIO` or `S3` for raw filings, transcripts, news payloads (large blobs)
- `DuckDB` for ad-hoc analyst queries on the historical attribution database

**NLP / event intelligence**
- `Anthropic API` (Claude Sonnet 4.6 for routine classification, Opus 4.7 for transcript reasoning) for filing parsing, sentiment, novelty, relevance scoring — but always returning structured JSON, never freeform causal claims
- `sentence-transformers` for novelty scoring via embedding-distance to historical events

**Data adapters (one per source, behind a common `Adapter` protocol)**
- SEC EDGAR (free, official) — 8-K, 10-Q, 10-K, Form 4, 13D/G, 13F
- FRED (free, official) — macro series
- Kenneth French data library (free) — academic style factors
- Bloomberg / FactSet / LSEG — prices, estimates, real-time news (requires licensing — gate behind a feature flag)
- RavenPack / Dataminr — event feeds (also licensed)
- FINRA — short interest
- OCC / OPRA — options open interest, volume, IV

**Backend service**
- `FastAPI` for the attribution API
- `Celery + Redis` for the daily attribution batch jobs
- `Prefect` (or Dagster) for the data ingestion DAG — preferred over Airflow because of point-in-time semantics

**Frontend dashboard**
- `Next.js 15` (App Router)
- `Tailwind` + `shadcn/ui`
- `TanStack Table` for the driver-table (sort, filter, virtualize)
- `Recharts` for sparkline factor decomposition
- Auth: `Clerk` (per Avthar's recommendation; swap for SAML/SSO at v3)

**Infra**
- Vercel for the dashboard
- Render or Fly.io for the FastAPI service
- Managed Postgres (Supabase or Neon) for dev, self-hosted for production once licensing demands it

### 2.2 Repository layout

```
single-stock-attribution/
├── CLAUDE.md                       # short, links out to other docs
├── PROJECT_SPEC.md                 # this file
├── ARCHITECTURE.md                 # auto-maintained by docs-keeper agent
├── CHANGELOG.md                    # auto-maintained
├── PROJECT_STATUS.md               # auto-maintained
├── docs/
│   ├── attribution_methodology.md
│   ├── exposure_update_policy.md
│   ├── data_licensing.md
│   └── compliance_checklist.md
├── .claude/
│   ├── agents/                     # the 10 sub-agents (see SUBAGENTS.md)
│   ├── commands/                   # slash commands
│   └── settings.json               # pre-approved permissions
├── engine/                         # Python — pure attribution logic
│   ├── returns/                    # deterministic return accounting
│   ├── factors/                    # statistical factor attribution
│   ├── events/                     # AI/NLP event intelligence
│   ├── attribution/                # reconciliation engine
│   ├── confidence/                 # confidence scoring
│   └── exposures/                  # company exposure profile + update logic
├── adapters/                       # one folder per source
│   ├── price/
│   ├── sec_edgar/
│   ├── fred/
│   ├── french/
│   ├── news/
│   └── ...
├── api/                            # FastAPI service
├── dashboard/                      # Next.js frontend
├── jobs/                           # Prefect flows for daily batch
├── tests/
│   ├── unit/
│   ├── integration/
│   └── lookahead_audit/            # standalone — runs against every PR
└── alembic/                        # DB migrations
```

### 2.3 Data model (canonical entities)

Already specified in the report's section 8.4. Lock these as the v0 schema:

`company` · `security` · `price_bar` · `factor_return` · `macro_series` · `event` · `company_exposure` · `attribution_run` · `attribution_contribution`

Two non-negotiable invariants:

1. **Every feature row stores `event_time`, `ingestion_time`, AND `timestamp_available`** — the last is what the model is allowed to see for a given attribution date. Backtests filter on `timestamp_available <= attribution_cutoff`. No exceptions.
2. **`security_id` and `company_id` are immutable** — never key on `ticker` because tickers change (FB→META, GOOG vs. GOOGL, share-class splits, ADRs).

### 2.4 The hybrid architecture (this is the moat)

The system is **deterministic where correctness matters, statistical where sensitivity must be estimated, AI where language must be interpreted, and human-reviewed where causality is ambiguous.** The four layers, top-to-bottom:

```
  ┌─ Layer 4: Explanation layer ─────────────────┐  ← LLM (constrained)
  │   Reads engine outputs, writes 4-sentence    │
  │   narrative. Cannot invent attributions.     │
  └──────────────────┬───────────────────────────┘
                     │
  ┌─ Layer 3: AI/NLP event intelligence ─────────┐  ← LLM + ML
  │   Filing classification, sentiment, novelty, │
  │   relevance, surprise. Outputs structured.   │
  └──────────────────┬───────────────────────────┘
                     │
  ┌─ Layer 2: Statistical attribution ───────────┐  ← Statsmodels / sklearn
  │   Factor regressions, peer-adjusted returns, │
  │   event-study sensitivities, residuals.      │
  └──────────────────┬───────────────────────────┘
                     │
  ┌─ Layer 1: Deterministic accounting ──────────┐  ← Pure functions
  │   Adjusted returns, corporate actions,       │
  │   contribution reconciliation, audit log.    │
  └──────────────────────────────────────────────┘
```

Why this layering matters for agent design: each layer maps to a different specialist subagent, and the boundaries between layers are where contracts (Pydantic schemas) live. Agents talk to each other through those contracts, not through prose.

### 2.5 Risk register → engineering controls

| Risk (from report §15.2) | Engineering control |
|---|---|
| Look-ahead bias | Mandatory `timestamp_available` on every feature; CI test that rebuilds historical features and asserts equality |
| Bad entity mapping | Immutable `security_id`; ticker-history table; entity-resolver agent with audit logs |
| Data licensing | Per-source license metadata in `adapter` config; production builds fail if any unlicensed adapter is enabled |
| Over-attribution to news | Architectural rule: residual is computed BEFORE event retrieval. Agents enforce this in code review. |
| Multicollinearity in factors | Hierarchical attribution + ridge regularization; reported as confidence-degrading flag |
| LLM hallucination in narrative | Narrative LLM receives ONLY structured engine outputs as context; no raw web access during narrative generation |
| Reproducibility | Every `attribution_run` stores `model_version`, `data_version`, `factor_basket_version` |

### 2.6 Definition of Done — MVP gate

The MVP ships when ALL of these are true:

- [ ] 50 named tickers run end-to-end every weekday after market close
- [ ] Attribution sums reconcile to observed return within 1 bp
- [ ] `unexplained_residual` is reported on every output
- [ ] Look-ahead audit suite passes for the trailing 252 trading days
- [ ] Entity-resolver covers ticker changes, share classes, and at least 5 historical M&A cases in the universe
- [ ] Analyst feedback (correct/partial/wrong/missing) is captured per driver
- [ ] No production code path uses unlicensed data
- [ ] `architecture.md`, `CHANGELOG.md`, `PROJECT_STATUS.md` are kept current by an agent
- [ ] Pilot test with ≥3 analysts, ≥4 weeks, ≥60% "useful" rating per driver

---

## 3. What's not in this file

- **Setup checklist** (GitHub repo, `CLAUDE.md`, automated docs, plugins, MCPs, slash-commands) → `SETUP.md`
- **Subagent definitions** (the 10 agents, why each, creation prompts, harness strategy) → `SUBAGENTS.md`
- **Build workflow** (general / issue-based / multi-agent + git worktree plan) → `BUILD.md`

Lock this spec before moving to setup. Iteration on product requirements is fine and expected — but iterate on this file, not on tribal knowledge in chat.
