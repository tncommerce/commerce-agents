"""No network or paid generation: exact-payload HTTP mocks and conservative billing tests."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from scripts import dufynd_anthropic_counted as c
from scripts.dufynd_bounded_provider import BudgetGate


def response(**usage):
    return {
        "id": "msg_mock",
        "model": c.MODEL,
        "content": [{"type": "text", "text": "draft"}],
        "usage": {"input_tokens": 120, "output_tokens": 10, **usage},
    }


class Bridge:
    def __init__(self):
        self.allowed = True
        self.sent = False
        self.settlements = []
        self.amount = "1"
        self.runs = 3

    def _rpc(self, name, args):
        if name == "resolve_dufynd_nightshift_budget":
            return {
                "allowed": self.allowed,
                "reason": "no_approved_budget",
                "budget": self.load_budget_status("new"),
            }
        if name == "dispatch_dufynd_counted_call":
            if self.sent:
                return False
            self.sent = True
            return True
        if name == "settle_dufynd_counted_call":
            self.settlements.append(args)
            return True
        raise AssertionError(name)

    def load_budget_status(self, budget_id):
        return {
            "budget_id": budget_id,
            "can_run": self.allowed,
            "remaining_usd": self.amount,
            "remaining_runs": self.runs,
        }

    def reserve_model_call(self, **kwargs):
        self.reservation = kwargs
        return {"allowed": True, "reservation": {"reservation_id": "mock-rid"}}


TASK = {"task_id": "task", "worker_owner": "mock", "lease_token": "mock-token"}


def execute(client, bridge, prepared=None):
    return client.execute(
        bridge, prepared or c.prepare("draft", 100), task=TASK, budget_id="new", key="once"
    )


def test_current_official_contract_and_separate_estimate_policy():
    assert c.pricing()["estimate_is_exact"] is False
    assert c.pricing()["rates_usd_per_million"]["input"] == "2"
    with pytest.raises(BudgetGate):
        c.pricing(datetime.now(UTC) + timedelta(days=2))


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider", "unknown"),
        ("model", "unknown"),
        ("margin_multiplier", "1"),
        ("max_output_tokens", 9999),
    ],
)
def test_unknown_or_tampered_contract(monkeypatch, tmp_path, field, value):
    data = c.pricing()
    data[field] = value
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(c, "PRICING", path)
    with pytest.raises(BudgetGate):
        c.pricing()


@pytest.mark.parametrize("estimate", [0, 1, 100, 6451])
def test_estimate_margin_output_hard_cap(estimate):
    p = c.prepare("bounded draft", estimate)
    proof = c.validate(p)
    assert proof["input_bound_tokens"] == (estimate * 5 + 3) // 4 + 128
    assert Decimal(proof["calculated_max_usd"]) <= p.reservation_usd
    assert 1 <= json.loads(p.payload)["max_tokens"] <= 2048


def test_reservation_limits_output_and_overlarge_input_denied():
    p = c.prepare("draft", 100, Decimal("0.001"))
    assert json.loads(p.payload)["max_tokens"] == 49
    for estimate, amount in [
        (8192, c.MAX_REQUEST_USD),
        (100, Decimal("0.0001")),
        (1, Decimal("1")),
    ]:
        with pytest.raises(BudgetGate):
            c.prepare("draft", estimate, amount)


@pytest.mark.parametrize(
    "mutation",
    [
        {"model": "other"},
        {"tools": [{}]},
        {"cache_control": {"type": "ephemeral"}},
        {"max_tokens": 9999},
    ],
)
def test_request_mutation_denied(mutation):
    p = c.prepare("draft", 100)
    with pytest.raises(BudgetGate):
        c.validate(replace(p, payload=c.canonical(json.loads(p.payload) | mutation)))


def test_free_count_matches_actual_input_payload_and_generation_once():
    calls = []

    def transport(request):
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(
            200,
            json={"input_tokens": 100} if request.url.path.endswith("count_tokens") else response(),
        )

    client = c.CountedClient("mock", transport=httpx.MockTransport(transport))
    bridge = Bridge()
    p = c.prepare("draft", client.count("draft"))
    result = execute(client, bridge, p)
    assert calls[0][0].endswith("count_tokens")
    assert calls[0][1] == {key: calls[1][1][key] for key in calls[0][1]}
    assert (
        hashlib.sha256(c.canonical(calls[0][1])).hexdigest()
        == json.loads(p.proof)["count_payload_hash"]
    )
    assert result["cost_usd"] == "0.000340"
    assert result["remaining_budget"]["budget_id"] == "new"
    with pytest.raises(BudgetGate):
        execute(client, bridge, p)
    assert len(calls) == 2


@pytest.mark.parametrize("allowed,amount,runs", [(False, "1", 3), (True, "0", 3), (True, "1", 0)])
def test_absent_exhausted_or_run_limit_sends_zero_requests(allowed, amount, runs):
    bridge = Bridge()
    bridge.allowed, bridge.amount, bridge.runs = allowed, amount, runs

    def transport(_):
        raise AssertionError("no network when budget blocked")

    with pytest.raises(BudgetGate):
        execute(c.CountedClient("mock", transport=httpx.MockTransport(transport)), bridge)
    assert not bridge.sent


@pytest.mark.parametrize(
    "usage",
    [
        {"cache_read_input_tokens": 1},
        {"cache_creation_input_tokens": 1},
        {"server_tool_use": {"web_search_requests": 1}},
        {"new_paid_tool": 1},
        {"inference_geo": "us"},
        {"service_tier": "priority"},
    ],
)
def test_unknown_optional_costs_fail_closed(usage):
    with pytest.raises(BudgetGate):
        c.actual_usage(c.prepare("draft", 100), response(**usage))


def test_thinking_not_double_billed_and_margin_not_exact():
    cost, _, violated = c.actual_usage(
        c.prepare("draft", 100),
        response(input_tokens=150, output_tokens_details={"thinking_tokens": 7}),
    )
    assert cost == Decimal("0.0004") and not violated
    cost, _, violated = c.actual_usage(c.prepare("draft", 100), response(input_tokens=30000))
    assert cost > c.MAX_REQUEST_USD and violated


def test_timeout_unknown_charge_pauses_without_retry():
    calls = []

    def transport(request):
        calls.append(request)
        raise httpx.ReadTimeout("mock")

    bridge = Bridge()
    with pytest.raises(BudgetGate, match="no_retry"):
        execute(c.CountedClient("mock", transport=httpx.MockTransport(transport)), bridge)
    assert len(calls) == 1
    assert bridge.settlements[0]["p_actual_usd"] is None
    assert bridge.settlements[0]["p_violation"] is True


def test_real_usage_over_margin_persisted_unclamped_then_stop():
    bridge = Bridge()
    client = c.CountedClient(
        "mock",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=response(input_tokens=30000))
        ),
    )
    with pytest.raises(BudgetGate, match="exceeded"):
        execute(client, bridge)
    assert Decimal(bridge.settlements[0]["p_actual_usd"]) > c.MAX_REQUEST_USD


@pytest.mark.parametrize("failure", ["count", "prepare", "execute", "dispatched"])
def test_failed_worker_preserves_stage_and_only_proves_zero_before_paid_request(
    monkeypatch, failure
):
    import asyncio

    class WorkerBridge(Bridge):
        def __init__(self):
            super().__init__()
            self.records, self.updates, self.contexts = [], [], []

        def load_autonomy_queue(self):
            return {"safe_to_execute": [TASK | {"domain": "research"}]}

        def claim_worker(self, *args):
            return TASK | {"domain": "research", "instruction": "attribution audit"}

        def record_run(self, **kwargs):
            self.records.append(kwargs)

        def update_worker(self, *args, **kwargs):
            self.updates.append(kwargs)

        def upsert_master_status(self, **kwargs):
            self.contexts.append(kwargs)

    class Client(c.CountedClient):
        def count(self, prompt):
            self.last_count = 7000
            if failure == "count":
                raise BudgetGate("count_tokens_exceeds_input_limit")
            return 7000 if failure == "prepare" else 100

        def execute(self, *args, **kwargs):
            if failure == "dispatched":
                self.execution_audit = {"provider_request_attempted": True, "cost_usd": None}
            raise BudgetGate(
                "provider_outcome_unknown_no_retry"
                if failure == "dispatched"
                else "reservation_denied"
            )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "mock")
    monkeypatch.setattr(c, "CountedClient", Client)
    bridge = WorkerBridge()
    assert asyncio.run(c.process_counted_task(bridge)) == 1
    decision = bridge.records[0]["decisions"][0]
    assert decision["failure_stage"] == ("execute" if failure == "dispatched" else failure)
    assert decision["cost_usd"] == (None if failure == "dispatched" else "0")
    assert decision["retry_allowed"] is False
    assert decision["prompt_bytes"] > 0
    assert decision["packet_sha256"] == bridge.contexts[0]["value"]["snapshot"]["packet_sha256"]
    assert len(bridge.updates) == 1
    assert not hasattr(bridge, "reservation")
