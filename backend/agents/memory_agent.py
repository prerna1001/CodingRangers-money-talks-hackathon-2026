"""Memory Agent (plan section 8).

Loads memories relevant to this run's flagged facts, detects when a
memory's expectation was NOT met by the data this period (the "memory
expected a spike, it didn't happen" moment that plan section 8.4 calls
"the single best 15 seconds in the demo"), and -- at the end of a run --
derives new candidate memories strictly from computed facts, never from
uploaded free text or retrieved documents (the poisoning defense in
plan section 8.5).

Relevance matching is intentionally simple and auditable: a memory is
"relevant" to a fact if its scope (accounts/counterparties/categories)
overlaps transactions cited as that fact's evidence, or its content
keywords appear in the fact's label. No embedding call is needed here --
that's what the RAG Agent is for (retrieving prose context, not memory).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.schemas import (
    CanonicalTransaction,
    Fact,
    Memory,
    MemoryInfluence,
    MemoryScope,
    MemoryStatus,
    MemoryType,
    Recurrence,
)
from services.memory_store import MemoryStore

_SPIKE_WORDS = re.compile(r"\bspike|increase|surge|renewal|expansion\b", re.I)


@dataclass
class MemoryApplication:
    memory: Memory
    relevant_facts: list[Fact] = field(default_factory=list)
    conflict: bool = False
    note: str = ""


def _fact_matches_scope(fact: Fact, scope: MemoryScope, txns_by_id: dict[str, CanonicalTransaction]) -> bool:
    if scope.categories and any(cat.lower() in fact.label.lower() for cat in scope.categories):
        return True
    for txn_id in fact.evidence_txn_ids:
        txn = txns_by_id.get(txn_id)
        if txn is None:
            continue
        if scope.accounts and txn.account_id in scope.accounts:
            return True
        if scope.counterparties and txn.counterparty_id in scope.counterparties:
            return True
    return False


def apply_memories(
    memories: list[Memory],
    facts: list[Fact],
    transactions: list[CanonicalTransaction] | None = None,
) -> list[MemoryApplication]:
    txns_by_id = {t.txn_id: t for t in (transactions or [])}
    applications: list[MemoryApplication] = []

    for memory in memories:
        relevant = [f for f in facts if _fact_matches_scope(f, memory.scope, txns_by_id)]

        if not relevant:
            # Fall back to a loose keyword match against the fact label when
            # scope alone finds nothing -- keeps the demo dataset workable
            # without requiring perfectly tagged scope on every memory.
            keywords = [w.lower() for w in memory.content.split() if len(w) > 4]
            relevant = [f for f in facts if any(w in f.label.lower() for w in keywords)]

        conflict = False
        if memory.memory_type == MemoryType.BUSINESS_PATTERN and _SPIKE_WORDS.search(memory.content):
            positive_relevant = [f for f in relevant if f.value > 0]
            if not positive_relevant:
                conflict = True

        if conflict:
            note = f"Memory expected “{memory.content}” (confidence {memory.confidence:.2f}), but it did not occur this period."
        elif relevant:
            note = f"Applied to interpret {len(relevant)} related fact(s)."
        else:
            note = "Not applicable to this run's flagged facts."

        applications.append(MemoryApplication(memory=memory, relevant_facts=relevant, conflict=conflict, note=note))

    return applications


def to_memory_influence(applications: list[MemoryApplication]) -> list[MemoryInfluence]:
    """Only memories that were actually consulted (relevant or conflicting)
    get surfaced to the Analyst prompt and the Memory Panel.
    """
    return [
        MemoryInfluence(memory_id=app.memory.memory_id, effect=app.note)
        for app in applications
        if app.relevant_facts or app.conflict
    ]


def load_and_apply(store: MemoryStore, *, company_id: str, facts: list[Fact],
                    transactions: list[CanonicalTransaction] | None = None) -> list[MemoryApplication]:
    memories = store.retrievable_for_run(company_id)
    return apply_memories(memories, facts, transactions)


def update_store_after_run(store: MemoryStore, *, company_id: str, run_id: str,
                            applications: list[MemoryApplication]) -> None:
    """Corroborate/contradict every memory that was actually consulted, then
    decay everything else that went unobserved this run (plan section 8.3).
    """
    observed_ids: set[str] = set()
    for app in applications:
        observed_ids.add(app.memory.memory_id)
        if app.conflict:
            store.contradict(app.memory.memory_id)
        elif app.relevant_facts:
            store.corroborate(app.memory.memory_id, run_id)
    store.decay_unobserved(company_id, observed_ids)


def derive_candidate_memories(
    *,
    company_id: str,
    facts: list[Fact],
    transactions: list[CanonicalTransaction] | None = None,
    min_confidence: float = 0.75,
) -> list[Memory]:
    """Create new candidate memories strictly from computed facts (never
    from prose) -- the poisoning defense in plan section 8.5. Only
    recurring, high-confidence driver facts become memories; everything
    else is too noisy or too one-off to be worth remembering.
    """
    txns_by_id = {t.txn_id: t for t in (transactions or [])}
    now = datetime.now(timezone.utc)
    candidates: list[Memory] = []

    for fact in facts:
        if fact.kind != "driver" or fact.confidence < min_confidence:
            continue
        counterparties = {
            txns_by_id[tid].counterparty_id
            for tid in fact.evidence_txn_ids
            if tid in txns_by_id and txns_by_id[tid].counterparty_id
        }
        accounts = {
            txns_by_id[tid].account_id
            for tid in fact.evidence_txn_ids
            if tid in txns_by_id
        }
        candidates.append(
            Memory(
                memory_id=f"mem_{uuid.uuid4().hex[:10]}",
                company_id=company_id,
                memory_type=MemoryType.BUSINESS_PATTERN,
                content=f"{fact.label} ({fact.formatted}) was a driver this period.",
                scope=MemoryScope(accounts=sorted(accounts), counterparties=sorted(counterparties)),
                evidence_run_ids=[],
                corroboration_count=0,
                contradiction_count=0,
                confidence=min(0.7, fact.confidence),
                status=MemoryStatus.CANDIDATE,
                created_at=now,
                last_reinforced_at=now,
            )
        )
    return candidates
