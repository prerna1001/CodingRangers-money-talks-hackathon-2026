from __future__ import annotations

import json
from dataclasses import asdict

from analytics.anomalies import find_duplicate_count
from analytics.facts import build_facts
from eval.metrics import EvalResult, MetricResult, amount_accuracy, driver_recall_at_k, find_variance
from eval.suites import SuiteCase, suite_cases
from services.csv_parser import parse_period_summaries, parse_transactions


def evaluate_case(case: SuiteCase) -> EvalResult:
    manifest = case.manifest
    expected = manifest["expected"]
    transactions = parse_transactions((txn.__dict__ for txn in case.txns), source_file_id=case.name)
    summaries = parse_period_summaries(line.__dict__ for line in case.summaries)
    facts = build_facts(
        transactions=transactions,
        period_summaries=summaries,
        current_period=manifest["current_period"],
        prior_period=manifest["prior_period"],
    )

    metrics: list[MetricResult] = []
    expected_variances = {
        "Subscription revenue": expected.get("subscription_revenue_change"),
        "Cloud hosting": expected.get("cloud_hosting_change"),
        "Gross sales": expected.get("gross_sales_change"),
        "Refunds": expected.get("refund_change"),
        "Patient revenue": expected.get("patient_revenue_change"),
        "Billing adjustments": expected.get("billing_adjustment_change"),
        "Contractor labor": expected.get("contractor_labor_change"),
    }
    for label, expected_amount in expected_variances.items():
        if expected_amount is None:
            continue
        fact = find_variance(facts, label)
        if fact is None:
            metrics.append(MetricResult(f"{label} variance", 0.0, "missing variance fact"))
        else:
            metrics.append(
                MetricResult(
                    f"{label} variance",
                    amount_accuracy(fact.value, expected_amount),
                    f"actual={fact.value} expected={expected_amount}",
                )
            )

    if "top_revenue_drivers" in expected:
        metrics.append(
            MetricResult(
                "driver recall@3",
                driver_recall_at_k(facts, expected["top_revenue_drivers"], k=3),
                f"expected={expected['top_revenue_drivers']}",
            )
        )

    if "duplicate_present" in expected:
        duplicate_count = find_duplicate_count(transactions)
        detected = duplicate_count > 0
        metrics.append(
            MetricResult(
                "duplicate detection",
                1.0 if detected == expected["duplicate_present"] else 0.0,
                f"detected={detected} count={duplicate_count}",
            )
        )

    if "missing_counterparty_present" in expected:
        detected = any(txn.counterparty_name is None for txn in transactions)
        metrics.append(
            MetricResult(
                "missing counterparty detection",
                1.0 if detected == expected["missing_counterparty_present"] else 0.0,
                f"detected={detected}",
            )
        )

    return EvalResult(dataset=case.name, metrics=metrics)


def run_suite() -> list[EvalResult]:
    return [evaluate_case(case) for case in suite_cases()]


def main() -> None:
    results = run_suite()
    print(json.dumps([asdict(result) | {"score": result.score} for result in results], indent=2))
    failed = [result for result in results if result.score < 0.95]
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

