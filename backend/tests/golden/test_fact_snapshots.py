from __future__ import annotations

from analytics.facts import build_facts
from eval.suites import suite_cases
from services.csv_parser import parse_period_summaries, parse_transactions


EXPECTED_VARIANCES = {
    "saas_clean": {
        "variance_4000_2026_07_to_2026_08": 28000.0,
        "variance_5100_2026_07_to_2026_08": 6400.0,
    },
    "saas_prompt_duplicate": {
        "variance_4000_2026_07_to_2026_08": 28000.0,
        "variance_5100_2026_07_to_2026_08": 41900.0,
        "variance_6000_2026_07_to_2026_08": 500.0,
    },
    "ecommerce_clean": {
        "variance_4000_2026_07_to_2026_08": 46000.0,
        "variance_4050_2026_07_to_2026_08": -5000.0,
        "variance_5200_2026_07_to_2026_08": 11000.0,
        "variance_6100_2026_07_to_2026_08": 24000.0,
    },
    "ecommerce_large_refund": {
        "variance_4000_2026_07_to_2026_08": 46000.0,
        "variance_4050_2026_07_to_2026_08": -16000.0,
        "variance_5200_2026_07_to_2026_08": 11000.0,
        "variance_6100_2026_07_to_2026_08": 24000.0,
    },
    "healthcare_clean": {
        "variance_4000_2026_07_to_2026_08": 4000.0,
        "variance_4060_2026_07_to_2026_08": -13000.0,
        "variance_6200_2026_07_to_2026_08": 23000.0,
    },
    "healthcare_missing_counterparty": {
        "variance_4000_2026_07_to_2026_08": 4000.0,
        "variance_4060_2026_07_to_2026_08": -13000.0,
        "variance_6200_2026_07_to_2026_08": 23000.0,
    },
}


def test_variance_fact_snapshots() -> None:
    for case in suite_cases():
        transactions = parse_transactions((txn.__dict__ for txn in case.txns), source_file_id=case.name)
        summaries = parse_period_summaries(line.__dict__ for line in case.summaries)
        facts = build_facts(
            transactions=transactions,
            period_summaries=summaries,
            current_period=case.manifest["current_period"],
            prior_period=case.manifest["prior_period"],
        )
        actual = {fact.fact_id: fact.value for fact in facts if fact.kind == "variance"}
        assert actual == EXPECTED_VARIANCES[case.name]

