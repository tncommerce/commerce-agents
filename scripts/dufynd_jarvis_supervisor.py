from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_jarvis_nightshift import (
    DEFAULT_MAX_EVENTS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TASKS,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    _safe_candidates,
    _tech_lease_state,
    run_nightshift,
)
from scripts.dufynd_jarvis_runtime import _require_autonomous_mode

SUPERVISOR_KEY = "jarvis.nightshift_supervisor"
DEFAULT_MAX_MINUTES = 300
HARD_MAX_MINUTES = 330
DEFAULT_MAX_CYCLES = 20
HARD_MAX_CYCLES = 40
DEFAULT_IDLE_SECONDS = 300
HARD_IDLE_SECONDS = 900
DEFAULT_MAX_IDLE_CYCLES = 12
HARD_MAX_IDLE_CYCLES = 24

IMMEDIATE_CONTINUE_REASONS = {
    "event_backlog_remaining",
    "task_limit_reached",
}
IDLE_CONTINUE_REASONS = {
    "no_safe_work",
    "tech_lease_active",
}
TERMINAL_REASONS = {
    "budget_gate",
    "event_timeout",
    "worker_runtime_error",
    "orchestration_error",
}


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso_at(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def _bounded(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(int(value), maximum))


def _session_summary(session: dict[str, Any]) -> dict[str, Any]:
    results = [item for item in (session.get("task_results") or []) if isinstance(item, dict)]
    return {
        "session_id": session.get("session_id"),
        "status": session.get("status"),
        "stop_reason": session.get("stop_reason"),
        "started_at": session.get("started_at"),
        "ended_at": session.get("ended_at"),
        "tasks_attempted": int(session.get("tasks_attempted") or 0),
        "events_processed_estimate": int(session.get("events_processed_estimate") or 0),
        "branch_worker_used": bool(session.get("branch_worker_used")),
        "result_states": [str(item.get("final_status") or "unknown") for item in results],
    }


def _preflight(bridge: DufyndJarvisBridge) -> dict[str, Any]:
    health = bridge.load_health()
    queue = bridge.load_autonomy_queue()
    safe_tasks = _safe_candidates(queue)
    lease = _tech_lease_state(bridge)
    inbox = dict(health.get("inbox") or {})
    pending_events = int(inbox.get("pending") or 0)
    non_engineering = [
        task for task in safe_tasks if str(task.get("domain") or "") != "engineering"
    ]
    engineering = [task for task in safe_tasks if str(task.get("domain") or "") == "engineering"]
    return {
        "pending_events": pending_events,
        "safe_task_count": len(safe_tasks),
        "non_engineering_safe_count": len(non_engineering),
        "engineering_safe_count": len(engineering),
        "tech_lease": lease,
        "potential_work": bool(pending_events or safe_tasks),
    }


def _persist_supervisor(
    bridge: DufyndJarvisBridge,
    state: dict[str, Any],
    *,
    verified_at: datetime,
) -> None:
    state["last_heartbeat_at"] = iso_at(verified_at)
    bridge.upsert_master_status(
        key=SUPERVISOR_KEY,
        category="jarvis",
        value=state,
        priority=100,
        last_verified_at=state["last_heartbeat_at"],
    )


async def supervise_nightshift(
    bridge: DufyndJarvisBridge,
    *,
    max_minutes: int = DEFAULT_MAX_MINUTES,
    max_cycles: int = DEFAULT_MAX_CYCLES,
    idle_seconds: int = DEFAULT_IDLE_SECONDS,
    max_idle_cycles: int = DEFAULT_MAX_IDLE_CYCLES,
    max_tasks: int = DEFAULT_MAX_TASKS,
    max_events: int = DEFAULT_MAX_EVENTS,
    worker_timeout_seconds: int = DEFAULT_WORKER_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    now: Callable[[], datetime] = utc_now,
    run_once: Callable[..., Awaitable[dict[str, Any]]] = run_nightshift,
) -> dict[str, Any]:
    _require_autonomous_mode()

    minute_limit = _bounded(max_minutes, minimum=1, maximum=HARD_MAX_MINUTES)
    cycle_limit = _bounded(max_cycles, minimum=1, maximum=HARD_MAX_CYCLES)
    idle_delay = _bounded(idle_seconds, minimum=1, maximum=HARD_IDLE_SECONDS)
    idle_limit = _bounded(
        max_idle_cycles,
        minimum=0,
        maximum=HARD_MAX_IDLE_CYCLES,
    )

    started = now()
    deadline = started + timedelta(minutes=minute_limit)
    state: dict[str, Any] = {
        "version": 1,
        "supervisor_id": f"nightshift_supervisor_{uuid4().hex[:10]}",
        "status": "running",
        "started_at": iso_at(started),
        "deadline_at": iso_at(deadline),
        "ended_at": None,
        "max_minutes": minute_limit,
        "max_cycles": cycle_limit,
        "idle_seconds": idle_delay,
        "max_idle_cycles": idle_limit,
        "cycles_completed": 0,
        "idle_cycles": 0,
        "stop_reason": None,
        "session_summaries": [],
        "last_preflight": None,
        "budget": None,
    }
    _persist_supervisor(bridge, state, verified_at=started)

    def finish(reason: str, *, status: str = "completed") -> dict[str, Any]:
        ended = now()
        state["status"] = status
        state["stop_reason"] = reason
        state["ended_at"] = iso_at(ended)
        _persist_supervisor(bridge, state, verified_at=ended)
        return state

    while int(state["cycles_completed"]) < cycle_limit:
        current = now()
        if current >= deadline:
            return finish("time_horizon_reached")

        preflight = await asyncio.to_thread(_preflight, bridge)
        state["last_preflight"] = preflight
        budget_id = os.getenv(
            "DUFYND_JARVIS_BUDGET_ID",
            "jarvis_activation_pilot_001",
        )
        budget = await asyncio.to_thread(bridge.load_budget_status, budget_id)
        state["budget"] = budget
        _persist_supervisor(bridge, state, verified_at=current)

        # Wait cheaply while the Work/TECH lease owns the only safe engineering
        # work. No model call is made during this handoff window.
        lease = preflight["tech_lease"]
        lease_blocks_only_work = (
            bool(lease.get("active"))
            and int(preflight["pending_events"]) == 0
            and int(preflight["non_engineering_safe_count"]) == 0
            and int(preflight["engineering_safe_count"]) > 0
        )

        if not preflight["potential_work"] or lease_blocks_only_work:
            if int(state["idle_cycles"]) >= idle_limit:
                return finish(
                    "tech_lease_idle_limit" if lease_blocks_only_work else "idle_limit_reached"
                )
            if not bool(budget.get("can_run")) and not preflight["potential_work"]:
                return finish("budget_gate")

            remaining = max(0, int((deadline - current).total_seconds()))
            if remaining <= 0:
                return finish("time_horizon_reached")

            wait_seconds = min(idle_delay, remaining)
            if lease_blocks_only_work:
                lease_remaining = int(lease.get("remaining_seconds") or 0)
                if lease_remaining > 0:
                    wait_seconds = min(wait_seconds, lease_remaining)

            state["idle_cycles"] = int(state["idle_cycles"]) + 1
            _persist_supervisor(bridge, state, verified_at=current)
            await sleep(wait_seconds)
            continue

        session = await run_once(
            bridge,
            max_tasks=max_tasks,
            max_events=max_events,
            worker_timeout_seconds=worker_timeout_seconds,
            max_retries=max_retries,
        )
        state["cycles_completed"] = int(state["cycles_completed"]) + 1
        state["idle_cycles"] = 0
        summary = _session_summary(session)
        state["session_summaries"].append(summary)
        if len(state["session_summaries"]) > HARD_MAX_CYCLES:
            state["session_summaries"] = state["session_summaries"][-HARD_MAX_CYCLES:]
        _persist_supervisor(bridge, state, verified_at=now())

        if (
            bool(session.get("branch_worker_used"))
            or str(session.get("status") or "") == "awaiting_validation"
        ):
            return finish("engineering_quality_gate_pending")

        if str(session.get("status") or "") == "needs_attention":
            return finish("session_needs_attention", status="needs_attention")

        reason = str(session.get("stop_reason") or "unknown")
        if reason in TERMINAL_REASONS:
            return finish(reason)
        if reason in IMMEDIATE_CONTINUE_REASONS:
            continue
        if reason in IDLE_CONTINUE_REASONS:
            results = [
                item for item in (session.get("task_results") or []) if isinstance(item, dict)
            ]
            if any(str(item.get("final_status") or "") == "in_progress" for item in results):
                return finish("unclassified_task_result", status="needs_attention")
            continue

        return finish(f"unexpected_session_stop:{reason}", status="needs_attention")

    return finish("cycle_limit_reached")


def main() -> int:
    parser = argparse.ArgumentParser(description="DUFYND Jarvis bounded overnight supervisor.")
    parser.add_argument("--max-minutes", type=int, default=DEFAULT_MAX_MINUTES)
    parser.add_argument("--max-cycles", type=int, default=DEFAULT_MAX_CYCLES)
    parser.add_argument("--idle-seconds", type=int, default=DEFAULT_IDLE_SECONDS)
    parser.add_argument(
        "--max-idle-cycles",
        type=int,
        default=DEFAULT_MAX_IDLE_CYCLES,
    )
    parser.add_argument("--max-tasks", type=int, default=DEFAULT_MAX_TASKS)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument(
        "--worker-timeout-seconds",
        type=int,
        default=DEFAULT_WORKER_TIMEOUT_SECONDS,
    )
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    args = parser.parse_args()

    state = asyncio.run(
        supervise_nightshift(
            DufyndJarvisBridge(),
            max_minutes=args.max_minutes,
            max_cycles=args.max_cycles,
            idle_seconds=args.idle_seconds,
            max_idle_cycles=args.max_idle_cycles,
            max_tasks=args.max_tasks,
            max_events=args.max_events,
            worker_timeout_seconds=args.worker_timeout_seconds,
            max_retries=args.max_retries,
        )
    )
    print(json.dumps(state, ensure_ascii=False))
    return 0 if state.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
