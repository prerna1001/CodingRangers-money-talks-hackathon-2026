"""Report Writer (plan section 6.8). Pure formatting -- renders an already
APPROVED Explanation into the dashboard payload, a Markdown report, and a
45-60 second voice-briefing script. It may not introduce a fact: every
function here only rearranges fields that already exist on the Explanation
and GroundingReport it's given.

Voice script generation happens from the approved explanation only, so
ElevenLabs (services/elevenlabs_client.py) can never speak a claim the
guardrail rejected (plan section 16.2).
"""

from __future__ import annotations

import json

from models.schemas import (
    Explanation,
    GroundingReport,
    GuardrailResult,
    QAReport,
)
from services import llm


def to_markdown(
    *,
    explanation: Explanation,
    current_period: str,
    prior_period: str,
    company_name: str,
    grounding: GroundingReport,
) -> str:
    lines = [
        f"# {company_name} - {prior_period} to {current_period}",
        "",
        f"**{explanation.headline}**",
        "",
        explanation.summary,
        "",
        f"_Grounding: {grounding.grounded_numbers}/{grounding.total_numbers} numbers verified against source data "
        f"({grounding.grounding_rate:.0%})._",
        "",
        "## Drivers",
    ]
    for driver in explanation.drivers:
        lines.append(
            f"- **{driver.driver}**: {driver.amount:+,.0f} "
            f"({driver.share_of_gross_change_pct:.0f}% of gross change, {driver.recurrence.value})"
        )
        for ev in driver.evidence:
            lines.append(f"  - {ev.counterparty_name}: {ev.amount:+,.0f} ({len(ev.txn_ids)} transaction(s))")

    if explanation.risks_or_caveats:
        lines += ["", "## Risks and caveats"]
        lines += [f"- {c}" for c in explanation.risks_or_caveats]

    if explanation.follow_up_questions:
        lines += ["", "## Follow-up questions"]
        lines += [f"- {q}" for q in explanation.follow_up_questions]

    if explanation.memory_influence:
        lines += ["", "## Memory influence"]
        lines += [f"- {m.effect}" for m in explanation.memory_influence]

    lines += [
        "",
        "---",
        "_Generated from synthetic data for demonstration purposes. Not financial, "
        "investment, tax, or legal advice._",
    ]
    return "\n".join(lines)


def to_dashboard_payload(
    *,
    run_id: str,
    explanation: Explanation,
    grounding: GroundingReport,
    guardrail: GuardrailResult,
    qa_report: QAReport,
) -> dict:
    return {
        "run_id": run_id,
        "headline": explanation.headline,
        "summary": explanation.summary,
        "status": guardrail.status.value,
        "grounding_badge": f"{grounding.grounded_numbers}/{grounding.total_numbers} numbers verified",
        "grounding_rate": grounding.grounding_rate,
        "data_quality_score": qa_report.data_quality_score,
        "drivers": [d.model_dump() for d in explanation.drivers],
        "claims": [c.model_dump() for c in explanation.claims],
        "risks_or_caveats": explanation.risks_or_caveats,
        "follow_up_questions": explanation.follow_up_questions,
        "memory_influence": [m.model_dump() for m in explanation.memory_influence],
        "qa_warnings": [w.model_dump() for w in qa_report.warnings],
    }


def to_voice_script(explanation: Explanation, *, max_sentences: int = 6) -> str:
    """A calm, executive-tone 45-60s script (~120-160 words at a natural
    speaking pace) built only from approved content.
    """
    parts = [explanation.headline, explanation.summary]
    fact_claims = [c.text for c in explanation.claims if c.claim_type.value == "fact"]
    parts += fact_claims[: max(0, max_sentences - len(parts))]
    if explanation.risks_or_caveats:
        parts.append(explanation.risks_or_caveats[0])
    parts.append("Full evidence is available in the dashboard.")
    return " ".join(parts)


def to_board_update(
    explanation: Explanation,
    *,
    company_name: str,
    current_period: str,
    token_usage: dict[str, int] | None = None,
) -> str:
    """A short, copyable paragraph -- the "board-ready" export (plan section 15.2)."""
    deterministic = (
        f"{company_name} — {current_period}: {explanation.headline} {explanation.summary} "
        f"Key drivers: {'; '.join(f'{d.driver} ({d.amount:+,.0f})' for d in explanation.drivers[:3])}."
        f"{f' Notable risk: {explanation.risks_or_caveats[0]}' if explanation.risks_or_caveats else ''}"
    )

    system = """You write concise CFO board updates.

Use only the approved explanation JSON supplied by the user. Do not add new
numbers, entities, advice, or recommendations. Return one short paragraph."""
    user = json.dumps(
        {
            "company_name": company_name,
            "current_period": current_period,
            "approved_explanation": explanation.model_dump(),
        },
        default=str,
    )
    response = llm.complete(
        task="report_writer",
        system=system,
        user=user,
        max_tokens=320,
        mock_fn=lambda: deterministic,
    )
    if token_usage is not None:
        llm.record_usage(token_usage, response)
    return response.text.strip()
