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
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*durable_executions.sql"))
            .read_text()
            .split("-- Hosted observer extension;")[0]
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*external_events.sql")).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*capability_packets.sql")).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*state_audit_handler.sql")).read_text()
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


def durable_fixture(*, key=None, resources=None, steps=3, interval=2):
    import json

    task = f"durable-{uuid4()}"
    result = query(
        "select prepare_dufynd_execution(%s,%s,'supervisor-test',%s::jsonb,%s::jsonb,'durable')",
        (
            task,
            key or str(uuid4()),
            json.dumps(resources or [f"db:{task}"]),
            json.dumps({"kind": "durability_probe", "steps": steps, "interval_seconds": interval}),
        ),
    )
    return task, result


def take_execution(e, run="123456", worker="actions:test"):
    return query("select take_dufynd_execution(%s,%s,%s)", (run, worker, e["execution_id"]))


def execution_checkpoint(e, step=None):
    return query(
        "select checkpoint_dufynd_execution(%s,%s,%s,%s)",
        (e["execution_id"], e["lease_token"], e["worker_id"], step),
    )


def execution_state(e):
    return query(
        "select to_jsonb(e) from dufynd_execution_runs e where execution_id=%s",
        (e["execution_id"],),
    )


def finish_execution(e):
    return query(
        "select finish_dufynd_execution(%s,%s,%s)",
        (e["execution_id"], e["lease_token"], e["worker_id"]),
    )


def force_execution_expired(e):
    import psycopg

    with psycopg.connect(DSN) as db:
        db.execute("select set_config('dufynd.execution_write','supervisor',true)")
        db.execute("select set_config('dufynd.worker_write','supervisor',true)")
        db.execute(
            "update dufynd_execution_runs set lease_expires_at=now()-interval '1 second' where execution_id=%s",
            (e["execution_id"],),
        )
        db.execute(
            "update dufynd_autonomy_tasks set lease_expires_at=now()-interval '1 second' where task_id=%s",
            (e["task_id"],),
        )


def test_durable_dispatch_binding_duplicate_and_chat_loss():
    import json

    task, prepared = durable_fixture()
    original = prepared["execution"]
    claimed = take_execution(original)
    assert claimed["external_run_id"] == "123456"
    running = execution_checkpoint(claimed)
    assert running["status"] == "running"
    # A retry/new client needs no local/chat state; the persisted command is enough.
    del prepared
    duplicate = query(
        "select prepare_dufynd_execution(%s,%s,%s,%s::jsonb,%s::jsonb,%s)",
        (
            task,
            original["idempotency_key"],
            original["scope"],
            json.dumps(original["resources"]),
            json.dumps(original["payload"]),
            original["durability_policy"],
        ),
    )
    assert duplicate["allowed"] and duplicate["reused"]
    assert duplicate["execution"]["status"] == "running"
    assert duplicate["execution"]["external_run_id"] == "123456"
    assert take_execution(original, run="987654", worker="duplicate") is None
    query("select reconcile_dufynd_supervisor_v2()")
    assert execution_state(original)["status"] == "running"
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (task,)) == 1


def test_durable_worker_verified_success_and_released_lease():
    task, p = durable_fixture(steps=2)
    e = take_execution(p["execution"])
    assert not finish_execution(e)
    assert execution_checkpoint(e, 1)["last_checkpoint"]["sum"] == 1
    assert execution_checkpoint(e, 1)["last_checkpoint"]["sum"] == 1  # idempotent ack
    assert execution_checkpoint(e, 2)["status"] == "verifying"
    assert finish_execution(e) and finish_execution(e)
    saved = execution_state(e)
    assert saved["status"] == "completed" and saved["completed_at"]
    t = query("select to_jsonb(t) from dufynd_autonomy_tasks t where task_id=%s", (task,))
    assert t["status"] == "done" and t["released_at"]
    assert saved["execution_id"] in t["evidence"]


def test_durable_worker_failure_retryable_and_autonomous_resume():
    _, p = durable_fixture(steps=2)
    e = take_execution(p["execution"])
    assert execution_checkpoint(e, 1)
    assert query(
        "select fail_dufynd_execution(%s,%s,%s,'fixture_failure')",
        (e["execution_id"], e["lease_token"], e["worker_id"]),
    )
    query("select reconcile_dufynd_executions()")
    retry = execution_state(e)
    assert retry["status"] == "retryable" and retry["recovery_count"] == 1
    assert retry["lease_token"] != e["lease_token"]
    assert execution_checkpoint(e, 2) is None
    query("select reconcile_dufynd_executions()")
    saved = execution_state(e)
    assert saved["status"] == "completed"
    assert saved["worker_type"] == "deterministic_supervisor" and saved["attempt"] == 2
    assert any(
        x["event"] == "checkpoint_resumed" and x["checkpoint"]["step"] == 1
        for x in saved["evidence"]
    )


