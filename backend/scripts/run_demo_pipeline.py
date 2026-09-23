"""Run the full agentic pipeline end to end against the checked-in demo
fixture -- proof that the walking skeleton (plan section 19.2, Day 2 exit
criterion) works before Codex's analytics engine and dataset generator
exist.

Usage:
    .venv/Scripts/python.exe scripts/run_demo_pipeline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.schemas import CanonicalTransaction, CompanyProfileCore, PeriodSummary  # noqa: E402
from graph.workflow import run_pipeline  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def main() -> None:
    txns_data = json.loads((FIXTURES_DIR / "saas_2026_08_transactions.json").read_text())
    transactions = [CanonicalTransaction(**t) for t in txns_data["transactions"]]
    period_summaries = [PeriodSummary(**p) for p in txns_data["period_summaries"]]

    profile_core = CompanyProfileCore(
        company_id="demo_saas",
        company_name="DemoCo",
        industry="B2B SaaS",
        business_model="subscription",
        primary_revenue_streams=["SMB subscriptions", "Enterprise subscriptions", "Professional services"],
        known_seasonality=["Q4 enterprise renewals", "summer SMB slowdown"],
    )

    final_state = run_pipeline(
        company_id="demo_saas",
        current_period="2026-08",
        prior_period="2026-07",
        company_profile_core=profile_core,
        transactions=transactions,
        period_summaries=period_summaries,
        known_aliases={"vendor:aws": ["AWS", "Amazon Web Services", "AMZN AWS"]},
    )

    print(f"\n=== run_id: {final_state['run_id']} ===\n")

    print("--- Agent timeline ---")
    for entry in final_state.get("timeline", []):
        print(f"  [{entry.status.value:8}] {entry.agent:20} {entry.duration_ms:7.1f}ms  {entry.output_summary or ''}")

    print("\n--- QA report ---")
    qa = final_state.get("qa_report")
    if qa:
        print(f"  status={qa.status.value} data_quality_score={qa.data_quality_score} safe_to_analyze={qa.safe_to_analyze}")
        for w in qa.warnings:
            print(f"  warning[{w.severity.value}]: {w.message}")

    explanation = final_state.get("explanation")
    if explanation:
        print("\n--- Explanation ---")
        print(f"  Headline: {explanation.headline}")
        print(f"  Summary:  {explanation.summary}")
        for claim in explanation.claims:
            print(f"  [{claim.claim_type.value}] {claim.text}  (facts: {claim.fact_ids})")

    grounding_report = final_state.get("grounding_report")
    if grounding_report:
        print("\n--- Grounding ---")
        print(f"  {grounding_report.grounded_numbers}/{grounding_report.total_numbers} numbers verified "
              f"({grounding_report.grounding_rate:.0%})")
        for v in grounding_report.violations:
            print(f"  VIOLATION [{v.severity}] {v.type.value}: {v.detail}")

    guardrail_result = final_state.get("guardrail_result")
    if guardrail_result:
        print(f"\n--- Guardrail: {guardrail_result.status.value} ---")
        for note in guardrail_result.notes:
            print(f"  note: {note}")

    print("\n--- Stress tests ---")
    for result in final_state.get("stress_results", []):
        print(f"  [{result.status.value:8}] {result.name}: {result.detail}")

    print("\n--- Token usage ---")
    print(f"  {final_state.get('token_usage', {})}")

    print("\n--- Markdown report ---\n")
    print(final_state.get("report_markdown", "(none -- run was blocked or incomplete)"))


if __name__ == "__main__":
    main()
