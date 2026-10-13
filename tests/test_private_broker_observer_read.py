from __future__ import annotations

import json

import pytest
from private_broker import observer_read


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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


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
    receipt = json.loads((tmp_path / "broker-failure.json").read_text())
    assert receipt["stage"] == "gmail_1_repeat"
    assert receipt["reason"] == "pending_redelivery_mismatch"
    from scripts.dufynd_private_observer_failure import validate_failure

    assert validate_failure(receipt, run_id="123456789", sha="a" * 40) == receipt
    assert len(client.calls) == 7


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
    assert len(client.calls) == 3


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


@pytest.mark.parametrize("repeat_index", [1, 2, 3])
@pytest.mark.parametrize("reason", ["revoked", "rate_limited", "sensitive-provider-canary"])
def test_repeat_read_failure_is_durable_bounded_and_never_retried(
    monkeypatch, tmp_path, repeat_index, reason
):
    observations = [
        {"observation_id": str(i), "evidence": {"history_id": str(i)}} for i in range(1, 4)
    ]
    client = FakeClient(
        [
            FakeResponse(200, {"value": "oidc-canary"}),
            FakeResponse(200, []),
            *[FakeResponse(200, item) for item in observations],
            FakeResponse(200, {"gmail": {"status": "healthy"}}),
            *[FakeResponse(200, item) for item in observations[: repeat_index - 1]],
            FakeResponse(403, {"error": reason, "token": "provider-canary"}),
        ]
    )
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    expected_reason = reason if reason in {"revoked", "rate_limited"} else "http_403"
    with pytest.raises(SystemExit, match=f"gmail_{repeat_index}_repeat:{expected_reason}"):
        observer_read.main()
    receipt = json.loads((tmp_path / "broker-failure.json").read_text())
    assert receipt["stage"] == f"gmail_{repeat_index}_repeat"
    assert receipt["reason"] == expected_reason
    assert "canary" not in json.dumps(receipt)
    assert not (tmp_path / "broker-observations.json").exists()
    assert len(client.calls) == 6 + repeat_index
    from scripts.dufynd_private_observer_failure import validate_failure

    assert validate_failure(receipt, run_id="123456789", sha="a" * 40) == receipt


def test_failure_ingestion_rejects_nonexistent_repeat_stage(monkeypatch):
    from scripts.dufynd_private_observer_failure import validate_failure

    configure(monkeypatch, FakeClient([]))
    payload = {
        "_meta": observer_read.source_from_env(),
        "stage": "gmail_4_repeat",
        "reason": "revoked",
    }
    with pytest.raises(ValueError, match="invalid failure stage"):
        validate_failure(payload, run_id="123456789", sha="a" * 40)


@pytest.mark.parametrize(
    "position,stage",
    list(
        enumerate(
            [
                "render",
                "gmail_1",
                "gmail_2",
                "gmail_3",
                "health",
                "gmail_1_repeat",
                "gmail_2_repeat",
                "gmail_3_repeat",
            ],
            start=1,
        )
    ),
)
@pytest.mark.parametrize(
    "failure", [observer_read.httpx.ReadTimeout, observer_read.httpx.ConnectError]
)
def test_transport_failure_records_stage_without_retry_or_secret(
    monkeypatch, tmp_path, position, stage, failure
):
    observations = [
        {"observation_id": str(i), "evidence": {"history_id": str(i)}} for i in range(3)
    ]
    responses = [
        FakeResponse(200, {"value": "oidc-secret-canary"}),
        FakeResponse(200, []),
        *[FakeResponse(200, item) for item in observations],
        FakeResponse(200, {}),
        *[FakeResponse(200, item) for item in observations],
    ]
    responses[position] = failure("provider-secret-canary https://secret.invalid/?token=secret")
    client = FakeClient(responses)
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        observer_read.main()
    assert (
        str(exc.value)
        == f"private observer read failed at {stage}:transport_error; no cursor acknowledged"
    )
    receipt = json.loads((tmp_path / "broker-failure.json").read_text())
    assert receipt["stage"] == stage
    assert receipt["reason"] == "transport_error"
    assert "secret" not in json.dumps(receipt)
    assert not (tmp_path / "broker-observations.json").exists()
    assert len(client.calls) == position + 1
    from scripts.dufynd_private_observer_failure import validate_failure

    assert validate_failure(receipt, run_id="123456789", sha="a" * 40) == receipt


def test_oidc_transport_failure_stays_outside_broker_receipts(monkeypatch, tmp_path):
    client = FakeClient([observer_read.httpx.ConnectError("oidc-secret-canary")])
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="failed at internal"):
        observer_read.main()
    assert len(client.calls) == 1
    assert not (tmp_path / "broker-failure.json").exists()


def test_unexpected_error_is_not_misclassified_as_transport(monkeypatch, tmp_path):
    client = FakeClient([FakeResponse(200, {"value": "oidc-secret"}), RuntimeError("secret")])
    configure(monkeypatch, client)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="failed at internal"):
        observer_read.main()
    assert len(client.calls) == 2
    assert not (tmp_path / "broker-failure.json").exists()
