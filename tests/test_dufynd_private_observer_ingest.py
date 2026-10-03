from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.dufynd_private_observer_ingest import (
    ArtifactError,
    GMAIL_PATHS,
    HEALTH_PATH,
    RENDER_PATH,
    ingest_artifact,
)


class FakeBridge:
    def __init__(self, *, reject_observer: str | None = None):
        self.reject_observer = reject_observer
        self.health_calls: list[dict[str, Any]] = []
        self.capture_calls: list[dict[str, Any]] = []

    def project_broker_health(self, health: dict[str, Any]) -> dict[str, Any]:
        self.health_calls.append(health)
        return {"projected": 2, "activation_changed": False}

    def capture_broker_observation(
        self,
        *,
        credential_id: str,
        observer_id: str,
        evidence: Any,
    ) -> dict[str, Any]:
        self.capture_calls.append(
            {
                "credential_id": credential_id,
                "observer_id": observer_id,
                "evidence": evidence,
            }
        )
        if observer_id == self.reject_observer:
            return {"accepted": False, "reason": "blocked_configuration"}
        return {"accepted": True, "inserted": 1}


def observation(thread_id: str, digest: str) -> dict[str, Any]:
    return {
        "observation_id": digest,
        "evidence": {
            "thread_id": thread_id,
            "history_id": "74042",
            "messages": [
                {
                    "message_id": "1a0f1234",
                    "thread_id": thread_id,
                    "internal_date": "1791012345000",
                    "sender": "brand@example.com",
                    "content_type": "text/plain",
                    "delivery_failure": False,
                }
            ],
        },
    }


def artifact() -> dict[str, Any]:
    result: dict[str, Any] = {
        HEALTH_PATH: {
            "gmail": {"status": "healthy"},
            "render": {"status": "healthy"},
        },
        RENDER_PATH: [
            {
                "deployment_id": "dep-test",
                "service_id": "srv-dakpfrnf3r2c73dr3f20",
                "commit_sha": "a" * 40,
                "status": "live",
                "timestamps": {},
            }
        ],
    }
    for index, (path, thread_id) in enumerate(GMAIL_PATHS.items(), start=1):
        result[path] = observation(thread_id, f"{index:x}" * 64)
    return result


def write_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ingest_writes_ack_plan_only_after_all_durable_captures(tmp_path: Path) -> None:
    artifact_path = tmp_path / "broker-observations.json"
    ack_path = tmp_path / "broker-acks.json"
    write_artifact(artifact_path, artifact())
    bridge = FakeBridge()

    summary = ingest_artifact(bridge, artifact_path, ack_path)

    assert summary == {"health_projected": 2, "captures": 4, "acks": 3}
    assert len(bridge.health_calls) == 1
    assert len(bridge.capture_calls) == 4

    gmail_calls = [
        call for call in bridge.capture_calls if call["credential_id"] == "gmail_known_threads"
    ]
    assert len(gmail_calls) == 3
    for call in gmail_calls:
        message = call["evidence"]["messages"][0]
        assert set(message) == {
            "message_id",
            "thread_id",
            "internal_date",
            "sender",
            "delivery_failure",
        }
        assert "content_type" not in message

    ack_plan = json.loads(ack_path.read_text(encoding="utf-8"))
    assert ack_plan["version"] == 1
    assert [item["thread_id"] for item in ack_plan["acks"]] == list(GMAIL_PATHS.values())
    assert all(len(item["observation_id"]) == 64 for item in ack_plan["acks"])


def test_ingest_rejects_unknown_artifact_path_before_control_plane_write(tmp_path: Path) -> None:
    artifact_path = tmp_path / "broker-observations.json"
    ack_path = tmp_path / "broker-acks.json"
    payload = artifact()
    payload["/v1/unexpected"] = {}
    write_artifact(artifact_path, payload)
    bridge = FakeBridge()

    with pytest.raises(ArtifactError, match="path set mismatch"):
        ingest_artifact(bridge, artifact_path, ack_path)

    assert bridge.health_calls == []
    assert bridge.capture_calls == []
    assert not ack_path.exists()


def test_ingest_rejects_bad_observation_digest_before_capture(tmp_path: Path) -> None:
    artifact_path = tmp_path / "broker-observations.json"
    ack_path = tmp_path / "broker-acks.json"
    payload = artifact()
    first_path = next(iter(GMAIL_PATHS))
    payload[first_path]["observation_id"] = "not-a-digest"
    write_artifact(artifact_path, payload)
    bridge = FakeBridge()

    with pytest.raises(ArtifactError, match="digest mismatch"):
        ingest_artifact(bridge, artifact_path, ack_path)

    assert len(bridge.health_calls) == 1
    assert len(bridge.capture_calls) == 1
    assert bridge.capture_calls[0]["credential_id"] == "render_deploy_broker"
    assert not ack_path.exists()


def test_ingest_never_writes_ack_plan_after_rejected_capture(tmp_path: Path) -> None:
    artifact_path = tmp_path / "broker-observations.json"
    ack_path = tmp_path / "broker-acks.json"
    write_artifact(artifact_path, artifact())
    rejected = f"gmail:{next(iter(GMAIL_PATHS.values()))}"
    bridge = FakeBridge(reject_observer=rejected)

    with pytest.raises(ArtifactError, match="blocked_configuration"):
        ingest_artifact(bridge, artifact_path, ack_path)

    assert not ack_path.exists()
