from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Lock

import pytest
from scripts.dufynd_bounded_provider import (
    BoundCertificate,
    BoundedProviderAdapter,
    BudgetGate,
    CallEnvelope,
    FakeBoundedProvider,
)


class Ledger:
    """Deterministic fake of the RPC contract; PostgreSQL has separate real tests."""

    def __init__(self, cap="0.10", spent="0"):
        self.cap, self.spent = Decimal(cap), Decimal(spent)
        self.rows = {}
        self.paused = []
        self.lock = Lock()

    def reserve_model_call(self, **p):
        with self.lock:
            key = p["idempotency_key"]
            if key in self.rows:
                r = self.rows[key]
                return {"allowed": r["status"] == "reserved", "reservation": r}
            amount = Decimal(p["max_usd"])
            held = sum(
                r["maximum"]
                for r in self.rows.values()
                if r["status"] in ("reserved", "dispatched")
            )
            if self.cap - self.spent - held - amount < 0:
                return {"allowed": False, "reason": "budget_exhausted"}
            r = {"reservation_id": key, "status": "reserved", "maximum": amount}
            self.rows[key] = r
            return {"allowed": True, "reservation": r}

    def dispatch_model_call(self, reservation_id, lease_token):
        with self.lock:
            r = self.rows[reservation_id]
            if r["status"] != "reserved":
                return False
            r["status"] = "dispatched"
            return True

    def settle_model_call(self, reservation_id, lease_token, actual_usd, evidence):
        with self.lock:
            r = self.rows[reservation_id]
            actual = Decimal(actual_usd)
            assert 0 <= actual <= r["maximum"]
            self.spent += actual
            r.update(status="settled", actual=actual, evidence=evidence)
            return True

    def update_worker(self, task_id, state, **kwargs):
        self.paused.append((task_id, state, kwargs))


def run(store, provider, key="one"):
    return BoundedProviderAdapter(store, provider).execute(
        CallEnvelope("free deterministic replay input"),
        budget_id="test",
        task_id="paid-task",
        worker_owner="test",
        lease_token="test",
        idempotency_key=key,
    )


def provider(maximum="0.10", actual="0.04", fail=False):
    return FakeBoundedProvider(
        BoundCertificate("fake-v1", Decimal(maximum)), cost_usd=Decimal(actual), fail=fail
    )


def test_enough_budget_releases_unused_reserve():
    store, p = Ledger(), provider()
    assert run(store, p).cost_usd == Decimal("0.04")
    assert p.calls == 1 and store.spent == Decimal("0.04")
    assert store.rows["one"]["evidence"]["dry_run"] is True
    run(store, provider(maximum="0.06", actual="0.06"), "two")
    assert store.spent == store.cap


@pytest.mark.parametrize("cap", ["0", "0.099999999999"])
def test_insufficient_budget_never_calls_provider_and_only_parks_paid_task(cap):
    store, p = Ledger(cap=cap), provider()
    with pytest.raises(BudgetGate, match="budget_exhausted"):
        run(store, p)
    assert p.calls == 0
    assert store.paused[0][:2] == ("paid-task", "queued")
    assert "waiting_human_input" not in repr(store.paused)


def test_exact_boundary_never_overruns():
    store = Ledger(cap="2.50", spent="2.49")
    p = provider(maximum="0.01", actual="0.01")
    run(store, p)
    assert store.spent == store.cap
    with pytest.raises(BudgetGate):
        run(store, p, "two")
    assert p.calls == 1


@pytest.mark.parametrize(
    "spent,actual",
    [
        ("2.49", "0.0147"),
        ("2.334318599999999955", "0.1703668"),
    ],
)
def test_nightshift_250_regression(spent, actual):
    store = Ledger(cap="2.50", spent=spent)
    p = provider(maximum=actual, actual=actual)
    with pytest.raises(BudgetGate):
        run(store, p)
    assert p.calls == 0 and store.spent == Decimal(spent)
    store = Ledger(cap="2.50", spent="2.5047")
    with pytest.raises(BudgetGate):
        run(store, p)
    assert p.calls == 0


def test_concurrent_workers_do_not_double_spend():
    store, p = Ledger(), provider(actual="0.10")

    def attempt(key):
        try:
            run(store, p, key)
            return True
        except BudgetGate:
            return False

    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(attempt, ["one", "two"])) == 1
    assert p.calls == 1 and store.spent == store.cap


def test_idempotent_replay_does_not_dispatch_twice():
    store, p = Ledger(), provider()
    run(store, p)
    with pytest.raises(BudgetGate):
        run(store, p)
    assert p.calls == 1 and len(store.rows) == 1


def test_ambiguous_failure_charged_max():
    store, p = Ledger(), provider(fail=True)
    with pytest.raises(RuntimeError, match="response loss"):
        run(store, p)
    assert store.spent == Decimal("0.10")
    assert store.rows["one"]["evidence"]["rule"] == "ambiguous_failure_charge_max"


@pytest.mark.parametrize("maximum", ["NaN", "Infinity", "-1", "0"])
def test_unknown_maximum_fails_closed(maximum):
    store, p = Ledger(), provider(maximum=maximum)
    with pytest.raises(BudgetGate, match="unbounded_provider_cost"):
        run(store, p)
    assert not store.rows and p.calls == 0


def test_envelope_and_real_transport_fail_closed():
    store, p = Ledger(), provider()
    with pytest.raises(BudgetGate):
        p.certificate.validate(CallEnvelope("x" * 4097))
    with pytest.raises(BudgetGate):
        p.certificate.validate(CallEnvelope("x", 257))
    with pytest.raises(BudgetGate, match="paid_canary"):
        BoundedProviderAdapter(store, object())
    assert p.calls == 0


def test_actual_supervisor_and_adapter_nightshift_replay():
    from scripts.dufynd_phase2a_replay import replay

    result = replay()
    assert result["provider_calls"] == 0
    assert result["free_deterministic_events"] == 1
    assert result["free_health_passes"] >= 3
    assert result["false_human_gates"] == 0


@pytest.mark.parametrize("value", ["false", "true", 1, 0, None, {}, []])
@pytest.mark.parametrize("stage", ["reserve", "dispatch", "settle"])
def test_only_boolean_true_confirms_cost_gate(monkeypatch, value, stage):
    store, p = Ledger(), provider()
    if stage == "reserve":
        monkeypatch.setattr(
            store,
            "reserve_model_call",
            lambda **kw: {"allowed": value, "reservation": {"reservation_id": "one"}},
        )
    else:
        method = "dispatch_model_call" if stage == "dispatch" else "settle_model_call"
        monkeypatch.setattr(store, method, lambda *args: value)
    with pytest.raises(BudgetGate):
        run(store, p)
    assert p.calls == (1 if stage == "settle" else 0)


@pytest.mark.parametrize("value", ["false", "true", 1, 0, None, {}, [], False, True])
def test_bridge_preserves_strict_cost_confirmation(monkeypatch, value):
    from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

    bridge = DufyndJarvisBridge(supabase_url="https://example.invalid", secret_key="fake")
    monkeypatch.setattr(bridge, "_rpc", lambda *args: value)
    assert bridge.dispatch_model_call("test", "test") is (value is True)
    assert bridge.settle_model_call("test", "test", "0", {"test": True}) is (value is True)
