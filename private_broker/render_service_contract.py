"""Strict public-artifact contract for two independently observed Render services.

This versioned scope does not change the existing API-only credential metadata.
It contains no provider credentials, Gmail health or acceptance/cursor operations.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from private_broker.observer_contract import ProvenanceError, validate_source

VERSION = 2
SCOPE_ID = "render_services_v2"
SERVICE_IDS = ("srv-dakpfrnf3r2c73dr3f20", "srv-dakpiajl550s73cp4lvg")
SERVICE_SET = frozenset(SERVICE_IDS)
MAX_RESPONSE_BYTES = 65_536
MAX_ARTIFACT_BYTES = 262_144
ARTIFACT_FILE = "broker-render-services-v2.json"
ENVELOPE_KEYS = frozenset({"version", "scope_id", "service_id", "observed_at", "deployments"})
DEPLOYMENT_KEYS = frozenset({"deployment_id", "service_id", "commit_sha", "status", "timestamps"})
TIMESTAMP_KEYS = frozenset({"createdAt", "updatedAt", "startedAt", "finishedAt"})
DEPLOYMENT_STATES = frozenset(
    {
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
)
SAFE_FAILURES = frozenset(
    {
        "invalid_grant",
        "revoked",
        "missing_configuration",
        "scope_mismatch",
        "account_mismatch",
        "refresh_failed",
        "rate_limited",
        "provider_outage",
        "refresh_race",
        "invalid_response",
        "broker_activation_required",
        "transport_error",
    }
)
TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})"
)


class RenderServiceError(ValueError):
    """A bounded error code; raw provider or artifact contents never enter errors."""


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 40 or not TIMESTAMP_PATTERN.fullmatch(value):
        raise RenderServiceError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed
    except (ValueError, OverflowError):
        raise RenderServiceError("invalid_timestamp") from None


def strict_json(raw: bytes, *, limit: int) -> Any:
    """Bound size and reject duplicate keys, NaN/Infinity and non-UTF-8 input."""
    if not isinstance(raw, bytes) or len(raw) > limit:
        raise RenderServiceError("invalid_response")

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def constant(_):
        raise ValueError

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise RenderServiceError("invalid_response") from None


def valid_failure(reason: Any) -> bool:
    return isinstance(reason, str) and (
        reason in SAFE_FAILURES or re.fullmatch(r"http_[3-5][0-9]{2}", reason) is not None
    )


def validate_observation(value: Any, *, service_id: str) -> dict[str, Any]:
    """Each service must carry its own actual provider-read completion time."""
    if (
        service_id not in SERVICE_SET
        or not isinstance(value, dict)
        or set(value) != ENVELOPE_KEYS
        or type(value["version"]) is not int
        or value["version"] != VERSION
        or value["scope_id"] != SCOPE_ID
        or value["service_id"] != service_id
    ):
        raise RenderServiceError("invalid_observation")
    timestamp(value["observed_at"])
    deployments = value["deployments"]
    if not isinstance(deployments, list) or not 1 <= len(deployments) <= 20:
        raise RenderServiceError("invalid_observation")
    seen = set()
    for deployment in deployments:
        if (
            not isinstance(deployment, dict)
            or set(deployment) != DEPLOYMENT_KEYS
            or deployment["service_id"] != service_id
            or not isinstance(deployment["deployment_id"], str)
            or not re.fullmatch(r"dep-[a-z0-9]{1,100}", deployment["deployment_id"])
            or deployment["deployment_id"] in seen
            or not isinstance(deployment["commit_sha"], str)
            or not re.fullmatch(r"[a-f0-9]{40}", deployment["commit_sha"])
            or not isinstance(deployment["status"], str)
            or deployment["status"] not in DEPLOYMENT_STATES
            or not isinstance(deployment["timestamps"], dict)
            or set(deployment["timestamps"]) != TIMESTAMP_KEYS
        ):
            raise RenderServiceError("invalid_observation")
        seen.add(deployment["deployment_id"])
        for stamp in deployment["timestamps"].values():
            if stamp is not None:
                timestamp(stamp)
    return value


def validate_provenance(source: Any, **expected: str) -> dict[str, Any]:
    try:
        source = validate_source(source, **expected)
    except (ProvenanceError, TypeError, ValueError):
        raise RenderServiceError("invalid_source") from None
    if (
        type(source["version"]) is not int
        or not re.fullmatch(r"[1-9][0-9]{0,19}", source["run_id"])
        or not re.fullmatch(r"[1-9][0-9]{0,3}", source["run_attempt"])
    ):
        raise RenderServiceError("invalid_source")
    return source


def validate_artifact(payload: Any, **expected: str) -> dict[str, Any]:
    """Validate the entire two-service partition before any durable capture."""
    if (
        not isinstance(payload, dict)
        or set(payload) != {"_meta", "version", "services", "failures"}
        or type(payload["version"]) is not int
        or payload["version"] != VERSION
        or not isinstance(payload["services"], dict)
        or not isinstance(payload["failures"], dict)
    ):
        raise RenderServiceError("invalid_artifact")
    validate_provenance(payload["_meta"], **expected)
    successes, failures = set(payload["services"]), set(payload["failures"])
    if successes & failures or successes | failures != SERVICE_SET:
        raise RenderServiceError("invalid_service_partition")
    for service_id, observation in payload["services"].items():
        validate_observation(observation, service_id=service_id)
    if not all(valid_failure(reason) for reason in payload["failures"].values()):
        raise RenderServiceError("invalid_failure_reason")
    return payload
