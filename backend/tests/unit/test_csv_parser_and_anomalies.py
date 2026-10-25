from __future__ import annotations

from analytics.anomalies import find_duplicate_count
from data.generate import saas_demo
from services.csv_parser import parse_transactions
from services.entity_resolver import resolve


def test_prompt_and_duplicate_dataset_parses() -> None:
    txns, _, manifest = saas_demo(inject_prompt=True, inject_duplicate=True)
    parsed = parse_transactions((txn.__dict__ for txn in txns), source_file_id="demo")

    assert manifest["expected"]["prompt_injection_present"] is True
    assert find_duplicate_count(parsed) == 1
    assert any("Ignore previous instructions" in txn.memo for txn in parsed)


def test_entity_resolver_alias_match() -> None:
    aliases = {"vendor:aws": ["AWS", "Amazon Web Services", "AMZN AWS"]}
    assert resolve("Amazon Web Services", aliases) == "vendor:aws"
    assert resolve("AWS", aliases) == "vendor:aws"

