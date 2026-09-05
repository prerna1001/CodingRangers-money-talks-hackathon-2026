"""Unit tests for services/memory_store.py (lifecycle, plan section 8.3)
and agents/memory_agent.py (relevance matching + conflict detection,
plan section 8.4).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents import memory_agent
from config import (
    MEMORY_CONFIRM_AFTER_CORROBORATIONS,
    MEMORY_DISPUTE_AFTER_CONTRADICTIONS,
    MEMORY_RETIRE_AFTER_CONTRADICTIONS,
)
from models.schemas import (
    CanonicalTransaction,
    Fact,
    Memory,
    MemoryScope,
    MemoryStatus,
    MemoryType,
)
from services.memory_store import MemoryStore


def _make_memory(**overrides) -> Memory:
    now = datetime.now(timezone.utc)
    defaults = dict(
        memory_id="mem_test_1",
        company_id="demo_saas",
        memory_type=MemoryType.BUSINESS_PATTERN,
        content="Enterprise renewals spike at quarter end.",
        scope=MemoryScope(accounts=["4000"], categories=["enterprise_subscription"]),
        confidence=0.5,
        status=MemoryStatus.CANDIDATE,
        created_at=now,
        last_reinforced_at=now,
    )
    defaults.update(overrides)
    return Memory(**defaults)


@pytest.fixture()
def store(tmp_path):
    return MemoryStore(tmp_path / "memory_test.db")


def test_create_and_get_roundtrip(store):
    memory = _make_memory()
    store.create(memory)
    fetched = store.get(memory.memory_id)
    assert fetched is not None
    assert fetched.content == memory.content


def test_corroboration_confirms_after_threshold(store):
    memory = _make_memory()
    store.create(memory)
    for i in range(MEMORY_CONFIRM_AFTER_CORROBORATIONS):
        updated = store.corroborate(memory.memory_id, f"run_{i}")
    assert updated.status == MemoryStatus.CONFIRMED
    assert updated.corroboration_count == MEMORY_CONFIRM_AFTER_CORROBORATIONS
    assert updated.confidence > 0.5


def test_contradiction_disputes_then_retires(store):
    memory = _make_memory(status=MemoryStatus.CONFIRMED, confidence=0.8)
    store.create(memory)
    for _ in range(MEMORY_DISPUTE_AFTER_CONTRADICTIONS):
        updated = store.contradict(memory.memory_id)
    assert updated.status == MemoryStatus.DISPUTED
    for _ in range(MEMORY_RETIRE_AFTER_CONTRADICTIONS - MEMORY_DISPUTE_AFTER_CONTRADICTIONS):
        updated = store.contradict(memory.memory_id)
    assert updated.status == MemoryStatus.RETIRED
    assert updated.confidence < 0.8


def test_user_edited_memory_is_locked_from_auto_retirement(store):
    memory = _make_memory(status=MemoryStatus.CONFIRMED, user_edited=True, confidence=0.9)
    store.create(memory)
    for _ in range(5):
        updated = store.contradict(memory.memory_id)
    assert updated.status == MemoryStatus.CONFIRMED  # never demoted -- user_edited locks it


def test_retrievable_for_run_excludes_retired_and_low_confidence(store):
    confirmed = _make_memory(memory_id="mem_a", status=MemoryStatus.CONFIRMED, confidence=0.8)
    retired = _make_memory(memory_id="mem_b", status=MemoryStatus.RETIRED, confidence=0.9)
    low_conf = _make_memory(memory_id="mem_c", status=MemoryStatus.CONFIRMED, confidence=0.1)
    for m in (confirmed, retired, low_conf):
        store.create(m)
    retrievable_ids = {m.memory_id for m in store.retrievable_for_run("demo_saas")}
    assert retrievable_ids == {"mem_a"}


def test_decay_unobserved_shrinks_confidence_but_skips_user_edited(store):
    observed = _make_memory(memory_id="mem_observed", confidence=0.8)
    unobserved = _make_memory(memory_id="mem_unobserved", confidence=0.8)
    locked = _make_memory(memory_id="mem_locked", confidence=0.8, user_edited=True)
    for m in (observed, unobserved, locked):
        store.create(m)

    store.decay_unobserved("demo_saas", observed_memory_ids={"mem_observed"})

    assert store.get("mem_observed").confidence == 0.8
    assert store.get("mem_unobserved").confidence < 0.8
    assert store.get("mem_locked").confidence == 0.8


# ---------------------------------------------------------------------------
# agents/memory_agent.py -- relevance matching and conflict detection
# ---------------------------------------------------------------------------


def _fact(fact_id: str, label: str, value: float, evidence_txn_ids=None) -> Fact:
    return Fact(
        fact_id=fact_id,
        kind="driver" if "driver" in fact_id else "variance",
        label=label,
        value=value,
        formatted=f"{value:+,.0f}",
        evidence_txn_ids=evidence_txn_ids or [],
        confidence=0.9,
    )


def test_apply_memories_finds_relevant_facts_via_scope():
    memory = _make_memory(scope=MemoryScope(accounts=["4000"]))
    txn = CanonicalTransaction(
        txn_id="t1",
        source_file_id="f1",
        source_row=1,
        posted_date="2026-08-01",
        period_id="2026-08",
        account_id="4000",
        account_name="Subscription revenue",
        account_type="revenue",
        category="enterprise_subscription",
        amount=1000.0,
    )
    fact = _fact("f_driver_1", "Enterprise expansion", 42000.0, evidence_txn_ids=["t1"])
    applications = memory_agent.apply_memories([memory], [fact], transactions=[txn])
    assert len(applications) == 1
    assert applications[0].relevant_facts == [fact]
    assert not applications[0].conflict


def test_apply_memories_flags_conflict_when_expected_spike_absent():
    memory = _make_memory(content="Enterprise renewals spike at quarter end.")
    unrelated_fact = _fact("f_other", "Completely unrelated payroll change", -500.0)
    applications = memory_agent.apply_memories([memory], [unrelated_fact], transactions=[])
    assert applications[0].conflict is True
    assert "did not occur" in applications[0].note


def test_derive_candidate_memories_only_from_high_confidence_drivers():
    high_conf_driver = _fact("f_driver_good", "Enterprise expansion", 42000.0)
    high_conf_driver.confidence = 0.9
    low_conf_driver = _fact("f_driver_bad", "Noisy driver", 500.0)
    low_conf_driver.confidence = 0.5
    variance = _fact("f_variance", "Revenue change", 28000.0)

    candidates = memory_agent.derive_candidate_memories(
        company_id="demo_saas", facts=[high_conf_driver, low_conf_driver, variance]
    )
    assert len(candidates) == 1
    assert "Enterprise expansion" in candidates[0].content
    assert candidates[0].status == MemoryStatus.CANDIDATE
