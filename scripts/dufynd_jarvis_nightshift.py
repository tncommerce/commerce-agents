from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_jarvis_runtime import (
    _require_autonomous_mode,
    _require_budget_window,
    process_branch_task,
    process_loop,
    process_safe_task,
)

SESSION_KEY = "jarvis.nightshift_session"
TECH_LEASE_KEY = "continuity.tech_lease"
DEFAULT_TECH_LEASE_WAIT_SECONDS = 2700
HARD_TECH_LEASE_WAIT_SECONDS = 3600
DEFAULT_MAX_TASKS = 8
HARD_MAX_TASKS = 20
DEFAULT_MAX_EVENTS = 2
HARD_MAX_EVENTS = 5
DEFAULT_WORKER_TIMEOUT_SECONDS = 600
HARD_WORKER_TIMEOUT_SECONDS = 900
DEFAULT_MAX_RETRIES = 1
HARD_MAX_RETRIES = 2
SAFE_TASK_STATE_PREFIX = "DUFYND_TASK_STATE:"
SAFE_TASK_STATES = {
    "done",
    "waiting_human_input",
    "waiting_external",
    "blocked",
    "in_progress",
}


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso_now() -> str:
    return utc_now().isoformat()


def _bounded(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(int(value), maximum))


def _parse_iso_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _tech_lease_state(bridge: DufyndJarvisBridge) -> dict[str, Any]:
    row = bridge.load_master_status_entry(TECH_LEASE_KEY)
    value = (row or {}).get("value") or {}
    expires_at = _parse_iso_timestamp(value.get("expires_at"))
    now = utc_now()
    active = (
        isinstance(value, dict)
        and str(value.get("status") or "").lower() == "active"
        and expires_at is not None
        and expires_at > now
    )
    remaining_seconds = max(0, int((expires_at - now).total_seconds())) if expires_at else 0
    return {
        "active": active,
        "owner": value.get("owner"),
        "heartbeat_at": value.get("heartbeat_at"),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "remaining_seconds": remaining_seconds if active else 0,
    }


def _tech_lease_wait_cap_seconds() -> int:
    raw = os.getenv(
        "DUFYND_JARVIS_TECH_LEASE_WAIT_SECONDS",
        str(DEFAULT_TECH_LEASE_WAIT_SECONDS),
    )
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_TECH_LEASE_WAIT_SECONDS
    return _bounded(value, minimum=0, maximum=HARD_TECH_LEASE_WAIT_SECONDS)


def _snapshot_fingerprint(bridge: DufyndJarvisBridge) -> str:
    row = bridge.load_master_status_entry("jarvis.repo_state_snapshot")
    value = (row or {}).get("value") or {}
    fingerprint = str(value.get("source_fingerprint_sha256") or "").strip()
    if not fingerprint:
        raise RuntimeError("Jarvis nightshift requires a synchronized repo-state fingerprint.")
    return fingerprint


def _new_session(*, fingerprint: str, max_tasks: int, max_events: int) -> dict[str, Any]:
    started = iso_now()
    return {
        "version": 1,
        "session_id": f"nightshift_{started.replace(':', '').replace('+00:00', 'Z')}_{uuid4().hex[:8]}",
        "status": "running",
        "started_at": started,
        "last_heartbeat_at": started,
        "ended_at": None,
        "source_fingerprint_sha256": fingerprint,
        "max_tasks": max_tasks,
        "max_events": max_events,
        "resume_count": 0,
        "tasks_attempted": 0,
        "branch_worker_used": False,
        "current_task": None,
        "task_results": [],
        "event_result": None,
        "stop_reason": None,
        "validation": {"status": "not_run", "pr_url": None},
    }


def _load_or_start_session(
    bridge: DufyndJarvisBridge,
    *,
    fingerprint: str,
    max_tasks: int,
    max_events: int,
) -> dict[str, Any]:
    row = bridge.load_master_status_entry(SESSION_KEY)
    value = (row or {}).get("value") or {}
    resumable = (
        isinstance(value, dict)
        and value.get("status") in {"running", "interrupted", "awaiting_validation"}
        and value.get("source_fingerprint_sha256") == fingerprint
    )

    if resumable:
        session = dict(value)
        session["status"] = "running"
        session["resume_count"] = int(session.get("resume_count") or 0) + 1
        session["max_tasks"] = max_tasks
        session["max_events"] = max_events
        session["last_heartbeat_at"] = iso_now()
        return session

    return _new_session(
        fingerprint=fingerprint,
        max_tasks=max_tasks,
        max_events=max_events,
    )


