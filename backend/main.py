"""FastAPI app entrypoint (plan section 14.3).

Run with: .venv/Scripts/python.exe -m uvicorn main:app --reload

The `/api/*` routers below are the original Ledgerlight surface and are
unchanged. Auth0 gates them: with a configured tenant every one of them
requires a session, and `GET /` serves the login screen that hands off to the
original application once the callback completes.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import auth0_setup
from api.routes import analyze, health, memory, reports, scenarios, stress_tests, upload, voice
from login_page import login_page, setup_required_page, signed_in_page

app = FastAPI(title="Ledgerlight API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    # The Auth0 session is a cookie, so the browser must be allowed to send
    # and receive credentials on cross-origin calls to :8000. The Vite proxy
    # makes /api same-origin, but direct calls from the frontend do not.
    allow_credentials=True,
)

# Installs SessionMiddleware and mounts /auth/login, /auth/callback,
# /auth/logout. A no-op beyond an ephemeral session cookie while the Auth0
# tenant is unconfigured.
auth0_setup.init_auth(app)

# Every original router keeps its path and tag; the dependency is added only
# when there is a tenant to authenticate against.
guard = [Depends(auth0_setup.require_session)] if auth0_setup.AUTH0_REQUIRED else []

app.include_router(health.router, prefix="/api", tags=["health"], dependencies=guard)
app.include_router(upload.router, prefix="/api", tags=["upload"], dependencies=guard)
app.include_router(analyze.router, prefix="/api", tags=["analyze"], dependencies=guard)
app.include_router(memory.router, prefix="/api", tags=["memory"], dependencies=guard)
app.include_router(stress_tests.router, prefix="/api", tags=["stress-tests"], dependencies=guard)
app.include_router(reports.router, prefix="/api", tags=["reports"], dependencies=guard)
app.include_router(voice.router, prefix="/api", tags=["voice"], dependencies=guard)
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"], dependencies=guard)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, response: Response):
    """Login screen for anonymous visitors; the original application for
    everyone who already has a session."""
    if not auth0_setup.AUTH0_ENABLED:
        return setup_required_page(auth0_setup.status_summary()["missing_env"], auth0_setup.APP_URL)

    session = await auth0_setup.current_session(request, response)
    if not session:
        return login_page("/auth/login", auth0_setup.APP_URL)

    user = await auth0_setup.current_user(request, response)
    return signed_in_page(user, "/auth/logout", auth0_setup.APP_URL)


@app.get("/profile")
async def profile(
    request: Request,
    response: Response,
    session=Depends(auth0_setup.require_session),
):
    """Protected endpoint returning the Auth0 user and session claims."""
    user = await auth0_setup.current_user(request, response)
    return {
        "message": "Your Profile",
        "user": user,
        "session_details": session,
    }


@app.get("/api/auth/status")
async def auth_status():
    """Unauthenticated by design: the frontend calls this on boot to decide
    whether to show a sign-in button or go straight to the dashboard."""
    return auth0_setup.status_summary()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