def test_durable_stale_worker_fenced_and_checkpoint_continues():
    _, p = durable_fixture(steps=3)
    e = take_execution(p["execution"])
    assert execution_checkpoint(e, 1)
    force_execution_expired(e)
    assert execution_checkpoint(e, 2) is None
    query("select reconcile_dufynd_supervisor_v2()")
    assert execution_state(e)["status"] == "retryable"
    query("select reconcile_dufynd_supervisor_v2()")
    resumed = execution_state(e)
    assert resumed["last_checkpoint"]["step"] == 2 and resumed["attempt"] == 2
    assert execution_checkpoint(e, 2) is None
    query("select reconcile_dufynd_supervisor_v2()")
    assert execution_state(e)["status"] == "completed"


def test_durable_verified_success_finalization_crash_reconciled():
    _, p = durable_fixture(steps=1)
    e = take_execution(p["execution"])
    assert execution_checkpoint(e, 1)["status"] == "verifying"
    force_execution_expired(e)
    assert not finish_execution(e)  # stale worker cannot mutate even verified result
    query("select reconcile_dufynd_supervisor_v2()")
    assert execution_state(e)["status"] == "completed"


def test_durable_different_scopes_and_scope_conflict():
    scope = [f"db:durable-conflict-{uuid4()}"]
    _, a = durable_fixture(resources=scope)
    _, b = durable_fixture()
    _, denied = durable_fixture(resources=scope)
    assert a["allowed"] and b["allowed"]
    assert not denied["allowed"] and denied["reason"] == "scope_or_task_unavailable"
    assert a["execution"]["execution_id"] != b["execution"]["execution_id"]
    assert take_execution(a["execution"], worker="first")
    assert take_execution(b["execution"], worker="second")


def test_durable_parallel_atomic_dispatch_and_idempotency():
    import json

    _, p = durable_fixture()
    original = p["execution"]
    barrier = Barrier(2)

    def duplicate(_):
        barrier.wait(timeout=10)
        return query(
            "select prepare_dufynd_execution(%s,%s,%s,%s::jsonb,%s::jsonb,%s)",
            (
                original["task_id"],
                original["idempotency_key"],
                original["scope"],
                json.dumps(original["resources"]),
                json.dumps(original["payload"]),
                original["durability_policy"],
            ),
        )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(duplicate, range(2)))
    assert all(x["allowed"] and x["reused"] for x in results)
    barrier = Barrier(2)

    def dispatch(i):
        barrier.wait(timeout=10)
        return take_execution(original, run=str(123456 + i), worker=f"worker-{i}")

    with ThreadPoolExecutor(2) as pool:
        assert sum(bool(x) for x in pool.map(dispatch, range(2))) == 1


def test_durable_external_missing_and_failed_runs_recover():
    import json

    for state in ("missing", "failure", "success"):
        _, p = durable_fixture()
        e = take_execution(p["execution"])
        assert not query(
            "select observe_dufynd_execution(%s,'wrong',%s::jsonb)",
            (e["execution_id"], json.dumps({"state": state})),
        )
        assert query(
            "select observe_dufynd_execution(%s,%s,%s::jsonb)",
            (e["execution_id"], e["external_run_id"], json.dumps({"state": state})),
        )
        query("select reconcile_dufynd_executions()")
        saved = execution_state(e)
        assert saved["status"] == "retryable"  # external success is NOT proof of work
        assert saved["lease_token"] != e["lease_token"]


def test_durable_status_reconstructable_without_history():
    _, p = durable_fixture()
    e = take_execution(p["execution"])
    execution_checkpoint(e, 1)
    saved = execution_state(e)
    required = {
        "execution_id",
        "task_id",
        "worker_type",
        "worker_id",
        "external_run_id",
        "status",
        "attempt",
        "scope",
        "resources",
        "lease_token",
        "started_at",
        "heartbeat_at",
        "last_progress_at",
        "last_checkpoint",
        "completed_at",
        "recovery_count",
        "last_error",
        "evidence",
    }
    assert required <= saved.keys()
    assert saved["last_checkpoint"]["step"] == 1 and saved["started_at"]
    assert "chat_id" not in saved and "conversation_id" not in saved


def test_durable_direct_and_legacy_mutations_rejected():
    import psycopg

    _, p = durable_fixture()
    e = take_execution(p["execution"])
    with pytest.raises(psycopg.errors.RaiseException, match="execution mutations"):
        query(
            "update dufynd_execution_runs set status='completed' where execution_id=%s returning true",
            (e["execution_id"],),
        )
    with pytest.raises(psycopg.errors.RaiseException, match="durable task"):
        query(
            "select update_dufynd_worker_v2(%s,%s,'verifying','legacy mutation',null)",
            (e["task_id"], e["lease_token"]),
        )
    assert execution_state(e)["status"] == "dispatched"


