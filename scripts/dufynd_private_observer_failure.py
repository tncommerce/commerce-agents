"""Persist a bounded failure receipt without provider credentials or cursor changes."""

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from private_broker.observer_contract import validate_source
from private_broker.observer_read import SAFE_REASONS
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_private_observer_ingest import ingest_render_recovery


def validate_failure(payload, *, run_id, sha, run_attempt=None):
    if not isinstance(payload, dict) or set(payload) != {"_meta", "stage", "reason"}:
        raise ValueError("invalid failure shape")
    source = validate_source(payload["_meta"], expected_run_id=run_id, expected_sha=sha)
    if run_attempt is not None and source["run_attempt"] != str(run_attempt):
        raise ValueError("failure provenance attempt mismatch")
    if payload["stage"] not in {
        "render",
        "gmail_1",
        "gmail_2",
        "gmail_3",
        "health",
        "gmail_1_repeat",
        "gmail_2_repeat",
        "gmail_3_repeat",
    }:
        raise ValueError("invalid failure stage")
    reason = payload["reason"]
    if not isinstance(reason, str) or not (
        reason in SAFE_REASONS
        or re.fullmatch(r"http_[1-5][0-9]{2}", reason)
        or reason == "invalid_json"
    ):
        raise ValueError("invalid failure reason")
    return {**payload, "_meta": source}


def main():
    path = Path("failure-artifact/broker-failure.json")
    if path.stat().st_size > 4096:
        raise ValueError("failure receipt too large")
    payload = validate_failure(
        json.loads(path.read_text()),
        run_id=os.environ["GITHUB_RUN_ID"],
        sha=os.environ["GITHUB_SHA"],
        run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
    )
    bridge = DufyndJarvisBridge()
    bridge.upsert_master_status(
        key="ops.private_observer.last_failure",
        category="ops",
        value=payload,
        last_verified_at=datetime.now(UTC).isoformat(),
    )
    recovery_path = path.with_name("broker-render-observation.json")
    summary = {"recorded": True, "stage": payload["stage"], "reason": payload["reason"]}
    if recovery_path.exists() and payload["stage"].startswith("gmail_"):
        recovery = ingest_render_recovery(
            bridge,
            recovery_path,
            failure_source=payload["_meta"],
            expected_run_id=os.environ["GITHUB_RUN_ID"],
            expected_sha=os.environ["GITHUB_SHA"],
            expected_run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
        )
        bridge.upsert_master_status(
            key="ops.private_observer.render_recovery",
            category="ops",
            value={"source": payload["_meta"], **recovery},
            last_verified_at=datetime.now(UTC).isoformat(),
        )
        summary["render_recovery"] = recovery
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
