# FinOps Explain AI

> Financial variance intelligence with evidence: explain what changed, why it changed, and which transactions prove it.

**FinOps Explain AI** is a multi-agent money-operations platform built for the Maximor Money Operations Track (Coding Rangers Hackathon 2026). It converts transaction and period-summary CSVs into CFO-ready explanations with traceability, guardrails, and exportable reporting.

---

## Table of Contents

- [Product Overview](#product-overview)
- [Prominent Features](#prominent-features)
- [Sponsor Integrations](#sponsor-integrations)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Data Expectations](#data-expectations)
- [Team](#team)

---

## Product Overview

Finance teams rarely struggle to *see* a variance; they struggle to *defend* it. FinOps Explain AI addresses that gap by combining deterministic financial math with agentic reasoning and explicit evidence grounding.

The platform workflow:
1. Ingests uploaded transaction and summary CSVs.
2. Normalizes and validates data quality before reasoning.
3. Runs a multi-agent pipeline (memory, RAG, analysis, guardrails, stress testing).
4. Produces an executive narrative, driver table, evidence trail, and run artifacts.
5. Supports follow-up delivery via PDF export and optional voice briefing.

---

## Prominent Features

- **Evidence-backed analysis**: Every major claim can be traced to transaction-level evidence.
- **Multi-agent pipeline visibility**: The dashboard surfaces each stage of the run and quality checks.
- **Executive summary and confidence**: Output includes headline findings, confidence, and quality signals.
- **Driver-level drilldown**: Revenue movement is decomposed into named drivers with period-over-period deltas.
- **Waterfall visualization**: Charts explain how prior-period performance maps to current-period outcomes.
- **Stress testing and safety**: Injection attempts, duplicates, and reconciliation risks are detected and surfaced.
- **Memory + RAG context**: Prior-run memory and retrieval context are included in reasoning support.
- **Scenario simulation**: Deterministic what-if simulation for excluding selected drivers.
- **Report export**: Markdown and PDF report endpoints support board-ready sharing.
- **Voice briefing**: ElevenLabs integration generates an optional spoken CFO update.

---

## Sponsor Integrations

FinOps Explain AI intentionally aligns with sponsor technologies while preserving deterministic financial correctness.

### PRISM
**PRISM** is reflected in the project’s explainability-first approach: structure first, interpretation second, and explicit evidence throughout. In practice, this appears in how the system organizes profile/QA outputs into a transparent, auditable explanation flow rather than producing ungrounded summaries.

### GIDE
**GIDE** informs the guided assistant interaction model: users can ask follow-up questions while staying anchored to the same run object used by the dashboard. This keeps conversational output aligned with the underlying financial facts, drivers, and guardrail decisions.

### Tavily
**Tavily** is integrated on the backend for optional external context enrichment (`backend/services/tavily_client.py`) with graceful fallback behavior when unavailable. It is used for contextual augmentation and research-style signal support, while core variance math and canonical demo datasets remain deterministic and locally generated.

---

## System Architecture

<img width="963" height="617" alt="FinOps Explain AI System Design" src="https://github.com/user-attachments/assets/a089a4eb-78b1-4a56-8206-bb82ff24c2eb" />

High-level runtime path:

1. **User/CFO + React Dashboard**: upload data and request analysis.
2. **FastAPI backend**: orchestrate runs and expose API surfaces.
3. **Agent graph + finance engine**: normalize, reason, reconcile, stress-test, and compose outputs.
4. **Final payload**: dashboard-ready analysis JSON, report artifacts, and optional voice output.

Design principle: LLM agents synthesize and explain; deterministic services calculate, reconcile, and validate.

---

## Tech Stack

### Frontend
- React 19
- Vite
- Recharts
- jsPDF + jspdf-autotable
- Oxlint

### Backend
- FastAPI
- Uvicorn
- Pydantic
- LangGraph
- Pandas / NumPy
- SQLAlchemy

### Integrations
- Tavily (context enrichment)
- ElevenLabs (voice briefing)
- Configured LLM providers in `.env.example`: Groq, NVIDIA NIM, OpenRouter, Anthropic

---

## Project Structure

```text
CodingRangers-money-talks-hackathon-2026/
├── backend/
│   ├── main.py                     # FastAPI entrypoint and router wiring
│   ├── api/routes/                 # upload, analyze, memory, stress-tests, reports, voice, scenarios
│   ├── agents/                     # agent implementations (analyzer, guardrail, report writer, etc.)
│   ├── analytics/                  # deterministic financial logic
│   ├── services/                   # csv parser, rag store, tavily client, elevenlabs client
│   ├── tests/fixtures/             # built-in demo fixture payloads
│   └── requirements.txt
├── Frontend/
│   ├── src/components/             # upload + dashboard modules
│   ├── src/services/               # real API and mock API clients
│   ├── src/constants/api.js        # frontend endpoint map
│   └── package.json
├── test_data/                      # deterministic upload-ready datasets
├── HACKATHON_PLAN.md               # implementation blueprint and architecture details
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd Frontend
npm install
npm run dev
```

Vite proxies API requests to `http://localhost:8000` (see `Frontend/vite.config.js`), and backend CORS allows local dashboard origins.

---

## API Reference

### Core endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Runtime health, provider flags, and demo tier status. |
| `POST` | `/api/upload` | Upload and parse CSV into canonical records. |
| `POST` | `/api/analyze` | Start an asynchronous analysis run. |
| `GET` | `/api/analyze/stream/{run_id}` | Server-sent event stream of run progress. |
| `GET` | `/api/runs/{run_id}` | Retrieve final dashboard payload (returns 202 while running). |
| `GET` | `/api/runs/{run_id}/evidence` | Return fact-level evidence transaction details. |

### Supporting endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET`/`PATCH`/`DELETE` | `/api/memory` and `/api/memory/{memory_id}` | Memory list and correction lifecycle. |
| `POST` / `GET` | `/api/stress-tests/run`, `/api/stress-tests/results` | Run and fetch stress-test scenarios. |
| `GET` / `POST` | `/api/reports/{run_id}/markdown`, `/api/reports/{run_id}/pdf` | Export report artifacts. |
| `POST` / `GET` | `/api/voice/{run_id}`, `/api/voice/{run_id}/audio` | Generate and retrieve voice briefing. |
| `POST` | `/api/scenarios/simulate` | Deterministic scenario simulation by driver exclusion. |

---

## Data Expectations

The system is built for period-over-period analysis, so input data should span at least two periods.

### Minimum required (transactions CSV)
- One **date** column (`posted_date`, `date`, or `transaction_date`)
- One **amount** column (`amount` or `value`)

### Recommended schema

| Column | Accepted aliases | Notes |
|---|---|---|
| `posted_date` | `date`, `transaction_date` | ISO `YYYY-MM-DD` preferred. |
| `amount` | `value` | Currency and negative formats are supported. |
| `period_id` | `period`, `month` | Inferred from date if missing. |
| `account_id` / `account_name` | `account_code` / `account` | Enables account-level variance explanations. |
| `account_type` | `type` | Typical values: `revenue`, `cogs`, `opex`, `asset`, `liability`, `equity`. |
| `counterparty_name` | `customer`, `vendor`, `name` | Improves “who drove the change” attribution. |
| `category` | `class` | Optional classification field. |
| `memo` | `description`, `notes` | Scanned for prompt-injection patterns. |

For known-good upload samples, use the datasets under `test_data/`.

---

## Team

Built by **Coding Rangers** for the **Maximor Money Operations Track (2026)**.
