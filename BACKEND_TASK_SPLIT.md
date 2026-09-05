# Backend Task Split — Claude vs. Codex

> Companion to `HACKATHON_PLAN.md`. That document defines *what* to build; this one defines *who* builds which file, in what order, and how the two halves plug together without stepping on each other. Every path below is relative to `backend/`.

## 1. Why split it this way

The backend has a natural fault line, and it already exists in the plan: **things that reason** vs. **things that compute**.

- **Claude owns the agentic pipeline** — the LangGraph workflow, the eight agents, prompts, the LLM client, the guardrail/grounding verifier, memory and RAG plumbing, and the FastAPI surface that drives them. This is the part the user just asked to start first.
- **Codex owns the deterministic core** — the canonical Pydantic schemas' *data* half (parsing/persistence), the CSV ingestion pipeline, the analytics engine (variance, bridges, attribution, concentration, reconciliation), the synthetic dataset generator with ground-truth manifests, and the evaluation harness that scores against that ground truth.

This split minimizes merge conflicts (near-disjoint file sets), matches each side's strengths (agent orchestration and LLM behavior vs. numeric/data engineering), and mirrors the plan's own "Rule zero: LLMs do not calculate financial truth" — the agentic side should never need to touch Pandas math, and the analytics side should never need to touch a prompt.

