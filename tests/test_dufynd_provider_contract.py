from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from threading import Barrier

import httpx
import pytest
from scripts.dufynd_bounded_provider import BoundedProviderAdapter, BudgetGate
from scripts.dufynd_messages_transport import SimulatedMessagesProvider, prepare_http_request
from scripts.dufynd_provider_contract import (
    build_bounded_request,
    calculate_worst_case_cost,
    load_contract,
    validate_bounded_request,
)
from tests.test_dufynd_bounded_provider import Ledger


def fixture():
    c = load_contract("simulated-messages-v1")
    return c, build_bounded_request(c, system="system", prompt="test €")


def provider(c, request, *, usage=None, handler=None):
    def response(wire):
        assert wire.url == "https://api.anthropic.com/v1/messages"
        assert wire.headers["anthropic-version"] == "2023-06-01"
        assert wire.content == request.payload
        return httpx.Response(
            200,
            json={
                "model": c.model,
                "id": "simulated-receipt",
                "content": [{"type": "text", "text": "fake only"}],
                "usage": usage or {"input_tokens": request.input_tokens, "output_tokens": 8},
            },
        )

    return SimulatedMessagesProvider(c, httpx.MockTransport(handler or response))


def execute(store, p, request, key="one"):
    return BoundedProviderAdapter(store, p).execute(
        request,
        budget_id="simulation",
        task_id="task",
        worker_owner="owner",
        lease_token="lease",
        idempotency_key=key,
    )


def test_exact_contract_central_price_and_token_count():
    c, r = fixture()
    assert r.input_tokens == len("systemtest €".encode()) + 8
    assert calculate_worst_case_cost(c) == Decimal("0.000896")
    assert validate_bounded_request(r) == Decimal("0.000896")
    body = json.loads(prepare_http_request(r, api_key="not-a-real-key").content)
    assert body["max_tokens"] == 64 and body["thinking"] == {"type": "disabled"}
    assert body["service_tier"] == "standard_only" and body["inference_geo"] == "global"
    assert "tools" not in body and "cache_control" not in body and body["stream"] is False


@pytest.mark.parametrize("length", [121, 32769])
def test_input_limit_rejected_without_dispatch_or_truncation(length):
    c, r = fixture()
    p = provider(c, r)
    with pytest.raises(BudgetGate, match="input_limit_exceeded"):
        build_bounded_request(c, system="", prompt="x" * length)
    assert p.calls == 0
    assert build_bounded_request(c, system="", prompt="x" * 120).input_tokens == 128


@pytest.mark.parametrize(
    "change",
    [
        {"hard_output_limit": False},
        {"output_includes_reasoning": False},
        {"model": "unknown"},
        {"input_usd_per_token": None},
        {"output_usd_per_token": None},
        {"unit_price_ceiling_certified": False},
        {"input_bound_certified": False},
        {"other_class_limits": (("server_tool_requests", 1),)},
        {"max_output_tokens": None},
        {"input_usd_per_token": Decimal("NaN")},
    ],
)
def test_unknown_or_forged_bounds_fail_closed(change):
    c, r = fixture()
    p = provider(c, r)
    with pytest.raises(BudgetGate, match="BOUND_UNKNOWN"):
        build_bounded_request(replace(c, **change), system="", prompt="test")
    assert p.calls == 0


@pytest.mark.parametrize(
    "name", ["anthropic-sonnet5-direct-v1", "openrouter-sonnet5-candidate-v1", "unknown"]
)
def test_real_provider_contracts_remain_uncertified(name):
    with pytest.raises(BudgetGate, match="BOUND_UNKNOWN"):
        build_bounded_request(load_contract(name), system="", prompt="test")


def test_no_network_transport_factory_or_env_bypass(monkeypatch):
    c, r = fixture()
    monkeypatch.setenv("DUFYND_PAID_CANARY_APPROVED", "true")
    with pytest.raises(BudgetGate, match="paid_transport_disabled"):
        SimulatedMessagesProvider(c, httpx.HTTPTransport())
    p = provider(c, r)
    p.transport = httpx.HTTPTransport()
    with pytest.raises(BudgetGate, match="paid_transport_disabled"):
        p.call(r)
    assert p.calls == 0


def test_sufficient_budget_reserve_dispatch_settlement_evidence():
    c, r = fixture()
    maximum = calculate_worst_case_cost(c)
    store, p = Ledger(cap=str(maximum)), provider(c, r)
    result = execute(store, p, r)
    assert result.cost_usd == r.input_tokens * Decimal("0.000002") + 8 * Decimal("0.000010")
    assert result.cost_usd < maximum
    assert p.calls == 1 and store.rows["one"]["status"] == "settled"
    evidence = store.rows["one"]["evidence"]["bound_and_usage"]
    assert evidence["catalog_digest"] == c.catalog_digest
    assert evidence["worst_case_cost_usd"] == str(maximum)
    assert evidence["request_hash"] == r.fingerprint()


