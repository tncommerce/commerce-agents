from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from scripts import dufynd_jarvis_supervisor as supervisor


def safe_task(task_id: str, domain: str) -> dict:
    return {
        "task_id": task_id,
        "domain": domain,
        "status": "ready",
        "priority": 100,
        "requires_human_approval": False,
        "approval_action_type": "auto_allowed",
    }


class FakeBridge:
    def __init__(self, tasks: list[dict] | None = None) -> None:
        self.tasks = list(tasks or [])
        self.master: dict[str, dict] = {}
        self.pending_events = 0
        self.budget = {
            "budget_id": "jarvis_activation_pilot_001",
            "can_run": True,
            "remaining_usd": 1.5,
            "remaining_runs": 8,
        }
        self.writes: list[dict] = []

    def load_health(self):
        return {
            "inbox": {
                "pending": self.pending_events,
                "processing": 0,
                "failed": 0,
            }
        }

    def load_autonomy_queue(self):
        return {
            "safe_to_execute": list(self.tasks),
            "in_progress": [],
            "waiting_human_input": [],
            "waiting_external": [],
            "blocked": [],
            "approval_required": [],
            "done_recent": [],
        }

    def load_budget_status(self, _budget_id: str):
        return dict(self.budget)

    def load_master_status_entry(self, key: str):
        return self.master.get(key)

    def upsert_master_status(
        self,
        *,
        key,
        category,
        value,
        priority,
        last_verified_at,
    ):
        row = {
            "key": key,
            "category": category,
            "value": dict(value),
            "priority": priority,
            "last_verified_at": last_verified_at,
        }
        self.master[key] = row
        self.writes.append(row)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 30, 5, 0, tzinfo=UTC)
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += timedelta(seconds=seconds)


def completed_session(
    *,
    stop_reason: str,
    status: str = "completed",
    branch_worker_used: bool = False,
    result_states: list[str] | None = None,
) -> dict:
    return {
        "session_id": f"session-{stop_reason}",
        "status": status,
        "started_at": "2026-09-30T05:00:00+00:00",
        "ended_at": "2026-09-30T05:01:00+00:00",
        "stop_reason": stop_reason,
        "tasks_attempted": len(result_states or []),
        "events_processed_estimate": 0,
        "branch_worker_used": branch_worker_used,
        "task_results": [
            {
                "task_id": f"task-{index}",
                "final_status": state,
            }
            for index, state in enumerate(result_states or [])
        ],
    }


