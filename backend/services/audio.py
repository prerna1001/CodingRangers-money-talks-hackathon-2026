"""ffmpeg wrappers shared by the local voice providers.

Kokoro emits raw float samples and the browser's MediaRecorder sends
webm/opus, but the chat UI wants MP3 and Whisper wants 16 kHz mono
floats -- so both directions go through ffmpeg. ffmpeg is a demo-machine
prerequisite rather than a pip dependency (macOS: `brew install ffmpeg`),
hence the explicit check with an actionable message.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import wave

import numpy as np

from services.voice_errors import VoiceError

WHISPER_SAMPLE_RATE = 16_000


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        raise VoiceError(
            "ffmpeg not found on PATH. Install it (macOS: `brew install ffmpeg`) "
            "to use the local voice providers, or set VOICE_TTS_PROVIDER=elevenlabs.",
            status_code=503,
        )
    return path


def _run(args: list[str], payload: bytes, *, what: str) -> bytes:
    proc = subprocess.run(args, input=payload, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise VoiceError(f"ffmpeg failed to {what}: {(tail[-1] if tail else 'no output')[:300]}")
    return proc.stdout


def samples_to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    """float32 [-1, 1] mono samples -> 16-bit PCM WAV bytes (no ffmpeg needed)."""
    clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


def samples_to_mp3(samples: np.ndarray, sample_rate: int) -> bytes:
    """Synthesized samples -> MP3, so the routes keep returning audio/mpeg.

    96 kbps mono is transparent for speech and keeps the cached briefing
    small enough to re-download over venue wifi.
    """
    return _run(
        [
            _ffmpeg(), "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0",
            "-codec:a", "libmp3lame", "-b:a", "96k",
            "-f", "mp3", "pipe:1",
        ],
        samples_to_wav(samples, sample_rate),
        what="encode MP3",
    )


def recording_to_samples(audio: bytes) -> np.ndarray:
    """Whatever the browser recorded (webm/ogg/mp4/wav) -> what Whisper wants.

    MediaRecorder clips routinely arrive without container duration
    metadata, which trips up in-process decoders; ffmpeg reads them anyway,
    so decoding here is more reliable than handing bytes to faster-whisper.
    """
    raw = _run(
        [
            _ffmpeg(), "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0",
            "-ac", "1", "-ar", str(WHISPER_SAMPLE_RATE),
            "-f", "f32le", "pipe:1",
        ],
        audio,
        what="decode the recording",
    )
    return np.frombuffer(raw, dtype="<f4")
