"""Profile Builder Agent (plan section 6.1).

Turns already-parsed rows into the canonical CompanyProfile. The actual
CSV -> CanonicalTransaction parsing is Codex's `services/csv_parser.py`
(see BACKEND_TASK_SPLIT.md section 2/3) -- this agent picks up from there:
entity alias resolution, free-text sanitization before anything can reach
a prompt, period inference, and the normalization report that makes the
whole step auditable.

Entity resolution prefers Codex's `services/entity_resolver.py` when it
exists; until then it falls back to a stdlib difflib fuzzy match so this
agent (and the whole downstream pipeline) is runnable standalone.
"""

from __future__ import annotations

import difflib

from models.schemas import (
    AvailableFile,
    CanonicalTransaction,
    CompanyProfile,
    CompanyProfileCore,
    PeriodInfo,
    PeriodSummary,
)
from services import injection_filter

FUZZY_MATCH_THRESHOLD = 0.88


def _resolve_via_codex_resolver(name: str, known_aliases: dict[str, list[str]]) -> str | None:
    try:
        from services import entity_resolver  # Codex's module -- may not exist yet
    except ImportError:
        return None
    return entity_resolver.resolve(name, known_aliases)  # type: ignore[attr-defined]


def _resolve_via_fallback(name: str, alias_lookup: dict[str, str]) -> str | None:
    name_lower = name.strip().lower()
    if name_lower in alias_lookup:
        return alias_lookup[name_lower]
    close = difflib.get_close_matches(name_lower, alias_lookup.keys(), n=1, cutoff=FUZZY_MATCH_THRESHOLD)
    return alias_lookup[close[0]] if close else None


def _resolve_entities(
    transactions: list[CanonicalTransaction],
    known_aliases: dict[str, list[str]],
    normalization_report: list[str],
) -> int:
    alias_lookup = {
        alias.strip().lower(): canonical_id
        for canonical_id, aliases in known_aliases.items()
        for alias in aliases
    }
    resolved = 0
    for txn in transactions:
        if not txn.counterparty_name or txn.counterparty_id:
            continue
        canonical_id = _resolve_via_codex_resolver(
            txn.counterparty_name, known_aliases
        ) or _resolve_via_fallback(txn.counterparty_name, alias_lookup)
        if canonical_id:
            txn.counterparty_id = canonical_id
            resolved += 1
    if resolved:
        normalization_report.append(f"Resolved {resolved} counterparty name(s) to canonical entity ids")
    return resolved


def _sanitize_memos(
    transactions: list[CanonicalTransaction], normalization_report: list[str]
) -> None:
    quarantined = injection_filter.scan_transactions(transactions)
    for q in quarantined:
        normalization_report.append(
            f"Quarantined suspicious memo at source_row={q.source_row} "
            f"(patterns: {[m.pattern_name for m in q.matches]})"
        )
    for txn in transactions:
        txn.memo = injection_filter.sanitize(txn.memo)


def _infer_periods(period_summaries: list[PeriodSummary]) -> list[PeriodInfo]:
    return [
        PeriodInfo(period_id=ps.period_id, start_date=ps.start_date, end_date=ps.end_date)
        for ps in sorted(period_summaries, key=lambda p: p.period_id)
    ]


def collect_known_entities(transactions: list[CanonicalTransaction]) -> set[str]:
    """The closed vocabulary of real counterparty names -- used by the
    Guardrail Agent's hallucinated-entity check (plan section 10.1) so it
    never has to guess via free-text NER.
    """
    return {t.counterparty_name for t in transactions if t.counterparty_name}


def build_profile(
    *,
    base: CompanyProfileCore,
    transactions: list[CanonicalTransaction],
    period_summaries: list[PeriodSummary],
    available_files: list[AvailableFile],
    known_aliases: dict[str, list[str]] | None = None,
) -> CompanyProfile:
    """Build the canonical CompanyProfile from already-parsed inputs.

    `transactions` are mutated in place (memo sanitization, counterparty_id
    resolution) -- callers should treat the returned profile and the input
    transaction list as the paired, normalized output of this step.
    """
    known_aliases = known_aliases or {}
    normalization_report: list[str] = []

    _sanitize_memos(transactions, normalization_report)
    _resolve_entities(transactions, known_aliases, normalization_report)

    return CompanyProfile(
        company_profile=base,
        periods=_infer_periods(period_summaries),
        available_files=available_files,
        entity_aliases=known_aliases,
        normalization_report=normalization_report,
    )
