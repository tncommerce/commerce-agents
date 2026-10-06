from datetime import UTC, datetime

from retail.api.jarvis_operator import build_operator_diagnosis

NOW = datetime(2026, 10, 5, 19, 16, tzinfo=UTC)


def test_idle_queue_is_not_misdiagnosed_as_one_email_blocker():
    tasks = [
        {
            "task_id": "social",
            "title": "Social remediation",
            "status": "waiting_external",
            "priority": 100,
        },
        {
            "task_id": "dior",
            "title": "Dior rights",
            "status": "waiting_external",
            "priority": 99,
        },
        {
            "task_id": "blocked",
            "title": "Merchant coverage",
            "status": "blocked",
            "priority": 90,
        },
    ]
    waits = [
        {
            "task_id": "dior",
            "observer_id": "gmail:dior",
            "satisfied": False,
        }
    ]
    observers = [
        {
            "observer_id": "gmail:dior",
            "source_type": "gmail",
            "health_status": "blocked_configuration",
            "last_error": "credential_expired",
            "credential_health": {"owner_reauthorization_required": False},
        }
    ]
    thin = {
        "active_leases": 0,
        "queue_counts": {"waiting_external": 15, "blocked": 1},
        "business_checkpoint": {"age_seconds": 100000},
    }
    runtime = {
        "phase": "live_measurement_window",
        "decision_state": "waiting_first_signal",
        "publication_verified": False,
        "next_evidence": "qualified_session",
        "funnel": {
            "landing_sessions": 0,
            "product_views": 0,
            "offer_views": 0,
            "offer_opens": 0,
            "merchant_clickouts": 0,
        },
    }

    result = build_operator_diagnosis(
        tasks=tasks,
        waits=waits,
        observers=observers,
        credentials=[],
        thin=thin,
        runtime=runtime,
        now=NOW,
    )

    assert result["state"] == "IDLE_NO_RUNNABLE_WORK"
    assert "keine ausführbare Aufgabe" in result["cause"]
    assert "Eine einzelne Mail ist deshalb nicht der globale Grund" in result["cause"]
    assert result["owner_action_required"] is False
    assert "keine Mailprüfung" in result["owner_message"]
    assert result["evidence"]["waiting_external_tasks"] == 15
    assert result["evidence"]["external_waits_without_observer"] == 1
    assert result["evidence"]["internal_observer_issues"] == 1
    assert result["recommended_now"]["id"] == "first_money_truth"
    ids = [move["id"] for move in result["next_moves"]]
    assert ids == [
        "first_money_truth",
        "repair_observers",
        "reconcile_waits",
        "refresh_business_checkpoint",
        "restore_autonomy",
    ]


def test_owner_is_only_asked_to_act_for_a_real_gate_or_reauthorization():
    result = build_operator_diagnosis(
        tasks=[],
        waits=[],
        observers=[
            {
                "observer_id": "gmail:x",
                "source_type": "gmail",
                "health_status": "blocked_configuration",
                "last_error": "invalid_grant",
                "credential_health": {"owner_reauthorization_required": True},
            }
        ],
        credentials=[],
        thin={"active_leases": 0, "queue_counts": {}},
        runtime={},
        now=NOW,
    )

    assert result["state"] == "MASTER_ACTION_REQUIRED"
    assert result["owner_action_required"] is True
    assert "Master" in result["owner_message"]


def test_active_work_wins_over_waiting_external_noise():
    result = build_operator_diagnosis(
        tasks=[
            {"task_id": "working", "status": "working", "priority": 10},
            {"task_id": "mail", "status": "waiting_external", "priority": 100},
        ],
        waits=[{"task_id": "mail", "observer_id": "gmail:x", "satisfied": False}],
        observers=[],
        credentials=[],
        thin={"active_leases": 1, "queue_counts": {"waiting_external": 1}},
        runtime={},
        now=NOW,
    )

    assert result["state"] == "WORKING"
    assert result["evidence"]["active_executions"] == 1
    assert result["owner_action_required"] is False

def test_scheduled_safe_work_is_not_reported_as_empty_autonomy():
    result = build_operator_diagnosis(
        tasks=[
            {
                "task_id": "old-wait",
                "status": "waiting_external",
                "priority": 90,
            }
        ],
        waits=[],
        observers=[],
        credentials=[],
        thin={
            "active_leases": 0,
            "stop_reason": "no_safe_work",
            "queue_counts": {"waiting_external": 15},
            "planner": {
                "state": "scheduled_safe_work",
                "next_safe_work_at": "2026-10-06T13:40:00+00:00",
                "ready_certified_free_tasks": 0,
                "external_waits_are_global_blocker": False,
            },
        },
        runtime={
            "phase": "live_measurement_window",
            "decision_state": "waiting_first_signal",
            "next_evidence": "qualified_session",
            "funnel": {},
        },
        now=NOW,
    )

    assert result["state"] == "SCHEDULED_SAFE_WORK"
    assert result["headline"] == "Nächste sichere Arbeit ist geplant"
    assert "2026-10-06T13:40:00+00:00" in result["cause"]
    assert result["owner_action_required"] is False
    assert "geplanten Fälligkeitspunkt" in result["jarvis_message"]
    assert result["evidence"]["planner_state"] == "scheduled_safe_work"
    assert result["rules"]["external_waits_are_global_blocker"] is False
    assert "restore_autonomy" not in [move["id"] for move in result["next_moves"]]

