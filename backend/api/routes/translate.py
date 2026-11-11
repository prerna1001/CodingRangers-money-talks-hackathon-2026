"""POST /api/translate -- screen/UI translation for English and Spanish.

Backs the frontend's language toggle: the UI sends every string it is
about to show in one batch and swaps in what comes back. Static labels
and LLM-written analysis text go through the same endpoint, so newly
generated content is translated too, not just the chrome.

services/translator.py runs the models locally and caches by string, so a
toggle back and forth costs nothing after the first pass.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import TRANSLATION_MAX_TEXTS, UI_DEFAULT_LANGUAGE
from services import translator

router = APIRouter()


class TranslateRequest(BaseModel):
    texts: list[str] = Field(default_factory=list)
    target: str
    source: str = UI_DEFAULT_LANGUAGE


class TranslateResponse(BaseModel):
    translations: list[str]
    source: str
    target: str
    engine: str


@router.get("/translate/languages")
def languages() -> dict:
    return {
        "languages": translator.supported_languages(),
        "default": UI_DEFAULT_LANGUAGE,
        "max_texts": TRANSLATION_MAX_TEXTS,
        "engine": translator.describe(),
    }


@router.post("/translate")
def translate(body: TranslateRequest) -> TranslateResponse:
    if not body.texts:
        return TranslateResponse(
            translations=[], source=body.source, target=body.target, engine=translator.describe()
        )
    try:
        translations = translator.translate(
            body.texts, target=body.target, source=body.source
        )
    except translator.TranslationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return TranslateResponse(
        translations=translations,
        source=body.source,
        target=body.target,
        engine=translator.describe(),
    )