def test_durable_unknown_handler_paid_task_and_changed_command_fail_closed():
    import json

    task, p = durable_fixture()
    e = p["execution"]
    changed = query(
        "select prepare_dufynd_execution(%s,%s,%s,%s::jsonb,%s::jsonb,'durable')",
        (
            task,
            e["idempotency_key"],
            e["scope"],
            json.dumps(e["resources"]),
            json.dumps({"kind": "durability_probe", "steps": 4, "interval_seconds": 2}),
        ),
    )
    assert not changed["allowed"] and changed["reason"] == "idempotency_conflict"
    unknown = query(
        "select prepare_dufynd_execution('unknown','unknown','test','[\"db:test\"]','{\"kind\":\"bounded_ai_worker\",\"steps\":1,\"interval_seconds\":2}')"
    )
    assert not unknown["allowed"]
    paid = fixture()[2][0][0]
    denied = query(
        'select prepare_dufynd_execution(%s,%s,\'test\',%s::jsonb,\'{"kind":"durability_probe","steps":1,"interval_seconds":2}\')',
        (paid, str(uuid4()), json.dumps([f"db:{paid}"])),
    )
    assert not denied["allowed"] and denied["reason"] == "task_contract_conflict"


def test_durable_unbound_queue_expiry_and_bounded_retry_exhaustion():
    import psycopg

    _, p = durable_fixture(steps=3)
    e = p["execution"]
    force_execution_expired(e)
    query("select reconcile_dufynd_supervisor_v2()")
    assert execution_state(e)["status"] == "retryable"
    query("select reconcile_dufynd_supervisor_v2()")
    assert execution_state(e)["attempt"] == 2
    with psycopg.connect(DSN) as db:
        db.execute("select set_config('dufynd.execution_write','supervisor',true)")
        db.execute(
            "update dufynd_execution_runs set attempt=3,status='stale',last_error='retry_test' where execution_id=%s",
            (e["execution_id"],),
        )
    query("select reconcile_dufynd_supervisor_v2()")
    assert execution_state(e)["status"] == "failed_terminal"
    assert query(
        "select released_at is not null from dufynd_autonomy_tasks where task_id=%s",
        (e["task_id"],),
    )


def test_durable_unknown_external_state_does_not_redispatch_or_accept_null_binding():
    _, p = durable_fixture()
    assert take_execution(p["execution"], run=None) is None
    e = take_execution(p["execution"])
    execution_checkpoint(e)
    assert not query(
        "select observe_dufynd_execution(%s,%s,'{}')", (e["execution_id"], e["external_run_id"])
    )
    assert query(
        'select observe_dufynd_execution(%s,%s,\'{"state":"unknown","http_status":429}\')',
        (e["execution_id"], e["external_run_id"]),
    )
    query("select reconcile_dufynd_supervisor_v2()")
    saved = execution_state(e)
    assert saved["status"] == "running" and saved["lease_token"] == e["lease_token"]
    assert take_execution(e, run="987654") is None


# Phase 2C tests exercise actual SQL, not a second in-memory event/queue model.
def event_query(sql, *args):
    import json

    return query(sql, tuple(json.dumps(a) if isinstance(a, (dict, list)) else a for a in args))


def external_wait(
    kind="github_ci", *, policy="dependency", payload=None, baseline=None, cursor=None
):
    source = str(uuid4().int) if kind.startswith("github_") else uuid4().hex[:16]
    if kind == "render":
        source = "srv-" + source
    observer = event_query(
        "select register_dufynd_observer(%s,%s,'{}',%s::jsonb,%s)",
        kind,
        source,
        baseline or {},
        cursor,
    )
    task = "observer-test-" + str(uuid4())
    event_query(
        "insert into dufynd_autonomy_tasks(task_id,domain,title,instruction,status,worker_state,budget_class,resource_scope,durability_policy,durable_payload) values(%s,'supervisor','test','free test','waiting_external','waiting_external','free',%s::jsonb,'durable',%s::jsonb) returning task_id",
        task,
        ["db:" + task],
        payload,
    )
    events = {
        "github_ci": ["github.ci.success"],
        "github_workflow": ["github.workflow.success"],
        "render": ["render.deployment.live"],
        "gmail": ["gmail.message.received", "gmail.delivery_failure"],
    }
    assert event_query(
        "select bind_dufynd_external_wait(%s,%s,%s::jsonb,%s,%s)",
        task,
        observer,
        events[kind],
        "a" * 40 if kind != "gmail" else None,
        policy,
    )
    return task, observer, source


def ci_raw(source, *, state="completed", conclusion="success", sha="a" * 40):
    return {
        "id": source,
        "head_branch": "scentai-mvp",
        "path": ".github/workflows/ci.yml",
        "head_sha": sha,
        "status": state,
        "conclusion": conclusion,
        "run_attempt": 1,
    }


