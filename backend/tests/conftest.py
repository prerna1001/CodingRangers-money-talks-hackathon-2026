"""Shared pytest fixtures.

CRITICAL: force LLM_MOCK_MODE on for the entire test suite, regardless of
what's in the developer's .env. services/llm.py checks `config.LLM_MOCK_MODE`
at call time (not at import time), so this monkeypatch reaches every agent
that calls `llm.complete(...)` -- analyst, guardrail, report_writer, etc. --
without needing per-module changes.

Without this, the moment real provider keys are configured for a live demo,
`pytest` silently starts making real network calls to Groq/NVIDIA/OpenRouter
on every run: slow, flaky, and burns quota on every test invocation. Tests
must be deterministic and network-independent no matter what's in the
environment -- that's the whole point of services/llm.py's mock_fn design.
"""

from __future__ import annotations

import pytest

import config


@pytest.fixture(autouse=True)
def _force_llm_mock_mode(monkeypatch):
    monkeypatch.setattr(config, "LLM_MOCK_MODE", True)
