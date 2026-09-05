"""FastAPI app entrypoint (plan section 14.3).

Run with: .venv/Scripts/python.exe -m uvicorn main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import analyze, health, memory, reports, scenarios, stress_tests, upload, voice

app = FastAPI(title="Ledgerlight API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(memory.router, prefix="/api", tags=["memory"])
app.include_router(stress_tests.router, prefix="/api", tags=["stress-tests"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(voice.router, prefix="/api", tags=["voice"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