def capture(observer, raw):
    return event_query("select capture_dufynd_observation(%s,%s::jsonb)", observer, raw)


def task_state(task):
    return query("select to_jsonb(t) from dufynd_autonomy_tasks t where task_id=%s", (task,))


def inbox_count(observer):
    return query(
        "select count(*) from dufynd_jarvis_inbox where payload->>'observer_id'=%s", (observer,)
    )


def mail_raw(source, *, message="abcdef12", date="2000", history="100", bounce=False):
    return {
        "id": source,
        "historyId": history,
        "messages": [
            {
                "id": message,
                "threadId": source,
                "internalDate": date,
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {
                            "name": "From",
                            "value": "mailer-daemon@example.test"
                            if bounce
                            else "sender@example.test",
                        }
                    ],
                    "body": "PRIVATE NOT PERSISTED",
                },
            }
        ],
    }


def test_external_ci_success_wakes_exact_task_and_is_deduplicated():
    task, observer, source = external_wait()
    assert capture(observer, ci_raw(source))["inserted"] == 1
    assert capture(observer, ci_raw(source))["inserted"] == 0
    assert inbox_count(observer) == 1
    query("select process_dufynd_external_events()")
    state = task_state(task)
    assert state["status"] == "ready" and state["last_external_event_id"]
    assert (
        query(
            "select attempts from dufynd_jarvis_inbox where payload->>'observer_id'=%s", (observer,)
        )
        == 1
    )
    query("select process_dufynd_external_events()")
    assert task_state(task)["evidence"] == state["evidence"]


def test_external_ci_failure_is_retryable_without_human_or_done():
    task, observer, source = external_wait()
    capture(observer, ci_raw(source, conclusion="failure"))
    query("select process_dufynd_external_events()")
    state = task_state(task)
    assert state["status"] == "waiting_external" and state["worker_state"] == "failed_retryable"
    assert state["blocked_reason"] == "external_failure_retryable"
    assert not query(
        "select bind_dufynd_external_wait(%s,%s,'[\"github.ci.failure\"]',%s,'dependency')",
        (task, observer, "a" * 40),
    )


@pytest.mark.parametrize(
    "status,expected", [("live", "ready"), ("build_failed", "waiting_external")]
)
def test_external_render_deploy_must_be_live_at_pinned_commit(status, expected):
    task, observer, source = external_wait("render")
    capture(
        observer, [{"deploy": {"id": "dep-fixture", "status": status, "commit": {"id": "b" * 40}}}]
    )
    query("select process_dufynd_external_events()")
    assert task_state(task)["status"] == "waiting_external"
    capture(
        observer, [{"deploy": {"id": "dep-fixture", "status": status, "commit": {"id": "a" * 40}}}]
    )
    query("select process_dufynd_external_events()")
    assert task_state(task)["status"] == expected


def test_external_known_gmail_reply_requires_review_never_approves_rights():
    task, observer, source = external_wait("gmail", policy="review")
    assert capture(observer, mail_raw(source))["inserted"] == 1
    query("select process_dufynd_external_events()")
    state = task_state(task)
    assert state["status"] == "ready" and state["external_review_required"]
    assert state["blocked_reason"] == "external_response_review" and state["status"] != "done"
    assert "PRIVATE NOT PERSISTED" not in query(
        "select payload::text from dufynd_jarvis_inbox where payload->>'observer_id'=%s",
        (observer,),
    )
    assert not query("select exists(select 1 from dufynd_execution_runs where task_id=%s)", (task,))


def test_external_gmail_baseline_restart_and_old_mail_never_replay():
    baseline = {"watermark_ms": "2000", "seen_message_ids": ["abcdef12"]}
    task, observer, source = external_wait(
        "gmail", policy="review", baseline=baseline, cursor="100"
    )
    assert capture(observer, mail_raw(source))["inserted"] == 0
    assert capture(observer, mail_raw(source, message="abcdef13", date="1999"))["inserted"] == 0
    event_query("select register_dufynd_observer('gmail',%s,'{}','{}','1')", source)
    assert (
        query("select last_cursor from dufynd_external_observers where observer_id=%s", (observer,))
        == "100"
    )
    assert (
        capture(observer, mail_raw(source, message="abcdef14", date="3000", history="101"))[
            "inserted"
        ]
        == 1
    )
    assert (
        capture(observer, mail_raw(source, message="abcdef14", date="3000", history="102"))[
            "inserted"
        ]
        == 0
    )
    assert inbox_count(observer) == 1 and task_state(task)["status"] == "waiting_external"


