"""faster-whisper speech-to-text -- the default, offline STT provider.

MIT-licensed CTranslate2 port of OpenAI's Whisper (MIT weights), so the
chat panel's mic button needs no API key and costs nothing per minute.
`small.en` at int8 on CPU handles the short spoken questions this app
gets in about a second on an M-series laptop.

Like the TTS provider, the model loads once and lazily -- the first
transcription pays for the load (and, on a clean machine, the ~500MB
model download from Hugging Face).
"""

from __future__ import annotations

import importlib.util
import logging
import threading

from config import (
    WHISPER_BEAM_SIZE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
    WHISPER_MODEL_MULTILINGUAL,
)
from services import audio as audio_utils
from services.voice_errors import VoiceError

logger = logging.getLogger(__name__)

# Shorter than this is a mis-click, not a question. Transcribing near-silence
# is how Whisper produces its classic hallucinations ("Thank you.", "Bye.").
MIN_SECONDS = 0.25

_models: dict[str, object] = {}
_lock = threading.Lock()


def available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def describe() -> str:
    return (
        f"faster-whisper (en {WHISPER_MODEL} / other {WHISPER_MODEL_MULTILINGUAL}, "
        f"{WHISPER_DEVICE}/{WHISPER_COMPUTE_TYPE})"
    )


def model_for(language: str) -> str:
    """An ".en" checkpoint can only decode English, so anything else has to
    go to the multilingual one."""
    if language == "en" or not WHISPER_MODEL.endswith(".en"):
        return WHISPER_MODEL
    return WHISPER_MODEL_MULTILINGUAL


def _load(name: str):
    cached = _models.get(name)
    if cached is not None:
        return cached

    with _lock:
        if name in _models:  # another request won the race while we waited
            return _models[name]

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise VoiceError(
                "faster-whisper is not installed. Run `pip install -r requirements.txt`, "
                "or set VOICE_STT_PROVIDER=elevenlabs to use the hosted provider.",
                status_code=503,
            ) from exc

        try:
            _models[name] = WhisperModel(
                name, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as VoiceError
            raise VoiceError(
                f"Whisper model {name!r} failed to load: {exc}", status_code=503
            ) from exc

        logger.info("whisper.loaded %s (%s)", name, WHISPER_DEVICE)
        return _models[name]


def transcribe(
    audio: bytes, *, filename: str = "", content_type: str = "", language: str = "en"
) -> str:
    """Recorded audio (webm/ogg/mp4/wav from the browser) -> text.

    filename/content_type are part of the provider interface (ElevenLabs
    needs them for its multipart upload); ffmpeg sniffs the container
    itself, so they're unused here.
    """
    samples = audio_utils.recording_to_samples(audio)
    if samples.size < audio_utils.WHISPER_SAMPLE_RATE * MIN_SECONDS:
        return ""

    name = model_for(language)
    model = _load(name)
    # An .en model only does English, whatever was asked for.
    decode_language = "en" if name.endswith(".en") else (language or WHISPER_LANGUAGE or None)

    try:
        segments, _info = model.transcribe(
            samples,
            beam_size=WHISPER_BEAM_SIZE,
            language=decode_language,
            # Each clip is a standalone question, so don't let the previous
            # one bias the decode.
            condition_on_previous_text=False,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as VoiceError
        raise VoiceError(f"Whisper transcription failed: {exc}") from exc
