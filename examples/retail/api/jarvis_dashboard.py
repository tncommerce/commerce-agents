"""Read-only CEO Control Room DTO behind the existing server owner boundary.

No mutations, provider calls, SQL inputs, browser credentials, or auth fallback.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlparse
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from .jarvis_clarity import task_explanation, worker_identity, workstream
from .jarvis_crew import project_crew, project_risk
from .jarvis_operator import build_operator_diagnosis

PROJECT_ORIGIN = "https://bqsdxaagklpkxioaqdqa.supabase.co"
ACTIVE = {"claimed", "working", "verifying", "in_progress", "running", "dispatched"}
LANES = ("READY", "WORKING", "WAITING EXTERNAL", "WAITING HUMAN", "BLOCKED", "DONE", "CANCELLED")
SENSITIVE = re.compile(
    r"(?i)(bearer\s|eyJ[A-Za-z0-9_-]+\.|sb_(?:secret|publishable)_|sk-[A-Za-z0-9]"
    r"|gh[pousr]_|github_pat_|ya29\.|1//|secret[_ -]?(?:key|reference)"
    r"|(?:access|refresh|owner|broker)[_ -]?(?:token|key)|service[_ -]?role"
    r"|https?://|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})"
)
TASK_COLUMNS = (
    "task_id,domain,title,status,priority,requires_human_approval,approval_action_type,owner,"
    "worker_state,worker_owner,started_at,heartbeat_at,last_progress_at,lease_expires_at,"
    "expected_next_checkpoint,retry_count,blocked_reason,budget_class,provider_cost_unknown,"
    "durability_policy,created_at,updated_at,released_at,dependencies"
)
RUN_COLUMNS = (
    "execution_id,task_id,worker_type,worker_id,external_run_id,status,attempt,scope,"
    "lease_expires_at,durability_policy,started_at,heartbeat_at,last_progress_at,completed_at,"
    "recovery_count,handler_id,handler_version,created_at,checkpoint_step:last_checkpoint->>step,"
    "checkpoint_verified:last_checkpoint->verified,checkpoint_verified_at:last_checkpoint->>verified_at"
)
OBSERVER_COLUMNS = (
    "observer_id,source_type,enabled,interval_seconds,last_attempt_at,last_success_at,"
    "last_event_at,consecutive_failures,next_retry_at,health_status,"
    "observed_sha:last_snapshot->>sha,monitor_basis:last_snapshot->>monitor_basis"
)
CREDENTIAL_COLUMNS = (
    "provider,status,expires_at,refreshed_at,last_health_check,rotation_due_at,"
    "health_reason,activation_enabled"
)
INBOX_COLUMNS = (
    "event_type,source_type,status,available_at,processed_at,attempts,observed_at,processing_status"
)
# Project nested master values at the database boundary; never fetch a full value/payload.
MASTER_READS = {
    "checkpoint": (
        "continuity.checkpoint.jarvis",
        "updated_at,observed_at:value->>checkpointed_at,priority:value->>next_priority,"
        "next_action:value->>next_safe_action,last_action:value->>last_completed_action,"
        "paid_enabled:value->paid_model_execution_enabled",
    ),
    "supervisor": ("jarvis.supervisor_v2.health", "checked_at:value->>checked_at"),
    "lease": (
        "continuity.tech_lease",
        "status:value->>status,owner:value->>owner,expires_at:value->>expires_at,"
        "released_at:value->>released_at",
    ),
    "smoke": (
        "jarvis.production_smoke.observation",
        "status:value->>status,observed_at:value->>observed_at,passed:value->passed,"
        "total:value->total,sha:value->>live_head_sha",
    ),
}

# Scalar database projections only. Never forward raw master values.
MASTER_READS.update(
    {
        "thin": (
            "jarvis.thin_v1.status",
            "observed_at:value->>observed_at,stop_reason:value->>stop_reason,active_leases:value->active_leases,stale_leases:value->stale_leases,open_reservations:value->open_reservations,provider_cost_unknown:value->provider_cost_unknown,done:value->queue_counts->done,active:value->queue_counts->in_progress,working:value->queue_counts->working,waiting_external:value->queue_counts->waiting_external,blocked:value->queue_counts->blocked,cancelled:value->queue_counts->cancelled,last_task:value->completed->0->>task_id,planner_state:value->planner->>state,planner_next_safe_work_at:value->planner->>next_safe_work_at,planner_ready_free:value->planner->ready_certified_free_tasks,planner_external_waits_global_blocker:value->planner->external_waits_are_global_blocker,planner_first_money_next_evidence:value->planner->>first_money_next_evidence",
        ),
        "business_planner": (
            "jarvis.planner_v1",
            "observed_at:value->>observed_at,state:value->>state,"
            "business_next_move:value->>business_next_move,"
            "capability_gap:value->>capability_gap,"
            "master_action_required:value->master_action_required,"
            "queue_state:value->queue->>state,"
            "queue_stop_reason:value->queue->>stop_reason",
        ),
        "thin_config": ("jarvis.thin_v1.config", "enabled:value->enabled"),
        "ci": (
            "jarvis.thin_v1.ci",
            "sha:value->>sha,ready:value->ready,checked_at:value->>checked_at,status:value->>status,conclusion:value->>conclusion,run_id:value->>run_id",
        ),
        "publication": (
            "jarvis.thin_v1.first_money_schedule_observation",
            "observed_at:value->>observed_at,content_id:value->>content_id,experiment_id:value->>experiment_id,platform0:value->posts->0->>platform,status0:value->posts->0->>status,scheduled0:value->posts->0->>scheduled_at,platform1:value->posts->1->>platform,status1:value->posts->1->>status,scheduled1:value->posts->1->>scheduled_at",
        ),
        "money_products": (
            "continuity.checkpoint.ceo_radar",
            "last_verified_at,product0:value->money_products->0->>product,state0:value->money_products->0->>state,product1:value->money_products->1->>product,state1:value->money_products->1->>state,product2:value->money_products->2->>product,state2:value->money_products->2->>state,product3:value->money_products->3->>product,state3:value->money_products->3->>state",
        ),
        "social_quality": (
            "first_money.social_quality_incident.20261005",
            "last_verified_at,status:value->>status,instagram_state:value->>instagram_state,tiktok_state:value->>tiktok_state,owner_quality_floor:value->owner_quality_floor,replacement_requires_new_content_id:value->replacement_requires_new_content_id,publishing_authorized:value->publishing_authorized,replacement_content_id:value->>replacement_content_id,replacement_experiment_id:value->>replacement_experiment_id,instagram_scheduled_at:value->>instagram_scheduled_at,metricool_post_id:value->>metricool_post_id,instagram_auto_publish:value->instagram_auto_publish,instagram_draft:value->instagram_draft",
        ),
    }
)
FIRST_MONEY_CONTENT = "one_million_still_hits_20261004_01"


class DashboardUnavailable(RuntimeError):
    """Fixed safe failure; never forward upstream response bodies or exception text."""


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _stamp(value: object) -> str | None:
    parsed = _time(value)
    return parsed.isoformat() if parsed else None


def _text(value: object, secrets: tuple[str, ...] = ()) -> str | None:
    if not isinstance(value, str):
        return None
    if SENSITIVE.search(value) or any(secret and secret in value for secret in secrets):
        return "[restricted]"
    return " ".join(value.split())[:300]


def _scrub_output(value: Any, secrets: tuple[str, ...]) -> Any:
    """Defense-in-depth scrub for every owner-facing DTO path.

    Canonical public DUFYND URLs are intentionally allowed by the existing
    caption/URL validators; arbitrary URLs, emails, tokens and known secrets
    remain restricted.
    """
    if isinstance(value, dict):
        return {key: _scrub_output(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_output(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub_output(item, secrets) for item in value)
    if isinstance(value, str) and (
        any(secret and secret in value for secret in secrets) or SENSITIVE.search(value)
    ):
        if _candidate_caption(value, secrets) == value or _public_frozen_media_url(value) == value:
            return value
        return "[restricted]"
    return value


def _public_frozen_media_url(value: object) -> str | None:
    """Only permanent content-addressed MP4s on this project's public origins."""
    if not isinstance(value, str) or len(value) > 1000:
        return None
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc not in {"dufynd.de", "bqsdxaagklpkxioaqdqa.supabase.co"}
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/[A-Za-z0-9/_-]*/[a-f0-9]{64}\.mp4", parsed.path)
    ):
        return None
    return value