def test_external_unknown_gmail_message_cannot_mutate_foreign_task():
    task, observer, source = external_wait("gmail", policy="review")
    unknown = uuid4().hex[:16]
    result = capture(
        observer,
        {
            "historyId": "100",
            "history": [
                {
                    "id": "99",
                    "messagesAdded": [
                        {"message": {"id": "123", "threadId": unknown, "labelIds": ["INBOX"]}}
                    ],
                }
            ],
        },
    )
    assert result["inserted"] == 0
    with pytest.raises(Exception, match="known bounded Gmail"):
        capture(observer, mail_raw(unknown))
    assert not capture("gmail:" + unknown, mail_raw(unknown))["accepted"]
    query("select process_dufynd_external_events()")
    assert task_state(task)["status"] == "waiting_external" and inbox_count(observer) == 0


def test_external_gmail_bounce_is_evidence_and_review_not_success():
    task, observer, source = external_wait("gmail", policy="review")
    capture(observer, mail_raw(source, bounce=True))
    query("select process_dufynd_external_events()")
    assert (
        query(
            "select event_type from dufynd_jarvis_inbox where payload->>'observer_id'=%s",
            (observer,),
        )
        == "gmail.delivery_failure"
    )
    assert task_state(task)["external_review_required"]


def test_external_rate_limit_backoff_preserves_cursor_and_never_human_gate():
    task, observer, source = external_wait(cursor="retained")
    query("select dufynd_observer_failure(%s,'rate_limited',429,300)", (observer,))
    health = query(
        "select to_jsonb(o) from dufynd_external_observers o where observer_id=%s", (observer,)
    )
    assert health["last_cursor"] == "retained" and health["consecutive_failures"] == 1
    assert health["health_status"] == "degraded"
    assert query(
        "select next_retry_at>=now()+interval '290 seconds' from dufynd_external_observers where observer_id=%s",
        (observer,),
    )
    assert task_state(task)["status"] == "waiting_external"
    for _ in range(2):
        query("select dufynd_observer_failure(%s,'network_error')", (observer,))
    assert (
        query(
            "select health_status from dufynd_external_observers where observer_id=%s", (observer,)
        )
        == "stale"
    )


def test_external_silent_dead_observer_distinguished_from_healthy_empty_poll():
    task, observer, source = external_wait("gmail", policy="review")
    capture(observer, {"id": source, "historyId": "100", "messages": []})
    assert (
        query(
            "select health_status from dufynd_external_observers where observer_id=%s", (observer,)
        )
        == "healthy"
    )
    query(
        "update dufynd_external_observers set last_success_at=now()-interval '5 hours' where observer_id=%s returning observer_id",
        (observer,),
    )
    assert (
        next(
            x for x in query("select get_dufynd_observer_health()") if x["observer_id"] == observer
        )["health_status"]
        == "stale"
    )
    assert task_state(task)["status"] == "waiting_external"


def test_external_internal_dependency_event_wakes_without_chat_or_binding_queue():
    parent, _, _ = external_wait()
    task, _, _ = external_wait()
    query("delete from dufynd_task_external_waits where task_id=%s returning task_id", (task,))
    event_query(
        "update dufynd_autonomy_tasks set dependencies=%s::jsonb where task_id=%s returning task_id",
        [parent],
        task,
    )
    query(
        "update dufynd_autonomy_tasks set status='done',worker_state='done' where task_id=%s returning task_id",
        (parent,),
    )
    query("select process_dufynd_external_events()")
    assert task_state(task)["status"] == "ready"
    assert (
        query(
            "select count(*) from dufynd_jarvis_inbox where event_type='internal.dependency.completed' and source_id=%s",
            (parent,),
        )
        == 1
    )


def test_external_ready_certified_free_handler_dispatches_existing_durable_plane_once():
    payload = {"kind": "durability_probe", "steps": 2, "interval_seconds": 2}
    task, observer, source = external_wait(payload=payload)
    capture(observer, ci_raw(source))
    query("select process_dufynd_external_events()")
    e = query("select to_jsonb(e) from dufynd_execution_runs e where task_id=%s", (task,))
    assert e["status"] == "dispatch_pending" and e["idempotency_key"] == "event-wake:" + task
    query("select process_dufynd_external_events()")
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (task,)) == 1
    e = take_execution(e)
    execution_checkpoint(e, 1)
    execution_checkpoint(e, 2)
    assert finish_execution(e)
    assert task_state(task)["status"] == "done" and task_state(task)["released_at"]


def test_external_ready_uncertified_handler_parked_no_improvised_dispatch():
    task, observer, source = external_wait(payload={"kind": "arbitrary_shell", "command": "false"})
    capture(observer, ci_raw(source))
    query("select process_dufynd_external_events()")
    assert task_state(task)["status"] == "ready"
    assert not query("select exists(select 1 from dufynd_execution_runs where task_id=%s)", (task,))


