from __future__ import annotations

import httpx
import pytest

from retail.api.jarvis_safe_actions import (
    JarvisSafeActionConflict,
    JarvisSafeActionRunner,
)


def test_safe_action_runner_calls_only_certified_thin_v1_and_sanitizes_gate_tokens():
    seen = {}

    def transport(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "stop_reason": "owner_gate",
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
        "path": "/rest/v1/rpc/run_dufynd_thin_v1",
        "body": "{}",
    }
    assert result["stop_reason"] == "owner_gate"
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