def _candidate_caption(value: object, secrets: tuple[str, ...] = ()) -> str | None:
    """Text only; allow canonical public DUFYND acquisition links, never asset/signed URLs."""
    if not isinstance(value, str):
        return None
    if len(value) > 2000 or any(secret and secret in value for secret in secrets):
        return "[restricted]"
    remainder = value
    for url in re.findall(r"https?://[^\s]+", value):
        try:
            parsed = urlparse(url)
        except ValueError:
            return "[restricted]"
        params = parse_qsl(parsed.query, keep_blank_values=True)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "dufynd.de"
            or not re.fullmatch(r"/(?:start|duft/[a-z0-9-]{1,80})?/?", parsed.path)
            or parsed.fragment
            or len(params) != len({key for key, _ in params})
            or any(
                key not in {"src", "cmp", "content"}
                or not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", item)
                or SENSITIVE.search(item)
                for key, item in params
            )
        ):
            return "[restricted]"
        remainder = remainder.replace(url, "")
    if SENSITIVE.search(remainder):
        return "[restricted]"
    return value


def _public_dufynd_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 1000:
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    params = parse_qsl(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "dufynd.de"
        or not re.fullmatch(r"/(?:start|duft/[a-z0-9-]{1,80})?/?", parsed.path)
        or parsed.fragment
        or len(params) != len({key for key, _ in params})
        or any(
            key not in {"src", "cmp", "content"} or not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", item)
            for key, item in params
        )
    ):
        return None
    return value


def _enum(value: object) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_.:-]{0,79}", value):
        return _text(value)
    return None


def _observer_error(value: object) -> str | None:
    if value in {
        "credential_expired",
        "invalid_grant",
        "purchase_target_disabled",
        "purchase_target_missing",
    }:
        return str(value)
    return None


def _number(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= 10**9 else None


def _money(value: object) -> str | None:
    if isinstance(value, (dict, list, bool)) or value is None:
        return None
    try:
        amount = Decimal(str(value))
        return str(amount) if amount.is_finite() and 0 <= amount <= 10**9 else None
    except InvalidOperation:
        return None


def _sha(value: object) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value) else None


def _fresh(value: object, now: datetime, seconds: int) -> bool:
    stamp = _time(value)
    return stamp is not None and 0 <= (now - stamp).total_seconds() <= seconds


def _health(row: dict[str, Any], now: datetime) -> str:
    if row.get("enabled") is not True:
        return "BLOCKED"
    status = row.get("health_status")
    if status in {"blocked_configuration", "blocked", "disabled"}:
        return "BLOCKED"
    if status in {"degraded", "failed", "error"} or (row.get("consecutive_failures") or 0):
        return "DEGRADED"
    if not row.get("last_success_at"):
        return "UNKNOWN"
    interval = _number(row.get("interval_seconds")) or 120
    window = max(
        600 if str(row.get("source_type", "")).startswith("github") else 1800, interval * 3
    )
    if status == "stale":
        return "STALE"
    if status == "healthy" and _fresh(row.get("last_success_at"), now, window):
        if row.get("monitor_basis") == "purchase_target_scheduler":
            return "MONITORED"
        return "HEALTHY"
    if status == "healthy" and _fresh(row.get("last_success_at"), now, window * 2 - 1):
        return "MONITORED"
    return "STALE" if status == "healthy" else "UNKNOWN"


def _observer_state(row: dict[str, Any], now: datetime) -> str:
    """Detailed source condition; never infer a successful read from a retry date."""
    if row.get("health_status") == "blocked_configuration":
        return "blocked_configuration"
    if row.get("health_status") in {"failed", "error", "degraded"} or (
        row.get("consecutive_failures") or 0
    ):
        return "failed"
    retry = _time(row.get("next_retry_at"))
    grace = max(360, (_number(row.get("interval_seconds")) or 120) * 3)
    if row.get("health_status") == "initializing" and not row.get("last_success_at"):
        if retry is not None and (now - retry).total_seconds() > grace:
            return "initializing_stuck"
        return "initializing"
    return _health(row, now).lower()


def _worker_health(row: dict[str, Any], now: datetime) -> str:
    if row.get("status") == "stale":
        return "STALE"
    if str(row.get("status", "")).startswith("failed"):
        return "FAILED"
    if row.get("released_at") or row.get("completed_at"):
        return "IDLE"
    if row.get("status") in {"dispatch_pending", "waiting_external", "waiting_human", "retryable"}:
        return "WAITING"
    if row.get("status") not in ACTIVE:
        return "FAILED" if str(row.get("status", "")).startswith("failed") else "IDLE"
    expiry = _time(row.get("lease_expires_at"))
    if expiry is None or expiry <= now or not _fresh(row.get("heartbeat_at"), now, 180):
        return "STALE"
    return "ACTIVE" if _fresh(row.get("last_progress_at"), now, 600) else "WAITING"


def _duration(row: dict[str, Any], now: datetime) -> int | None:
    start = _time(row.get("started_at"))
    end = _time(row.get("completed_at")) or now
    return int((end - start).total_seconds()) if start is not None and start <= end else None


def _checkpoint_step(value: object) -> str | int | None:
    # PostgREST ->> projects numeric JSON steps as strings. Accept only bounded
    # numbers or code-like labels, never checkpoint bodies or arbitrary prose.
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,9}", value):
        return int(value)
    return _enum(value)


def _dependencies(value: object, secrets: tuple[str, ...]) -> list[str]:
    # Dependencies are bounded code-like markers, never payloads or instructions.
    if not isinstance(value, list):
        return []
    return list(
        dict.fromkeys(
            marker
            for raw in value[:20]
            if (marker := _enum(raw)) and _text(marker, secrets) not in {None, "[restricted]"}
        )
    )


