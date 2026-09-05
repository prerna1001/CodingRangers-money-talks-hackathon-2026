from __future__ import annotations

from services import llm


def test_routes_are_explicit_per_agent() -> None:
    assert llm._route_for_task("analyst") == ("nvidia", "nvidia/nemotron-3-super-120b-a12b")
    assert llm._route_for_task("guardrail") == ("groq", "openai/gpt-oss-120b")
    rag_provider, rag_model = llm._route_for_task("rag_rerank")
    report_provider, report_model = llm._route_for_task("report_writer")
    assert rag_provider == "openrouter"
    assert report_provider == "openrouter"
    assert rag_model
    assert report_model


def test_mock_response_records_provider(monkeypatch) -> None:
    import config

    monkeypatch.setattr(config, "LLM_MOCK_MODE", True)
    response = llm.complete(task="analyst", system="", user="", mock_fn=lambda: "{}")

    assert response.provider == "nvidia"
    assert response.model == "nvidia/nemotron-3-super-120b-a12b"
