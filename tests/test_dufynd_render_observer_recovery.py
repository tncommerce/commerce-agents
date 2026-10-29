"""Independent Render capture must never authorize Gmail or activation."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from scripts.dufynd_observer_credentials import metadata
from scripts.dufynd_private_observer_ingest import (
    HEALTH_PATH,
    RENDER_PATH,
    ArtifactError,
    ingest_render_recovery,
)

SOURCE = {
    "version": 1,
    "repository": "tncommerce/commerce-agents",
    "repository_id": "1367576041",
    "repository_owner_id": "324597697",
    "ref": "refs/heads/scentai-mvp",
    "workflow_ref": "tncommerce/commerce-agents/.github/workflows/dufynd-private-observer.yml@refs/heads/scentai-mvp",
    "event_name": "workflow_dispatch",
    "sha": "a" * 40,
    "run_id": "123456789",
    "run_attempt": "1",
}
DEPLOY = {
    "deployment_id": "dep-current",
    "service_id": "srv-dakpfrnf3r2c73dr3f20",
    "commit_sha": "b" * 40,
    "status": "live",
    "timestamps": {
        key: "2026-10-27T10:30:00Z" for key in ("createdAt", "updatedAt", "startedAt", "finishedAt")
    },
}


class Bridge:
    def __init__(self, *, active=True):
        self.calls = []
        self.active = active

    def capture_render_observer_read(self, **kwargs):
        self.calls.append(("capture", kwargs))
        return {
            "accepted": self.active,
            "reason": "blocked_configuration",
            "render_captures": 1,
            "gmail_captures": 0,
            "acks": 0,
            "activation_changed": False,
            "full_chain_complete": False,
            "business_success": False,
            "reused": False,
            "observed_at": kwargs["health"]["render"]["last_health_check"],
        }

    def begin_broker_acceptance(self, *args, **kwargs):
        raise AssertionError("recovery must not activate a provider")

    def capture_broker_acceptance_observation(self, *args, **kwargs):
        raise AssertionError("recovery must not use all-provider acceptance")


def artifact(tmp_path, **changes):
    payload = {
        "_meta": SOURCE,
        RENDER_PATH: [DEPLOY],
        HEALTH_PATH: {
            p: replace(
                metadata(p),
                status="revoked" if p == "gmail" else "healthy",
                last_health_check=datetime.now(UTC),
            ).public()
            for p in ("gmail", "render")
        },
        **changes,
    }
    path = tmp_path / "broker-render-observation.json"
    path.write_text(json.dumps(payload))
    return path


def recover(bridge, path, *, source=SOURCE, attempt="1"):
    return ingest_render_recovery(
        bridge,
        path,
        failure_source=source,
        expected_run_id=SOURCE["run_id"],
        expected_sha=SOURCE["sha"],
        expected_run_attempt=attempt,
    )


def test_render_is_captured_after_gmail_failure_without_ack_or_activation(tmp_path):
    bridge = Bridge()
    result = recover(bridge, artifact(tmp_path))
    assert result == {
        "render_captures": 1,
        "gmail_captures": 0,
        "acks": 0,
        "activation_changed": False,
        "full_chain_complete": False,
        "business_success": False,
        "observed_at": bridge.calls[0][1]["health"]["render"]["last_health_check"],
        "reused": False,
    }
    assert [call[0] for call in bridge.calls] == ["capture"]
    assert bridge.calls[0][1]["source"] == SOURCE
    assert bridge.calls[0][1]["evidence"] == [DEPLOY]


def test_initial_activation_cannot_be_bypassed_by_partial_recovery(tmp_path):
    bridge = Bridge(active=False)
    with pytest.raises(ArtifactError, match="blocked_configuration"):
        recover(bridge, artifact(tmp_path))


def test_both_artifacts_from_previous_attempt_cannot_be_replayed(tmp_path):
    bridge = Bridge()
    with pytest.raises(ArtifactError, match="provenance"):
        recover(bridge, artifact(tmp_path), source=SOURCE, attempt="2")
    assert bridge.calls == []
    from scripts.dufynd_private_observer_failure import validate_failure

    with pytest.raises(ValueError, match="attempt mismatch"):
        validate_failure(
            {"_meta": SOURCE, "stage": "gmail_1", "reason": "revoked"},
            run_id=SOURCE["run_id"],
            sha=SOURCE["sha"],
            run_attempt="2",
        )


@pytest.mark.parametrize(
    "source_change",
    [
        {"run_id": "999"},
        {"sha": "c" * 40},
        {"repository_id": "999"},
        {"ref": "refs/heads/main"},
        {"run_attempt": "2"},
    ],
)
def test_replayed_foreign_or_other_attempt_evidence_is_rejected_before_writes(
    tmp_path, source_change
):
    bridge = Bridge()
    with pytest.raises(ArtifactError, match="provenance"):
        recover(bridge, artifact(tmp_path, _meta={**SOURCE, **source_change}))
    assert bridge.calls == []


@pytest.mark.parametrize(
    "changes",
    [
        {RENDER_PATH: []},
        {RENDER_PATH: [{**DEPLOY, "service_id": "srv-foreign"}]},
        {RENDER_PATH: [{**DEPLOY, "commit_sha": "not-a-sha"}]},
        {RENDER_PATH: [{**DEPLOY, "secret": "must-not-pass"}]},
        {RENDER_PATH: [{**DEPLOY, "status": "invented"}]},
        {"/v1/gmail/threads/1a0f385ed98c6af8/metadata": {"messages": []}},
        {HEALTH_PATH: []},
    ],
)
def test_unbounded_or_wrong_provider_evidence_is_rejected_before_writes(tmp_path, changes):
    bridge = Bridge()
    with pytest.raises(ArtifactError):
        recover(bridge, artifact(tmp_path, **changes))
    assert bridge.calls == []


def test_incomplete_atomic_receipt_is_not_reported_as_success(tmp_path):
    bridge = Bridge()
    bridge.capture_render_observer_read = lambda **kwargs: {"accepted": True}
    with pytest.raises(ArtifactError, match="receipt mismatch"):
        recover(bridge, artifact(tmp_path))
    assert bridge.calls == []
