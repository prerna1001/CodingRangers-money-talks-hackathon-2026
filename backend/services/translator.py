"""English <-> Spanish machine translation for the UI and the analysis text.

Helsinki-NLP's OPUS-MT models (MarianMT) run locally through transformers,
which sentence-transformers already puts in the venv -- so translation
adds no service, no API key and no per-call cost, same as the voice
providers. Each direction is a separate ~78M-parameter model, small
enough to run on CPU in a fraction of a second per batch.

Chosen over Argos Translate (the other strong open-source option) because
Argos pulls in spacy and stanza, and over the Google Translate API because
that one bills per character -- the charge the team hit with ElevenLabs.

Translations are cached in-process and keyed by direction, so the UI can
re-request the same labels on every language toggle without re-running
the model.
"""

from __future__ import annotations

import logging
import threading

from config import (
    TRANSLATION_MAX_CHARS,
    TRANSLATION_MAX_TEXTS,
    TRANSLATION_MODELS,
    TRANSLATION_SUPPORTED_LANGUAGES,
)

logger = logging.getLogger(__name__)


class TranslationError(RuntimeError):
    """503 for a setup problem (missing package or model), 502 for a
    failure during an otherwise-working translation."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


_models: dict[str, tuple] = {}
_cache: dict[tuple[str, str], str] = {}
_lock = threading.Lock()

# Plenty for a UI's worth of labels plus a run's analysis text; keeps a
# long demo session from growing the cache without bound.
MAX_CACHE_ENTRIES = 5_000


def available() -> bool:
    """Cheap enough for /api/health: checks the package, not the weights."""
    import importlib.util

    return importlib.util.find_spec("transformers") is not None


def describe() -> str:
    pairs = ", ".join(sorted(TRANSLATION_MODELS))
    return f"opus-mt ({pairs})"


def supported_languages() -> list[str]:
    return list(TRANSLATION_SUPPORTED_LANGUAGES)


def _pair_key(source: str, target: str) -> str:
    return f"{source}-{target}"


def _load(source: str, target: str):
    pair = _pair_key(source, target)
    cached = _models.get(pair)
    if cached is not None:
        return cached

    model_name = TRANSLATION_MODELS.get(pair)
    if model_name is None:
        raise TranslationError(
            f"No translation model configured for {source!r} -> {target!r}. "
            f"Supported: {', '.join(sorted(TRANSLATION_MODELS))}.",
            status_code=400,
        )

    with _lock:
        if pair in _models:  # another request won the race while we waited
            return _models[pair]

        try:
            from transformers import MarianMTModel, MarianTokenizer
        except ImportError as exc:
            raise TranslationError(
                "transformers is not installed. Run `pip install -r requirements.txt`.",
                status_code=503,
            ) from exc

        try:
            tokenizer = MarianTokenizer.from_pretrained(model_name)
            model = MarianMTModel.from_pretrained(model_name)
            model.eval()
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller
            raise TranslationError(
                f"Translation model {model_name!r} failed to load: {exc}", status_code=503
            ) from exc

        _models[pair] = (tokenizer, model)
        logger.info("translator.loaded %s (%s)", pair, model_name)
        return _models[pair]


def _translate_uncached(texts: list[str], source: str, target: str) -> list[str]:
    tokenizer, model = _load(source, target)
    try:
        import torch

        batch = tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        with torch.inference_mode():
            generated = model.generate(**batch, max_new_tokens=512)
        return tokenizer.batch_decode(generated, skip_special_tokens=True)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller
        raise TranslationError(f"Translation failed: {exc}") from exc


def translate(texts: list[str], *, target: str, source: str = "en") -> list[str]:
    """Translate a batch, preserving order. Raises TranslationError.

    Same-language requests, blank strings and anything already cached skip
    the model entirely, so a language toggle only pays for what is new.
    """
    if len(texts) > TRANSLATION_MAX_TEXTS:
        raise TranslationError(
            f"Too many texts in one request ({len(texts)} > {TRANSLATION_MAX_TEXTS}).",
            status_code=400,
        )
    for language in (source, target):
        if language not in TRANSLATION_SUPPORTED_LANGUAGES:
            raise TranslationError(
                f"Unsupported language {language!r}. "
                f"Supported: {', '.join(TRANSLATION_SUPPORTED_LANGUAGES)}.",
                status_code=400,
            )

    if source == target:
        return list(texts)

    pair = _pair_key(source, target)
    out: list[str | None] = [None] * len(texts)
    todo: dict[str, list[int]] = {}

    for index, text in enumerate(texts):
        clipped = (text or "")[:TRANSLATION_MAX_CHARS]
        if not clipped.strip():
            out[index] = text
            continue
        hit = _cache.get((pair, clipped))
        if hit is not None:
            out[index] = hit
        else:
            # One entry per distinct string: a repeated label is translated once.
            todo.setdefault(clipped, []).append(index)

    if todo:
        originals = list(todo)
        translated = _translate_uncached(originals, source, target)
        if len(_cache) > MAX_CACHE_ENTRIES:
            _cache.clear()
        for original, result in zip(originals, translated):
            _cache[(pair, original)] = result
            for index in todo[original]:
                out[index] = result

    return [text if value is None else value for text, value in zip(texts, out)]


def status() -> dict:
    """What /api/health reports."""
    return {
        "ready": available(),
        "engine": describe(),
        "languages": supported_languages(),
        "loaded_pairs": sorted(_models),
        "cached_strings": len(_cache),
    }
