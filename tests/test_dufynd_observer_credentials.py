from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock

import httpx
import pytest
from scripts.dufynd_observer_credentials import (
    GMAIL_SCOPE,
    KNOWN_THREADS,
    RENDER_SERVICE,
    BrokerError,
    FixedTransport,
    GmailKnownThreadBroker,
    GmailRefreshBroker,
    PrivateCredential,
    RenderReadBroker,
    metadata,
)

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
SECRET = PrivateCredential(
    "access-canary", "refresh-canary", "client-id", "client-secret-canary", "owner@example.com"
)


class MockVault:
    """Test-only adapter; production must supply durable private Vault + lock/CAS."""

    def __init__(self, state="expired"):
        self.metadata = replace(
            metadata("gmail"),
            status=state,
            health_reason=state,
            expires_at=NOW - timedelta(seconds=1),
        )
        self.secret = SECRET
        self.mutex = RLock()
        self.rotations = 0
        self.race = False

    @contextmanager
    def lock(self, _):
        with self.mutex:
            yield

    def read(self, _):
        return self.metadata, self.secret

    def rotate(self, _, generation, secret, health):
        if self.race or not self.secret or self.secret.generation != generation:
            return False
        self.secret, self.metadata = secret, health
        self.rotations += 1
        return True

    def mark(self, _, generation, health):
        if not self.secret or self.secret.generation != generation:
            return False
        self.metadata = health
        return True

    def revoke(self, _, generation, health):
        if not self.secret or self.secret.generation != generation:
            return False
        self.secret, self.metadata = None, health
        return True


def transport(handler):
    return FixedTransport(httpx.Client(transport=httpx.MockTransport(handler), trust_env=False))


def refresh_handler(request):
    if request.url.path == "/token":
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-canary",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": GMAIL_SCOPE,
            },
        )
    return httpx.Response(200, json={"emailAddress": "owner@example.com"})


@pytest.mark.parametrize(
    "state",
    [
        "missing_configuration",
        "expired",
        "revoked",
        "refresh_failed",
        "scope_mismatch",
        "account_mismatch",
    ],
)
def test_health_precise_without_human_gate(state):
    item = replace(
        metadata("gmail"), status=state, health_reason=state, expires_at=NOW - timedelta(seconds=1)
    )
    assert item.health(NOW, secret_present=True) == state
    assert not set(item.public()) & {"access_token", "refresh_token", "client_secret"}


def test_scope_contract_and_rotation_missing_secret():
    with pytest.raises(BrokerError, match="scope_mismatch"):
        replace(metadata("gmail"), oauth_scopes=("gmail.readonly",)).public()
    item = replace(
        metadata("gmail"),
        status="healthy",
        health_reason="healthy",
        expires_at=NOW + timedelta(hours=1),
    )
    assert item.health(NOW, secret_present=False) == "missing_configuration"
    assert (
        replace(item, expires_at=NOW + timedelta(minutes=2)).health(NOW, secret_present=True)
        == "expiring"
    )
    assert "access-canary" not in repr(SECRET)


def test_mock_refresh_concurrency_atomic_rotation_and_no_leak(capsys):
    vault = MockVault()
    broker = GmailRefreshBroker(vault, transport(refresh_handler), clock=lambda: NOW)
    with ThreadPoolExecutor(2) as pool:
        outputs = list(pool.map(lambda _: broker.refresh(), range(2)))
    assert vault.rotations == 1
    assert vault.secret.generation == 1
    assert vault.secret.access_token == "new-access-canary"
    assert all(x["status"] == "healthy" for x in outputs)
    assert "canary" not in json.dumps(outputs) + capsys.readouterr().out


@pytest.mark.parametrize(
    ("failure", "state", "attempts"),
    [
        ("invalid_grant", "revoked", 1),
        ("account_mismatch", "account_mismatch", 1),
        ("scope_mismatch", "scope_mismatch", 1),
        ("provider_outage", "refresh_failed", 2),
        ("rate_limited", "refresh_failed", 2),
    ],
)
def test_refresh_fail_closed_precise_and_bounded(failure, state, attempts, capsys):
    calls = []

    def handler(request):
        if request.url.path == "/token":
            calls.append(request)
        if failure == "invalid_grant":
            return httpx.Response(
                400, json={"error": "invalid_grant", "description": "refresh-canary"}
            )
        if failure == "rate_limited":
            return httpx.Response(429, json={"secret": "refresh-canary"})
        if failure == "provider_outage":
            return httpx.Response(503, text="client-secret-canary")
        if failure == "account_mismatch" and request.url.path.endswith("profile"):
            return httpx.Response(200, json={"emailAddress": "wrong@example.com"})
        if failure == "scope_mismatch":
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access-canary",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": GMAIL_SCOPE + " gmail.readonly",
                },
            )
        return refresh_handler(request)

    vault = MockVault()
    with pytest.raises(BrokerError, match=failure) as error:
        GmailRefreshBroker(vault, transport(handler), clock=lambda: NOW).refresh()
    assert vault.rotations == 0 and vault.metadata.status == state
    assert len(calls) == attempts
    assert "canary" not in str(error.value) + capsys.readouterr().out + json.dumps(
        vault.metadata.public()
    )
    if failure == "invalid_grant":
        assert vault.secret is None


