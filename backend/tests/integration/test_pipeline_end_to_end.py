"""Full-pipeline integration test (plan section 11, "Full SaaS demo run").

Runs the entire LangGraph workflow -- Profile Builder through Memory
Update -- against the checked-in demo fixture, using Codex's real
analytics engine when available (falls back to the fixture fact table
otherwise, per graph/workflow.py's compute_facts()). Runs in
LLM_MOCK_MODE so it needs no network access or API key.

This is the walking-skeleton exit criterion from the plan's Day 2 /
hour-16 milestones (section 19.2/19.3): upload -> run -> explanation on
screen, end to end, with memory persisting across runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph.workflow import run_pipeline
from models.schemas import CanonicalTransaction, CompanyProfileCore, GuardrailStatus, PeriodSummary
from services.memory_store import MemoryStore

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture()
def demo_dataset():
    data = json.loads((FIXTURES_DIR / "saas_2026_08_transactions.json").read_text())
    transactions = [CanonicalTransaction(**t) for t in data["transactions"]]
    period_summaries = [PeriodSummary(**p) for p in data["period_summaries"]]
    profile_core = CompanyProfileCore(
        company_id="demo_saas_test",
        company_name="DemoCo",
        industry="B2B SaaS",
        business_model="subscription",
    )
    return transactions, period_summaries, profile_core


@pytest.fixture(autouse=True)
def isolated_memory_db(tmp_path, monkeypatch):
    """Point the Memory Agent's store at a throwaway file so this test
    doesn't read or pollute the developer's real ledgerlight_memory.db.
    """
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setattr("services.memory_store._DEFAULT_DB_PATH", str(db_path))
    yield db_path


def test_pipeline_runs_end_to_end_and_produces_a_grounded_approved_explanation(demo_dataset):
    transactions, period_summaries, profile_core = demo_dataset

    final_state = run_pipeline(
        company_id="demo_saas_test",
        current_period="2026-08",
        prior_period="2026-07",
        company_profile_core=profile_core,
        transactions=transactions,
        period_summaries=period_summaries,
        known_aliases={"vendor:aws": ["AWS", "Amazon Web Services", "AMZN AWS"]},
    )

    assert final_state["qa_report"].safe_to_analyze is True
    assert final_state["facts"], "analytics engine (real or fixture) must produce at least one fact"
    assert final_state["explanation"] is not None

    grounding_report = final_state["grounding_report"]
    assert grounding_report.grounding_rate == 1.0
    assert not grounding_report.has_critical_violation

    assert final_state["guardrail_result"].status in {
        GuardrailStatus.APPROVED,
        GuardrailStatus.APPROVED_WITH_CAVEATS,
    }

    # Every agent that should run for a clean, safe-to-analyze dataset
    # actually ran (this is what would silently break if a parallel-branch
    # reducer regressed back to last-write-wins -- see models/schemas.py).
    ran_agents = {entry.agent for entry in final_state["timeline"]}
    assert {"profile_builder", "data_qa", "memory", "rag", "analytics_engine", "analyst", "guardrail",
            "stress_test", "report_writer", "memory_update"} <= ran_agents

    assert final_state["report_markdown"]
    assert final_state["dashboard_payload"]["grounding_rate"] == 1.0


def test_memory_persists_and_is_used_across_two_runs(demo_dataset, isolated_memory_db):
    transactions, period_summaries, profile_core = demo_dataset
    kwargs = dict(
        company_id="demo_saas_test",
        current_period="2026-08",
        prior_period="2026-07",
        company_profile_core=profile_core,
        transactions=transactions,
        period_summaries=period_summaries,
    )

    first_run = run_pipeline(**kwargs)
    assert len(first_run["memories"]) == 0  # nothing to load on a cold store

    store = MemoryStore(isolated_memory_db)
    assert len(store.list_for_company("demo_saas_test")) > 0, "memory_update should have created candidates"

    second_run = run_pipeline(**kwargs)
    assert len(second_run["memories"]) > 0, "second run should load memories the first run created"
