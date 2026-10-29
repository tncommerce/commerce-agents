"""Real HTTP boundary cases for the explicitly gated two-service read scope."""

from __future__ import annotations

import base64
import io
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import private_broker.runtime as runtime
import pytest
from fastapi.testclient import TestClient
from scripts.dufynd_observer_credentials import (
    RENDER_SCOPE_V2,
    RENDER_SERVICE,
    RENDER_SERVICES_V2,
    RENDER_STOREFRONT_SERVICE,
    BrokerError,
    FixedTransport,
    PrivateCredential,
    RenderReadBroker,
    RenderServicesReadBroker,
    metadata,
)

HEADERS = {"Authorization": "Bearer workload-canary"}
CONFIG = runtime.Config(
    origin="https://broker.example.com",
    mailbox="owner@example.com",
    client_id="client-id",
    client_secret="google-secret-canary",
    owner_key="owner-secret-canary-01234567890123456789",
    render_key="render-secret-canary",
    repository_id="1367576041",
    render_services_v2=True,
)


class UntouchedVault:
    """Any v2 state/health/Gmail access is a test failure, including a lock."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        self.calls.append(name)
        raise AssertionError("v2 must not access the legacy vault")


def deployment(service_id, **changes):
    return {
        "id": "dep-example",
        "serviceId": service_id,
        "commit": {"id": "a" * 40, "message": "private-message-canary"},
        "status": "live",
        "createdAt": "2026-10-29T10:00:00Z",
        "updatedAt": "2026-10-29T10:01:00+00:00",
        "startedAt": None,
        "finishedAt": "2026-10-29T10:01:00.123456Z",
        "env": {"SECRET": "provider-secret-canary"},
        **changes,
    }


def make_client(handler, *, enabled=True, transport_enabled=True, render_key=None, auth=None):
    vault = UntouchedVault()
    transport = FixedTransport(
        httpx.Client(transport=httpx.MockTransport(handler), trust_env=False),
        render_services_v2=transport_enabled,
    )
    config = replace(
        CONFIG,
        render_services_v2=enabled,
        render_key=CONFIG.render_key if render_key is None else render_key,
    )
    verifier = auth or SimpleNamespace(verify=lambda token: None)
    return TestClient(runtime.create_app(config, vault, transport, verifier)), vault


def path(service_id):
    return f"/v2/render/services/{service_id}/deployments"


def test_two_services_have_actual_independent_read_times_and_no_global_health(monkeypatch):
    start = datetime(2026, 10, 29, 10, tzinfo=UTC)
    observed = [start]
    events = []

    class Clock:
        @staticmethod
        def now(tz):
            assert tz is UTC
            events.append("timestamp")
            return observed[0]

    def handler(request):
        service_id = request.url.path.split("/")[-2]
        assert service_id in RENDER_SERVICES_V2
        assert request.url.host == "api.render.com"
        assert request.method == "GET"
        assert dict(request.url.params) == {"limit": "20"}
        assert request.headers["authorization"] == "Bearer render-secret-canary"
        assert request.headers["accept-encoding"] == "identity"
        events.append(service_id)
        observed[0] += timedelta(seconds=7)
        return httpx.Response(200, json=[{"deploy": deployment(service_id), "cursor": "private"}])

    monkeypatch.setattr(runtime, "datetime", Clock)
    client, vault = make_client(handler)
    bodies = []
    for service_id in RENDER_SERVICES_V2:
        response = client.get(path(service_id), headers=HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"version", "scope_id", "service_id", "observed_at", "deployments"}
        assert body["version"] == 2
        assert body["scope_id"] == RENDER_SCOPE_V2
        assert body["service_id"] == service_id
        assert body["deployments"][0]["service_id"] == service_id
        assert set(body["deployments"][0]) == {
            "deployment_id",
            "service_id",
            "commit_sha",
            "status",
            "timestamps",
        }
        assert "canary" not in response.text and "private" not in response.text
        assert response.headers["cache-control"] == "no-store"
        bodies.append(body)
    assert bodies[0]["observed_at"] == (start + timedelta(seconds=7)).isoformat()
    assert bodies[1]["observed_at"] == (start + timedelta(seconds=14)).isoformat()
    assert events == [RENDER_SERVICE, "timestamp", RENDER_STOREFRONT_SERVICE, "timestamp"]
    assert vault.calls == []


@pytest.mark.parametrize("service_id", RENDER_SERVICES_V2)
@pytest.mark.parametrize(
    "enabled,transport_enabled", [(False, False), (False, True), (True, False)]
)
def test_both_explicit_gates_are_required_before_network(service_id, enabled, transport_enabled):
    calls = []
    client, vault = make_client(
        lambda request: calls.append(request), enabled=enabled, transport_enabled=transport_enabled
    )
    response = client.get(path(service_id), headers=HEADERS)
    assert response.status_code == 403
    assert response.json() == {"error": "broker_activation_required"}
    assert calls == [] and vault.calls == []


@pytest.mark.parametrize(
    "method,url",
    [
        ("GET", path("srv-other")),
        ("POST", path(RENDER_SERVICE)),
        ("DELETE", path(RENDER_STOREFRONT_SERVICE)),
        ("PATCH", path(RENDER_SERVICE)),
        ("GET", path(RENDER_SERVICE) + "/"),
        ("GET", path(RENDER_SERVICE) + "?url=https://evil.invalid"),
        ("GET", path(RENDER_SERVICE) + "?limit=1"),
        ("GET", "/v2/render/services/" + RENDER_SERVICE + "/env"),
        ("GET", "/v2/render/services/" + RENDER_SERVICE + "/logs"),
        ("GET", "/v2/render/services/" + RENDER_SERVICE + "/restart"),
    ],
)
def test_unknown_services_paths_queries_and_mutations_never_reach_provider(method, url):
    calls = []
    client, vault = make_client(lambda request: calls.append(request))
    response = client.request(method, url, headers=HEADERS, follow_redirects=False)
    assert response.status_code in {403, 404, 405}
    assert calls == [] and vault.calls == []


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic canary"}]
)
def test_workload_authentication_precedes_v2_provider_access(headers):
    calls = []

    def reject(token):
        raise BrokerError("broker_activation_required")

    client, vault = make_client(
        lambda request: calls.append(request), auth=SimpleNamespace(verify=reject)
    )
    response = client.get(path(RENDER_SERVICE), headers=headers)
    assert response.status_code == 403
    assert response.json() == {"error": "broker_activation_required"}
    assert calls == [] and vault.calls == []


@pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 401, 403, 404, 429, 500, 503])
def test_failed_or_redirected_reads_have_no_freshness_receipt(status, monkeypatch):
    calls = []

    class NoSuccessClock:
        @staticmethod
        def now(tz):
            pytest.fail("failed read must not create an observation timestamp")

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, headers={"location": "https://evil.invalid"}, text="secret-canary"
        )

    monkeypatch.setattr(runtime, "datetime", NoSuccessClock)
    client, vault = make_client(handler)
    response = client.get(path(RENDER_STOREFRONT_SERVICE), headers=HEADERS)
    assert response.status_code == 403
    assert set(response.json()) == {"error"}
    assert "canary" not in response.text
    assert len(calls) == 1 and vault.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        [None],
        [deployment(RENDER_SERVICE)] * 21,
        [deployment(RENDER_SERVICE), deployment(RENDER_SERVICE)],
        [deployment(RENDER_STOREFRONT_SERVICE)],
        [deployment(RENDER_SERVICE, commit={"id": "not-a-sha"})],
        [deployment(RENDER_SERVICE, status="unknown")],
        [deployment(RENDER_SERVICE, createdAt="2026-10-29T10:00:00")],
        [deployment(RENDER_SERVICE, createdAt="2026-10-29 10:00:00+00:00")],
        [deployment(RENDER_SERVICE, createdAt="2026-10-29T10:00:00.1234567Z")],
        [deployment(RENDER_SERVICE, createdAt="infinity")],
    ],
)
def test_malformed_cross_service_and_empty_evidence_have_no_success(payload, monkeypatch):
    class NoSuccessClock:
        @staticmethod
        def now(tz):
            pytest.fail("invalid evidence must not receive an observation timestamp")

    monkeypatch.setattr(runtime, "datetime", NoSuccessClock)
    client, vault = make_client(lambda _: httpx.Response(200, json=payload))
    response = client.get(path(RENDER_SERVICE), headers=HEADERS)
    assert response.status_code == 403
    assert set(response.json()) == {"error"}
    assert vault.calls == []


def test_missing_mounted_key_rejects_before_network():
    calls = []
    client, vault = make_client(lambda request: calls.append(request), render_key="")
    response = client.get(path(RENDER_SERVICE), headers=HEADERS)
    assert response.json() == {"error": "missing_configuration"}
    assert calls == [] and vault.calls == []


def test_default_transport_and_legacy_broker_keep_api_only_scope():
    calls = []
    client = httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(request)))
    legacy = FixedTransport(client)
    with pytest.raises(BrokerError, match="scope_mismatch"):
        legacy.request(
            "GET", f"https://api.render.com/v1/services/{RENDER_STOREFRONT_SERVICE}/deploys"
        )
    enabled = FixedTransport(client, render_services_v2=True)
    with pytest.raises(BrokerError, match="scope_mismatch"):
        RenderReadBroker(enabled, PrivateCredential("canary")).read(
            service_id=RENDER_STOREFRONT_SERVICE
        )
    assert metadata("render").public()["allowed_resources"] == [RENDER_SERVICE]
    assert calls == []


@pytest.mark.parametrize("value", [None, "1", "true", 1, 0, [], {}])
def test_runtime_and_transport_config_reject_truthy_or_malformed_opt_in(value):
    with pytest.raises(BrokerError, match="missing_configuration"):
        replace(CONFIG, render_services_v2=value).validate()
    with pytest.raises(BrokerError, match="missing_configuration"):
        FixedTransport(httpx.Client(), render_services_v2=value)


@pytest.mark.parametrize(
    "value", ["1", "true", "disabled", "api", "api-storefront-v2 ", "*", "unknown"]
)
def test_production_scope_flag_is_exact_and_checked_before_secret_reads(monkeypatch, value):
    monkeypatch.setattr(runtime.logging, "disable", lambda level: None)
    for name in (
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SECRET_KEY",
        "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BROKER_RENDER_SERVICES_V2", value)

    def no_secret_read(*args, **kwargs):
        pytest.fail("unknown scope flag must fail before reading secret files")

    monkeypatch.setattr("builtins.open", no_secret_read)
    with pytest.raises(BrokerError, match="missing_configuration"):
        runtime.production_app()


@pytest.mark.parametrize("value,enabled", [(None, False), ("", False), ("api-storefront-v2", True)])
def test_production_wires_only_the_explicit_scope_and_defaults_off(monkeypatch, value, enabled):
    monkeypatch.setattr(runtime.logging, "disable", lambda level: None)
    for name in (
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SECRET_KEY",
        "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    if value is None:
        monkeypatch.delenv("BROKER_RENDER_SERVICES_V2", raising=False)
    else:
        monkeypatch.setenv("BROKER_RENDER_SERVICES_V2", value)
    for name, setting in {
        "BROKER_ORIGIN": CONFIG.origin,
        "BROKER_MAILBOX": CONFIG.mailbox,
        "GOOGLE_CLIENT_ID": CONFIG.client_id,
        "BROKER_REPOSITORY_ID": CONFIG.repository_id,
        "BROKER_PROJECT": "private-broker-project",
    }.items():
        monkeypatch.setenv(name, setting)
    values = {
        "/run/secrets/google-client-secret-dir/value": CONFIG.client_secret,
        "/run/secrets/owner-key-dir/value": CONFIG.owner_key,
        "/run/secrets/render-key-dir/value": CONFIG.render_key,
        "/run/secrets/encryption-key-dir/value": base64.b64encode(b"x" * 32).decode(),
    }
    monkeypatch.setattr("builtins.open", lambda name, **kwargs: io.StringIO(values[name]))
    monkeypatch.setattr(runtime.httpx, "Client", lambda **kwargs: object())
    monkeypatch.setattr(runtime.jwt, "PyJWKClient", lambda *args, **kwargs: object())
    captured = {}

    def inspect(config, vault, transport, auth):
        captured.update(config=config, transport=transport, auth=auth)
        return "app-sentinel"

    monkeypatch.setattr(runtime, "create_app", inspect)
    assert runtime.production_app() == "app-sentinel"
    assert captured["config"].render_services_v2 is enabled
    assert captured["transport"].render_services_v2 is enabled
    assert captured["config"].render_key == CONFIG.render_key
    assert metadata("render").allowed_resources == (RENDER_SERVICE,)


@pytest.mark.parametrize("service_id", RENDER_SERVICES_V2)
def test_provider_only_whitelisted_methods_and_paths(service_id):
    calls = []
    transport = FixedTransport(
        httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(request))),
        render_services_v2=True,
    )
    broker = RenderServicesReadBroker(transport, PrivateCredential("canary"))
    for method, suffix in (
        ("POST", "deploys"),
        ("GET", "env-vars"),
        ("GET", "deploys/../env-vars"),
    ):
        with pytest.raises(BrokerError, match="scope_mismatch"):
            broker.read(service_id=service_id, method=method, path=suffix)
    for method, url in (
        ("POST", f"https://api.render.com/v1/services/{service_id}/deploys"),
        ("GET", f"https://api.render.com/v1/services/{service_id}/env-vars"),
        ("GET", "https://api.render.com/v1/services/srv-other/deploys"),
        ("GET", f"https://evil.invalid/v1/services/{service_id}/deploys"),
    ):
        with pytest.raises(BrokerError, match="scope_mismatch"):
            transport.request(method, url)
    assert calls == []


@pytest.mark.parametrize("service_id", RENDER_SERVICES_V2)
@pytest.mark.parametrize("field", ["serviceId", "id", "status", "unknown_nan"])
def test_v2_rejects_duplicate_upstream_keys_and_non_json_constants(service_id, field):
    payload = json.dumps(deployment(service_id))
    if field == "unknown_nan":
        payload = '{"provider_noise":NaN,' + payload[1:]
    else:
        payload = '{"' + field + '":"foreign-secret-canary",' + payload[1:]
    client, vault = make_client(lambda _: httpx.Response(200, content="[" + payload + "]"))
    response = client.get(path(service_id), headers=HEADERS)
    assert response.status_code == 403
    assert response.json() == {"error": "invalid_response"}
    assert vault.calls == [] and "canary" not in response.text


@pytest.mark.parametrize("length,status", [(100, 200), (101, 403)])
def test_v2_deployment_id_bound_matches_reader_and_storage(length, status):
    payload = [deployment(RENDER_SERVICE, id="dep-" + "a" * length)]
    client, vault = make_client(lambda _: httpx.Response(200, json=payload))
    response = client.get(path(RENDER_SERVICE), headers=HEADERS)
    assert response.status_code == status
    assert vault.calls == []


def test_v1_decode_contract_is_unchanged_when_v2_transport_is_enabled():
    payload = '{"serviceId":"previously-ignored",' + json.dumps(deployment(RENDER_SERVICE))[1:]
    transport = FixedTransport(
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, content="[" + payload + "]")
            )
        ),
        render_services_v2=True,
    )
    result = RenderReadBroker(transport, PrivateCredential("canary")).read(
        service_id=RENDER_SERVICE
    )
    assert result[0]["service_id"] == RENDER_SERVICE


@pytest.mark.parametrize("encoding", ["gzip", "br", "deflate", "identity,gzip"])
def test_v2_rejects_unexpected_compression_before_reading_body(encoding):
    seen = []

    class UnreadBody(httpx.SyncByteStream):
        def __iter__(self):
            seen.append("iterated")
            yield b"body-must-not-be-read"

        def close(self):
            seen.append("closed")

    def handler(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers={"Content-Encoding": encoding}, stream=UnreadBody())

    client, vault = make_client(handler)
    response = client.get(path(RENDER_SERVICE), headers=HEADERS)
    assert response.json() == {"error": "invalid_response"}
    assert seen == ["closed"] and vault.calls == []


def test_v2_oversized_stream_stops_before_the_remaining_chunks():
    seen = []

    class TooMuchBody(httpx.SyncByteStream):
        def __iter__(self):
            seen.append("first")
            yield b"x" * 65537
            seen.append("extra")
            yield b"body-must-not-be-read"

        def close(self):
            seen.append("closed")

    client, vault = make_client(lambda _: httpx.Response(200, stream=TooMuchBody()))
    response = client.get(path(RENDER_SERVICE), headers=HEADERS)
    assert response.json() == {"error": "invalid_response"}
    assert seen == ["first", "closed"] and vault.calls == []