def build_snapshot(
    data: dict[str, list[dict[str, Any]]],
    *,
    now: datetime,
    secrets: tuple[str, ...] = (),
    source_counts: dict[str, int | None] | None = None,
) -> dict[str, Any]:
    """Allowlisted browser DTO, also usable by future non-browser owner clients."""
    clean = lambda value: _text(value, secrets)  # noqa: E731
    enum = lambda value: _enum(clean(value))  # noqa: E731
    first = lambda name: (data.get(name) or [{}])[0]  # noqa: E731
    tasks = data.get("tasks", []) + data.get("recent_done", [])
    board: dict[str, list[dict[str, Any]]] = {lane: [] for lane in LANES}
    for row in tasks:
        status = row.get("status")
        if status == "cancelled":
            lane = "CANCELLED"
        elif status == "done":
            lane = "DONE"
        elif status == "waiting_human_input":
            lane = "WAITING HUMAN"
        elif status == "waiting_external":
            lane = "WAITING EXTERNAL"
        elif status in ACTIVE:
            lane = "WORKING"
        elif (
            status in {"ready", "queued"}
            and not row.get("blocked_reason")
            and row.get("provider_cost_unknown") is not True
        ):
            lane = "READY"
        else:
            lane = "BLOCKED"
        mission = {
            "task_id": clean(row.get("task_id")),
            "title": clean(row.get("title")),
            "domain": enum(row.get("domain")),
            "priority": _number(row.get("priority")),
            "status": enum(status),
            "owner": clean(row.get("worker_owner") or row.get("owner")),
            "blocker": enum(row.get("blocked_reason"))
            or ("unknown_provider_cost" if row.get("provider_cost_unknown") is True else None),
            "next_checkpoint": clean(row.get("expected_next_checkpoint")),
            "approval_type": enum(row.get("approval_action_type")),
            "human_gate": status == "waiting_human_input",
            "provider_cost_unknown": row.get("provider_cost_unknown") is True,
            "lease_health": _worker_health({**row, "status": row.get("worker_state")}, now),
            "updated_at": _stamp(row.get("updated_at")),
            "created_at": _stamp(row.get("created_at")),
            "budget_class": enum(row.get("budget_class")),
            "durability_policy": enum(row.get("durability_policy")),
            "retry_count": _number(row.get("retry_count")),
            "dependencies": _dependencies(row.get("dependencies"), secrets),
        }
        board[lane].append(mission)
    task_context = {row["task_id"]: row for lane in board.values() for row in lane}
    task_names = {key: row["title"] for key, row in task_context.items()}
    workers = []
    seen = set()
    for row in data.get("active_runs", []) + data.get("recent_runs", []):
        execution_id = clean(row.get("execution_id"))
        if execution_id in seen:
            continue
        seen.add(execution_id)
        task_id = clean(row.get("task_id"))
        workers.append(
            {
                "execution_id": execution_id,
                "worker_id": clean(row.get("worker_id")),
                "worker_type": enum(row.get("worker_type")),
                "task_id": task_id,
                "task_title": task_names.get(task_id),
                "status": _worker_health(row, now),
                "execution_status": enum(row.get("status")),
                "attempt": _number(row.get("attempt")),
                "scope": clean(row.get("scope")),
                "external_run_id": clean(row.get("external_run_id")),
                "started_at": _stamp(row.get("started_at")),
                "heartbeat_at": _stamp(row.get("heartbeat_at")),
                "last_progress_at": _stamp(row.get("last_progress_at")),
                "lease_expires_at": _stamp(row.get("lease_expires_at")),
                "completed_at": _stamp(row.get("completed_at")),
                "handler_id": enum(row.get("handler_id")),
                "recovery_count": _number(row.get("recovery_count")),
                "duration_seconds": _duration(row, now),
                "task_context": task_context.get(task_id),
                "checkpoint": {
                    "step": _checkpoint_step(clean(row.get("checkpoint_step"))),
                    "verified": row.get("checkpoint_verified")
                    if type(row.get("checkpoint_verified")) is bool
                    else None,
                    "verified_at": _stamp(row.get("checkpoint_verified_at")),
                },
            }
        )
    # Tasks may be claimed without a durable execution record; never hide those workers.
    run_tasks = {worker["task_id"] for worker in workers if not worker["completed_at"]}
    for row in data.get("tasks", []):
        if row.get("worker_state") in ACTIVE and clean(row.get("task_id")) not in run_tasks:
            workers.append(
                {
                    "worker_id": clean(row.get("worker_owner")),
                    "worker_type": "task_lease",
                    "task_id": clean(row.get("task_id")),
                    "task_title": clean(row.get("title")),
                    "status": _worker_health({**row, "status": row.get("worker_state")}, now),
                    "execution_status": enum(row.get("worker_state")),
                    "heartbeat_at": _stamp(row.get("heartbeat_at")),
                    "last_progress_at": _stamp(row.get("last_progress_at")),
                    "lease_expires_at": _stamp(row.get("lease_expires_at")),
                    "duration_seconds": _duration(row, now),
                    "next_checkpoint": clean(row.get("expected_next_checkpoint")),
                    "started_at": _stamp(row.get("started_at")),
                    "task_context": task_context.get(clean(row.get("task_id"))),
                }
            )
    for worker in workers:
        context = worker.get("task_context") or {}
        worker["next_checkpoint"] = context.get("next_checkpoint")
        worker["wait_reason"] = (
            None
            if worker["status"] in {"ACTIVE", "IDLE"}
            else (
                "lease_missing"
                if _time(worker.get("lease_expires_at")) is None
                else "lease_expired"
                if _time(worker.get("lease_expires_at")) <= now
                else "heartbeat_missing"
                if _time(worker.get("heartbeat_at")) is None
                else "heartbeat_not_current"
                if not _fresh(worker.get("heartbeat_at"), now, 180)
                else "execution_marked_stale"
            )
            if worker["status"] == "STALE"
            else "execution_failed"
            if worker["status"] == "FAILED"
            else context.get("blocker")
            or (
                "external_dependency"
                if context.get("status") == "waiting_external"
                or worker.get("execution_status") == "waiting_external"
                else "owner_decision"
                if context.get("human_gate") or worker.get("execution_status") == "waiting_human"
                else "dispatch_pending"
                if worker.get("execution_status") == "dispatch_pending"
                else "retry_pending"
                if worker.get("execution_status") == "retryable"
                else "no_recent_progress"
                if worker["status"] == "WAITING"
                else None
            )
        )
    observers = [
        {
            "observer_id": clean(row.get("observer_id")),
            "source_type": enum(row.get("source_type")),
            "enabled": row.get("enabled") is True,
            "health": _health(row, now),
            "observer_state": _observer_state(row, now),
            "last_success_at": _stamp(row.get("last_success_at")),
            "last_attempt_at": _stamp(row.get("last_attempt_at")),
            "next_retry_at": _stamp(row.get("next_retry_at")),
            "failures": _number(row.get("consecutive_failures")),
            "interval_seconds": _number(row.get("interval_seconds")),
            "last_error": _observer_error(row.get("last_error")),
        }
        for row in data.get("observers", [])
    ]
    credentials = [
        {
            "provider": enum(row.get("provider")),
            "status": enum(row.get("status")),
            "expires_at": _stamp(row.get("expires_at")),
            "refreshed_at": _stamp(row.get("refreshed_at")),
            "last_health_check": _stamp(row.get("last_health_check")),
            "rotation_due_at": _stamp(row.get("rotation_due_at")),
            "activation_enabled": row.get("activation_enabled") is True,
            "owner_reauthorization_required": row.get("status") in {"revoked", "account_mismatch"}
            or row.get("health_reason") == "invalid_grant",
            "effective_status": "expired"
            if _time(row.get("expires_at")) is not None and _time(row.get("expires_at")) <= now
            else enum(row.get("status")),
        }
        for row in data.get("credentials", [])
    ]
    systems = []
    precedence = ["BLOCKED", "DEGRADED", "STALE", "UNKNOWN", "MONITORED", "HEALTHY"]
    for name, prefix in (("GitHub", "github"), ("Render", "render"), ("Gmail", "gmail")):
        matching = [
            row
            for row in observers
            if row["enabled"] and (row["source_type"] or "").startswith(prefix)
        ]
        health = min((row["health"] for row in matching), key=precedence.index, default="UNKNOWN")
        systems.append(
            {
                "name": name,
                "health": health,
                "observers": matching,
                "credentials": [row for row in credentials if row["provider"] == prefix],
            }
        )
    supervisor_at = _stamp(first("supervisor").get("checked_at"))
    supervisor_health = (
        "HEALTHY" if _fresh(supervisor_at, now, 360) else "STALE" if supervisor_at else "UNKNOWN"
    )
    systems.append(
        {"name": "Supervisor", "health": supervisor_health, "last_success_at": supervisor_at}
    )
    execution_health = "DEGRADED" if any(w["status"] == "STALE" for w in workers) else "HEALTHY"
    systems.append(
        {
            "name": "Execution Plane",
            "health": execution_health,
            "basis": "bounded_execution_and_task_lease_read",
        }
    )
    budget_raw = first("budget")
    budget = {
        key: _money(budget_raw.get(key))
        for key in ("cap_usd", "spent_usd", "remaining_usd", "reserved_unsettled_usd")
    }
    budget.update(
        {
            "status": enum(budget_raw.get("status")),
            "runs": _number(budget_raw.get("runs")),
            "max_runs": _number(budget_raw.get("max_runs")),
            "provider_cost_unknown": budget_raw.get("provider_cost_unknown") is True,
            "paid_model_execution": "OFF"
            if first("checkpoint").get("paid_enabled") is False
            else "UNKNOWN",
            "paid_model_execution_observed_at": _stamp(first("checkpoint").get("updated_at")),
        }
    )
    decisions = [
        {"task_id": row["task_id"], "title": row["title"], "type": row["approval_type"]}
        for row in board["WAITING HUMAN"]
    ]
    decisions.extend(
        {
            "provider": row["provider"],
            "title": "Credential reauthorization",
            "type": "credential_reauthorization",
        }
        for row in credentials
        if row["owner_reauthorization_required"]
    )
    budget["unknown_provider_cost_task_count"] = sum(
        row.get("provider_cost_unknown") is True for row in data.get("tasks", [])
    )
    active_workers = sum(row["status"] == "ACTIVE" for row in workers)
    status = "IDLE"
    if board["BLOCKED"]:
        status = "BLOCKED"
    if decisions:
        status = "WAITING HUMAN"
    if active_workers:
        status = "ACTIVE"
    if any(system["health"] != "HEALTHY" for system in systems):
        status = "DEGRADED"
    counts = source_counts or {name: len(rows) for name, rows in data.items()}
    incomplete = [
        name
        for name, rows in data.items()
        if counts.get(name) is None or counts.get(name, 0) > len(rows)
    ]
    # Recent history is intentionally bounded; truncation of operational reads is different.
    operational_incomplete = [
        name
        for name in incomplete
        if name
        in {
            "tasks",
            "active_runs",
            "observers",
            "credentials",
            "decisions",
            "thin",
            "thin_config",
            "ci",
            "external_waits",
        }
    ]
    if operational_incomplete:
        status = "DEGRADED"
        next(system for system in systems if system["name"] == "Execution Plane")["health"] = (
            "UNKNOWN"
        )
    branch = next(
        (
            row
            for row in data.get("observers", [])
            if row.get("observer_id") == "github_branch:scentai-mvp"
        ),
        {},
    )
    activity = [
        {
            "event_type": enum(row.get("event_type")),
            "source_type": enum(row.get("source_type")),
            "status": enum(row.get("status")),
            "processing_status": enum(row.get("processing_status")),
            "observed_at": _stamp(row.get("observed_at")),
            "processed_at": _stamp(row.get("processed_at")),
            "attempts": _number(row.get("attempts")),
        }
        for row in data.get("inbox", [])
    ]
    checkpoint = first("checkpoint")
    snapshot = {
        "version": 1,
        "generated_at": now.isoformat(),
        "read_only": True,
        "freshness": {
            "supervisor_observed_at": supervisor_at,
            "incomplete_sources": incomplete,
            "operational_complete": not operational_incomplete,
            "source_counts": counts,
            "atomic": False,
        },
        "command_center": {
            "status": status,
            "active_workers": active_workers,
            "working_tasks": len(board["WORKING"]),
            "human_approval_count": len(decisions),
            "observed_head_sha": _sha(branch.get("observed_sha")),
            "head_observed_at": _stamp(branch.get("last_success_at")),
            "priority": clean(checkpoint.get("priority")),
            "next_safe_action": clean(checkpoint.get("next_action")),
            "last_completed_action": clean(checkpoint.get("last_action")),
            "checkpoint_observed_at": _stamp(checkpoint.get("observed_at")),
            "checkpoint_stale": not _fresh(checkpoint.get("observed_at"), now, 900),
            "last_supervisor_wake": supervisor_at,
            "next_supervisor_wake_estimate": (
                (_time(supervisor_at) + timedelta(seconds=120)).isoformat()
                if supervisor_health == "HEALTHY"
                else None
            ),
            "observer_health_summary": dict(Counter(row["health"] for row in observers)),
        },
        "worker_deck": workers,
        "mission_board": board,
        "live_activity": activity,
        "system_health": systems,
        "budget": budget,
        "safety": {
            "main": "OWNER APPROVAL",
            "publishing": "OWNER APPROVAL",
            "external_messages": "OWNER APPROVAL",
            "commands_available": False,
        },
        "decision_center": decisions,
        "system_map": {
            "levels": ["OWNER", "JARVIS / SUPERVISOR", "WORKERS", "OBSERVERS / TOOLS"],
            "systems": ["GitHub", "Supabase", "Render", "Gmail"],
        },
    }
    thin, ci, publication = first("thin"), first("ci"), first("publication")
    thin_fresh = _fresh(thin.get("observed_at"), now, 360)
    gates = [
        {
            "task_id": clean(r.get("task_id")),
            "decision_id": clean(r.get("decision_id")),
            "title": clean(r.get("title")),
            "question": clean(r.get("question")),
            "type": enum(r.get("action_type")),
            "reason": clean(r.get("reason")),
            "risk": clean(r.get("risk")),
            "cost_usd": _money(r.get("cost_usd")),
            "benefit": clean(r.get("benefit")),
            "current_url": _public_dufynd_url(r.get("current_url")),
            "required_url": _public_dufynd_url(r.get("required_url")),
            "manual_action_required": r.get("manual_action_required") is True,
            "approval_alone_enables_execution": r.get("approval_alone_enables_execution") is True,
            "gate_action_executed": r.get("gate_action_executed") is True,
            "owner_confirmed_manual_action": r.get("owner_confirmed_manual_action") is True,
            "owner_confirmed_at": _stamp(r.get("owner_confirmed_at")),
            "content_candidate": {
                "product": clean(r.get("candidate_product")),
                "product_id": clean(r.get("candidate_product_id")),
                "asset_reference": clean(r.get("candidate_asset_reference")),
                "revision_fingerprint": clean(r.get("candidate_revision_fingerprint")),
                "hook": clean(r.get("candidate_hook")),
                "caption": _candidate_caption(r.get("candidate_caption"), secrets),
                "platform": enum(r.get("candidate_platform")),
                "requested_at": _stamp(r.get("candidate_requested_at")),
                "content_id": clean(r.get("candidate_content_id")),
                "experiment_id": clean(r.get("candidate_experiment_id")),
                "internal_rating": _money(r.get("candidate_internal_rating")),
                "recommendation_reason": clean(r.get("candidate_reason")),
                "publishing_authorized": False,
                "scheduling_authorized": False,
            }
            if r.get("action_type") == "content_candidate_review"
            else None,
            "publish_candidate": {
                "asset_id": clean(r.get("candidate_publish_asset_id")),
                "asset_sha256": clean(r.get("candidate_publish_sha256")),
                "media_url": _public_frozen_media_url(r.get("candidate_publish_uri")),
                "caption": _candidate_caption(r.get("candidate_caption"), secrets),
                "platform": enum(r.get("candidate_platform")),
                "requested_at": _stamp(r.get("candidate_requested_at")),
                "scope": "schedule_and_publish",
            }
            if r.get("action_type") == "content_publish_go"
            else None,
            "action_token": r.get("decision_token")
            if isinstance(r.get("decision_token"), str)
            and re.fullmatch(r"[A-Z][A-Z0-9_-]{2,180}", r["decision_token"])
            else None,
        }
        for r in data.get("decisions", [])
    ]
    snapshot["decision_center"] = gates + [
        d
        for d in decisions
        if d.get("provider") or d.get("task_id") not in {g["task_id"] for g in gates}
    ]
    gate_complete = "decisions" in data and "decisions" not in incomplete
    actionable_gates = [
        gate
        for gate in snapshot["decision_center"]
        if gate.get("owner_confirmed_manual_action") is not True
    ]
    command = snapshot["command_center"]
    command["human_approval_count"] = len(actionable_gates)
    command["status"] = (
        "ERROR"
        if not thin_fresh
        or operational_incomplete
        or first("thin_config").get("enabled") is not True
        else "WORKING"
        if active_workers
        else "OWNER GATE"
        if actionable_gates
        else "WAITING"
    )
    command["owner_action"] = (
        "Owner Action Center: " + (actionable_gates[0].get("title") or "Entscheidung")
        if actionable_gates
        else "NICHTS"
        if snapshot["decision_center"]
        else "NICHTS"
        if gate_complete
        else "Owner-Gates derzeit nicht vollständig prüfbar"
    )
    command["current_task"] = next(
        (w["task_title"] or w["task_id"] for w in workers if w["status"] == "ACTIVE"), None
    )
    command["stop_reason"] = (
        enum(thin.get("stop_reason")) if thin_fresh else "stale_loop_observation"
    )
    planner_state = enum(thin.get("planner_state")) if thin_fresh else None
    planner_next_safe_work_at = _stamp(thin.get("planner_next_safe_work_at"))
    command["planner_state"] = planner_state
    command["next_safe_work_at"] = planner_next_safe_work_at
    command["next_allowed_task"] = (
        f"Nächster zertifizierter kostenloser Check: {planner_next_safe_work_at}"
        if planner_state == "scheduled_safe_work" and planner_next_safe_work_at
        else "Nächstes belastbares Geschäftssignal beobachten"
        if planner_state == "waiting_for_business_signal"
        else "Zertifizierte kostenlose Arbeit liegt bereit"
        if planner_state == "work_ready"
        else "Kein zulässiger Task im letzten Loop ausgewählt; nächste Auswahl beim Wake-up"
        if thin_fresh
        and thin.get("stop_reason") in {"no_safe_work", "waiting_external", "owner_gate"}
        else None
    )
    command["last_loop_at"] = _stamp(thin.get("observed_at"))
    command["next_loop_estimate"] = (
        (_time(thin["observed_at"]) + timedelta(seconds=120)).isoformat() if thin_fresh else None
    )
    command["last_verified_task"] = clean(thin.get("last_task"))
    branch_sha = command["observed_head_sha"]
    ci_health = (
        "HEALTHY"
        if ci.get("ready") is True
        and _sha(ci.get("sha")) == branch_sha
        and branch_sha
        and _fresh(ci.get("checked_at"), now, 1200)
        else "DEGRADED"
    )
    smoke = first("smoke")
    smoke_health = (
        "HEALTHY"
        if smoke.get("status") == "healthy"
        and _sha(smoke.get("sha")) == branch_sha
        and branch_sha
        and _fresh(smoke.get("observed_at"), now, 3600)
        else "STALE"
        if smoke
        else "UNKNOWN"
    )
    systems.extend(
        [
            {
                "name": "CI · scentai-mvp",
                "health": ci_health,
                "last_success_at": _stamp(ci.get("checked_at")),
                "sha": _sha(ci.get("sha")),
                "run_id": clean(ci.get("run_id")),
            },
            {
                "name": "Production Smoke",
                "health": smoke_health,
                "last_success_at": _stamp(smoke.get("observed_at")),
                "sha": _sha(smoke.get("sha")),
                "passed": _number(smoke.get("passed")),
                "total": _number(smoke.get("total")),
                "test_passed": smoke.get("status") == "healthy"
                and (_number(smoke.get("total")) or 0) > 0
                and _number(smoke.get("passed")) == _number(smoke.get("total")),
            },
            {
                "name": "Jarvis free loop",
                "health": "HEALTHY"
                if thin_fresh and first("thin_config").get("enabled") is True
                else "STALE",
                "last_success_at": _stamp(thin.get("observed_at")),
            },
        ]
    )
    snapshot["queue"] = {
        k: _number(thin.get(k)) if thin_fresh else None
        for k in ("done", "waiting_external", "blocked", "cancelled")
    }
    snapshot["queue"]["active"] = (
        ((_number(thin.get("active")) or 0) + (_number(thin.get("working")) or 0))
        if thin_fresh
        else None
    )
    snapshot["queue"]["observed_at"] = _stamp(thin.get("observed_at"))
    reservations = data.get("daily_costs", [])
    cost_complete = "daily_costs" in data and "daily_costs" not in incomplete
    unknown_cost = any(
        r.get("status") in {"dispatched", "cost_unknown", "charged_max"}
        or (r.get("status") == "settled" and _money(r.get("actual_usd")) is None)
        for r in reservations
    )
    spent = sum(
        (
            Decimal(_money(r.get("actual_usd")) or "0")
            for r in reservations
            if r.get("status") == "settled"
        ),
        Decimal(0),
    )
    open_costs = data.get("open_costs", [])
    open_complete = "open_costs" in data and "open_costs" not in incomplete
    global_unknown = any(
        r.get("status") in {"dispatched", "cost_unknown", "charged_max"} for r in open_costs
    )
    snapshot["runtime_safety"] = {
        "active_leases": _number(thin.get("active_leases")) if thin_fresh else None,
        "stale_leases": _number(thin.get("stale_leases")) if thin_fresh else None,
        "open_reservations": _number(thin.get("open_reservations")) if thin_fresh else None,
        "ledger_open_reservations": len(open_costs) if open_complete else None,
        "provider_cost_unknown": (
            thin.get("provider_cost_unknown") is True or unknown_cost or global_unknown
        )
        if thin_fresh and cost_complete and open_complete
        else None,
        "today_new_cost_usd": str(spent) if cost_complete and not unknown_cost else None,
        "cost_basis": "Europe/Berlin day; settled provider reservations by dispatched_at; charged_max/unsettled remains unknown",
    }
    # Raw session hashes/event IDs never leave the server. Bounded reads explicitly
    # expose lower bounds; product views are detail events, not navigation clicks.
    events = data.get("first_money_events", [])
    analytics_complete = "first_money_events" in data and "first_money_events" not in incomplete
    unique = {r.get("event_id"): r for r in events if isinstance(r.get("event_id"), str)}
    event_counts = Counter(r.get("event") for r in unique.values())
    snapshot["first_money"] = {
        "content_id": clean(publication.get("content_id")),
        "experiment_id": clean(publication.get("experiment_id")),
        "publication_observed_at": _stamp(publication.get("observed_at")),
        "publication_stale": not _fresh(publication.get("observed_at"), now, 3600),
        "posts": [
            {
                "platform": enum(publication.get(f"platform{i}")),
                "state": clean(publication.get(f"status{i}")),
                "scheduled_at": _stamp(publication.get(f"scheduled{i}")),
            }
            for i in range(2)
        ],
        "sessions": len({r["session_key"] for r in unique.values() if r.get("session_key")})
        if "first_money_events" in data
        else None,
        "product_views": event_counts["fragrance_detail_view"]
        if "first_money_events" in data
        else None,
        "offer_views": event_counts["offer_section_view"] if "first_money_events" in data else None,
        "merchant_clickouts": event_counts["merchant_clickout"]
        if "first_money_events" in data
        else None,
        "transactions": None,
        "commission_eur": None,
        "analytics_complete": analytics_complete,
        "analytics_provenance": "unclassified_may_include_tests",
        "basis": "Observed events for the exact content and 1 Million product; may include readiness tests. Clickouts are not sales. Transactions/commission require affiliate-network evidence, not currently ingested.",
    }
    products = first("money_products")
    snapshot["money_products"] = {
        "observed_at": _stamp(products.get("last_verified_at")),
        "stale": not _fresh(products.get("last_verified_at"), now, 86400),
        "rows": [
            {
                "product": clean(products.get(f"product{i}")),
                "state": enum(products.get(f"state{i}")),
            }
            for i in range(4)
        ],
    }
    social_quality = first("social_quality")
    snapshot["social_quality"] = {
        "observed_at": _stamp(social_quality.get("last_verified_at")),
        "status": enum(social_quality.get("status")),
        "instagram_state": enum(social_quality.get("instagram_state")),
        "tiktok_state": enum(social_quality.get("tiktok_state")),
        "owner_quality_floor": _money(social_quality.get("owner_quality_floor")),
        "replacement_requires_new_content_id": social_quality.get(
            "replacement_requires_new_content_id"
        )
        is True,
        "publishing_authorized": social_quality.get("publishing_authorized") is True,
        "replacement_content_id": clean(social_quality.get("replacement_content_id")),
        "replacement_experiment_id": clean(social_quality.get("replacement_experiment_id")),
        "instagram_scheduled_at": _stamp(social_quality.get("instagram_scheduled_at")),
        "metricool_post_id": clean(social_quality.get("metricool_post_id")),
        "instagram_auto_publish": social_quality.get("instagram_auto_publish") is True,
        "instagram_draft": social_quality.get("instagram_draft") is True,
    }
    replacement_scheduled = (
        snapshot["social_quality"]["publishing_authorized"]
        and snapshot["social_quality"]["instagram_auto_publish"]
        and not snapshot["social_quality"]["instagram_draft"]
        and bool(snapshot["social_quality"]["replacement_content_id"])
        and bool(snapshot["social_quality"]["instagram_scheduled_at"])
    )
    snapshot["social_quality"]["replacement_scheduled"] = replacement_scheduled
    # Later persisted stop/removal evidence supersedes a historical schedule.
    # This is a read-only projection; retain the original states for history.
    money = snapshot["first_money"]
    quality_at = _time(social_quality.get("last_verified_at"))
    publication_at = _time(publication.get("observed_at"))
    if (
        publication.get("content_id") == FIRST_MONEY_CONTENT
        and quality_at
        and (not publication_at or quality_at > publication_at)
    ):
        overrides = {
            "instagram": ("owner_confirmed_removed", "REMOVED"),
            "tiktok": ("stopped_before_publish", "STOPPED"),
        }
        for post in money["posts"]:
            platform = post["platform"]
            expected, state = overrides.get(platform, (None, None))
            if expected and social_quality.get(f"{platform}_state") == expected:
                post["historical_state"] = post["state"]
                post["historical_scheduled_at"] = post["scheduled_at"]
                post["state"] = state
                post["scheduled_at"] = None
                post["evidence_source"] = "persisted_social_quality"
                post["observed_at"] = quality_at.isoformat()
        money["publication_stopped"] = bool(money["posts"]) and all(
            p["state"] in {"REMOVED", "STOPPED"} for p in money["posts"]
        )
        if money["publication_stopped"]:
            money["publication_observed_at"] = quality_at.isoformat()
            money["publication_stale"] = False
    if replacement_scheduled:
        money["replacement_scheduled"] = True
        money["replacement"] = {
            "platform": "instagram",
            "state": "SCHEDULED",
            "scheduled_at": snapshot["social_quality"]["instagram_scheduled_at"],
            "content_id": snapshot["social_quality"]["replacement_content_id"],
            "experiment_id": snapshot["social_quality"]["replacement_experiment_id"],
            "metricool_post_id": snapshot["social_quality"]["metricool_post_id"],
            "evidence_source": "persisted_social_quality",
            "observed_at": snapshot["social_quality"]["observed_at"],
        }
    # Additive CEO projections. A candidate is not a certified handler selection.
    missions = [
        m for lane, rows in board.items() if lane not in {"DONE", "CANCELLED"} for m in rows
    ]
    ranked = sorted(board["READY"], key=lambda m: (-(m["priority"] or 0), m["task_id"] or ""))
    snapshot["next_tasks"] = ranked[:5]
    snapshot["waiting"] = {
        "owner": len(actionable_gates) if gate_complete else None,
        "external": len(board["WAITING EXTERNAL"]) if not operational_incomplete else None,
        "technical": sum("budget" not in (m["blocker"] or "") for m in board["BLOCKED"])
        if not operational_incomplete
        else None,
        "budget": sum("budget" in (m["blocker"] or "") for m in board["BLOCKED"])
        if not operational_incomplete
        else None,
        "rows": sorted(
            board["WAITING EXTERNAL"] + board["BLOCKED"], key=lambda m: -(m["priority"] or 0)
        )[:5],
    }
    snapshot["workstreams"] = []
    for label, _domains in (
        ("Content", {"content"}),
        ("Tech / Workmode", {"tech", "platform"}),
        ("Jarvis", {"jarvis", "supervisor", "automation"}),
        ("Business / Growth", {"business", "growth", "product"}),
        ("Affiliate", {"affiliate", "commerce"}),
    ):
        rows = sorted(
            (m for m in missions if workstream(m) == label), key=lambda m: -(m["priority"] or 0)
        )
        active = [
            w
            for w in workers
            if w["status"] == "ACTIVE" and w["task_id"] in {m["task_id"] for m in rows}
        ]
        state = (
            "UNKNOWN"
            if operational_incomplete
            else "WORKING"
            if active
            else "OWNER GATE"
            if any(m["human_gate"] for m in rows)
            else "BLOCKED"
            if any(m["blocker"] for m in rows)
            else "READY"
            if any(m["status"] in {"ready", "queued"} for m in rows)
            else "WAITING EXTERNAL"
            if any(m["status"] == "waiting_external" for m in rows)
            else "WAITING"
            if rows
            else "NO DATA"
        )
        if label == "Jarvis" and not rows and thin_fresh:
            state = "MONITORING" if command["status"] == "WAITING" else command["status"]
        evidence_note = None
        if label == "Content" and not rows and publication and not operational_incomplete:
            post_states = {str(p["state"] or "").upper() for p in snapshot["first_money"]["posts"]}
            state = (
                "STALE"
                if snapshot["first_money"]["publication_stale"]
                else "BLOCKED"
                if post_states & {"ERROR", "FAILED", "REJECTED"}
                else "LIVE"
                if post_states & {"PUBLISHED", "POSTED", "LIVE", "SUCCESS"}
                else "SCHEDULED"
                if post_states & {"PENDING", "SCHEDULED"}
                else "UNKNOWN"
            )
            evidence_note = "Veröffentlichungsplan vorhanden · " + (
                "Nachweis älter; kein Publikationsfehler bestätigt"
                if state == "STALE"
                else "keine aktive Worker-Aufgabe"
            )
        snapshot["workstreams"].append(
            {
                "name": label,
                "status": state,
                "tasks": len(rows),
                "next_task": rows[0] if rows else None,
                "evidence_note": evidence_note,
                "active_workers": active,
                "tasks_preview": rows[:15],
                "tasks_preview_complete": len(rows) <= 15 and not operational_incomplete,
                "focus_task": (
                    next((m for m in rows if m["task_id"] in {w["task_id"] for w in active}), None)
                    if active
                    else next((m for m in rows if m["human_gate"]), None)
                    if state == "OWNER GATE"
                    else next((m for m in rows if m["blocker"]), None)
                    if state == "BLOCKED"
                    else rows[0]
                    if rows
                    else None
                ),
            }
        )
    runtime = first("first_money_runtime")
    purchase = runtime.get("purchase_evidence")
    purchase = purchase if isinstance(purchase, dict) else {}
    funnel_runtime = runtime.get("funnel")
    funnel_runtime = funnel_runtime if isinstance(funnel_runtime, dict) else {}
    snapshot["first_money"]["runtime"] = {
        "phase": enum(runtime.get("phase")),
        "next_evidence": enum(runtime.get("next_evidence")),
        "observed_at": _stamp(runtime.get("observed_at")),
        "landing_sessions": _number(funnel_runtime.get("landing_sessions")),
        "purchase_verified_at": _stamp(purchase.get("last_verified_at")),
        "purchase_expires_at": _stamp(purchase.get("expires_at")),
        "purchase_decision": enum(purchase.get("decision")),
    }
    # Versioned STABLE runtime is authoritative; old/missing RPC stays explicitly unclassified.
    target_matches = (
        runtime.get("version") == 3
        and replacement_scheduled
        and runtime.get("content_id") == social_quality.get("replacement_content_id")
        and runtime.get("experiment_id") == social_quality.get("replacement_experiment_id")
    ) or (
        runtime.get("version") in {2, 3}
        and not replacement_scheduled
        and runtime.get("content_id") == FIRST_MONEY_CONTENT
        and runtime.get("experiment_id") == "fms_1m_still_hits_20261004"
    )
    if replacement_scheduled:
        for field in (
            "sessions",
            "product_views",
            "offer_views",
            "offer_opens",
            "merchant_clickouts",
        ):
            snapshot["first_money"][field] = None
        snapshot["first_money"]["analytics_complete"] = False
    launch_fresh = (
        target_matches
        and runtime.get("analytics_provenance") == "launch_attributed_excludes_prelaunch"
        and _fresh(runtime.get("observed_at"), now, 300)
    )
    if launch_fresh:
        money = snapshot["first_money"]
        money["measurement_content_id"] = clean(runtime.get("content_id"))
        money["measurement_experiment_id"] = clean(runtime.get("experiment_id"))
        for output, field in (
            ("sessions", "landing_sessions"),
            ("product_views", "product_views"),
            ("offer_views", "offer_views"),
            ("offer_opens", "offer_opens"),
            ("merchant_clickouts", "merchant_clickouts"),
        ):
            money[output] = _number(funnel_runtime.get(field))
        money["analytics_complete"] = all(
            money[k] is not None
            for k in (
                "sessions",
                "product_views",
                "offer_views",
                "offer_opens",
                "merchant_clickouts",
            )
        )
        money["analytics_provenance"] = "launch_attributed_excludes_prelaunch"
        money["basis"] = (
            "Exact launch content/campaign/source/product after each platform launch. Prelaunch and unrelated traffic excluded. Attribution does not prove organic reach. Clickouts are not sales; network evidence required."
        )
        money["runtime"]["decision_state"] = enum(runtime.get("decision_state"))
        money["runtime"]["source"] = "scentai_analytics_events"
    command["gates_complete"] = gate_complete and not operational_incomplete
    command["ceo_status"] = (
        "PRÜFEN"
        if command["status"] == "ERROR"
        else "WARTET AUF DEINE AKTION"
        if actionable_gates
        else "JARVIS AKTIV"
        if active_workers
        else "BLOCKIERT"
        if thin.get("stop_reason") not in {"waiting_external", "no_safe_work", "owner_gate"}
        and board["BLOCKED"]
        else "JARVIS ÜBERWACHT"
    )
    feed = [
        {
            "id": w.get("execution_id"),
            "title": w["task_title"] or w["task_id"],
            "detail": "Ausführung verifiziert",
            "observed_at": w["completed_at"],
        }
        for w in workers
        if w.get("completed_at")
        and w.get("execution_status") == "completed"
        and w.get("checkpoint", {}).get("verified") is True
    ]
    for system in systems:
        if system["health"] == "HEALTHY" and system.get("last_success_at"):
            feed.append(
                {
                    "id": system["name"],
                    "title": system["name"],
                    "detail": "Erfolgreiche Beobachtung",
                    "observed_at": system["last_success_at"],
                }
            )
    if launch_fresh:
        for row in runtime.get("recent_signals", [])[:8]:
            when = _stamp(row.get("occurred_at"))
            kind = row.get("event")
            if when and kind in {
                "page_view",
                "fragrance_detail_view",
                "offer_section_view",
                "offer_section_open",
                "merchant_clickout",
            }:
                feed.append(
                    {
                        "id": clean(row.get("event_id")),
                        "title": "First Money · " + kind,
                        "detail": "Attributiertes Analytics-Signal · kein Sale-Nachweis",
                        "observed_at": when,
                    }
                )
    snapshot["live_feed"] = sorted(feed, key=lambda e: e["observed_at"] or "", reverse=True)[:8]
    # Presentation semantics are separate from execution eligibility and freshness guards.
    for mission in task_context.values():
        mission["workstream"] = workstream(mission)
        mission["explanation"] = task_explanation(
            mission, data.get("external_waits", []), observers
        )
    for worker in workers:
        worker.update(worker_identity(worker))
        worker["description"] = (worker.get("task_context") or {}).get("explanation")
    for system in systems:
        health = system["health"]
        credential_blocked = any(
            c.get("effective_status") in {"expired", "revoked", "blocked", "account_mismatch"}
            for c in system.get("credentials", [])
        )
        failed = health in {"BLOCKED", "DEGRADED"} or credential_blocked
        if system["name"].startswith("CI"):
            failed = (
                bool(branch_sha)
                and _sha(ci.get("sha")) == branch_sha
                and ci.get("conclusion") in {"failure", "timed_out", "action_required"}
            )
        if system["name"] == "Production Smoke":
            failed = smoke.get("status") in {"failed", "failure", "error", "unhealthy"} or (
                _number(smoke.get("passed")) is not None
                and _number(smoke.get("total")) is not None
                and smoke["passed"] < smoke["total"]
            )
        source_times = [_time(o.get("last_success_at")) for o in system.get("observers", [])]
        source_times = [t for t in source_times if t]
        if source_times:
            # Conservative: show the oldest monitored source, never hide a lagging observer.
            system["last_success_at"] = min(source_times).isoformat()
        label, tone = (
            ("VERBINDUNG / SYSTEM PRÜFEN", "red")
            if failed
            else (
                ("AKTUELL", "green")
                if health == "HEALTHY"
                else ("ÜBERWACHT", "blue")
                if health == "MONITORED"
                else ("NACHWEIS ÄLTER", "amber")
                if health == "STALE"
                else ("NICHT BESTÄTIGT", "amber")
            )
        )
        system["display_status"] = label
        system["display_tone"] = tone
        if (
            system["name"] in {"Gmail", "Render"}
            and failed
            and not any(
                c.get("owner_reauthorization_required") for c in system.get("credentials", [])
            )
        ):
            system["display_status"] = "VERBINDUNG EINGESCHRÄNKT"
            system["display_tone"] = "amber"
        system["confirmed_failure"] = failed
        system["evidence_note"] = (
            "Bestätigten Fehler prüfen." if failed else "Kein Ausfall bestätigt."
        )
        if system["name"] == "Production Smoke" and system.get("test_passed"):
            system["evidence_note"] = "Letzter Test bestanden. " + (
                "Nachweis älter oder von einem früheren HEAD; kein Ausfall bestätigt."
                if health != "HEALTHY"
                else "Aktueller HEAD erfolgreich geprüft."
            )
    money_checkpoint_at = _time(products.get("last_verified_at"))
    checkpoint_age_seconds = (
        max(0, int((now - money_checkpoint_at).total_seconds()))
        if money_checkpoint_at is not None
        else None
    )
    business_planner = first("business_planner")
    operator_tasks = [
        {
            "task_id": clean(row.get("task_id")),
            "domain": enum(row.get("domain")),
            "title": clean(row.get("title")),
            "status": enum(row.get("status")),
            "requires_human_approval": row.get("requires_human_approval") is True,
            "provider_cost_unknown": row.get("provider_cost_unknown") is True,
        }
        for row in data.get("tasks", [])
        if isinstance(row, dict)
    ]
    operator = build_operator_diagnosis(
        tasks=operator_tasks,
        waits=[row for row in data.get("external_waits", []) if isinstance(row, dict)],
        observers=observers,
        credentials=credentials,
        thin={
            "stop_reason": thin.get("stop_reason"),
            "active_leases": max(_number(thin.get("active_leases")) or 0, active_workers),
            "queue_counts": {
                "waiting_external": thin.get("waiting_external"),
                "blocked": thin.get("blocked"),
            },
            "business_checkpoint": {"age_seconds": checkpoint_age_seconds},
            "pending_owner_gates": [{"action_type": gate.get("type")} for gate in actionable_gates],
            "planner": {
                "state": thin.get("planner_state"),
                "next_safe_work_at": thin.get("planner_next_safe_work_at"),
                "ready_certified_free_tasks": thin.get("planner_ready_free"),
                "external_waits_are_global_blocker": thin.get(
                    "planner_external_waits_global_blocker"
                ),
                "first_money_next_evidence": thin.get("planner_first_money_next_evidence"),
            },
            "business_planner": {
                "state": business_planner.get("state"),
                "business_next_move": business_planner.get("business_next_move"),
                "capability_gap": business_planner.get("capability_gap"),
                "master_action_required": business_planner.get("master_action_required"),
                "queue_state": business_planner.get("queue_state"),
                "queue_stop_reason": business_planner.get("queue_stop_reason"),
            },
        },
        runtime=runtime if isinstance(runtime, dict) else {},
        now=now,
    )
    snapshot["operator_diagnosis"] = operator
    command["system_explanation"] = operator["cause"]
    if not active_workers and operator.get("recommended_now"):
        command["priority"] = operator["recommended_now"]["title"]
        command["next_safe_action"] = operator["jarvis_message"]
    command["owner_action"] = operator["owner_message"]
    command["ceo_status"] = (
        "ARBEIT LÄUFT"
        if operator["state"] == "WORKING"
        else "MASTER-AKTION NÖTIG"
        if operator["state"] == "MASTER_ACTION_REQUIRED"
        else "ARBEIT BEREIT"
        if operator["state"] == "READY"
        else "PLANUNG NÖTIG"
        if operator["state"] == "PLANNING_REQUIRED"
        else "ARBEIT GEPLANT"
        if operator["state"] == "SCHEDULED_SAFE_WORK"
        else "SIGNAL WIRD ÜBERWACHT"
        if operator["state"] == "WAITING_FOR_BUSINESS_SIGNAL"
        else "AUTONOMIE LEER"
    )
    snapshot["crew"] = project_crew(snapshot)
    snapshot["global_risk"] = project_risk(snapshot)
    return _scrub_output(snapshot, secrets)


