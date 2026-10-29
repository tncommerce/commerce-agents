"""Fixed provenance contract for the DUFYND Private Observer handoff."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from scripts.dufynd_observer_credentials import CredentialMetadata, metadata

REPOSITORY = "tncommerce/commerce-agents"
REPOSITORY_ID = "1367576041"
REPOSITORY_OWNER_ID = "324597697"
REF = "refs/heads/scentai-mvp"
WORKFLOW_REF = (
    "tncommerce/commerce-agents/.github/workflows/"
    "dufynd-private-observer.yml@refs/heads/scentai-mvp"
)
EVENTS = frozenset({"workflow_dispatch", "schedule"})
SOURCE_KEYS = frozenset(
    {
        "version",
        "repository",
        "repository_id",
        "repository_owner_id",
        "ref",
        "workflow_ref",
        "event_name",
        "sha",
        "run_id",
        "run_attempt",
    }
)


class ProvenanceError(RuntimeError):
    pass


def validate_render_recovery_evidence(health: Any, render: Any) -> None:
    """Reject unexpected fields before a public-repository artifact is written.

    Reuse the broker's exact credential metadata contract. This accepts only
    references and bounded state, never provider secrets or Gmail messages.
    """

    def timestamp(value):
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > 40:
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed

    try:
        if not isinstance(health, dict) or set(health) != {"gmail", "render"}:
            raise ValueError
        for provider in ("gmail", "render"):
            raw = health[provider]
            if not isinstance(raw, dict) or set(raw) != set(metadata(provider).public()):
                raise ValueError
            values = dict(raw)
            for key in ("allowed_operations", "allowed_resources", "oauth_scopes"):
                if not isinstance(values[key], list):
                    raise ValueError
                values[key] = tuple(values[key])
            for key in (
                "expires_at",
                "refreshed_at",
                "revoked_at",
                "last_health_check",
                "rotation_due_at",
            ):
                values[key] = timestamp(values[key])
            if values["provider"] != provider or values["last_health_check"] is None:
                raise ValueError
            CredentialMetadata(**values).validate()
        if not isinstance(render, list) or not 1 <= len(render) <= 20:
            raise ValueError
        for deploy in render:
            if (
                not isinstance(deploy, dict)
                or set(deploy)
                != {"deployment_id", "service_id", "commit_sha", "status", "timestamps"}
                or deploy.get("service_id") != "srv-dakpfrnf3r2c73dr3f20"
                or not re.fullmatch(r"dep-[a-z0-9]+", str(deploy.get("deployment_id", "")))
                or not re.fullmatch(r"[a-f0-9]{40}", str(deploy.get("commit_sha", "")))
                or deploy.get("status")
                not in {
                    "live",
                    "created",
                    "queued",
                    "build_in_progress",
                    "update_in_progress",
                    "pre_deploy_in_progress",
                    "build_failed",
                    "update_failed",
                    "pre_deploy_failed",
                    "canceled",
                    "deactivated",
                }
                or not isinstance(deploy.get("timestamps"), dict)
                or set(deploy["timestamps"])
                != {"createdAt", "updatedAt", "startedAt", "finishedAt"}
            ):
                raise ValueError
            for value in deploy["timestamps"].values():
                timestamp(value)
    except Exception:
        raise ProvenanceError("render_recovery_evidence_mismatch") from None


def _digits(value: Any, *, maximum: int) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1," + str(maximum) + r"}", value):
        raise ProvenanceError("invalid_run_identity")
    return value


def validate_source(
    source: Any,
    *,
    expected_run_id: str | None = None,
    expected_sha: str | None = None,
    expected_run_attempt: str | None = None,
) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
        raise ProvenanceError("source_shape_mismatch")
    if source.get("version") != 1:
        raise ProvenanceError("source_version_mismatch")

    expected = {
        "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID,
        "repository_owner_id": REPOSITORY_OWNER_ID,
        "ref": REF,
        "workflow_ref": WORKFLOW_REF,
    }
    if any(source.get(key) != value for key, value in expected.items()):
        raise ProvenanceError("source_identity_mismatch")
    if source.get("event_name") not in EVENTS:
        raise ProvenanceError("source_event_mismatch")

    sha = source.get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ProvenanceError("source_sha_mismatch")
    run_id = _digits(source.get("run_id"), maximum=20)
    run_attempt = _digits(source.get("run_attempt"), maximum=4)

    if expected_run_id is not None and run_id != str(expected_run_id):
        raise ProvenanceError("source_run_mismatch")
    if expected_sha is not None and sha != str(expected_sha):
        raise ProvenanceError("source_sha_mismatch")
    if expected_run_attempt is not None and run_attempt != str(expected_run_attempt):
        raise ProvenanceError("source_run_attempt_mismatch")

    return {
        **source,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "sha": sha,
    }


def source_from_env(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    values = os.environ if env is None else env
    source = {
        "version": 1,
        "repository": values.get("GITHUB_REPOSITORY", ""),
        "repository_id": values.get("GITHUB_REPOSITORY_ID", ""),
        "repository_owner_id": values.get("GITHUB_REPOSITORY_OWNER_ID", ""),
        "ref": values.get("GITHUB_REF", ""),
        "workflow_ref": values.get("GITHUB_WORKFLOW_REF", ""),
        "event_name": values.get("GITHUB_EVENT_NAME", ""),
        "sha": values.get("GITHUB_SHA", ""),
        "run_id": values.get("GITHUB_RUN_ID", ""),
        "run_attempt": values.get("GITHUB_RUN_ATTEMPT", ""),
    }
    return validate_source(source)
