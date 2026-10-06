"""Deterministic CEO-level diagnosis for Jarvis and the Control Room.

This module does not dispatch work. It explains the real operating state in plain
business language and separates internal system faults from genuine Master actions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

ACTIVE_STATES = {
    "claimed",
    "working",
    "verifying",
    "in_progress",
    "running",
    "dispatched",
}
OWNER_STATES = {"approval_required", "waiting_human_input", "waiting_human"}
READY_STATES = {"ready", "queued"}
UNHEALTHY_OBSERVERS = {
    "blocked_configuration",
    "blocked",
    "degraded",
    "stale",
    "unknown",
}


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
    if value in {
        "credential_expired",
        "invalid_grant",
        "purchase_target_disabled",
        "purchase_target_missing",
    }:
        return str(value)
    return None


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
    owner_tasks = [task for task in tasks if _status(task) in OWNER_STATES]
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
    internal_observer_issues = [row for row in bad_observers if not _credential_owner_action(row)]
    observer_owner_issues = [row for row in bad_observers if _credential_owner_action(row)]

    credential_owner_issues = [
        row for row in credentials if isinstance(row, dict) and _credential_owner_action(row)
    ]

    pending_gates = thin.get("pending_owner_gates")
    pending_gates = pending_gates if isinstance(pending_gates, list) else []
    real_owner_action = bool(
        owner_tasks or pending_gates or observer_owner_issues or credential_owner_issues
    )

    active_leases = _int(thin.get("active_leases"))
    active_count = active_leases if active_leases and not active else len(active)

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
        for key in (
            "landing_sessions",
            "product_views",
            "offer_views",
            "offer_opens",
            "merchant_clickouts",
        )
    )

    business_checkpoint = thin.get("business_checkpoint")
    business_checkpoint = business_checkpoint if isinstance(business_checkpoint, dict) else {}
    checkpoint_age = business_checkpoint.get("age_seconds")
    checkpoint_stale = isinstance(checkpoint_age, (int, float)) and checkpoint_age > 3600

    planner = thin.get("planner")
    planner = planner if isinstance(planner, dict) else {}
    planner_state = str(planner.get("state") or "")
    planner_next_safe_work_at = planner.get("next_safe_work_at")
    planner_ready_free = _int(planner.get("ready_certified_free_tasks"))
    planner_external_waits_block = planner.get("external_waits_are_global_blocker") is True

    business_planner = thin.get("business_planner")
    business_planner = business_planner if isinstance(business_planner, dict) else {}
    business_planner_state = str(business_planner.get("state") or "")
    business_next_move = str(business_planner.get("business_next_move") or "")
    business_planner_requires_master = business_planner.get("master_action_required") is True
    planner_gap = business_planner_state == "planner_gap" and not business_planner_requires_master
    business_move_label = {
        "social_publication_readiness": "die heutige Social-Publishing-Bereitschaft",
        "qualified_traffic_generation": "die Erzeugung qualifizierten Traffics",
        "funnel_conversion_readiness": "die nächste Funnel-Optimierung",
        "business_reprioritization": "die nächste Geschäftspriorität",
    }.get(business_next_move, "den nächsten Geschäftsschritt")

    if active_count:
        state = "WORKING"
        headline = "Arbeit läuft"
        cause = f"{active_count} Ausführung(en) sind aktuell aktiv."
    elif real_owner_action:
        state = "MASTER_ACTION_REQUIRED"
        headline = "Eine echte Master-Entscheidung fehlt"
        cause = (
            "Eine bestätigte Entscheidung oder Reautorisierung blockiert einen "
            "konkreten nächsten Schritt."
        )
    elif planner_state == "work_ready" or (
        ready and str(thin.get("stop_reason") or "") not in {"waiting_external", "no_safe_work"}
    ):
        state = "READY"
        headline = "Arbeit liegt bereit"
        ready_count = max(len(ready), planner_ready_free)
        cause = (
            f"{ready_count} zertifizierte kostenlose Aufgabe(n) sind bereit, "
            "aber aktuell noch nicht in Ausführung."
        )
    elif planner_gap:
        state = "PLANNING_REQUIRED"
        headline = "Neue sichere Arbeit muss geplant werden"
        cause = (
            f"Der Business-Planner hat {business_move_label} als nächsten Schritt erkannt, "
            "aber dafür existiert noch kein zertifizierter kostenloser interner Ausführungspfad. "
            "Ein späterer Wartungscheck ersetzt diese Planung nicht."
        )
    elif planner_state == "scheduled_safe_work":
        state = "SCHEDULED_SAFE_WORK"
        headline = "Nächste sichere Arbeit ist geplant"
        cause = (
            "Aktuell ist kein zertifizierter kostenloser Task fällig. "
            f"Der nächste sichere Check ist für {planner_next_safe_work_at or 'den nächsten Fälligkeitspunkt'} geplant. "
            "Alte externe Wartezustände blockieren diesen Plan nicht."
        )
    elif planner_state == "waiting_for_business_signal":
        state = "WAITING_FOR_BUSINESS_SIGNAL"
        headline = "Jarvis überwacht das nächste Geschäftssignal"
        cause = (
            "Aktuell ist keine sichere Ausführung fällig. Jarvis wartet nicht auf Master, "
            "sondern auf das nächste belastbare First-Money-Signal."
        )
    else:
        state = "IDLE_NO_RUNNABLE_WORK"
        headline = "Aktuell keine sichere Arbeit fällig"
        if waiting_count or blocked_count:
            cause = (
                "Es gibt aktuell keine ausführbare Aufgabe. "
                f"Die Arbeitsliste enthält {waiting_count} extern wartende und {blocked_count} blockierte Aufgabe(n). "
                "Diese Einträge sind kein globaler Blocker."
            )
        else:
            cause = "Es gibt aktuell weder aktive noch ausführbare Arbeit in der Queue."

    moves: list[dict[str, Any]] = []

    if planner_gap:
        moves.append(
            {
                "id": "plan_business_priority",
                "title": "Sichere Arbeit aus der aktuellen Geschäftspriorität erzeugen",
                "reason": (
                    f"Jarvis hat {business_move_label} als nächsten Geschäftsschritt erkannt, "
                    "aber noch keinen zertifizierten kostenlosen internen Ausführungspfad dafür."
                ),
                "master_required": False,
                "jarvis_can_execute_now": False,
            }
        )

    if phase == "live_measurement_window" and (
        publication_verified is False
        or decision_state == "waiting_first_signal"
        or first_signal_count == 0
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
                "reason": (
                    "Der letzte Business-Checkpoint ist älter als eine Stunde und taugt "
                    "nicht als aktuelle Priorität."
                ),
                "master_required": False,
                "jarvis_can_execute_now": False,
            }
        )

    if (
        not active_count
        and not ready
        and not planner_gap
        and planner_state not in {"scheduled_safe_work", "waiting_for_business_signal"}
    ):
        moves.append(
            {
                "id": "restore_autonomy",
                "title": "Neue sinnvolle Arbeit aus dem aktuellen Geschäftsziel einplanen",
                "reason": (
                    "Es ist weder aktuelle noch bereits terminierte sichere Arbeit vorhanden. "
                    "Jarvis muss aus dem Geschäftsziel einen neuen internen Arbeitsplan erzeugen."
                ),
                "master_required": False,
                "jarvis_can_execute_now": False,
            }
        )

    if real_owner_action:
        owner_message = (
            "Eine bestätigte Entscheidung oder Reautorisierung von Master ist erforderlich."
        )
    else:
        owner_message = (
            "Keine Aktion von Master erforderlich. Insbesondere ist keine Mailprüfung "
            "als notwendige Master-Aktion belegt."
        )

    if active_count:
        jarvis_message = (
            "Jarvis soll die laufende Arbeit überwachen und bei Abweichungen konkret eingreifen."
        )
    elif state == "READY":
        jarvis_message = "Jarvis kann die bereitliegende sichere Arbeit anstoßen."
    elif state == "PLANNING_REQUIRED":
        jarvis_message = (
            "Jarvis muss aus der aktuellen Geschäftspriorität sichere interne Arbeit erzeugen; "
            "der spätere Wartungscheck ist zusätzlich sinnvoll, aber kein Ersatz dafür."
        )
    elif state == "SCHEDULED_SAFE_WORK":
        jarvis_message = (
            "Jarvis überwacht die First-Money-Signale und führt den nächsten zertifizierten "
            "kostenlosen Check zum geplanten Fälligkeitspunkt aus."
        )
    elif state == "WAITING_FOR_BUSINESS_SIGNAL":
        jarvis_message = (
            "Jarvis überwacht das nächste belastbare Geschäftssignal; Master muss dafür nichts tun."
        )
    else:
        jarvis_message = (
            "Jarvis muss Arbeitsliste und Prioritäten neu aufbauen, weil weder aktuelle "
            "noch terminierte sichere Arbeit vorhanden ist."
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
            "planner_state": planner_state or None,
            "planner_next_safe_work_at": planner_next_safe_work_at,
            "planner_ready_certified_free_tasks": planner_ready_free,
            "business_planner_state": business_planner_state or None,
            "business_planner_next_move": business_next_move or None,
        },
        "rules": {
            "external_email_is_global_blocker": False,
            "external_waits_are_global_blocker": planner_external_waits_block,
            "tell_master_to_check_mail_without_owner_gate": False,
            "implementation_jargon_for_owner": False,
        },
        "observed_at": now.isoformat(),
    }