def test_external_bound_cursor_pagination_and_fail_closed_missing_identity():
    task, observer, source = external_wait("gmail", policy="review", cursor="100")
    capture(observer, {"historyId": "200", "nextPageToken": "page2", "history": []})
    assert (
        query("select last_cursor from dufynd_external_observers where observer_id=%s", (observer,))
        == "100"
    )
    capture(observer, {"historyId": "200", "history": []})
    assert (
        query("select last_cursor from dufynd_external_observers where observer_id=%s", (observer,))
        == "200"
    )
    with pytest.raises(Exception, match="identity mismatch"):
        capture(external_wait()[1], {})


def test_external_legacy_sdk_cannot_claim_external_event():
    _, observer, source = external_wait()
    capture(observer, ci_raw(source))
    assert query("select claim_dufynd_jarvis_event()") is None


def test_external_empty_gmail_history_is_healthy_and_retains_no_message_content():
    _, observer, _ = external_wait("gmail", policy="review", cursor="100")
    assert capture(observer, {"historyId": "200"})["inserted"] == 0
    assert (
        query("select last_cursor from dufynd_external_observers where observer_id=%s", (observer,))
        == "200"
    )
    assert (
        query(
            "select health_status from dufynd_external_observers where observer_id=%s", (observer,)
        )
        == "healthy"
    )


def test_external_branch_movement_and_pr_freshness_are_deterministic():
    observer = event_query(
        "select register_dufynd_observer('github_branch','scentai-mvp','{}',%s::jsonb,%s)",
        {"sha": "a" * 40},
        "a" * 40,
    )
    assert capture(observer, {"name": "scentai-mvp", "commit": {"sha": "a" * 40}})["inserted"] == 0
    assert capture(observer, {"name": "scentai-mvp", "commit": {"sha": "b" * 40}})["inserted"] == 1
    assert capture(observer, {"name": "scentai-mvp", "commit": {"sha": "b" * 40}})["inserted"] == 0
    task, _, source = external_wait()
    pr = event_query("select register_dufynd_observer('github_pr',%s)", source)
    assert event_query(
        "select bind_dufynd_external_wait(%s,%s,%s::jsonb,null,'freshness')",
        task,
        pr,
        ["github.pr.base_moved"],
    )
    raw = {
        "number": source,
        "state": "open",
        "merged": False,
        "head": {"sha": "a" * 40},
        "base": {"ref": "scentai-mvp", "sha": "a" * 40},
        "updated_at": "2026-10-02T00:00:00Z",
    }
    capture(pr, raw)
    raw["base"]["sha"] = "b" * 40
    capture(pr, raw)
    query("select process_dufynd_external_events()")
    assert task_state(task)["needs_freshness_recheck"]
    assert task_state(task)["status"] == "waiting_external"


def test_external_network_transport_receipt_rate_limit_etag_and_missing_credentials():
    import json

    import psycopg

    # Fake pg_net runs the actual portable polling/receipt logic without HTTP.
    # Every fixture/config change rolls back, including temporary net/vault schemas.
    with psycopg.connect(DSN) as db:
        db.execute("create schema net; create schema vault")
        db.execute("create table vault.decrypted_secrets(name text,decrypted_secret text)")
        db.execute(
            "create table net._http_response(id bigint,status_code int,content text,headers jsonb,timed_out boolean,error_msg text)"
        )
        db.execute("create table net.requests(id bigserial,url text,headers jsonb)")
        db.execute(
            "create function net.http_get(url text,headers jsonb,timeout_milliseconds int) returns bigint language sql as $$ insert into net.requests(url,headers) values(url,headers) returning id $$"
        )
        db.execute("update dufynd_external_observers set enabled=false")
        source = str(uuid4().int)
        observer = db.execute(
            "select register_dufynd_observer('github_ci',%s)", (source,)
        ).fetchone()[0]
        assert db.execute("select poll_dufynd_observers()").fetchone()[0]["attempted"] == 1
        request = db.execute(
            "select request_id from dufynd_external_observers where observer_id=%s", (observer,)
        ).fetchone()[0]
        db.execute(
            'insert into net._http_response values(%s,200,%s,\'{"etag":"fixture-etag"}\',false,null)',
            (request, json.dumps(ci_raw(source))),
        )
        db.execute("select poll_dufynd_observers()")
        assert (
            db.execute(
                "select health_status from dufynd_external_observers where observer_id=%s",
                (observer,),
            ).fetchone()[0]
            == "healthy"
        )
        assert (
            db.execute(
                "select count(*) from dufynd_jarvis_inbox where payload->>'observer_id'=%s",
                (observer,),
            ).fetchone()[0]
            == 1
        )
        db.execute(
            "update dufynd_external_observers set next_retry_at=now() where observer_id=%s",
            (observer,),
        )
        db.execute("select poll_dufynd_observers()")
        assert (
            db.execute(
                "select headers->>'If-None-Match' from net.requests order by id desc limit 1"
            ).fetchone()[0]
            == "fixture-etag"
        )
        request = db.execute(
            "select request_id from dufynd_external_observers where observer_id=%s", (observer,)
        ).fetchone()[0]
        db.execute(
            "insert into net._http_response values(%s,429,'{}','{\"retry-after\":\"300\"}',false,null)",
            (request,),
        )
        db.execute("select poll_dufynd_observers()")
        assert (
            db.execute(
                "select last_error from dufynd_external_observers where observer_id=%s", (observer,)
            ).fetchone()[0]
            == "rate_limited"
        )
        mail = db.execute(
            "select register_dufynd_observer('gmail',%s,'{}','{}','100')", (uuid4().hex[:16],)
        ).fetchone()[0]
        db.execute("select poll_dufynd_observers()")
        assert (
            db.execute(
                "select health_status from dufynd_external_observers where observer_id=%s", (mail,)
            ).fetchone()[0]
            == "blocked_configuration"
        )
        db.rollback()


