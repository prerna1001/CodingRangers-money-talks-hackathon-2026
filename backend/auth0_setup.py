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

import logging
import os
import secrets
from typing import Any
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from starlette.middleware.sessions import SessionMiddleware

from config import DEFAULT_USER_ID

load_dotenv()

logger = logging.getLogger(__name__)

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


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


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

# Cookie names owned by the Auth0 SDK's stateless stores. The session is
# chunked (`_a0_session_0`, `_a0_session_1`, ...), so clearing it means
# expiring every chunk, not just the base name.
SDK_SESSION_COOKIE = "_a0_session"
SDK_TRANSACTION_COOKIE = "_a0_tx"
# Auth0 and this host can disagree on the current time by a few seconds.
# PyJWT rejects an ID token whose `iat` is even one second in the future, so
# a slightly fast Auth0 clock would otherwise turn a valid login into a 400.
CLOCK_SKEW_LEEWAY_SECONDS = _env_int("AUTH0_CLOCK_SKEW_LEEWAY_SECONDS", 120)
# Signing out of the app should not leave the upstream identity provider
# (Google, etc.) logged in, or the next login silently reuses it. Set to 0 if
# you would rather keep the IdP session and only end the Auth0/app session.
AUTH0_FEDERATED_LOGOUT = _env_bool("AUTH0_FEDERATED_LOGOUT", True)

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


def _expire_cookie(response: Response, name: str) -> None:
    """Expire ``name`` in both its Secure and non-Secure form.

    The SDK writes its cookies with ``Secure``. localhost is treated as a
    secure context, but not every dev host is, and a Secure deletion cookie
    can be ignored on a plain-http origin. Sending both means whichever one
    the browser accepts removes the cookie; the duplicate is harmless.
    """
    response.delete_cookie(name, path="/", samesite="lax")
    response.delete_cookie(name, path="/", samesite="lax", secure=True)


def _clear_session_cookies(response: Response) -> None:
    """Remove the SDK session/transaction and Starlette session cookies."""
    for name in (SDK_SESSION_COOKIE, SDK_TRANSACTION_COOKIE, "session"):
        _expire_cookie(response, name)
    # The stateless session is chunked; expire a generous fixed range so a
    # stale chunk from an older, larger session cannot survive a logout.
    for index in range(20):
        _expire_cookie(response, f"{SDK_SESSION_COOKIE}_{index}")


def _clear_auth_cookies(response: Response) -> None:
    """Clear everything the auth flow wrote, including the return-to marker."""
    _clear_session_cookies(response)
    _expire_cookie(response, APP_ORIGIN_COOKIE)


def _load_sdk():
    """Import the SDK lazily so a missing dependency degrades to a warning
    instead of an ImportError at module import time."""
    from auth0_fastapi.auth.auth_client import AuthClient
    from auth0_fastapi.config import Auth0Config
    from auth0_fastapi.server.routes import register_auth_routes

    return Auth0Config, AuthClient, register_auth_routes