**One shared file** (`models/schemas.py`) is the interface contract both sides import. See [§4](#4-the-shared-contract) for how changes to it are handled.

## 2. Claude's scope — Agentic Pipeline, Guardrails, API

Build order matches "start with the agentic pipeline" — everything here can run **today** against fixture data, without waiting on Codex's real analytics engine or CSV parser.

| Path | Responsibility | Plan reference |
|---|---|---|
| `config.py` | Thresholds, model ids, weights, `DEMO_FAST_MODE` | §17.3 |
| `models/schemas.py` | **Owned by Claude** (see §4) — all Pydantic contracts | §4 |
| `graph/state.py` | `RunState` TypedDict | §7.2 |
| `graph/events.py` | SSE event shapes | §7.3 |
| `graph/workflow.py` | LangGraph wiring: 8 nodes, parallel Memory/RAG/Analytics branch, QA gate, revision loop (cap 2) | §7.1 |
| `agents/profile_builder.py` | Normalizes already-parsed rows into `CompanyProfile`; entity alias resolution; sanitizes free text before it can reach a prompt | §6.1 |
| `agents/data_qa.py` | **Orchestrator only** — calls Codex's `analytics/reconciliation.py`; owns the gate policy (block vs. warn) and the QA report shape | §6.2 |
| `agents/memory_agent.py` | Memory lifecycle (candidate → confirmed → disputed → retired), confidence updates, conflict surfacing | §8 |
| `agents/rag_agent.py` | Query construction from flagged variances, Chroma retrieval, hybrid rerank | §9 |
| `agents/analyst.py` | Builds the fixed-order prompt, calls the LLM, parses into the `Explanation` contract, assigns `claim_type` | §6.5, §4.5 |
| `agents/guardrail.py` | Runs the grounding verifier + LLM guardrail review, returns `GuardrailResult` | §6.6, §10.1, §10.2 |
| `agents/stress_tester.py` | Orchestrates the 15 stress scenarios against a run; owns injection-resistance and grounding-related scenarios directly | §12 |
| `agents/report_writer.py` | Renders approved `Explanation` → dashboard payload, Markdown, voice script. **May not introduce a fact.** | §6.8 |
| `services/llm.py` | Single LLM entry point: retries, prompt caching, token accounting, mock mode when no API key | §17.2 |
| `services/grounding.py` | Numeric grounding verifier (regex extraction, fact matching, entity check, direction check) | §10.1 |
| `services/injection_filter.py` | Prompt-injection detection + neutralization for free-text cells | §10.3 |
| `services/memory_store.py` | SQLite-backed CRUD + lifecycle for memories | §8 |
| `services/rag_store.py` | Chroma wrapper, embedding calls, hybrid search | §9.2 |
| `services/tavily_client.py` | Cached, timeout-guarded research client | §16.1 |
| `services/elevenlabs_client.py` | Voice briefing generation with pre-rendered fallback | §16.2 |
| `api/routes/analyze.py`, `runs.py`, `memory.py`, `stress_tests.py`, `reports.py`, `voice.py`, `scenarios.py`, `health.py` | FastAPI routes over the graph and stores | §14.3 |
| `main.py` | App wiring, SSE endpoint | — |

**Explicitly not Claude's job:** `services/csv_parser.py`, anything under `analytics/`, `data/generate.py`, `models/db.py` (persistence schema for runs/files — memory store is the exception, see below), `eval/`.

## 3. Codex's scope — Deterministic Core, Data, Evaluation

Everything here is pure Python/Pandas with unit tests. No prompts, no LLM calls, no agent framework.

| Path | Responsibility | Plan reference |
|---|---|---|
| `services/csv_parser.py` | Column mapping, sign normalization, dedup, canonical row/summary construction from raw uploads | §4.1, §4.2 |
| `services/entity_resolver.py` | Fuzzy counterparty matching against `entity_aliases` (pure matching logic; Profile Builder calls this) | §6.1, §4.3 |
| `analytics/variance.py` | Absolute/percentage change, zero-prior handling, share-of-gross vs share-of-net | §5.1 |
| `analytics/bridges.py` | Component bridge, revenue bridge (new/expansion/contraction/churn/reactivation), gross-margin bridge, **with identity-sum tests** | §5.3 |
| `analytics/attribution.py` | Top-N attribution, evidence-txn mapping onto facts | §5.3 |
| `analytics/price_volume_mix.py` | Volume/price/mix decomposition, **with identity-sum test** | §5.3 |
| `analytics/concentration.py` | Top-1/top-3 share, HHI | §5.3 |
| `analytics/recurrence.py` | Recurring / one-time / seasonal / unclassified classification | §5.4 |
| `analytics/anomalies.py` | Outlier detection (>4σ), duplicate near-match detection | §6.2 |
| `analytics/reconciliation.py` | Summary-vs-transaction reconciliation per account, `worst_difference_pct`, gate signal | §6.2 |
| `analytics/materiality.py` | Priority score, control-limit flagging, `insufficient_history` fallback | §5.2 |
| `analytics/facts.py` | Assembles the outputs of the above into the immutable `Fact` list (fact table) — **this is the hand-off object into Claude's `agents/analyst.py`** | §4.4 |
| `models/db.py` | SQLAlchemy models for runs, files, audit log (memories stay in Claude's `memory_store.py`) | §14.1 |
| `data/generate.py` + `data/synthetic/` | Three dataset generators (SaaS, e-commerce, healthcare), seeded RNG, defect injection flags, ground-truth manifests | §13 |
| `eval/run.py`, `eval/suites.py`, `eval/metrics.py` | Evaluation harness: driver recall@3, attribution error, reconciliation accuracy, defect detection rate | §11 |
| `tests/unit/`, `tests/golden/` | Unit tests for all of the above + golden fact-table snapshots per demo dataset | §11.4 |

**Explicitly not Codex's job:** anything that calls an LLM, anything under `agents/` or `graph/`, prompts, `services/grounding.py` (that's verification of LLM output, not data computation — it lives with the agentic side even though it's deterministic), the FastAPI routes.

## 4. The shared contract

`models/schemas.py` is imported by both sides constantly, so exactly one side owns edits to it, to avoid the two of us drifting into incompatible shapes mid-build.

**Claude owns `models/schemas.py`.** Rationale: the agentic pipeline is the most schema-sensitive consumer (every agent's input/output is a Pydantic model), and it's being built first per the user's instruction, so the schemas need to exist before Codex's analytics functions have a `Fact` object to return.

Process:

1. Claude publishes `models/schemas.py` first, covering every shape in plan §4 (`CanonicalTransaction`, `PeriodSummary`, `CompanyProfile`, `Fact`, `Basis`, `Significance`, `Explanation`, `Claim`, `Driver`, `DriverEvidence`, `QAReport`, `ReconciliationLine`, `Warning`, `Memory`, `MemoryScope`, `GroundingReport`, `GuardrailResult`, `StressResult`, `RunState`).
2. Codex builds `analytics/facts.py` and friends **against those types** — import them, don't redefine them.
3. If Codex needs a field that doesn't exist yet (e.g., a new field on `Fact` for a decomposition type), open the request as a comment/note in `analytics/facts.py` (a `# SCHEMA REQUEST:` marker) rather than editing `schemas.py` directly — Claude applies it in one pass to keep the file's shape coherent.
4. Both sides treat the JSON examples in `HACKATHON_PLAN.md` §4 as the source of truth for field names and types.

## 5. Integration points (where the two halves touch)

| Boundary | Producer | Consumer | Object passed |
|---|---|---|---|
| Ingestion → Profile Builder | Codex's `csv_parser.py` | Claude's `agents/profile_builder.py` | `list[CanonicalTransaction]`, `PeriodSummary` |
| Profile Builder → Data QA | Claude's `profile_builder.py` | Claude's `data_qa.py` | `CompanyProfile` |
| Data QA → Codex reconciliation | Claude's `data_qa.py` | Codex's `analytics/reconciliation.py` | transactions + summaries in, `QAReport.reconciliation` out |
| Analytics Engine → Analyst | Codex's `analytics/facts.py` | Claude's `agents/analyst.py` | `list[Fact]` (the fact table — **never raw CSVs**) |
| Ground-truth manifest → Eval | Codex's `data/generate.py` | Codex's `eval/run.py` | manifest JSON |
| Eval → grounding cross-check (optional, could have) | Codex's `eval/metrics.py` | Claude's `services/grounding.py` | shared tolerance constant, kept in `config.py` |

**Until Codex's analytics engine exists**, Claude's pipeline runs against a **fixture fact table** (a hand-written JSON matching §4.4) so the agentic side is independently testable and demoable from day one. This is the same fixture the plan's offline/mock mode (`VITE_MOCK=1` on the frontend side) will eventually reuse.

## 6. Build order (both sides, in parallel)

```text
Hour 0        Claude: models/schemas.py (frozen v1)
              Codex:  data/generate.py skeleton + one dataset's raw CSVs (no parser yet)

Hour 0-4      Claude: config.py, graph/state.py, fixture fact table, services/llm.py (mock mode)
              Codex:  services/csv_parser.py, analytics/variance.py + reconciliation.py + tests

Hour 4-8      Claude: agents/analyst.py + guardrail.py + grounding.py against the FIXTURE fact table
              Codex:  analytics/bridges.py, attribution.py, materiality.py, facts.py (identity tests)

Hour 8-12     Claude: graph/workflow.py wiring all 8 nodes end-to-end (still on fixture data)
              Codex:  wire csv_parser -> analytics -> facts.py into one callable; golden fact-table snapshot

Hour 12       INTEGRATION: swap Claude's fixture fact table for Codex's real analytics/facts.py output.
              This is the single point where the two halves must actually match schemas.py exactly.

Hour 12+      Claude: memory_agent.py, rag_agent.py, stress_tester.py, API routes, SSE
              Codex:  second + third dataset generators, eval harness, unit test coverage, models/db.py
```

The hour-12 integration step is deliberately the *only* required sync point. Everything before it, both sides can build and test in complete isolation because Claude works off a fixture and Codex works off unit tests and golden files.

## 7. Definition of done (per side)

**Claude's agentic pipeline is done for a milestone when:** the LangGraph workflow runs end-to-end against the fixture fact table, produces a schema-valid `Explanation`, the grounding verifier reports a rate on it, and the guardrail returns a status — all reachable through at least one FastAPI route.

**Codex's deterministic core is done for a milestone when:** every analytics function has a passing unit test, every decomposition has a passing identity-sum test, `analytics/facts.py` produces a schema-valid `list[Fact]` from a real generated dataset, and the golden snapshot for that dataset is checked in.

## 8. What this document does not cover

Frontend (React dashboard) and sponsor integrations beyond the client stubs listed in §2 are out of scope here — see `HACKATHON_PLAN.md` §15–16 for those specs; they are unassigned as of this writing.
