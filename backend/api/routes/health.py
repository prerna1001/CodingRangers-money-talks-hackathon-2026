"""GET /api/health -- dependency status for the demo-safety banner (plan
section 18.1's three-tier demo plan reads this before walking on stage).
"""

from __future__ import annotations

from fastapi import APIRouter

import config
from services.rag_store import RagStore

router = APIRouter()


@router.get("/health")
def health() -> dict:
    rag_backend = RagStore().backend
    return {
        "status": "ok",
        "llm_mock_mode": config.LLM_MOCK_MODE,
        "demo_fast_mode": config.DEMO_FAST_MODE,
        "rag_backend": rag_backend,
        "tavily_configured": bool(config.TAVILY_API_KEY),
        "elevenlabs_configured": bool(config.ELEVENLABS_API_KEY),
        "tier": _tier(rag_backend),
    }


def _tier(rag_backend: str) -> str:
    if config.LLM_MOCK_MODE:
        return "red"  # no live LLM -- fine for rehearsal, not for a live judged demo
    if not config.TAVILY_API_KEY or not config.ELEVENLABS_API_KEY:
        return "yellow"
    return "green"
