from __future__ import annotations

import httpx

from retail.api.jarvis_truth import JarvisTruthReader


def test_truth_reader_reports_exact_waits_priorities_and_sanitized_gates():
    def transport(request):
        path = request.url.path
        if path == "/rest/v1/dufynd_autonomy_tasks":
            return httpx.Response(
                200,
                json=[
                    {
                        "task_id": "task_external_confirmed",
                        "domain": "content",
                        "title": "Wait for platform evidence",
                        "status": "waiting_external",
                        "priority": 100,
                        "budget_class": "free",
                        "requires_human_approval": False,
                        "approval_action_type": None,
                        "worker_state": "waiting_external",
                        "last_progress_at": "2026-10-05T18:00:00Z",
                        "lease_expires_at": None,
                        "dependencies": [],
                        "external_review_required": False,
                        "needs_freshness_recheck": False,
                        "provider_cost_unknown": False,
                        "durable_payload": None,
                    },
                    {
                        "task_id": "task_external_unproven",
                        "domain": "affiliate",
                        "title": "External state without wait row",
                        "status": "waiting_external",
                        "priority": 99,
                        "budget_class": "free",
                        "requires_human_approval": False,
                        "approval_action_type": None,
                        "worker_state": "waiting_external",
                        "last_progress_at": None,
                        "lease_expires_at": None,
                        "dependencies": [],
                        "external_review_required": False,
                        "needs_freshness_recheck": False,
                        "provider_cost_unknown": False,
                        "durable_payload": None,
                    },
                    {
                        "task_id": "task_safe_ready",
                        "domain": "supervisor",
                        "title": "Run certified state audit",
                        "status": "ready",
                        "priority": 90,
                        "budget_class": "free",
                        "requires_human_approval": False,
                        "approval_action_type": None,
                        "worker_state": "queued",
                        "last_progress_at": None,
                        "lease_expires_at": None,
                        "dependencies": [],
                        "external_review_required": False,
                        "needs_freshness_recheck": False,
                        "provider_cost_unknown": False,
                        "durable_payload": {"kind": "supervisor_state_audit"},
                    },
                ],
            )
        if path == "/rest/v1/dufynd_task_external_waits":
            return httpx.Response(
                200,
                json=[
                    {
                        "task_id": "task_external_confirmed",
                        "observer_id": "gmail:abc",
                        "event_types": ["gmail.message.received"],
                        "expected_sha": None,
                        "policy": "review",
                        "satisfied": False,
                        "last_event_id": None,
                        "reevaluated_at": None,
                    }
                ],
            )
        if path == "/rest/v1/dufynd_master_status":
            return httpx.Response(
                200,
                json=[
                    {
                        "key": "jarvis.thin_v1.config",
                        "value": {"enabled": True},
                        "last_verified_at": "2026-10-05T18:10:00Z",
                    },
                    {
                        "key": "jarvis.thin_v1.first_money_schedule_observation",
                        "value": {
                            "observed_at": "2026-10-05T05:31:41Z",
                            "posts": [
                                {
                                    "platform": "tiktok",
                                    "status": "PENDING",
                                    "scheduled_at": "2026-10-05T18:00:00+02:00",
                                    "auto_publish": True,
                                }
                            ],
                        },
                        "last_verified_at": "2026-10-05T05:31:41Z",
                    },
                    {
                        "key": "first_money.social_quality_incident.20261005",
                        "value": {
                            "tiktok_state": "stopped_before_publish",
                            "tiktok_draft": True,
                            "tiktok_autopublish": False,
                        },
                        "last_verified_at": "2026-10-05T10:40:31Z",
                    },
                    {
                        "key": "jarvis.thin_v1.status",
                        "value": {
                            "stop_reason": "waiting_external",
                            "queue_counts": {"ready": 1, "waiting_external": 2},
                            "active_leases": 0,
                            "stale_leases": 0,
                            "provider_cost_unknown": False,
                            "pending_owner_gates": [],
                            "observer_health": [
                                {
                                    "observer_id": "gmail:abc",
                                    "source_type": "gmail",
                                    "health_status": "blocked_configuration",
                                    "last_error": "credential_expired",
                                    "credential_health": {"owner_reauthorization_required": False},
                                }
                            ],
                            "business_checkpoint": {"age_seconds": 7200},
                            "first_money_runtime": {
                                "phase": "live_measurement_window",
                                "decision_state": "waiting_first_signal",
                                "publication_verified": False,
                                "funnel": {
                                    "landing_sessions": 0,
                                    "product_views": 0,
                                    "offer_views": 0,
                                    "offer_opens": 0,
                                    "merchant_clickouts": 0,
                                },
                            },
                            "ci": {"ready": True, "reason": "ci_observed"},
                        },
                        "last_verified_at": "2026-10-05T18:11:00Z",
                    },
                ],
            )
        raise AssertionError(path)

    reader = JarvisTruthReader(
        secret_key="server-secret",
        transport=httpx.MockTransport(transport),
    )
    result = reader.inspect(area="overview", focus="robin")

    assert result["verified"] is True
    assert result["focus_match"] is False
    assert result["thin_v1"]["stop_reason"] == "waiting_external"
    assert result["thin_v1"]["pending_owner_gates"] == []
    assert "decision_token" not in str(result)
    assert result["operator_diagnosis"]["state"] == "IDLE_NO_RUNNABLE_WORK"
    assert result["operator_diagnosis"]["owner_action_required"] is False
    assert "keine ausführbare Aufgabe" in result["operator_diagnosis"]["cause"]
    assert result["operator_diagnosis"]["recommended_now"]["id"] == "first_money_truth"

    tasks = {task["task_id"]: task for task in result["tasks"]}
    assert tasks["task_external_confirmed"]["evidence_state"] == "confirmed_external_wait"
    assert tasks["task_external_confirmed"]["external_waits"][0]["observer_id"] == "gmail:abc"
    assert tasks["task_external_unproven"]["evidence_state"] == "external_wait_reason_not_verified"
    assert tasks["task_safe_ready"]["certified_free_handler"] is True
    assert result["priority"]["highest_priority_task"]["task_id"] == "task_external_confirmed"
    assert result["priority"]["certified_safe_ready"][0]["task_id"] == "task_safe_ready"