def test_refresh_race_never_overwrites_and_revoke_is_fail_closed():
    vault = MockVault()
    vault.race = True
    with pytest.raises(BrokerError, match="refresh_race"):
        GmailRefreshBroker(vault, transport(refresh_handler), clock=lambda: NOW).refresh()
    assert vault.secret.access_token == "access-canary"
    vault.race = False
    with pytest.raises(BrokerError, match="provider_outage"):
        GmailRefreshBroker(
            vault, transport(lambda _: httpx.Response(503)), clock=lambda: NOW
        ).revoke()
    assert vault.secret is None and vault.metadata.status == "revoked"


@pytest.mark.parametrize(
    ("service", "method", "path"),
    [
        ("other", "GET", "deploys"),
        (RENDER_SERVICE, "POST", "deploys"),
        (RENDER_SERVICE, "GET", "env-vars"),
        (RENDER_SERVICE, "GET", "deploys/../env-vars"),
    ],
)
def test_render_denies_outside_exact_read_without_request(service, method, path):
    calls = []
    broker = RenderReadBroker(transport(lambda r: calls.append(r)), SECRET)
    with pytest.raises(BrokerError, match="scope_mismatch"):
        broker.read(service_id=service, method=method, path=path)
    assert calls == []


def test_render_filters_response_secrets_and_foreign_identity():
    deploy = {
        "id": "dep-example",
        "status": "live",
        "commit": {"id": "a" * 40, "message": "private-prose"},
        "createdAt": "2026-10-02T12:00:00Z",
        "secret": "upstream-canary",
    }
    broker = RenderReadBroker(
        transport(lambda _: httpx.Response(200, json=[{"deploy": deploy, "cursor": "private"}])),
        SECRET,
    )
    result = broker.read(service_id=RENDER_SERVICE)
    assert result[0]["service_id"] == RENDER_SERVICE
    assert "canary" not in json.dumps(result) and "private" not in json.dumps(result)
    deploy["serviceId"] = "other"
    with pytest.raises(BrokerError, match="scope_mismatch"):
        broker.read(service_id=RENDER_SERVICE)


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_transport_never_follows_redirects(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"location": "https://evil.example"})

    with pytest.raises(BrokerError, match="invalid_response"):
        RenderReadBroker(transport(handler), SECRET).read(service_id=RENDER_SERVICE)
    assert len(calls) == 1


def gmail_broker(handler):
    health = replace(
        metadata("gmail"),
        status="healthy",
        health_reason="healthy",
        expires_at=NOW + timedelta(hours=1),
    )
    return GmailKnownThreadBroker(transport(handler), SECRET, health, NOW)


def test_known_thread_filter_sender_bounce_and_no_body():
    thread = sorted(KNOWN_THREADS)[0]
    raw = {
        "id": thread,
        "historyId": "42",
        "messages": [
            {
                "id": "abc",
                "threadId": thread,
                "internalDate": "123",
                "payload": {
                    "body": {"data": "body-canary"},
                    "headers": [
                        {"name": "From", "value": "mailer-daemon@example.com"},
                        {
                            "name": "Content-Type",
                            "value": "multipart/report; report-type=delivery-status",
                        },
                    ],
                },
            },
            {
                "id": "def",
                "threadId": thread,
                "internalDate": "124",
                "labelIds": ["SENT"],
                "payload": {},
            },
        ],
    }
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=raw)

    result = gmail_broker(handler).read(thread)
    assert len(result["messages"]) == 1 and result["messages"][0]["delivery_failure"]
    assert result["messages"][0]["sender"] == "mailer-daemon@example.com"
    assert "body-canary" not in json.dumps(result)
    assert calls[0].url.params["format"] == "metadata"
    with pytest.raises(BrokerError, match="scope_mismatch"):
        gmail_broker(handler).read("unknown")
    assert len(calls) == 1


def test_history_foreign_ids_dropped_before_output_and_pagination_fail_closed():
    thread = sorted(KNOWN_THREADS)[0]
    raw = {
        "historyId": "43",
        "history": [
            {
                "id": "42",
                "messagesAdded": [
                    {"message": {"id": "abc", "threadId": thread}},
                    {"message": {"id": "foreign-canary", "threadId": "foreign-thread"}},
                ],
            }
        ],
    }

    def handler(request):
        if request.url.path.endswith("history"):
            return httpx.Response(200, json=raw)
        return httpx.Response(200, json={"id": thread, "historyId": "43", "messages": []})

    result = gmail_broker(handler).read(thread, "40")
    assert "foreign" not in json.dumps(result)
    raw["nextPageToken"] = "page2"
    with pytest.raises(BrokerError, match="invalid_response"):
        gmail_broker(lambda _: httpx.Response(200, json=raw)).read(thread, "40")


def test_history_pagination_is_drained_before_cursor_commit():
    thread = sorted(KNOWN_THREADS)[0]
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.params.get("pageToken") == "page2":
            return httpx.Response(200, json={"historyId": "44", "history": []})
        return httpx.Response(
            200, json={"historyId": "43", "history": [], "nextPageToken": "page2"}
        )

    result = gmail_broker(handler).read(thread, "40")
    assert result == {"thread_id": thread, "history_id": "44", "messages": []}
    assert len(calls) == 2


def test_secret_present_after_rotation_and_oversized_response_fail_closed():
    vault = MockVault("healthy")
    vault.secret = None
    with pytest.raises(BrokerError, match="missing_configuration"):
        GmailRefreshBroker(vault, transport(refresh_handler), clock=lambda: NOW).refresh()
    with pytest.raises(BrokerError, match="invalid_response"):
        RenderReadBroker(
            transport(lambda _: httpx.Response(200, content=b"x" * 65537)), SECRET
        ).read(service_id=RENDER_SERVICE)
