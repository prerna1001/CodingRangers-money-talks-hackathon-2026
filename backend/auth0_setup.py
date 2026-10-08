"""Auth0 wiring for the Ledgerlight API.

Everything in this module is opt-in. If the Auth0 tenant variables are not
filled in, the app still boots and every route still works -- the API simply
runs unauthenticated. That matters here because the demo path, the unit tests,
and the Vite dev server all come up before anyone has created an Auth0
application, and a hard failure at import time would take the whole backend
down rather than just the login page.

Once AUTH0_DOMAIN / AUTH0_CLIENT_ID / AUTH0_CLIENT_SECRET / SESSION_SECRET
are real values, `AUTH0_ENABLED` flips to True and:

  * `SessionMiddleware` is installed (it signs the SDK's session cookie),
  * `/auth/login`, `/auth/callback`, `/auth/logout` are mounted,
  * `require_session` gates the existing `/api/*` routers,
  * `GET /` forwards browsers to the frontend homepage (the Vite app at
    `APP_URL`), where the public homepage owns the sign-in button.
"""

from __future__ import annotations

import os
import secrets
from typing import Any
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

# Sentinel for an unconfigured secret. Handing a predictable value to the
# session cookie would let anyone forge a session, so this is deliberately
# *not* a fixed dev string: it is random per process, which means sessions
# simply do not survive a restart while the tenant is being set up.
_UNSAFE_DEV_SECRET = secrets.token_hex(32)

_TRUTHY = {"1", "true", "yes", "on"}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in _TRUTHY


APP_BASE_URL = _env("APP_BASE_URL", "http://localhost:8000").rstrip("/")
# Where a completed sign-in lands: the original Ledgerlight application.
APP_URL = _env("APP_URL", "http://localhost:5173").rstrip("/")

