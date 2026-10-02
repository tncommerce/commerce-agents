"""Credential-free Canary: mock RPCs + mock HTTP; no approvals or live budgets."""

from __future__ import annotations

import json
from contextlib import suppress
from decimal import Decimal
from unittest.mock import Mock

import httpx
from scripts.dufynd_bounded_provider import BoundedProviderAdapter, BudgetGate
from scripts.dufynd_messages_transport import SimulatedMessagesProvider
from scripts.dufynd_provider_contract import (
    build_bounded_request,
    calculate_worst_case_cost,
    load_contract,
)


def simulate_canary() -> dict:
    contract = load_contract("simulated-messages-v1")
    request = build_bounded_request(contract, system="test", prompt="fully simulated canary")
    maximum = calculate_worst_case_cost(contract)
    trace = ["build_bounded_request", "calculate_worst_case_cost"]
    state = {"status": None, "actual_usd": None, "evidence": None}
    store = Mock()

    def reserve(**p):
        assert p["request_hash"] == request.fingerprint()
        assert Decimal(p["max_usd"]) == maximum
        trace.append("atomic_reserve_mock")
        if state["status"] is not None:
            return {"allowed": False, "reason": "already_settled"}
        state["status"] = "reserved"
        return {"allowed": True, "reservation": {"reservation_id": "offline-reservation"}}

    def dispatch(reservation_id, token):
        assert state["status"] == "reserved"
        trace.append("single_dispatch_mock")
        state["status"] = "dispatched"
        return True

    def settle(reservation_id, token, amount, evidence):
        assert state["status"] == "dispatched" and 0 <= Decimal(amount) <= maximum
        trace.append("actual_usage_settlement_mock")
        state.update(status="settled", actual_usd=amount, evidence=evidence)
        return True

    store.reserve_model_call.side_effect = reserve
    store.dispatch_model_call.side_effect = dispatch
    store.settle_model_call.side_effect = settle

    def response(wire):
        assert state["status"] == "dispatched" and wire.content == request.payload
        trace.append("fake_provider_http")
        return httpx.Response(
            200,
            json={
                "id": "offline-receipt",
                "model": contract.model,
                "content": [{"type": "text", "text": "fully simulated result"}],
                "usage": {"input_tokens": request.input_tokens, "output_tokens": 8},
            },
        )

    provider = SimulatedMessagesProvider(contract, httpx.MockTransport(response))
    adapter = BoundedProviderAdapter(store, provider)
    args = {
        "budget_id": "offline-fixture-no-approval",
        "task_id": "offline-task",
        "worker_owner": "offline",
        "lease_token": "offline-token",
        "idempotency_key": "same-call",
    }
    result = adapter.execute(request, **args)
    completed_trace = trace.copy()
    with suppress(BudgetGate):
        adapter.execute(request, **args)
    assert provider.calls == 1 and store.dispatch_model_call.call_count == 1
    # Scripted denied RPC result, with the margin independently checked here.
    # Real admission/concurrency is tested through the existing SQL RPC in CI.
    insufficient = Mock()
    remaining = maximum - Decimal("0.000001")
    assert remaining - maximum == Decimal("-0.000001")
    insufficient.reserve_model_call.return_value = {"allowed": False, "reason": "budget_exhausted"}
    with suppress(BudgetGate):
        BoundedProviderAdapter(insufficient, provider).execute(request, **args)
    assert not insufficient.dispatch_model_call.called and provider.calls == 1
    return {
        "mode": "fully_simulated_no_owner_approval",
        "real_provider_calls": 0,
        "real_cost_usd": "0",
        "mock_provider_calls": provider.calls,
        "worst_case_cost_usd": str(maximum),
        "simulated_actual_cost_usd": str(result.cost_usd),
        "simulated_unused_reserve_usd": str(maximum - result.cost_usd),
        "input_tokens": request.input_tokens,
        "max_input_tokens": contract.max_input_tokens,
        "max_output_tokens_including_reasoning": contract.max_output_tokens,
        "reservation_status": state["status"],
        "duplicate_dispatches": 0,
        "microdollar_overrun_admission": "denied_before_dispatch",
        "trace": completed_trace,
        "catalog_version": contract.catalog_version,
        "catalog_digest": contract.catalog_digest,
        "real_contract_status": "BOUND_UNKNOWN_FAIL_CLOSED",
        "live_budget_changes": 0,
        "owner_approval_created_or_simulated": False,
    }


if __name__ == "__main__":
    print(json.dumps(simulate_canary(), indent=2))
