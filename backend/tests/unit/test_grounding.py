"""Unit tests for services/grounding.py -- the numeric grounding verifier
(plan section 10.1). This is the highest-value module in the agentic
pipeline, so it gets the most direct coverage: a clean explanation must
verify at 100%, and each of the three violation types must be caught
independently.
"""

from __future__ import annotations

from models.schemas import (
    Basis,
    BasisPoint,
    Claim,
    ClaimType,
    Driver,
    DriverEvidence,
    Explanation,
    Fact,
    GroundingViolationType,
)
from services import grounding

FACTS = [
    Fact(
        fact_id="f_rev_change",
        kind="variance",
        label="Revenue, month over month",
        value=28000.0,
        formatted="+$28.0K",
        pct=0.18,
        basis=Basis(
            current=BasisPoint(period="2026-08", value=183000.0),
            prior=BasisPoint(period="2026-07", value=155000.0),
        ),
        evidence_txn_ids=["t1", "t2"],
        evidence_count=412,
        confidence=0.9,
    ),
    Fact(
        fact_id="f_driver",
        kind="driver",
        label="Enterprise expansion",
        value=42000.0,
        formatted="+$42.0K",
        evidence_txn_ids=["t1"],
        evidence_count=1,
        confidence=0.91,
    ),
]

KNOWN_ENTITIES = {"Northwind Labs"}


def _clean_explanation() -> Explanation:
    return Explanation(
        headline="Revenue increased 18% month over month.",
        summary="Enterprise expansion drove the increase.",
        claims=[
            Claim(text="Revenue increased $28.0K, or 18%.", fact_ids=["f_rev_change"], claim_type=ClaimType.FACT),
            Claim(text="Enterprise expansion contributed $42.0K.", fact_ids=["f_driver"], claim_type=ClaimType.FACT),
        ],
        drivers=[
            Driver(
                driver="Enterprise expansion",
                amount=42000.0,
                share_of_gross_change_pct=100.0,
                evidence=[DriverEvidence(counterparty_name="Northwind Labs", amount=42000.0, txn_ids=["t1"])],
            )
        ],
    )


def test_clean_explanation_is_fully_grounded():
    report = grounding.verify(_clean_explanation(), FACTS, KNOWN_ENTITIES)
    assert report.total_numbers == 3
    assert report.grounded_numbers == 3
    assert report.grounding_rate == 1.0
    assert report.violations == []
    assert not report.has_critical_violation


def test_ungrounded_number_is_caught():
    explanation = _clean_explanation()
    explanation.claims.append(
        Claim(text="Revenue actually grew $999.0K.", fact_ids=["f_rev_change"], claim_type=ClaimType.FACT)
    )
    report = grounding.verify(explanation, FACTS, KNOWN_ENTITIES)
    assert any(v.type == GroundingViolationType.UNGROUNDED_NUMBER for v in report.violations)
    assert report.has_critical_violation


def test_hallucinated_entity_is_caught():
    explanation = _clean_explanation()
    explanation.drivers[0].evidence.append(
        DriverEvidence(counterparty_name="Fake Corp Inc", amount=1000.0, txn_ids=[])
    )
    report = grounding.verify(explanation, FACTS, KNOWN_ENTITIES)
    assert report.entity_check.hallucinated == 1
    assert any(v.type == GroundingViolationType.HALLUCINATED_ENTITY for v in report.violations)


def test_direction_error_is_caught():
    explanation = _clean_explanation()
    explanation.claims.append(
        Claim(text="Revenue decreased $28.0K month over month.", fact_ids=["f_rev_change"], claim_type=ClaimType.FACT)
    )
    report = grounding.verify(explanation, FACTS, KNOWN_ENTITIES)
    assert any(v.type == GroundingViolationType.DIRECTION_ERROR for v in report.violations)