AUTH0_DOMAIN = _env("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = _env("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = _env("AUTH0_CLIENT_SECRET")
SESSION_SECRET = _env("SESSION_SECRET")

_PLACEHOLDER_PREFIXES = ("your-", "your_tenant", "changeme", "xxx")
_MISSING: list[str] = [
    name
    for name, value in (
        ("AUTH0_DOMAIN", AUTH0_DOMAIN),
        ("AUTH0_CLIENT_ID", AUTH0_CLIENT_ID),
        ("AUTH0_CLIENT_SECRET", AUTH0_CLIENT_SECRET),
        ("SESSION_SECRET", SESSION_SECRET),
    )
    if not value or value.lower().startswith(_PLACEHOLDER_PREFIXES)
]

AUTH0_ENABLED = not _MISSING
# Fail closed by default: a half-configured tenant should return 401, not
# serve the ledger to anonymous callers. AUTH0_REQUIRED=0 is the deliberate
# escape hatch for local work before the tenant exists.
AUTH0_REQUIRED = _env_bool("AUTH0_REQUIRED", True) if AUTH0_ENABLED else False

# Written by the frontend (Frontend/src/pages/HomePage.jsx) just before it
# sends the browser off to sign in. Cookies ignore ports, so a cookie set on
# localhost:5173 is sent to localhost:8000 too, which is what makes this
# survive the Auth0 round trip. The value carries a path as well as an origin
# (e.g. http://localhost:5173/app) so a completed sign-in lands on the app
# rather than back on the homepage.
APP_ORIGIN_COOKIE = "ledgerlight_app_origin"

# Redirect targets are restricted to these. Anything else is ignored and we
# fall back to APP_URL: this endpoint is a redirect, so honouring an arbitrary
# origin would be an open redirect (a phishing primitive). Loopback is allowed
# because Vite picks a different port whenever 5173 is taken, and that is the
# whole reason this function exists.
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _origin_of(raw: str | None) -> str | None:
    """Reduce a URL to ``scheme://host:port``, or None if it isn't one."""
    if not raw:
        return None
    try:
        parsed = urlparse(raw.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_trusted_app_origin(origin: str | None) -> bool:
    if not origin:
        return False
    if origin in {_origin_of(APP_URL), _origin_of(APP_BASE_URL)}:
        return True
    parsed = urlparse(origin)
    return parsed.scheme == "http" and parsed.hostname in _LOOPBACK_HOSTS


def _trusted_app_target(raw: str | None) -> str | None:
    """Reduce a URL to ``scheme://host[:port]/path`` if it points at the
    frontend, or None. Query and fragment are dropped; so is a path starting
    with ``//``, which some browsers would re-parse as a protocol-relative
    URL. The backend's own origin is rejected: a Referer from /auth/callback
    would otherwise bounce the browser straight back here in a redirect loop.
    """
    if not raw:
        return None
    try:
        parsed = urlparse(raw.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if not _is_trusted_app_origin(origin) or origin == _origin_of(APP_BASE_URL):
        return None
    path = parsed.path or "/"
    if not path.startswith("/") or path.startswith("//"):
        return None
    return f"{origin}{path}"


def resolve_app_url(request: Request) -> str:
    """Where a completed sign-in should send the browser.

    Priority: the URL the browser actually came from (the origin cookie the
    homepage wrote before redirecting to login, path included so /app
    survives the round trip), then the Referer as a weaker second signal,
    then APP_URL. Only frontend targets count -- the Auth0 callback's own
    Referer points at this backend.
    """
    candidates = [
        unquote(request.cookies.get(APP_ORIGIN_COOKIE, "")),
        request.headers.get("referer", ""),
    ]
    for candidate in candidates:
        target = _trusted_app_target(candidate)
        if target:
            return target
    return f"{APP_URL}/"


def _load_sdk():
    """Import the SDK lazily so a missing dependency degrades to a warning
    instead of an ImportError at module import time."""
    from auth0_fastapi.auth.auth_client import AuthClient
    from auth0_fastapi.config import Auth0Config
    from auth0_fastapi.server.routes import register_auth_routes

    return Auth0Config, AuthClient, register_auth_routes


def build_auth_client():
    """Return ``(config, auth_client, register_auth_routes)`` or ``None`` when
    Auth0 is not configured."""
    if not AUTH0_ENABLED:
        return None

    Auth0Config, AuthClient, register_auth_routes = _load_sdk()

    config = Auth0Config(
        domain=AUTH0_DOMAIN,
        client_id=AUTH0_CLIENT_ID,
        client_secret=AUTH0_CLIENT_SECRET,
        app_base_url=APP_BASE_URL,
        secret=SESSION_SECRET or _UNSAFE_DEV_SECRET,
    )
    return config, AuthClient(config), register_auth_routes


def init_auth(app: FastAPI) -> None:
    """Attach sessions and the /auth/* routes to ``app``.

    Safe to call when Auth0 is unconfigured -- it then only installs a
    SessionMiddleware with an ephemeral key so nothing else in the app has to
    care whether auth is on.
    """
    built = build_auth_client()

    if built is None:
        app.add_middleware(SessionMiddleware, secret_key=_UNSAFE_DEV_SECRET)
        return

    config, auth_client, register_auth_routes = built

    app.add_middleware(SessionMiddleware, secret_key=config.secret)
    app.state.config = config
    app.state.auth_client = auth_client

    # The SDK exposes a module-level router. Registering into our own
    # APIRouter and including that keeps /auth/* namespaced here instead of
    # mutating a global that other apps in this process may also import.
    from fastapi import APIRouter

    auth_router = APIRouter()
    register_auth_routes(auth_router, config)
    app.include_router(auth_router)


async def require_session(request: Request, response: Response) -> dict[str, Any] | None:
    """FastAPI dependency gating the protected routers.

    Returns the Auth0 session when auth is on, or ``None`` when the app is
    running unauthenticated (see module docstring).
    """
    if not AUTH0_ENABLED:
        return None

    auth_client = getattr(request.app.state, "auth_client", None)
    if auth_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication client not configured.",
        )

    store_options = {"request": request, "response": response}
    session = await auth_client.client.get_session(store_options=store_options)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in",
            headers={"Location": f"{APP_BASE_URL}/auth/login"},
        )
    return session


async def current_session(request: Request, response: Response) -> dict[str, Any] | None:
    """Like `require_session` but never raises -- used by `GET /` to decide
    between the frontend homepage redirect and the application redirect."""
    if not AUTH0_ENABLED:
        return None
    try:
        return await require_session(request, response)
    except HTTPException:
        return None


async def current_user(request: Request, response: Response) -> dict[str, Any] | None:
    auth_client = getattr(request.app.state, "auth_client", None)
    if auth_client is None:
        return None
    return await auth_client.client.get_user(
        store_options={"request": request, "response": response}
    )


def status_summary() -> dict[str, Any]:
    """Static half of /api/auth/status: is the API gated, and where does a
    browser go to sign in or out?"""
    return {
        "auth_enabled": AUTH0_ENABLED,
        "auth_required": AUTH0_REQUIRED,
        # Absolute, because the frontend (APP_URL) is a different origin than
        # the backend and only /api is proxied -- /auth/* is not reachable
        # through Vite, so a relative path would 404 there.
        "login_url": f"{APP_BASE_URL}/auth/login" if AUTH0_ENABLED else None,
        # returnTo must stay on APP_BASE_URL's origin. The SDK passes it
        # through to Auth0, which only honours origins listed in the
        # application's Allowed Logout URLs.
        "logout_url": (
            f"{APP_BASE_URL}/auth/logout?returnTo={APP_BASE_URL}/"
            if AUTH0_ENABLED
            else None
        ),
        "app_url": APP_URL,
        "missing_env": _MISSING,
    }


async def auth_status(request: Request, response: Response) -> dict[str, Any]:
    """/api/auth/status, including whether *this* caller has a session.

    Never raises: the frontend calls it on every page load to pick the
    homepage CTA and to decide whether /app may open, so a 401 here would be
    a deadlock.
    """
    summary = status_summary()
    if not AUTH0_ENABLED:
        summary["authenticated"] = False
        summary["user"] = None
        return summary

    session = await current_session(request, response)
    summary["authenticated"] = bool(session)
    summary["user"] = await current_user(request, response) if session else None
    return summary
