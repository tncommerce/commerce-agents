"""Deterministic Supervisor V2 policy; no model calls or inferred completion."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

ACTIVE_STATES = {"claimed", "working", "verifying", "in_progress"}
HUMAN_REASONS = {"owner_decision", "spend_approval", "publication_approval", "contract_approval"}
RETRY_REASONS = {"tool_timeout", "session_ended", "technical_research", "retryable_error"}
STATES = {
    "queued",
    "ready",
    "claimed",
    "working",
    "verifying",
    "done",
    "waiting_external",
    "waiting_human_input",
    "blocked",
    "failed_retryable",
    "failed_terminal",
    "stale",
}


def timestamp(value: object) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def lease_state(value: dict[str, Any], now: datetime) -> dict[str, Any]:
    expires = timestamp(value.get("expires_at") or value.get("lease_expires_at"))
    released = bool(value.get("released_at"))
    active = (
        value.get("status") == "active" and not released and expires is not None and expires > now
    )
    return {
        "active": active,
        "inconsistent": value.get("status") == "active" and released,
        "reclaimable": not active,
        "owner": value.get("owner"),
        "heartbeat_at": value.get("heartbeat_at"),
        "expires_at": expires.isoformat() if expires else None,
        "remaining_seconds": max(0, int((expires - now).total_seconds())) if active else 0,
    }


def worker_health(task: dict[str, Any], now: datetime) -> str:
    if task.get("worker_state", task.get("status")) not in ACTIVE_STATES:
        return "inactive"
    if task.get("released_at"):
        return "released_lease"
    expires = timestamp(task.get("lease_expires_at"))
    heartbeat = timestamp(task.get("heartbeat_at"))
    progress = timestamp(task.get("last_progress_at"))
    if expires is None or expires <= now:
        return "lease_expired"
    if heartbeat is None or (now - heartbeat).total_seconds() > 180:
        return "heartbeat_stale"
    if progress is None or (now - progress).total_seconds() > 600:
        return "progress_stalled"
    return "healthy"


def resources_conflict(left: list[str], right: list[str]) -> bool:
    # Undeclared resources fail closed. Paths are canonical, repo-relative prefixes.
    if not left or not right or "exclusive:global" in left + right:
        return True
    for a in left:
        for b in right:
            if a == b:
                return True
            if a.startswith("repo:") and b.startswith("repo:"):
                x, y = a[5:].rstrip("/"), b[5:].rstrip("/")
                if "*" in (x, y) or x.startswith(y + "/") or y.startswith(x + "/"):
                    return True
    return False


def recovery_state(reason: str, *, retry_count: int = 0, cost_unknown: bool = False) -> str:
    if reason in HUMAN_REASONS:
        return "waiting_human_input"
    if reason == "external_dependency":
        return "waiting_external"
    if reason in {"budget_exhausted", "unbounded_provider_cost"}:
        return "queued"
    if cost_unknown:
        return "blocked"
    if reason in RETRY_REASONS and retry_count < 2:
        return "failed_retryable"
    return "failed_terminal"


def worst_case_call_allowed(remaining: object, worst_case: object, *, bounded: bool) -> bool:
    try:
        remaining_amount = Decimal(str(remaining))
        maximum = Decimal(str(worst_case))
        return (
            bounded
            and remaining_amount.is_finite()
            and maximum.is_finite()
            and maximum > 0
            and remaining_amount >= maximum
        )
    except (InvalidOperation, TypeError, ValueError):
        return False


def human_gate_allowed(task: dict[str, Any], text: str) -> bool:
    # A model marker or prose is insufficient authorization for an owner gate.
    return bool(task.get("requires_human_approval")) or any(
        line.strip() in {f"DUFYND_BLOCK_REASON: {reason}" for reason in HUMAN_REASONS}
        for line in text.splitlines()
    )


def health_loop(bridge: Any) -> dict[str, Any]:
    """One atomic database pass: reconcile, recover, discover, persist evidence."""
    return bridge.reconcile_control_plane()
