"""Inputless monitoring reads Render and health, never Gmail or acceptance."""

from __future__ import annotations

import copy
import json
import shlex
from pathlib import Path

import httpx
import pytest
import yaml
from private_broker import observer_read
from scripts.dufynd_private_observer_ingest import (
    ArtifactError,
    ingest_render_artifact,
)
from tests.test_dufynd_render_observer_recovery import SOURCE, Bridge, artifact
from tests.test_private_broker_observer_read import (
    FakeClient,
    FakeResponse,
    configure,
    recovery_health,
    recovery_render,
)


@pytest.mark.parametrize("mode", [None, "render"])
@pytest.mark.parametrize("gmail_state", ["revoked", "missing_configuration", "expired"])
def test_successful_render_default_never_requests_gmail_or_ack(
    monkeypatch, tmp_path, mode, gmail_state
):
    health = recovery_health()
    health["gmail"]["status"] = gmail_state
    client = FakeClient(
        [
            FakeResponse(200, {"value": "workload-token"}),
            FakeResponse(200, recovery_render()),
            FakeResponse(200, health),
        ]
    )
    configure(monkeypatch, client, mode=mode)
    monkeypatch.chdir(tmp_path)
    observer_read.main()
    assert [url for url, _ in client.calls] == [
        "https://oidc.example/token",
        "https://broker.example" + observer_read.RENDER_PATH,
        "https://broker.example/v1/health",
    ]
    output = json.loads((tmp_path / observer_read.RENDER_SUCCESS_FILE).read_text())
    assert set(output) == {"_meta", observer_read.RENDER_PATH, observer_read.HEALTH_PATH}
    assert output["/v1/health"]["gmail"]["status"] == gmail_state
    assert sorted(p.name for p in tmp_path.iterdir()) == [observer_read.RENDER_SUCCESS_FILE]
    assert "workload-token" not in json.dumps(output)


def test_render_mode_preserves_no_redirect_no_proxy_and_bounded_timeout(monkeypatch, tmp_path):
    client = FakeClient(
        [
            FakeResponse(200, {"value": "workload-token"}),
            FakeResponse(200, recovery_render()),
            FakeResponse(200, recovery_health()),
        ]
    )
    configure(monkeypatch, client, mode=None)
    monkeypatch.chdir(tmp_path)
    configurations = []

    def factory(**kwargs):
        configurations.append(kwargs)
        return client

    monkeypatch.setattr(observer_read.httpx, "Client", factory)
    observer_read.main()
    assert configurations == [{"trust_env": False, "timeout": 30, "follow_redirects": False}]


@pytest.mark.parametrize(
    "response,reason",
    [
        (FakeResponse(503, {"error": "provider_outage"}), "provider_outage"),
        (FakeResponse(302, {"Location": "https://gmail.example"}), "http_302"),
        (FakeResponse(200, []), "invalid_response"),
        (FakeResponse(200, [{"unknown": "provider-secret"}]), "invalid_response"),
    ],
)
def test_render_failure_is_failed_without_recovery_or_acceptance(
    monkeypatch, tmp_path, response, reason
):
    client = FakeClient(
        [
            FakeResponse(200, {"value": "workload-token"}),
            response,
            FakeResponse(200, recovery_health()),
        ]
    )
    configure(monkeypatch, client, mode=None)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="render:" + reason):
        observer_read.main()
    failure = json.loads((tmp_path / "broker-failure.json").read_text())
    assert failure["stage"] == "render" and failure["reason"] == reason
    assert sorted(p.name for p in tmp_path.iterdir()) == ["broker-failure.json"]
    assert len(client.calls) <= 3


def test_render_transport_failure_never_performs_additional_provider_reads(monkeypatch, tmp_path):
    class NetworkFailure(FakeClient):
        def get(self, url, **kwargs):
            if "/v1/render/" in url:
                self.calls.append((url, kwargs))
                raise httpx.ConnectError("must-not-leak")
            return super().get(url, **kwargs)

    client = NetworkFailure([FakeResponse(200, {"value": "token"})])
    configure(monkeypatch, client, mode=None)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="render:transport_error") as exc:
        observer_read.main()
    assert "must-not-leak" not in str(exc.value)
    assert len(client.calls) == 2


def test_invalid_mode_removes_old_artifacts_before_any_oidc_or_provider_read(monkeypatch, tmp_path):
    client = FakeClient([])
    configure(monkeypatch, client, mode="gmail")
    monkeypatch.chdir(tmp_path)
    for name in (
        "broker-observations.json",
        "broker-failure.json",
        observer_read.RENDER_SUCCESS_FILE,
        observer_read.RENDER_RECOVERY_FILE,
    ):
        (tmp_path / name).write_text("previous attempt")
    with pytest.raises(SystemExit, match="invalid observer mode"):
        observer_read.main()
    assert client.calls == [] and list(tmp_path.iterdir()) == []


