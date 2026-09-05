"""POST /api/analyze, GET /api/runs, GET /api/runs/{run_id},
GET /api/runs/{run_id}/evidence, GET /api/runs/{run_id}/trace,
GET /api/analyze/stream/{run_id} (plan section 14.3).

Run persistence here is an in-memory dict, not Codex's real `models/db.py`
(runs/files/audit -- BACKEND_TASK_SPLIT.md section 2/3). This is a
placeholder good enough to demo and test the agentic pipeline through
HTTP; swapping it for real persistence is a drop-in change once that
module exists (same function signatures: `_save_run`/`_get_run`).

Ingestion (CSV upload -> CanonicalTransaction/PeriodSummary) is also not
built yet -- Codex's `services/csv_parser.py` owns that (plan section
4.1/4.2). Until then, `POST /api/analyze` runs against the checked-in
demo fixture so the endpoint is exercisable end to end today.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.presenters import to_frontend_analysis
from graph.events import EVENT_BUS
from graph.workflow import run_pipeline
from models.schemas import (
    CanonicalTransaction,
    CompanyProfileCore,
    PeriodLine,
    PeriodSummary,
    RunState,
)

router = APIRouter()

# In-memory run registry keyed by run_id -- {"status": "running"|"complete"|"error",
# "state": RunState | None, "error": str | None}. Placeholder for Codex's real
# `models/db.py` persistence (BACKEND_TASK_SPLIT.md section 2/3); swapping this
# for a real table is a drop-in change since every route below only calls
# `get_run_or_404` / assigns into `_RUNS`.
_RUNS: dict[str, dict] = {}
_FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


class AnalyzeRequest(BaseModel):
    company_id: str = "demo_saas"
    company_name: str | None = None
    current_period: str = "2026-08"
    prior_period: str = "2026-07"
    # When both lists are empty, the checked-in demo fixture is used
    # (documented below) -- pass file_ids from POST /api/upload to analyze
    # a real uploaded dataset instead.
    transaction_file_ids: list[str] = []
    period_summary_file_ids: list[str] = []
    known_aliases: dict[str, list[str]] = {}


def _derive_period_summaries(transactions: list[CanonicalTransaction]) -> list[PeriodSummary]:
    """Roll transactions up into period summaries when the caller only
    uploaded a transactions file.

    The dashboard's upload flow posts a single CSV, so without this a
    transactions-only upload could never be analyzed (the variance engine
    needs both periods' summaries to diff). Note the tradeoff: summaries
    derived this way reconcile perfectly *by construction*, so the Data QA
    reconciliation gate is a no-op for them -- it only does real work when
    an independent summary file is supplied alongside the transactions.
    """
    totals: dict[tuple[str, str], float] = defaultdict(float)
    names: dict[str, tuple[str, str]] = {}
    dates: dict[str, list] = defaultdict(list)

    for txn in transactions:
        totals[(txn.period_id, txn.account_id)] += txn.amount
        names[txn.account_id] = (txn.account_name, txn.account_type)
        dates[txn.period_id].append(txn.posted_date)

    summaries: list[PeriodSummary] = []
    for period_id in sorted({p for p, _ in totals}):
        lines = [
            PeriodLine(
                account_id=account_id,
                account_name=names[account_id][0],
                account_type=names[account_id][1],
                amount=round(amount, 2),
            )
            for (p, account_id), amount in sorted(totals.items())
            if p == period_id
        ]
        summaries.append(
            PeriodSummary(
                period_id=period_id,
                start_date=min(dates[period_id]),
                end_date=max(dates[period_id]),
                lines=lines,
            )
        )
    return summaries


def _infer_periods(summaries: list[PeriodSummary]) -> tuple[str, str] | None:
    """Current/prior = the two most recent periods present in the data."""
    period_ids = sorted({s.period_id for s in summaries})
    if len(period_ids) < 2:
        return None
    return period_ids[-1], period_ids[-2]


def _load_uploaded_dataset(
    request: "AnalyzeRequest",
) -> tuple[list[CanonicalTransaction], list[PeriodSummary], CompanyProfileCore]:
    from api.routes.upload import get_uploaded_period_summaries, get_uploaded_transactions

    transactions = get_uploaded_transactions(request.transaction_file_ids)
    period_summaries = get_uploaded_period_summaries(request.period_summary_file_ids)

    if not period_summaries and transactions:
        period_summaries = _derive_period_summaries(transactions)

    profile_core = CompanyProfileCore(
        company_id=request.company_id,
        company_name=request.company_name or request.company_id,
        industry="unknown",
        business_model="unknown",
    )
    return transactions, period_summaries, profile_core


def _load_demo_fixture() -> tuple[list[CanonicalTransaction], list[PeriodSummary], CompanyProfileCore]:
    data = json.loads((_FIXTURES_DIR / "saas_2026_08_transactions.json").read_text())
    transactions = [CanonicalTransaction(**t) for t in data["transactions"]]
    period_summaries = [PeriodSummary(**p) for p in data["period_summaries"]]
    profile_core = CompanyProfileCore(
        company_id="demo_saas",
        company_name="DemoCo",
        industry="B2B SaaS",
        business_model="subscription",
        primary_revenue_streams=["SMB subscriptions", "Enterprise subscriptions", "Professional services"],
        known_seasonality=["Q4 enterprise renewals", "summer SMB slowdown"],
    )
    return transactions, period_summaries, profile_core


async def _execute_pipeline(run_id: str, **kwargs) -> None:
    """Runs the (synchronous, LLM-calling) pipeline off the event loop so
    the SSE stream below can actually receive events as they happen,
    instead of the whole run completing -- and publishing every event --
    before a client has had a chance to subscribe.
    """
    try:
        final_state = await asyncio.to_thread(run_pipeline, run_id=run_id, **kwargs)
        _RUNS[run_id] = {"status": "complete", "state": final_state, "error": None}
    except Exception as exc:  # noqa: BLE001 - surfaced via GET /api/runs/{run_id}
        _RUNS[run_id] = {"status": "error", "state": None, "error": str(exc)}


@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    current_period = request.current_period
    prior_period = request.prior_period

    if request.transaction_file_ids or request.period_summary_file_ids:
        transactions, period_summaries, profile_core = _load_uploaded_dataset(request)
        # Uploaded data won't necessarily cover the request's default periods,
        # so take the two most recent periods actually present. An explicit
        # period pair in the request still wins if it matches the data.
        available = {s.period_id for s in period_summaries}
        if not {current_period, prior_period} <= available:
            inferred = _infer_periods(period_summaries)
            if inferred is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Need at least two periods to compare, but the uploaded data "
                        f"contains: {sorted(available) or 'none'}. Upload a file spanning "
                        "two or more periods (see test_data/ for examples)."
                    ),
                )
            current_period, prior_period = inferred
    else:
        transactions, period_summaries, profile_core = _load_demo_fixture()

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    _RUNS[run_id] = {"status": "running", "state": None, "error": None}

    asyncio.create_task(
        _execute_pipeline(
            run_id,
            company_id=request.company_id,
            current_period=current_period,
            prior_period=prior_period,
            company_profile_core=profile_core,
            transactions=transactions,
            period_summaries=period_summaries,
            known_aliases=request.known_aliases or {"vendor:aws": ["AWS", "Amazon Web Services", "AMZN AWS"]},
        )
    )
    return {"run_id": run_id, "status": "running", "stream_url": f"/api/analyze/stream/{run_id}"}


@router.get("/runs")
def list_runs() -> list[dict]:
    return [
        {
            "run_id": run_id,
            "status": entry["status"],
            "company_id": entry["state"]["company_id"] if entry["state"] else None,
            "current_period": entry["state"]["current_period"] if entry["state"] else None,
        }
        for run_id, entry in _RUNS.items()
    ]


def get_run_or_404(run_id: str) -> RunState:
    entry = _RUNS.get(run_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if entry["status"] == "running":
        raise HTTPException(status_code=202, detail=f"Run {run_id} is still in progress")
    if entry["status"] == "error":
        raise HTTPException(status_code=500, detail=f"Run {run_id} failed: {entry['error']}")
    return entry["state"]


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    """Returns the finished run in the shape the React dashboard consumes
    (api/presenters.py). Raises 202 while the run is still in flight, which
    is what the frontend's analyzeRun() polls on.
    """
    state = get_run_or_404(run_id)
    return to_frontend_analysis(state)


@router.get("/runs/{run_id}/evidence")
def get_evidence(run_id: str, fact_id: str | None = None) -> dict:
    state = get_run_or_404(run_id)
    facts = state.get("facts", [])
    if fact_id:
        facts = [f for f in facts if f.fact_id == fact_id]
        if not facts:
            raise HTTPException(status_code=404, detail=f"fact_id {fact_id} not found in run {run_id}")
    txns_by_id = {t.txn_id: t for t in state.get("transactions", [])}
    return {
        "facts": [
            {
                **f.model_dump(),
                "evidence_transactions": [
                    txns_by_id[tid].model_dump() for tid in f.evidence_txn_ids if tid in txns_by_id
                ],
            }
            for f in facts
        ]
    }


@router.get("/runs/{run_id}/trace")
def get_trace(run_id: str) -> dict:
    """Full audit trace -- every input, every agent output, every check
    result (plan section 10.4's auditability requirement).
    """
    state = get_run_or_404(run_id)
    return {
        key: (
            [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
            if isinstance(value, list)
            else (value.model_dump() if hasattr(value, "model_dump") else value)
        )
        for key, value in state.items()
    }


@router.get("/analyze/stream/{run_id}")
async def stream_run(run_id: str):
    async def event_generator():
        async for event in EVENT_BUS.subscribe(run_id):
            yield {"event": event["type"], "data": json.dumps(event, default=str)}
            if event["type"] == "run_complete":
                break

    return EventSourceResponse(event_generator())
