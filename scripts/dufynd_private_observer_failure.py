"""Persist a bounded failure receipt without provider credentials or cursor changes."""

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from private_broker.observer_contract import validate_source
from private_broker.observer_read import SAFE_REASONS
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge


def validate_failure(payload, *, run_id, sha):
    if not isinstance(payload, dict) or set(payload) != {"_meta", "stage", "reason"}:
        raise ValueError("invalid failure shape")
    source = validate_source(payload["_meta"], expected_run_id=run_id, expected_sha=sha)
    if payload["stage"] not in {"render", "gmail_1", "gmail_2", "gmail_3", "health"}:
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
    )
    bridge = DufyndJarvisBridge()
    bridge.upsert_master_status(
        key="ops.private_observer.last_failure",
        category="ops",
        value=payload,
        last_verified_at=datetime.now(UTC).isoformat(),
    )
    print(json.dumps({"recorded": True, "stage": payload["stage"], "reason": payload["reason"]}))


if __name__ == "__main__":
    main()