def test_external_gmail_watermarks_never_rewind_and_same_timestamp_new_id_detected():
    _, observer, source = external_wait(
        "gmail",
        policy="review",
        baseline={"watermark_ms": "2000", "seen_message_ids": ["abcdef12"]},
        cursor="100",
    )
    assert (
        capture(observer, mail_raw(source, message="abcdef13", date="1999", history="99"))[
            "inserted"
        ]
        == 0
    )
    assert (
        query("select last_cursor from dufynd_external_observers where observer_id=%s", (observer,))
        == "100"
    )
    assert (
        query(
            "select last_snapshot->>'watermark_ms' from dufynd_external_observers where observer_id=%s",
            (observer,),
        )
        == "2000"
    )
    assert (
        capture(observer, mail_raw(source, message="abcdef14", date="2000", history="101"))[
            "inserted"
        ]
        == 1
    )


def test_external_concurrent_observations_persist_one_event():
    _, observer, source = external_wait()
    barrier = Barrier(2)

    def observe(_):
        barrier.wait(timeout=10)
        return capture(observer, ci_raw(source))

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(observe, range(2)))
    assert sum(x["inserted"] for x in results) == 1
    assert inbox_count(observer) == 1


def test_external_extension_outage_cannot_stop_supervisor_reconciliation():
    import psycopg

    with psycopg.connect(DSN) as db:
        db.execute("create schema net")  # Missing pg_net response/dispatch tables.
        db.execute("update dufynd_external_observers set enabled=false")
        observer = db.execute(
            "select register_dufynd_observer('github_ci',%s)", (str(uuid4().int),)
        ).fetchone()[0]
        result = db.execute("select reconcile_dufynd_supervisor_v2()").fetchone()[0]
        assert "executions" in result and "external_events" in result
        assert (
            db.execute(
                "select last_error from dufynd_external_observers where observer_id=%s", (observer,)
            ).fetchone()[0]
            == "observer_transport_unavailable"
        )
        db.rollback()


@pytest.mark.parametrize(
    "required,forbidden,allowed",
    [
        (["supabase.execution_state"], [], True),
        (["github.ci.observe"], [], False),
        (["unknown.permission"], [], False),
        (["gmail.send"], [], False),
        (["social.publish"], [], False),
        (["supabase.execution_state"], ["supabase.execution_state"], False),
    ],
)
def test_capability_matching_required_missing_unknown_sensitive_and_forbidden(
    required, forbidden, allowed
):
    import json

    task, _, _ = external_wait(
        payload={"kind": "durability_probe", "steps": 2, "interval_seconds": 2}
    )
    query(
        "update dufynd_autonomy_tasks set required_capabilities=%s::jsonb, forbidden_actions=%s::jsonb where task_id=%s returning task_id",
        (json.dumps(required), json.dumps(forbidden), task),
    )
    contract = query(
        "select select_dufynd_handler(%s,'supervisor',%s::jsonb,%s::jsonb,'durable')",
        (
            task,
            json.dumps(["db:" + task]),
            json.dumps({"kind": "durability_probe", "steps": 2, "interval_seconds": 2}),
        ),
    )
    assert bool(contract) == allowed


