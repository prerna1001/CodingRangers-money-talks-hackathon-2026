"""Adapts a finished RunState into the exact JSON shape the React
dashboard already consumes.

Deliberately a separate, additive module rather than a change to
agents/report_writer.py's `to_dashboard_payload`: that function is part
of the agent contract and is covered by existing tests, whereas this one
exists purely to serve the frontend's established component props. If
the UI's needs change, this file changes and nothing in the pipeline
does.

The target shape is dictated by the existing frontend components (not
invented here) -- Dashboard.jsx, ExecutiveSummary.jsx, WaterfallChart.jsx,
DriverTable.jsx, PipelinePanel.jsx and utils/pdfReport.js between them
require:

    { run_id, headline, summary, confidence, data_quality_score,
      periods: { current: {label, revenue}, prior: {label, revenue} },
      drivers: [{ driver, account, current, prior, amount,
                  share_of_change_pct, confidence }],
      waterfall: [{ name, value, type: start|increase|decrease|end }],
      agent_timeline: [{ name, status, duration_ms }],
      risks_or_caveats: [str] }
"""

from __future__ import annotations

from models.schemas import AccountType, AgentStatus, CanonicalTransaction, Fact, RunState

# The frontend's PipelinePanel only knows these three status strings.
_STATUS_MAP = {
    AgentStatus.PASSED: "passed",
    AgentStatus.WARNING: "passed_with_warnings",
    AgentStatus.REVISED: "passed_with_warnings",
    AgentStatus.FAILED: "failed",
    AgentStatus.RUNNING: "passed",
    AgentStatus.WAITING: "passed",
}


# .title() mangles the acronyms ("Data Qa", "Rag"), and these strings are
# shown verbatim in the dashboard's pipeline panel.
_AGENT_DISPLAY_NAMES = {
    "profile_builder": "Profile Builder",
    "data_qa": "Data QA",
    "memory": "Memory Agent",
    "rag": "RAG Agent",
    "analytics_engine": "Analytics Engine",
    "analyst": "Analyst",
    "guardrail": "Safety Guardrail",
    "template_fallback": "Template Fallback",
    "stress_test": "Stress Test",
    "report_writer": "Report Writer",
    "memory_update": "Memory Update",
    "data_issue_report": "Data Issue Report",
}


def _pretty_agent_name(agent: str) -> str:
    return _AGENT_DISPLAY_NAMES.get(agent, agent.replace("_", " ").title())


def _revenue_for_period(state: RunState, period_id: str) -> float:
    """Total revenue for a period, taken from the reconciled period
    summary (not the transaction rows) so it matches what the Data QA
    gate already validated.
    """
    for summary in state.get("period_summaries", []):
        if summary.period_id != period_id:
            continue
        return round(
            sum(line.amount for line in summary.lines if line.account_type == AccountType.REVENUE), 2
        )
    return 0.0


def _driver_facts(state: RunState) -> list[Fact]:
    return [f for f in state.get("facts", []) if f.kind == "driver"]


def _txn_index(state: RunState) -> dict[str, CanonicalTransaction]:
    return {t.txn_id: t for t in state.get("transactions", [])}


def _counterparty_period_total(
    transactions: list[CanonicalTransaction], counterparty: str, account_id: str, period_id: str
) -> float:
    return round(
        sum(
            t.amount
            for t in transactions
            if t.period_id == period_id
            and t.account_id == account_id
            and (t.counterparty_name or t.counterparty_id) == counterparty
        ),
        2,
    )


def _build_drivers(state: RunState) -> list[dict]:
    """One row per driver fact, enriched with the account it belongs to and
    its current/prior totals -- both resolved from the fact's own evidence
    transactions, never guessed from the label text.
    """
    transactions = state.get("transactions", [])
    by_id = _txn_index(state)
    current_period = state["current_period"]
    prior_period = state["prior_period"]

    rows: list[dict] = []
    for fact in _driver_facts(state):
        evidence = [by_id[tid] for tid in fact.evidence_txn_ids if tid in by_id]
        if not evidence:
            continue
        sample = evidence[0]
        counterparty = sample.counterparty_name or sample.counterparty_id or "Unknown"
        current = _counterparty_period_total(transactions, counterparty, sample.account_id, current_period)
        prior = _counterparty_period_total(transactions, counterparty, sample.account_id, prior_period)
        rows.append(
            {
                "driver": counterparty,
                "account": sample.account_name,
                "current": current,
                "prior": prior,
                "amount": round(fact.value, 2),
                # Percentage change for this driver against its own prior
                # base -- the DriverTable column is labelled "% change".
                "share_of_change_pct": round((fact.value / abs(prior)) * 100, 1) if prior else 100.0,
                "confidence": round(fact.confidence, 2),
            }
        )

    rows.sort(key=lambda r: abs(r["amount"]), reverse=True)
    return rows


