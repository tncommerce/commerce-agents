"""OIDC-only acknowledgment harness for DUFYND Private Observer Gmail cursors.

The input is the bounded ack plan emitted only after trusted Supabase ingestion.
This process intentionally has no Supabase, provider, owner or management credential.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from private_broker.observer_contract import ProvenanceError, validate_source

MAX_ACK_PLAN_BYTES = 16_384
THREADS = (
    "1a0f385ed98c6af8",
    "1a0f69c169fb928f",
    "1a0f6a90772a743d",
)


class AckFailure(Exception):
    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}:{reason}")


def _json(response: httpx.Response, stage: str) -> dict:
    if not 200 <= response.status_code < 300:
        raise AckFailure(stage, f"http_{response.status_code}")
    try:
        payload = response.json()
    except Exception:
        raise AckFailure(stage, "invalid_json") from None
    if not isinstance(payload, dict):
        raise AckFailure(stage, "invalid_json")
    return payload


def load_ack_plan(
    path: Path,
    *,
    expected_run_id: str,
    expected_sha: str,
) -> list[tuple[str, str]]:
    try:
        if path.stat().st_size > MAX_ACK_PLAN_BYTES:
            raise AckFailure("plan", "size_limit")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except AckFailure:
        raise
    except Exception:
        raise AckFailure("plan", "unreadable") from None

    if not isinstance(payload, dict) or set(payload) != {"version", "source", "acks"}:
        raise AckFailure("plan", "shape_mismatch")
    if payload.get("version") != 2 or not isinstance(payload.get("acks"), list):
        raise AckFailure("plan", "version_mismatch")
    try:
        validate_source(
            payload.get("source"),
            expected_run_id=expected_run_id,
            expected_sha=expected_sha,
        )
    except ProvenanceError as exc:
        raise AckFailure("plan", f"provenance_{exc}") from None
    if len(payload["acks"]) != len(THREADS):
        raise AckFailure("plan", "thread_set_mismatch")

    by_thread: dict[str, str] = {}
    for item in payload["acks"]:
        if not isinstance(item, dict) or set(item) != {"thread_id", "observation_id"}:
            raise AckFailure("plan", "ack_shape_mismatch")
        thread_id = item.get("thread_id")
        digest = item.get("observation_id")
        if (
            thread_id not in THREADS
            or thread_id in by_thread
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise AckFailure("plan", "ack_value_mismatch")
        by_thread[thread_id] = digest

    if set(by_thread) != set(THREADS):
        raise AckFailure("plan", "thread_set_mismatch")
    return [(thread_id, by_thread[thread_id]) for thread_id in THREADS]


def acknowledge(
    origin: str,
    ack_plan_path: Path,
    *,
    expected_run_id: str | None = None,
    expected_sha: str | None = None,
    client_factory=httpx.Client,
) -> dict[str, int]:
    url = urlsplit(origin)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.path
        or url.query
        or url.fragment
        or url.username
        or url.port not in {None, 443}
    ):
        raise AckFailure("origin", "invalid")

    run_id = expected_run_id or os.getenv("GITHUB_RUN_ID")
    sha = expected_sha or os.getenv("GITHUB_SHA")
    if not run_id or not sha:
        raise AckFailure("plan", "provenance_required")
    acks = load_ack_plan(
        ack_plan_path,
        expected_run_id=run_id,
        expected_sha=sha,
    )
    with client_factory(trust_env=False, timeout=30, follow_redirects=False) as client:
        identity = client.get(
            os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"],
            params={"audience": origin},
            headers={"Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
        )
        identity_payload = _json(identity, "oidc_identity")
        token = identity_payload.get("value")
        if not isinstance(token, str) or not token:
            raise AckFailure("oidc_identity", "invalid_response")
        headers = {"Authorization": "Bearer " + token}

        acknowledged = 0
        duplicate_first_pass = 0
        for thread_id, digest in acks:
            response = client.post(
                f"{origin}/v1/gmail/threads/{thread_id}/ack/{digest}",
                headers=headers,
            )
            result = _json(response, f"ack:{thread_id}")
            if set(result) != {"status"} or result.get("status") not in {
                "acknowledged",
                "duplicate",
            }:
                raise AckFailure(f"ack:{thread_id}", "invalid_response")
            if result["status"] == "acknowledged":
                acknowledged += 1
            else:
                duplicate_first_pass += 1

        # A second pass must be idempotent. This also makes a partially completed
        # previous workflow run safely recoverable: first-pass duplicates are valid.
        for thread_id, digest in acks:
            response = client.post(
                f"{origin}/v1/gmail/threads/{thread_id}/ack/{digest}",
                headers=headers,
            )
            result = _json(response, f"ack_repeat:{thread_id}")
            if set(result) != {"status"} or result.get("status") != "duplicate":
                raise AckFailure(f"ack_repeat:{thread_id}", "not_idempotent")

    return {
        "acknowledged": acknowledged,
        "duplicate_first_pass": duplicate_first_pass,
        "idempotent_rechecks": len(acks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Acknowledge one fixed DUFYND broker ack plan.")
    parser.add_argument("--ack-plan", type=Path, default=Path("broker-acks.json"))
    args = parser.parse_args()
    origin = os.environ.get("BROKER_ORIGIN", "")

    try:
        summary = acknowledge(origin, args.ack_plan)
    except AckFailure as exc:
        raise SystemExit(f"private observer ack failed at {exc.stage}:{exc.reason}") from None
    except Exception:
        raise SystemExit("private observer ack failed at internal") from None

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
