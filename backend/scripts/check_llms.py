from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from services import llm  # noqa: E402


def main() -> int:
    config.LLM_MOCK_MODE = False
    config.LLM_MAX_RETRIES = 0
    config.LLM_TIMEOUT_SECONDS = 12

    tasks = [
        "analyst",
        "guardrail",
        "report_writer",
        "normalization",
        "memory_relevance",
        "rag_rerank",
        "stress_test",
    ]

    failures = 0
    for task in tasks:
        provider, model = llm._route_for_task(task)
        try:
            response = llm.complete(
                task=task,
                system="Return only OK.",
                user="Return only OK.",
                max_tokens=8,
                mock_fn=lambda: "OK",
            )
            text = response.text.replace("\n", " ")[:60]
            print(f"{task}\t{provider}\t{model}\tWORKING\t{response.duration_ms:.0f}ms\t{text}")
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            failures += 1
            print(f"{task}\t{provider}\t{model}\tFAILED\t{type(exc).__name__}: {str(exc)[:220]}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
