"""GET /api/health -- dependency status for the demo-safety banner (plan
section 18.1's three-tier demo plan reads this before walking on stage).
"""

from __future__ import annotations

from fastapi import APIRouter

import config
from services import translator, voice_client
from services.rag_store import RagStore

router = APIRouter()


@router.get("/health")
def health() -> dict:
    rag_backend = RagStore().backend
    voice = voice_client.status()
    return {
        "status": "ok",
        "llm_mock_mode": config.LLM_MOCK_MODE,
        "demo_fast_mode": config.DEMO_FAST_MODE,
        "rag_backend": rag_backend,
        "tavily_configured": bool(config.TAVILY_API_KEY),
        "voice": voice,
        "translation": translator.status(),
        "tier": _tier(rag_backend, voice),
    }


def _tier(rag_backend: str, voice: dict) -> str:
    if config.LLM_MOCK_MODE:
        return "red"  # no live LLM -- fine for rehearsal, not for a live judged demo
    # Voice counts as ready when the selected providers can actually run --
    # for the local default that means the weights are on disk, not that an
    # API key happens to be set.
    if not config.TAVILY_API_KEY or not voice["tts_ready"] or not voice["stt_ready"]:
        return "yellow"
    return "green"
