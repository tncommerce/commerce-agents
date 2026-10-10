"""Real PostgreSQL contention tests, executed by the dedicated CI service job."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
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
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*receipt_projection.sql")).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*purchase_freshness_handler.sql")).read_text()
        )
        connection.execute(
            next(
                (ROOT / "supabase/migrations").glob("*purchase_acceptance_receipt.sql")
            ).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*ci_pr_verifier.sql")).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*supervisor_recovery_audit.sql")).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*observer_credential_plane.sql")).read_text()
        )
        connection.execute(
            next(
                (ROOT / "supabase/migrations").glob("*private_observer_health_projection.sql")
            ).read_text()
        )
        connection.execute(
            next(
                (ROOT / "supabase/migrations").glob("*audit_known_terminal_states.sql")
            ).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*paid_dispatch_revalidation.sql")).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*nightshift_budget_resolver.sql")).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*counted_preflight_snapshot.sql")).read_text()
        )
        connection.execute(
            next(
                (ROOT / "supabase/migrations").glob("*private_observer_acceptance_gate.sql")
            ).read_text()
        )
        connection.execute(
            next(
                (ROOT / "supabase/migrations").glob("*private_observer_recurring_capture.sql")
            ).read_text()
        )
        connection.execute(
            next(
                (ROOT / "supabase/migrations").glob("*dependency_observer_reliability.sql")
            ).read_text()
        )
        connection.execute(
            next((ROOT / "supabase/migrations").glob("*gmail_observer_recovery.sql")).read_text()
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
    # Two different certified handlers may own disjoint resources simultaneously.
    _, probe = durable_fixture()
    assert probe["allowed"]
    audit_run = take_execution(after["execution"])
    probe_run = take_execution(probe["execution"])
    assert audit_run and probe_run and audit_run["execution_id"] != probe_run["execution_id"]
    execution_checkpoint(audit_run, 1)
    assert finish_execution(audit_run)
    for step in range(1, 4):
        execution_checkpoint(probe_run, step)
    assert finish_execution(probe_run)
    other = query(
        "select prepare_dufynd_execution(%s,%s,'supervisor','[\"db:foreign\"]',%s::jsonb,'durable')",
        (str(uuid4()), str(uuid4()), json.dumps(payload)),
    )
    assert not other["allowed"]


def test_acceptance_receipt_projects_verified_execution_without_inventing_ci_or_duplicates():
    import json

    task, result = durable_fixture()
    e = take_execution(result["execution"])
    for step in range(1, 4):
        execution_checkpoint(e, step)
    assert finish_execution(e)
    key = "jarvis.capability_packet.acceptance"
    query(
        "insert into dufynd_master_status(key,value) values(%s,%s::jsonb) on conflict(key) do update set value=excluded.value returning key",
        (key, json.dumps({"status": "armed", "task_id": task, "execution_id": e["execution_id"]})),
    )
    assert query("select project_dufynd_acceptance_receipts()")["projected"] >= 1
    receipt = query("select value from dufynd_master_status where key=%s", (key,))
    assert receipt["status"] == "live_execution_verified"
    assert receipt["execution_receipt"]["execution_verified"]
    assert receipt["execution_receipt"]["lease_released"]
    assert not receipt["execution_receipt"]["ci_acceptance_inferred"]
    assert query("select project_dufynd_acceptance_receipts()")["projected"] == 0
    query(
        'update dufynd_master_status set value=value||\'{"status":"live_accepted"}\' where key=%s returning key',
        (key,),
    )
    query("select project_dufynd_acceptance_receipts()")
    assert (
        query("select value->>'status' from dufynd_master_status where key=%s", (key,))
        == "live_accepted"
    )
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (task,)) == 1


@pytest.fixture(scope="module")
def purchase_net(database):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute((ROOT / "tests/sql_dufynd_purchase_net_fixture.sql").read_text())
    yield


PURCHASE_OFFER = "perfumetrader-rabanne-1-million-edt-100"
PURCHASE_HTML = (
    '<h1 id="product-name">Paco Rabanne 1 Million Eau de Toilette 100 ml</h1> '
    '"productName":"Paco Rabanne 1 Million Eau de Toilette 100 ml",'
    '"productSku":"16978322","productPrice":"71.9000" '
    '<meta itemprop="gtin13" content="3349666007921" /> '
    '<meta itemprop="availability" content="InStock" />'
)
PURCHASE_SHIPPING = "pauschal mit 4,99 € pro Bestellung"


def purchase_payload():
    return query(
        "select jsonb_build_object('kind','purchase_destination_freshness_audit','steps',1,'interval_seconds',2,"
        "'offer_id',offer_id,'product_id',product_id,'canonical_identity',canonical_identity,'offer_contract',offer_contract,"
        "'last_verified_at',last_verified_at,'expiry',last_verified_at+interval '72 hours',"
        "'verification_contract','perfumetrader_exact_html_v1','allowed_mutations','[\"verification_evidence\"]'::jsonb)"
        " from dufynd_purchase_verification_targets where offer_id=%s",
        (PURCHASE_OFFER,),
    )


def purchase_decision(html=PURCHASE_HTML, shipping=PURCHASE_SHIPPING, payload=None):
    import json

    return query(
        "select evaluate_dufynd_purchase_page(%s::jsonb,%s,%s,200,200)",
        (json.dumps(payload or purchase_payload()), html, shipping),
    )["decision"]


def test_purchase_safe_identity_refresh(purchase_net):
    assert purchase_decision() == "safe_evidence_refresh"


@pytest.mark.parametrize(
    ("old", "new", "decision"),
    [
        ("71.9000", "70.9000", "price_review_required"),
        ("InStock", "OutOfStock", "stock_unverified_or_changed"),
        ("100 ml", "50 ml", "variant_identity_mismatch"),
        ("Eau de Toilette", "Eau de Parfum", "variant_identity_mismatch"),
        ("16978322", "16978323", "merchant_identity_mismatch"),
        ("3349666007921", "3349666007891", "gtin_mismatch"),
        ("100 ml", "100 ml Refill", "variant_identity_mismatch"),
    ],
)
def test_purchase_exact_variant_price_and_stock_fail_closed(purchase_net, old, new, decision):
    assert purchase_decision(PURCHASE_HTML.replace(old, new)) == decision


def test_purchase_invalid_route_never_refreshes(purchase_net):
    payload = purchase_payload()
    payload["offer_contract"]["affiliate_url"] += "&awinmid=99999"
    assert purchase_decision(payload=payload) == "route_contract_mismatch"


def test_purchase_shipping_change_requires_review(purchase_net):
    assert purchase_decision(shipping="Versandkosten 5,99 €") == "shipping_review_required"


def test_purchase_fresh_offer_no_wake(purchase_net):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "update dufynd_purchase_verification_targets set enabled=true,certification_due=false,last_result=null,last_verified_at=now()"
        )
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 0}


def test_purchase_scheduler_observation_preserves_verification_truth(purchase_net):
    import psycopg

    offer = "perfumetrader-rabanne-1-million-edt-100"
    with psycopg.connect(DSN, autocommit=True) as c:
        oid = c.execute(
            "select register_dufynd_observer('internal_dependency',%s)",
            ("purchase-freshness:" + offer,),
        ).fetchone()[0]
        c.execute(
            "update dufynd_external_observers set health_status='initializing',"
            "last_attempt_at=null,last_success_at=null,next_retry_at=now()-interval '1 hour'"
            " where observer_id=%s",
            (oid,),
        )
        c.execute(
            "update dufynd_purchase_verification_targets set enabled=true,"
            "certification_due=false,last_verified_at=now(),last_result=null where offer_id=%s",
            (offer,),
        )
        before = c.execute(
            "select last_verified_at,offer_contract from dufynd_purchase_verification_targets"
            " where offer_id=%s",
            (offer,),
        ).fetchone()
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 0}
    assert query(
        "select health_status='healthy' and last_attempt_at is not null and last_success_at is not null"
        " and next_retry_at>now() and last_snapshot->>'monitor_basis'='purchase_target_scheduler'"
        " from dufynd_external_observers where observer_id=%s",
        (oid,),
    )
    with psycopg.connect(DSN, autocommit=True) as c:
        assert (
            c.execute(
                "select last_verified_at,offer_contract from dufynd_purchase_verification_targets"
                " where offer_id=%s",
                (offer,),
            ).fetchone()
            == before
        )
        c.execute(
            "update dufynd_purchase_verification_targets set enabled=false where offer_id=%s",
            (offer,),
        )
    query("select wake_dufynd_purchase_freshness()")
    assert query(
        "select health_status='blocked_configuration' and last_error='purchase_target_disabled'"
        " from dufynd_external_observers where observer_id=%s",
        (oid,),
    )


def test_purchase_pre_expiry_before_today_regression(purchase_net):
    # The real 09-29 12:04:36 verification would wake 10-01 12:04:36,
    # a full day before the 10-02 12:04:36 production exclusion.
    assert query(
        "select '2026-09-29T12:04:36Z'::timestamptz + make_interval(hours=>max_age_hours-safety_window_hours)"
        " < '2026-10-02T12:04:36Z'::timestamptz from dufynd_purchase_verification_targets"
    )
    from datetime import UTC, datetime

    assert query(
        "select '2026-09-29T12:04:36Z'::timestamptz + make_interval(hours=>max_age_hours-safety_window_hours)"
        " from dufynd_purchase_verification_targets"
    ) == datetime(2026, 10, 1, 12, 4, 36, tzinfo=UTC)


def test_purchase_live_chain_deduplicates_and_fences(purchase_net):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "update dufynd_purchase_verification_targets set enabled=false,certification_due=true,last_result=null"
        )
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 1}
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 0}
    query("select process_dufynd_external_events()")
    eid = query(
        "select execution_id from dufynd_execution_runs where task_id='purchase_freshness_acceptance_20261002'"
    )
    e = query("select take_dufynd_execution('999999','purchase-test',%s)", (eid,))
    assert e["task_packet"]["payload"]["allowed_mutations"] == ["verification_evidence"]
    assert query("select take_dufynd_execution('999998','duplicate-worker',%s)", (eid,)) is None
    assert (
        query("select checkpoint_dufynd_execution(%s,%s,'wrong-worker',1)", (eid, e["lease_token"]))
        is None
    )
    query("select checkpoint_dufynd_execution(%s,%s,'purchase-test',1)", (eid, e["lease_token"]))
    verified = query(
        "select checkpoint_dufynd_execution(%s,%s,'purchase-test',1)", (eid, e["lease_token"])
    )
    assert verified["last_checkpoint"]["audit"]["decision"] == "safe_evidence_refresh"
    assert query("select finish_dufynd_execution(%s,%s,'purchase-test')", (eid, e["lease_token"]))
    assert query("select certify_dufynd_purchase_freshness(%s)", (eid,))
    assert (
        query(
            "select count(*) from dufynd_purchase_verification_evidence where execution_id=%s",
            (eid,),
        )
        == 1
    )
    assert (
        query(
            "select status from dufynd_autonomy_tasks where task_id='purchase_freshness_acceptance_20261002'"
        )
        == "done"
    )


def test_purchase_approaching_expiry_wake_and_chatless_recovery(purchase_net):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "update dufynd_purchase_verification_targets set enabled=true,certification_due=false,last_result=null,last_verified_at=now()-interval '49 hours'"
        )
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 1}
    query("select process_dufynd_external_events()")
    eid = query(
        "select execution_id from dufynd_execution_runs where handler_id='purchase_destination_freshness_audit' and status='dispatch_pending'"
    )
    e = query("select take_dufynd_execution('888888','crash-worker',%s)", (eid,))
    assert query(
        "select fail_dufynd_execution(%s,%s,'crash-worker','simulated_crash')",
        (eid, e["lease_token"]),
    )
    query("select reconcile_dufynd_executions()")
    assert (
        query("select checkpoint_dufynd_execution(%s,%s,'crash-worker',1)", (eid, e["lease_token"]))
        is None
    )
    for _ in range(3):
        query("select reconcile_dufynd_executions()")
    final = query(
        "select row_to_json(e)::jsonb from dufynd_execution_runs e where execution_id=%s", (eid,)
    )
    assert final["status"] == "completed"
    assert final["worker_type"] == "deterministic_supervisor"
    assert final["packet_hash"] == e["packet_hash"]
    assert final["recovery_count"] >= 1
    assert (
        query(
            "select count(*) from dufynd_purchase_verification_evidence where execution_id=%s",
            (eid,),
        )
        == 1
    )


def test_purchase_unknown_capability_cannot_dispatch(purchase_net):
    import json

    import psycopg

    tid = f"purchase-unknown-{uuid4()}"
    resources = f'["db:purchase-evidence:{PURCHASE_OFFER}"]'
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "insert into dufynd_autonomy_tasks(task_id,domain,title,instruction,status,budget_class,durability_policy,resource_scope,required_capabilities) values(%s,'supervisor','test','test','ready','free','durable',%s::jsonb,'[\"unknown.capability\"]')",
            (tid, resources),
        )
    denied = query(
        "select prepare_dufynd_execution(%s,%s,'supervisor',%s::jsonb,%s::jsonb,'durable')",
        (tid, tid, resources, json.dumps(purchase_payload())),
    )
    assert not denied["allowed"]
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (tid,)) == 0


def test_purchase_concurrent_same_offer_has_one_owner(purchase_net):
    import json

    payload = json.dumps(purchase_payload())
    resource = f'["db:purchase-evidence:{PURCHASE_OFFER}"]'
    tids = [f"purchase-concurrent-{uuid4()}" for _ in range(2)]
    barrier = Barrier(2)

    def claim(tid):
        barrier.wait()
        return query(
            "select prepare_dufynd_execution(%s,%s,'supervisor',%s::jsonb,%s::jsonb,'durable')",
            (tid, tid, resource, payload),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, tids))
    assert sum(x["allowed"] for x in outcomes) == 1
    winner = next(x["execution"] for x in outcomes if x["allowed"])
    for _ in range(3):
        query("select reconcile_dufynd_executions()")
    assert (
        query(
            "select status from dufynd_execution_runs where execution_id=%s",
            (winner["execution_id"],),
        )
        == "completed"
    )


def test_purchase_non_200_never_creates_safe_evidence(purchase_net):
    import json

    result = query(
        "select evaluate_dufynd_purchase_page(%s::jsonb,%s,%s,403,200)",
        (json.dumps(purchase_payload()), PURCHASE_HTML, PURCHASE_SHIPPING),
    )
    assert result["decision"] == "transport_unverified"


def test_purchase_ambiguous_primary_fields_fail_closed(purchase_net):
    assert purchase_decision(PURCHASE_HTML + '\n"productSku":"other"') == "ambiguous_primary_fields"


def test_purchase_visible_variant_disagrees_with_metadata(purchase_net):
    html = PURCHASE_HTML.replace("100 ml</h1>", "50 ml</h1>")
    assert purchase_decision(html) == "variant_identity_mismatch"


def test_purchase_acceptance_receipt_projects_existing_evidence(purchase_net):
    import json

    eid = query(
        "select execution_id from dufynd_execution_runs where task_id='purchase_freshness_acceptance_20261002'"
    )
    query(
        "insert into dufynd_master_status(key,value) values('jarvis.purchase_freshness.acceptance',%s::jsonb) on conflict(key) do update set value=excluded.value returning key",
        (
            json.dumps(
                {
                    "status": "armed",
                    "task_id": "purchase_freshness_acceptance_20261002",
                    "execution_id": str(eid),
                }
            ),
        ),
    )
    query("select project_dufynd_acceptance_receipts()")
    receipt = query(
        "select value from dufynd_master_status where key='jarvis.purchase_freshness.acceptance'"
    )
    assert receipt["status"] == "live_execution_verified"
    assert receipt["execution_receipt"]["execution_verified"]
    assert receipt["execution_receipt"]["lease_released"]
    assert receipt["execution_receipt"]["report_hash"]
    assert query("select project_dufynd_acceptance_receipts()")["projected"] == 0


def ci_pr_target(*, acceptance=False):
    pr = str(100000 + uuid4().int % 800000000)
    run = str(10000000000 + uuid4().int % 80000000000)
    scheduled = query(
        "select schedule_dufynd_ci_pr_verification(%s,%s,%s,%s,%s)",
        (pr, run, "a" * 40, "b" * 40, acceptance),
    )
    assert scheduled["scheduled"]
    payload = task_state(scheduled["task_id"])["durable_payload"]
    pr_raw = {
        "number": int(pr),
        "merged": True,
        "state": "closed",
        "base": {"ref": "scentai-mvp", "sha": "a" * 40},
        "head": {"sha": "b" * 40},
        "merge_commit_sha": "a" * 40,
        "updated_at": "2026-10-02T13:00:00Z",
    }
    capture("github_pr:" + pr, pr_raw)
    capture("github_ci:" + run, ci_raw(run))
    return scheduled["task_id"], payload, pr_raw


@pytest.fixture(scope="module")
def ci_pr_admitted():
    assert not query(
        "select schedule_dufynd_ci_pr_verification('623','37014817569',%s,%s)", ("a" * 40, "b" * 40)
    )["scheduled"]
    task, payload, raw = ci_pr_target(acceptance=True)
    assert query("select process_dufynd_external_events()")
    query("select reconcile_dufynd_executions()")
    e = query("select to_jsonb(e) from dufynd_execution_runs e where task_id=%s", (task,))
    assert e["status"] == "completed"
    assert e["last_checkpoint"]["audit"]["decision"] == "verified"
    assert query("select certify_dufynd_ci_pr_verifier(%s)", (e["execution_id"],))
    return e


def test_ci_pr_free_acceptance_registry_receipt_and_packet(ci_pr_admitted):
    import json

    e = ci_pr_admitted
    assert e["worker_type"] == "deterministic_supervisor"
    assert task_state(e["task_id"])["released_at"]
    assert e["task_packet"]["required_capabilities"] == [
        "github.ci.observe",
        "github.read",
        "supabase.execution_state",
        "supabase.task_state",
    ]
    assert e["last_checkpoint"]["audit"]["deployment_verified"] is False
    query(
        "insert into dufynd_master_status(key,value) values('jarvis.ci_pr_verifier.acceptance',%s::jsonb) returning key",
        (
            json.dumps(
                {
                    "task_id": e["task_id"],
                    "execution_id": e["execution_id"],
                    "status": "live_accepted",
                }
            ),
        ),
    )
    query("select project_dufynd_acceptance_receipts()")
    receipt = query(
        "select value->'execution_receipt' from dufynd_master_status where key='jarvis.ci_pr_verifier.acceptance'"
    )
    assert receipt["execution_verified"] and receipt["dispatch_count"] == 1
    assert receipt["report_hash"] == e["last_checkpoint"]["audit_hash"]
    assert not receipt["ci_acceptance_inferred"]


@pytest.mark.parametrize(
    "change,decision",
    [
        ("pr_head", "pr_sha_mismatch"),
        ("pr_merge", "pr_sha_mismatch"),
        ("ci_sha", "ci_sha_mismatch"),
        ("ci_failed", "ci_not_successful"),
        ("ci_queued", "ci_not_successful"),
        ("pr_open", "pr_not_merged_to_integration"),
        ("stale", "source_unverified_or_stale"),
        ("unhealthy", "source_unverified_or_stale"),
    ],
)
def test_ci_pr_exact_truth_fail_closed(ci_pr_admitted, change, decision):
    import json

    task, payload, raw = ci_pr_target()
    run = payload["ci_run_id"]
    if change in ("pr_head", "pr_merge", "pr_open"):
        if change == "pr_head":
            raw["head"]["sha"] = "c" * 40
        if change == "pr_merge":
            raw["merge_commit_sha"] = "c" * 40
        if change == "pr_open":
            raw.update(merged=False, state="open")
        capture("github_pr:" + payload["pr_number"], raw)
    if change == "ci_sha":
        capture("github_ci:" + run, ci_raw(run, sha="c" * 40))
    if change == "ci_failed":
        capture("github_ci:" + run, ci_raw(run, conclusion="failure"))
    if change == "ci_queued":
        capture("github_ci:" + run, ci_raw(run, state="queued", conclusion=None))
    if change == "stale":
        query(
            "update dufynd_external_observers set last_success_at=now()-interval '21 minutes' where observer_id=%s returning true",
            ("github_ci:" + run,),
        )
    if change == "unhealthy":
        query("select dufynd_observer_failure(%s,'transport_failure',500)", ("github_ci:" + run,))
    report = query("select read_dufynd_ci_pr_audit(%s::jsonb)", (json.dumps(payload),))
    assert report["decision"] == decision
    assert not report["approvals_inferred"] and not report["business_mutations"]
    # Retire this isolated fixture target before later global event reevaluation.
    query("update dufynd_autonomy_tasks set status='done' where task_id=%s returning true", (task,))


@pytest.mark.parametrize("pr", ["1", "598", "0", "main", "622;select 1"])
def test_ci_pr_protected_or_invalid_targets_not_scheduled(ci_pr_admitted, pr):
    assert not query(
        "select schedule_dufynd_ci_pr_verification(%s,'37014817569',%s,%s)",
        (pr, "a" * 40, "b" * 40),
    )["scheduled"]


def test_ci_pr_main_and_wrong_workflow_rejected(ci_pr_admitted):
    import psycopg

    task, payload, raw = ci_pr_target()
    raw["base"]["ref"] = "main"
    with pytest.raises(psycopg.errors.RaiseException, match="PR identity mismatch"):
        capture("github_pr:" + payload["pr_number"], raw)
    bad = ci_raw(payload["ci_run_id"])
    bad["path"] = ".github/workflows/not-ci.yml"
    with pytest.raises(psycopg.errors.RaiseException, match="CI workflow mismatch"):
        capture("github_ci:" + payload["ci_run_id"], bad)
    query("update dufynd_autonomy_tasks set status='done' where task_id=%s returning true", (task,))


def test_ci_pr_duplicate_event_schedule_and_chatless_completion(ci_pr_admitted):
    task, payload, raw = ci_pr_target()
    again = query(
        "select schedule_dufynd_ci_pr_verification(%s,%s,%s,%s)",
        tuple(
            payload[k]
            for k in ("pr_number", "ci_run_id", "expected_merge_sha", "expected_pr_head_sha")
        ),
    )
    assert again["reused"] and again["task_id"] == task
    assert capture("github_pr:" + payload["pr_number"], raw)["inserted"] == 0
    query("select process_dufynd_external_events()")
    query("select process_dufynd_external_events()")
    query("select reconcile_dufynd_executions()")
    e = query("select to_jsonb(e) from dufynd_execution_runs e where task_id=%s", (task,))
    assert e["status"] == "completed" and task_state(task)["status"] == "done"
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (task,)) == 1
    assert (
        query(
            "select count(*) from dufynd_ci_pr_verification_evidence where execution_id=%s",
            (e["execution_id"],),
        )
        == 1
    )


def test_ci_pr_changed_ci_after_dispatch_blocks_completion(ci_pr_admitted):
    task, payload, raw = ci_pr_target()
    query("select process_dufynd_external_events()")
    capture("github_ci:" + payload["ci_run_id"], ci_raw(payload["ci_run_id"], conclusion="failure"))
    query("select reconcile_dufynd_executions()")
    assert task_state(task)["status"] == "blocked"
    assert task_state(task)["blocked_reason"] == "ci_not_successful"


def test_ci_pr_unknown_capability_prevents_dispatch(ci_pr_admitted):
    task, payload, raw = ci_pr_target()
    query(
        "update dufynd_autonomy_tasks set required_capabilities='[\"github.unknown\"]' where task_id=%s returning true",
        (task,),
    )
    query("select process_dufynd_external_events()")
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (task,)) == 0


def test_ci_pr_crash_rotates_fence_and_resumes_same_packet(ci_pr_admitted):
    task, payload, raw = ci_pr_target()
    query("select process_dufynd_external_events()")
    e = query("select to_jsonb(e) from dufynd_execution_runs e where task_id=%s", (task,))
    e = take_execution(e)
    force_execution_expired(e)
    query("select reconcile_dufynd_executions()")
    assert execution_checkpoint(e, 1) is None
    query("select reconcile_dufynd_executions()")
    finished = execution_state(e)
    assert finished["status"] == "completed"
    assert finished["packet_hash"] == e["packet_hash"]
    assert finished["recovery_count"] == 1
    assert task_state(task)["released_at"]


@pytest.mark.parametrize(
    ("task_changes", "execution", "reason"),
    [
        (
            {"worker_state": "done", "status": "done", "released_at": "2026-10-02T12:00:00Z"},
            {"status": "completed", "lease_token": "a"},
            None,
        ),
        ({"lease_expires_at": "2026-10-02T11:00:00Z"}, None, "expired_active_lease"),
        ({"released_at": "2026-10-02T11:00:00Z"}, None, "active_released_lease"),
        ({"heartbeat_at": "2026-10-02T11:00:00Z"}, None, "stale_heartbeat"),
        ({"last_progress_at": "2026-10-02T11:00:00Z"}, None, "progress_stalled"),
        ({}, {"status": "completed", "lease_token": "a"}, "completed_execution_unreleased_lease"),
        (
            {"status": "done"},
            {"status": "running", "lease_token": "a"},
            "done_task_running_execution",
        ),
        ({}, {"status": "running", "lease_token": "old"}, "stale_fencing_token"),
        (
            {"worker_owner": None},
            {"status": "retryable", "lease_token": "a"},
            "retryable_without_owner",
        ),
        ({"status": "invented"}, None, "unknown_state"),
    ],
)
def test_recovery_audit_readonly_classification(task_changes, execution, reason):
    import json

    task = {
        "status": "in_progress",
        "worker_state": "working",
        "lease_token": "a",
        "worker_owner": "durable_recovery",
        "released_at": None,
        "lease_expires_at": "2026-10-02T12:03:00Z",
        "heartbeat_at": "2026-10-02T12:00:00Z",
        "last_progress_at": "2026-10-02T12:00:00Z",
    } | task_changes
    args = (json.dumps(task), json.dumps(execution) if execution else None)
    sql = "select dufynd_recovery_findings(%s::jsonb,%s::jsonb,'2026-10-02T12:00:00Z')"
    first = query(sql, args)
    assert first == query(sql, args)  # duplicate/retry requires no persisted audit owner
    assert (reason in first) if reason else first == []


def test_extended_audit_preserves_existing_packet_and_no_chat_contract():
    before = query("select count(*) from dufynd_execution_runs")
    audit = query("select read_dufynd_supervisor_audit()")
    assert audit["extension_revision"] == 2
    assert not audit["recovery_consistency"]["repair_performed"]
    assert not audit["dependency_readiness"]["state_mutated"]
    assert audit["unknown_state_fail_closed"] and not audit["chat_history_required"]
    assert query("select count(*) from dufynd_execution_runs") == before


def broker_health_payload(*, checked_at=None):
    checked = checked_at or datetime.now(UTC)
    return {
        "render": {
            "credential_id": "render_deploy_broker",
            "provider": "render",
            "account_alias": "tncommerce_render",
            "allowed_operations": ["deployment.read"],
            "allowed_resources": ["srv-dakpfrnf3r2c73dr3f20"],
            "oauth_scopes": [],
            "secret_reference": "dufynd_observer_render_read_token",
            "status": "healthy",
            "expires_at": None,
            "refreshed_at": None,
            "revoked_at": None,
            "last_health_check": checked.isoformat(),
            "health_reason": "healthy",
            "rotation_due_at": None,
        },
        "gmail": {
            "credential_id": "gmail_known_threads",
            "provider": "gmail",
            "account_alias": "dufynd_owner_mailbox",
            "allowed_operations": ["thread.metadata", "history.read"],
            "allowed_resources": [
                "1a0f385ed98c6af8",
                "1a0f69c169fb928f",
                "1a0f6a90772a743d",
            ],
            "oauth_scopes": ["https://www.googleapis.com/auth/gmail.metadata"],
            "secret_reference": "dufynd_observer_gmail_read_access_token",
            "status": "healthy",
            "expires_at": (checked + timedelta(hours=1)).isoformat(),
            "refreshed_at": (checked - timedelta(minutes=1)).isoformat(),
            "revoked_at": None,
            "last_health_check": checked.isoformat(),
            "health_reason": "healthy",
            "rotation_due_at": None,
        },
    }


def test_broker_health_projection_preserves_activation_and_projects_no_secrets():
    import json

    query(
        "update dufynd_observer_credentials set status='missing_configuration',"
        "health_reason='missing_configuration',expires_at=null,refreshed_at=null,"
        "revoked_at=null,last_health_check=null,rotation_due_at=null,"
        "activation_enabled=(provider='render') returning true"
    )
    health = broker_health_payload()
    projected = query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(health),))

    assert projected["projected"] == 2
    assert not projected["activation_changed"]
    assert projected["render"]["status"] == "healthy"
    assert projected["gmail"]["status"] == "healthy"
    assert query(
        "select activation_enabled from dufynd_observer_credentials where provider='render'"
    )
    assert not query(
        "select activation_enabled from dufynd_observer_credentials where provider='gmail'"
    )
    assert not query(
        "select capture_dufynd_broker_observation("
        "'gmail_known_threads','gmail:1a0f69c169fb928f','{}')"
    )["accepted"]
    saved = query(
        "select jsonb_object_agg(provider,to_jsonb(c)-'activation_enabled') "
        "from dufynd_observer_credentials c"
    )
    for metadata in saved.values():
        assert "access_token" not in metadata
        assert "refresh_token" not in metadata
        assert "client_secret" not in metadata

    query(
        "update dufynd_observer_credentials set status='missing_configuration',"
        "health_reason='missing_configuration',expires_at=null,refreshed_at=null,"
        "revoked_at=null,last_health_check=null,rotation_due_at=null,"
        "activation_enabled=false returning true"
    )


def test_broker_health_projection_rejects_extra_scope_and_stale_health():
    import json

    import psycopg

    extra = broker_health_payload()
    extra["gmail"]["access_token"] = "must-not-project"
    with pytest.raises(psycopg.errors.RaiseException, match="invalid bounded broker health"):
        query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(extra),))

    broadened = broker_health_payload()
    broadened["gmail"]["oauth_scopes"] = ["https://www.googleapis.com/auth/gmail.readonly"]
    with pytest.raises(psycopg.errors.RaiseException, match="contract mismatch"):
        query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(broadened),))

    stale = broker_health_payload(checked_at=datetime.now(UTC) - timedelta(minutes=6))
    with pytest.raises(psycopg.errors.RaiseException, match="stale broker health"):
        query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(stale),))


@pytest.mark.parametrize(
    "status",
    [
        "missing_configuration",
        "expired",
        "revoked",
        "refresh_failed",
        "scope_mismatch",
        "account_mismatch",
    ],
)
def test_credential_health_fail_closed_and_no_false_human_gate(status):
    query(
        "update dufynd_observer_credentials set status=%s, health_reason=%s, activation_enabled=false where provider='gmail' returning true",
        (status, status),
    )
    health = query("select get_dufynd_credential_health('gmail')")
    assert health["status"] == status
    assert not health["waiting_human_input"]
    assert not query(
        "select capture_dufynd_broker_observation('gmail_known_threads','gmail:1a0f69c169fb928f','{}')"
    )["accepted"]


def test_credential_metadata_exact_contract_and_public_role_denied():
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute(
                "update dufynd_observer_credentials set secret_reference='token-canary' where provider='gmail'"
            )
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute(
                "update dufynd_observer_credentials set oauth_scopes='[\"gmail.readonly\"]' where provider='gmail'"
            )
        c.execute("set role anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select * from dufynd_observer_credentials")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select get_dufynd_credential_health('gmail')")


def test_broker_ingress_exact_source_dedupe_and_no_send():
    import json

    oid = "gmail:1a0f69c169fb928f"
    query("select register_dufynd_observer('gmail','1a0f69c169fb928f')")
    query(
        "update dufynd_observer_credentials set status='healthy',health_reason='healthy',expires_at=now()+interval '1 hour',last_health_check=now(),activation_enabled=true where provider='gmail' returning true"
    )
    evidence = {
        "thread_id": "1a0f69c169fb928f",
        "history_id": "10001",
        "messages": [
            {
                "message_id": "ab123456",
                "thread_id": "1a0f69c169fb928f",
                "internal_date": "1790950000000",
                "sender": "sender@example.com",
                "delivery_failure": False,
            }
        ],
    }
    sql = "select capture_dufynd_broker_observation('gmail_known_threads',%s,%s::jsonb)"
    first = query(sql, (oid, json.dumps(evidence)))
    assert first["inserted"] == 1
    assert query(sql, (oid, json.dumps(evidence)))["inserted"] == 0
    payload = query(
        "select payload->'evidence' from dufynd_jarvis_inbox where source_type='gmail' and payload->'evidence'->>'message_id'='ab123456'"
    )
    assert payload["sender"] == "sender@example.com"
    assert not {"body", "access_token", "refresh_token"} & set(payload)
    import psycopg

    for invalid in (evidence | {"access_token": "canary"}, evidence | {"thread_id": "foreign"}):
        with pytest.raises(psycopg.errors.RaiseException):
            query(sql, (oid, json.dumps(invalid)))
    query(
        "update dufynd_observer_credentials set activation_enabled=false,status='missing_configuration',health_reason='missing_configuration' where provider='gmail' returning true"
    )


@pytest.mark.parametrize("status", ["approval_required", "cancelled"])
def test_recovery_audit_recognizes_known_nonrunning_task_states(status):
    import json

    findings = query(
        "select dufynd_recovery_findings(%s::jsonb,null,now())",
        (
            json.dumps(
                {"status": status, "worker_state": "blocked", "released_at": "2026-10-02T12:00:00Z"}
            ),
        ),
    )
    assert findings == []


def paid_authorization_fixture():
    """Database-only simulation; never installs a real provider or sends a call."""
    import json

    f = fixture()
    decision = f"decision-{uuid4()}"
    approval = {
        "approved": True,
        "scope": "supervisor_v2_bounded_canary",
        "budget_id": f[0],
        "contract_id": f[1],
        "cap_usd": "0.10",
        "per_call_cap_usd": "0.10",
        "max_runs": 20,
    }
    query(
        "update dufynd_provider_contracts set dry_run=false where contract_id=%s returning contract_id",
        (f[1],),
    )
    query(
        "insert into dufynd_human_decisions values(%s,'approved',%s::jsonb) returning decision_id",
        (decision, json.dumps(approval)),
    )
    query(
        "update dufynd_jarvis_budget_windows set reservation_dry_run=false,approved_decision_id=%s where budget_id=%s returning budget_id",
        (decision, f[0]),
    )
    return f, decision


@pytest.mark.parametrize(
    "mutation",
    [
        "approval_revoked",
        "approval_scope_removed",
        "contract_model",
        "contract_dry_run",
        "contract_bound",
        "contract_evidence",
        "worker_state",
        "worker_owner",
        "run_limit",
    ],
)
def test_dispatch_revalidates_current_authorization(mutation):
    f, decision = paid_authorization_fixture()
    admitted = reserve(f)
    assert admitted["allowed"] is True
    if mutation == "approval_revoked":
        query(
            "update dufynd_human_decisions set status='pending' where decision_id=%s returning decision_id",
            (decision,),
        )
    elif mutation == "approval_scope_removed":
        query(
            "update dufynd_human_decisions set decision=decision-'scope' where decision_id=%s returning decision_id",
            (decision,),
        )
    elif mutation.startswith("contract_"):
        assignment = {
            "contract_model": "model='different'",
            "contract_dry_run": "dry_run=true",
            "contract_bound": "max_call_usd=0.11",
            "contract_evidence": 'evidence=\'{"tariff":"changed"}\'',
        }[mutation]
        query(
            f"update dufynd_provider_contracts set {assignment} where contract_id=%s returning contract_id",
            (f[1],),
        )
    elif mutation.startswith("worker_"):
        task, token = f[2][0]
        destination = "verifying" if mutation == "worker_state" else "queued"
        assert (
            query(
                "select update_dufynd_worker_v2(%s,%s,%s,'controlled lease transition',null)",
                (task, token, destination),
            )
            is True
        )
        if mutation == "worker_owner":
            assert (
                query("select claim_dufynd_worker_v2(%s,'other',%s)", (task, str(uuid4())))
                is not None
            )
    else:
        query(
            "update dufynd_jarvis_budget_windows set max_runs=0 where budget_id=%s returning budget_id",
            (f[0],),
        )
    assert (
        query(
            "select dispatch_dufynd_model_call(%s,%s)",
            (admitted["reservation"]["reservation_id"], f[2][0][1]),
        )
        is False
    )
    assert (
        query(
            "select status from dufynd_budget_reservations where reservation_id=%s",
            (admitted["reservation"]["reservation_id"],),
        )
        == "reserved"
    )


def test_dispatch_accepts_exact_run_and_cost_boundary():
    f, _ = paid_authorization_fixture()
    query(
        "update dufynd_jarvis_budget_windows set max_runs=1 where budget_id=%s returning budget_id",
        (f[0],),
    )
    admitted = reserve(f)
    assert admitted["allowed"] is True
    assert (
        query(
            "select dispatch_dufynd_model_call(%s,%s)",
            (admitted["reservation"]["reservation_id"], f[2][0][1]),
        )
        is True
    )


def test_reserve_rejects_incomplete_approval():
    f, decision = paid_authorization_fixture()
    query(
        "update dufynd_human_decisions set decision=decision-'scope' where decision_id=%s returning decision_id",
        (decision,),
    )
    assert reserve(f)["allowed"] is False


@pytest.fixture
def counted_window(counted_contract_clock):
    """Ephemeral test database approval only. Never runs on production, never uses HTTP."""
    import json

    from scripts import dufynd_anthropic_counted as c

    # This registry exists only in the disposable CI PostgreSQL database.
    # The migration's historical expiry must not hide budget/dispatch checks.
    query(
        "update dufynd_provider_contracts set expires_at=now()+interval '1 hour' "
        "where contract_id=%s returning contract_id",
        (c.CONTRACT_ID,),
    )
    f = fixture(cap="0.036864", maximum="0.036864")
    decision = f"decision-{uuid4()}"
    approval = {
        "approved": True,
        "scope": "supervisor_v2_bounded_canary",
        "budget_id": f[0],
        "contract_id": c.CONTRACT_ID,
        "provider": "anthropic",
        "model": c.MODEL,
        "cost_policy": c.POLICY,
        "accept_estimate_margin": True,
        "cap_usd": "0.036864",
        "max_runs": 1,
        "per_call_cap_usd": "0.036864",
    }
    query(
        "insert into dufynd_human_decisions values(%s,'approved',%s::jsonb) returning decision_id",
        (decision, json.dumps(approval)),
    )
    query(
        "update dufynd_jarvis_budget_windows set provider='anthropic',model=%s,max_runs=1,reservation_dry_run=false,approved_decision_id=%s where budget_id=%s returning budget_id",
        (c.MODEL, decision, f[0]),
    )
    prepared = c.prepare("database-only mock draft", 100)
    yield ((f[0], c.CONTRACT_ID, f[2]), decision, prepared)
    query(
        "update dufynd_jarvis_budget_windows set status='closed' where budget_id=%s returning budget_id",
        (f[0],),
    )


def counted_resolve():
    import hashlib

    from scripts import dufynd_anthropic_counted as c

    return query(
        "select resolve_dufynd_nightshift_budget(%s,%s)",
        (c.CONTRACT_ID, hashlib.sha256(c.canonical(c.pricing())).hexdigest()),
    )


def counted_dispatch(f, prepared):
    r = query(
        "select reserve_dufynd_model_call(%s,%s,'test',%s,%s,%s,%s,0.036864,180)",
        (f[0], f[2][0][0], f[2][0][1], str(uuid4()), prepared.fingerprint(), f[1]),
    )
    assert r["allowed"] is True
    rid = r["reservation"]["reservation_id"]
    assert (
        query(
            "select dispatch_dufynd_counted_call(%s,%s,%s::jsonb)",
            (rid, f[2][0][1], prepared.proof.decode()),
        )
        is True
    )
    return rid


def test_counted_new_window_last_reservation_and_settlement(counted_window):
    import json

    from scripts import dufynd_anthropic_counted as c

    f, _, prepared = counted_window
    assert counted_resolve()["budget"]["budget_id"] == f[0]
    rid = counted_dispatch(f, prepared)
    assert counted_resolve()["allowed"] is False
    cost, evidence, violation = c.actual_usage(
        prepared,
        {
            "id": "msg_" + str(uuid4()),
            "model": c.MODEL,
            "usage": {"input_tokens": 120, "output_tokens": 10},
        },
    )
    args = (rid, f[2][0][1], cost, json.dumps(evidence), violation)
    assert query("select settle_dufynd_counted_call(%s,%s,%s,%s::jsonb,%s)", args) is True
    assert query("select settle_dufynd_counted_call(%s,%s,%s,%s::jsonb,%s)", args) is True
    status = query("select get_dufynd_jarvis_budget_status(%s)", (f[0],))
    assert status["runs"] == 1 and Decimal(str(status["spent_usd"])) == cost


@pytest.mark.parametrize(
    "mutation", ["approval", "margin", "expiry", "start", "provider", "cap", "runs"]
)
def test_counted_resolver_fail_closed(counted_window, mutation):
    f, decision, _ = counted_window
    if mutation == "approval":
        query(
            "update dufynd_human_decisions set status='pending' where decision_id=%s returning decision_id",
            (decision,),
        )
    elif mutation == "margin":
        query(
            "update dufynd_human_decisions set decision=decision-'accept_estimate_margin' where decision_id=%s returning decision_id",
            (decision,),
        )
    else:
        setters = {
            "expiry": "ended_at=now()-interval '1 hour'",
            "start": "started_at=now()+interval '1 hour'",
            "provider": "provider='unknown'",
            "cap": "cap_usd=0.02",
            "runs": "max_runs=0",
        }
        query(
            f"update dufynd_jarvis_budget_windows set {setters[mutation]} where budget_id=%s returning budget_id",
            (f[0],),
        )
    assert counted_resolve()["allowed"] is False


def test_counted_worker_crash_dispatched_expiry_pauses_window(counted_window):
    f, _, p = counted_window
    rid = counted_dispatch(f, p)
    query(
        "update dufynd_budget_reservations set expires_at=now()-interval '1 second' where reservation_id=%s returning reservation_id",
        (rid,),
    )
    query("select reconcile_dufynd_budget_reservations()")
    assert (
        query("select status from dufynd_jarvis_budget_windows where budget_id=%s", (f[0],))
        == "paused"
    )
    assert (
        query("select status from dufynd_budget_reservations where reservation_id=%s", (rid,))
        == "charged_max"
    )


def test_counted_usage_margin_breach_recorded_even_with_false_caller_flag(counted_window):
    import json

    from scripts import dufynd_anthropic_counted as c

    f, _, p = counted_window
    rid = counted_dispatch(f, p)
    cost, evidence, _ = c.actual_usage(
        p,
        {
            "id": "msg_" + str(uuid4()),
            "model": c.MODEL,
            "usage": {"input_tokens": 30000, "output_tokens": 10},
        },
    )
    assert (
        query(
            "select settle_dufynd_counted_call(%s,%s,%s,%s::jsonb,false)",
            (rid, f[2][0][1], cost, json.dumps(evidence)),
        )
        is True
    )
    assert (
        Decimal(
            str(
                query(
                    "select actual_usd from dufynd_budget_reservations where reservation_id=%s",
                    (rid,),
                )
            )
        )
        == cost
    )
    assert (
        query("select status from dufynd_jarvis_budget_windows where budget_id=%s", (f[0],))
        == "paused"
    )


def test_counted_parallel_reservation_never_exceeds_window(counted_window):
    f, _, p = counted_window
    barrier = Barrier(2)

    def claim(worker):
        barrier.wait(timeout=10)
        return query(
            "select reserve_dufynd_model_call(%s,%s,'test',%s,%s,%s,%s,0.036864,180)",
            (f[0], f[2][worker][0], f[2][worker][1], str(uuid4()), p.fingerprint(), f[1]),
        )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, range(2)))
    assert sum(r["allowed"] for r in results) == 1


def test_counted_no_new_owner_budget_after_test_cleanup(counted_contract_clock):
    assert counted_resolve()["allowed"] is False


def test_counted_expired_provider_contract_remains_denied(counted_window):
    from scripts import dufynd_anthropic_counted as c

    query(
        "update dufynd_provider_contracts set expires_at=now()-interval '1 second' "
        "where contract_id=%s returning contract_id",
        (c.CONTRACT_ID,),
    )
    result = counted_resolve()
    assert result["allowed"] is False
    assert result["reason"] == "provider_contract_unverified_or_expired"


def test_counted_unresolved_sent_request_blocks_next_even_with_remaining_budget(counted_window):
    import json

    from scripts import dufynd_anthropic_counted as c

    f, decision, p = counted_window
    query(
        'update dufynd_human_decisions set decision=decision||\'{"cap_usd":"1","max_runs":3}\' where decision_id=%s returning decision_id',
        (decision,),
    )
    query(
        "update dufynd_jarvis_budget_windows set cap_usd=1,max_runs=3 where budget_id=%s returning budget_id",
        (f[0],),
    )
    rid = counted_dispatch(f, p)
    assert query("select get_dufynd_jarvis_budget_status(%s)", (f[0],))["remaining_runs"] == 2
    assert counted_resolve()["allowed"] is False
    cost, evidence, violation = c.actual_usage(
        p,
        {
            "id": "msg_" + str(uuid4()),
            "model": c.MODEL,
            "usage": {"input_tokens": 120, "output_tokens": 10},
        },
    )
    assert (
        query(
            "select settle_dufynd_counted_call(%s,%s,%s,%s::jsonb,%s)",
            (rid, f[2][0][1], cost, json.dumps(evidence), violation),
        )
        is True
    )
    assert counted_resolve()["allowed"] is True


def test_counted_preflight_snapshot_is_read_only_and_service_role_only():
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as connection:
        before = connection.execute(
            "select (select count(*) from dufynd_budget_reservations), "
            "(select count(*) from dufynd_jarvis_budget_windows)"
        ).fetchone()
        connection.execute("begin read only")
        state = connection.execute("select get_dufynd_counted_preflight_state()").fetchone()[0]
        connection.execute("rollback")
        after = connection.execute(
            "select (select count(*) from dufynd_budget_reservations), "
            "(select count(*) from dufynd_jarvis_budget_windows)"
        ).fetchone()
        assert before == after
        assert "settle_dufynd_counted_call" in state["functions"]
        assert isinstance(state["leases"]["active_workers"], list)
        assert isinstance(state["observer_health"], list)
        for role in ("anon", "authenticated"):
            assert (
                connection.execute(
                    "select has_function_privilege(%s,'get_dufynd_counted_preflight_state()','execute')",
                    (role,),
                ).fetchone()[0]
                is False
            )
        assert (
            connection.execute(
                "select has_function_privilege('service_role','get_dufynd_counted_preflight_state()','execute')"
            ).fetchone()[0]
            is True
        )


@pytest.mark.parametrize(
    "active,event", [(False, "workflow_dispatch"), (True, "workflow_dispatch"), (True, "schedule")]
)
def test_observer_receipt_lifecycle_preserves_recurring_activation(active, event):
    import json

    from tests.test_dufynd_private_observer_ingest import artifact, source

    query("update dufynd_observer_credentials set activation_enabled=%s returning true", (active,))
    query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(broker_health_payload()),))
    # Earlier audit fixtures intentionally disable observers globally. Recreate
    # only this test's fixed resource set rather than relying on shared DB state.
    for observer, kind, resource in [
        ("render:srv-dakpfrnf3r2c73dr3f20", "render", "srv-dakpfrnf3r2c73dr3f20"),
        *[
            (f"gmail:{thread}", "gmail", thread)
            for thread in ("1a0f385ed98c6af8", "1a0f69c169fb928f", "1a0f6a90772a743d")
        ],
    ]:
        query(
            "insert into dufynd_external_observers(observer_id,source_type,source_id,enabled) "
            "values(%s,%s,%s,true) on conflict(observer_id) do update set enabled=true returning true",
            (observer, kind, resource),
        )
    origin = source()
    origin["event_name"] = event
    origin["run_id"] = str(int(uuid4().hex[:12], 16))
    run = int(origin["run_id"])
    try:
        result = query("select begin_dufynd_broker_acceptance(%s::jsonb)", (json.dumps(origin),))
        assert result["accepted"]
        assert (
            query(
                "select recurring_read from dufynd_broker_acceptance_sessions where run_id=%s",
                (run,),
            )
            is active
        )
        data = artifact()
        render_path = "/v1/render/services/srv-dakpfrnf3r2c73dr3f20/deployments"
        entries = [("render_deploy_broker", "render:srv-dakpfrnf3r2c73dr3f20", data[render_path])]
        for path, value in data.items():
            if path.startswith("/v1/gmail/"):
                evidence = value["evidence"]
                for message in evidence["messages"]:
                    message.pop("content_type", None)
                entries.append(("gmail_known_threads", "gmail:" + evidence["thread_id"], evidence))
        for credential, observer, evidence in entries:
            capture_result = query(
                "select capture_dufynd_broker_acceptance_observation(%s,%s,%s,%s::jsonb)",
                (run, credential, observer, json.dumps(evidence)),
            )
            assert capture_result["accepted"], (observer, capture_result)
        summary = {"acknowledged": 3, "duplicate_first_pass": 0, "idempotent_rechecks": 3}
        result = query(
            "select finalize_dufynd_broker_acceptance(%s::jsonb,%s::jsonb)",
            (json.dumps(origin), json.dumps(summary)),
        )
        assert result["accepted"]
        assert result["activation_changed"] is (not active)
        duplicate = query(
            "select finalize_dufynd_broker_acceptance(%s::jsonb,%s::jsonb)",
            (json.dumps(origin), json.dumps(summary)),
        )
        assert duplicate["activation_changed"] is False
    finally:
        query(
            "delete from dufynd_broker_acceptance_sessions where run_id=%s returning true", (run,)
        )
        query("update dufynd_observer_credentials set activation_enabled=false returning true")


def test_observer_partial_activation_and_initial_schedule_fail_closed():
    import json

    import psycopg
    from tests.test_dufynd_private_observer_ingest import source

    origin = source()
    origin["run_id"] = str(int(uuid4().hex[:12], 16))
    query(
        "update dufynd_observer_credentials set activation_enabled=(provider='render') returning true"
    )
    try:
        with pytest.raises(psycopg.errors.RaiseException, match="partial activation"):
            query("select begin_dufynd_broker_acceptance(%s::jsonb)", (json.dumps(origin),))
        query("update dufynd_observer_credentials set activation_enabled=false returning true")
        origin["event_name"] = "schedule"
        with pytest.raises(psycopg.errors.RaiseException, match="owner manual"):
            query("select begin_dufynd_broker_acceptance(%s::jsonb)", (json.dumps(origin),))
    finally:
        query("update dufynd_observer_credentials set activation_enabled=false returning true")


def test_gmail_expiry_dedup_and_real_recovery():
    import psycopg

    with psycopg.connect(DSN) as connection:
        connection.execute(
            "update dufynd_external_observers set last_success_at=null where source_type='gmail'"
        )
        connection.execute(
            "update dufynd_observer_credentials set activation_enabled=true,status='healthy',health_reason='healthy',revoked_at=null,expires_at=now()-interval '1 hour' where provider='gmail'"
        )
        first = connection.execute("select reconcile_dufynd_gmail_health_v1()").fetchone()[0]
        second = connection.execute("select reconcile_dufynd_gmail_health_v1()").fetchone()[0]
        assert first["state"] == "credential_expired"
        assert second["dedup_key"] == first["dedup_key"]
        assert second["first_seen_at"] == first["first_seen_at"]
        assert second["owner_action_required"] is False
        assert second["email_sent"] is False
        assert (
            connection.execute(
                "select status from dufynd_observer_credentials where provider='gmail'"
            ).fetchone()[0]
            == "expired"
        )
        connection.execute(
            "update dufynd_observer_credentials set status='healthy',health_reason='healthy',expires_at=now()+interval '1 hour',refreshed_at=now()-interval '1 minute' where provider='gmail'"
        )
        assert (
            connection.execute("select reconcile_dufynd_gmail_health_v1()->>'state'").fetchone()[0]
            != "recovered"
        )
        connection.execute(
            "update dufynd_external_observers set enabled=true,health_status='healthy',last_success_at=now() where source_type='gmail'"
        )
        recovered = connection.execute("select reconcile_dufynd_gmail_health_v1()").fetchone()[0]
        assert recovered["state"] == "recovered"
        assert recovered["fresh_successes"] == 3
        connection.rollback()


@pytest.fixture
def mission_db():
    import psycopg

    with psycopg.connect(DSN) as c:
        # Disposable CI database only. Isolate from leases left by other tests.
        c.execute("select set_config('dufynd.worker_write','supervisor',true)")
        c.execute(
            "update dufynd_autonomy_tasks set released_at=now(),lease_expires_at=now() where released_at is null"
        )
        c.execute("select set_config('dufynd.worker_write','',true)")
        c.execute(
            "alter table dufynd_autonomy_tasks add column if not exists created_at timestamptz default now()"
        )
        c.execute("""create table if not exists dufynd_content_ideas(
          id text primary key,title text,format_id text,fragrance text,hook text,
          objective text,affiliate_role text,priority int,status text,source text,
          concept text,risk_notes jsonb default '[]');""")
        for pattern in ("*zero_budget_content_queue_v1.sql", "*content_production_packet_v1.sql"):
            c.execute(
                next((ROOT / "supabase/migrations").glob(pattern)).read_text().split("\ndo $$")[0]
            )
        c.execute(
            next(
                (ROOT / "supabase/migrations").glob("*photo_first_content_binding_fix.sql")
            ).read_text()
        )
        c.execute(
            next((ROOT / "supabase/migrations").glob("*jarvis_bounded_missions.sql")).read_text()
        )
        c.execute("""insert into dufynd_content_ideas(id,title,format_id,hook,objective,priority,status,concept)
          values('mission_test_idea','Fixture idea','static_text_hook','Fixture hook','engagement',99,'planned','Concrete fixture concept')""")
        yield c
        c.rollback()


def mission_start(c, mid="acceptance"):
    return c.execute(
        "select start_dufynd_mission_v1(%s,'zero_budget_content_preparation')", (mid,)
    ).fetchone()[0]


def mission_tick(c):
    return c.execute("select tick_dufynd_mission_v1()").fetchone()[0]


def mission_due(c):
    c.execute(
        "update dufynd_master_status set value=value||jsonb_build_object('next_retry_at',now()-interval '1 minute') where key like 'jarvis.mission.v1:%'"
    )


def test_mission_two_real_workers_and_immutable_results(mission_db):
    c = mission_db
    initial = mission_start(c)
    assert mission_start(c) == initial
    assert mission_start(c, "duplicate")["mission_id"] == "acceptance"
    first = mission_tick(c)
    assert first["state"] == "ready" and first["step"] == 2
    assert len(first["checkpoints"]) == 1
    artifact1 = c.execute(
        "select value from dufynd_master_status where key='jarvis.mission_result.v1:acceptance:1'"
    ).fetchone()[0]
    assert artifact1["artifact"]["next_content_move"]["idea_id"] == "mission_test_idea"
    done = mission_tick(c)
    assert done["state"] == "completed" and len(done["checkpoints"]) == 2
    assert {x["worker"] for x in done["checkpoints"]} == {
        "content_backlog_worker_v1",
        "content_packet_worker_v1",
    }
    artifact2 = c.execute(
        "select value from dufynd_master_status where key='jarvis.mission_result.v1:acceptance:2'"
    ).fetchone()[0]
    assert artifact2["artifact"]["concept"] == "Concrete fixture concept"
    assert artifact2["artifact"]["idea_id"] == "mission_test_idea"
    assert artifact2["artifact"]["publishing_allowed"] is False
    assert artifact2["quality_verified"] is True
    assert (
        c.execute(
            "select count(*) from dufynd_autonomy_tasks where task_id like 'mission:v1:acceptance:%' and status='done' and worker_state='done' and released_at is not null and lease_expires_at<=now()"
        ).fetchone()[0]
        == 2
    )
    assert mission_tick(c)["state"] == "idle"
    assert mission_start(c) == done
    assert (
        c.execute(
            "select value from dufynd_master_status where key='jarvis.mission_result.v1:acceptance:1'"
        ).fetchone()[0]
        == artifact1
    )


def test_mission_respects_live_lease_and_recovers_expired_lease(mission_db):
    c = mission_db
    token = str(uuid4())
    c.execute(
        """insert into dufynd_autonomy_tasks(task_id,domain,title,instruction,status,worker_state,worker_owner,
      lease_token,lease_expires_at,heartbeat_at,last_progress_at,budget_class,resource_scope)
      values('mission-conflict','content','fixture','fixture','in_progress','working','fixture',%s,
      now()+interval '1 hour',now(),now(),'free','["db:dufynd.content_ideas"]')""",
        (token,),
    )
    mission_start(c)
    assert mission_tick(c)["state"] == "waiting_lease"
    assert (
        c.execute(
            "select count(*) from dufynd_autonomy_tasks where task_id like 'mission:v1:%'"
        ).fetchone()[0]
        == 0
    )
    c.execute("select set_config('dufynd.worker_write','supervisor',true)")
    c.execute(
        "update dufynd_autonomy_tasks set lease_expires_at=now()-interval '1 minute' where task_id='mission-conflict'"
    )
    c.execute("select set_config('dufynd.worker_write','',true)")
    mission_due(c)
    assert mission_tick(c)["step"] == 2
    assert (
        c.execute(
            "select update_dufynd_worker_v2('mission-conflict',%s,'working','stale lease',null)",
            (token,),
        ).fetchone()[0]
        is False
    )


def inject_mission_failure(c):
    c.execute("""create or replace function read_dufynd_zero_budget_content_queue_v1() returns jsonb
      language plpgsql stable set search_path=public as $$ begin raise exception 'injected failure'; end $$""")


def test_mission_retry_backoff_rollback_dedup_and_resume(mission_db):
    c = mission_db
    mission_start(c)
    inject_mission_failure(c)
    failed = mission_tick(c)
    assert failed["state"] == "retry_wait" and failed["attempts"] == 1
    assert mission_tick(c)["attempts"] == 1
    assert (
        c.execute(
            "select count(*) from dufynd_autonomy_tasks where task_id like 'mission:v1:%'"
        ).fetchone()[0]
        == 0
    )
    mission_due(c)
    assert mission_tick(c)["attempts"] == 2
    assert (
        c.execute(
            "select count(*) from dufynd_master_status where key='jarvis.mission_alert.v1:acceptance'"
        ).fetchone()[0]
        == 1
    )
    c.execute(
        next(
            (ROOT / "supabase/migrations").glob("*photo_first_content_binding_fix.sql")
        ).read_text()
    )
    mission_due(c)
    assert mission_tick(c)["step"] == 2
    assert mission_tick(c)["state"] == "completed"
    assert (
        c.execute(
            "select value->>'state' from dufynd_master_status where key='jarvis.mission_alert.v1:acceptance'"
        ).fetchone()[0]
        == "resolved"
    )


def test_mission_bounded_terminal_failure_and_gate(mission_db):
    c = mission_db
    mission_start(c)
    inject_mission_failure(c)
    for _ in range(3):
        mission_due(c)
        state = mission_tick(c)
    assert state["state"] == "blocked" and state["attempts"] == 3
    assert state["checkpoints"] == []
    assert mission_tick(c)["state"] == "idle"
    assert mission_start(c)["state"] == "blocked"


def test_mission_idea_drift_retains_checkpoint(mission_db):
    c = mission_db
    mission_start(c)
    first = mission_tick(c)
    c.execute("update dufynd_content_ideas set status='draft' where id='mission_test_idea'")
    state = mission_tick(c)
    assert state["state"] == "retry_wait"
    assert state["checkpoints"] == first["checkpoints"]
    assert state["step"] == 2
    assert (
        c.execute(
            "select count(*) from dufynd_master_status where key='jarvis.mission_result.v1:acceptance:2'"
        ).fetchone()[0]
        == 0
    )


def test_mission_disabled_handler_and_public_access_fail_closed(mission_db):
    import psycopg

    c = mission_db
    mission_start(c)
    c.execute(
        "update dufynd_handler_contracts set enabled=false where handler_id='content_backlog_prioritize'"
    )
    assert mission_tick(c)["state"] == "blocked"
    assert (
        c.execute(
            "select count(*) from dufynd_autonomy_tasks where task_id like 'mission:v1:%'"
        ).fetchone()[0]
        == 0
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
        c.execute("set local role anon")
        c.execute("select tick_dufynd_mission_v1()")
    with pytest.raises(psycopg.errors.RaiseException), c.transaction():
        c.execute("select start_dufynd_mission_v1('unsafe','social_publish')")