def _persist_session(bridge: DufyndJarvisBridge, session: dict[str, Any]) -> None:
    session["last_heartbeat_at"] = iso_now()
    bridge.upsert_master_status(
        key=SESSION_KEY,
        category="jarvis",
        value=session,
        priority=100,
        last_verified_at=session["last_heartbeat_at"],
    )


def _safe_candidates(queue: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        task
        for task in (queue.get("safe_to_execute") or [])
        if isinstance(task, dict)
        and str(task.get("task_id") or "").startswith("repo_current_")
        and not bool(task.get("requires_human_approval"))
        and str(task.get("approval_action_type") or "auto_allowed") == "auto_allowed"
    ]


def _select_task(
    queue: dict[str, Any],
    *,
    branch_worker_used: bool,
    attempted_task_ids: set[str] | None = None,
    engineering_allowed: bool = True,
) -> dict[str, Any] | None:
    candidates = _safe_candidates(queue)
    attempted = attempted_task_ids or set()
    eligible = [task for task in candidates if str(task.get("task_id") or "") not in attempted]

    # Keep the shared checkout trustworthy for read-only workers: consume
    # non-engineering GREEN work first, then prepare at most one engineering
    # patch as the final model task before deterministic QA.
    for task in eligible:
        if str(task.get("domain") or "") != "engineering":
            return task

    if branch_worker_used or not engineering_allowed:
        return None

    for task in eligible:
        if str(task.get("domain") or "") == "engineering":
            return task
    return None


def _append_evidence(existing: object, note: str) -> str:
    base = str(existing or "").strip()
    if not base:
        return note[:12000]
    return f"{base}\n{note}"[:12000]


def _safe_worker_outcome(evidence: object) -> str:
    text = str(evidence or "")
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped.startswith(SAFE_TASK_STATE_PREFIX):
            continue
        state = stripped[len(SAFE_TASK_STATE_PREFIX) :].strip().lower()
        if state in SAFE_TASK_STATES:
            return state
    return "in_progress"


def _latest_task_run(
    bridge: DufyndJarvisBridge,
    *,
    task_id: str,
    since_iso: str,
) -> dict[str, Any] | None:
    relevant_types = {
        f"safe_task:{task_id}",
        f"safe_task_failed:{task_id}",
        f"branch_task:{task_id}",
        f"branch_task_failed:{task_id}",
    }
    matches = [
        run
        for run in bridge.load_agent_runs_since(since_iso)
        if str(run.get("run_type") or "") in relevant_types
    ]
    return matches[-1] if matches else None


def _record_persistence_error(
    session: dict[str, Any],
    *,
    task_id: str,
    status: str,
    error: Exception,
) -> None:
    errors = session.setdefault("persistence_errors", [])
    errors.append(
        {
            "task_id": task_id,
            "status": status,
            "error": str(error)[:1200],
            "at": iso_now(),
        }
    )
    if len(errors) > 20:
        del errors[:-20]


def _best_effort_set_task_status(
    bridge: DufyndJarvisBridge,
    session: dict[str, Any],
    *,
    task_id: str,
    status: str,
    evidence: str,
) -> bool:
    try:
        bridge.set_autonomy_task_status(
            task_id=task_id,
            status=status,
            evidence=evidence,
        )
    except Exception as error:
        _record_persistence_error(
            session,
            task_id=task_id,
            status=status,
            error=error,
        )
        return False
    return True


