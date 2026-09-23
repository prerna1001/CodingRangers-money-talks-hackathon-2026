from __future__ import annotations

from dataclasses import dataclass

from data.generate import ecommerce_demo, healthcare_demo, saas_demo


@dataclass(frozen=True)
class SuiteCase:
    name: str
    txns: list
    summaries: list
    manifest: dict


def suite_cases() -> list[SuiteCase]:
    cases = []
    for name, factory, kwargs in [
        ("saas_clean", saas_demo, {}),
        ("saas_prompt_duplicate", saas_demo, {"inject_prompt": True, "inject_duplicate": True}),
        ("ecommerce_clean", ecommerce_demo, {}),
        ("ecommerce_large_refund", ecommerce_demo, {"inject_large_refund": True}),
        ("healthcare_clean", healthcare_demo, {}),
        ("healthcare_missing_counterparty", healthcare_demo, {"inject_missing_counterparty": True}),
    ]:
        txns, summaries, manifest = factory(**kwargs)
        cases.append(SuiteCase(name=name, txns=txns, summaries=summaries, manifest=manifest))
    return cases

