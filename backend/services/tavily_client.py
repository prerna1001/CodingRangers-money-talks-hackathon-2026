"""Tavily research client (plan section 16.1): context only, never math.

Hard timeout, disk-cached by query hash so the demo never needs the
network live, and never raises -- on any failure the caller continues
without external context and the report notes the omission (plan section
18's graceful-degradation principle).
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from config import TAVILY_API_KEY, TAVILY_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

CACHE_DIR = Path("./.cache/tavily")


def _cache_path(query: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(query.encode()).hexdigest()[:24]
    return CACHE_DIR / f"{key}.json"


def search(query: str, max_results: int = 3) -> dict | None:
    """Returns None on any failure or missing key -- never raises. Callers
    must treat a None result as "context unavailable", not an error.
    """
    cache_path = _cache_path(query)
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    if not TAVILY_API_KEY:
        logger.info("tavily.search skipped -- no TAVILY_API_KEY configured")
        return None

    try:
        import httpx

        response = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "max_results": max_results},
            timeout=TAVILY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        cache_path.write_text(json.dumps(data))
        return data
    except Exception as exc:  # noqa: BLE001 - graceful degradation by design
        logger.warning("tavily.search failed for query=%r: %s", query, exc)
        return None
