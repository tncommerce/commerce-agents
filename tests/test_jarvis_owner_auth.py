from __future__ import annotations

import re
import time
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from retail.api.jarvis_owner_auth import (
    ORIGIN,
    SESSION_COOKIE,
    OwnerAuth,
    OwnerConfig,
    OwnerDenied,
    create_control_room_router,
)

OWNER = str(uuid4())
SESSION = str(uuid4())


class Reader:
    def __init__(self):
        self.calls = 0

    def snapshot(self):
        self.calls += 1
        return {"read_only": True, "version": 1}


class FakeVoiceGateway:
    enabled = True

    def __init__(self):
        self.calls = []

    def connect(self, sdp):
        self.calls.append(sdp)
        return "v=0\r\no=- 9 9 IN IP4 127.0.0.1\r\n"


@pytest.fixture
def setup():
    config = OwnerConfig(
        OWNER, "sb_publishable_test", Fernet.generate_key().decode(), "server-only"
    )
    state = {"owner": OWNER, "alive": True, "confirmed": True, "anonymous": False, "logout": 204}
    calls = []
    claims = {
        "session_id": SESSION,
        "sub": OWNER,
        "role": "authenticated",
        "aud": "authenticated",
        "iss": "https://bqsdxaagklpkxioaqdqa.supabase.co/auth/v1",
        "exp": int(time.time()) + 1800,
    }
    token = jwt.encode(claims, "test-only-key-with-at-least-32-chars")

    def transport(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(
                200,
                json={
                    "id": state["owner"],
                    "is_anonymous": state["anonymous"],
                    "email_confirmed_at": "now" if state["confirmed"] else None,
                },
            )
        if request.url.path == "/rest/v1/rpc/dufynd_dashboard_owner_session":
            assert request.url.params["p_session_id"] == SESSION
            return httpx.Response(200, json=state["alive"])
        if request.url.path == "/auth/v1/token":
            return httpx.Response(
                200,
                json={
                    "access_token": token,
                    "refresh_token": "discard-me",
                    "provider_token": "never-store",
                },
            )
        if request.url.path == "/auth/v1/logout":
            return httpx.Response(state["logout"])
        raise AssertionError(request.url)

    auth = OwnerAuth(config, transport=httpx.MockTransport(transport))
    reader = Reader()
    reader.voice = FakeVoiceGateway()
    app = FastAPI()
    app.include_router(
        create_control_room_router(
            config,
            auth=auth,
            reader=reader,
            voice_gateway=reader.voice,
        )
    )
    client = TestClient(app, base_url=ORIGIN)
    return client, auth, reader, state, token, calls, claims


def login(client):
    page = client.get("/internal/login")
    nonce = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    return client.post(
        "/internal/login",
        headers={"Origin": ORIGIN},
        json={"email": "owner@example.test", "password": "test-password", "csrf": nonce},
    )


def test_owner_login_cookie_and_protected_shell(setup):
    client, auth, reader, _, _, calls, _ = setup
    r = login(client)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert "Domain=" not in cookie and "Path=/" in cookie
    assert "discard-me" not in cookie and "never-store" not in cookie
    data = auth.open(client.cookies[SESSION_COOKIE], ttl=3600)
    assert set(data) == {"csrf", "access_token"}
    room = client.get("/internal/jarvis")
    assert room.status_code == 200
    assert 'data-voice-enabled="true"' in room.text
    assert "VOICE_ENABLED" not in room.text
    assert client.get("/internal/jarvis/snapshot").status_code == 200
    assert reader.calls == 1
    assert calls.count(("GET", "/auth/v1/user")) == 3
    assert calls.count(("GET", "/rest/v1/rpc/dufynd_dashboard_owner_session")) == 3
    assert client.get("/internal/jarvis").headers["cache-control"] == "private, no-store"
    assert not any("internal" in p for p in client.get("/openapi.json").json()["paths"])


@pytest.mark.parametrize(
    "condition", ["nonowner", "revoked", "unconfirmed", "anonymous", "forged", "missing"]
)
def test_denial_before_privileged_read(setup, condition):
    client, auth, reader, state, token, _, _ = setup
    if condition != "missing":
        client.cookies.set(SESSION_COOKIE, auth.seal({"access_token": token, "csrf": "c" * 43}))
    if condition == "nonowner":
        state["owner"] = str(uuid4())
    if condition == "revoked":
        state["alive"] = False
    if condition == "unconfirmed":
        state["confirmed"] = False
    if condition == "anonymous":
        state["anonymous"] = True
    if condition == "forged":
        client.cookies.set(SESSION_COOKIE, "forged")
    assert client.get("/internal/jarvis/snapshot").status_code == 401
    assert reader.calls == 0
    assert client.get("/internal/jarvis", follow_redirects=False).status_code == 303


@pytest.mark.parametrize(
    "claim,new",
    [
        ("sub", "wrong"),
        ("exp", 1),
        ("role", "service_role"),
        ("session_id", "invalid"),
        ("aud", "wrong"),
        ("iss", "wrong"),
    ],
)
def test_claims_are_restricted_even_after_remote_user_validation(setup, claim, new):
    _, auth, _, _, _, _, claims = setup
    claims[claim] = new
    token = jwt.encode(claims, "test-only-key-with-at-least-32-chars")
    with pytest.raises(OwnerDenied):
        auth.verify_token(token)


def test_origin_csrf_size_method_and_assets(setup):
    client, _, reader, _, _, _, _ = setup
    client.get("/internal/login")
    assert client.post("/internal/login", json={}).status_code == 403
    assert (
        client.post(
            "/internal/login",
            headers={"Origin": ORIGIN},
            json={"email": "a", "password": "p", "csrf": "wrong"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/internal/login",
            headers={"Origin": ORIGIN, "Content-Type": "application/json"},
            content="x" * 5000,
        ).status_code
        == 400
    )
    assert client.post("/internal/jarvis/snapshot").status_code == 405
    assert reader.calls == 0
    for asset in ("room.css", "room.js", "login.js"):
        r = client.get("/internal/assets/" + asset)
        assert r.status_code == 200
        assert "server-only" not in r.text
    assert client.get("/internal/assets/jarvis_owner_auth.py").status_code == 404


def test_voice_session_requires_owner_origin_csrf_and_sdp(setup):
    client, auth, reader, _, _, _, _ = setup
    assert (
        client.post(
            "/internal/jarvis/voice/session",
            headers={"Origin": ORIGIN, "Content-Type": "application/sdp"},
            content="v=0\r\n",
        ).status_code
        == 401
    )

    assert login(client).status_code == 200
    csrf = auth.open(client.cookies[SESSION_COOKIE], ttl=3600)["csrf"]

    assert (
        client.post(
            "/internal/jarvis/voice/session",
            headers={
                "Origin": "https://evil.example",
                "X-CSRF-Token": csrf,
                "Content-Type": "application/sdp",
            },
            content="v=0\r\n",
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/internal/jarvis/voice/session",
            headers={"Origin": ORIGIN, "X-CSRF-Token": "wrong", "Content-Type": "application/sdp"},
            content="v=0\r\n",
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/internal/jarvis/voice/session",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf, "Content-Type": "text/plain"},
            content="v=0\r\n",
        ).status_code
        == 400
    )

    response = client.post(
        "/internal/jarvis/voice/session",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf, "Content-Type": "application/sdp"},
        content="v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n",
    )
    assert response.status_code == 201
    assert response.headers["content-type"].startswith("application/sdp")
    assert response.text.startswith("v=0")
    assert reader.voice.calls == ["v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n"]


def test_revoked_after_login_and_logout_csrf(setup):
    client, auth, reader, state, _, _, _ = setup
    assert login(client).status_code == 200
    assert client.post("/internal/logout", headers={"Origin": ORIGIN}).status_code == 403
    csrf = auth.open(client.cookies[SESSION_COOKIE], ttl=3600)["csrf"]
    assert (
        client.post(
            "/internal/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}
        ).status_code
        == 200
    )
    assert SESSION_COOKIE not in client.cookies
    assert login(client).status_code == 200
    state["alive"] = False
    assert client.get("/internal/jarvis/snapshot").status_code == 401
    assert reader.calls == 0


def test_logout_upstream_failure_is_not_claimed_success(setup):
    client, auth, _, state, _, _, _ = setup
    login(client)
    csrf = auth.open(client.cookies[SESSION_COOKIE], ttl=3600)["csrf"]
    state["logout"] = 503
    r = client.post("/internal/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
    assert r.status_code == 503 and r.json()["ok"] is False
    assert SESSION_COOKIE not in client.cookies


def test_rate_limit_is_bounded(setup):
    _, auth, _, _, _, _, _ = setup
    for _ in range(5):
        auth.check_attempt()
    with pytest.raises(Exception) as exc:
        auth.check_attempt()
    assert exc.value.status_code == 429


def test_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("DUFYND_CONTROL_ROOM_ENABLED", raising=False)
    app = FastAPI()
    app.include_router(create_control_room_router())
    client = TestClient(app)
    assert client.get("/internal/jarvis/snapshot").status_code == 503
    assert "disabled" in client.get("/internal/login").text