def _recover_interrupted_work(
    bridge: DufyndJarvisBridge,
    session: dict[str, Any],
) -> None:
    candidate = session.get("current_task")
    if not isinstance(candidate, dict):
        for result in reversed(session.get("task_results") or []):
            if (
                isinstance(result, dict)
                and result.get("worker") == "branch_worker"
                and result.get("final_status") == "in_progress"
            ):
                candidate = {
                    "task_id": result.get("task_id"),
                    "domain": result.get("domain"),
                    "worker": result.get("worker"),
                    "started_at": result.get("finished_at") or session.get("started_at"),
                }
                break

    if not isinstance(candidate, dict) or not candidate.get("task_id"):
        return

    task_id = str(candidate["task_id"])
    current = bridge.load_autonomy_task(task_id) or {}
    if str(current.get("status") or "") != "in_progress":
        session["current_task"] = None
        return

    worker = str(candidate.get("worker") or "")
    since_iso = str(candidate.get("started_at") or session.get("started_at") or iso_now())
    latest_run = _latest_task_run(
        bridge,
        task_id=task_id,
        since_iso=since_iso,
    )

    if worker == "safe_worker" and latest_run:
        run_type = str(latest_run.get("run_type") or "")
        recovered_state = _safe_worker_outcome(latest_run.get("output_summary"))
        failed_run = run_type == f"safe_task_failed:{task_id}"

        if recovered_state in {"waiting_human_input", "waiting_external", "blocked"}:
            persisted_status = recovered_state
            final_status = recovered_state
        elif recovered_state == "done" and not failed_run:
            persisted_status = "done"
            final_status = "done"
        else:
            persisted_status = "ready"
            final_status = "in_progress"

        persisted = _best_effort_set_task_status(
            bridge,
            session,
            task_id=task_id,
            status=persisted_status,
            evidence=_append_evidence(
                current.get("evidence"),
                (
                    f"nightshift_session={session['session_id']}; "
                    f"resume recovered run_type={run_type}; "
                    f"recovered_state={final_status}."
                ),
            ),
        )
        session.setdefault("task_results", []).append(
            {
                "task_id": task_id,
                "domain": str(candidate.get("domain") or "unknown"),
                "title": str(current.get("title") or task_id),
                "worker": "safe_worker",
                "result_code": 1 if failed_run else 0,
                "final_status": final_status if persisted else "blocked",
                "attempts": int(candidate.get("attempt") or 1),
                "finished_at": iso_now(),
                "recovered_after_interruption": True,
                "persistence_recovered": persisted,
            }
        )
    else:
        # Branch-worker patches are ephemeral until deterministic QA uploads/pushes
        # them. Unknown/failed safe work is re-queued rather than guessed complete.
        _best_effort_set_task_status(
            bridge,
            session,
            task_id=task_id,
            status="ready",
            evidence=_append_evidence(
                current.get("evidence"),
                (
                    f"nightshift_session={session['session_id']}; "
                    "resume reset interrupted work to ready for a bounded retry."
                ),
            ),
        )
        if worker == "branch_worker":
            session["branch_worker_used"] = False

    session["current_task"] = None


def _task_result(
    task: dict[str, Any],
    *,
    worker: str,
    result_code: int,
    final_status: str,
    attempts: int,
) -> dict[str, Any]:
    return {
        "task_id": str(task.get("task_id") or ""),
        "domain": str(task.get("domain") or "unknown"),
        "title": str(task.get("title") or task.get("task_id") or "Untitled task"),
        "worker": worker,
        "result_code": result_code,
        "final_status": final_status,
        "attempts": attempts,
        "finished_at": iso_now(),
    }