def test_uncited_fact_claim_is_caught_even_bypassing_pydantic_validation():
    # Claim's own validator normally blocks this; construct via model_construct
    # to exercise the verifier's own defense-in-depth check independently.
    explanation = _clean_explanation()
    bad_claim = Claim.model_construct(text="Something happened.", fact_ids=[], claim_type=ClaimType.FACT)
    explanation.claims.append(bad_claim)
    report = grounding.verify(explanation, FACTS, KNOWN_ENTITIES)
    assert any(v.type == GroundingViolationType.UNCITED_CLAIM for v in report.violations)


def test_claim_model_rejects_uncited_fact_claim_at_construction():
    import pytest

    with pytest.raises(ValueError):
        Claim(text="Something happened.", fact_ids=[], claim_type=ClaimType.FACT)


def test_extract_numbers_handles_currency_percent_and_multiples():
    numbers = grounding.extract_numbers("Revenue grew $42.0K, or 18%, roughly 1.5x last year across three accounts.")
    assert 42000.0 in numbers
    assert 18.0 in numbers
    assert 1.5 in numbers
    assert 3.0 in numbers


# ---------------------------------------------------------------------------
# Regressions: contra-revenue accounts (refunds, discounts, returns).
# Both of these were live false positives that rejected a factually correct
# analyst explanation three times and dumped the run into the template
# fallback -- see the "Refunds increased $5,000 from -$12,000 to -$17,000"
# case on the e-commerce dataset.
# ---------------------------------------------------------------------------

REFUND_FACT = Fact(
    fact_id="f_refunds",
    kind="variance",
    label="Refunds, period over period",
    value=-5000.0,
    formatted="-$5.0K",
    basis=Basis(
        current=BasisPoint(period="2026-08", value=-17000.0),
        prior=BasisPoint(period="2026-07", value=-12000.0),
    ),
    confidence=0.9,
)


def test_growing_refunds_described_as_increase_is_not_a_direction_error():
    explanation = Explanation(
        headline="Refunds grew.",
        summary="Refunds grew.",
        claims=[
            Claim(
                text="Refunds increased $5,000 from -$12,000 in July to -$17,000 in August.",
                fact_ids=["f_refunds"],
                claim_type=ClaimType.FACT,
            )
        ],
    )
    report = grounding.verify(explanation, [REFUND_FACT], set())
    assert report.direction_check.errors == 0
    assert not report.has_critical_violation


def test_negative_basis_values_cited_in_prose_are_grounded():
    """Prose writes a negative balance as "-$12,000"; the currency token
    parses as +12000, so the abs() variants of basis values must be
    groundable or a correct citation reads as invented.
    """
    explanation = Explanation(
        headline="Refunds grew.",
        summary="Refunds grew.",
        claims=[
            Claim(
                text="Refunds moved from -$12,000 to -$17,000.",
                fact_ids=["f_refunds"],
                claim_type=ClaimType.FACT,
            )
        ],
    )
    report = grounding.verify(explanation, [REFUND_FACT], set())
    assert report.grounding_rate == 1.0
    assert report.violations == []


def test_shrinking_refunds_described_as_increase_is_still_an_error():
    """The check must stay useful -- only the contra-account reading was
    wrong, not the concept.
    """
    shrinking = REFUND_FACT.model_copy(
        update={
            "value": 5000.0,
            "basis": Basis(
                current=BasisPoint(period="2026-08", value=-7000.0),
                prior=BasisPoint(period="2026-07", value=-12000.0),
            ),
        }
    )
    explanation = Explanation(
        headline="Refunds grew.",
        summary="Refunds grew.",
        claims=[
            Claim(text="Refunds increased sharply.", fact_ids=["f_refunds"], claim_type=ClaimType.FACT)
        ],
    )
    report = grounding.verify(explanation, [shrinking], set())
    assert report.direction_check.errors == 1


def test_ordinary_account_direction_check_unchanged():
    explanation = Explanation(
        headline="Revenue fell.",
        summary="Revenue fell.",
        claims=[Claim(text="Revenue decreased this month.", fact_ids=["f_rev_change"], claim_type=ClaimType.FACT)],
    )
    report = grounding.verify(explanation, FACTS, set())
    assert report.direction_check.errors == 1  # cited fact is +28000, prose says decreased