def test_supervisor_idles_without_model_calls_then_stops(monkeypatch) -> None:
    bridge = FakeBridge()
    clock = FakeClock()
    calls = 0

    monkeypatch.setattr(supervisor, "_require_autonomous_mode", lambda: None)

    async def run_once(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return completed_session(stop_reason="no_safe_work")

    state = asyncio.run(
        supervisor.supervise_nightshift(
            bridge,
            max_minutes=60,
            max_cycles=5,
            idle_seconds=60,
            max_idle_cycles=2,
            sleep=clock.sleep,
            now=clock.now,
            run_once=run_once,
        )
    )

    assert calls == 0
    assert clock.sleeps == [60, 60]
    assert state["cycles_completed"] == 0
    assert state["idle_cycles"] == 2
    assert state["stop_reason"] == "idle_limit_reached"
    assert state["status"] == "completed"


def test_supervisor_continues_across_task_limit_until_budget_gate(monkeypatch) -> None:
    bridge = FakeBridge([safe_task("repo_current_commerce", "commerce")])
    clock = FakeClock()
    sessions = [
        completed_session(stop_reason="task_limit_reached", result_states=["done"]),
        completed_session(stop_reason="budget_gate"),
    ]

    monkeypatch.setattr(supervisor, "_require_autonomous_mode", lambda: None)

    async def run_once(*_args, **_kwargs):
        return sessions.pop(0)

    state = asyncio.run(
        supervisor.supervise_nightshift(
            bridge,
            max_minutes=60,
            max_cycles=5,
            idle_seconds=60,
            max_idle_cycles=2,
            sleep=clock.sleep,
            now=clock.now,
            run_once=run_once,
        )
    )

    assert state["cycles_completed"] == 2
    assert state["stop_reason"] == "budget_gate"
    assert len(state["session_summaries"]) == 2
    assert state["session_summaries"][0]["task_results"][0]["final_status"] == "done"
    assert state["session_summaries"][0]["task_results"][0]["task_id"] == "task-0"
    assert clock.sleeps == []


def test_supervisor_waits_for_tech_lease_without_model_call(monkeypatch) -> None:
    bridge = FakeBridge([safe_task("repo_current_engineering", "engineering")])
    clock = FakeClock()
    lease_calls = 0
    run_calls = 0

    monkeypatch.setattr(supervisor, "_require_autonomous_mode", lambda: None)

    def lease_state(_bridge):
        nonlocal lease_calls
        lease_calls += 1
        if lease_calls <= 2:
            return {
                "active": True,
                "owner": "chatgpt_work_tech",
                "remaining_seconds": 60,
            }
        return {
            "active": False,
            "owner": "chatgpt_work_tech",
            "remaining_seconds": 0,
        }

    monkeypatch.setattr(supervisor, "_tech_lease_state", lease_state)

    async def run_once(*_args, **_kwargs):
        nonlocal run_calls
        run_calls += 1
        return completed_session(
            stop_reason="engineering_quality_gate_pending",
            status="awaiting_validation",
            branch_worker_used=True,
            result_states=["in_progress"],
        )

    state = asyncio.run(
        supervisor.supervise_nightshift(
            bridge,
            max_minutes=60,
            max_cycles=5,
            idle_seconds=60,
            max_idle_cycles=4,
            sleep=clock.sleep,
            now=clock.now,
            run_once=run_once,
        )
    )

    assert run_calls == 1
    assert clock.sleeps == [60, 60]
    assert state["stop_reason"] == "engineering_quality_gate_pending"
    assert state["cycles_completed"] == 1


def test_supervisor_stops_immediately_when_budget_is_exhausted_and_idle(
    monkeypatch,
) -> None:
    bridge = FakeBridge()
    bridge.budget["can_run"] = False
    clock = FakeClock()

    monkeypatch.setattr(supervisor, "_require_autonomous_mode", lambda: None)

    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("Nightshift must not run when there is no work and budget is closed")

    state = asyncio.run(
        supervisor.supervise_nightshift(
            bridge,
            max_minutes=60,
            max_cycles=5,
            idle_seconds=60,
            max_idle_cycles=2,
            sleep=clock.sleep,
            now=clock.now,
            run_once=should_not_run,
        )
    )

    assert state["stop_reason"] == "budget_gate"
    assert state["cycles_completed"] == 0
    assert clock.sleeps == []


def test_supervisor_fails_closed_on_unclassified_in_progress_task(monkeypatch) -> None:
    bridge = FakeBridge([safe_task("repo_current_content", "content")])
    clock = FakeClock()

    monkeypatch.setattr(supervisor, "_require_autonomous_mode", lambda: None)

    async def run_once(*_args, **_kwargs):
        return completed_session(
            stop_reason="no_safe_work",
            result_states=["in_progress"],
        )

    state = asyncio.run(
        supervisor.supervise_nightshift(
            bridge,
            max_minutes=60,
            max_cycles=5,
            idle_seconds=60,
            max_idle_cycles=2,
            sleep=clock.sleep,
            now=clock.now,
            run_once=run_once,
        )
    )

    assert state["status"] == "needs_attention"
    assert state["stop_reason"] == "unclassified_task_result"
    assert state["cycles_completed"] == 1


def test_supervisor_stops_for_branch_worker_validation(monkeypatch) -> None:
    bridge = FakeBridge([safe_task("repo_current_engineering", "engineering")])
    clock = FakeClock()

    monkeypatch.setattr(supervisor, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(
        supervisor,
        "_tech_lease_state",
        lambda _bridge: {"active": False, "remaining_seconds": 0},
    )

    async def run_once(*_args, **_kwargs):
        return completed_session(
            stop_reason="engineering_quality_gate_pending",
            status="awaiting_validation",
            branch_worker_used=True,
            result_states=["in_progress"],
        )

    state = asyncio.run(
        supervisor.supervise_nightshift(
            bridge,
            max_minutes=60,
            max_cycles=5,
            idle_seconds=60,
            max_idle_cycles=2,
            sleep=clock.sleep,
            now=clock.now,
            run_once=run_once,
        )
    )

    assert state["status"] == "completed"
    assert state["stop_reason"] == "engineering_quality_gate_pending"
    assert state["cycles_completed"] == 1


def test_supervisor_hard_bounds_requested_limits(monkeypatch) -> None:
    bridge = FakeBridge()
    clock = FakeClock()

    monkeypatch.setattr(supervisor, "_require_autonomous_mode", lambda: None)

    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("No work should trigger model execution")

    state = asyncio.run(
        supervisor.supervise_nightshift(
            bridge,
            max_minutes=9999,
            max_cycles=9999,
            idle_seconds=9999,
            max_idle_cycles=0,
            sleep=clock.sleep,
            now=clock.now,
            run_once=should_not_run,
        )
    )

    assert state["max_minutes"] == supervisor.HARD_MAX_MINUTES
    assert state["max_cycles"] == supervisor.HARD_MAX_CYCLES
    assert state["idle_seconds"] == supervisor.HARD_IDLE_SECONDS
    assert state["max_idle_cycles"] == 0
    assert state["stop_reason"] == "idle_limit_reached"
