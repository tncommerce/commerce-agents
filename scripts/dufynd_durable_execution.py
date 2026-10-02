"""Chat-independent deterministic worker for the existing Jarvis Actions runner.

No arbitrary shell, SDK, model, credential forwarding or task instruction evaluator.
Supabase owns identity, checkpoint, scope and fencing; this process owns no queue.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_task_packet import PacketTools

REPOSITORY = "tncommerce/commerce-agents"
BRANCH = "scentai-mvp"


class ExecutionFenceLost(RuntimeError):
    pass


def run_execution(
    bridge: DufyndJarvisBridge,
    execution: dict[str, Any],
    *,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    eid = execution["execution_id"]
    tools = PacketTools(bridge, execution)
    payload = tools.packet["payload"]
    if (
        payload.get("kind") not in ("durability_probe", "supervisor_state_audit")
        or type(payload.get("steps")) is not int
        or type(payload.get("interval_seconds")) is not int
        or not 1 <= payload["steps"] <= 30
        or not 2 <= payload["interval_seconds"] <= 30
    ):
        raise ValueError("uncertified_free_handler")

    def checkpoint(step=None):
        value = tools.call("checkpoint_dufynd_execution", p_step=step)
        if not isinstance(value, dict):
            raise ExecutionFenceLost("execution lease/fence lost; no further mutation")
        return value

    state = checkpoint()
    # Resume entirely from the durable cursor, never local/chat history.
    for step in range(int(state["last_checkpoint"]["step"]) + 1, payload["steps"] + 1):
        deadline = monotonic() + payload["interval_seconds"]
        while (remaining := deadline - monotonic()) > 0:
            sleep(min(remaining, 10))
            checkpoint()  # Heartbeat does not fabricate progress.
        state = checkpoint(step)
        print(
            json.dumps({"execution_id": eid, "step": step, "status": state["status"]}), flush=True
        )
    if not tools.call("finish_dufynd_execution"):
        raise ExecutionFenceLost("verified result persists; finalization deferred to supervisor")
    return {"execution_id": eid, "status": "completed", "real_provider_calls": 0}


def consume(
    bridge: DufyndJarvisBridge,
    *,
    external_run_id: str,
    worker_id: str,
    execution_id: str | None = None,
    max_tasks: int = 2,
    wait_seconds: int = 0,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> list[dict[str, Any]]:
    results = []
    # Bounded existing Actions runner window. Supabase remains the queue/owner.
    deadline = monotonic() + max(0, min(wait_seconds, 360))
    for _ in range(max(1, min(max_tasks, 2))):
        execution = bridge._rpc(
            "take_dufynd_execution",
            {
                "p_external_run_id": external_run_id,
                "p_worker_id": worker_id,
                "p_execution_id": execution_id,
            },
        )
        while not execution and not results and monotonic() < deadline:
            if not bridge._rpc("has_dufynd_durable_event_waiters", {}):
                break
            sleep(min(15, deadline - monotonic()))
            execution = bridge._rpc(
                "take_dufynd_execution",
                {
                    "p_external_run_id": external_run_id,
                    "p_worker_id": worker_id,
                    "p_execution_id": execution_id,
                },
            )
        if not execution:
            break
        print(
            json.dumps(
                {
                    "execution_id": execution["execution_id"],
                    "external_run_id": external_run_id,
                    "status": "dispatched",
                }
            ),
            flush=True,
        )
        try:
            results.append(run_execution(bridge, execution, sleep=sleep, monotonic=monotonic))
        except Exception as error:
            # Secrets/provider output never enter the durable error string.
            bridge._rpc(
                "fail_dufynd_execution",
                {
                    "p_execution_id": execution["execution_id"],
                    "p_token": execution["lease_token"],
                    "p_worker_id": execution["worker_id"],
                    "p_error": type(error).__name__,
                },
            )
            raise
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Free, fenced durable execution worker/status interface"
    )
    parser.add_argument("command", choices=("consume", "status"))
    parser.add_argument("--execution-id")
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args()
    bridge = DufyndJarvisBridge()
    if args.command == "status":
        if not args.execution_id:
            parser.error("status requires --execution-id")
        with bridge._client() as client:
            from scripts.dufynd_jarvis_bridge import _headers

            response = client.get(
                f"{bridge.supabase_url}/rest/v1/dufynd_execution_runs",
                headers=_headers(bridge.secret_key),
                params={"execution_id": f"eq.{args.execution_id}", "select": "*"},
            )
            response.raise_for_status()
            print(json.dumps(response.json()))
        return 0
    if (
        os.getenv("GITHUB_ACTIONS") != "true"
        or os.getenv("GITHUB_REPOSITORY") != REPOSITORY
        or os.getenv("GITHUB_REF_NAME") != BRANCH
        or not os.getenv("GITHUB_RUN_ID", "").isdigit()
    ):
        raise RuntimeError("durable worker must run in the authorized scentai-mvp Actions runner")
    worker = f"github_actions:{os.environ['GITHUB_RUN_ID']}:{os.getenv('GITHUB_JOB')}:{os.getenv('GITHUB_RUN_ATTEMPT')}"
    print(
        json.dumps(
            consume(
                bridge,
                external_run_id=os.environ["GITHUB_RUN_ID"],
                worker_id=worker,
                execution_id=args.execution_id,
                wait_seconds=args.wait_seconds,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
