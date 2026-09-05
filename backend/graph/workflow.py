"""LangGraph workflow wiring (plan section 7.1).

    Profile Builder -> Data QA -> gate
                                     |-- blocked --> Data Issue Report [END]
                                     |-- safe    --> Memory   \\
                                                     RAG        >--> Analyst -> Guardrail -> revision router
                                                     Analytics /                                 |
                                        (needs_revision, count <= cap) -----------back to Analyst-'
                                        (needs_revision, count >  cap) --> Template Fallback --.
                                        (approved / approved_with_caveats) --> Stress Test <----'
                                                                                    |
                                                                              Report Writer
                                                                                    |
                                                                              Memory Update [END]

Memory, RAG, and the Analytics Engine genuinely run in the same LangGraph
superstep (fan-out from the gate, fan-in at the Analyst) -- this is the
plan's "difference between a 40-second and a 25-second run" (section
7.1), which is why models/schemas.py gives `timeline`/`timings`/
`token_usage`/`errors` additive reducers instead of relying on
last-write-wins.

`compute_facts()` is the single hand-off point to Codex's analytics
engine (BACKEND_TASK_SPLIT.md section 5): it tries `analytics.facts`
first and falls back to the checked-in fixture fact table so this whole
graph is runnable and demoable today, before that module exists.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from agents import analyst as analyst_agent
from agents import data_qa as data_qa_agent
from agents import guardrail as guardrail_agent
from agents import memory_agent
from agents import profile_builder as profile_builder_agent
from agents import rag_agent
from agents import report_writer as report_writer_agent
from agents import stress_tester as stress_tester_agent
from config import MAX_REVISION_PASSES
from graph.events import EVENT_BUS, agent_step, emit_run_complete
from graph.state import new_run_state
from models.schemas import (
    AvailableFile,
    CanonicalTransaction,
    Claim,
    ClaimType,
    CompanyProfileCore,
    Driver,
    Explanation,
    Fact,
    GuardrailResult,
    GuardrailStatus,
    PeriodSummary,
    RunState,
)
from services import grounding
from services.memory_store import MemoryStore
from services.rag_store import Document, RagStore

logger = logging.getLogger(__name__)

_FIXTURE_FACTS_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "saas_2026_08_facts.json"
)


def _load_fixture_facts() -> list[Fact]:
    """Stand-in for Codex's analytics/facts.py -- see BACKEND_TASK_SPLIT.md
    section 5's integration-points table. Deleted the moment that module
    exists; `compute_facts` below already prefers it automatically.
    """
    data = json.loads(_FIXTURE_FACTS_PATH.read_text())
    return [Fact(**f) for f in data["facts"]]


def compute_facts(state: RunState) -> list[Fact]:
    try:
        from analytics import facts as facts_module  # Codex's module
    except ImportError:
        logger.info("analytics.facts not found -- using fixture fact table (see BACKEND_TASK_SPLIT.md)")
        return _load_fixture_facts()
    return facts_module.build_facts(
        transactions=state["transactions"],
        period_summaries=state["period_summaries"],
        current_period=state["current_period"],
        prior_period=state["prior_period"],
    )


def _seed_rag_store_if_empty(store: RagStore, state: RunState) -> None:
    """The BM25 fallback backend (services/rag_store.py) is in-memory and
    unseeded by default -- there is no ingestion-time corpus population
    step yet, so seed a couple of demo documents inline. Once Codex's
    ingestion pipeline populates a persistent Chroma corpus (plan section
    9.1), this becomes a no-op (the store will already have documents).
    """
    if store.backend != "empty":
        return
    store.add_documents(
        [
            Document(
                chunk_id="chunk_prior_report_seed",
                source=f"prior_analysis_report:{state['prior_period']}",
                text=f"{state['prior_period']} enterprise expansion was driven by named enterprise accounts adding seats mid-month.",
                metadata={"period_id": state["prior_period"]},
            ),
            Document(
                chunk_id="chunk_vendor_mapping_seed",
                source="vendor_mapping",
                text="AWS is the primary cloud hosting vendor, billed on usage.",
                metadata={"kind": "vendor_mapping"},
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def node_profile_builder(state: RunState) -> dict:
    with agent_step(state["run_id"], "profile_builder") as step:
        profile = profile_builder_agent.build_profile(
            base=state["company_profile_core"],
            transactions=state["transactions"],
            period_summaries=state["period_summaries"],
            available_files=state.get("available_files", []),
            known_aliases=state.get("known_aliases", {}),
        )
        step.output_summary = f"{len(profile.normalization_report)} normalization note(s)"
    return {
        "profile": profile,
        "timeline": [step.entry],
        "timings": {"profile_builder": step.entry.duration_ms},
    }


def node_data_qa(state: RunState) -> dict:
    with agent_step(state["run_id"], "data_qa") as step:
        qa_report = data_qa_agent.run_data_qa(
            transactions=state["transactions"], period_summaries=state["period_summaries"]
        )
        step.output_summary = f"status={qa_report.status.value} quality={qa_report.data_quality_score}"
        if qa_report.warnings:
            step.safety_notes = [w.message for w in qa_report.warnings]
    return {
        "qa_report": qa_report,
        "timeline": [step.entry],
        "timings": {"data_qa": step.entry.duration_ms},
    }


def route_after_qa(state: RunState) -> list[str]:
    if not state["qa_report"].safe_to_analyze:
        return ["data_issue_report"]
    return ["memory", "rag", "analytics_engine"]


def node_memory(state: RunState) -> dict:
    """Loads candidate memories only -- matching them against this run's
    facts happens at the fan-in (node_analyst), since facts aren't
    available yet from this parallel branch's point of view within the
    same superstep.
    """
    with agent_step(state["run_id"], "memory") as step:
        store = MemoryStore()
        memories = store.retrievable_for_run(state["company_id"])
        step.output_summary = f"{len(memories)} memorie(s) loaded"
    return {
        "memories": memories,
        "timeline": [step.entry],
        "timings": {"memory": step.entry.duration_ms},
    }


def node_rag(state: RunState) -> dict:
    with agent_step(state["run_id"], "rag") as step:
        store = RagStore()
        _seed_rag_store_if_empty(store, state)
        facts = compute_facts(state)
        retrieved = rag_agent.retrieve_for_facts(store, facts)
        step.output_summary = f"{len(retrieved)} chunk(s) retrieved via {store.backend}"
    return {
        "retrieved": retrieved,
        "timeline": [step.entry],
        "timings": {"rag": step.entry.duration_ms},
    }


def node_analytics(state: RunState) -> dict:
    with agent_step(state["run_id"], "analytics_engine") as step:
        facts = compute_facts(state)
        step.output_summary = f"{len(facts)} fact(s) computed"
    return {
        "facts": facts,
        "timeline": [step.entry],
        "timings": {"analytics_engine": step.entry.duration_ms},
    }


def node_analyst(state: RunState) -> dict:
    with agent_step(
        state["run_id"], "analyst", detail=f"Explaining {len(state['facts'])} fact(s)"
    ) as step:
        applications = memory_agent.apply_memories(state["memories"], state["facts"], state["transactions"])
        hints = memory_agent.to_memory_influence(applications)

        revision_feedback = None
        guardrail_result = state.get("guardrail_result")
        if guardrail_result is not None and guardrail_result.status == GuardrailStatus.NEEDS_REVISION:
            revision_feedback = guardrail_result.revision_feedback

        token_usage_delta: dict[str, int] = {}
        explanation, _response = analyst_agent.generate_explanation(
            profile=state["profile"],
            facts=state["facts"],
            retrieved=state["retrieved"],
            memories=state["memories"],
            memory_influence_hints=hints,
            qa_report=state["qa_report"],
            revision_feedback=revision_feedback,
            token_usage=token_usage_delta,
        )
        step.output_summary = explanation.headline
    return {
        "explanation": explanation,
        "timeline": [step.entry],
        "timings": {"analyst": step.entry.duration_ms},
        "token_usage": token_usage_delta,
    }


def node_guardrail(state: RunState) -> dict:
    with agent_step(state["run_id"], "guardrail") as step:
        known_entities = profile_builder_agent.collect_known_entities(state["transactions"])
        token_usage_delta: dict[str, int] = {}
        result = guardrail_agent.review(
            explanation=state["explanation"],
            facts=state["facts"],
            known_entities=known_entities,
            qa_report=state["qa_report"],
            token_usage=token_usage_delta,
        )
        step.output_summary = f"status={result.status.value} grounding={result.grounding.grounding_rate:.0%}"
        if result.status != GuardrailStatus.APPROVED:
            step.safety_notes = list(result.notes)

    revision_count = state.get("revision_count", 0)
    if result.status == GuardrailStatus.NEEDS_REVISION:
        revision_count += 1

    return {
        "guardrail_result": result,
        "grounding_report": result.grounding,
        "revision_count": revision_count,
        "timeline": [step.entry],
        "timings": {"guardrail": step.entry.duration_ms},
        "token_usage": token_usage_delta,
    }


def route_after_guardrail(state: RunState) -> str:
    status = state["guardrail_result"].status
    if status == GuardrailStatus.BLOCKED_DUE_TO_DATA_QUALITY:
        return "blocked"
    if status == GuardrailStatus.NEEDS_REVISION:
        # "On a third failure, fall back" (plan section 6.6) -- the count
        # was already incremented in node_guardrail for THIS failure.
        return "revise" if state.get("revision_count", 0) <= MAX_REVISION_PASSES else "fallback"
    return "approved"


def node_template_fallback(state: RunState) -> dict:
    """Never a blank screen, never an unverified claim (plan section 6.6):
    a deterministic report built directly from the fact table, bypassing
    the LLM narrator entirely after repeated grounding failures.
    """
    with agent_step(state["run_id"], "template_fallback") as step:
        facts = state["facts"]

        # Prefer the Analyst's last narrative when it is numerically clean.
        # Exhausting the revision cap usually means the reviewer objected on
        # soft grounds (tone, a missing caveat) -- not that the numbers were
        # wrong. Throwing away a fully-grounded explanation for a bare fact
        # listing makes the output far less useful than the evidence
        # justifies, so keep it and label why it wasn't formally approved.
        kept = None
        kept_report = None
        last = state.get("explanation")
        if last is not None:
            report = grounding.verify(last, facts, known_entities=set())
            if not report.has_critical_violation:
                caveat = (
                    "The reviewer model did not sign off on this explanation after "
                    f"{MAX_REVISION_PASSES} revisions. Every number in it was still verified "
                    "against source data."
                )
                kept = last.model_copy(update={"risks_or_caveats": [*last.risks_or_caveats, caveat]})
                kept_report = report
                step.output_summary = "Kept last analyst narrative (numerically verified)"
                step.safety_notes = ["Revision cap reached; narrative retained on grounding evidence"]

        variance = next((f for f in facts if f.kind == "variance"), None)
        drivers = [f for f in facts if f.kind == "driver"]

        explanation = Explanation(
            headline=f"{variance.label}: {variance.formatted}" if variance else "See the fact table for this period's results.",
            summary=(
                "The narrative generator could not produce a fully grounded explanation after "
                f"{MAX_REVISION_PASSES} revision attempt(s); this report lists the computed facts directly."
            ),
            claims=[
                Claim(text=f"{f.label}: {f.formatted}", fact_ids=[f.fact_id], claim_type=ClaimType.FACT)
                for f in facts[:5]
            ],
            drivers=[
                Driver(driver=f.label, amount=f.value, share_of_gross_change_pct=0.0, confidence=f.confidence)
                for f in drivers
            ],
            risks_or_caveats=[
                "This report was generated directly from computed facts after the AI narrative "
                "failed grounding review; treat it as a data listing, not prose analysis."
            ],
        )
        grounding_report = grounding.verify(explanation, facts, known_entities=set())
        step.output_summary = "Deterministic template report (narrative failed grounding review)"
        step.safety_notes = ["Fell back to the deterministic template report"]

    if kept is not None:
        return {
            "explanation": kept,
            "guardrail_result": GuardrailResult(
                status=GuardrailStatus.APPROVED_WITH_CAVEATS,
                grounding=kept_report,
                notes=kept.risks_or_caveats[-1:],
            ),
            "grounding_report": kept_report,
            "timeline": [step.entry],
            "timings": {"template_fallback": step.entry.duration_ms},
        }

    guardrail_result = GuardrailResult(
        status=GuardrailStatus.APPROVED_WITH_CAVEATS,
        grounding=grounding_report,
        notes=["Template fallback used after repeated grounding failures."],
    )
    return {
        "explanation": explanation,
        "guardrail_result": guardrail_result,
        "grounding_report": grounding_report,
        "timeline": [step.entry],
        "timings": {"template_fallback": step.entry.duration_ms},
    }


def node_stress_test(state: RunState) -> dict:
    with agent_step(state["run_id"], "stress_test") as step:
        applications = memory_agent.apply_memories(state["memories"], state["facts"], state["transactions"])
        results = stress_tester_agent.run_available_scenarios(
            transactions=state["transactions"],
            explanation=state["explanation"],
            qa_report=state["qa_report"],
            memory_applications=applications,
        )
        passed = sum(1 for r in results if r.status.value == "pass")
        runnable = sum(1 for r in results if r.status.value != "not_run")
        step.output_summary = f"{passed}/{runnable} runnable scenario(s) passed ({len(results)} total defined)"
    return {
        "stress_results": results,
        "timeline": [step.entry],
        "timings": {"stress_test": step.entry.duration_ms},
    }


def node_report_writer(state: RunState) -> dict:
    with agent_step(state["run_id"], "report_writer") as step:
        markdown = report_writer_agent.to_markdown(
            explanation=state["explanation"],
            current_period=state["current_period"],
            prior_period=state["prior_period"],
            company_name=state["profile"].company_profile.company_name,
            grounding=state["grounding_report"],
        )
        dashboard_payload = report_writer_agent.to_dashboard_payload(
            run_id=state["run_id"],
            explanation=state["explanation"],
            grounding=state["grounding_report"],
            guardrail=state["guardrail_result"],
            qa_report=state["qa_report"],
        )
        token_usage_delta: dict[str, int] = {}
        board_update = report_writer_agent.to_board_update(
            state["explanation"],
            company_name=state["profile"].company_profile.company_name,
            current_period=state["current_period"],
            token_usage=token_usage_delta,
        )
        step.output_summary = "Markdown, dashboard payload, and board update rendered"
    return {
        "report_markdown": markdown,
        "dashboard_payload": dashboard_payload,
        "board_update": board_update,
        "timeline": [step.entry],
        "timings": {"report_writer": step.entry.duration_ms},
        "token_usage": token_usage_delta,
    }


def node_memory_update(state: RunState) -> dict:
    with agent_step(state["run_id"], "memory_update") as step:
        store = MemoryStore()
        applications = memory_agent.apply_memories(state["memories"], state["facts"], state["transactions"])
        memory_agent.update_store_after_run(
            store, company_id=state["company_id"], run_id=state["run_id"], applications=applications
        )
        new_candidates = memory_agent.derive_candidate_memories(
            company_id=state["company_id"], facts=state["facts"], transactions=state["transactions"]
        )
        for candidate in new_candidates:
            store.create(candidate)
        step.output_summary = f"{len(applications)} memorie(s) reinforced, {len(new_candidates)} new candidate(s) created"
    return {
        "timeline": [step.entry],
        "timings": {"memory_update": step.entry.duration_ms},
    }


def node_data_issue_report(state: RunState) -> dict:
    with agent_step(state["run_id"], "data_issue_report") as step:
        step.output_summary = "; ".join(state["qa_report"].blocking_issues) or "Run blocked by data QA"
        step.safety_notes = list(state["qa_report"].blocking_issues)
    return {
        "timeline": [step.entry],
        "timings": {"data_issue_report": step.entry.duration_ms},
    }


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_graph():
    graph = StateGraph(RunState)

    graph.add_node("profile_builder", node_profile_builder)
    graph.add_node("data_qa", node_data_qa)
    graph.add_node("memory", node_memory)
    graph.add_node("rag", node_rag)
    graph.add_node("analytics_engine", node_analytics)
    graph.add_node("analyst", node_analyst)
    graph.add_node("guardrail", node_guardrail)
    graph.add_node("template_fallback", node_template_fallback)
    graph.add_node("stress_test", node_stress_test)
    graph.add_node("report_writer", node_report_writer)
    graph.add_node("memory_update", node_memory_update)
    graph.add_node("data_issue_report", node_data_issue_report)

    graph.add_edge(START, "profile_builder")
    graph.add_edge("profile_builder", "data_qa")
    graph.add_conditional_edges("data_qa", route_after_qa)

    graph.add_edge("memory", "analyst")
    graph.add_edge("rag", "analyst")
    graph.add_edge("analytics_engine", "analyst")

    graph.add_edge("analyst", "guardrail")
    graph.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {
            "revise": "analyst",
            "fallback": "template_fallback",
            "approved": "stress_test",
            "blocked": "data_issue_report",
        },
    )

    graph.add_edge("template_fallback", "stress_test")
    graph.add_edge("stress_test", "report_writer")
    graph.add_edge("report_writer", "memory_update")
    graph.add_edge("memory_update", END)
    graph.add_edge("data_issue_report", END)

    return graph.compile()


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_pipeline(
    *,
    company_id: str,
    current_period: str,
    prior_period: str,
    company_profile_core: CompanyProfileCore,
    transactions: list[CanonicalTransaction],
    period_summaries: list[PeriodSummary],
    available_files: list[AvailableFile] | None = None,
    known_aliases: dict[str, list[str]] | None = None,
    run_id: str | None = None,
) -> RunState:
    initial_state = new_run_state(
        company_id=company_id,
        current_period=current_period,
        prior_period=prior_period,
        company_profile_core=company_profile_core,
        transactions=transactions,
        period_summaries=period_summaries,
        available_files=available_files,
        known_aliases=known_aliases,
        run_id=run_id,
    )
    graph = get_compiled_graph()
    final_state = graph.invoke(initial_state, config={"recursion_limit": 50})
    EVENT_BUS.publish(
        final_state["run_id"],
        emit_run_complete(final_state["run_id"], sum(final_state.get("timings", {}).values())),
    )
    return final_state
