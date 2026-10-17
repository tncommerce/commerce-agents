"""Scheduler OIDC contract, path confinement and actual refresh – all offline/fake.

No Google account, Gmail, private broker or provider creds are used here.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Lock
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from private_broker.runtime import Config, OAuth, WorkloadAuth, create_app
from private_broker.scheduler_oidc import (
    GOOGLE_SCHEDULER_ISSUER,
    SCHEDULER_PATH,
    SchedulerOIDC,
)
from private_broker.store import EncryptedVault
from scripts.dufynd_observer_credentials import (
    GMAIL_SCOPE,
    BrokerError,
    FixedTransport,
)

EMAIL = "dufynd-refresh-scheduler@project-test.iam.gserviceaccount.com"
CONFIG = Config(
    "https://broker.example.com",
    "owner@example.com",
    "client-id",
    "client-secret-canary",
    "owner-secret-canary-01234567890123456789",
    "render-secret-canary",
    "12345",
    True,
    EMAIL,
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


def token(key, **overrides):
    now = int(time.time())
    claims = {
        "iss": GOOGLE_SCHEDULER_ISSUER,
        "aud": CONFIG.origin + SCHEDULER_PATH,
        "sub": "verified-service-account-subject",
        "email": EMAIL,
        "email_verified": True,
        "iat": now,
        "exp": now + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


def keys_for(key):
    return SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("iss", "https://token.actions.githubusercontent.com"),
        ("aud", CONFIG.origin),
        ("sub", ""),
        ("email", "unknown@project-test.iam.gserviceaccount.com"),
        ("email_verified", False),
        ("exp", 1),
        ("iat", 1),
    ],
)
def test_scheduler_identity_fail_closed(field, value):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = SchedulerOIDC(CONFIG, keys_for(key))
    verifier.verify(token(key))
    with pytest.raises(BrokerError, match="broker_activation_required"):
        verifier.verify(token(key, **{field: value}))


def test_scheduler_rejects_bad_signature_and_disabled_config():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = SchedulerOIDC(CONFIG, keys_for(key))
    with pytest.raises(BrokerError, match="broker_activation_required"):
        verifier.verify(token(other))
    disabled = replace(CONFIG, scheduler_sa_email="")
    with pytest.raises(BrokerError, match="broker_activation_required"):
        SchedulerOIDC(disabled, keys_for(key)).verify(token(key))
    with pytest.raises(BrokerError, match="missing_configuration"):
        replace(CONFIG, scheduler_sa_email="attacker@example.com").validate()


def test_scheduler_rejects_stale_and_excessive_lifetime():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = SchedulerOIDC(CONFIG, keys_for(key))
    now = int(time.time())
    for claims in ({"iat": now - 601}, {"exp": now + 3601}, {"iat": now + 60}):
        with pytest.raises(BrokerError, match="broker_activation_required"):
            verifier.verify(token(key, **claims))


def test_scheduler_can_refresh_but_not_read_ack_or_admin():
    calls = []
    thread_reads = []
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def handler(request):
        if request.url.path == "/token":
            calls.append("token")
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access-canary",
                    "refresh_token": "refresh-canary",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": GMAIL_SCOPE,
                },
            )
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": CONFIG.mailbox})
        if "/threads/" in request.url.path:
            thread_reads.append(str(request.url))
            return httpx.Response(503, json={})
        raise AssertionError("Unexpected upstream route")

    vault = EncryptedVault(MemoryCAS(), b"x" * 32)
    transport = FixedTransport(
        httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
    )
    oauth = OAuth(CONFIG, vault, transport)
    query = parse_qs(urlsplit(oauth.start()["authorization_url"]).query)
    oauth.callback(query["state"][0], "code-canary")
    with vault.lock("gmail_known_threads"):
        health, secret = vault.read("gmail_known_threads")
        assert vault.mark(
            "gmail_known_threads",
            secret.generation,
            replace(
                health,
                expires_at=datetime.now(UTC) - timedelta(seconds=5),
                status="expired",
                health_reason="expired",
            ),
        )

    scheduler_auth = SchedulerOIDC(CONFIG, keys_for(key))
    github_auth = WorkloadAuth(CONFIG, keys_for(key))
    client = TestClient(create_app(CONFIG, vault, transport, github_auth, scheduler_auth))
    auth = {"Authorization": "Bearer " + token(key)}
    before = len(calls)

    for method, url in (
        ("GET", SCHEDULER_PATH),
        ("POST", SCHEDULER_PATH + "?task=other"),
        ("POST", "/owner/gmail/revoke"),
        ("GET", "/v1/health"),
    ):
        assert client.request(method, url, headers=auth).status_code == 403
    assert len(calls) == before

    reply = client.post(SCHEDULER_PATH, headers=auth)
    assert reply.status_code == 204
    assert not reply.content
    assert reply.headers["cache-control"] == "no-store"
    assert len(calls) == before + 1
    health, secret = vault.read("gmail_known_threads")
    assert health.status == "healthy"
    assert health.expires_at > datetime.now(UTC) + timedelta(minutes=30)
    assert secret.generation == 2

    # Repeated Cloud Scheduler request is a no-op while access token is healthy.
    assert client.post(SCHEDULER_PATH, headers=auth).status_code == 204
    assert len(calls) == before + 1
    assert not thread_reads
    assert all(vault.thread_state(t).get("cursor") is None for t in (
        "1a0f385ed98c6af8", "1a0f69c169fb928f", "1a0f6a90772a743d"
    ))
    assert "refresh-canary" not in reply.text
    assert "new-access-canary" not in reply.text
    assert not json.loads(json.dumps({"status": "read-only"})).get("secret")


def test_scheduler_feature_not_enabled_by_default():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    config = replace(CONFIG, scheduler_sa_email="")
    config.validate()
    vault = EncryptedVault(MemoryCAS(), b"x" * 32)
    transport = FixedTransport(
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    )
    client = TestClient(
        create_app(
            config,
            vault,
            transport,
            WorkloadAuth(config, keys_for(key)),
            SchedulerOIDC(config, keys_for(key)),
        )
    )
    reply = client.post(SCHEDULER_PATH, headers={"Authorization": "Bearer " + token(key)})
    assert reply.status_code == 403
    assert reply.json() == {"error": "broker_activation_required"}
