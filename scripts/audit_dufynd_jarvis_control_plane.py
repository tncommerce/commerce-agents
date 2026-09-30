from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

SESSION_KEY = "jarvis.nightshift_session"
SUPERVISOR_KEY = "jarvis.nightshift_supervisor"
TECH_LEASE_KEY = "continuity.tech_lease"
DEFAULT_STALE_AFTER_MINUTES = 45


def _parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_minutes(value: object, now: datetime) -> float | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 60.0)


def _queue_boundary(queue: dict[str, Any]) -> dict[str, Any]:
    counts = {
        "safe_to_execute": len(queue.get("safe_to_execute") or []),
        "in_progress": len(queue.get("in_progress") or []),
        "waiting_human_input": len(queue.get("waiting_human_input") or []),
        "waiting_external": len(queue.get("waiting_external") or []),
        "approval_required": len(queue.get("approval_required") or []),
    }
    if counts["safe_to_execute"]:
        state = "work_available"
    elif counts["in_progress"]:
        state = "in_progress"
    elif counts["waiting_human_input"] or counts["approval_required"]:
        state = "owner_review"
    elif counts["waiting_external"]:
        state = "waiting_external"
    else:
        state = "idle"
    return {"state": state, **counts}


def _budget_snapshot_drift(
    health: dict[str, Any],
    authoritative_budget: dict[str, Any],
) -> dict[str, Any]:
    snapshot = (health.get("runtime_state") or {}).get("pilot") or {}
    if not isinstance(snapshot, dict) or not snapshot:
        return {
            "available": False,
            "consistent": None,
            "mismatches": [],
            "authoritative_source": "database_budget_status",
        }

    mismatches: list[str] = []
    for field in (
        "budget_id",
        "model",
        "cap_usd",
        "max_runs",
        "spent_usd",
        "remaining_usd",
        "remaining_runs",
    ):
        current = authoritative_budget.get(field)
        cached = snapshot.get(field)
        if current is None or cached is None:
            continue
        if isinstance(current, (int, float)) and isinstance(cached, (int, float)):
            if abs(float(current) - float(cached)) > 0.000001:
                mismatches.append(field)
        elif current != cached:
            mismatches.append(field)

    return {
        "available": True,
        "consistent": not mismatches,
        "mismatches": mismatches,
        "authoritative_source": "database_budget_status",
    }


