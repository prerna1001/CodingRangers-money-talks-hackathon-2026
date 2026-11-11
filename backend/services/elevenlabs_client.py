"""ElevenLabs voice provider -- the hosted, paid alternative to the local
Kokoro/Whisper default (plan section 16.2).

Selected by setting VOICE_TTS_PROVIDER=elevenlabs and/or
VOICE_STT_PROVIDER=elevenlabs. services/voice_client.py owns provider
choice, text normalization, MP3 caching and the demo fallback recording,
so this module is just the two HTTP calls.
"""

from __future__ import annotations

import logging

from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
from services.voice_errors import VoiceError

logger = logging.getLogger(__name__)

API_BASE = "https://api.elevenlabs.io/v1"
TTS_MODEL = "eleven_multilingual_v2"
STT_MODEL = "scribe_v1"


def cache_tag(language: str = "en") -> str:
    """Identifies this provider+voice in the MP3 cache key, so switching
    provider, voice or language doesn't replay audio in the old one."""
    return f"elevenlabs:{TTS_MODEL}:{ELEVENLABS_VOICE_ID}:{language}"


def available() -> bool:
    return bool(ELEVENLABS_API_KEY)


def describe() -> str:
    # One provider fills both the TTS and the STT slot, so name both models.
    return f"elevenlabs (tts {TTS_MODEL} voice {ELEVENLABS_VOICE_ID}, stt {STT_MODEL})"


def _require_key() -> None:
    if not ELEVENLABS_API_KEY:
        raise VoiceError(
            "ElevenLabs API key not configured. Add ELEVENLABS_API_KEY to backend/.env "
            "and restart the server, or unset VOICE_TTS_PROVIDER/VOICE_STT_PROVIDER to "
            "use the local open-source providers.",
            status_code=503,
        )


def synthesize(text: str, *, language: str = "en") -> bytes:
    """Text -> MP3 bytes. Text is already normalized by voice_client.

    eleven_multilingual_v2 detects the language from the text itself, so
    `language` only takes part in the cache key here.
    """
    _require_key()
    import httpx

    response = httpx.post(
        f"{API_BASE}/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": TTS_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise VoiceError(
            f"ElevenLabs text-to-speech error ({response.status_code}): {response.text[:300]}"
        )
    return response.content


def transcribe(
    audio: bytes, *, filename: str, content_type: str, language: str = "en"
) -> str:
    """Recorded audio (webm/ogg/mp4/wav from the browser) -> text.

    Scribe auto-detects the language, so `language` is accepted only to
    match the provider interface.
    """
    _require_key()
    import httpx

    response = httpx.post(
        f"{API_BASE}/speech-to-text",
        headers={"xi-api-key": ELEVENLABS_API_KEY},
        data={"model_id": STT_MODEL, "tag_audio_events": "false"},
        files={"file": (filename, audio, content_type)},
        timeout=60,
    )
    if response.status_code != 200:
        raise VoiceError(
            f"ElevenLabs speech-to-text error ({response.status_code}): {response.text[:300]}"
        )
    return (response.json().get("text") or "").strip()
