"""POST /api/chat -- dashboard chatbot, grounded in one finished run.

The bot only ever sees the same presenter payload the dashboard renders
(api/presenters.to_frontend_analysis), so it can't cite a number the
dashboard doesn't show. With an LLM key configured it answers through
services/llm.py (task "chat"); in mock mode, or if the call fails, it
falls back to a deterministic rule-based answer over the same data.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import auth0_setup
from api.presenters import to_frontend_analysis
from api.routes.analyze import get_run_or_404
from services import llm

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_HISTORY_TURNS = 10

SYSTEM_PROMPT = """You are FinOps Explain AI, a financial analyst assistant answering questions \
about ONE analysis run. Use only the facts in the RUN DATA JSON below. If the answer is not in \
the data, say so plainly -- never invent numbers, customers, or causes. Keep answers short \
(2-4 sentences), in plain text with no markdown, because answers may be read aloud. Format \
money like $12,400."""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    run_id: str
    message: str
    history: list[ChatMessage] = []


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def _rule_based_reply(message: str, analysis: dict) -> str:
    text = message.lower()
    drivers = analysis.get("drivers") or []
    risks = analysis.get("risks_or_caveats") or []
    prior = analysis["periods"]["prior"]
    current = analysis["periods"]["current"]

    if any(w in text for w in ["risk", "caveat", "concern", "worr"]):
        if not risks:
            return "No specific risks or caveats were flagged for this run."
        return "Flagged risks for this run: " + " ".join(risks)

    if any(w in text for w in ["churn", "lost", "cancel", "decline", "decrease", "drop", "down"]):
        negatives = [d for d in drivers if d["amount"] < 0]
        if not negatives:
            return "No negative drivers were found between these periods."
        parts = [f"{d['driver']} ({_money(d['amount'])})" for d in negatives[:3]]
        return "The biggest negative movements were: " + "; ".join(parts) + "."

    if any(w in text for w in ["driver", "why", "cause", "reason", "increase", "grow", "up"]):
        if not drivers:
            return analysis.get("summary") or "No drivers were identified for this run."
        top = drivers[0]
        others = ", ".join(f"{d['driver']} ({_money(d['amount'])})" for d in drivers[1:3])
        reply = (
            f"The biggest driver is {top['driver']} in {top['account']}, moving {_money(top['amount'])} "
            f"({_money(top['prior'])} to {_money(top['current'])})."
        )
        return reply + (f" Next largest: {others}." if others else "")

    if any(w in text for w in ["confiden", "quality", "trust", "sure", "reliab"]):
        reply = (
            f"Overall confidence is {round(analysis['confidence'] * 100)}%, with a data quality "
            f"score of {round(analysis['data_quality_score'] * 100)}%."
        )
        if analysis.get("grounding_badge"):
            reply += f" Grounding check: {analysis['grounding_badge']}."
        return reply

    if any(w in text for w in ["revenue", "total", "how much", "number"]):
        return (
            f"Revenue went from {_money(prior['revenue'])} in {prior['label']} to "
            f"{_money(current['revenue'])} in {current['label']}."
        )

    if text.strip(" !.?") in {"hi", "hello", "hey"}:
        return "Hi! Ask me about drivers, risks, confidence, or revenue for this run."

    return (
        f"{analysis['headline']} {analysis.get('summary', '')} "
        "Ask about a specific driver, risk, or the confidence score for more detail."
    ).strip()


def _llm_reply(message: str, history: list[ChatMessage], analysis: dict) -> str:
    run_data = {k: v for k, v in analysis.items() if k not in {"agent_timeline", "report_markdown"}}
    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in history[-MAX_HISTORY_TURNS:])
    user = (
        f"RUN DATA JSON:\n{json.dumps(run_data, default=str)}\n\n"
        f"CONVERSATION SO FAR:\n{transcript or '(none)'}\n\n"
        f"USER QUESTION: {message}"
    )
    response = llm.complete(
        task="chat",
        system=SYSTEM_PROMPT,
        user=user,
        max_tokens=400,
        mock_fn=lambda: _rule_based_reply(message, analysis),
    )
    return response.text.strip()


@router.post("/chat")
def chat(
    body: ChatRequest, user_id: str = Depends(auth0_setup.get_current_user_id)
) -> dict:
    analysis = to_frontend_analysis(get_run_or_404(body.run_id, user_id=user_id))
    try:
        reply = _llm_reply(body.message, body.history, analysis)
    except llm.LLMError as exc:
        logger.warning("chat LLM failed, using rule-based reply: %s", exc)
        reply = _rule_based_reply(body.message, analysis)
    return {"reply": reply or _rule_based_reply(body.message, analysis)}
