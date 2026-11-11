"""Kokoro-82M text-to-speech -- the default, offline voice provider.

Apache-2.0 weights run through ONNX Runtime (which chromadb already pulls
in), so the CFO briefing and the chat "read aloud" button need no API key
and cost nothing per call. Picked over the PyTorch `kokoro` package
because that one caps at Python <3.13 and this venv is on 3.14.

kokoro-onnx is pinned to 0.4.7 for the same reason -- every later release
caps at <3.14 -- and 0.4.7's own create() passes `speed` to this model
export as int32 where the model wants float, so synthesis runs the ONNX
session here instead. We use the library for what it is good at
(phonemizing text and holding the voice styles) and feed the model
ourselves.

The model is loaded once, lazily: building the session costs a couple of
seconds, which shouldn't be paid by a server start that may never
synthesize anything. Caching of the finished MP3 lives in voice_client.py.
"""

from __future__ import annotations

import importlib.util
import logging
import threading
from pathlib import Path

import numpy as np

from config import (
    KOKORO_LANG,
    KOKORO_MODEL_DIR,
    KOKORO_MODEL_FILE,
    KOKORO_RELEASE_URL,
    KOKORO_SPEED,
    KOKORO_VOICE,
    KOKORO_VOICE_ES,
    KOKORO_VOICES_FILE,
)
from services import audio as audio_utils
from services.voice_errors import VoiceError

logger = logging.getLogger(__name__)

# Kokoro always emits 24 kHz mono.
SAMPLE_RATE = 24_000

# The model's context is 512 tokens; two are the pad tokens added per batch.
MAX_PHONEME_LENGTH = 510

_model = None
_lock = threading.Lock()


def model_path() -> Path:
    return Path(KOKORO_MODEL_DIR) / KOKORO_MODEL_FILE


def voices_path() -> Path:
    return Path(KOKORO_MODEL_DIR) / KOKORO_VOICES_FILE


def voice_for(language: str) -> str:
    """One checkpoint holds every voice, so a language switch is just a
    different voice and a different phonemizer language."""
    return KOKORO_VOICE if language == "en" else KOKORO_VOICE_ES


def _espeak_lang(language: str) -> str:
    return KOKORO_LANG if language == "en" else language


def cache_tag(language: str = "en") -> str:
    """Identifies this provider+voice in the MP3 cache key, so switching
    provider, voice or language doesn't replay audio in the old one."""
    return f"kokoro:{KOKORO_MODEL_FILE}:{voice_for(language)}:{KOKORO_SPEED}"


def available() -> bool:
    """True when a synthesize() call would not fail on setup alone.

    Deliberately cheap -- /api/health calls this on every poll, so it
    checks for the package and the weights without loading either.
    """
    if importlib.util.find_spec("kokoro_onnx") is None:
        return False
    return model_path().exists() and voices_path().exists()


def describe() -> str:
    return f"kokoro-82m ({KOKORO_MODEL_FILE}, en {KOKORO_VOICE} / es {KOKORO_VOICE_ES})"


def _load():
    global _model
    if _model is not None:
        return _model

    with _lock:
        if _model is not None:  # another request won the race while we waited
            return _model

        try:
            from kokoro_onnx import Kokoro
        except ImportError as exc:
            raise VoiceError(
                "kokoro-onnx is not installed. Run `pip install -r requirements.txt`, "
                "or set VOICE_TTS_PROVIDER=elevenlabs to use the hosted provider.",
                status_code=503,
            ) from exc

        missing = [str(p) for p in (model_path(), voices_path()) if not p.exists()]
        if missing:
            raise VoiceError(
                f"Kokoro weights missing ({', '.join(missing)}). Run "
                f"`python scripts/fetch_voice_models.py` to download them from "
                f"{KOKORO_RELEASE_URL}.",
                status_code=503,
            )

        try:
            _model = Kokoro(str(model_path()), str(voices_path()))
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as VoiceError
            raise VoiceError(f"Kokoro failed to load: {exc}") from exc

        logger.info("kokoro.loaded %s", describe())
        return _model


def _split_phonemes(phonemes: str) -> list[str]:
    """Anything past the model's context has to be synthesized in batches.

    Split on spaces so a word is never cut in half; the pieces are
    concatenated back into one waveform.
    """
    parts: list[str] = []
    current = ""
    for word in phonemes.split(" "):
        if current and len(current) + 1 + len(word) > MAX_PHONEME_LENGTH:
            parts.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        parts.append(current)
    return parts


def _infer(model, phonemes: str, voice: str) -> np.ndarray:
    """One batch of phonemes -> float32 samples, straight through the session."""
    tokens = model.tokenizer.tokenize(phonemes)[:MAX_PHONEME_LENGTH]
    if not tokens:
        return np.zeros(0, dtype=np.float32)

    # Each voice is a stack of styles indexed by token count, so the style
    # has to be picked for this batch's length.
    style = np.asarray(model.get_voice_style(voice)[len(tokens)], dtype=np.float32)
    inputs = {
        "input_ids": np.array([[0, *tokens, 0]], dtype=np.int64),
        "style": style,
        "speed": np.array([KOKORO_SPEED], dtype=np.float32),
    }
    # Pre-v1.0 exports call the token input "tokens" instead.
    if "input_ids" not in {i.name for i in model.sess.get_inputs()}:
        inputs["tokens"] = inputs.pop("input_ids")
    return np.asarray(model.sess.run(None, inputs)[0], dtype=np.float32)


def synthesize(text: str, *, language: str = "en") -> bytes:
    """Text -> MP3 bytes. Text is already normalized by voice_client."""
    model = _load()
    voice = voice_for(language)
    if voice not in model.voices:
        raise VoiceError(
            f"Unknown Kokoro voice {voice!r} for language {language!r}. "
            f"Available: {', '.join(voices())}.",
            status_code=503,
        )
    if not 0.5 <= KOKORO_SPEED <= 2.0:
        raise VoiceError(
            f"KOKORO_SPEED must be between 0.5 and 2.0 (got {KOKORO_SPEED}).",
            status_code=503,
        )

    try:
        phonemes = model.tokenizer.phonemize(text, _espeak_lang(language))
        chunks = [_infer(model, part, voice) for part in _split_phonemes(phonemes)]
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as VoiceError
        raise VoiceError(f"Kokoro speech synthesis failed: {exc}") from exc

    samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    if samples.size == 0:
        raise VoiceError("Kokoro produced no audio for that text")
    return audio_utils.samples_to_mp3(samples, SAMPLE_RATE)


def voices() -> list[str]:
    """Every voice baked into the checkpoint -- handy when picking KOKORO_VOICE."""
    return sorted(_load().get_voices())
