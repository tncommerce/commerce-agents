from __future__ import annotations

import json
import time
from dataclasses import replace
from threading import Lock
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from private_broker.runtime import (
    ISSUER,
    OWNER_ID,
    WORKFLOW,
    Config,
    OAuth,
    WorkloadAuth,
    create_app,
)
from private_broker.store import EncryptedVault, FirestoreCAS
from scripts.dufynd_observer_credentials import (
    GMAIL_SCOPE,
    KNOWN_THREADS,
    BrokerError,
    FixedTransport,
)


class MemoryCAS:
    def __init__(self):
        self.rows = {}
        self.mutex = Lock()

    def get(self, key):
        with self.mutex:
            return self.rows.get(key, (None, None))

    def cas(self, key, version, value):
        with self.mutex:
            if self.rows.get(key, (None, None))[1] != version:
                return False
            self.rows[key] = (value, (version or 0) + 1)
            return True


CONFIG = Config(
    "https://broker.example.com",
    "owner@example.com",
    "client-id",
    "client-secret-canary",
    "owner-secret-canary-01234567890123456789",
    "render-secret-canary",
    "12345",
    True,
)


def setup(handler):
    backend = MemoryCAS()
    vault = EncryptedVault(backend, b"x" * 32)
    transport = FixedTransport(
        httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
    )
    return vault, OAuth(CONFIG, vault, transport), transport


def handler(request):
    if request.url.path == "/token":
        return httpx.Response(
            200,
            json={
                "access_token": "access-secret-canary",
                "refresh_token": "refresh-secret-canary",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": GMAIL_SCOPE,
            },
        )
    if request.url.path.endswith("profile"):
        return httpx.Response(200, json={"emailAddress": "owner@example.com"})
    thread = request.url.path.rsplit("/", 1)[1]
    return httpx.Response(
        200,
        json={
            "id": thread,
            "historyId": "100",
            "messages": [
                {
                    "id": "abc",
                    "threadId": thread,
                    "internalDate": "123",
                    "payload": {
                        "headers": [{"name": "From", "value": "Sender <sender@example.com>"}]
                    },
                }
            ],
        },
    )


