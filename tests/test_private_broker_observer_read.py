from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from private_broker import observer_read
from scripts.dufynd_observer_credentials import metadata


def recovery_health():
    return {
        p: replace(
            metadata(p),
            status="revoked" if p == "gmail" else "healthy",
            last_health_check=datetime.now(UTC),
        ).public()
        for p in ("gmail", "render")
    }


def recovery_render():
    return [
        {
            "deployment_id": "dep-live",
            "service_id": "srv-dakpfrnf3r2c73dr3f20",
            "commit_sha": "b" * 40,
            "status": "live",
            "timestamps": {
                key: None for key in ("createdAt", "updatedAt", "startedAt", "finishedAt")
            },
        }
    ]


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = {} if payload is None else payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def configure(monkeypatch, client):
    monkeypatch.setenv("BROKER_ORIGIN", "https://broker.example")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://oidc.example/token")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "tncommerce/commerce-agents")
    monkeypatch.setenv("GITHUB_REPOSITORY_ID", "1367576041")
    monkeypatch.setenv("GITHUB_REPOSITORY_OWNER_ID", "324597697")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/scentai-mvp")
    monkeypatch.setenv(
        "GITHUB_WORKFLOW_REF",
        "tncommerce/commerce-agents/.github/workflows/"
        "dufynd-private-observer.yml@refs/heads/scentai-mvp",
    )
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setattr(observer_read.httpx, "Client", lambda **kwargs: client)


def test_reports_bounded_oidc_status_without_token(monkeypatch):
    client = FakeClient([FakeResponse(403, {"token": "must-not-leak"})])
    configure(monkeypatch, client)

    with pytest.raises(SystemExit) as exc:
        observer_read.main()

    message = str(exc.value)
    assert (
        message == "private observer read failed at oidc_identity:http_403; no cursor acknowledged"
    )
    assert "must-not-leak" not in message
    assert "request-token" not in message


def test_reports_fixed_broker_stage_without_response_body(monkeypatch):
    client = FakeClient(
        [
            FakeResponse(200, {"value": "workload-token"}),
            FakeResponse(403, {"error": "secret-provider-detail"}),
        ]
    )
    configure(monkeypatch, client)

    with pytest.raises(SystemExit) as exc:
        observer_read.main()

    message = str(exc.value)
    assert message == "private observer read failed at render:http_403; no cursor acknowledged"
    assert "secret-provider-detail" not in message
    assert "workload-token" not in message


def test_rejects_non_list_render_payload(monkeypatch):
    client = FakeClient(
        [
            FakeResponse(200, {"value": "workload-token"}),
            FakeResponse(200, {"deployments": []}),
        ]
    )
    configure(monkeypatch, client)

    with pytest.raises(SystemExit) as exc:
        observer_read.main()

    assert (
        str(exc.value)
        == "private observer read failed at render:invalid_json; no cursor acknowledged"
    )


def test_success_writes_only_fixed_observations(monkeypatch, tmp_path):
    responses = [
        FakeResponse(200, {"value": "workload-token"}),
        FakeResponse(200, [{"deployment_id": "dep-1"}]),
        FakeResponse(200, {"observation_id": "a", "evidence": {"history_id": "1"}}),
        FakeResponse(200, {"observation_id": "b", "evidence": {"history_id": "2"}}),
        FakeResponse(200, {"observation_id": "c", "evidence": {"history_id": "3"}}),
        FakeResponse(200, {"gmail": {"status": "healthy"}, "render": {"status": "healthy"}}),
        FakeResponse(200, {"observation_id": "a", "evidence": {"history_id": "1"}}),
        FakeResponse(200, {"observation_id": "b", "evidence": {"history_id": "2"}}),
        FakeResponse(200, {"observation_id": "c", "evidence": {"history_id": "3"}}),
    ]
    client = FakeClient(responses)
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)

    observer_read.main()

    result = json.loads((tmp_path / "broker-observations.json").read_text(encoding="utf-8"))
    assert sorted(result) == sorted(
        [
            "_meta",
            "/v1/health",
            "/v1/render/services/srv-dakpfrnf3r2c73dr3f20/deployments",
            "/v1/gmail/threads/1a0f385ed98c6af8/metadata",
            "/v1/gmail/threads/1a0f69c169fb928f/metadata",
            "/v1/gmail/threads/1a0f6a90772a743d/metadata",
        ]
    )
    assert result["_meta"]["run_id"] == "123456789"
    assert result["_meta"]["sha"] == "a" * 40
    assert "workload-token" not in json.dumps(result)