def test_packet_is_compact_immutable_and_resume_keeps_version():
    import json

    import psycopg

    task, result = durable_fixture()
    e = result["execution"]
    packet = e["task_packet"]
    assert packet["packet_version"] == 1 and packet["required_capabilities"] == [
        "supabase.execution_state"
    ]
    assert packet["allowed_resources"] == e["resources"]
    assert len(json.dumps(packet)) < 8192
    assert "instruction" not in packet and "chat_history" not in packet
    assert packet["relevant_evidence"] == []
    with psycopg.connect(DSN) as db:
        db.execute("select set_config('dufynd.execution_write',%s,true)", (e["execution_id"],))
        with pytest.raises(Exception, match="immutable execution packet"):
            db.execute(
                'update dufynd_execution_runs set task_packet=task_packet||\'{"goal":"silently changed"}\' where execution_id=%s',
                (e["execution_id"],),
            )
        db.rollback()
    e = take_execution(e)
    execution_checkpoint(e, 1)
    force_execution_expired(e)
    query("select reconcile_dufynd_executions()")
    resumed = execution_state(e)
    assert resumed["task_packet"] == packet and resumed["packet_hash"] == e["packet_hash"]
    assert resumed["lease_token"] != e["lease_token"]


def test_handler_additional_harmless_capability_is_not_granted_to_packet():
    import psycopg

    task, result = durable_fixture()
    e = result["execution"]
    with psycopg.connect(DSN) as db:
        db.execute(
            "update dufynd_handler_contracts set contract=jsonb_set(contract,'{capabilities}','[\"supabase.execution_state\",\"github.read\"]') where handler_id='durability_probe'"
        )
        assert db.execute(
            "select dufynd_execution_contract_valid(%s)", (e["execution_id"],)
        ).fetchone()[0]
        assert "github.read" not in e["task_packet"]["required_capabilities"]
        db.rollback()


@pytest.mark.parametrize(
    "scope,resources",
    [("commerce", ["db:fixture"]), ("supervisor", ["repo:main"]), ("supervisor", ["db:foreign"])],
)
def test_capability_scope_and_resource_conflicts_deny(scope, resources):
    import json

    task, _, _ = external_wait()
    assert (
        query(
            "select select_dufynd_handler(%s,%s,%s::jsonb,'{\"kind\":\"durability_probe\"}','durable')",
            (task, scope, json.dumps(resources)),
        )
        is None
    )


def test_revoked_handler_cannot_dispatch_or_progress():
    import psycopg

    _, result = durable_fixture()
    e = result["execution"]
    with psycopg.connect(DSN) as db:
        db.execute(
            "update dufynd_handler_contracts set enabled=false where handler_id='durability_probe'"
        )
        assert (
            db.execute(
                "select take_dufynd_execution('123','test',%s)", (e["execution_id"],)
            ).fetchone()[0]
            is None
        )
        assert not db.execute(
            "select dufynd_execution_contract_valid(%s)", (e["execution_id"],)
        ).fetchone()[0]
        db.rollback()


def test_supervisor_state_audit_requires_live_certification_and_persists_readonly_findings():
    import json

    task = "supervisor_v2_state_audit_acceptance_20261002"
    payload = {"kind": "supervisor_state_audit", "steps": 1, "interval_seconds": 2}
    resources = ["db:jarvis.supervisor_v2.health"]
    ordinary = "ordinary-audit-" + str(uuid4())
    blocked = query(
        "select prepare_dufynd_execution(%s,%s,'supervisor',%s::jsonb,%s::jsonb,'durable')",
        (ordinary, ordinary, json.dumps(resources), json.dumps(payload)),
    )
    assert not blocked["allowed"]
    prepared = query(
        "select prepare_dufynd_execution(%s,%s,'supervisor',%s::jsonb,%s::jsonb,'durable')",
        (task, task, json.dumps(resources), json.dumps(payload)),
    )
    e = prepared["execution"]
    assert e["task_packet"]["required_capabilities"] == [
        "supabase.execution_state",
        "supabase.task_state",
    ]
    assert e["task_packet"]["handler_contract"]["allowed_resources"] == resources
    assert not query("select certify_dufynd_state_audit(%s)", (e["execution_id"],))
    e = take_execution(e)
    checkpoint = execution_checkpoint(e, 1)
    audit = checkpoint["last_checkpoint"]["audit"]
    assert audit["audit_version"] == 1 and audit["paid_provider_calls"] == 0
    assert type(audit["unclassified_human_gates"]) is int
    assert type(audit["stale_active_leases"]) is int
    assert "instruction" not in json.dumps(audit) and "task_id" not in json.dumps(audit)
    assert finish_execution(e)
    assert query("select certify_dufynd_state_audit(%s)", (e["execution_id"],))
    assert (
        query(
            "select contract->>'certification_status' from dufynd_handler_contracts where handler_id='supervisor_state_audit'"
        )
        == "certified"
    )
    after = query(
        "select prepare_dufynd_execution(%s,%s,'supervisor',%s::jsonb,%s::jsonb,'durable')",
        (ordinary, ordinary, json.dumps(resources), json.dumps(payload)),
    )
    assert after["allowed"]
    other = query(
        "select prepare_dufynd_execution(%s,%s,'supervisor','[\"db:foreign\"]',%s::jsonb,'durable')",
        (str(uuid4()), str(uuid4()), json.dumps(payload)),
    )
    assert not other["allowed"]
