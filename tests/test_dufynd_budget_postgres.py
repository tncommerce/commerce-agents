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