def test_rejects_changed_pending_gmail_redelivery(monkeypatch, tmp_path):
    responses = [
        FakeResponse(200, {"value": "workload-token"}),
        FakeResponse(200, [{"deployment_id": "dep-1"}]),
        FakeResponse(200, {"observation_id": "a", "evidence": {"history_id": "1"}}),
        FakeResponse(200, {"observation_id": "b", "evidence": {"history_id": "2"}}),
        FakeResponse(200, {"observation_id": "c", "evidence": {"history_id": "3"}}),
        FakeResponse(200, {"gmail": {"status": "healthy"}, "render": {"status": "healthy"}}),
        FakeResponse(200, {"observation_id": "changed", "evidence": {"history_id": "1"}}),
    ]
    client = FakeClient(responses)
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc:
        observer_read.main()

    assert (
        str(exc.value)
        == "private observer read failed at gmail_1_repeat:pending_redelivery_mismatch; "
        "no cursor acknowledged"
    )
    assert not (tmp_path / "broker-observations.json").exists()


def test_rejects_wrong_workflow_provenance_before_oidc(monkeypatch):
    client = FakeClient([])
    configure(monkeypatch, client)
    monkeypatch.setenv("GITHUB_REPOSITORY_ID", "999")

    with pytest.raises(SystemExit) as exc:
        observer_read.main()

    assert (
        str(exc.value) == "private observer read failed at provenance:source_identity_mismatch; "
        "no cursor acknowledged"
    )
    assert client.calls == []


def test_failure_receipt_preserves_only_allowlisted_reason(monkeypatch, tmp_path):
    client = FakeClient(
        [
            FakeResponse(200, {"value": "secret-oidc"}),
            FakeResponse(200, []),
            FakeResponse(403, {"error": "invalid_grant", "token": "secret-provider"}),
        ]
    )
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="gmail_1:invalid_grant"):
        observer_read.main()
    receipt = json.loads((tmp_path / "broker-failure.json").read_text())
    assert receipt["stage"] == "gmail_1"
    assert receipt["reason"] == "invalid_grant"
    assert "secret-" not in json.dumps(receipt)
    assert not (tmp_path / "broker-observations.json").exists()
    # One bounded health read follows the failure; Gmail is never retried.
    assert len(client.calls) == 4
    assert client.calls[-1][0] == "https://broker.example/v1/health"


def test_gmail_failure_keeps_render_evidence_but_never_gmail_or_full_success(monkeypatch, tmp_path):
    render = recovery_render()
    health = recovery_health()
    client = FakeClient(
        [
            FakeResponse(payload={"value": "secret-oidc"}),
            FakeResponse(payload=render),
            FakeResponse(403, {"error": "revoked", "secret": "must-not-leak"}),
            FakeResponse(payload=health),
        ]
    )
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="gmail_1:revoked"):
        observer_read.main()
    recovery = json.loads((tmp_path / observer_read.RENDER_RECOVERY_FILE).read_text())
    assert set(recovery) == {"_meta", observer_read.RENDER_PATH, observer_read.HEALTH_PATH}
    assert recovery[observer_read.RENDER_PATH] == render
    assert recovery[observer_read.HEALTH_PATH] == health
    assert not (tmp_path / "broker-observations.json").exists()
    assert len(client.calls) == 4
    assert not any("ack" in call[0] for call in client.calls)
    assert "secret-oidc" not in json.dumps(recovery)
    assert "must-not-leak" not in json.dumps(recovery)


def test_health_failure_does_not_hide_original_gmail_failure(monkeypatch, tmp_path):
    client = FakeClient(
        [
            FakeResponse(payload={"value": "token"}),
            FakeResponse(payload=[]),
            FakeResponse(403, {"error": "revoked"}),
            FakeResponse(503, {"error": "provider_outage"}),
        ]
    )
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="gmail_1:revoked"):
        observer_read.main()
    assert json.loads((tmp_path / "broker-failure.json").read_text())["reason"] == "revoked"
    assert not (tmp_path / observer_read.RENDER_RECOVERY_FILE).exists()


