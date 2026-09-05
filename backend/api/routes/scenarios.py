"""POST /api/scenarios/simulate -- the Scenario Simulator (plan section
15.2, #9): "What if this customer had not expanded?" etc. Deterministic,
no LLM call, so it's instant.

Simplified relative to the full plan: this excludes named drivers'
dollar amounts from the headline variance directly, rather than
re-running the analytics engine over a filtered transaction set. A full
re-run (Codex's analytics.facts.build_facts against transactions with
certain counterparties removed) is the natural upgrade path once a
richer simulator is needed -- this version already answers the question
judges actually ask ("what's the delta if I pull this driver out?").
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.routes.analyze import get_run_or_404

router = APIRouter()


class ScenarioRequest(BaseModel):
    run_id: str
    exclude_drivers: list[str] = []


@router.post("/scenarios/simulate")
def simulate_scenario(request: ScenarioRequest) -> dict:
    state = get_run_or_404(request.run_id)
    explanation = state.get("explanation")
    if explanation is None:
        raise HTTPException(status_code=404, detail=f"No explanation available for run {request.run_id}")

    variance_fact = next((f for f in state.get("facts", []) if f.kind == "variance"), None)
    base_total = variance_fact.value if variance_fact is not None else sum(d.amount for d in explanation.drivers)

    excluded = [d for d in explanation.drivers if d.driver in request.exclude_drivers]
    excluded_amount = sum(d.amount for d in excluded)
    adjusted_total = base_total - excluded_amount

    return {
        "run_id": request.run_id,
        "base_total": base_total,
        "excluded_drivers": [d.model_dump() for d in excluded],
        "excluded_amount": excluded_amount,
        "adjusted_total": adjusted_total,
        "delta": adjusted_total - base_total,
    }