def _install_clock_skew_tolerance(auth_client) -> None:
    """Allow a little clock drift when the SDK verifies the ID token.

    PyJWT's default tolerance is zero, so an Auth0 server whose clock is a
    few seconds ahead makes every login fail with "The token is not yet valid
    (iat)". The SDK exposes no leeway option, so replace its verifier with
    the same checks plus ``leeway``. Signature, audience and expiry
    verification are otherwise unchanged.
    """
    if CLOCK_SKEW_LEEWAY_SECONDS <= 0:
        return

    import jwt

    async def verify(token: str, jwks: dict, audience: str | None = None) -> dict:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        signing_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                signing_key = jwt.PyJWK.from_dict(key)
                break
        if signing_key is None:
            raise ValueError(f"No matching key found in JWKS for kid: {kid}")

        kwargs: dict[str, Any] = {
            "algorithms": ["RS256"],
            "options": {"verify_signature": True, "verify_iss": False},
            "leeway": CLOCK_SKEW_LEEWAY_SECONDS,
        }
        if audience:
            kwargs["audience"] = audience
        return jwt.decode(token, signing_key.key, **kwargs)

    auth_client.client._verify_and_decode_jwt = verify


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
        # Without `openid` Auth0 returns no ID token/userinfo, so the SDK
        # persists a session with `user=None`. That passes `require_session`
        # but has no `sub`, which is what makes `get_current_user_id` fail
        # with "session is missing a user identifier".
        authorization_params={"scope": "openid profile email"},
    )
    auth_client = AuthClient(config)
    _install_clock_skew_tolerance(auth_client)
    return config, auth_client, register_auth_routes


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

    config, auth_client, _ = built

    app.add_middleware(SessionMiddleware, secret_key=config.secret)
    app.state.config = config
    app.state.auth_client = auth_client

    # Own the /auth/* routes rather than registering the SDK's. The SDK turns
    # a declined consent (and a rejected ID token) into a raw 400 JSON page on
    # the backend origin, and its logout does not clear every cookie we write.
    from auth0_server_python.auth_types import LogoutOptions
    from fastapi import APIRouter
    from fastapi.responses import RedirectResponse

    auth_router = APIRouter()

    @auth_router.get("/auth/login")
    async def login(request: Request, response: Response):
        # Start from a clean slate so a stale chunk from an earlier session
        # cannot be concatenated with the new one. The origin cookie is left
        # alone here -- the homepage wrote it and the callback needs it.
        _clear_session_cookies(response)
        return_to = request.query_params.get("returnTo")
        authorization_params = {
            key: value
            for key, value in request.query_params.items()
            if key != "returnTo"
        }
        auth_url = await auth_client.start_login(
            app_state={"returnTo": return_to} if return_to else None,
            authorization_params=authorization_params,
            store_options={"request": request, "response": response},
        )
        return RedirectResponse(auth_url, status_code=302, headers=response.headers)

    @auth_router.get("/auth/callback")
    async def callback(request: Request, response: Response):
        # Auth0 sends `error` when the user declines consent or the upstream
        # IdP fails. That is a normal outcome, not a server error: clear the
        # half-finished transaction and send the browser home.
        if request.query_params.get("error"):
            _clear_auth_cookies(response)
            return RedirectResponse(
                f"{APP_URL}/", status_code=302, headers=response.headers
            )

        try:
            session_data = await auth_client.complete_login(
                str(request.url),
                store_options={"request": request, "response": response},
            )
        except Exception as exc:  # noqa: BLE001 - surfaced on the homepage instead
            # Includes a rejected ID token (clock skew, bad signature, ...).
            # Nothing was persisted, so clean up rather than showing raw JSON
            # at the backend origin.
            logger.warning("Auth0 callback failed: %s", exc)
            _clear_auth_cookies(response)
            return RedirectResponse(
                f"{APP_URL}/", status_code=302, headers=response.headers
            )

        app_state = session_data.get("app_state") or {}
        target = _trusted_app_target(app_state.get("returnTo")) or resolve_app_url(request)
        return RedirectResponse(target, status_code=302, headers=response.headers)

    @auth_router.get("/auth/logout")
    async def logout(request: Request, response: Response):
        # Clear the app's cookies before anything that can fail, and log out
        # federated so Auth0 also ends the upstream (e.g. Google) session.
        # Otherwise the next login silently reuses that session and drops the
        # user straight onto the consent screen.
        _clear_auth_cookies(response)
        return_to = request.query_params.get("returnTo") or f"{APP_BASE_URL}/"
        try:
            logout_url = await auth_client.client.logout(
                LogoutOptions(
                    return_to=return_to, federated=AUTH0_FEDERATED_LOGOUT
                ),
                store_options={"request": request, "response": response},
            )
        except Exception as exc:  # noqa: BLE001 - never strand the browser
            logger.warning("Auth0 logout failed: %s", exc)
            logout_url = f"{APP_URL}/"
        return RedirectResponse(logout_url, status_code=302, headers=response.headers)

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

    # A session without a subject is a leftover from a login that did not
    # request `openid` (or from an older version of this app). Treat it as
    # signed out and expire it so the homepage offers "Log in" again instead
    # of letting the visitor into /app with no usable identity.
    if not owner_from_session(session):
        _clear_session_cookies(response)
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


def owner_from_session(session: dict[str, Any] | None) -> str | None:
    """Extract the stable owner id (Auth0 ``sub``) from an SDK session.

    The SDK stores the ID-token claims under ``session["user"]``. A few
    older/fake sessions use ``user_id`` or a top-level ``sub``; accepting
    those keeps tests and local shims working without weakening production,
    where a missing subject makes the request fail closed.
    """
    if not session:
        return None

    candidates: list[Any] = []
    user = session.get("user")
    if isinstance(user, dict):
        candidates.extend([user.get("sub"), user.get("user_id"), user.get("id")])
    elif isinstance(user, str):
        candidates.append(user)
    candidates.extend([session.get("sub"), session.get("user_id")])

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


async def get_current_user_id(request: Request, response: Response) -> str:
    """FastAPI dependency returning the owner id for this request.

    Authenticated callers are scoped to their Auth0 subject. When Auth0 is
    not configured we fall back to ``DEFAULT_USER_ID`` so local development
    and tests still work. If a tenant is configured but the operator
    explicitly set ``AUTH0_REQUIRED=0``, an anonymous caller gets the shared
    local owner rather than every account's data.
    """
    if not AUTH0_ENABLED:
        return DEFAULT_USER_ID

    if not AUTH0_REQUIRED:
        session = await current_session(request, response)
        return owner_from_session(session) or DEFAULT_USER_ID

    session = await require_session(request, response)
    owner = owner_from_session(session)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is missing a user identifier",
            headers={"Location": f"{APP_BASE_URL}/auth/login"},
        )
    return owner


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
