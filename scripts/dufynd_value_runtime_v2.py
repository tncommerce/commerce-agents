"""Bounded V2 adapter on the existing Jarvis Actions host and Supabase queue.

No activation path here. A separately approved SQL manifest/decision must exist.
The child has no DB credentials or external capabilities. Only the parent owns
fixed, fenced RPCs. No scheduler, arbitrary handler import or publisher calls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_nightshift_value_v2 import SAFETY, instant, sha

CHILD = Path(__file__).with_name("dufynd_value_worker_v2.py")


def evaluate(claim: dict) -> dict:
    m = claim["manifest"]
    timeout = min(10.0, (instant(m["ends_at"]) - datetime.now(UTC)).total_seconds())
    if timeout <= 0:
        return {"state": "OWNER_HOLD", "reason": "deadline_reached", **SAFETY}
    packet = {
        "handler": claim["task"]["durable_payload"]["handler"],
        "sources": m["sources"],
        "pins": m["pins"],
    }
    try:
        worker = subprocess.run(
            [sys.executable, "-I", str(CHILD)],
            input=json.dumps(packet, ensure_ascii=False, allow_nan=False),
            capture_output=True,
            text=True,
            timeout=timeout,
            # No inherited tokens, database credentials, paid-model keys or PYTHONPATH.
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
            cwd=CHILD.parent.parent,
        )
        if worker.returncode or len(worker.stdout.encode()) > 200000:
            raise ValueError("worker_failed")
        result = json.loads(worker.stdout)
        if any(result.get(k) != v or type(result.get(k)) is not type(v) for k, v in SAFETY.items()):
            raise ValueError("unsafe_worker_result")
        return result
    except (ValueError, TypeError, OSError, subprocess.TimeoutExpired):
        return {"state": "OWNER_HOLD", "reason": "isolated_worker_failed_or_timed_out", **SAFETY}


def run(bridge, run_id: str, code_sha: str) -> dict:
    if not re.fullmatch(r"dufynd_value_[a-z0-9_]{6,100}", run_id) or not re.fullmatch(
        r"[a-f0-9]{40}", code_sha
    ):
        raise ValueError("exact_run_and_code_required")
    results = []
    for _ in range(2):
        token = str(uuid4())
        claim = bridge._rpc(
            "claim_dufynd_value_v2", {"p_run": run_id, "p_code_sha": code_sha, "p_token": token}
        )
        if claim is None:
            break
        tid = claim["task"]["task_id"]
        result = evaluate(claim)
        receipt = {
            "version": 2,
            "task_id": tid,
            "handler": claim["task"]["durable_payload"]["handler"],
            "manifest_sha256": sha(claim["manifest"]),
            "result": result,
            "result_sha256": sha(result),
        }
        try:
            accepted = bridge._rpc(
                "commit_dufynd_value_v2",
                {
                    "p_run": run_id,
                    "p_task": tid,
                    "p_token": token,
                    "p_receipt": receipt,
                },
            )
        except Exception:
            # Read the exact durable receipt once after ambiguous transport. Never
            # fabricate success, retry provider calls, or mark a task done locally.
            saved = bridge.load_master_status_entry("jarvis.value_v2.result." + tid)
            if not saved or saved.get("value") != receipt:
                results.append({"task_id": tid, "state": "COMMIT_UNKNOWN_LEASE_RECOVERY_REQUIRED"})
                continue
            accepted = True
        results.append(
            {"task_id": tid, "state": result["state"] if accepted else "FENCE_OR_STOP_HOLD"}
        )
    saved = bridge.load_master_status_entry("jarvis.value_v2.run." + run_id)
    state = (saved or {}).get("value", {})
    tids = state.get("task_ids", [])
    # Do not cancel a competing worker merely because this instance found no claim.
    if len(tids) == 2 and all(
        (bridge.load_autonomy_task(t) or {}).get("status") in {"done", "blocked"} for t in tids
    ):
        bridge._rpc("stop_dufynd_value_v2", {"p_run": run_id, "p_reason": "completed"})
    return {"state": "BOUNDED_RUN_RETURNED", "results": results, "cost_eur": 0, "provider_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if (
        os.getenv("GITHUB_ACTIONS") != "true"
        or os.getenv("GITHUB_REPOSITORY") != "tncommerce/commerce-agents"
        or os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or not os.getenv("GITHUB_RUN_ID", "").isdigit()
        or os.getenv("SUPABASE_URL") != "https://bqsdxaagklpkxioaqdqa.supabase.co"
    ):
        raise SystemExit("authorized_existing_Actions_host_required")
    bridge = DufyndJarvisBridge()

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        print(json.dumps(run(bridge, args.run_id, os.environ.get("GITHUB_SHA", ""))))
    except BaseException:
        with suppress(Exception):
            bridge._rpc(
                "stop_dufynd_value_v2", {"p_run": args.run_id, "p_reason": "runner_failure"}
            )
        # DB deadline/leases still fence SIGKILL, network failure, or outage.
        print("runtime_failed_closed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
