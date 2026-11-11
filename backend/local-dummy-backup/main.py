import os
import random
import string

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

load_dotenv()

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

app = FastAPI(title="FinOps Explain AI - Dummy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def detect_file_type(filename: str) -> str:
    name = filename.lower()
    if "transaction" in name:
        return "transaction_csv"
    if "summary" in name:
        return "monthly_summary_csv"
    return "unknown_csv"


@app.post("/api/upload")
async def upload_file(file: UploadFile):
    raw = await file.read()
    text = raw.decode("utf-8", errors="ignore")
    rows_detected = max(len([line for line in text.splitlines() if line.strip()]) - 1, 0)

    return {
        "status": "success",
        "file_id": "file_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)),
        "filename": file.filename,
        "type": detect_file_type(file.filename or ""),
        "rows_detected": rows_detected,
        "size_bytes": len(raw),
    }


# Dummy Analyzer/Researcher output. Shape matches HACKATHON_PLAN.original.md
# section "5. Analyzer / Researcher Agent", plus a waterfall series for the
# dashboard chart and an agent_timeline used to drive the frontend's
# processing animation. Real agent orchestration (LangGraph) replaces this
# constant later — the response contract stays the same. Also used to ground
# the /api/chat answers below, so the chatbot and the dashboard never disagree.
MOCK_ANALYSIS = {
    "headline": "Revenue increased 18% month over month.",
    "summary": (
        "The increase was mainly driven by enterprise expansion revenue across "
        "three key accounts, partially offset by SMB churn and lower services revenue."
    ),
    "confidence": 0.91,
    "data_quality_score": 0.96,
    "periods": {
        "prior": {"id": "2026-07", "label": "Jul 2026", "revenue": 155000},
        "current": {"id": "2026-08", "label": "Aug 2026", "revenue": 183000},
    },
    "waterfall": [
        {"name": "Jul Revenue", "value": 155000, "type": "start"},
        {"name": "Enterprise Expansion", "value": 42000, "type": "increase"},
        {"name": "SMB Churn", "value": -9000, "type": "decrease"},
        {"name": "Services Revenue", "value": -5000, "type": "decrease"},
        {"name": "Aug Revenue", "value": 183000, "type": "end"},
    ],
    "drivers": [
        {
            "driver": "Enterprise subscription expansion",
            "account": "Subscription revenue",
            "current": 124000,
            "prior": 82000,
            "amount": 42000,
            "share_of_change_pct": 64,
            "confidence": 0.91,
            "evidence": [
                "Northwind Labs +$18,000",
                "AtlasGrid +$14,000",
                "Meridian Health +$10,000",
            ],
        },
        {
            "driver": "SMB churn",
            "account": "Subscription revenue",
            "current": 21000,
            "prior": 30000,
            "amount": -9000,
            "share_of_change_pct": -14,
            "confidence": 0.84,
            "evidence": ["6 SMB accounts cancelled", "Largest single loss: -$2,400"],
        },
        {
            "driver": "Professional services slowdown",
            "account": "Services revenue",
            "current": 15000,
            "prior": 20000,
            "amount": -5000,
            "share_of_change_pct": -8,
            "confidence": 0.78,
            "evidence": ["2 fewer onboarding engagements vs. prior month"],
        },
    ],
    "risks_or_caveats": [
        "One customer accounts for 27% of the increase, creating concentration risk.",
        "Services revenue has declined two months in a row.",
    ],
    "agent_timeline": [
        {"name": "Profile Builder", "status": "passed", "duration_ms": 450},
        {"name": "Fetch Tester / Data QA", "status": "passed_with_warnings", "duration_ms": 380},
        {"name": "Memory Agent", "status": "passed", "duration_ms": 260},
        {"name": "RAG Agent", "status": "passed", "duration_ms": 320},
        {"name": "Analyzer / Researcher", "status": "passed", "duration_ms": 600},
        {"name": "Safety Guardrail", "status": "passed", "duration_ms": 260},
        {"name": "Stress Test", "status": "passed", "duration_ms": 340},
        {"name": "Report Writer", "status": "passed", "duration_ms": 200},
    ],
}


class AnalyzeRequest(BaseModel):
    file_id: str | None = None


@app.post("/api/analyze")
async def analyze(_body: AnalyzeRequest | None = None):
    return {
        "run_id": "run_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)),
        **MOCK_ANALYSIS,
    }


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


def build_chat_reply(message: str) -> str:
    # Deterministic, rule-based FAQ bot grounded in MOCK_ANALYSIS — a stand-in
    # for the real RAG-backed Analyzer agent from the plan doc. Swap this
    # function's body for a real LLM/agent call later; the endpoint contract
    # (ChatRequest in, {"reply": str} out) does not need to change.
    text = message.lower()
    top_driver = max(MOCK_ANALYSIS["drivers"], key=lambda d: abs(d["amount"]))

    if any(word in text for word in ["risk", "caveat", "concern", "worried"]):
        risks = " ".join(MOCK_ANALYSIS["risks_or_caveats"])
        return f"Here are the flagged risks for this run: {risks}"

    if any(word in text for word in ["churn", "lost", "cancel"]):
        churn = next(d for d in MOCK_ANALYSIS["drivers"] if "churn" in d["driver"].lower())
        return (
            f"{churn['driver']} moved revenue from ${churn['prior']:,} to ${churn['current']:,} "
            f"({churn['amount']:+,}), driven by: {'; '.join(churn['evidence'])}."
        )

    if any(word in text for word in ["driver", "why", "cause", "reason"]):
        sign = "+" if top_driver["amount"] >= 0 else "-"
        return (
            f"The top driver is {top_driver['driver']}, contributing "
            f"{top_driver['share_of_change_pct']}% of the change "
            f"({sign}${abs(top_driver['amount']):,}). "
            f"Evidence: {'; '.join(top_driver['evidence'])}."
        )

    if any(word in text for word in ["confiden", "quality", "trust", "sure"]):
        return (
            f"Confidence on this run is {round(MOCK_ANALYSIS['confidence'] * 100)}%, with a data "
            f"quality score of {round(MOCK_ANALYSIS['data_quality_score'] * 100)}%."
        )

    if any(word in text for word in ["revenue", "total", "how much"]):
        prior = MOCK_ANALYSIS["periods"]["prior"]
        current = MOCK_ANALYSIS["periods"]["current"]
        return (
            f"Revenue went from ${prior['revenue']:,} in {prior['label']} to "
            f"${current['revenue']:,} in {current['label']}."
        )

    if any(word in text for word in ["hi", "hello", "hey"]):
        return "Hi! Ask me about drivers, risks, confidence, or revenue for this run."

    return (
        f"{MOCK_ANALYSIS['headline']} {MOCK_ANALYSIS['summary']} "
        "Ask me about a specific driver, risk, or the confidence score for more detail."
    )


@app.post("/api/chat")
async def chat(body: ChatRequest):
    return {"reply": build_chat_reply(body.message)}


class SpeakRequest(BaseModel):
    text: str


@app.post("/api/voice/speak")
async def speak(body: SpeakRequest):
    if not ELEVENLABS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ElevenLabs API key not configured. Add ELEVENLABS_API_KEY to backend/.env and restart the server.",
        )

    response = requests.post(
        ELEVENLABS_TTS_URL.format(voice_id=ELEVENLABS_VOICE_ID),
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": body.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {response.text}")

    return Response(content=response.content, media_type="audio/mpeg")
