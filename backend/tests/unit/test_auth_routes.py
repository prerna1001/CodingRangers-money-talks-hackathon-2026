"""Behavior of the /auth/* routes when Auth0 is configured.

These use a fake AuthClient so they do not need a tenant, network access, or
the real environment: the point is the redirect/cleanup contract around the
SDK, not the SDK itself.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth0_setup


class _FakeServerClient:
    def __init__(self) -> None:
        self.logout_options = None

    async def logout(self, options, store_options=None) -> str:
        self.logout_options = options
        return (
            "https://tenant.example/v2/logout"
            f"?returnTo={options.return_to}&federated={str(options.federated).lower()}"
        )


class _FakeAuthClient:
    def __init__(self) -> None:
        self.client = _FakeServerClient()
        self.login_calls = []
        self.complete_login_error: Exception | None = None

    async def start_login(self, app_state=None, authorization_params=None, store_options=None) -> str:
        self.login_calls.append((app_state, authorization_params))
        return "https://tenant.example/authorize?scope=openid"

    async def complete_login(self, url: str, store_options=None) -> dict:
        if self.complete_login_error:
            raise self.complete_login_error
        return {"user": {"sub": "auth0|test"}, "app_state": {}}


@pytest.fixture()
def app(monkeypatch):
    config = SimpleNamespace(secret="test-secret")
    fake = _FakeAuthClient()
    monkeypatch.setattr(
        auth0_setup, "build_auth_client", lambda: (config, fake, None)
    )
    application = FastAPI()
    auth0_setup.init_auth(application)
    return application, fake


def _cleared_cookies(response) -> set[str]:
    return {
        value.split("=", 1)[0]
        for key, value in response.headers.multi_items()
        if key.lower() == "set-cookie"
    }


def test_declined_consent_redirects_to_the_homepage(app):
    application, _ = app
    with TestClient(application) as client:
        response = client.get(
            "/auth/callback?error=access_denied&error_description=User%20did%20not%20authorize",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == f"{auth0_setup.APP_URL}/"
    assert auth0_setup.SDK_SESSION_COOKIE in _cleared_cookies(response)
    assert auth0_setup.APP_ORIGIN_COOKIE in _cleared_cookies(response)


def test_failed_callback_redirects_home_instead_of_returning_json(app):
    application, fake = app
    fake.complete_login_error = ValueError("The token is not yet valid (iat)")

    with TestClient(application) as client:
        response = client.get(
            "/auth/callback?code=abc&state=xyz", follow_redirects=False
        )

    assert response.status_code == 302
    assert response.headers["location"] == f"{auth0_setup.APP_URL}/"


def test_logout_clears_every_session_chunk_without_logging_out_of_google(app):
    application, fake = app
    with TestClient(application) as client:
        client.cookies.set(f"{auth0_setup.SDK_SESSION_COOKIE}_0", "stale")
        client.cookies.set(auth0_setup.APP_ORIGIN_COOKIE, "http://localhost:5173/app")
        response = client.get(
            "/auth/logout?returnTo=http://localhost:8000/", follow_redirects=False
        )

    assert response.status_code == 302
    assert "federated=false" in response.headers["location"]
    assert fake.client.logout_options.federated is False
    cleared = _cleared_cookies(response)
    assert f"{auth0_setup.SDK_SESSION_COOKIE}_0" in cleared
    assert auth0_setup.SDK_TRANSACTION_COOKIE in cleared
    assert auth0_setup.APP_ORIGIN_COOKIE in cleared


def test_login_asks_for_the_account_chooser(monkeypatch):
    monkeypatch.setattr(auth0_setup, "AUTH0_LOGIN_PROMPT", "select_account")
    assert auth0_setup._authorization_params()["prompt"] == "select_account"


def test_login_prompt_can_be_disabled(monkeypatch):
    monkeypatch.setattr(auth0_setup, "AUTH0_LOGIN_PROMPT", "")
    assert "prompt" not in auth0_setup._authorization_params()


def test_login_clears_stale_session_but_keeps_the_return_target(app):
    application, fake = app
    with TestClient(application) as client:
        client.cookies.set(f"{auth0_setup.SDK_SESSION_COOKIE}_0", "stale")
        client.cookies.set(auth0_setup.APP_ORIGIN_COOKIE, "http://localhost:5173/app")
        response = client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://tenant.example/authorize")
    cleared = _cleared_cookies(response)
    assert f"{auth0_setup.SDK_SESSION_COOKIE}_0" in cleared
    assert auth0_setup.APP_ORIGIN_COOKIE not in cleared
    assert fake.login_calls == [(None, {})]


def test_session_without_a_subject_is_treated_as_signed_out(monkeypatch):
    from fastapi import HTTPException
    from starlette.responses import Response

    async def get_session(store_options=None):
        return {"user": None}

    fake = SimpleNamespace(client=SimpleNamespace(get_session=get_session))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth_client=fake)))
    response = Response()
    monkeypatch.setattr(auth0_setup, "AUTH0_ENABLED", True)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(auth0_setup.require_session(request, response))

    assert excinfo.value.status_code == 401
    assert any(
        auth0_setup.SDK_SESSION_COOKIE in value
        for value in response.headers.getlist("set-cookie")
    )


def test_clock_skew_tolerance_accepts_a_slightly_future_iat():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "test-kid"

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "auth0|test",
            "aud": "client-id",
            "iss": "https://tenant.example/",
            "iat": now + 60,
            "exp": now + 3600,
        },
        key,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )

    fake = SimpleNamespace(client=SimpleNamespace())
    auth0_setup._install_clock_skew_tolerance(fake)

    claims = asyncio.run(
        fake.client._verify_and_decode_jwt(
            token, {"keys": [jwk]}, audience="client-id"
        )
    )
    assert claims["sub"] == "auth0|test"
