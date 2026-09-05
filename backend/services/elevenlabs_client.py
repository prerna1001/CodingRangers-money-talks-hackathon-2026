"""ElevenLabs voice briefing client (plan section 16.2).

The script it's given must already be the output of
agents/report_writer.to_voice_script() -- built only from an APPROVED
Explanation, so this client can never speak a claim the guardrail
rejected. Falls back to a pre-rendered MP3 for the primary demo dataset
if no API key is configured or the call fails, so a flaky connection on
stage never blocks the demo (plan section 16.2, 18.1).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from config import ELEVENLABS_API_KEY

logger = logging.getLogger(__name__)

CACHE_DIR = Path("./.cache/voice")
FALLBACK_MP3 = Path("./data/fallback_briefing.mp3")
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel" -- calm, neutral


def generate(script: str, *, voice_id: str = DEFAULT_VOICE_ID) -> Path | None:
    """Returns a path to an MP3 file, or None if neither a live call nor
    the fallback recording is available. Never raises.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(script.encode()).hexdigest()[:24]
    cache_path = CACHE_DIR / f"{key}.mp3"
    if cache_path.exists():
        return cache_path

    if not ELEVENLABS_API_KEY:
        logger.info("elevenlabs.generate skipped -- no ELEVENLABS_API_KEY configured")
        return FALLBACK_MP3 if FALLBACK_MP3.exists() else None

    try:
        import httpx

        response = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            json={"text": script, "model_id": "eleven_monolingual_v1"},
            timeout=15,
        )
        response.raise_for_status()
        cache_path.write_bytes(response.content)
        return cache_path
    except Exception as exc:  # noqa: BLE001 - graceful degradation by design
        logger.warning("elevenlabs.generate failed: %s", exc)
        return FALLBACK_MP3 if FALLBACK_MP3.exists() else None
