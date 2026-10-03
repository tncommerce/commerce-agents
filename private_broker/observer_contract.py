"""Fixed provenance contract for the DUFYND Private Observer handoff."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

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


def _digits(value: Any, *, maximum: int) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1," + str(maximum) + r"}", value):
        raise ProvenanceError("invalid_run_identity")
    return value


def validate_source(
    source: Any,
    *,
    expected_run_id: str | None = None,
    expected_sha: str | None = None,
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
