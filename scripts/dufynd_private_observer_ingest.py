"""Trusted control-plane ingestion for a fixed DUFYND Private Observer artifact.

This process may hold the existing Supabase service-role credential, but never a
provider credential or broker owner key. It validates one bounded filtered artifact,
projects non-secret health, commits fixed observations through existing RPCs, and
emits only the Gmail digests that are safe to acknowledge after durable capture.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Protocol

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

MAX_ARTIFACT_BYTES = 262_144
HEALTH_PATH = "/v1/health"
RENDER_PATH = "/v1/render/services/srv-dakpfrnf3r2c73dr3f20/deployments"
GMAIL_PATHS = {
    "/v1/gmail/threads/1a0f385ed98c6af8/metadata": "1a0f385ed98c6af8",
    "/v1/gmail/threads/1a0f69c169fb928f/metadata": "1a0f69c169fb928f",
    "/v1/gmail/threads/1a0f6a90772a743d/metadata": "1a0f6a90772a743d",
}
EXPECTED_PATHS = frozenset({HEALTH_PATH, RENDER_PATH, *GMAIL_PATHS})
GMAIL_RESPONSE_KEYS = frozenset({"observation_id", "evidence"})
GMAIL_EVIDENCE_KEYS = frozenset({"thread_id", "history_id", "messages"})
GMAIL_MESSAGE_KEYS = frozenset(
    {
        "message_id",
        "thread_id",
        "internal_date",
        "sender",
        "delivery_failure",
        "content_type",
    }
)
CAPTURE_MESSAGE_KEYS = (
    "message_id",
    "thread_id",
    "internal_date",
    "sender",
    "delivery_failure",
)


class ControlPlane(Protocol):
    def project_broker_health(self, health: dict[str, Any]) -> dict[str, Any]: ...

    def capture_broker_observation(
        self,
        *,
        credential_id: str,
        observer_id: str,
        evidence: Any,
    ) -> dict[str, Any]: ...


class ArtifactError(RuntimeError):
    pass


def load_artifact(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ArtifactError("observer artifact exceeds size limit")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ArtifactError:
        raise
    except Exception:
        raise ArtifactError("observer artifact is unreadable") from None

    if not isinstance(payload, dict) or set(payload) != EXPECTED_PATHS:
        raise ArtifactError("observer artifact path set mismatch")
    return payload


def _sanitize_gmail(path: str, raw: Any) -> tuple[str, dict[str, Any]]:
    thread_id = GMAIL_PATHS[path]
    if not isinstance(raw, dict) or set(raw) != GMAIL_RESPONSE_KEYS:
        raise ArtifactError("gmail observation shape mismatch")

    digest = raw.get("observation_id")
    evidence = raw.get("evidence")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ArtifactError("gmail observation digest mismatch")
    if not isinstance(evidence, dict) or set(evidence) != GMAIL_EVIDENCE_KEYS:
        raise ArtifactError("gmail evidence shape mismatch")
    if evidence.get("thread_id") != thread_id:
        raise ArtifactError("gmail thread mismatch")
    if not re.fullmatch(r"[0-9]{1,30}", str(evidence.get("history_id", ""))):
        raise ArtifactError("gmail history id mismatch")

    messages = evidence.get("messages")
    if not isinstance(messages, list) or len(messages) > 100:
        raise ArtifactError("gmail message list mismatch")

    sanitized_messages = []
    for message in messages:
        if not isinstance(message, dict) or not set(message).issubset(GMAIL_MESSAGE_KEYS):
            raise ArtifactError("gmail message shape mismatch")
        if not set(CAPTURE_MESSAGE_KEYS).issubset(message):
            raise ArtifactError("gmail message fields missing")
        if message.get("thread_id") != thread_id:
            raise ArtifactError("gmail message thread mismatch")
        sanitized_messages.append({key: message[key] for key in CAPTURE_MESSAGE_KEYS})

    return digest, {
        "thread_id": thread_id,
        "history_id": str(evidence["history_id"]),
        "messages": sanitized_messages,
    }


def _accepted(result: Any, stage: str) -> None:
    if not isinstance(result, dict) or result.get("accepted") is not True:
        reason = result.get("reason") if isinstance(result, dict) else None
        if reason not in {"blocked_configuration", "unknown_observer"}:
            reason = "rejected"
        raise ArtifactError(f"{stage} capture {reason}")


def ingest_artifact(
    bridge: ControlPlane,
    artifact_path: Path,
    ack_plan_path: Path,
) -> dict[str, int]:
    artifact = load_artifact(artifact_path)

    health = artifact[HEALTH_PATH]
    if not isinstance(health, dict):
        raise ArtifactError("broker health shape mismatch")
    projection = bridge.project_broker_health(health)
    if (
        projection.get("projected") != 2
        or projection.get("activation_changed") is not False
    ):
        raise ArtifactError("broker health projection mismatch")

    render = artifact[RENDER_PATH]
    if not isinstance(render, list) or len(render) > 20:
        raise ArtifactError("render evidence shape mismatch")
    _accepted(
        bridge.capture_broker_observation(
            credential_id="render_deploy_broker",
            observer_id="render:srv-dakpfrnf3r2c73dr3f20",
            evidence=render,
        ),
        "render",
    )

    acks = []
    for path, thread_id in GMAIL_PATHS.items():
        digest, evidence = _sanitize_gmail(path, artifact[path])
        _accepted(
            bridge.capture_broker_observation(
                credential_id="gmail_known_threads",
                observer_id=f"gmail:{thread_id}",
                evidence=evidence,
            ),
            f"gmail:{thread_id}",
        )
        acks.append({"thread_id": thread_id, "observation_id": digest})

    ack_plan = {"version": 1, "acks": acks}
    temporary = ack_plan_path.with_name(ack_plan_path.name + ".tmp")
    temporary.write_text(
        json.dumps(ack_plan, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(ack_plan_path)
    return {"health_projected": 2, "captures": 4, "acks": len(acks)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest one fixed DUFYND Private Observer artifact.")
    parser.add_argument("--artifact", type=Path, default=Path("broker-observations.json"))
    parser.add_argument("--ack-plan", type=Path, default=Path("broker-acks.json"))
    args = parser.parse_args()

    try:
        summary = ingest_artifact(DufyndJarvisBridge(), args.artifact, args.ack_plan)
    except ArtifactError as exc:
        raise SystemExit(f"private observer ingest failed: {exc}") from None

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
