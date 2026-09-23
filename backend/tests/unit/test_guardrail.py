"""Unit tests for agents/guardrail.py (plan sections 6.6, 10.1, 10.2).
Runs entirely in LLM_MOCK_MODE (no API key needed / no network calls).
"""

from __future__ import annotations

from datetime import date

from agents import guardrail
from models.schemas import (
    Claim,
    ClaimType,
    Driver,
    Explanation,
    Fact,
    GuardrailStatus,
    QAReport,
    ReconciliationReport,
    RunSafety,
)

FACTS = [
    Fact(
        fact_id="f_rev",
        kind="variance",
        label="Revenue, month over month",
        value=28000.0,
        formatted="+$28.0K",
        pct=0.18,
        confidence=0.9,
    )
]


def _qa_report(*, status=RunSafety.PASS, score=1.0, warnings=None):
    return QAReport(
        status=status,
        data_quality_score=score,
        reconciliation=ReconciliationReport(by_account=[], worst_difference_pct=0.0),
        warnings=warnings or [],
        blocking_issues=[] if status != RunSafety.BLOCKED else ["reconciliation failed"],
        safe_to_analyze=status != RunSafety.BLOCKED,
    )


def _clean_explanation():
    return Explanation(
        headline="Revenue increased 18% month over month.",
        summary="Driven by broad growth.",
        claims=[Claim(text="Revenue increased $28.0K, or 18%.", fact_ids=["f_rev"], claim_type=ClaimType.FACT)],
        drivers=[Driver(driver="Overall growth", amount=28000.0, share_of_gross_change_pct=100.0, confidence=0.9)],
    )


def test_clean_explanation_is_approved():
    result = guardrail.review(
        explanation=_clean_explanation(), facts=FACTS, known_entities=set(), qa_report=_qa_report()
    )
    assert result.status == GuardrailStatus.APPROVED
    assert result.grounding.grounding_rate == 1.0


def test_ungrounded_explanation_needs_revision_with_feedback():
    explanation = _clean_explanation()
    explanation.claims.append(
        Claim(text="Revenue actually grew $999.0K.", fact_ids=["f_rev"], claim_type=ClaimType.FACT)
    )
    result = guardrail.review(
        explanation=explanation, facts=FACTS, known_entities=set(), qa_report=_qa_report()
    )
    assert result.status == GuardrailStatus.NEEDS_REVISION
    assert result.revision_feedback  # concrete, actionable feedback for the Analyst's retry


def test_blocked_qa_short_circuits_before_grounding_matters():
    result = guardrail.review(
        explanation=_clean_explanation(),
        facts=FACTS,
        known_entities=set(),
        qa_report=_qa_report(status=RunSafety.BLOCKED, score=0.2),
    )
    assert result.status == GuardrailStatus.BLOCKED_DUE_TO_DATA_QUALITY


def test_warnings_downgrade_to_approved_with_caveats():
    from models.schemas import QAWarning, WarningSeverity

    result = guardrail.review(
        explanation=_clean_explanation(),
        facts=FACTS,
        known_entities=set(),
        qa_report=_qa_report(warnings=[QAWarning(code="x", message="minor issue", severity=WarningSeverity.LOW)]),
    )
    assert result.status == GuardrailStatus.APPROVED_WITH_CAVEATS


def test_overconfident_driver_is_capped_to_approved_with_caveats():
    explanation = _clean_explanation()
    explanation.drivers[0].confidence = 0.99
    # A caveat is present so the mock LLM reviewer's own "missing caveats
    # for imperfect data quality" heuristic doesn't also fire and mask
    # which check we're actually testing (the confidence-cap logic below).
    explanation.risks_or_caveats.append("Data quality for this period is imperfect.")
    result = guardrail.review(
        explanation=explanation,
        facts=FACTS,
        known_entities=set(),
        qa_report=_qa_report(score=0.5),  # confidence cap = 0.5 + slack, driver at 0.99 exceeds it
    )
    assert result.status == GuardrailStatus.APPROVED_WITH_CAVEATS
