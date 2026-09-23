"""Numeric grounding verifier (plan section 10.1).

"The highest-value 80 lines of code in the project." Every number in the
Analyst's generated prose is extracted and matched against the computed
fact table within a small tolerance. An unmatched number is a critical
violation and forces a revision pass -- this runs deterministically,
before the LLM-based guardrail review, and is what makes the dashboard's
"14 / 14 numbers verified" badge (plan section 10.1) true rather than
decorative.

Three more checks ride along because they're nearly free once the claims
are already parsed and structured:
  - uncited_claim   : a `fact` claim with no fact_ids (also enforced by the
                       Explanation model itself; checked again here for
                       defense in depth against hand-built objects).
  - hallucinated_entity : a driver's evidence names an entity outside the
                       known/closed vocabulary.
  - direction_error : prose says "increased" but the cited fact is negative
                       (or vice versa).
"""

from __future__ import annotations

import re

from config import GROUNDING_NUMERIC_TOLERANCE_PCT
from models.schemas import (
    ClaimType,
    DirectionCheck,
    EntityCheck,
    Explanation,
    Fact,
    GroundingReport,
    GroundingViolation,
    GroundingViolationType,
)

_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}

_CURRENCY_RE = re.compile(r"\$\s?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?[KMB]?\b", re.I)
_PERCENT_RE = re.compile(r"-?\d+(?:\.\d+)?\s?%")
_MULTIPLE_RE = re.compile(r"-?\d+(?:\.\d+)?\s?x\b", re.I)
_WORD_NUMBER_RE = re.compile(
    r"\b(" + "|".join(_WORD_NUMBERS) + r")\b\s+(customers?|vendors?|accounts?|transactions?|months?|times?)",
    re.I,
)

_INCREASE_WORDS = re.compile(r"\b(increase[ds]?|rose|grew|growth|up|higher|expansion)\b", re.I)
_DECREASE_WORDS = re.compile(r"\b(decrease[ds]?|fell|declined?|down|lower|churn|contraction|drop(?:ped)?)\b", re.I)


