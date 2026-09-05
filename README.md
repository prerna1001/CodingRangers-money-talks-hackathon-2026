# FinOps Explain AI

> Money operations, explained with evidence — not just a variance number, but *why* it moved and *which transactions* proved it.

Built for the **Maximor Money Operations Track**, Coding Rangers hackathon team.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Product Overview](#product-overview)
3. [Key Features](#key-features)
4. [System Architecture](#system-architecture)
5. [Tech Stack](#tech-stack)
6. [Project Structure](#project-structure)
7. [API Reference](#api-reference)
8. [Getting Started](#getting-started)
9. [Team](#team)

---

## Problem Statement

Finance teams don't lack dashboards — they lack **trustworthy explanations**. A chart showing "revenue +18%" answers *what* happened but not *why*, *who* drove it, or *whether it will hold*. Today that gap is closed manually: an analyst opens the transaction ledger, cross-references customers, and writes a summary for the board — a slow, error-prone process repeated every month-end.

Most "AI for finance" demos just pipe one CSV into an LLM and ask it to summarize. That produces fluent but unverifiable prose — numbers an LLM can invent, drivers it can hallucinate, and no way for a CFO to check the claim before presenting it to a board.

**FinOps Explain AI** exists to close that gap: turn raw monthly summaries and transaction data into evidence-backed, board-ready explanations of what changed and why — with every claim traceable back to a source transaction.

## Product Overview

FinOps Explain AI is a money-operations analyst that:

1. Ingests monthly account summaries and transaction-level CSVs.
2. Runs them through an analysis pipeline (Profile Builder → Data QA → Memory → RAG → Analyzer → Guardrail → Stress Test → Report).
3. Presents an executive dashboard: headline finding, top drivers, a revenue waterfall, a driver drilldown table, and transaction-level evidence.
4. Lets the user ask follow-up questions in a chat panel grounded in the same analysis (no separate source of truth).
5. Generates a downloadable PDF report and an optional spoken CFO-style audio briefing (ElevenLabs).

Target users: startup founders, fractional CFOs, finance operators, and RevOps teams who need a defensible answer to "what changed this month, and why" without waiting on a full manual close.

## Key Features

| Feature | Description |
|---|---|
| **CSV Upload** | Drag-and-drop upload of transaction and account-summary CSVs; backend detects file type and row count. |
| **Agent Pipeline Visualization** | Animated timeline showing each analysis stage (Profile Builder, Data QA, Memory, RAG, Analyzer, Guardrail, Stress Test, Report Writer) with pass/warning status. |
| **Executive Summary** | One-sentence headline, confidence score, and data-quality score for the run. |
| **Revenue Waterfall** | Recharts-based waterfall showing how prior-period revenue became current-period revenue, broken into named drivers. |
| **Driver Drilldown Table** | Account-level table of current vs. prior value, absolute/percentage change, and confidence per driver. |
| **Evidence Trail** | Every driver links to the transactions that justify it (customer, amount, contribution). |
| **Grounded Chat Assistant** | Ask "why did revenue increase," "what are the risks," "how confident are you" — answers pull from the same analysis object shown on the dashboard, so chat and dashboard never disagree. |
| **Stress Test Panel** | Surfaces data-quality and robustness checks (duplicate transactions, missing fields, reconciliation mismatches). |
| **Memory & RAG Panels** | UI surfaces for prior-run memory and retrieved context, showing what informed the current explanation. |
| **Scenario Simulator** | What-if exploration on top of the analyzed drivers. |
| **Report Export** | One-click PDF report generation (jsPDF) with the executive summary, waterfall, and driver table. |
| **Voice Briefing** | Real ElevenLabs text-to-speech integration — turns the written summary into a downloadable audio briefing. |

## System Architecture

<img width="963" height="617" alt="Screenshot 2026-09-05 at 3 29 56 PM" src="https://github.com/user-attachments/assets/a089a4eb-78b1-4a56-8206-bb82ff24c2eb" />



## Tech Stack

**Frontend**
- React 19 + Vite
- Recharts (waterfall / charts)
- jsPDF + jspdf-autotable (report export)
- oxlint

**Backend**
- FastAPI + Uvicorn
- Pydantic (request/response models)
- python-dotenv

**Third-party / Sponsor integrations**
- ElevenLabs (text-to-speech CFO voice briefing)

**Planned (per hackathon plan)**
- LangGraph (multi-agent orchestration)
- Pandas (deterministic variance/attribution engine)
- ChromaDB / FAISS (RAG store)
- SQLite/Postgres (run history, memory store)
- Tavily (external research enrichment)

## Project Structure

```text
CodingRangers-money-talks-hackathon-2026/
├── backend/
│   ├── main.py              # FastAPI app: upload, analyze, chat, voice endpoints
│   ├── requirements.txt
│   └── .env.example
├── Frontend/
│   ├── src/
│   │   ├── App.jsx                 # phase state machine: upload -> analyzing -> dashboard
│   │   ├── components/
│   │   │   ├── UploadCard.jsx
│   │   │   ├── AgentTimeline.jsx
│   │   │   └── dashboard/
│   │   │       ├── Dashboard.jsx
│   │   │       ├── ExecutiveSummary.jsx
│   │   │       ├── WaterfallChart.jsx
│   │   │       ├── DriverTable.jsx
│   │   │       ├── ChatPanel.jsx
│   │   │       ├── MemoryPanel.jsx
│   │   │       ├── RagPanel.jsx
│   │   │       ├── StressTestPanel.jsx
│   │   │       ├── ScenarioSimulator.jsx
│   │   │       ├── ReportPanel.jsx
│   │   │       └── PipelinePanel.jsx
│   │   ├── services/api.js         # real API client
│   │   ├── services/mockApi.js     # local mock client (offline/dev)
│   │   └── utils/pdfReport.js
│   └── package.json
├── data/
│   ├── table_1a_transactions.csv
│   └── table_1b_account_summary.csv
├── HACKATHON_PLAN.original.md  # full target vision / architecture
└── README.md
```

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload` | Accepts a CSV file, detects type (`transaction_csv` / `monthly_summary_csv`), returns row count and file metadata. |
| `POST` | `/api/analyze` | Runs analysis for a given `file_id` (optional) and returns the full explanation object: headline, drivers, waterfall series, agent timeline, risks/caveats. |
| `POST` | `/api/chat` | Accepts `{ message, history }`, returns a reply grounded in the current analysis. |
| `POST` | `/api/voice/speak` | Accepts `{ text }`, returns an MP3 audio stream generated via ElevenLabs. Requires `ELEVENLABS_API_KEY`. |

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
cp .env.example .env   # add ELEVENLABS_API_KEY to enable voice briefings
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd Frontend
npm install
npm run dev
```

The frontend expects the backend at the URL configured in [`src/constants/api.js`](Frontend/src/constants/api.js), with CORS already allowed for `http://localhost:5173`.

## Team

Coding Rangers — Maximor Money Operations Track, 2026.
