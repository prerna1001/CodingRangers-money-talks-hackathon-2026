"""Pre-download the local voice and translation models, so the first demo
request doesn't pay for the download over venue wifi (plan section 18.1).

Fetches the Kokoro ONNX checkpoint and voice pack from the kokoro-onnx
release, then warms the faster-whisper and OPUS-MT models so their Hugging
Face downloads happen now too. All of it is a no-op once cached.

Usage:
    venv/bin/python scripts/fetch_voice_models.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


def _download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  already have {dest.name} ({dest.stat().st_size / 1e6:.0f}MB)")
        return
    print(f"  downloading {dest.name} from {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # .part first, so an interrupted download isn't mistaken for a good one.
    part = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, part)
    part.rename(dest)
    print(f"  saved {dest.name} ({dest.stat().st_size / 1e6:.0f}MB)")


def main() -> int:
    print(f"Kokoro TTS -> {config.KOKORO_MODEL_DIR}")
    model_dir = Path(config.KOKORO_MODEL_DIR)
    for filename in (config.KOKORO_MODEL_FILE, config.KOKORO_VOICES_FILE):
        _download(f"{config.KOKORO_RELEASE_URL}/{filename}", model_dir / filename)

    print(f"faster-whisper -> {config.WHISPER_MODEL} (Hugging Face cache)")
    try:
        from faster_whisper import WhisperModel

        WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
        )
        print("  ready")
    except ImportError:
        print("  faster-whisper not installed -- run `pip install -r requirements.txt`")
        return 1

    print("translation -> OPUS-MT (Hugging Face cache)")
    try:
        from transformers import MarianMTModel, MarianTokenizer

        for pair, model_name in sorted(config.TRANSLATION_MODELS.items()):
            MarianTokenizer.from_pretrained(model_name)
            MarianMTModel.from_pretrained(model_name)
            print(f"  {pair} ready ({model_name})")
    except ImportError:
        print("  transformers not installed -- run `pip install -r requirements.txt`")
        return 1

    print("\nVoice and translation models are cached. Both work offline from here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
