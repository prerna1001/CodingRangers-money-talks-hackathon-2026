from __future__ import annotations

from eval.run import run_suite


def test_eval_suite_scores_all_synthetic_cases() -> None:
    results = run_suite()

    assert len(results) == 6
    assert all(result.score >= 0.95 for result in results)

