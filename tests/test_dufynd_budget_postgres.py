"""Real PostgreSQL contention tests, executed by the dedicated CI service job."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated PostgreSQL service required")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def database():
    if not DSN:
        yield
        return
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute((ROOT / "tests/dufynd_budget_schema_fixture.sql").read_text())
        phase1 = next((ROOT / "supabase/migrations").glob("*supervisor_v2_phase1.sql")).read_text()
        connection.execute(phase1.split("-- No model and no paid runner:")[0])
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*cost_reservations.sql")).read_text()
        )
    yield


def query(sql, args=()):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as connection:
        return connection.execute(sql, args).fetchone()[0]


def fixture(cap="0.10", maximum="0.10", workers=2):
    import psycopg

    budget, contract = f"budget-{uuid4()}", f"fake-{uuid4()}"
    tasks = [(f"task-{uuid4()}", str(uuid4())) for _ in range(workers)]
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            "insert into dufynd_jarvis_budget_windows values(%s,'test','active','fake',%s,20,null,true,true)",
            (budget, cap),
        )
        connection.execute(
            "insert into dufynd_provider_contracts values(%s,'fake',%s,true,true,'{}',now()+interval '1 hour')",
            (contract, maximum),
        )
        for task, token in tasks:
            connection.execute(
                "insert into dufynd_autonomy_tasks(task_id,domain,title,instruction,status,worker_state,worker_owner,lease_token,lease_expires_at,heartbeat_at,last_progress_at,resource_scope) values(%s,'test','test','test','in_progress','working','test',%s,now()+interval '1 hour',now(),now(),%s)",
                (task, token, f'["db:{task}"]'),
            )
    return budget, contract, tasks


def reserve(f, worker=0, key=None, amount="0.10"):
    budget, contract, tasks = f
    task, token = tasks[worker]
    return query(
        "select reserve_dufynd_model_call(%s,%s,'test',%s,%s,%s,%s,%s,180)",
        (budget, task, token, key or str(uuid4()), "a" * 64, contract, amount),
    )


def test_parallel_budget_claims():
    f = fixture()
    barrier = Barrier(2)

    def claim(worker):
        barrier.wait(timeout=10)
        return reserve(f, worker)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, range(2)))
    assert sum(r["allowed"] for r in results) == 1
    assert (
        query("select get_dufynd_jarvis_budget_status(%s)", (f[0],))["reserved_unsettled_usd"]
        == 0.10
    )


def test_parallel_idempotency_and_dispatch():
    f = fixture()
    barrier = Barrier(2)

    def claim(_):
        barrier.wait(timeout=10)
        return reserve(f, key="same")

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, range(2)))
    assert all(r["allowed"] for r in results)
    ids = {r["reservation"]["reservation_id"] for r in results}
    assert len(ids) == 1
    reservation = ids.pop()
    barrier = Barrier(2)

    def dispatch(_):
        barrier.wait(timeout=10)
        return query("select dispatch_dufynd_model_call(%s,%s)", (reservation, f[2][0][1]))

    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(dispatch, range(2))) == 1


def test_boundaries_settlement_and_ttl():
    f = fixture()
    r = reserve(f)["reservation"]["reservation_id"]
    assert not reserve(f, worker=1)["allowed"]
    assert query("select dispatch_dufynd_model_call(%s,%s)", (r, f[2][0][1]))
    assert not query("select settle_dufynd_model_call(%s,%s,0.10001,'{}')", (r, f[2][0][1]))
    assert query(
        'select settle_dufynd_model_call(%s,%s,0.04,\'{"request_id":"fake"}\')', (r, f[2][0][1])
    )
    status = query("select get_dufynd_jarvis_budget_status(%s)", (f[0],))
    assert Decimal(str(status["remaining_usd"])) == Decimal("0.06")
    assert status["reserved_unsettled_usd"] == 0
    assert not reserve(f, worker=1)["allowed"]
    for dispatched in (False, True):
        f = fixture()
        r = reserve(f)["reservation"]["reservation_id"]
        if dispatched:
            assert query("select dispatch_dufynd_model_call(%s,%s)", (r, f[2][0][1]))
        query(
            "update dufynd_budget_reservations set expires_at=now()-interval '1 second' where reservation_id=%s returning reservation_id",
            (r,),
        )
        query("select reconcile_dufynd_supervisor_v2()")
        row = query(
            "select to_jsonb(r) from dufynd_budget_reservations r where reservation_id=%s", (r,)
        )
        assert row["status"] == ("charged_max" if dispatched else "released")
        assert row["actual_usd"] == (0.1 if dispatched else 0)
        assert not query("select dispatch_dufynd_model_call(%s,%s)", (r, f[2][0][1]))
        assert query("select reconcile_dufynd_budget_reservations()")["reconciled"] == 0


def test_unknown_bound_old_approval_and_historical_overrun():
    f = fixture(cap="2.50", maximum="0.01")
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "insert into dufynd_agent_runs(agent_name,decisions) values('jarvis',jsonb_build_array(jsonb_build_object('budget_id',%s::text,'cost_usd','2.49')))",
            (f[0],),
        )
    assert not reserve(f, amount="0.0147")["allowed"]  # would reproduce $2.5047
    assert reserve(f, amount="0.01")["allowed"]
    assert not reserve(f, worker=1, amount="0.01")["allowed"]
    assert not reserve(f, amount="NaN")["allowed"]
    assert not reserve(f, amount="0.001")["allowed"]
    query(
        "update dufynd_jarvis_budget_windows set reservation_dry_run=false where budget_id=%s returning budget_id",
        (f[0],),
    )
    assert not reserve(f, amount="0.01")["allowed"]


def test_old_budget_approval_cannot_authorize_paid_contract():
    import psycopg

    f = fixture()
    decision = f"old-approval-{uuid4()}"
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "update dufynd_provider_contracts set dry_run=false where contract_id=%s", (f[1],)
        )
        c.execute(
            'insert into dufynd_human_decisions values(%s,\'approved\',\'{"approved":true,"cap_usd":2.5,"per_run_cap_usd":0.25,"max_runs":20}\')',
            (decision,),
        )
        c.execute(
            "update dufynd_jarvis_budget_windows set reservation_dry_run=false,approved_decision_id=%s where budget_id=%s",
            (decision, f[0]),
        )
    r = reserve(f)
    assert not r["allowed"] and r["reason"] == "new_budget_approval_required"
    assert query("select count(*) from dufynd_budget_reservations where budget_id=%s", (f[0],)) == 0


class ProviderPostgresStore:
    """Existing production RPCs against the ephemeral CI database; no approval."""

    def __init__(self, f, fault=None):
        self.f, self.fault = f, fault

    def reserve_model_call(self, **p):
        return query(
            "select reserve_dufynd_model_call(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            tuple(
                p[k]
                for k in (
                    "budget_id",
                    "task_id",
                    "owner",
                    "lease_token",
                    "idempotency_key",
                    "request_hash",
                    "contract_id",
                    "max_usd",
                    "ttl_seconds",
                )
            ),
        )

    def dispatch_model_call(self, reservation_id, lease_token):
        if self.fault == "before_dispatch":
            raise RuntimeError("worker crash after reserve before dispatch")
        result = query("select dispatch_dufynd_model_call(%s,%s)", (reservation_id, lease_token))
        if self.fault == "dispatch_response_lost":
            raise RuntimeError("dispatch acknowledgement lost")
        return result

    def settle_model_call(self, reservation_id, lease_token, actual_usd, evidence):
        import json

        if self.fault == "before_settlement":
            raise RuntimeError("response received worker crash before settlement")
        return query(
            "select settle_dufynd_model_call(%s,%s,%s,%s::jsonb)",
            (reservation_id, lease_token, actual_usd, json.dumps(evidence)),
        )

    def update_worker(self, task_id, state, **kwargs):
        token = dict(self.f[2])[task_id]
        assert query(
            "select update_dufynd_worker_v2(%s,%s,%s,%s,%s)",
            (task_id, token, state, kwargs.get("evidence"), kwargs.get("reason")),
        )


def provider_canary_fixture(cap="0.000896", workers=1):
    import json

    import httpx
    import psycopg
    from scripts.dufynd_messages_transport import SimulatedMessagesProvider
    from scripts.dufynd_provider_contract import (
        build_bounded_request,
        calculate_worst_case_cost,
        load_contract,
    )

    c = load_contract("simulated-messages-v1")
    request = build_bounded_request(c, system="test", prompt="fully simulated canary")
    f = fixture(cap=cap, maximum=str(calculate_worst_case_cost(c)), workers=workers)
    with psycopg.connect(DSN, autocommit=True) as db:
        db.execute(
            "insert into dufynd_provider_contracts values(%s,%s,%s,true,true,%s::jsonb,now()+interval '1 hour') on conflict do nothing",
            (
                c.contract_id,
                c.model,
                str(calculate_worst_case_cost(c)),
                json.dumps({"catalog_digest": c.catalog_digest, "simulation_only": True}),
            ),
        )
        db.execute(
            "update dufynd_jarvis_budget_windows set model=%s where budget_id=%s", (c.model, f[0])
        )

    def handler(wire):
        assert wire.content == request.payload
        assert (
            query("select status from dufynd_budget_reservations where budget_id=%s", (f[0],))
            == "dispatched"
        )
        return httpx.Response(
            200,
            json={
                "id": "mock-receipt",
                "model": c.model,
                "content": [{"type": "text", "text": "offline"}],
                "usage": {"input_tokens": request.input_tokens, "output_tokens": 8},
            },
        )

    return f, request, SimulatedMessagesProvider(c, httpx.MockTransport(handler))


def execute_provider_canary(f, request, provider, store, worker=0, key="canary"):
    from scripts.dufynd_bounded_provider import BoundedProviderAdapter

    task, token = f[2][worker]
    return BoundedProviderAdapter(store, provider).execute(
        request,
        budget_id=f[0],
        task_id=task,
        worker_owner="test",
        lease_token=token,
        idempotency_key=key,
    )


def test_simulated_canary_real_reservation_to_http_mock_to_settlement():
    from scripts.dufynd_bounded_provider import BudgetGate

    f, request, provider = provider_canary_fixture()
    store = ProviderPostgresStore(f)
    result = execute_provider_canary(f, request, provider, store)
    status = query("select get_dufynd_jarvis_budget_status(%s)", (f[0],))
    assert Decimal(str(status["spent_usd"])) == result.cost_usd
    assert status["reserved_unsettled_usd"] == 0
    assert Decimal(str(status["remaining_usd"])) == Decimal("0.000896") - result.cost_usd
    with pytest.raises(BudgetGate):
        execute_provider_canary(f, request, provider, store)
    assert provider.calls == 1
    assert (
        query(
            "select approved_decision_id from dufynd_jarvis_budget_windows where budget_id=%s",
            (f[0],),
        )
        is None
    )


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("before_dispatch", "released"),
        ("dispatch_response_lost", "charged_max"),
        ("before_settlement", "charged_max"),
    ],
)
def test_simulated_canary_worker_crashes_conservatively_reconcile(fault, expected):
    from scripts.dufynd_bounded_provider import BudgetGate

    f, request, provider = provider_canary_fixture()
    with pytest.raises(RuntimeError):
        execute_provider_canary(f, request, provider, ProviderPostgresStore(f, fault=fault))
    reservation = query(
        "select reservation_id from dufynd_budget_reservations where budget_id=%s", (f[0],)
    )
    query(
        "update dufynd_budget_reservations set expires_at=now()-interval '1 second' where reservation_id=%s returning reservation_id",
        (reservation,),
    )
    query("select reconcile_dufynd_supervisor_v2()")
    assert (
        query(
            "select status from dufynd_budget_reservations where reservation_id=%s", (reservation,)
        )
        == expected
    )
    calls = provider.calls
    with pytest.raises(BudgetGate):
        execute_provider_canary(f, request, provider, ProviderPostgresStore(f))
    assert provider.calls == calls
    assert calls == (1 if fault == "before_settlement" else 0)


def test_simulated_canary_microdollar_overrun_rejected_before_mock():
    from scripts.dufynd_bounded_provider import BudgetGate

    f, request, provider = provider_canary_fixture(cap="0.000895")
    with pytest.raises(BudgetGate, match="budget_exhausted"):
        execute_provider_canary(f, request, provider, ProviderPostgresStore(f))
    assert provider.calls == 0
    assert query("select count(*) from dufynd_budget_reservations where budget_id=%s", (f[0],)) == 0
