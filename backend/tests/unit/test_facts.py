from __future__ import annotations

from data.generate import saas_demo
from services.csv_parser import parse_period_summaries, parse_transactions
from analytics.facts import build_facts


def test_build_facts_from_saas_demo() -> None:
    txns, summaries, _ = saas_demo()
    transactions = parse_transactions((txn.__dict__ for txn in txns), source_file_id="demo")
    period_summaries = parse_period_summaries(line.__dict__ for line in summaries)

    facts = build_facts(
        transactions=transactions,
        period_summaries=period_summaries,
        current_period="2026-08",
        prior_period="2026-07",
    )

    revenue_variance = next(f for f in facts if f.fact_id.startswith("variance_4000"))
    assert revenue_variance.value == 28000
    assert revenue_variance.pct == 0.1806
    assert any(f.kind == "driver" and "Northwind Labs" in f.label and f.value == 18000 for f in facts)
    assert any(f.kind == "concentration" for f in facts)