def _build_waterfall(state: RunState, drivers: list[dict]) -> list[dict]:
    """Prior revenue -> each revenue driver -> current revenue.

    Only revenue-account drivers participate, and any unattributed
    remainder is shown explicitly as "Other" rather than silently
    dropped -- a waterfall whose bars don't tie to the endpoints is
    worse than one that admits a residual.
    """
    current_period = state["current_period"]
    prior_period = state["prior_period"]
    prior_revenue = _revenue_for_period(state, prior_period)
    current_revenue = _revenue_for_period(state, current_period)

    revenue_accounts = {
        line.account_id
        for summary in state.get("period_summaries", [])
        for line in summary.lines
        if line.account_type == AccountType.REVENUE
    }
    by_id = _txn_index(state)
    revenue_account_names = {
        by_id[tid].account_name
        for fact in _driver_facts(state)
        for tid in fact.evidence_txn_ids
        if tid in by_id and by_id[tid].account_id in revenue_accounts
    }

    steps: list[dict] = [{"name": prior_period, "value": prior_revenue, "type": "start"}]

    # One bar per driver *of a revenue account*. A counterparty can drive more
    # than one revenue account (e.g. Shopify moves both Gross sales and
    # Refunds), so bars are keyed by driver+account and aggregated -- keying
    # by name alone silently dropped all but one of them, which is why the
    # bars stopped adding up to the endpoints.
    contributions: dict[str, float] = {}
    for row in drivers:
        if row["account"] not in revenue_account_names:
            continue
        label = row["driver"] if len(revenue_account_names) == 1 else f"{row['driver']} ({row['account']})"
        contributions[label] = contributions.get(label, 0.0) + row["amount"]

    attributed = 0.0
    for label, amount in sorted(contributions.items(), key=lambda kv: -abs(kv[1])):
        attributed += amount
        steps.append(
            {
                "name": label,
                "value": round(amount, 2),
                "type": "increase" if amount >= 0 else "decrease",
            }
        )

    residual = round((current_revenue - prior_revenue) - attributed, 2)
    if abs(residual) >= 1:
        steps.append(
            {"name": "Other", "value": residual, "type": "increase" if residual >= 0 else "decrease"}
        )

    steps.append({"name": current_period, "value": current_revenue, "type": "end"})
    return steps


def _overall_confidence(state: RunState, drivers: list[dict]) -> float:
    explanation = state.get("explanation")
    if explanation is not None and explanation.drivers:
        values = [d.confidence for d in explanation.drivers]
    elif drivers:
        values = [d["confidence"] for d in drivers]
    else:
        grounding = state.get("grounding_report")
        return round(grounding.grounding_rate, 2) if grounding else 0.0
    return round(max(0.0, min(1.0, sum(values) / len(values))), 2)


def to_frontend_analysis(state: RunState) -> dict:
    explanation = state.get("explanation")
    qa_report = state.get("qa_report")
    grounding = state.get("grounding_report")
    guardrail = state.get("guardrail_result")

    drivers = _build_drivers(state)

    return {
        "run_id": state["run_id"],
        "headline": explanation.headline if explanation else "No explanation produced for this run.",
        "summary": explanation.summary if explanation else "",
        "confidence": _overall_confidence(state, drivers),
        "data_quality_score": round(qa_report.data_quality_score, 2) if qa_report else 0.0,
        "periods": {
            "current": {
                "label": state["current_period"],
                "revenue": _revenue_for_period(state, state["current_period"]),
            },
            "prior": {
                "label": state["prior_period"],
                "revenue": _revenue_for_period(state, state["prior_period"]),
            },
        },
        "drivers": drivers,
        "waterfall": _build_waterfall(state, drivers),
        "agent_timeline": [
            {
                "name": _pretty_agent_name(entry.agent),
                "status": _STATUS_MAP.get(entry.status, "passed"),
                "duration_ms": round(entry.duration_ms or 0),
            }
            for entry in state.get("timeline", [])
        ],
        "risks_or_caveats": explanation.risks_or_caveats if explanation else [],
        # Extra fields the current components don't read yet, but which the
        # backend already proves -- kept here so the UI can surface them
        # without another round-trip (grounding badge, follow-ups, etc.).
        "follow_up_questions": explanation.follow_up_questions if explanation else [],
        "grounding_rate": grounding.grounding_rate if grounding else None,
        "grounding_badge": (
            f"{grounding.grounded_numbers}/{grounding.total_numbers} numbers verified" if grounding else None
        ),
        "guardrail_status": guardrail.status.value if guardrail else None,
        "board_update": state.get("board_update"),
        "report_markdown": state.get("report_markdown"),
    }