def test_render_artifact_limit_fails_without_publishing_success(monkeypatch, tmp_path):
    client = FakeClient(
        [
            FakeResponse(200, {"value": "token"}),
            FakeResponse(200, recovery_render()),
            FakeResponse(200, recovery_health()),
        ]
    )
    configure(monkeypatch, client, mode=None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(observer_read, "MAX_ARTIFACT_BYTES", 100)
    with pytest.raises(SystemExit, match="render:invalid_response"):
        observer_read.main()
    assert not (tmp_path / observer_read.RENDER_SUCCESS_FILE).exists()


def ingest(bridge, path, **changes):
    return ingest_render_artifact(
        bridge,
        path,
        **{
            "expected_run_id": SOURCE["run_id"],
            "expected_sha": SOURCE["sha"],
            "expected_run_attempt": SOURCE["run_attempt"],
            **changes,
        },
    )


def test_success_uses_same_atomic_capture_without_failure_or_acceptance(tmp_path):
    bridge = Bridge()
    result = ingest(bridge, artifact(tmp_path))
    assert [name for name, _ in bridge.calls] == ["capture"]
    assert result["render_captures"] == 1 and result["gmail_captures"] == 0
    assert result["acks"] == 0
    assert result["full_chain_complete"] is False and result["business_success"] is False
    assert result["activation_changed"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_run_id": "999"},
        {"expected_run_attempt": "2"},
        {"expected_sha": "c" * 40},
    ],
)
def test_success_rejects_wrong_artifact_provenance_before_db(tmp_path, changes):
    bridge = Bridge()
    with pytest.raises(ArtifactError, match="provenance"):
        ingest(bridge, artifact(tmp_path), **changes)
    assert bridge.calls == []


def test_success_rejects_health_secret_or_foreign_service_before_db(tmp_path):
    bridge = Bridge()
    path = artifact(tmp_path)
    content = json.loads(path.read_text())
    for field, value in (("secret", "must-not-pass"), ("service_id", "srv-other")):
        changed = copy.deepcopy(content)
        changed[observer_read.RENDER_PATH][0][field] = value
        path.write_text(json.dumps(changed))
        with pytest.raises(ArtifactError, match="evidence shape"):
            ingest(bridge, path)
    assert bridge.calls == []


def test_inputless_workflow_success_and_all_provider_path_are_disjoint():
    workflow = yaml.safe_load(Path(".github/workflows/dufynd-private-observer.yml").read_text())
    trigger = workflow.get("on", workflow.get(True))
    assert trigger["workflow_dispatch"]["inputs"]["mode"]["default"] == "render"
    jobs = workflow["jobs"]
    reader = next(step for step in jobs["read"]["steps"] if "observer_read" in step.get("run", ""))
    assert reader["env"]["DUFYND_OBSERVER_MODE"] == "${{ inputs.mode || 'render' }}"
    assert jobs["ingest"]["if"] == "inputs.mode == 'all'"
    assert (
        jobs["render-ingest"]["if"] == "inputs.mode != 'all' && inputs.mode != 'render_services_v2'"
    )
    assert jobs["render-ingest"]["needs"] == "read"
    assert jobs["ack"]["needs"] == "ingest" and jobs["finalize"]["needs"] == "ack"
    rendered = json.dumps(jobs["render-ingest"])
    assert "id-token" not in rendered and "observer_finalize" not in rendered
    assert "observer_ack" not in rendered and "begin_broker_acceptance" not in rendered
    assert "SUPABASE_SECRET_KEY" not in json.dumps(jobs["read"])
    artifact_name = next(
        step["with"]["name"]
        for step in jobs["read"]["steps"]
        if step.get("with", {}).get("path") == observer_read.RENDER_SUCCESS_FILE
    )
    download = next(
        step["run"]
        for step in jobs["render-ingest"]["steps"]
        if "gh run download" in step.get("run", "")
    )
    for attempt in ("1", "2"):
        produced = artifact_name.replace("${{ github.run_id }}", "123").replace(
            "${{ github.run_attempt }}", attempt
        )
        args = shlex.split(
            download.replace("${GITHUB_RUN_ID}", "123").replace("${GITHUB_RUN_ATTEMPT}", attempt)
        )
        assert args[args.index("--name") + 1] == produced
