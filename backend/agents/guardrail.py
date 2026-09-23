"""Guardrail Agent (plan sections 6.6, 10.1, 10.2). Runs on Sonnet 5 --
deliberately a different model from the Analyst (Opus 5), and it never
sees the Analyst's reasoning, only its output and the fact table. A
reviewer that shares the author's context shares the author's mistakes.

Two layers, in order:
  1. The deterministic numeric grounding verifier (services/grounding.py)
     runs FIRST. Any critical violation is an automatic `needs_revision`
     with the specific violations fed back to the Analyst -- no LLM call
     needed to catch this class of failure, and it's instant.
  2. Only if grounding passes does the LLM guardrail review run, checking
     the softer things a regex can't: overconfidence, tone, whether
     caveats are present for incomplete data, whether the output reads
     like financial advice.
"""

from __future__ import annotations

import json
import logging

from config import CONFIDENCE_DATA_QUALITY_SLACK
from models.schemas import (
    CompanyProfile,
    Explanation,
    Fact,
    GroundingReport,
    GuardrailResult,
    GuardrailStatus,
    QAReport,
    RunSafety,
)
from services import grounding, llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an independent reviewer of a financial explanation \
written by another analyst. You did not write it and have not seen its \
reasoning -- only the final text and the same fact table it was built from. \
Your job is to catch what a mechanical grounding check cannot:

- Overconfidence: does the tone claim certainty the data doesn't support?
- Missing caveats: is a known data-quality issue omitted from the caveats?
- Advice-shaped language: does anything read as a recommendation \
("you should...", "consider doing...") rather than an explanation of what \
happened? Financial/investment/tax/legal advice is not permitted.
- Tone: is language measured and specific, or vague and hand-wavy?

Respond with ONLY a JSON object:
{"approved": bool, "notes": [str], "revision_feedback": [str]}
`revision_feedback` should be empty if approved is true, and should list \
concrete, actionable fixes if false.
"""


def _mock_review(explanation: Explanation, qa_report: QAReport) -> str:
    notes = []
    if qa_report.data_quality_score < 0.9 and not explanation.risks_or_caveats:
        notes.append("Data quality is imperfect but no caveats were included.")
    approved = not notes
    return json.dumps({"approved": approved, "notes": notes, "revision_feedback": notes})


def _llm_review(
    explanation: Explanation, facts: list[Fact], qa_report: QAReport, token_usage: dict[str, int] | None
) -> tuple[bool, list[str], list[str]]:
    user_prompt = "\n".join(
        [
            "## Explanation under review",
            explanation.model_dump_json(indent=2),
            "",
            "## Fact table it was built from",
            json.dumps([f.model_dump() for f in facts], indent=2, default=str),
            "",
            "## Data quality report",
            qa_report.model_dump_json(indent=2),
        ]
    )
    response = llm.complete(
        task="guardrail",
        system=_SYSTEM_PROMPT,
        user=user_prompt,
        mock_fn=lambda: _mock_review(explanation, qa_report),
    )
    if token_usage is not None:
        llm.record_usage(token_usage, response)

    text = response.text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    payload = json.loads(text[start : end + 1])
    return bool(payload.get("approved", False)), payload.get("notes", []), payload.get("revision_feedback", [])


def review(
    *,
    explanation: Explanation,
    facts: list[Fact],
    known_entities: set[str],
    qa_report: QAReport,
    token_usage: dict[str, int] | None = None,
) -> GuardrailResult:
    grounding_report = grounding.verify(explanation, facts, known_entities)

    if qa_report.status == RunSafety.BLOCKED:
        return GuardrailResult(
            status=GuardrailStatus.BLOCKED_DUE_TO_DATA_QUALITY,
            grounding=grounding_report,
            notes=["Data QA blocked this run; no explanation should have reached the guardrail."],
        )

    if grounding_report.has_critical_violation:
        feedback = [v.detail for v in grounding_report.violations if v.severity == "critical"]
        return GuardrailResult(
            status=GuardrailStatus.NEEDS_REVISION,
            grounding=grounding_report,
            notes=["Numeric grounding verifier found critical violations."],
            revision_feedback=feedback,
        )

    try:
        approved, notes, revision_feedback = _llm_review(explanation, facts, qa_report, token_usage)
    except Exception as exc:  # noqa: BLE001 - provider outage must not kill the run
        # Plan section 6.6: this agent "fails to the deterministic verifier
        # alone". The numeric grounding pass above already ran and found no
        # critical violations, so the explanation is still provably grounded
        # -- we just lose the softer tone/caveat review. Far better than
        # failing a run outright because a provider rate-limited us.
        logger.warning("guardrail LLM review unavailable (%s) -- falling back to grounding-only", exc)
        return GuardrailResult(
            status=GuardrailStatus.APPROVED_WITH_CAVEATS,
            grounding=grounding_report,
            notes=[
                "Reviewer model unavailable; approved on deterministic numeric "
                "grounding alone (all numbers verified against source data)."
            ],
        )

    if not approved:
        # A rejection with no actionable feedback makes the revision loop
        # useless: the Analyst is re-prompted with an identical prompt,
        # produces the same output, and gets rejected again until the cap
        # dumps the run into the template fallback. Reviewers reliably
        # explain themselves in `notes` even when they leave
        # `revision_feedback` empty, so fall back to those -- and never
        # hand back an empty rejection.
        if not revision_feedback:
            revision_feedback = notes or [
                "The reviewer rejected the explanation without specifics. Re-check that every "
                "claim carries a caveat where the data is incomplete, and that no claim overstates "
                "certainty beyond what the facts support."
            ]
        return GuardrailResult(
            status=GuardrailStatus.NEEDS_REVISION,
            grounding=grounding_report,
            notes=notes,
            revision_feedback=revision_feedback,
        )

    # confidence <= data_quality_score + slack (plan section 10.2)
    confidence_cap = qa_report.data_quality_score + CONFIDENCE_DATA_QUALITY_SLACK
    overconfident_drivers = [d for d in explanation.drivers if d.confidence > confidence_cap]
    if overconfident_drivers:
        return GuardrailResult(
            status=GuardrailStatus.APPROVED_WITH_CAVEATS,
            grounding=grounding_report,
            notes=notes + [f"{len(overconfident_drivers)} driver(s) exceeded the data-quality confidence cap; capped in the report."],
        )

    status = GuardrailStatus.APPROVED_WITH_CAVEATS if qa_report.warnings else GuardrailStatus.APPROVED
    return GuardrailResult(status=status, grounding=grounding_report, notes=notes)