def authorize(oauth):
    query = parse_qs(urlsplit(oauth.start()["authorization_url"]).query)
    assert query["scope"] == [GMAIL_SCOPE]
    assert query["include_granted_scopes"] == ["false"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["access_type"] == ["offline"]
    assert query["redirect_uri"] == [CONFIG.callback]
    oauth.callback(query["state"][0], "code-canary")
    return query["state"][0]


def test_callback_accepts_google_issuer_and_rejects_other_issuers():
    vault, oauth, transport = setup(handler)
    client = TestClient(
        create_app(CONFIG, vault, transport, SimpleNamespace(verify=lambda token: None))
    )
    query = parse_qs(urlsplit(oauth.start()["authorization_url"]).query)
    response = client.get(
        "/oauth/gmail/callback",
        params={
            "state": query["state"][0],
            "code": "code-canary",
            "iss": "https://accounts.google.com",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "authorized"}

    vault, oauth, transport = setup(handler)
    client = TestClient(
        create_app(CONFIG, vault, transport, SimpleNamespace(verify=lambda token: None))
    )
    query = parse_qs(urlsplit(oauth.start()["authorization_url"]).query)
    response = client.get(
        "/oauth/gmail/callback",
        params={
            "state": query["state"][0],
            "code": "code-canary",
            "iss": "https://evil.example",
        },
    )
    assert response.status_code == 403
    assert response.json() == {"error": "invalid_response"}
    assert vault.read("gmail_known_threads")[1] is None


def test_oauth_pkce_replay_encryption():
    def check(request):
        if request.url.path == "/token":
            data = parse_qs(request.content.decode())
            assert len(data["code_verifier"][0]) >= 43
            assert data["redirect_uri"] == [CONFIG.callback]
        return handler(request)

    vault, oauth, _ = setup(check)
    state = authorize(oauth)
    with pytest.raises(BrokerError):
        oauth.callback(state, "code-canary")
    assert "secret-canary" not in json.dumps(vault.backend.rows)
    assert "code-canary" not in json.dumps(vault.backend.rows)


@pytest.mark.parametrize("failure", ["scope", "account", "pkce", "invalid_grant"])
def test_callback_fail_closed(failure):
    def fail(request):
        if request.url.path == "/token" and failure in {"pkce", "invalid_grant"}:
            return httpx.Response(
                400, json={"error": "invalid_grant", "error_description": "secret-canary"}
            )
        response = handler(request)
        data = response.json()
        if request.url.path == "/token" and failure == "scope":
            data["scope"] += " https://mail.google.com/"
        if request.url.path.endswith("profile") and failure == "account":
            data["emailAddress"] = "wrong@example.com"
        return httpx.Response(200, json=data)

    vault, oauth, _ = setup(fail)
    state = parse_qs(urlsplit(oauth.start()["authorization_url"]).query)["state"][0]
    with pytest.raises(BrokerError) as exc:
        oauth.callback(state, "code")
    assert "canary" not in str(exc.value)
    assert vault.read("gmail_known_threads")[1] is None
    with pytest.raises(BrokerError):
        oauth.callback(state, "code")


def test_lock_fencing_and_generation():
    vault, oauth, _ = setup(handler)
    authorize(oauth)
    other = EncryptedVault(vault.backend, b"x" * 32)
    with vault.lock("gmail_known_threads"):
        with pytest.raises(BrokerError), other.lock("gmail_known_threads"):
            pass
        health, secret = vault.read("gmail_known_threads")
        assert not vault.rotate("gmail_known_threads", 99, secret, health)
        assert vault.revoke(
            "gmail_known_threads",
            secret.generation,
            replace(health, status="revoked", health_reason="revoked"),
        )
    assert vault.read("gmail_known_threads")[1] is None
    assert vault.get("gmail_known_threads")[0]["generation"] == 2


@pytest.mark.parametrize(
    "claim,value",
    [
        ("exp", 0),
        ("repository", "other/repo"),
        ("ref", "refs/heads/main"),
        ("workflow_ref", "wrong"),
        ("aud", "wrong"),
        ("iss", "wrong"),
        ("repository_id", "999"),
        ("repository_owner_id", "999"),
        ("sub", "repo:tncommerce/commerce-agents:ref:refs/heads/scentai-mvp"),
        ("event_name", "pull_request"),
    ],
)
def test_oidc_claim_rejection(claim, value):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
    )
    claims = {
        "iss": ISSUER,
        "aud": CONFIG.origin,
        "sub": (
            f"repo:tncommerce@{OWNER_ID}/commerce-agents@12345"
            ":ref:refs/heads/scentai-mvp"
        ),
        "repository": "tncommerce/commerce-agents",
        "repository_id": "12345",
        "repository_owner_id": OWNER_ID,
        "ref": "refs/heads/scentai-mvp",
        "workflow_ref": WORKFLOW,
        "event_name": "workflow_dispatch",
        "iat": int(time.time()),
        "nbf": int(time.time()),
        "exp": int(time.time()) + 300,
    }
    auth = WorkloadAuth(CONFIG, keys)
    auth.verify(jwt.encode(claims, key, algorithm="RS256"))
    claims[claim] = value
    with pytest.raises(BrokerError):
        auth.verify(jwt.encode(claims, key, algorithm="RS256"))


def test_routes_owner_boundary_dedupe_ack(caplog):
    vault, oauth, transport = setup(handler)
    authorize(oauth)
    auth = SimpleNamespace(verify=lambda token: None)
    client = TestClient(create_app(CONFIG, vault, transport, auth))
    assert client.get("/v1/health").status_code == 403
    headers = {"Authorization": "Bearer workload"}
    assert client.post("/owner/oauth/gmail/start", headers=headers).status_code == 403
    assert client.get("/v1/gmail/threads/unknown/metadata", headers=headers).status_code == 403
    thread = sorted(KNOWN_THREADS)[0]
    url = f"/v1/gmail/threads/{thread}/metadata"
    first = client.get(url, headers=headers).json()
    assert client.get(url, headers=headers).json() == first
    assert not vault.thread_state(thread).get("cursor")
    ack = f"/v1/gmail/threads/{thread}/ack/{first['observation_id']}"
    assert client.post(ack, headers=headers).json() == {"status": "acknowledged"}
    assert client.post(ack, headers=headers).json() == {"status": "duplicate"}
    assert "secret-canary" not in json.dumps(first) + caplog.text
    assert client.post("/v1/render/services/other/deployments", headers=headers).status_code == 405
    assert client.get("/v1/render/services/other/deployments", headers=headers).status_code == 403


def test_partial_failure_leaves_cursor_unchanged():
    vault, oauth, transport = setup(handler)
    authorize(oauth)

    def fail(request):
        if "threads/" in request.url.path:
            return httpx.Response(503, json={"secret": "secret-canary"})
        return handler(request)

    transport.client = httpx.Client(transport=httpx.MockTransport(fail), trust_env=False)
    client = TestClient(
        create_app(CONFIG, vault, transport, SimpleNamespace(verify=lambda token: None))
    )
    thread = sorted(KNOWN_THREADS)[0]
    assert (
        client.get(
            f"/v1/gmail/threads/{thread}/metadata", headers={"Authorization": "Bearer workload"}
        ).status_code
        == 403
    )
    assert not vault.thread_state(thread).get("cursor")


def test_firestore_cas_preconditions():
    seen = []

    def fake(request):
        if request.url.host == "metadata.google.internal":
            return httpx.Response(200, json={"access_token": "private-adc"})
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(200, json={})

    store = FirestoreCAS(
        "private-broker-project", httpx.Client(transport=httpx.MockTransport(fake))
    )
    assert store.get("credential") == (None, None)
    assert store.cas("credential", None, "ciphertext")
    assert seen[-1].url.params["currentDocument.exists"] == "false"
    assert store.cas("credential", "version", "ciphertext")
    assert seen[-1].url.params["currentDocument.updateTime"] == "version"
    with pytest.raises(BrokerError):
        store.get("../secrets")


def test_logging_gate_and_revoke_invalidates_outstanding_consent():
    vault, oauth, transport = setup(handler)
    with pytest.raises(BrokerError):
        OAuth(replace(CONFIG, callback_logging_ready=False), vault, transport).start()
    state = parse_qs(urlsplit(oauth.start()["authorization_url"]).query)["state"][0]
    client = TestClient(
        create_app(CONFIG, vault, transport, SimpleNamespace(verify=lambda token: None))
    )
    response = client.post(
        "/owner/gmail/revoke", headers={"Authorization": "Bearer " + CONFIG.owner_key}
    )
    assert response.json()["status"] == "revoked"
    with pytest.raises(BrokerError, match="refresh_race"):
        oauth.callback(state, "code")


def test_expired_lease_cannot_commit_after_takeover():
    backend = MemoryCAS()
    ticks = [1000.0]
    first = EncryptedVault(backend, b"x" * 32, clock=lambda: ticks[0])
    second = EncryptedVault(backend, b"x" * 32, clock=lambda: ticks[0])
    with first.lock("gmail_known_threads"):
        health, _ = first.read("gmail_known_threads")
        ticks[0] += 91
        with second.lock("gmail_known_threads"):
            assert not first.revoke("gmail_known_threads", 0, health)
            assert second.revoke(
                "gmail_known_threads", 0, replace(health, status="revoked", health_reason="revoked")
            )
    assert first.read("gmail_known_threads")[0].status == "revoked"


def test_ciphertext_tamper_and_cross_document_replay_rejected():
    backend = MemoryCAS()
    vault = EncryptedVault(backend, b"x" * 32)
    assert vault.cas("one", None, {"token": "secret-canary"})
    raw, _ = backend.get("one")
    backend.cas("two", None, raw)
    with pytest.raises(BrokerError):
        vault.get("two")
    backend.cas("one", 1, raw[:-4] + "AAAA")
    with pytest.raises(BrokerError):
        vault.get("one")


def test_render_runtime_exact_read_health_and_redaction():
    def render(request):
        assert request.url.path == "/v1/services/srv-dakpfrnf3r2c73dr3f20/deploys"
        assert request.method == "GET"
        return httpx.Response(
            200,
            json=[
                {
                    "deploy": {
                        "id": "dep-abc",
                        "commit": {"id": "a" * 40},
                        "status": "live",
                        "secret": "render-secret-canary",
                        "env": {"KEY": "secret-canary"},
                    }
                }
            ],
        )

    vault, _, transport = setup(render)
    client = TestClient(
        create_app(CONFIG, vault, transport, SimpleNamespace(verify=lambda token: None))
    )
    headers = {"Authorization": "Bearer workload"}
    assert (
        client.get("/v1/health", headers=headers).json()["render"]["status"]
        == "missing_configuration"
    )
    response = client.get(
        "/v1/render/services/srv-dakpfrnf3r2c73dr3f20/deployments", headers=headers
    )
    assert response.status_code == 200
    assert set(response.json()[0]) == {
        "deployment_id",
        "service_id",
        "commit_sha",
        "status",
        "timestamps",
    }
    assert "secret-canary" not in response.text
    assert client.get("/v1/health", headers=headers).json()["render"]["status"] == "healthy"
    for suffix in (
        "env",
        "settings",
        "restart",
        "logs",
        "deployments/",
        "deployments?url=https://evil.invalid",
    ):
        result = client.get(
            "/v1/render/services/srv-dakpfrnf3r2c73dr3f20/" + suffix, headers=headers
        )
        assert result.status_code in {403, 404}


def test_real_vault_refresh_serialization_and_new_refresh_token():
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime, timedelta
    from threading import Event

    from scripts.dufynd_observer_credentials import GmailRefreshBroker

    vault, oauth, transport = setup(handler)
    authorize(oauth)
    with vault.lock("gmail_known_threads"):
        health, secret = vault.read("gmail_known_threads")
        assert vault.mark(
            "gmail_known_threads",
            secret.generation,
            replace(health, expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        )
    entered, release = Event(), Event()
    calls = []

    def refresh(request):
        if request.url.path == "/token":
            calls.append(request)
            entered.set()
            assert release.wait(5)
            body = handler(request).json()
            body["refresh_token"] = "rotated-refresh-canary"
            return httpx.Response(200, json=body)
        return handler(request)

    transport.client = httpx.Client(transport=httpx.MockTransport(refresh), trust_env=False)
    other = EncryptedVault(vault.backend, b"x" * 32)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(GmailRefreshBroker(vault, transport).refresh)
        assert entered.wait(5)
        with pytest.raises(BrokerError, match="refresh_race"):
            GmailRefreshBroker(other, transport).refresh()
        release.set()
        assert first.result()["status"] == "healthy"
    assert len(calls) == 1
    assert vault.read("gmail_known_threads")[1].generation == 2
    assert vault.read("gmail_known_threads")[1].refresh_token == "rotated-refresh-canary"
