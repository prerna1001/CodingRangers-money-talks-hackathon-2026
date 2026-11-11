"""POST /api/voice/{run_id} -- CFO voice briefing (plan section 16.2).

The script is generated only from an APPROVED Explanation
(agents/report_writer.to_voice_script), so the voice can never say
anything the Guardrail rejected. services/voice_client.py already
handles provider choice (local Kokoro/Whisper by default, ElevenLabs when
configured) and the synthesis-vs-fallback-recording decision; this route
just wires that into HTTP.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import auth0_setup
from agents import report_writer as report_writer_agent
from api.routes.analyze import get_run_or_404
from config import UI_DEFAULT_LANGUAGE
from services import translator, voice_client

router = APIRouter()

MAX_SPEAK_CHARS = 2500


class SpeakRequest(BaseModel):
    text: str
    # The language to speak in. The caller sends text already in that
    # language; `translate` asks the backend to translate it first, which is
    # what the UI does when the screen is in Spanish but the analysis text
    # came back from the LLM in English.
    language: str = UI_DEFAULT_LANGUAGE
    translate: bool = False


# Chatbot voice routes. Declared before /voice/{run_id} so "speak" and
# "transcribe" aren't swallowed as run ids.
@router.post("/voice/speak")
def speak(body: SpeakRequest) -> Response:
    text = body.text.strip()[:MAX_SPEAK_CHARS]
    if not text:
        raise HTTPException(status_code=400, detail="Nothing to read aloud")
    try:
        if body.translate and body.language != UI_DEFAULT_LANGUAGE:
            text = translator.translate(
                [text], target=body.language, source=UI_DEFAULT_LANGUAGE
            )[0]
        audio = voice_client.synthesize(text, language=body.language)
    except translator.TranslationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except voice_client.VoiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/voice/transcribe")
async def transcribe(file: UploadFile, language: str = Form(UI_DEFAULT_LANGUAGE)) -> dict:
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="No audio received")
    try:
        text = voice_client.transcribe(
            audio,
            filename=file.filename or "recording.webm",
            content_type=file.content_type or "audio/webm",
            language=language,
        )
    except voice_client.VoiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"text": text, "language": language}


def _script_for_run(run_id: str, *, user_id: str) -> str:
    state = get_run_or_404(run_id, user_id=user_id)
    explanation = state.get("explanation")
    if explanation is None:
        raise HTTPException(status_code=404, detail=f"No explanation available for run {run_id}")
    return report_writer_agent.to_voice_script(explanation)


@router.post("/voice/{run_id}")
def generate_voice_briefing(
    run_id: str, user_id: str = Depends(auth0_setup.get_current_user_id)
) -> dict:
    script = _script_for_run(run_id, user_id=user_id)
    audio_path = voice_client.generate(script)
    if audio_path is None:
        raise HTTPException(
            status_code=503,
            detail="Voice briefing unavailable: speech synthesis failed and no fallback recording was found.",
        )
    return {"run_id": run_id, "script": script, "audio_url": f"/api/voice/{run_id}/audio"}


@router.get("/voice/{run_id}/audio")
def get_voice_audio(run_id: str, user_id: str = Depends(auth0_setup.get_current_user_id)):
    script = _script_for_run(run_id, user_id=user_id)
    audio_path = voice_client.generate(script)
    if audio_path is None or not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not available")
    return FileResponse(audio_path, media_type="audio/mpeg")
