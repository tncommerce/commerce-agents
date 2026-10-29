"""Offline recovery proof: a prior attempt cannot capture, ACK or finalize."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

import pytest
import yaml
from private_broker import observer_ack
from scripts import dufynd_private_observer_finalize as finalizer
from scripts import dufynd_private_observer_ingest as ingester
from tests.test_dufynd_private_observer_finalize import FakeBridge as FinalizeBridge
from tests.test_dufynd_private_observer_finalize import receipt
from tests.test_dufynd_private_observer_ingest import FakeBridge as IngestBridge
from tests.test_dufynd_private_observer_ingest import artifact
from tests.test_private_broker_observer_ack import FakeClient, FakeResponse, write_plan

EXPECTED = {
    "expected_run_id": "123456789",
    "expected_sha": "a" * 40,
    "expected_run_attempt": "2",
}


@pytest.mark.parametrize("other_attempt", ["1", "3"])
def test_old_or_foreign_attempt_never_reaches_capture(tmp_path, other_attempt):
    payload = artifact()
    payload["_meta"]["run_attempt"] = other_attempt
    read = tmp_path / "read.json"
    read.write_text(json.dumps(payload))
    plan = tmp_path / "plan.json"
    bridge = IngestBridge()
    with pytest.raises(ingester.ArtifactError, match="source_run_attempt_mismatch"):
        ingester.ingest_artifact(bridge, read, plan, **EXPECTED)
    assert bridge.health_calls == []
    assert bridge.capture_calls == []
    assert not plan.exists()


@pytest.mark.parametrize("other_attempt", ["1", "3"])
def test_old_or_foreign_attempt_never_reaches_oidc_or_ack(tmp_path, other_attempt):
    plan = tmp_path / "plan.json"
    write_plan(plan)
    payload = json.loads(plan.read_text())
    payload["source"]["run_attempt"] = other_attempt
    plan.write_text(json.dumps(payload))

    def forbidden_client(**kwargs):
        raise AssertionError("OIDC and ACK must not be reached")

    with pytest.raises(observer_ack.AckFailure, match="source_run_attempt_mismatch"):
        observer_ack.acknowledge(
            "https://broker.example", plan, client_factory=forbidden_client, **EXPECTED
        )
    result = tmp_path / "receipt.json"
    with pytest.raises(observer_ack.AckFailure, match="source_run_attempt_mismatch"):
        observer_ack.write_receipt(plan, result, receipt()["ack_summary"], **EXPECTED)
    assert not result.exists()


@pytest.mark.parametrize("other_attempt", ["1", "3"])
def test_old_or_foreign_attempt_never_reaches_finalization(tmp_path, other_attempt):
    payload = receipt()
    payload["source"]["run_attempt"] = other_attempt
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(payload))
    bridge = FinalizeBridge()
    with pytest.raises(finalizer.FinalizeError, match="source_run_attempt_mismatch"):
        finalizer.finalize(bridge, path, **EXPECTED)
    assert bridge.calls == []
    assert bridge.reconciled == 0


def test_current_attempt_complete_chain_keeps_provenance_and_idempotent_ack(monkeypatch, tmp_path):
    """Exercise all handoffs with fakes, including the successful second attempt."""
    monkeypatch.setenv("GITHUB_RUN_ID", EXPECTED["expected_run_id"])
    monkeypatch.setenv("GITHUB_SHA", EXPECTED["expected_sha"])
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", EXPECTED["expected_run_attempt"])
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://oidc.example/token")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "fake-request-token")
    payload = artifact()
    payload["_meta"]["run_attempt"] = "2"
    read, plan, result = (tmp_path / name for name in ("read.json", "plan.json", "receipt.json"))
    read.write_text(json.dumps(payload))
    ingest_bridge = IngestBridge()
    captured = ingester.ingest_artifact(ingest_bridge, read, plan, **EXPECTED)
    assert captured["captures"] == 4
    client = FakeClient(
        posts=[
            *[FakeResponse(200, {"status": "acknowledged"}) for _ in range(3)],
            *[FakeResponse(200, {"status": "duplicate"}) for _ in range(3)],
        ]
    )
    summary = observer_ack.acknowledge(
        "https://broker.example", plan, client_factory=lambda **kwargs: client
    )
    observer_ack.write_receipt(plan, result, summary, **EXPECTED)
    assert json.loads(result.read_text())["source"] == payload["_meta"]
    finalize_bridge = FinalizeBridge()
    assert finalizer.finalize(finalize_bridge, result, **EXPECTED)["accepted"] is True
    assert len(ingest_bridge.health_calls) == 1
    assert len(ingest_bridge.capture_calls) == 4
    assert len(client.get_calls) == 1 and len(client.post_calls) == 6
    assert len(finalize_bridge.calls) == 1 and finalize_bridge.reconciled == 1


def test_ack_requires_current_attempt_before_any_network(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    with pytest.raises(observer_ack.AckFailure, match="provenance_required"):
        observer_ack.acknowledge(
            "https://broker.example",
            tmp_path / "unread-plan.json",
            expected_run_id=EXPECTED["expected_run_id"],
            expected_sha=EXPECTED["expected_sha"],
            client_factory=lambda **kwargs: pytest.fail("network must not be reached"),
        )


@pytest.mark.parametrize("module", [ingester, finalizer])
def test_control_plane_cli_requires_attempt_before_creating_bridge(monkeypatch, module):
    monkeypatch.setenv("GITHUB_RUN_ID", EXPECTED["expected_run_id"])
    monkeypatch.setenv("GITHUB_SHA", EXPECTED["expected_sha"])
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    monkeypatch.setattr("sys.argv", ["observer-stage"])
    monkeypatch.setattr(module, "DufyndJarvisBridge", lambda: pytest.fail("bridge must not exist"))
    with pytest.raises(SystemExit, match="provenance is required"):
        module.main()


@pytest.mark.parametrize(
    "producer,consumer,path",
    [
        ("read", "ingest", "broker-observations.json"),
        ("ingest", "ack", "broker-acks.json"),
        ("ack", "finalize", "broker-ack-receipt.json"),
    ],
)
def test_workflow_producer_and_consumer_select_same_unique_attempt(producer, consumer, path):
    workflow = yaml.safe_load(Path(".github/workflows/dufynd-private-observer.yml").read_text())
    produced = next(
        step["with"]["name"]
        for step in workflow["jobs"][producer]["steps"]
        if step.get("with", {}).get("path") == path
    )
    downloaded = next(
        step["run"]
        for step in workflow["jobs"][consumer]["steps"]
        if "gh run download" in step.get("run", "")
    )
    names = []
    for attempt in ("1", "2"):
        upload_name = produced.replace("${{ github.run_id }}", "123456789").replace(
            "${{ github.run_attempt }}", attempt
        )
        command = downloaded.replace("${GITHUB_RUN_ID}", "123456789").replace(
            "${GITHUB_RUN_ATTEMPT}", attempt
        )
        args = shlex.split(command)
        assert args[args.index("--name") + 1] == upload_name
        names.append(upload_name)
    assert names[0] != names[1]
