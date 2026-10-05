"""Deterministic CEO-level diagnosis for Jarvis and the Control Room.

This module does not dispatch work. It explains the real operating state in plain
business language and separates internal system faults from genuine Master actions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

ACTIVE_STATES = {"claimed", "working", "verifying", "in_progress", "running", "dispatched"}
OWNER_STATES = {"approval_required", "waiting_human_input", "waiting_human"}
READY_STATES = {"ready", "queued"}
UNHEALTHY_OBSERVERS = {"blocked_configuration", "blocked", "degraded", "stale", "unknown"}


def _int(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _bool(value: object) -> bool:
    return value is True


def _status(row: dict[str, Any]) -> str:
    return str(row.get("status") or row.get("worker_state") or "").lower()


def _observer_health(row: dict[str, Any]) -> str:
    return str(row.get("health_status") or row.get("health") or "").lower()


def _observer_error(row: dict[str, Any]) -> str | None:
    value = row.get("last_error")
    return str(value)[:120] if value else None


def _credential_owner_action(row: dict[str, Any]) -> bool:
    nested = row.get("credential_health")
    if isinstance(nested, dict) and nested.get("owner_reauthorization_required") is True:
        return True
    return row.get("owner_reauthorization_required") is True


def _runtime(thin: dict[str, Any], runtime: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(runtime, dict) and runtime:
        return runtime
    nested = thin.get("first_money_runtime")
    return nested if isinstance(nested, dict) else {}


def build_operator_diagnosis(
    *,
    tasks: list[dict[str, Any]],
    waits: list[dict[str, Any]],
    observers: list[dict[str, Any]] | None = None,
    credentials: list[dict[str, Any]] | None = None,
    thin: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return one bounded, user-facing operating diagnosis."""

    thin = thin if isinstance(thin, dict) else {}
    observers = observers or []
    credentials = credentials or []
    now = now or datetime.now(UTC)

    active = [task for task in tasks if _status(task) in ACTIVE_STATES]
    ready = [task for task in tasks if _status(task) in READY_STATES]
    owner_tasks = [
        task
        for task in tasks
        if _status(task) in OWNER_STATES or task.get("requires_human_approval") is True
    ]
    external = [task for task in tasks if _status(task) == "waiting_external"]
    blocked = [task for task in tasks if _status(task) == "blocked"]

    unsatisfied_waits = [
        row
        for row in waits
        if isinstance(row, dict) and row.get("satisfied") is not True and row.get("task_id")
    ]
    wait_task_ids = {str(row.get("task_id")) for row in unsatisfied_waits}
    external_with_binding = [task for task in external if str(task.get("task_id")) in wait_task_ids]
    external_without_binding = [
        task for task in external if str(task.get("task_id")) not in wait_task_ids
    ]

    observer_rows = [row for row in observers if isinstance(row, dict)]
    bad_observers = [
        row
        for row in observer_rows
        if _observer_health(row) in UNHEALTHY_OBSERVERS
        or _observer_error(row) in {"credential_expired", "invalid_grant"}
    ]
    internal_observer_issues = [
        row for row in bad_observers if not _credential_owner_action(row)
    ]
    observer_owner_issues = [row for row in bad_observers if _credential_owner_action(row)]

    credential_owner_issues = [
        row for row in credentials if isinstance(row, dict) and _credential_owner_action(row)
    ]

    pending_gates = thin.get("pending_owner_gates")
    pending_gates = pending_gates if isinstance(pending_gates, list) else []
    real_owner_action = bool(owner_tasks or pending_gates or observer_owner_issues or credential_owner_issues)

    active_leases = _int(thin.get("active_leases"))
    if active_leases and not active:
        active_count = active_leases
    else:
        active_count = len(active)

    queue_counts = thin.get("queue_counts")
    queue_counts = queue_counts if isinstance(queue_counts, dict) else {}
    waiting_count = max(len(external), _int(queue_counts.get("waiting_external")))
    blocked_count = max(len(blocked), _int(queue_counts.get("blocked")))

    runtime_value = _runtime(thin, runtime)
    phase = str(runtime_value.get("phase") or "")
    decision_state = str(runtime_value.get("decision_state") or "")
    publication_verified = runtime_value.get("publication_verified")
    next_evidence = str(runtime_value.get("next_evidence") or "")
    funnel = runtime_value.get("funnel")
    funnel = funnel if isinstance(funnel, dict) else {}
    first_signal_count = sum(
        _int(funnel.get(key))
        for key in ("landing_sessions", "product_views", "offer_views", "offer_opens", "merchant_clickouts")
    )

    business_checkpoint = thin.get("business_checkpoint")
    business_checkpoint = business_checkpoint if isinstance(business_checkpoint, dict) else {}
    checkpoint_age = business_checkpoint.get("age_seconds")
    checkpoint_stale = isinstance(checkpoint_age, (int, float)) and checkpoint_age > 3600

    if active_count:
        state = "WORKING"
        headline = "Arbeit läuft"
        cause = f"{active_count} Ausführung(en) sind aktuell aktiv."
    elif real_owner_action:
        state = "MASTER_ACTION_REQUIRED"
        headline = "Eine echte Master-Entscheidung fehlt"
        cause = "Mindestens ein bestätigter Human-Gate blockiert einen konkreten nächsten Schritt."
    elif ready:
        state = "READY"
        headline = "Arbeit liegt bereit"
        cause = f"{len(ready)} Aufgabe(n) sind bereit, aber aktuell noch nicht in Ausführung."
    else:
        state = "IDLE_NO_RUNNABLE_WORK"
        headline = "Autonomie ist leer gelaufen"
        if waiting_count or blocked_count:
            cause = (
                "Es gibt aktuell keine ausführbare Aufgabe. "
                f"Die Queue enthält {waiting_count} extern wartende und {blocked_count} blockierte Aufgabe(n). "
                "Eine einzelne Mail ist deshalb nicht der globale Grund für den Stillstand."
            )
        else:
            cause = "Es gibt aktuell weder aktive noch ausführbare Arbeit in der Queue."

    moves: list[dict[str, Any]] = []

    if phase == "live_measurement_window" and (
        publication_verified is False or decision_state == "waiting_first_signal" or first_signal_count == 0
    ):
        moves.append(
            {
                "id": "first_money_truth",
                "title": "First-Money-Veröffentlichung und ersten echten Messimpuls verifizieren",
                "reason": (
                    "Der Umsatztest befindet sich im Live-Messfenster, aber Veröffentlichung bzw. erster "
                    "qualifizierter Traffic ist noch nicht belastbar bestätigt."
                ),
                "master_required": False,
                "jarvis_can_execute_now": False,
            }
        )

    if internal_observer_issues:
        providers = sorted(
            {
                str(row.get("source_type") or row.get("provider") or "observer").split(":", 1)[0]
                for row in internal_observer_issues
            }
        )
        moves.append(
            {
                "id": "repair_observers",
                "title": "Interne Beobachter reparieren",
                "reason": (
                    "Mindestens ein Antwort-/Systembeobachter ist technisch gestört"
                    + (f" ({', '.join(providers)})" if providers else "")
                    + "; dafür ist keine Aktion von Master bestätigt."
                ),
                "master_required": False,
                "jarvis_can_execute_now": False,
            }
        )

    if external_without_binding:
        moves.append(
            {
                "id": "reconcile_waits",
                "title": "Alte externe Wartezustände bereinigen",
                "reason": (
                    f"{len(external_without_binding)} extern wartende Aufgabe(n) haben keinen konkreten "
                    "ungelösten Observer-Nachweis. Diese Einträge dürfen nicht als Hauptblocker behandelt werden."
                ),
                "master_required": False,
                "jarvis_can_execute_now": False,
            }
        )

    if checkpoint_stale:
        moves.append(
            {
                "id": "refresh_business_checkpoint",
                "title": "Geschäftslage neu berechnen",
                "reason": "Der letzte Business-Checkpoint ist älter als eine Stunde und taugt nicht als aktuelle Priorität.",
                "master_required": False,
                "jarvis_can_execute_now": False,
            }
        )

    if not active_count and not ready:
        moves.append(
            {
                "id": "restore_autonomy",
                "title": "Neue sinnvolle Arbeit aus dem aktuellen Geschäftsziel einplanen",
                "reason": (
                    "Der Executor kann nur bereits vorhandene Arbeit ausführen. Wenn keine passende Aufgabe "
                    "bereitsteht, muss Jarvis einen neuen internen Arbeitsplan erzeugen statt auf alte Waits zu zeigen."
                ),
                "master_required": False,
                "jarvis_can_execute_now": False,
            }
        )

    if real_owner_action:
        owner_message = "Eine bestätigte Entscheidung oder Reautorisierung von Master ist erforderlich."
    else:
        owner_message = (
            "Keine Aktion von Master erforderlich. Insbesondere ist keine Mailprüfung als Owner-Schritt belegt."
        )

    if active_count:
        jarvis_message = "Jarvis soll die laufende Arbeit überwachen und bei Abweichungen konkret eingreifen."
    elif ready:
        jarvis_message = "Jarvis kann die bereitliegende sichere Arbeit anstoßen."
    else:
        jarvis_message = (
            "Jarvis muss die Queue und Prioritäten neu aufbauen; der heutige Executor kann aus einer leergelaufenen "
            "Queue noch keine neue Geschäftstätigkeit erzeugen."
        )

    return {
        "state": state,
        "headline": headline,
        "cause": cause,
        "owner_action_required": real_owner_action,
        "owner_message": owner_message,
        "jarvis_message": jarvis_message,
        "recommended_now": moves[0] if moves else None,
        "next_moves": moves[:6],
        "evidence": {
            "active_executions": active_count,
            "ready_tasks": len(ready),
            "waiting_external_tasks": waiting_count,
            "blocked_tasks": blocked_count,
            "external_waits_with_observer": len(external_with_binding),
            "external_waits_without_observer": len(external_without_binding),
            "internal_observer_issues": len(internal_observer_issues),
            "owner_observer_issues": len(observer_owner_issues) + len(credential_owner_issues),
            "first_money_phase": phase or None,
            "first_money_decision_state": decision_state or None,
            "first_money_next_evidence": next_evidence or None,
            "first_money_publication_verified": publication_verified,
            "first_money_signal_count": first_signal_count,
            "business_checkpoint_age_seconds": checkpoint_age,
            "business_checkpoint_stale": checkpoint_stale,
        },
        "rules": {
            "external_email_is_global_blocker": False,
            "tell_master_to_check_mail_without_owner_gate": False,
            "implementation_jargon_for_owner": False,
        },
        "observed_at": now.isoformat(),
    }
