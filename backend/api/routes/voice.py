"""POST /api/voice/{run_id} -- CFO voice briefing (plan section 16.2).

The script is generated only from an APPROVED Explanation
(agents/report_writer.to_voice_script), so the voice can never say
anything the Guardrail rejected. services/elevenlabs_client.py already
handles the live-call-vs-fallback-recording decision; this route just
wires that into HTTP.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from agents import report_writer as report_writer_agent
from api.routes.analyze import get_run_or_404
from services import elevenlabs_client

router = APIRouter()


def _script_for_run(run_id: str) -> str:
    state = get_run_or_404(run_id)
    explanation = state.get("explanation")
    if explanation is None:
        raise HTTPException(status_code=404, detail=f"No explanation available for run {run_id}")
    return report_writer_agent.to_voice_script(explanation)


@router.post("/voice/{run_id}")
def generate_voice_briefing(run_id: str) -> dict:
    script = _script_for_run(run_id)
    audio_path = elevenlabs_client.generate(script)
    if audio_path is None:
        raise HTTPException(
            status_code=503,
            detail="Voice briefing unavailable: no ELEVENLABS_API_KEY configured and no fallback recording found.",
        )
    return {"run_id": run_id, "script": script, "audio_url": f"/api/voice/{run_id}/audio"}


@router.get("/voice/{run_id}/audio")
def get_voice_audio(run_id: str):
    script = _script_for_run(run_id)
    audio_path = elevenlabs_client.generate(script)
    if audio_path is None or not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not available")
    return FileResponse(audio_path, media_type="audio/mpeg")
