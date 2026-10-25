"""POST /api/stress-tests/run, GET /api/stress-tests/results (plan
sections 12, 14.3).

Re-evaluates the Stress Test Agent's scenarios against an already-
completed run's stored state. This is deliberately NOT a full pipeline
re-run (no LLM calls involved) -- it lets the Stress Test Dashboard's
"run on demand" button (plan section 15.2) be instant, and lets scenario
logic be iterated on without paying for a fresh Analyst/Guardrail pass.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from agents import memory_agent, stress_tester as stress_tester_agent
from api.routes.analyze import get_run_or_404

router = APIRouter()


class StressTestRequest(BaseModel):
    run_id: str


@router.post("/stress-tests/run")
def run_stress_tests(request: StressTestRequest) -> dict:
    state = get_run_or_404(request.run_id)
    applications = memory_agent.apply_memories(state["memories"], state["facts"], state["transactions"])
    results = stress_tester_agent.run_available_scenarios(
        transactions=state["transactions"],
        explanation=state["explanation"],
        qa_report=state["qa_report"],
        memory_applications=applications,
    )
    return {"run_id": request.run_id, "results": [r.model_dump() for r in results]}


@router.get("/stress-tests/results")
def get_stress_results(run_id: str) -> dict:
    state = get_run_or_404(run_id)
    return {"run_id": run_id, "results": [r.model_dump() for r in state.get("stress_results", [])]}
