"""Provider-agnostic voice layer: text -> speech and speech -> text.

Which provider runs is set by VOICE_TTS_PROVIDER / VOICE_STT_PROVIDER
(config.py). The defaults are the local open-source stack -- Kokoro-82M
(Apache-2.0) and faster-whisper (MIT) -- so voice works offline with no
API key and no per-call cost; set either to "elevenlabs" to go back to
the hosted provider.

Normalization, MP3 caching and the pre-rendered demo fallback live here
rather than in a provider, so every provider gets them and the cache key
changes whenever the provider or voice does (plan sections 16.2, 18.1).

The scripts it's given must already be the output of
agents/report_writer.to_voice_script() -- built only from an APPROVED
Explanation -- so no provider here can ever speak a claim the guardrail
rejected.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from types import ModuleType

from config import (
    TRANSLATION_SUPPORTED_LANGUAGES,
    UI_DEFAULT_LANGUAGE,
    VOICE_STT_PROVIDER,
    VOICE_TTS_PROVIDER,
)
from services.speech_normalizer import normalize
from services.voice_errors import VoiceError

logger = logging.getLogger(__name__)

CACHE_DIR = Path("./.cache/voice")
FALLBACK_MP3 = Path("./data/fallback_briefing.mp3")

TTS_PROVIDERS = ("kokoro", "elevenlabs")
STT_PROVIDERS = ("whisper", "elevenlabs")

# Re-exported so routes can keep catching voice_client.VoiceError.
__all__ = ["VoiceError", "generate", "status", "synthesize", "transcribe"]


def _tts_provider() -> ModuleType:
    """Imported lazily: loading a provider shouldn't drag in onnxruntime or
    httpx on a server start that never speaks."""
    if VOICE_TTS_PROVIDER == "kokoro":
        from services import kokoro_tts

        return kokoro_tts
    if VOICE_TTS_PROVIDER == "elevenlabs":
        from services import elevenlabs_client

        return elevenlabs_client
    raise VoiceError(
        f"Unknown VOICE_TTS_PROVIDER {VOICE_TTS_PROVIDER!r}. "
        f"Expected one of: {', '.join(TTS_PROVIDERS)}.",
        status_code=503,
    )


def _stt_provider() -> ModuleType:
    if VOICE_STT_PROVIDER == "whisper":
        from services import whisper_stt

        return whisper_stt
    if VOICE_STT_PROVIDER == "elevenlabs":
        from services import elevenlabs_client

        return elevenlabs_client
    raise VoiceError(
        f"Unknown VOICE_STT_PROVIDER {VOICE_STT_PROVIDER!r}. "
        f"Expected one of: {', '.join(STT_PROVIDERS)}.",
        status_code=503,
    )


def _check_language(language: str) -> str:
    if language not in TRANSLATION_SUPPORTED_LANGUAGES:
        raise VoiceError(
            f"Unsupported voice language {language!r}. "
            f"Supported: {', '.join(TRANSLATION_SUPPORTED_LANGUAGES)}.",
            status_code=400,
        )
    return language


def _cache_path(provider: ModuleType, text: str, prefix: str, language: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{provider.cache_tag(language)}:{text}".encode()).hexdigest()[:24]
    return CACHE_DIR / f"{prefix}{key}.mp3"


def synthesize(text: str, *, language: str = UI_DEFAULT_LANGUAGE) -> bytes:
    """Text -> MP3 bytes for the chat "read aloud" button. Cached by text.

    The caller passes the language the text is already in -- translation
    happens before this point (services/translator.py), so the voice just
    needs to know which one to speak.

    Raises VoiceError, so the chat UI can say what went wrong instead of
    silently playing the demo fallback recording.
    """
    _check_language(language)
    provider = _tts_provider()
    text = normalize(text)
    cache_path = _cache_path(provider, text, "chat_", language)
    if cache_path.exists():
        return cache_path.read_bytes()

    audio = provider.synthesize(text, language=language)
    cache_path.write_bytes(audio)
    return audio


def transcribe(
    audio: bytes, *, filename: str, content_type: str, language: str = UI_DEFAULT_LANGUAGE
) -> str:
    """Recorded audio from the browser -> text. Raises VoiceError."""
    _check_language(language)
    return _stt_provider().transcribe(
        audio, filename=filename, content_type=content_type, language=language
    )


def generate(script: str, *, language: str = UI_DEFAULT_LANGUAGE) -> Path | None:
    """The CFO voice briefing: returns a path to an MP3, or None if neither
    synthesis nor the fallback recording is available. Never raises.

    Falls back to a pre-rendered MP3 so a missing model or a flaky
    connection on stage never blocks the demo (plan sections 16.2, 18.1).
    """
    script = normalize(script)
    try:
        _check_language(language)
        provider = _tts_provider()
        cache_path = _cache_path(provider, script, "", language)
        if cache_path.exists():
            return cache_path
        cache_path.write_bytes(provider.synthesize(script, language=language))
        return cache_path
    except Exception as exc:  # noqa: BLE001 - graceful degradation by design
        logger.warning("voice.generate failed (tts=%s): %s", VOICE_TTS_PROVIDER, exc)
        return FALLBACK_MP3 if FALLBACK_MP3.exists() else None


def status() -> dict:
    """What /api/health reports: which providers are selected and whether
    each one could actually run right now."""
    out = {
        "tts_provider": VOICE_TTS_PROVIDER,
        "stt_provider": VOICE_STT_PROVIDER,
        "tts_ready": False,
        "stt_ready": False,
        "fallback_recording": FALLBACK_MP3.exists(),
    }
    for key, resolve in (("tts", _tts_provider), ("stt", _stt_provider)):
        try:
            provider = resolve()
            out[f"{key}_ready"] = provider.available()
            out[f"{key}_detail"] = provider.describe()
        except VoiceError as exc:
            out[f"{key}_detail"] = str(exc)
    return out
