"""Isolated PostgreSQL, never Supabase. Each test owns a disposable local database.

The existing CI PostgreSQL 17 service supplies real independent backends. No
sqlite, mocked locks or PGlite multiplexing is accepted for contention/crash tests.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated local PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase/migrations"
NATIVE = next(MIGRATIONS.glob("*dufynd_native_nightshift_v1.sql"))


def bootstrap(c):
    """Reuse the actual supervisor/packet migrations, not a reimplemented lease."""
    c.execute("""do $$ begin
      if not exists(select from pg_roles where rolname='anon') then create role anon; end if;
      if not exists(select from pg_roles where rolname='authenticated') then create role authenticated; end if;
      if not exists(select from pg_roles where rolname='service_role') then create role service_role bypassrls; end if;
    end $$;""")
    c.execute(
        (ROOT / "tests/dufynd_budget_schema_fixture.sql")
        .read_text()
        .replace(
            "create role anon; create role authenticated; create role service_role bypassrls;", ""
        )
    )
    c.execute(
        next(MIGRATIONS.glob("*supervisor_v2_phase1.sql"))
        .read_text()
        .split("-- No model and no paid runner:")[0]
    )
    # Same dependency chain as the existing budget-postgres suite.
    for name in (
        "cost_reservations",
        "durable_executions",
        "external_events",
        "capability_packets",
        "state_audit_handler",
        "receipt_projection",
        "purchase_freshness_handler",
        "purchase_acceptance_receipt",
        "ci_pr_verifier",
        "supervisor_recovery_audit",
        "observer_credential_plane",
        "private_observer_health_projection",
        "audit_known_terminal_states",
        "paid_dispatch_revalidation",
        "nightshift_budget_resolver",
        "counted_preflight_snapshot",
        "private_observer_acceptance_gate",
        "private_observer_recurring_capture",
        "dependency_observer_reliability",
        "gmail_observer_recovery",
        "gmail_owner_gate_persistence",
    ):
        sql = next(MIGRATIONS.glob(f"*{name}.sql")).read_text()
        if name == "durable_executions":
            sql = sql.split("-- Hosted observer extension;")[0]
        c.execute(sql)
    c.execute(
        "alter table dufynd_autonomy_tasks add column if not exists created_at timestamptz default now()"
    )
    # Load real mission routing before the cron-fixture table exists: no cron DDL.
    c.execute(next(MIGRATIONS.glob("*jarvis_bounded_missions.sql")).read_text())
    c.execute((ROOT / "tests/dufynd_native_nightshift_fixture.sql").read_text())
    before = c.execute("select jsonb_agg(to_jsonb(j) order by jobid) from cron.job j").fetchone()[0]
    c.execute(NATIVE.read_text())
    assert (
        before
        == c.execute("select jsonb_agg(to_jsonb(j) order by jobid) from cron.job j").fetchone()[0]
    )


class Database:
    def __init__(self, dsn):
        self.dsn = dsn

    def connect(self):
        import psycopg

        return psycopg.connect(
            self.dsn, autocommit=True, options="-c statement_timeout=5000 -c lock_timeout=1500"
        )

    def q(self, sql, args=None):
        with self.connect() as c:
            cur = c.execute(sql, args)
            return cur.fetchone()[0] if cur.description else None

    def approve(self, mid="pilot", start=None, end=None):
        start = start or datetime.now(UTC) - timedelta(seconds=1)
        end = end or start + timedelta(minutes=45)
        self.q(
            "update dufynd_handler_contracts set enabled=true where handler_id like 'nightshift_%'"
        )
        self.q(
            "update dufynd_master_status set value='{\"enabled\":true,\"stop\":false}' where key='jarvis.native_nightshift_v1.config'"
        )
        self.q(
            """insert into dufynd_human_decisions(decision_id,status,decision)
          select %s,'approved',jsonb_build_object('scope','dufynd_native_nightshift_v1',
          'starts_at',%s::timestamptz,'ends_at',%s::timestamptz,
          'manifest_sha256',dufynd_ns_v1_hash(dufynd_ns_v1_manifest(%s,%s)))""",
            (mid, start, end, start, end),
        )
        return self.q("select dufynd_ns_v1_start(%s,%s)", (mid, mid))

    def claim(self):
        return self.q("select dufynd_ns_v1_claim()")

    def finish(self, claim):
        return self.q(
            "select dufynd_ns_v1_finish(%s,%s,%s)",
            (claim["mission_key"], claim["task_id"], claim["token"]),
        )

    def expire(self, claim):
        with self.connect() as c, c.transaction():
            c.execute("select set_config('dufynd.worker_write','supervisor',true)")
            c.execute(
                "update dufynd_autonomy_tasks set lease_expires_at=now()-interval '1 second' where task_id=%s",
                (claim["task_id"],),
            )


@pytest.fixture
def db():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.sql import SQL, Identifier

    params = conninfo_to_dict(DSN)
    assert params.get("host") in {"localhost", "127.0.0.1", "::1"}, "No non-local database testing"
    assert "test" in params.get("dbname", ""), "Explicit test database required"
    name = "dufynd_ns_test_" + uuid4().hex
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(SQL("create database {}").format(Identifier(name)))
    instance = Database(make_conninfo(DSN, dbname=name))
    try:
        with instance.connect() as c:
            bootstrap(c)
        yield instance
    finally:
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute(SQL("drop database {} with (force)").format(Identifier(name)))


def test_disabled_no_scheduler_and_privileges(db):
    import psycopg

    assert db.claim() == {"state": "idle"}
    assert db.q("select count(*) from cron.job") == 11
    assert (
        db.q(
            "select count(*) from dufynd_handler_contracts where handler_id like 'nightshift_%' and enabled"
        )
        == 0
    )
    for role in ("anon", "authenticated", "service_role"):
        with db.connect() as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("set role " + role)
            c.execute("select dufynd_ns_v1_claim()")
    with pytest.raises(psycopg.errors.RaiseException, match="exact_owner_approval"):
        db.q("select dufynd_ns_v1_start('unapproved','missing')")


def test_holds_skipped_real_results_atomic_and_restart(db):
    m = db.approve()
    assert m["definition"]["holds"][0]["state"] == "OWNER_HOLD"
    first = db.claim()
    assert first["attempt"] == 1
    # All q() calls open a new connection: no hidden process/session state.
    result = db.finish(first)
    assert result["state"] == "done"
    assert result["artifact"]["revenue"] == "UNKNOWN"
    assert result["artifact"]["findings"] == []
    assert db.finish(first)["state"] == "stale_fence"
    assert db.finish(db.claim())["state"] == "done"
    assert db.claim()["state"] == "terminal"
    assert (
        db.q(
            "select sum(nightshift_attempts) from dufynd_autonomy_tasks where task_id like 'nightshift:v1:%'"
        )
        == 2
    )
    assert (
        db.q(
            "select count(*) from dufynd_autonomy_tasks where task_id like 'nightshift:v1:%' and status='done' and released_at is not null"
        )
        == 2
    )


def test_concurrent_backends_only_one_claim_and_finish(db):
    db.approve()
    barrier = Barrier(8)

    def claim(_):
        barrier.wait(timeout=10)
        return db.claim()

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(claim, range(8)))
    claims = [r for r in results if r["state"] == "claimed"]
    assert len(claims) == 1  # Shared resource lease, not just task ID uniqueness.
    with ThreadPoolExecutor(2) as pool:
        finished = list(pool.map(lambda _: db.finish(claims[0]), range(2)))
    assert sorted(r["state"] for r in finished) == ["done", "stale_fence"]


def test_expired_lease_fences_old_worker_and_caps_crash_attempts(db):
    db.approve()
    old = db.claim()
    for attempt in (2, 3):
        db.expire(old)
        new = db.claim()
        assert new["attempt"] == attempt and new["task_id"] == old["task_id"]
        assert db.finish(old)["state"] == "stale_fence"
        old = new
    db.expire(old)
    independent = db.claim()
    assert independent["task_id"] != old["task_id"]
    assert db.finish(independent)["state"] == "done"
    assert db.claim()["state"] == "terminal"
    assert (
        db.q(
            "select nightshift_attempts from dufynd_autonomy_tasks where task_id=%s",
            (old["task_id"],),
        )
        == 3
    )


def test_identical_inputs_across_nights_reuse_verified_result(db):
    db.approve()
    for _ in range(2):
        assert db.finish(db.claim())["state"] == "done"
    assert db.claim()["state"] == "terminal"
    db.q(
        "update dufynd_master_status set last_verified_at=now(),value=value||jsonb_build_object('observed_at',now()) where key='jarvis.first_money_measurement_v1'"
    )
    db.approve("second_night")
    assert db.claim()["state"] == "terminal"
    assert (
        db.q(
            "select sum(nightshift_attempts) from dufynd_autonomy_tasks where task_id like 'nightshift:v1:%'"
        )
        == 2
    )


def test_owner_hold_task_does_not_block_independent_task(db):
    m = db.approve()
    tid = m["definition"]["items"][0]["task_id"]
    db.q(
        "update dufynd_autonomy_tasks set requires_human_approval=true,status='waiting_human_input',blocked_reason='owner_decision' where task_id=%s",
        (tid,),
    )
    independent = db.claim()
    assert independent["task_id"] != tid
    assert db.finish(independent)["state"] == "done"
    assert db.claim()["state"] == "terminal"
    assert (
        db.q("select nightshift_attempts from dufynd_autonomy_tasks where task_id=%s", (tid,)) == 0
    )


@pytest.mark.parametrize(
    "condition,expected",
    [
        ("stop", "stop_requested"),
        ("disabled", "disabled"),
        ("revoked", "owner_approval_revoked"),
        ("timeout", "statement_timeout_unbounded"),
    ],
)
def test_stop_and_revocation_recheck_between_claim_and_finish(db, condition, expected):
    db.approve()
    claim = db.claim()
    if condition == "stop":
        db.q(
            "update dufynd_master_status set value=value||'{\"stop\":true}' where key='jarvis.native_nightshift_v1.config'"
        )
    elif condition == "disabled":
        db.q(
            "update dufynd_master_status set value=value||'{\"enabled\":false}' where key='jarvis.native_nightshift_v1.config'"
        )
    elif condition == "revoked":
        db.q("update dufynd_human_decisions set status='rejected' where decision_id='pilot'")
    if condition == "timeout":
        with db.connect() as c:
            c.execute("set statement_timeout=0")
            result = c.execute(
                "select dufynd_ns_v1_finish(%s,%s,%s)",
                (claim["mission_key"], claim["task_id"], claim["token"]),
            ).fetchone()[0]
    else:
        result = db.finish(claim)
    assert result["state"] == expected
    assert (
        db.q(
            "select count(*) from dufynd_master_status where key like 'jarvis.mission_result.v1:native:%'"
        )
        == 0
    )
    if condition == "stop":
        db.q(
            "update dufynd_master_status set value=value||'{\"stop\":false}' where key='jarvis.native_nightshift_v1.config'"
        )
        retry = db.claim()
        assert retry["attempt"] == 2
        assert db.finish(retry)["state"] == "done"


def test_scheduled_top_level_call_preserves_legacy_missions_and_cron_rows(db):
    start = datetime.now(UTC) + timedelta(seconds=2)
    db.approve(start=start)
    before = db.q("select jsonb_agg(to_jsonb(j) order by jobid) from cron.job j")
    db.q("call dufynd_ns_v1_cycle()")
    assert (
        db.q(
            "select sum(nightshift_attempts) from dufynd_autonomy_tasks where task_id like 'nightshift:v1:%'"
        )
        == 0
    )
    time.sleep(max(0, (start - datetime.now(UTC)).total_seconds()) + 0.05)
    db.q("call dufynd_ns_v1_cycle()")
    assert (
        db.q(
            "select count(*) from dufynd_autonomy_tasks where task_id like 'nightshift:v1:%' and status='done'"
        )
        == 1
    )
    assert (
        db.q("select value->>'calls' from dufynd_master_status where key='test.legacy_ceo'") == "2"
    )
    assert db.q("select jsonb_agg(to_jsonb(j) order by jobid) from cron.job j") == before


def test_no_partial_receipt_on_failure_and_attempt_limit(db):
    db.approve()
    db.q("""create function test_fail_receipt() returns trigger language plpgsql as $$ begin
      if new.key like 'jarvis.mission_result.v1:native:%' then raise exception 'synthetic_failure'; end if;
      return new; end $$;
      create trigger test_fail_receipt before insert on dufynd_master_status for each row execute function test_fail_receipt();""")
    for _ in range(3):
        assert db.finish(db.claim())["state"] == "failed"
    assert (
        db.q(
            "select count(*) from dufynd_master_status where key like 'jarvis.mission_result.v1:native:%'"
        )
        == 0
    )
    assert (
        db.q(
            "select count(*) from dufynd_autonomy_tasks where nightshift_attempts=3 and status='blocked'"
        )
        == 1
    )


def test_backend_death_after_committed_claim_resumes_without_lost_attempt(db):
    import psycopg

    db.approve()
    # Block result insertion without changing the pinned evaluator or runtime.
    db.q("""create function test_block_receipt() returns trigger language plpgsql as $$ begin
      if new.key like 'jarvis.mission_result.v1:native:%' then perform pg_advisory_xact_lock(88223311); end if;
      return new; end $$;
      create trigger test_block_receipt before insert on dufynd_master_status for each row execute function test_block_receipt();""")
    with db.connect() as blocker, db.connect() as victim, ThreadPoolExecutor(1) as pool:
        blocker.execute("select pg_advisory_lock(88223311)")
        pid = victim.execute("select pg_backend_pid()").fetchone()[0]
        future = pool.submit(victim.execute, "call dufynd_ns_v1_cycle()")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if db.q(
                "select count(*) from pg_stat_activity where pid=%s and wait_event='advisory'",
                (pid,),
            ):
                break
            time.sleep(0.02)
        else:
            pytest.fail("backend never reached the post-commit execution phase")
        # This task+attempt is visible to another backend BEFORE execution ends.
        tid = db.q("select task_id from dufynd_autonomy_tasks where nightshift_attempts=1")
        assert tid
        assert db.q("select pg_terminate_backend(%s)", (pid,)) is True
        with pytest.raises(psycopg.OperationalError):
            future.result(timeout=5)
        blocker.execute("select pg_advisory_unlock(88223311)")
    db.q("drop trigger test_block_receipt on dufynd_master_status")
    assert (
        db.q(
            "select count(*) from dufynd_master_status where key like 'jarvis.mission_result.v1:native:%'"
        )
        == 0
    )
    db.expire({"task_id": tid})
    retry = db.claim()
    assert retry["task_id"] == tid and retry["attempt"] == 2
    assert db.finish(retry)["state"] == "done"


@pytest.mark.parametrize(
    "mutation", ["packet", "manifest", "attempt_reset", "task_delete", "result_delete"]
)
def test_immutable_input_checkpoint_and_result(db, mutation):
    import psycopg

    m = db.approve()
    tid = m["definition"]["items"][0]["task_id"]
    assert db.finish(db.claim())["state"] == "done"
    statements = {
        "packet": "update dufynd_autonomy_tasks set durable_payload='{}' where task_id=%s",
        "manifest": "update dufynd_master_status set value=jsonb_set(value,'{definition,max_total_attempts}','99') where key='jarvis.mission.v1:native_pilot' and %s is not null",
        "attempt_reset": "update dufynd_autonomy_tasks set nightshift_attempts=0 where task_id=%s",
        "task_delete": "delete from dufynd_autonomy_tasks where task_id=%s",
        "result_delete": "delete from dufynd_master_status where key='jarvis.mission_result.v1:native:'||%s",
    }
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        db.q(statements[mutation], (tid,))


@pytest.mark.parametrize(
    "corruption,expected",
    [
        ("task", "task_missing"),
        ("receipt", "result_missing_or_corrupt"),
        ("manifest", "checkpoint_corrupt"),
    ],
)
def test_privileged_corruption_or_missing_state_fails_closed(db, corruption, expected):
    db.approve()
    done = db.claim()
    db.finish(done)
    # Deliberate superuser corruption is confined to this disposable database.
    if corruption == "task":
        db.q("alter table dufynd_autonomy_tasks disable trigger dufynd_ns_task_guard")
        db.q("delete from dufynd_autonomy_tasks where task_id=%s", (done["task_id"],))
    else:
        db.q("alter table dufynd_master_status disable trigger dufynd_ns_status_guard")
        if corruption == "receipt":
            db.q(
                "delete from dufynd_master_status where key='jarvis.mission_result.v1:native:'||%s",
                (done["task_id"],),
            )
        else:
            db.q(
                "update dufynd_master_status set value=jsonb_set(value,'{definition,paid_calls}','1') where key='jarvis.mission.v1:native_pilot'"
            )
    assert db.claim()["state"] == expected


@pytest.mark.parametrize("condition", ["cost", "unknown_cost", "handler_disabled", "handler_drift"])
def test_cost_and_contract_gates(db, condition):
    db.approve()
    if condition == "cost":
        db.q(
            "update dufynd_autonomy_tasks set budget_class='model' where task_id like 'nightshift:v1:%'"
        )
    elif condition == "unknown_cost":
        db.q(
            "update dufynd_autonomy_tasks set provider_cost_unknown=true where task_id like 'nightshift:v1:%'"
        )
    elif condition == "handler_disabled":
        db.q(
            "update dufynd_handler_contracts set enabled=false where handler_id like 'nightshift_%'"
        )
    else:
        db.q(
            "update dufynd_handler_contracts set contract=contract||'{\"cost_class\":\"model\"}' where handler_id like 'nightshift_%'"
        )
    assert db.claim()["state"] == "task_contract_invalid"
    assert (
        db.q(
            "select sum(nightshift_attempts) from dufynd_autonomy_tasks where task_id like 'nightshift:v1:%'"
        )
        == 0
    )


def test_unrelated_delete_still_works(db):
    db.q("insert into dufynd_master_status(key,value) values('test.delete','{}')")
    db.q("delete from dufynd_master_status where key='test.delete'")
    assert db.q("select count(*) from dufynd_master_status where key='test.delete'") == 0


def test_expired_window_stops_without_spending_an_attempt(db):
    start = datetime.now(UTC) - timedelta(seconds=1)
    end = datetime.now(UTC) + timedelta(seconds=1)
    db.approve(start=start, end=end)
    time.sleep(max(0, (end - datetime.now(UTC)).total_seconds()) + 0.05)
    assert db.claim()["state"] == "window_closed"
    assert (
        db.q(
            "select sum(nightshift_attempts) from dufynd_autonomy_tasks where task_id like 'nightshift:v1:%'"
        )
        == 0
    )


def test_real_statement_timeout_keeps_committed_attempt(db):
    import psycopg

    db.approve()
    db.q("""create function test_slow_receipt() returns trigger language plpgsql as $$ begin
      if new.key like 'jarvis.mission_result.v1:native:%' then perform pg_sleep(2); end if;
      return new; end $$;
      create trigger test_slow_receipt before insert on dufynd_master_status for each row execute function test_slow_receipt();""")
    with db.connect() as c:
        c.execute("set statement_timeout='500ms'")
        with pytest.raises(psycopg.errors.QueryCanceled):
            c.execute("call dufynd_ns_v1_cycle()")
    assert (
        db.q(
            "select sum(nightshift_attempts) from dufynd_autonomy_tasks where task_id like 'nightshift:v1:%'"
        )
        == 1
    )
    assert (
        db.q(
            "select count(*) from dufynd_master_status where key like 'jarvis.mission_result.v1:native:%'"
        )
        == 0
    )


def test_runtime_code_drift_invalidates_approval(db):
    db.approve()
    db.q("""create or replace function public.dufynd_ns_v1_evaluate(packet jsonb) returns jsonb
      language plpgsql immutable security invoker set search_path=public as $$
      begin raise exception 'unapproved changed runtime'; end $$""")
    assert db.claim()["state"] == "checkpoint_corrupt"