async def _run_task_with_retry(
    bridge: DufyndJarvisBridge,
    session: dict[str, Any],
    task: dict[str, Any],
    *,
    timeout_seconds: int,
    max_retries: int,
) -> dict[str, Any]:
    task_id = str(task["task_id"])
    domain = str(task.get("domain") or "")
    worker = "branch_worker" if domain == "engineering" else "safe_worker"
    total_attempts = max_retries + 1

    for attempt in range(1, total_attempts + 1):
        _require_budget_window(bridge)
        session["current_task"] = {
            "task_id": task_id,
            "domain": domain,
            "worker": worker,
            "attempt": attempt,
            "started_at": iso_now(),
        }
        _persist_session(bridge, session)

        if attempt > 1:
            current = bridge.load_autonomy_task(task_id) or {}
            _best_effort_set_task_status(
                bridge,
                session,
                task_id=task_id,
                status="ready",
                evidence=_append_evidence(
                    current.get("evidence"),
                    (
                        f"nightshift_session={session['session_id']}; "
                        f"retry_attempt={attempt}; prior attempt failed or timed out."
                    ),
                ),
            )

        try:
            if worker == "branch_worker":
                result_code = await asyncio.wait_for(
                    process_branch_task(bridge, task_id=task_id),
                    timeout=timeout_seconds,
                )
            else:
                result_code = await asyncio.wait_for(
                    process_safe_task(bridge, task_id=task_id),
                    timeout=timeout_seconds,
                )
        except TimeoutError:
            result_code = 124
            current = bridge.load_autonomy_task(task_id) or {}
            _best_effort_set_task_status(
                bridge,
                session,
                task_id=task_id,
                status="blocked",
                evidence=_append_evidence(
                    current.get("evidence"),
                    (
                        f"nightshift_session={session['session_id']}; "
                        f"worker_timeout_seconds={timeout_seconds}; attempt={attempt}; "
                        "no automatic retry because provider cost is not reliably known."
                    ),
                ),
            )
            return _task_result(
                task,
                worker=worker,
                result_code=result_code,
                final_status="blocked",
                attempts=attempt,
            )
        except RuntimeError as error:
            # Budget/runtime gates are session-level stop conditions, not task failures.
            if "budget" in str(error).lower() or "active" in str(error).lower():
                raise
            result_code = 1
            current = bridge.load_autonomy_task(task_id) or {}
            _best_effort_set_task_status(
                bridge,
                session,
                task_id=task_id,
                status="blocked" if attempt == total_attempts else "ready",
                evidence=_append_evidence(
                    current.get("evidence"),
                    (
                        f"nightshift_session={session['session_id']}; "
                        f"runtime_error={str(error)[:1200]}; attempt={attempt}."
                    ),
                ),
            )
        except Exception as error:
            # Unexpected task-local worker failures must not abandon the whole
            # Nightshift session in a stale "running" state.
            result_code = 1
            current = bridge.load_autonomy_task(task_id) or {}
            _best_effort_set_task_status(
                bridge,
                session,
                task_id=task_id,
                status="blocked" if attempt == total_attempts else "ready",
                evidence=_append_evidence(
                    current.get("evidence"),
                    (
                        f"nightshift_session={session['session_id']}; "
                        f"worker_exception={type(error).__name__}: {str(error)[:1200]}; "
                        f"attempt={attempt}."
                    ),
                ),
            )

        if result_code == 0:
            current = bridge.load_autonomy_task(task_id) or {}
            if worker == "safe_worker":
                worker_state = _safe_worker_outcome(current.get("evidence"))
                if worker_state == "done":
                    final_status = "done"
                    persisted_status = "done"
                    note = "GREEN task completed for the current repo fingerprint."
                elif worker_state in {
                    "waiting_human_input",
                    "waiting_external",
                    "blocked",
                }:
                    final_status = worker_state
                    persisted_status = worker_state
                    note = f"Safe worker outcome={worker_state}; no autonomous final action taken."
                else:
                    final_status = "in_progress"
                    persisted_status = "ready"
                    note = (
                        "Safe worker reported in_progress or omitted a valid terminal marker; "
                        "task re-queued for a future bounded session instead of being marked done."
                    )
                persisted = _best_effort_set_task_status(
                    bridge,
                    session,
                    task_id=task_id,
                    status=persisted_status,
                    evidence=_append_evidence(
                        current.get("evidence"),
                        f"nightshift_session={session['session_id']}; {note}",
                    ),
                )
                if not persisted:
                    return _task_result(
                        task,
                        worker=worker,
                        result_code=2,
                        final_status="blocked",
                        attempts=attempt,
                    )
            else:
                final_status = "in_progress"
                _best_effort_set_task_status(
                    bridge,
                    session,
                    task_id=task_id,
                    status=final_status,
                    evidence=_append_evidence(
                        current.get("evidence"),
                        (
                            f"nightshift_session={session['session_id']}; "
                            "YELLOW engineering patch prepared; deterministic QA/PR handoff pending."
                        ),
                    ),
                )
                metadata_path = Path(
                    os.getenv(
                        "DUFYND_JARVIS_TASK_METADATA_PATH",
                        "jarvis-worker-task.json",
                    )
                )
                metadata_path.write_text(
                    json.dumps(
                        {
                            "session_id": session["session_id"],
                            "task_id": task_id,
                            "domain": domain,
                            "worker": worker,
                            "source_fingerprint_sha256": session["source_fingerprint_sha256"],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            return _task_result(
                task,
                worker=worker,
                result_code=0,
                final_status=final_status,
                attempts=attempt,
            )

        if attempt == total_attempts:
            current = bridge.load_autonomy_task(task_id) or {}
            if str(current.get("status") or "") != "blocked":
                _best_effort_set_task_status(
                    bridge,
                    session,
                    task_id=task_id,
                    status="blocked",
                    evidence=_append_evidence(
                        current.get("evidence"),
                        (
                            f"nightshift_session={session['session_id']}; "
                            f"worker failed after {attempt} attempt(s)."
                        ),
                    ),
                )
            return _task_result(
                task,
                worker=worker,
                result_code=result_code,
                final_status="blocked",
                attempts=attempt,
            )

    raise AssertionError("unreachable")


async def run_nightshift(
    bridge: DufyndJarvisBridge,
    *,
    max_tasks: int = DEFAULT_MAX_TASKS,
    max_events: int = DEFAULT_MAX_EVENTS,
    worker_timeout_seconds: int = DEFAULT_WORKER_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    _require_autonomous_mode()

    task_limit = _bounded(max_tasks, minimum=1, maximum=HARD_MAX_TASKS)
    event_limit = _bounded(max_events, minimum=0, maximum=HARD_MAX_EVENTS)
    timeout_seconds = _bounded(
        worker_timeout_seconds,
        minimum=60,
        maximum=HARD_WORKER_TIMEOUT_SECONDS,
    )
    retry_limit = _bounded(max_retries, minimum=0, maximum=HARD_MAX_RETRIES)

    fingerprint = _snapshot_fingerprint(bridge)
    session = _load_or_start_session(
        bridge,
        fingerprint=fingerprint,
        max_tasks=task_limit,
        max_events=event_limit,
    )
    _recover_interrupted_work(bridge, session)
    _persist_session(bridge, session)

    stop_reason = "no_safe_work"
    processed_this_run = 0
    tech_lease_waited_seconds = 0

    # Consume event-first backlog before repo-current work. Deterministic,
    # no-cost status events do not consume the paid/model event allowance.
    # If model budget is exhausted, deterministic housekeeping may still run,
    # then task execution fails closed at the budget gate.
    if event_limit:
        health_before = await asyncio.to_thread(bridge.load_health)
        session["inbox_before"] = dict(health_before.get("inbox") or {})
        try:
            session["event_result"] = await asyncio.wait_for(
                process_loop(bridge, max_events=event_limit),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            session["event_result"] = 124
            stop_reason = "event_timeout"
        health_after = await asyncio.to_thread(bridge.load_health)
        session["inbox_after"] = dict(health_after.get("inbox") or {})
        before_pending = int(session["inbox_before"].get("pending") or 0)
        after_pending = int(session["inbox_after"].get("pending") or 0)
        session["events_processed_estimate"] = max(0, before_pending - after_pending)
        if after_pending > 0 and stop_reason == "no_safe_work":
            try:
                _require_budget_window(bridge)
            except RuntimeError:
                stop_reason = "budget_gate"
            else:
                stop_reason = "event_backlog_remaining"
        _persist_session(bridge, session)

    while processed_this_run < task_limit and stop_reason == "no_safe_work":
        try:
            _require_budget_window(bridge)
        except RuntimeError:
            stop_reason = "budget_gate"
            break

        queue = await asyncio.to_thread(bridge.load_autonomy_queue)
        attempted_task_ids = {
            str(item.get("task_id") or "")
            for item in (session.get("task_results") or [])
            if isinstance(item, dict)
        }
        tech_lease = _tech_lease_state(bridge)
        selected = _select_task(
            queue,
            branch_worker_used=bool(session.get("branch_worker_used")),
            attempted_task_ids=attempted_task_ids,
            engineering_allowed=not bool(tech_lease.get("active")),
        )
        if selected is None:
            safe_tasks = _safe_candidates(queue)
            remaining_engineering = [
                task
                for task in safe_tasks
                if str(task.get("domain") or "") == "engineering"
                and str(task.get("task_id") or "") not in attempted_task_ids
            ]
            if safe_tasks and bool(session.get("branch_worker_used")):
                stop_reason = "engineering_quality_gate_pending"
                break
            if remaining_engineering and bool(tech_lease.get("active")):
                wait_cap = _tech_lease_wait_cap_seconds()
                remaining_wait_cap = max(0, wait_cap - tech_lease_waited_seconds)
                wait_seconds = min(
                    int(tech_lease.get("remaining_seconds") or 0),
                    remaining_wait_cap,
                )
                session["tech_lease"] = dict(tech_lease)
                if wait_seconds > 0:
                    session["tech_lease_waited_seconds"] = tech_lease_waited_seconds
                    _persist_session(bridge, session)
                    await asyncio.sleep(wait_seconds)
                    tech_lease_waited_seconds += wait_seconds
                    session["tech_lease_waited_seconds"] = tech_lease_waited_seconds
                    continue
                stop_reason = "tech_lease_active"
                break
            stop_reason = "no_safe_work"
            break

        session["tasks_attempted"] = int(session.get("tasks_attempted") or 0) + 1
        outcome = await _run_task_with_retry(
            bridge,
            session,
            selected,
            timeout_seconds=timeout_seconds,
            max_retries=retry_limit,
        )
        session.setdefault("task_results", []).append(outcome)
        session["current_task"] = None
        if outcome["worker"] == "branch_worker" and outcome["result_code"] == 0:
            session["branch_worker_used"] = True
        processed_this_run += 1
        _persist_session(bridge, session)

        # An engineering patch is the final model task in this checkout. Hand it
        # immediately to deterministic validation so no later worker observes
        # unvalidated repository state.
        if bool(session.get("branch_worker_used")):
            stop_reason = "engineering_quality_gate_pending"
            break

    if processed_this_run >= task_limit and stop_reason == "no_safe_work":
        stop_reason = "task_limit_reached"

    session["stop_reason"] = stop_reason
    session["status"] = (
        "awaiting_validation" if bool(session.get("branch_worker_used")) else "completed"
    )
    if session["status"] == "completed":
        session["ended_at"] = iso_now()
    _persist_session(bridge, session)

    bridge.record_run(
        run_type=f"nightshift:{session['session_id']}",
        input_summary=(
            f"Nightshift task_limit={task_limit}, event_limit={event_limit}, "
            f"fingerprint={fingerprint}"
        ),
        output_summary=(
            f"Nightshift stopped with reason={stop_reason}; "
            f"processed_this_run={processed_this_run}; "
            f"branch_worker_used={session.get('branch_worker_used')}"
        ),
        decisions=[
            {
                "session_id": session["session_id"],
                "stop_reason": stop_reason,
                "processed_this_run": processed_this_run,
                "task_limit": task_limit,
                "event_limit": event_limit,
                "tech_lease_waited_seconds": tech_lease_waited_seconds,
            }
        ],
        human_approval_required=bool(session.get("branch_worker_used")),
        human_approval_status=("pending" if bool(session.get("branch_worker_used")) else None),
        agent_name="jarvis_nightshift",
    )
    return session


def _load_metadata(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.stat().st_size:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Jarvis worker metadata must be a JSON object")
    return payload


def finalize_branch_task(
    bridge: DufyndJarvisBridge,
    *,
    metadata_path: Path,
    status: str,
    evidence: str,
    pr_url: str | None = None,
) -> bool:
    metadata = _load_metadata(metadata_path)
    if not metadata:
        return False

    task_id = str(metadata["task_id"])
    if status == "waiting_human_input" and not pr_url:
        status = "blocked"
        evidence = f"{evidence} No validated PR URL was produced; YELLOW handoff cannot be claimed."

    current = bridge.load_autonomy_task(task_id) or {}
    bridge.set_autonomy_task_status(
        task_id=task_id,
        status=status,
        evidence=_append_evidence(
            current.get("evidence"),
            evidence,
        ),
    )

    row = bridge.load_master_status_entry(SESSION_KEY)
    session = dict((row or {}).get("value") or {})
    if session and session.get("session_id") == metadata.get("session_id"):
        session["validation"] = {
            "status": "passed" if status == "waiting_human_input" else "failed",
            "pr_url": pr_url,
            "updated_at": iso_now(),
        }
        for result in session.get("task_results") or []:
            if result.get("task_id") == task_id:
                result["final_status"] = status
                if pr_url:
                    result["pr_url"] = pr_url
        session["status"] = "completed" if status == "waiting_human_input" else "needs_attention"
        session["ended_at"] = iso_now()
        _persist_session(bridge, session)
    return True


def _decision_cost(decision: object) -> float:
    if not isinstance(decision, dict):
        return 0.0
    raw = decision.get("cost_usd")
    if isinstance(raw, (int, float)):
        return float(raw)
    return 0.0


def _sum_run_costs(runs: list[dict[str, Any]]) -> float:
    total = 0.0
    for run in runs:
        for decision in run.get("decisions") or []:
            total += _decision_cost(decision)
    return round(total, 6)


def _duration_text(start_iso: str, end_iso: str) -> str:
    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    seconds = max(0, int((end - start).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def build_morning_report(
    bridge: DufyndJarvisBridge,
    *,
    qa_status: str,
    pr_url: str | None = None,
) -> tuple[dict[str, Any], str]:
    row = bridge.load_master_status_entry(SESSION_KEY)
    session = dict((row or {}).get("value") or {})
    if not session:
        raise RuntimeError("No Jarvis nightshift session is available for reporting.")

    ended_at = session.get("ended_at") or iso_now()
    started_at = str(session["started_at"])
    runs = bridge.load_agent_runs_since(started_at)
    queue = bridge.load_autonomy_queue()
    health = bridge.load_health()
    pending_decisions = bridge.load_pending_decisions()

    budget_id = os.getenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")
    budget = bridge.load_budget_status(budget_id)
    ai_cost_usd = _sum_run_costs(runs)

    results = [r for r in (session.get("task_results") or []) if isinstance(r, dict)]
    cost_complete = not any(int(r.get("result_code") or 0) == 124 for r in results)
    if int(session.get("event_result") or 0) == 124:
        cost_complete = False
    completed = sum(1 for r in results if r.get("final_status") == "done")
    in_progress = len(queue.get("in_progress") or [])
    blocked = sum(1 for r in results if r.get("final_status") == "blocked")
    waiting_approval = len(queue.get("waiting_human_input") or []) + len(
        queue.get("approval_required") or []
    )

    domains: dict[str, list[str]] = {}
    for result in results:
        domain = str(result.get("domain") or "other")
        line = (
            f"{result.get('title')} — {result.get('final_status')} "
            f"({result.get('worker')}, attempts={result.get('attempts')})"
        )
        domains.setdefault(domain, []).append(line)

    blockers = [
        str(item.get("title") or item.get("task_id"))
        for item in (queue.get("waiting_external") or [])
        if isinstance(item, dict)
    ]
    blockers += [
        str(result.get("title") or result.get("task_id"))
        for result in results
        if result.get("final_status") == "blocked"
    ]
    if int((health.get("inbox") or {}).get("failed") or 0):
        blockers.append(
            f"Jarvis inbox failed events: {int((health.get('inbox') or {}).get('failed') or 0)}"
        )

    approvals = [
        str(item.get("title") or item.get("task_id"))
        for item in (queue.get("waiting_human_input") or [])
        if isinstance(item, dict)
    ]
    approvals += [
        str(item.get("title") or item.get("task_id"))
        for item in (queue.get("approval_required") or [])
        if isinstance(item, dict)
    ]
    approvals += [
        str(item.get("decision_token") or item.get("decision_id"))
        for item in pending_decisions
        if isinstance(item, dict) and str(item.get("status") or "") == "pending"
    ]

    safe = [item for item in (queue.get("safe_to_execute") or []) if isinstance(item, dict)]
    if safe:
        next_priority = str(safe[0].get("title") or safe[0].get("task_id"))
    elif approvals:
        next_priority = f"Owner review: {approvals[0]}"
    elif blockers:
        next_priority = f"Resolve blocker: {blockers[0]}"
    else:
        next_priority = "No safe autonomous work available."

    report = {
        "title": "DUFYND NIGHTSHIFT",
        "session_id": session["session_id"],
        "start": started_at,
        "end": ended_at,
        "duration": _duration_text(started_at, ended_at),
        "stop_reason": session.get("stop_reason"),
        "completed": completed,
        "in_progress": in_progress,
        "blocked": blocked,
        "waiting_approval": waiting_approval,
        "domains": domains,
        "tests": {
            "workflow_status": qa_status,
            "branch_validation": (session.get("validation") or {}).get("status"),
        },
        "ai_cost_usd": ai_cost_usd,
        "ai_cost_source": "audited_agent_runs",
        "ai_cost_complete": cost_complete,
        "budget": budget,
        "blockers": blockers,
        "approvals": approvals,
        "recommended_next_priority": next_priority,
        "pr_url": pr_url or (session.get("validation") or {}).get("pr_url"),
        "inbox": health.get("inbox") or {},
        "source_fingerprint_sha256": session.get("source_fingerprint_sha256"),
    }

    lines = [
        "# DUFYND NIGHTSHIFT",
        "",
        f"Start: {report['start']}",
        f"Ende: {report['end']}",
        f"Dauer: {report['duration']}",
        "",
        f"Completed: {completed}",
        f"In Progress: {in_progress}",
        f"Blocked: {blocked}",
        f"Waiting Approval: {waiting_approval}",
        "",
    ]

    for label, domain in (
        ("Tech", "engineering"),
        ("Content", "content"),
        ("Commerce", "commerce"),
        ("Research", "research"),
    ):
        lines.append(f"## {label}")
        items = domains.get(domain) or []
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- Keine Nightshift-Aktivität in diesem Bereich.")
        lines.append("")

    lines.extend(
        [
            "## Tests",
            f"- Workflow: {qa_status}",
            f"- Branch Validation: {(session.get('validation') or {}).get('status')}",
            "",
            "## AI Cost",
            f"${ai_cost_usd:.4f}",
            (
                "- Quelle: auditierte Agent-Runs."
                if cost_complete
                else "- Quelle: auditierte Agent-Runs; wegen Timeout kann zusätzlicher Provider-Verbrauch unverbucht sein."
            ),
            "",
            "## Blocker",
        ]
    )
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- Keine.")
    lines.extend(["", "## Benötigte Freigaben"])
    if approvals:
        lines.extend(f"- {item}" for item in approvals)
    else:
        lines.append("- Keine.")
    if report["pr_url"]:
        lines.append(f"- Validierter Jarvis-PR: {report['pr_url']}")
    lines.extend(
        [
            "",
            "## Empfohlene nächste Priorität",
            f"- {next_priority}",
            "",
            f"Stop-Grund: {session.get('stop_reason')}",
        ]
    )

    return report, "\n".join(lines) + "\n"


def write_morning_report(
    bridge: DufyndJarvisBridge,
    *,
    output_dir: Path,
    qa_status: str,
    pr_url: str | None,
) -> dict[str, Any]:
    report, markdown = build_morning_report(
        bridge,
        qa_status=qa_status,
        pr_url=pr_url,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "morning-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "morning-report.md").write_text(markdown, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="DUFYND Jarvis Nightshift Orchestrator v1.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--max-tasks", type=int, default=DEFAULT_MAX_TASKS)
    run_parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    run_parser.add_argument(
        "--worker-timeout-seconds",
        type=int,
        default=DEFAULT_WORKER_TIMEOUT_SECONDS,
    )
    run_parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)

    finalize_parser = subparsers.add_parser("finalize-branch")
    finalize_parser.add_argument("--metadata", type=Path, required=True)
    finalize_parser.add_argument(
        "--status",
        choices=["waiting_human_input", "blocked"],
        required=True,
    )
    finalize_parser.add_argument("--evidence", required=True)
    finalize_parser.add_argument("--pr-file", type=Path)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--output-dir", type=Path, required=True)
    report_parser.add_argument("--qa-status", required=True)
    report_parser.add_argument("--pr-file", type=Path)

    args = parser.parse_args()
    bridge = DufyndJarvisBridge()

    if args.command == "run":
        session = asyncio.run(
            run_nightshift(
                bridge,
                max_tasks=args.max_tasks,
                max_events=args.max_events,
                worker_timeout_seconds=args.worker_timeout_seconds,
                max_retries=args.max_retries,
            )
        )
        print(json.dumps(session, ensure_ascii=False))
        return 0

    pr_url = None
    if args.pr_file and args.pr_file.exists():
        pr_url = args.pr_file.read_text(encoding="utf-8").strip() or None

    if args.command == "finalize-branch":
        changed = finalize_branch_task(
            bridge,
            metadata_path=args.metadata,
            status=args.status,
            evidence=args.evidence,
            pr_url=pr_url,
        )
        print(json.dumps({"updated": changed, "status": args.status}, ensure_ascii=False))
        return 0

    report = write_morning_report(
        bridge,
        output_dir=args.output_dir,
        qa_status=args.qa_status,
        pr_url=pr_url,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