def _session_summary(
    row: dict[str, Any] | None,
    *,
    now: datetime,
    stale_after_minutes: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    session = dict((row or {}).get("value") or {})
    if not session:
        return {"available": False}, []

    status = str(session.get("status") or "unknown")
    heartbeat = session.get("last_heartbeat_at") or session.get("started_at")
    heartbeat_age = _age_minutes(heartbeat, now)
    active = status in {"running", "awaiting_validation"}
    stale = bool(
        active and heartbeat_age is not None and heartbeat_age > max(1, stale_after_minutes)
    )

    summary = {
        "available": True,
        "session_id": session.get("session_id"),
        "status": status,
        "started_at": session.get("started_at"),
        "ended_at": session.get("ended_at"),
        "last_heartbeat_at": session.get("last_heartbeat_at"),
        "heartbeat_age_minutes": round(heartbeat_age, 2) if heartbeat_age is not None else None,
        "stop_reason": session.get("stop_reason"),
        "current_task": session.get("current_task"),
        "stale": stale,
    }

    issues: list[dict[str, Any]] = []
    if stale:
        issues.append(
            {
                "code": "stale_active_nightshift_session",
                "severity": "warning",
                "message": (
                    "Nightshift is still marked active although its heartbeat is older "
                    f"than {stale_after_minutes} minutes."
                ),
            }
        )
    if active and heartbeat_age is None:
        issues.append(
            {
                "code": "active_nightshift_missing_heartbeat",
                "severity": "warning",
                "message": "Nightshift is marked active but has no parseable heartbeat/start timestamp.",
            }
        )
    return summary, issues


def _supervisor_summary(
    row: dict[str, Any] | None,
    *,
    now: datetime,
    stale_after_minutes: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    supervisor = dict((row or {}).get("value") or {})
    if not supervisor:
        return {"available": False}, []

    status = str(supervisor.get("status") or "unknown")
    heartbeat = supervisor.get("last_heartbeat_at") or supervisor.get("started_at")
    heartbeat_age = _age_minutes(heartbeat, now)
    active = status == "running"
    stale = bool(
        active and heartbeat_age is not None and heartbeat_age > max(1, stale_after_minutes)
    )
    summary = {
        "available": True,
        "supervisor_id": supervisor.get("supervisor_id"),
        "status": status,
        "started_at": supervisor.get("started_at"),
        "ended_at": supervisor.get("ended_at"),
        "deadline_at": supervisor.get("deadline_at"),
        "last_heartbeat_at": supervisor.get("last_heartbeat_at"),
        "heartbeat_age_minutes": round(heartbeat_age, 2) if heartbeat_age is not None else None,
        "cycles_completed": int(supervisor.get("cycles_completed") or 0),
        "idle_cycles": int(supervisor.get("idle_cycles") or 0),
        "lease_wait_cycles": int(supervisor.get("lease_wait_cycles") or 0),
        "stop_reason": supervisor.get("stop_reason"),
        "stale": stale,
    }

    issues: list[dict[str, Any]] = []
    if stale:
        issues.append(
            {
                "code": "stale_active_nightshift_supervisor",
                "severity": "warning",
                "message": (
                    "Overnight Supervisor is still marked running although its heartbeat "
                    f"is older than {stale_after_minutes} minutes."
                ),
            }
        )
    if active and heartbeat_age is None:
        issues.append(
            {
                "code": "active_supervisor_missing_heartbeat",
                "severity": "warning",
                "message": (
                    "Overnight Supervisor is marked running but has no parseable "
                    "heartbeat/start timestamp."
                ),
            }
        )
    return summary, issues


def _lease_summary(
    row: dict[str, Any] | None,
    *,
    now: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lease = dict((row or {}).get("value") or {})
    if not lease:
        return {"available": False}, []

    expires_at = _parse_iso(lease.get("expires_at"))
    expired = bool(expires_at and expires_at <= now)
    summary = {
        "available": True,
        "owner": lease.get("owner"),
        "status": lease.get("status"),
        "heartbeat_at": lease.get("heartbeat_at"),
        "expires_at": lease.get("expires_at"),
        "expired": expired,
    }

    issues: list[dict[str, Any]] = []
    if str(lease.get("status") or "") == "active" and expired:
        issues.append(
            {
                "code": "expired_active_tech_lease",
                "severity": "warning",
                "message": "TECH continuity lease is still labelled active although expires_at is past.",
            }
        )
    return summary, issues


def audit_control_plane(
    bridge: DufyndJarvisBridge,
    *,
    now: datetime | None = None,
    stale_after_minutes: int = DEFAULT_STALE_AFTER_MINUTES,
    budget_id: str | None = None,
) -> dict[str, Any]:
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    selected_budget_id = (
        budget_id or os.getenv("DUFYND_JARVIS_BUDGET_ID") or "jarvis_activation_pilot_001"
    )

    queue = bridge.load_autonomy_queue()
    health = bridge.load_health()
    budget = bridge.load_budget_status(selected_budget_id)
    session_row = bridge.load_master_status_entry(SESSION_KEY)
    supervisor_row = bridge.load_master_status_entry(SUPERVISOR_KEY)
    lease_row = bridge.load_master_status_entry(TECH_LEASE_KEY)

    issues: list[dict[str, Any]] = []
    session, session_issues = _session_summary(
        session_row,
        now=current_time,
        stale_after_minutes=stale_after_minutes,
    )
    issues.extend(session_issues)

    supervisor, supervisor_issues = _supervisor_summary(
        supervisor_row,
        now=current_time,
        stale_after_minutes=stale_after_minutes,
    )
    issues.extend(supervisor_issues)

    tech_lease, lease_issues = _lease_summary(lease_row, now=current_time)
    issues.extend(lease_issues)

    budget_snapshot = _budget_snapshot_drift(health, budget)
    if budget_snapshot["consistent"] is False:
        issues.append(
            {
                "code": "stale_health_budget_snapshot",
                "severity": "warning",
                "message": (
                    "Embedded health pilot budget differs from direct database budget status; "
                    "direct budget status is authoritative."
                ),
                "fields": budget_snapshot["mismatches"],
            }
        )

    inbox = health.get("inbox") or {}
    failed_inbox = int(inbox.get("failed") or 0)
    if failed_inbox:
        issues.append(
            {
                "code": "failed_jarvis_inbox_events",
                "severity": "warning",
                "message": f"Jarvis inbox contains {failed_inbox} failed event(s).",
            }
        )

    return {
        "status": "attention" if issues else "ok",
        "checked_at": current_time.isoformat(),
        "budget_id": selected_budget_id,
        "budget": budget,
        "budget_snapshot": budget_snapshot,
        "autonomy_boundary": _queue_boundary(queue),
        "inbox": inbox,
        "nightshift_session": session,
        "nightshift_supervisor": supervisor,
        "tech_lease": tech_lease,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only DUFYND Jarvis control-plane consistency audit."
    )
    parser.add_argument(
        "--stale-after-minutes",
        type=int,
        default=DEFAULT_STALE_AFTER_MINUTES,
    )
    parser.add_argument("--budget-id")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--fail-on-attention", action="store_true")
    args = parser.parse_args()

    payload = audit_control_plane(
        DufyndJarvisBridge(),
        stale_after_minutes=max(1, args.stale_after_minutes),
        budget_id=args.budget_id,
    )
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=args.pretty,
        )
    )
    return 2 if args.fail_on_attention and payload["status"] == "attention" else 0


if __name__ == "__main__":
    raise SystemExit(main())