def test_one_microdollar_above_remaining_rejected_before_http():
    c, r = fixture()
    store = Ledger(cap=str(calculate_worst_case_cost(c) - Decimal("0.000001")))
    p = provider(c, r)
    with pytest.raises(BudgetGate, match="budget_exhausted"):
        execute(store, p, r)
    assert p.calls == 0 and not store.rows


def test_parallel_calls_and_retry_use_existing_single_dispatch():
    c, r = fixture()
    store = Ledger(cap=str(calculate_worst_case_cost(c)))
    p = provider(c, r, usage={"input_tokens": r.input_tokens, "output_tokens": 64})
    barrier = Barrier(2)

    def attempt(key):
        barrier.wait(timeout=5)
        try:
            execute(store, p, r, key)
            return True
        except BudgetGate:
            return False

    # Both may fit sequentially after cheap settlement; use two distinct claims
    # with a total cap below the sum of actual costs so only one can win.
    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(attempt, ["one", "two"])) == 1
    key = next(iter(store.rows))
    with pytest.raises(BudgetGate):
        execute(store, p, r, key)
    assert p.calls == 1


def test_forged_payload_count_and_extra_tools_rejected_before_reserve():
    c, r = fixture()
    p = provider(c, r)
    body = json.loads(r.payload)
    body["tools"] = [{"type": "web_search"}]
    for forged in (replace(r, input_tokens=0), replace(r, payload=json.dumps(body).encode())):
        store = Ledger()
        with pytest.raises(BudgetGate, match="BOUND_UNKNOWN"):
            execute(store, p, forged)
        assert not store.rows
    assert p.calls == 0


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": 22, "output_tokens": 65},
        {"input_tokens": 22, "output_tokens": 8, "cache_creation_input_tokens": 1},
        {"input_tokens": 22, "output_tokens": 8, "server_tool_use": {"web_search_requests": 1}},
        {"input_tokens": 22, "output_tokens": 8, "output_tokens_details": {"thinking_tokens": 9}},
        {"output_tokens": 8},
    ],
)
def test_unknown_usage_charges_maximum_and_never_retries(usage):
    c, r = fixture()
    store, p = Ledger(), provider(c, r, usage=usage)
    with pytest.raises(BudgetGate):
        execute(store, p, r)
    assert store.spent == calculate_worst_case_cost(c)
    assert p.calls == 1
    with pytest.raises(BudgetGate):
        execute(store, p, r)
    assert p.calls == 1


def test_reasoning_is_subset_of_output_not_unbounded_extra_fee():
    c, r = fixture()
    p = provider(
        c,
        r,
        usage={
            "input_tokens": r.input_tokens,
            "output_tokens": 64,
            "output_tokens_details": {"thinking_tokens": 50},
        },
    )
    assert execute(Ledger(), p, r).cost_usd <= calculate_worst_case_cost(c)


def test_historical_nightshift_still_blocked_before_mock_transport():
    c, r = fixture()
    p = provider(c, r)
    with pytest.raises(BudgetGate):
        execute(Ledger(cap="2.50", spent="2.504685399999999955"), p, r)
    assert p.calls == 0
    # The actual legacy model cannot prepare a call, even with unlimited money.
    with pytest.raises(BudgetGate, match="BOUND_UNKNOWN"):
        build_bounded_request(
            load_contract("anthropic-sonnet5-direct-v1"), system="", prompt="legacy task"
        )


def test_crash_before_reservation_creates_no_claim_or_dispatch():
    c, r = fixture()
    store, p = Ledger(), provider(c, r)

    def crash(**kwargs):
        raise RuntimeError("crash before reservation commit")

    store.reserve_model_call = crash
    with pytest.raises(RuntimeError):
        execute(store, p, r)
    assert not store.rows and p.calls == 0


def test_unclear_provider_response_charged_max_without_hidden_retry():
    c, r = fixture()
    store = Ledger()

    def lost_response(wire):
        assert store.rows["one"]["status"] == "dispatched"
        raise httpx.ReadTimeout("simulated unknown response", request=wire)

    p = provider(c, r, handler=lost_response)
    with pytest.raises(httpx.ReadTimeout):
        execute(store, p, r)
    assert p.calls == 1 and store.spent == calculate_worst_case_cost(c)
    with pytest.raises(BudgetGate):
        execute(store, p, r)
    assert p.calls == 1


def test_fully_simulated_canary_does_not_simulate_owner_approval():
    from scripts.dufynd_simulated_provider_canary import simulate_canary

    result = simulate_canary()
    assert result["real_provider_calls"] == 0 and result["real_cost_usd"] == "0"
    assert result["reservation_status"] == "settled"
    assert result["owner_approval_created_or_simulated"] is False
    assert result["trace"] == [
        "build_bounded_request",
        "calculate_worst_case_cost",
        "atomic_reserve_mock",
        "single_dispatch_mock",
        "fake_provider_http",
        "actual_usage_settlement_mock",
    ]