@pytest.mark.parametrize(
    "target", ["deployment", "health", "timestamps", "credential", "gmail_messages"]
)
def test_unexpected_sensitive_fields_never_enter_recovery_artifact(monkeypatch, tmp_path, target):
    render, health = recovery_render(), recovery_health()
    if target == "deployment":
        render[0]["token"] = "secret-canary"
    elif target == "health":
        health["access_token"] = "secret-canary"
    elif target == "timestamps":
        render[0]["timestamps"]["token"] = "secret-canary"
    elif target == "credential":
        health["render"]["secret_reference"] = "secret-canary"
    else:
        health["gmail"]["messages"] = [{"body": "secret-canary"}]
    client = FakeClient(
        [
            FakeResponse(payload={"value": "token"}),
            FakeResponse(payload=render),
            FakeResponse(403, {"error": "revoked"}),
            FakeResponse(payload=health),
        ]
    )
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="gmail_1:revoked"):
        observer_read.main()
    assert not (tmp_path / observer_read.RENDER_RECOVERY_FILE).exists()
    assert "secret-canary" not in (tmp_path / "broker-failure.json").read_text()


def test_failed_retry_cannot_upload_previous_success_or_recovery(monkeypatch, tmp_path):
    configure(monkeypatch, FakeClient([FakeResponse(403)]))
    monkeypatch.chdir(tmp_path)
    for filename in (
        "broker-observations.json",
        "broker-failure.json",
        observer_read.RENDER_RECOVERY_FILE,
    ):
        (tmp_path / filename).write_text('{"stale":true}')
    with pytest.raises(SystemExit, match="oidc_identity:http_403"):
        observer_read.main()
    assert list(tmp_path.iterdir()) == []


def test_gmail_network_exception_produces_bounded_failure_and_render_recovery(
    monkeypatch, tmp_path
):
    class NetworkFailure(FakeClient):
        def get(self, url, **kwargs):
            if "/gmail/" in url:
                self.calls.append((url, kwargs))
                raise httpx.ConnectError("secret-provider-error")
            return super().get(url, **kwargs)

    client = NetworkFailure(
        [
            FakeResponse(payload={"value": "token"}),
            FakeResponse(payload=recovery_render()),
            FakeResponse(payload=recovery_health()),
        ]
    )
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="gmail_1:transport_error"):
        observer_read.main()
    assert (tmp_path / observer_read.RENDER_RECOVERY_FILE).exists()
    failure = (tmp_path / "broker-failure.json").read_text()
    assert "secret-provider-error" not in failure
    assert "transport_error" in failure


def test_redelivery_mismatch_emits_failure_receipt_and_only_render_recovery(monkeypatch, tmp_path):
    health = recovery_health()
    first = {"observation_id": "a", "evidence": {"history_id": "1"}}
    client = FakeClient(
        [
            FakeResponse(payload={"value": "token"}),
            FakeResponse(payload=recovery_render()),
            *[FakeResponse(payload=first) for _ in range(3)],
            FakeResponse(payload=health),
            FakeResponse(payload={**first, "observation_id": "changed"}),
            FakeResponse(payload=health),
        ]
    )
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="pending_redelivery_mismatch"):
        observer_read.main()
    failure = json.loads((tmp_path / "broker-failure.json").read_text())
    from scripts.dufynd_private_observer_failure import validate_failure

    assert validate_failure(failure, run_id="123456789", sha="a" * 40)["stage"] == "gmail_1_repeat"
    assert (tmp_path / observer_read.RENDER_RECOVERY_FILE).exists()
    assert not (tmp_path / "broker-observations.json").exists()


def test_failure_ingestion_rejects_wrong_run_and_unbounded_reason(monkeypatch):
    from scripts.dufynd_private_observer_failure import validate_failure

    configure(monkeypatch, FakeClient([]))
    payload = {
        "_meta": observer_read.source_from_env(),
        "stage": "gmail_1",
        "reason": "invalid_grant",
    }
    assert validate_failure(payload, run_id="123456789", sha="a" * 40) == payload
    with pytest.raises(ValueError, match="invalid failure reason"):
        validate_failure(
            {**payload, "reason": "sensitive provider detail"}, run_id="123456789", sha="a" * 40
        )
    with pytest.raises(observer_read.ProvenanceError, match="source_run_mismatch"):
        validate_failure(payload, run_id="999", sha="a" * 40)