class DashboardReader:
    """Fixed-project, GET-only reader. Never inherit the mutating Jarvis bridge."""

    def __init__(
        self,
        *,
        secret_key: str,
        budget_id: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not secret_key:
            raise DashboardUnavailable("Dashboard read configuration unavailable")
        if budget_id is not None and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", budget_id):
            raise DashboardUnavailable("Dashboard read configuration unavailable")
        self._secret_key = secret_key
        self._budget_id = budget_id
        self._transport = transport

    def snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        headers = {"apikey": self._secret_key, "Prefer": "count=exact"}
        if self._secret_key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + self._secret_key
        reads = {
            "tasks": (
                "dufynd_autonomy_tasks",
                TASK_COLUMNS,
                500,
                {"status": "neq.done", "order": "priority.desc,task_id.asc"},
            ),
            "recent_done": (
                "dufynd_autonomy_tasks",
                TASK_COLUMNS,
                12,
                {"status": "eq.done", "order": "updated_at.desc,task_id.asc"},
            ),
            "active_runs": (
                "dufynd_execution_runs",
                RUN_COLUMNS,
                200,
                {
                    "status": "not.in.(completed,failed_terminal)",
                    "order": "created_at.desc,execution_id.asc",
                },
            ),
            "recent_runs": (
                "dufynd_execution_runs",
                RUN_COLUMNS,
                12,
                {"order": "created_at.desc,execution_id.asc"},
            ),
            "observers": (
                "dufynd_external_observers",
                OBSERVER_COLUMNS,
                200,
                {"order": "observer_id.asc"},
            ),
            "credentials": (
                "dufynd_observer_credentials",
                CREDENTIAL_COLUMNS,
                50,
                {"order": "provider.asc"},
            ),
            "external_waits": (
                "dufynd_task_external_waits",
                "task_id,observer_id,satisfied,policy",
                500,
                {"order": "task_id.asc,observer_id.asc"},
            ),
            "inbox": (
                "dufynd_jarvis_inbox",
                INBOX_COLUMNS,
                100,
                {"order": "observed_at.desc.nullslast,inbox_id.desc"},
            ),
        }
        read_now = now or datetime.now(UTC)
        day_start = (
            read_now.astimezone(ZoneInfo("Europe/Berlin"))
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(UTC)
        )
        reads.update(
            {
                "decisions": (
                    "dufynd_human_decisions",
                    "decision_id,task_id:context->>task_id,action_type,title,question,decision_token,reason:context->>reason,risk:context->>risk,cost_usd:context->cost_usd,benefit:context->>benefit,current_url:context->>current_url,required_url:context->>required_url,manual_action_required:context->manual_action_required,approval_alone_enables_execution:context->approval_alone_enables_execution,gate_action_executed:context->gate_action_executed,owner_confirmed_manual_action:decision->owner_confirmed_manual_action,owner_confirmed_at:decision->>confirmed_at,candidate_publish_asset_id:context->candidate->>asset_id,candidate_publish_sha256:context->candidate->>asset_sha256,candidate_publish_uri:context->candidate->>uri,candidate_product:context->candidate->>product,candidate_product_id:context->candidate->>product_id,candidate_asset_reference:context->candidate->>asset_reference,candidate_revision_fingerprint:context->candidate->>revision_fingerprint,candidate_hook:context->candidate->>hook,candidate_caption:context->candidate->>caption,candidate_platform:context->candidate->>platform,candidate_requested_at:context->candidate->>requested_at,candidate_content_id:context->candidate->>content_id,candidate_experiment_id:context->candidate->>experiment_id,candidate_internal_rating:context->candidate->internal_rating,candidate_reason:context->candidate->>recommendation_reason",
                    200,
                    {"status": "eq.pending", "order": "created_at.asc,decision_id.asc"},
                ),
                "first_money_events": (
                    "scentai_analytics_events",
                    "event_id,session_key,event,occurred_at",
                    10000,
                    {
                        "content_id": "eq." + FIRST_MONEY_CONTENT,
                        "campaign_id": "eq.fms_1m_still_hits_20261004",
                        "acquisition_source": "in.(instagram,tiktok)",
                        "occurred_at": "gte.2026-10-05T08:00:00Z",
                        "or": "(product_id.is.null,product_id.eq.SC-RABANNE-1-MILLION-EDT-100)",
                        "order": "id.desc",
                    },
                ),
                "open_costs": (
                    "dufynd_budget_reservations",
                    "status",
                    1000,
                    {
                        "status": "in.(reserved,dispatched,cost_unknown,charged_max)",
                        "order": "created_at.asc,reservation_id.asc",
                    },
                ),
                "daily_costs": (
                    "dufynd_budget_reservations",
                    "actual_usd,status",
                    1000,
                    {
                        "dispatched_at": "gte." + day_start.isoformat(),
                        "order": "dispatched_at.asc,reservation_id.asc",
                    },
                ),
            }
        )
        reads.update(
            {
                name: ("dufynd_master_status", columns, 1, {"key": "eq." + key})
                for name, (key, columns) in MASTER_READS.items()
            }
        )
        data: dict[str, list[dict[str, Any]]] = {}
        counts: dict[str, int | None] = {}
        try:
            with httpx.Client(
                transport=self._transport, timeout=5, follow_redirects=False
            ) as client:

                def fetch_read(item):
                    name, (table, columns, limit, filters) = item
                    response = client.get(
                        PROJECT_ORIGIN + "/rest/v1/" + table,
                        headers=headers,
                        params={"select": columns, "limit": str(limit), **filters},
                    )
                    if response.status_code not in {200, 206} or len(response.content) > 2_000_000:
                        raise DashboardUnavailable("Dashboard read unavailable")
                    rows = response.json()
                    if (
                        not isinstance(rows, list)
                        or len(rows) > limit
                        or any(not isinstance(row, dict) for row in rows)
                    ):
                        raise DashboardUnavailable("Dashboard read unavailable")
                    total = response.headers.get("content-range", "").rsplit("/", 1)[-1]
                    return name, rows, int(total) if total.isdigit() else None

                with ThreadPoolExecutor(max_workers=6) as pool:
                    for name, rows, total in pool.map(fetch_read, reads.items()):
                        data[name], counts[name] = rows, total
                # Existing STABLE, service-only, read-only function; sanitize all
                # returned scalars in build_snapshot. Raw RPC JSON never reaches clients.
                response = client.get(
                    PROJECT_ORIGIN + "/rest/v1/rpc/read_dufynd_first_money_runtime",
                    headers=headers,
                )
                if response.status_code == 200 and len(response.content) <= 100_000:
                    runtime = response.json()
                    if isinstance(runtime, dict):
                        data["first_money_runtime"], counts["first_money_runtime"] = [runtime], 1
                if self._budget_id:
                    response = client.get(
                        PROJECT_ORIGIN + "/rest/v1/rpc/get_dufynd_jarvis_budget_status",
                        headers=headers,
                        params={"p_budget_id": self._budget_id},
                    )
                    if response.status_code != 200 or len(response.content) > 100_000:
                        raise DashboardUnavailable("Dashboard read unavailable")
                    budget = response.json()
                    if not isinstance(budget, dict):
                        raise DashboardUnavailable("Dashboard read unavailable")
                    data["budget"], counts["budget"] = [budget], 1
            return build_snapshot(
                data,
                now=now or datetime.now(UTC),
                secrets=(self._secret_key,),
                source_counts=counts,
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise DashboardUnavailable("Dashboard read unavailable") from None


def _deny_owner() -> None:
    raise HTTPException(
        status_code=404, detail="Not found", headers={"Cache-Control": "private, no-store"}
    )


def create_dashboard_router(
    reader: DashboardReader, *, authorize_owner: Callable[..., Any] = _deny_owner
) -> APIRouter:
    """Dormant adapter. Default denies BEFORE any database access.

    A future owner verifier must validate a current session AND a server-owned
    owner identity allowlist; generic authentication is insufficient. Never mount
    behind the broker owner key or hand service/provider credentials to a browser.
    """
    router = APIRouter(include_in_schema=False)

    @router.get("/internal/jarvis/snapshot", dependencies=[Depends(authorize_owner)])
    def snapshot() -> JSONResponse:
        try:
            return JSONResponse(
                reader.snapshot(),
                headers={
                    "Cache-Control": "private, no-store",
                    "Vary": "Cookie, Authorization",
                    "X-Robots-Tag": "noindex, nofollow, noarchive",
                },
            )
        except DashboardUnavailable:
            return JSONResponse(
                {"status": "UNAVAILABLE"},
                status_code=503,
                headers={"Cache-Control": "private, no-store"},
            )

    return router
