from __future__ import annotations

import httpx
import pytest

from retail.api.jarvis_safe_actions import (
    JarvisSafeActionConflict,
    JarvisSafeActionRunner,
)


def test_safe_action_runner_calls_certified_ceo_cycle_and_sanitizes_gate_tokens():
    seen = {}

    def transport(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "stop_reason": "owner_gate",
                "state": "no_certified_work",
                "plan_state": "owner_gate",
                "waiting_external_total": 14,
                "next_evidence": "qualified_session",
                "paid_calls": 0,
                "new_spend_usd": 0,
                "owner_gate_action_executed": False,
                "completed": [],
                "queue_counts": {"ready": 1, "waiting_human_input": 1},
                "pending_owner_gates": [
                    {
                        "decision_id": "thin-gate:task:abc",
                        "decision_token": "GO-SECRET-NOT-FOR-VOICE",
                        "action_type": "publication_approval",
                    }
                ],
                "active_leases": 0,
                "stale_leases": 0,
                "provider_cost_unknown": False,
            },
        )

    runner = JarvisSafeActionRunner(
        secret_key="server-secret",
        transport=httpx.MockTransport(transport),
    )
    result = runner.advance_next_safe_work()

    assert seen == {
        "method": "POST",
        "path": "/rest/v1/rpc/run_dufynd_ceo_safe_cycle_v1",
        "body": "{}",
    }
    assert result["stop_reason"] == "owner_gate"
    assert result["state"] == "no_certified_work"
    assert result["plan_state"] == "owner_gate"
    assert result["source"] == "dufynd_ceo_certified_free_orchestrator"
    assert result["waiting_external_total"] == 14
    assert result["next_evidence"] == "qualified_session"
    assert result["paid_calls"] == 0
    assert result["new_spend_usd"] == 0
    assert result["pending_owner_gates"] == [
        {
            "decision_id": "thin-gate:task:abc",
            "action_type": "publication_approval",
        }
    ]
    assert "decision_token" not in str(result)


@pytest.mark.parametrize(
    "payload",
    [
        {"paid_calls": 1, "owner_gate_action_executed": False},
        {"paid_calls": 0, "new_spend_usd": 0.01, "owner_gate_action_executed": False},
        {"paid_calls": 0, "new_spend_usd": 0, "owner_gate_action_executed": True},
    ],
)
def test_safe_action_runner_fails_closed_on_forbidden_execution_evidence(payload):
    def transport(_request):
        return httpx.Response(200, json=payload)

    runner = JarvisSafeActionRunner(
        secret_key="server-secret",
        transport=httpx.MockTransport(transport),
    )
    with pytest.raises(JarvisSafeActionConflict):
        runner.advance_next_safe_work()

def test_safe_action_runner_returns_actual_completed_growth_work_not_just_no_work():
    def transport(_request):
        return httpx.Response(
            200,
            json={
                "state": "completed",
                "stop_reason": "one_safe_task_completed",
                "task_id": "ceo:distribution-preflight:known",
                "handler": "ceo_distribution_preflight_v2",
                "worker_status": "completed",
                "action": "distribution_packet_prepared",
                "selected_asset_id": "asset_one_night_fourteen_perfumes_20261008_v1",
                "next_step": "Transfer and QA media, then get an explicit publishing GO.",
                "owner_action_required": True,
                "paid_calls": 0,
                "new_spend_usd": 0,
                "owner_gate_action_executed": False,
                "completed": [
                    {
                        "task_id": "ceo:distribution-preflight:known",
                        "status": "completed",
                        "handler": "ceo_distribution_preflight_v2",
                    }
                ],
            },
        )

    runner = JarvisSafeActionRunner(
        secret_key="server-secret", transport=httpx.MockTransport(transport)
    )
    result = runner.advance_next_safe_work()
    assert result["state"] == "completed"
    assert result["handler"] == "ceo_distribution_preflight_v2"
    assert result["action"] == "distribution_packet_prepared"
    assert result["selected_asset_id"] == "asset_one_night_fourteen_perfumes_20261008_v1"
    assert result["owner_action_required"] is True
    assert "explicit publishing GO" in result["next_step"]
    assert result["new_spend_usd"] == 0