def _parse_numeric_token(token: str) -> float | None:
    token = token.strip()
    if token.startswith("$"):
        body = token[1:].strip()
        suffix = ""
        if body and body[-1].upper() in "KMB":
            suffix = body[-1].upper()
            body = body[:-1]
        body = body.replace(",", "").strip()
        try:
            value = float(body)
        except ValueError:
            return None
        return value * {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
    if token.endswith("%"):
        try:
            return float(token[:-1].strip())
        except ValueError:
            return None
    if token.lower().endswith("x"):
        try:
            return float(token[:-1].strip())
        except ValueError:
            return None
    return None


def extract_numbers(text: str) -> list[float]:
    """Pull every currency amount, percentage, multiple, and small spelled-out
    count out of `text`, normalized to plain floats (see module docstring
    for the exact token grammar this handles).
    """
    found: list[float] = []
    for regex in (_CURRENCY_RE, _PERCENT_RE, _MULTIPLE_RE):
        for match in regex.finditer(text):
            value = _parse_numeric_token(match.group(0))
            if value is not None:
                found.append(value)
    for match in _WORD_NUMBER_RE.finditer(text):
        found.append(float(_WORD_NUMBERS[match.group(1).lower()]))
    return found


def _groundable_values(facts: list[Fact]) -> list[float]:
    values: list[float] = []
    for fact in facts:
        for v in (fact.value, abs(fact.value), fact.value / 1_000, abs(fact.value) / 1_000,
                  fact.value / 1_000_000, abs(fact.value) / 1_000_000):
            values.append(round(v, 4))
        if fact.pct is not None:
            values.append(round(fact.pct, 4))
            values.append(round(fact.pct * 100, 4))
        values.append(float(fact.evidence_count))
        values.append(float(len(fact.evidence_txn_ids)))
        if fact.basis is not None:
            # Absolute variants matter as much here as they do for
            # fact.value above: prose writes a negative balance as
            # "-$12,000", and extract_numbers reads that as +12000
            # (the minus sits outside the currency token). Without the
            # abs() forms, correctly-cited negative balances get
            # reported as ungrounded.
            for basis_value in (fact.basis.current.value, fact.basis.prior.value):
                for v in (basis_value, abs(basis_value), basis_value / 1_000, abs(basis_value) / 1_000):
                    values.append(round(v, 4))
        if fact.significance is not None and fact.significance.z is not None:
            values.append(round(fact.significance.z, 4))
    return values


def _is_grounded(number: float, groundable: list[float]) -> bool:
    for g in groundable:
        tolerance = max(abs(g) * GROUNDING_NUMERIC_TOLERANCE_PCT, 0.5)
        if abs(number - g) <= tolerance:
            return True
    return False


def _fact_increased(fact: Fact) -> bool:
    """Did this fact move 'up' in the sense a finance reader means?

    For an ordinary account, that's simply a positive delta. But contra
    accounts (refunds, discounts, returns) carry negative balances, and
    there "refunds increased" means the balance got *more* negative --
    a negative delta. Judging those by raw sign flags a correct
    statement like "Refunds increased $5,000, from -$12,000 to -$17,000"
    as a direction error, which is exactly backwards.
    """
    if fact.basis is not None:
        current, prior = fact.basis.current.value, fact.basis.prior.value
        if current <= 0 and prior <= 0:
            return abs(current) > abs(prior)
    return fact.value > 0


def _check_direction(claim_text: str, cited_facts: list[Fact]) -> bool:
    """Return True iff a direction mismatch was found (i.e. an error)."""
    says_increase = bool(_INCREASE_WORDS.search(claim_text))
    says_decrease = bool(_DECREASE_WORDS.search(claim_text))
    if says_increase == says_decrease:  # neither, or ambiguous both -- nothing to check
        return False
    for fact in cited_facts:
        if fact.value == 0:
            continue
        # Without a basis we only know the delta's sign, which is not enough
        # to tell "refunds increased" (a -$5K delta on a contra account) from
        # a genuine contradiction. Driver facts carry no basis, so judging
        # them here produced false criticals that rejected correct analyses.
        if fact.basis is None:
            continue
        increased = _fact_increased(fact)
        if says_increase and not increased:
            return True
        if says_decrease and increased:
            return True
    return False


def verify(explanation: Explanation, facts: list[Fact], known_entities: set[str]) -> GroundingReport:
    """Run the full grounding pass over an Analyst-produced Explanation.

    `known_entities` is the closed vocabulary of real counterparty/vendor
    names (assembled by the caller from the fact table's evidence and the
    company profile) -- never inferred via free-text NER.
    """
    facts_by_id = {f.fact_id: f for f in facts}
    groundable = _groundable_values(facts)

    violations: list[GroundingViolation] = []
    total_numbers = 0
    grounded_numbers = 0

    for idx, claim in enumerate(explanation.claims):
        numbers = extract_numbers(claim.text)
        total_numbers += len(numbers)
        for number in numbers:
            if _is_grounded(number, groundable):
                grounded_numbers += 1
            else:
                violations.append(
                    GroundingViolation(
                        type=GroundingViolationType.UNGROUNDED_NUMBER,
                        severity="critical",
                        detail=f"Number {number!r} in claim not found in fact table",
                        claim_index=idx,
                    )
                )

        if claim.claim_type == ClaimType.FACT and not claim.fact_ids:
            violations.append(
                GroundingViolation(
                    type=GroundingViolationType.UNCITED_CLAIM,
                    severity="critical",
                    detail="Claim of type 'fact' has no fact_ids",
                    claim_index=idx,
                )
            )

        cited_facts = [facts_by_id[fid] for fid in claim.fact_ids if fid in facts_by_id]
        if _check_direction(claim.text, cited_facts):
            violations.append(
                GroundingViolation(
                    type=GroundingViolationType.DIRECTION_ERROR,
                    severity="critical",
                    detail="Claim's stated direction contradicts the sign of its cited fact(s)",
                    claim_index=idx,
                )
            )

    entity_checked = 0
    entity_hallucinated = 0
    for driver in explanation.drivers:
        for evidence in driver.evidence:
            entity_checked += 1
            if evidence.counterparty_name not in known_entities:
                entity_hallucinated += 1
                violations.append(
                    GroundingViolation(
                        type=GroundingViolationType.HALLUCINATED_ENTITY,
                        severity="critical",
                        detail=f"Entity '{evidence.counterparty_name}' not in the known entity index",
                    )
                )

    direction_checked = sum(
        1 for c in explanation.claims
        if _INCREASE_WORDS.search(c.text) or _DECREASE_WORDS.search(c.text)
    )
    direction_errors = sum(1 for v in violations if v.type == GroundingViolationType.DIRECTION_ERROR)

    grounding_rate = (grounded_numbers / total_numbers) if total_numbers else 1.0

    return GroundingReport(
        grounded_numbers=grounded_numbers,
        total_numbers=total_numbers,
        grounding_rate=round(grounding_rate, 4),
        violations=violations,
        entity_check=EntityCheck(checked=entity_checked, hallucinated=entity_hallucinated),
        direction_check=DirectionCheck(checked=direction_checked, errors=direction_errors),
    )
