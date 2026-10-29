"""Explicit v2 capture of independently validated API and Storefront observations."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

from private_broker.render_service_contract import (
    ARTIFACT_FILE,
    MAX_ARTIFACT_BYTES,
    SCOPE_ID,
    SERVICE_IDS,
    RenderServiceError,
    strict_json,
    timestamp,
    validate_artifact,
    validate_provenance,
)
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

RECEIPT_KEYS = frozenset(
    {
        "version",
        "mode",
        "scope_id",
        "source",
        "service_id",
        "observer_id",
        "observed_at",
        "captured_at",
        "evidence_sha256",
        "accepted",
        "reused",
        "render_captures",
        "gmail_captures",
        "acks",
        "activation_changed",
        "business_success",
        "full_chain_complete",
    }
)
REJECTION_REASONS = frozenset(
    {
        "invalid_render_source",
        "invalid_render_observation",
        "blocked_configuration",
        "render_scope_unverified",
        "render_receipt_invalid",
        "render_receipt_conflict",
        "superseded_render_observation",
        "stale_render_observation",
    }
)


class ControlPlane(Protocol):
    def capture_render_service_read(
        self, *, source: dict[str, Any], observation: dict[str, Any]
    ) -> dict[str, Any]: ...


def load_artifact(path: Path, **expected: str) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_ARTIFACT_BYTES + 1)
        return validate_artifact(strict_json(raw, limit=MAX_ARTIFACT_BYTES), **expected)
    except RenderServiceError:
        raise
    except Exception:
        raise RenderServiceError("artifact_unreadable") from None


def validate_receipt(
    value: Any, *, source: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    service_id = observation["service_id"]
    if (
        not isinstance(value, dict)
        or set(value) != RECEIPT_KEYS
        or type(value["version"]) is not int
        or value["version"] != 2
        or value["mode"] != SCOPE_ID
        or value["scope_id"] != SCOPE_ID
        or value["source"] != source
        or value["service_id"] != service_id
        or value["observer_id"] != "render:" + service_id
        or value["accepted"] is not True
        or type(value["reused"]) is not bool
        or type(value["render_captures"]) is not int
        or value["render_captures"] != (0 if value["reused"] else 1)
        or type(value["gmail_captures"]) is not int
        or value["gmail_captures"] != 0
        or type(value["acks"]) is not int
        or value["acks"] != 0
        or value["activation_changed"] is not False
        or value["business_success"] is not False
        or value["full_chain_complete"] is not False
        or not isinstance(value["evidence_sha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", value["evidence_sha256"])
    ):
        raise RenderServiceError("invalid_capture_receipt")
    validate_provenance(value["source"])
    observed = timestamp(value["observed_at"])
    if (
        observed != timestamp(observation["observed_at"])
        or timestamp(value["captured_at"]) < observed
    ):
        raise RenderServiceError("invalid_capture_receipt")
    return value


def ingest_artifact(
    bridge: ControlPlane,
    artifact_path: Path,
    *,
    expected_run_id: str,
    expected_sha: str,
    expected_run_attempt: str,
) -> dict[str, Any]:
    """No DB write until the complete source and both-service partition validate.

    Each authorized service capture is atomic in SQL. A rejection or transport
    error for one service does not erase a durably captured independent peer.
    """
    artifact = load_artifact(
        artifact_path,
        expected_run_id=expected_run_id,
        expected_sha=expected_sha,
        expected_run_attempt=expected_run_attempt,
    )
    receipts = {}
    failures = dict(artifact["failures"])
    for service_id in SERVICE_IDS:
        if service_id not in artifact["services"]:
            continue
        observation = artifact["services"][service_id]
        try:
            result = bridge.capture_render_service_read(
                source=artifact["_meta"], observation=observation
            )
        except Exception:
            failures[service_id] = "capture_failed"
            continue
        if isinstance(result, dict) and result.get("accepted") is False:
            reason = result.get("reason")
            failures[service_id] = (
                reason
                if set(result) == {"accepted", "reason"}
                and isinstance(reason, str)
                and reason in REJECTION_REASONS
                else "invalid_capture_receipt"
            )
            continue
        try:
            receipts[service_id] = validate_receipt(
                result, source=artifact["_meta"], observation=observation
            )
        except Exception:
            failures[service_id] = "invalid_capture_receipt"
    return {
        "version": 2,
        "scope_id": SCOPE_ID,
        "receipts": receipts,
        "failures": failures,
        "render_captures": sum(r["render_captures"] for r in receipts.values()),
        "all_requested_services_captured": len(receipts) == len(SERVICE_IDS) and not failures,
        "gmail_captures": 0,
        "acks": 0,
        "activation_changed": False,
        "business_success": False,
        "full_chain_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path(ARTIFACT_FILE))
    parser.add_argument("--expected-run-id", default=os.getenv("GITHUB_RUN_ID"))
    parser.add_argument("--expected-sha", default=os.getenv("GITHUB_SHA"))
    parser.add_argument("--expected-run-attempt", default=os.getenv("GITHUB_RUN_ATTEMPT"))
    args = parser.parse_args()
    if not args.expected_run_id or not args.expected_sha or not args.expected_run_attempt:
        raise SystemExit("render services v2 ingest requires exact workflow provenance")
    try:
        result = ingest_artifact(
            DufyndJarvisBridge(),
            args.artifact,
            expected_run_id=args.expected_run_id,
            expected_sha=args.expected_sha,
            expected_run_attempt=args.expected_run_attempt,
        )
    except Exception:
        raise SystemExit("render services v2 ingest rejected artifact or configuration") from None
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["all_requested_services_captured"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
