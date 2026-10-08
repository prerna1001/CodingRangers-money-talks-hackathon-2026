"""Unit tests for the auth redirect plumbing (auth0_setup.resolve_app_url,
the GET / forwarder, and the login/logout URLs handed to the frontend).

These cover the pieces the frontend routing depends on: where a completed
sign-in lands (must be the frontend, path preserved), where a sign-out or a
hand-typed localhost:8000 visit lands (the public homepage), and that no
cookie or Referer can talk the backend into redirecting off-origin.
"""

from __future__ import annotations

import auth0_setup
from fastapi.testclient import TestClient


class _FakeRequest:
    """Minimal stand-in for a starlette Request: resolve_app_url only ever
    reads the cookie jar and the Referer header."""

    def __init__(self, cookies: dict | None = None, referer: str | None = None):
        self.cookies = cookies or {}
        self.headers = {"referer": referer} if referer else {}


def _resolve(**kwargs) -> str:
    return auth0_setup.resolve_app_url(_FakeRequest(**kwargs))


def test_cookie_path_survives_the_round_trip():
    target = _resolve(cookies={auth0_setup.APP_ORIGIN_COOKIE: "http://localhost:5173/app"})
    assert target == "http://localhost:5173/app"


def test_cookie_is_read_url_encoded():
    # The frontend writes encodeURIComponent(...); / is %2F in that encoding.
    target = _resolve(
        cookies={
            auth0_setup.APP_ORIGIN_COOKIE: "http%3A%2F%2Flocalhost%3A5173%2Fapp%3Ftab%3D1"
        }
    )
    assert target == "http://localhost:5173/app"


def test_origin_only_cookie_lands_on_root():
    target = _resolve(cookies={auth0_setup.APP_ORIGIN_COOKIE: "http://localhost:5173"})
    assert target == "http://localhost:5173/"


def test_referer_from_the_backend_itself_is_not_used():
    # After /auth/callback the browser's Referer points at this backend;
    # honouring it would bounce the browser straight back to GET / in a loop.
    target = _resolve(referer="http://localhost:8000/auth/callback")
    assert target == f"{auth0_setup.APP_URL}/"


def test_foreign_origin_cookie_falls_back_to_the_app_url():
    target = _resolve(cookies={auth0_setup.APP_ORIGIN_COOKIE: "https://evil.example/app"})
    assert target == f"{auth0_setup.APP_URL}/"


def test_protocol_relative_path_is_rejected():
    target = _resolve(cookies={auth0_setup.APP_ORIGIN_COOKIE: "http://localhost:5173//evil"})
    assert target == f"{auth0_setup.APP_URL}/"


def test_empty_cookie_and_no_referer_falls_back_to_the_app_url():
    assert _resolve() == f"{auth0_setup.APP_URL}/"
    assert _resolve(cookies={auth0_setup.APP_ORIGIN_COOKIE: ""}) == f"{auth0_setup.APP_URL}/"


def test_login_and_logout_urls_stay_on_the_backend_origin():
    # /auth/* is not proxied through Vite, so both URLs must be absolute on
    # APP_BASE_URL; returnTo in particular must stay there because Auth0 only
    # honours Allowed Logout URLs (configured as http://localhost:8000).
    summary = auth0_setup.status_summary()
    assert summary["login_url"] == f"{auth0_setup.APP_BASE_URL}/auth/login"
    assert summary["logout_url"].startswith(f"{auth0_setup.APP_BASE_URL}/auth/logout?returnTo=")
    assert f"{auth0_setup.APP_BASE_URL}/" in summary["logout_url"]


def test_get_root_forwards_anonymous_visitors_to_the_homepage(monkeypatch):
    import main

    monkeypatch.setattr(auth0_setup, "AUTH0_ENABLED", True)
    monkeypatch.setattr(auth0_setup, "AUTH0_REQUIRED", True)

    async def _no_session(request, response):
        return None

    monkeypatch.setattr(auth0_setup, "current_session", _no_session)

    with TestClient(main.app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == f"{auth0_setup.APP_URL}/"


def test_get_root_sends_signed_in_visitors_to_their_target(monkeypatch):
    import main

    monkeypatch.setattr(auth0_setup, "AUTH0_ENABLED", True)
    monkeypatch.setattr(auth0_setup, "AUTH0_REQUIRED", True)

    async def _session(request, response):
        return {"user_id": "auth0|test"}

    monkeypatch.setattr(auth0_setup, "current_session", _session)

    with TestClient(main.app) as client:
        response = client.get(
            "/",
            follow_redirects=False,
            cookies={auth0_setup.APP_ORIGIN_COOKIE: "http://localhost:5173/app"},
        )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/app"


def test_get_root_ignores_an_off_origin_cookie_for_signed_in_visitors(monkeypatch):
    import main

    monkeypatch.setattr(auth0_setup, "AUTH0_ENABLED", True)
    monkeypatch.setattr(auth0_setup, "AUTH0_REQUIRED", True)

    async def _session(request, response):
        return {"user_id": "auth0|test"}

    monkeypatch.setattr(auth0_setup, "current_session", _session)

    with TestClient(main.app) as client:
        response = client.get(
            "/",
            follow_redirects=False,
            cookies={auth0_setup.APP_ORIGIN_COOKIE: "https://evil.example/app"},
        )

    assert response.status_code == 302
    assert response.headers["location"] == f"{auth0_setup.APP_URL}/"
