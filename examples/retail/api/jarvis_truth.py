"""Authoritative operational truth reader for the private DUFYND Jarvis interface."""

from __future__ import annotations

from typing import Any

import httpx

from .jarvis_dashboard import PROJECT_ORIGIN
from .jarvis_operator import build_operator_diagnosis


class JarvisTruthUnavailable(RuntimeError):
    pass


class JarvisTruthReader:
    """Read exact queue/wait/orchestrator evidence with the server-only key."""

    _ACTIVE_STATUSES = (
        "ready,approval_required,waiting_human_input,waiting_external,claimed,working,verifying,blocked"
    )

    def __init__(self, *, secret_key: str, transport: httpx.BaseTransport | None = None) -> None:
        if not secret_key:
            raise JarvisTruthUnavailable()
        self._secret_key = secret_key
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {"apikey": self._secret_key}
        if self._secret_key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + self._secret_key
        return headers

    def _get(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=7,
                follow_redirects=False,
            ) as client:
                response = client.get(
                    PROJECT_ORIGIN + path,
                    headers=self._headers(),
                    params=params,
                )
        except httpx.HTTPError:
            raise JarvisTruthUnavailable() from None
        if response.status_code != 200 or len(response.content) > 500_000:
            raise JarvisTruthUnavailable()
        payload = response.json()
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise JarvisTruthUnavailable()
        return payload

    @staticmethod
    def _safe_focus(value: object) -> str | None:
        text = str(value or "").strip().lower()
        if not text:
            return None
        return text[:120]

    def inspect(self, *, area: object = "overview", focus: object = None) -> dict[str, Any]:
        area_text = str(area or "overview")
        focus_text = self._safe_focus(focus)
        tasks = self._get(
            "/rest/v1/dufynd_autonomy_tasks",
            {
                "select": (
                    "task_id,domain,title,status,priority,budget_class,"
                    "requires_human_approval,approval_action_type,worker_state,"
                    "last_progress_at,lease_expires_at,dependencies,blocked_reason,"
                    "external_review_required,needs_freshness_recheck,"
                    "provider_cost_unknown,durable_payload,created_at,updated_at"
                ),
                "status": f"in.({self._ACTIVE_STATUSES})",
                "order": "priority.desc,created_at.asc",
                "limit": "40",
            },
        )
        waits = self._get(
            "/rest/v1/dufynd_task_external_waits",
            {
                "select": (
                    "task_id,observer_id,event_types,expected_sha,policy,"
                    "satisfied,last_event_id,reevaluated_at"
                ),
                "limit": "200",
            },
        )
        status_rows = self._get(
            "/rest/v1/dufynd_master_status",
            {
                "select": "key,value,last_verified_at",
                "key": (
                    "in.(jarvis.thin_v1.config,jarvis.thin_v1.status,"
                    "continuity.checkpoint.ceo_radar)"
                ),
                "limit": "3",
            },
        )

        waits_by_task: dict[str, list[dict[str, Any]]] = {}
        for wait in waits:
            task_id = str(wait.get("task_id") or "")
            waits_by_task.setdefault(task_id, []).append(
                {
                    "observer_id": wait.get("observer_id"),
                    "event_types": wait.get("event_types"),
                    "expected_sha": wait.get("expected_sha"),
                    "policy": wait.get("policy"),
                    "satisfied": wait.get("satisfied"),
                    "last_event_id": wait.get("last_event_id"),
                    "reevaluated_at": wait.get("reevaluated_at"),
                }
            )

        normalized: list[dict[str, Any]] = []
        focused: list[dict[str, Any]] = []
        certified_handlers = {
            "supervisor_state_audit",
            "purchase_destination_freshness_audit",
            "ci_pr_verifier",
        }
        for task in tasks:
            haystack = " ".join(
                str(task.get(key) or "")
                for key in ("task_id", "title", "domain", "status", "worker_state")
            ).lower()
            external_waits = waits_by_task.get(str(task.get("task_id") or ""), [])
            unsatisfied = [wait for wait in external_waits if wait.get("satisfied") is not True]
            if task.get("status") == "waiting_external":
                evidence_state = (
                    "confirmed_external_wait"
                    if unsatisfied
                    else "external_wait_reason_not_verified"
                )
            elif task.get("status") in {"waiting_human_input", "approval_required"}:
                evidence_state = "confirmed_owner_gate"
            elif task.get("status") in {"claimed", "working", "verifying"}:
                evidence_state = "confirmed_active_execution"
            elif task.get("status") == "ready":
                evidence_state = "confirmed_ready"
            else:
                evidence_state = "confirmed_state"

            handler_kind = (
                task.get("durable_payload", {}).get("kind")
                if isinstance(task.get("durable_payload"), dict)
                else None
            )
            row = {
                "task_id": task.get("task_id"),
                "domain": task.get("domain"),
                "title": task.get("title"),
                "status": task.get("status"),
                "worker_state": task.get("worker_state"),
                "priority": task.get("priority"),
                "budget_class": task.get("budget_class"),
                "requires_human_approval": task.get("requires_human_approval"),
                "approval_action_type": task.get("approval_action_type"),
                "provider_cost_unknown": task.get("provider_cost_unknown"),
                "last_progress_at": task.get("last_progress_at"),
                "lease_expires_at": task.get("lease_expires_at"),
                "dependencies": task.get("dependencies"),
                "external_review_required": task.get("external_review_required"),
                "needs_freshness_recheck": task.get("needs_freshness_recheck"),
                "handler_kind": handler_kind,
                "certified_free_handler": (
                    task.get("budget_class") == "free"
                    and task.get("requires_human_approval") is not True
                    and task.get("provider_cost_unknown") is False
                    and handler_kind in certified_handlers
                ),
                "evidence_state": evidence_state,
                "external_waits": external_waits,
            }
            normalized.append(row)
            if focus_text and focus_text in haystack:
                focused.append(row)

        visible_tasks = focused if focused else normalized

        statuses = {
            str(row.get("key")): {
                "value": row.get("value"),
                "last_verified_at": row.get("last_verified_at"),
            }
            for row in status_rows
        }
        thin = statuses.get("jarvis.thin_v1.status", {})
        thin_value = thin.get("value") if isinstance(thin.get("value"), dict) else {}
        config = statuses.get("jarvis.thin_v1.config", {})
        config_value = config.get("value") if isinstance(config.get("value"), dict) else {}

        highest = normalized[0] if normalized else None
        safe_ready = [
            task
            for task in normalized
            if task.get("status") == "ready" and task.get("certified_free_handler") is True
        ]
        thin_observers = thin_value.get("observer_health")
        thin_observers = thin_observers if isinstance(thin_observers, list) else []
        operator = build_operator_diagnosis(
            tasks=normalized,
            waits=waits,
            observers=[row for row in thin_observers if isinstance(row, dict)],
            credentials=[],
            thin=thin_value,
            runtime=(
                thin_value.get("first_money_runtime")
                if isinstance(thin_value.get("first_money_runtime"), dict)
                else {}
            ),
        )

        pending_gates = thin_value.get("pending_owner_gates")
        sanitized_gates = [
            {
                "decision_id": gate.get("decision_id"),
                "action_type": gate.get("action_type"),
            }
            for gate in (pending_gates if isinstance(pending_gates, list) else [])
            if isinstance(gate, dict)
        ][:12]

        return {
            "source": "dufynd_control_plane_authoritative_truth",
            "verified": True,
            "area": area_text,
            "focus": focus_text,
            "focus_match": bool(focused) if focus_text else None,
            "thin_v1": {
                "enabled": config_value.get("enabled"),
                "config_verified_at": config.get("last_verified_at"),
                "status_verified_at": thin.get("last_verified_at"),
                "stop_reason": thin_value.get("stop_reason"),
                "queue_counts": thin_value.get("queue_counts"),
                "active_leases": thin_value.get("active_leases"),
                "stale_leases": thin_value.get("stale_leases"),
                "provider_cost_unknown": thin_value.get("provider_cost_unknown"),
                "pending_owner_gates": sanitized_gates,
                "ci": thin_value.get("ci") or thin_value.get("loop_ci"),
            },
            "priority": {
                "highest_priority_task": highest,
                "certified_safe_ready": safe_ready[:5],
            },
            "operator_diagnosis": operator,
            "tasks": visible_tasks[:20],
            "truth_rule": (
                "waiting_external without an unsatisfied external-wait row is not a "
                "verified causal explanation; report the missing wait evidence instead of guessing."
            ),
        }
