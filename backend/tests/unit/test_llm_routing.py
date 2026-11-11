from __future__ import annotations

import importlib
import os

import dotenv
import pytest

import config
from services import llm


@pytest.fixture
def default_routes():
    """Rebuild config from its code defaults, ignoring the developer's .env.

    The routes are env-overridable (LLM_PROVIDER_* / LLM_MODEL_*), so asserting
    against the live config fails for anyone who points an agent at a
    different provider locally. These tests are about the shipped defaults.
    """
    with pytest.MonkeyPatch.context() as mp:
        for key in list(os.environ):
            if key.startswith(("LLM_PROVIDER_", "LLM_MODEL_")) or key == "DEMO_FAST_MODE":
                mp.delenv(key)
        # config calls load_dotenv() at import; stop it re-reading .env.
        mp.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
        importlib.reload(config)
        yield
    # Environment is restored by now, so this brings the real config back.
    importlib.reload(config)


def test_routes_are_explicit_per_agent(default_routes) -> None:
    assert llm._route_for_task("analyst") == ("groq", "openai/gpt-oss-120b")
    assert llm._route_for_task("guardrail") == ("groq", "openai/gpt-oss-120b")
    rag_provider, rag_model = llm._route_for_task("rag_rerank")
    report_provider, report_model = llm._route_for_task("report_writer")
    assert rag_provider == "openrouter"
    assert report_provider == "openrouter"
    assert rag_model
    assert report_model


def test_mock_response_records_provider(default_routes, monkeypatch) -> None:
    monkeypatch.setattr(config, "LLM_MOCK_MODE", True)
    response = llm.complete(task="analyst", system="", user="", mock_fn=lambda: "{}")

    assert response.provider == "groq"
    assert response.model == "openai/gpt-oss-120b"
