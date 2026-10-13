"""Real pg_cron 1.6.4 clock on an isolated localhost CI container, never Supabase.

No manual cycle CALL substitutes for a scheduled tick in these tests. Seconds
cadence accelerates the clock; the approved manifest still spans exactly 45 min.
Ten peer registrations and the CEO business action are harmless sentinels. The
scheduler, alter_job C function, connections and commits are real PostgreSQL.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from tests.test_dufynd_native_nightshift_postgres import Database, bootstrap

DSN = os.getenv("DUFYND_CRON_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated real pg_cron container required")
OLD = "select public.run_dufynd_ceo_with_missions_v1();"
PILOT = "CALL public.dufynd_ns_v1_cycle();"
PKEY = "jarvis.native_nightshift_v1.pilot:pilot"


def wait_for(check, seconds=20):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        result = check()
        if result:
            return result
        time.sleep(0.05)
    pytest.fail("real pg_cron condition not reached before bounded deadline")


def snapshot(db):
    return db.q("select jsonb_agg(to_jsonb(j) order by jobid) from cron.job j")


def state(db):
    return db.q("select value from dufynd_master_status where key=%s", (PKEY,))


def arm(db, remaining=10):
    end = datetime.now(UTC) + timedelta(seconds=remaining)
    db.approve(start=end - timedelta(minutes=45), end=end)
    baseline = snapshot(db)
    assert db.q("select dufynd_ns_v1_pilot_arm('pilot')")["state"] == "armed"
    return baseline


@pytest.fixture
def clock():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    params = conninfo_to_dict(DSN)
    assert params.get("host") in {"localhost", "127.0.0.1"}
    assert params.get("dbname") == "dufynd_cron_test"
    assert params.get("port") == "5433"
    db = Database(DSN)
    with db.connect() as c:
        assert c.execute("show cron.database_name").fetchone()[0] == "dufynd_cron_test"
        c.execute("drop schema public cascade; create schema public")
        bootstrap(c)
        jobs = snapshot(db)
        c.execute("drop schema cron cascade; create extension pg_cron")
        assert (
            c.execute("select extversion from pg_extension where extname='pg_cron'").fetchone()[0]
            == "1.6"
        )
        assert (
            c.execute(
                "select lanname from pg_proc p join pg_language l on l.oid=p.prolang where p.oid='cron.alter_job(bigint,text,text,text,text,boolean)'::regprocedure"
            ).fetchone()[0]
            == "c"
        )
        for j in jobs:
            # Peers are inert but real registered jobs; never execute a business handler.
            cadence = "1 second" if j["jobid"] == 11 else "0 0 1 1 *"
            command = OLD if j["jobid"] == 11 else "select 1;"
            assert (
                c.execute(
                    "select cron.schedule(%s,%s,%s)", (j["jobname"], cadence, command)
                ).fetchone()[0]
                == j["jobid"]
            )
        print(
            "REAL_CLOCK PostgreSQL",
            c.execute("show server_version").fetchone()[0],
            "pg_cron source v1.6.4, SQL extension 1.6; libpq mode",
        )
    try:
        yield db
    finally:
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("select cron.unschedule(jobid) from cron.job")
            c.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity where datname=current_database() and application_name='pg_cron' and backend_type='client backend' and pid<>pg_backend_pid()"
            )
            c.execute("drop extension pg_cron cascade")


def test_real_clock_expiry_exact_restore_and_unchanged_ceo_resume(clock):
    baseline = arm(clock)
    wait_for(lambda: state(clock)["state"] == "restored")
    p = state(clock)
    assert p["stop_reason"] == "window_closed"
    assert p["all_eleven_exact"] is True
    assert snapshot(clock) == baseline
    assert (
        clock.q(
            "select count(*) from dufynd_autonomy_tasks where status='done' and nightshift_attempts=1"
        )
        == 2
    )
    assert (
        clock.q(
            "select count(*) from cron.job_run_details where jobid=11 and command=%s and status='succeeded'",
            (PILOT,),
        )
        >= 2
    )
    wait_for(
        lambda: clock.q(
            "select count(*) from cron.job_run_details where jobid=11 and command=%s and status='succeeded' and start_time>%s::timestamptz",
            (OLD, p["restored_at"]),
        )
    )
    assert clock.q("select sum(nightshift_attempts) from dufynd_autonomy_tasks") == 2
    assert (
        clock.q(
            "select count(*) from dufynd_handler_contracts where handler_id like 'nightshift_%' and enabled"
        )
        == 0
    )
    # Repeated arm returns the closed receipt; it cannot renew dates or command.
    assert clock.q("select dufynd_ns_v1_pilot_arm('pilot')") == p
    assert snapshot(clock) == baseline


def test_abort_is_idempotent_concurrent_and_preserves_checkpoint(clock):
    baseline = arm(clock, 30)
    wait_for(lambda: clock.q("select count(*) from dufynd_autonomy_tasks where status='done'") == 2)
    attempts = clock.q("select sum(nightshift_attempts) from dufynd_autonomy_tasks")
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: clock.q("call dufynd_ns_v1_pilot_abort()"), range(4)))
    receipt = state(clock)
    assert receipt["state"] == "restored"
    assert receipt["restore_attempts"] == 1
    clock.q("call dufynd_ns_v1_pilot_abort()")
    assert state(clock) == receipt
    assert snapshot(clock) == baseline
    assert clock.q("select sum(nightshift_attempts) from dufynd_autonomy_tasks") == attempts == 2


def test_real_clock_transient_restore_failure_stops_then_recovers(clock):
    baseline = arm(clock, 30)
    clock.q("""create function test_restore_error() returns trigger language plpgsql as $$ begin
      if new.command='select public.run_dufynd_ceo_with_missions_v1();' then raise exception 'test_restore_error'; end if;
      return new; end $$;
      create trigger test_restore_error before update on cron.job for each row execute function test_restore_error();""")
    clock.q(
        "update dufynd_master_status set value=value||'{\"stop\":true}' where key='jarvis.native_nightshift_v1.config'"
    )
    wait_for(lambda: state(clock)["state"] == "restore_failed")
    assert (
        clock.q(
            "select value->'enabled' from dufynd_master_status where key='jarvis.native_nightshift_v1.config'"
        )
        is False
    )
    attempts = clock.q("select coalesce(sum(nightshift_attempts),0) from dufynd_autonomy_tasks")
    clock.q("drop trigger test_restore_error on cron.job")
    wait_for(lambda: state(clock)["state"] == "restored")
    assert state(clock)["restore_attempts"] >= 2
    assert snapshot(clock) == baseline
    assert (
        clock.q("select coalesce(sum(nightshift_attempts),0) from dufynd_autonomy_tasks")
        == attempts
    )


def test_real_cron_backend_death_during_restore_keeps_stop_and_retries(clock):
    baseline = arm(clock, 30)
    clock.q("""create function test_restore_block() returns trigger language plpgsql as $$ begin
      if new.command='select public.run_dufynd_ceo_with_missions_v1();' then perform pg_advisory_xact_lock(88112299); end if;
      return new; end $$;
      create trigger test_restore_block before update on cron.job for each row execute function test_restore_block();""")
    with clock.connect() as blocker:
        blocker.execute("select pg_advisory_lock(88112299)")
        clock.q(
            "update dufynd_master_status set value=value||'{\"stop\":true}' where key='jarvis.native_nightshift_v1.config'"
        )
        pid = wait_for(
            lambda: clock.q(
                "select max(pid) from pg_stat_activity where datname=current_database() and application_name='pg_cron' and wait_event='advisory'"
            )
        )
        assert state(clock)["state"] == "restoring"
        assert (
            clock.q(
                "select value->'stop' from dufynd_master_status where key='jarvis.native_nightshift_v1.config'"
            )
            is True
        )
        assert clock.q("select pg_terminate_backend(%s)", (pid,)) is True
        blocker.execute("select pg_advisory_unlock(88112299)")
    wait_for(lambda: state(clock)["state"] == "restored")
    assert snapshot(clock) == baseline
    assert (
        clock.q("select count(*) from cron.job_run_details where jobid=11 and status='failed'") >= 1
    )


def test_restore_commits_before_legacy_ceo_failure(clock):
    baseline = arm(clock, 3)
    clock.q("""create or replace function public.run_dufynd_ceo_safe_cycle_v1() returns jsonb language plpgsql as $$
      begin raise exception 'legacy_failure_fixture'; end $$;""")
    wait_for(lambda: state(clock)["state"] == "restored")
    assert snapshot(clock) == baseline
    assert state(clock)["all_eleven_exact"] is True


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_real_clock_lost_or_corrupt_pilot_fails_closed_and_restores(clock, damage):
    baseline = arm(clock, 30)
    with clock.connect() as c, c.transaction():
        c.execute("alter table dufynd_master_status disable trigger dufynd_ns_status_guard")
        if damage == "missing":
            c.execute("delete from dufynd_master_status where key=%s", (PKEY,))
        else:
            c.execute(
                "update dufynd_master_status set value=jsonb_set(value,'{definition}', '\"corrupt\"') where key=%s",
                (PKEY,),
            )
        c.execute("alter table dufynd_master_status enable trigger dufynd_ns_status_guard")
    wait_for(lambda: clock.q("select command from cron.job where jobid=11") == OLD)
    assert snapshot(clock) == baseline
    assert (
        clock.q(
            "select value->'stop' from dufynd_master_status where key='jarvis.native_nightshift_v1.config'"
        )
        is True
    )


def test_peer_drift_preserved_instead_of_overwritten(clock):
    baseline = arm(clock, 30)
    clock.q("select cron.alter_job(1,command:='select 2;')")
    wait_for(lambda: state(clock)["state"] == "restored")
    assert state(clock)["all_eleven_exact"] is False
    baseline[0]["command"] = "select 2;"
    assert snapshot(clock) == baseline


def test_permanent_restore_error_is_bounded_owner_hold(clock):
    arm(clock, 30)
    clock.q("""create function test_restore_error() returns trigger language plpgsql as $$ begin
      if new.command='select public.run_dufynd_ceo_with_missions_v1();' then raise exception 'test_restore_error'; end if;
      return new; end $$;
      create trigger test_restore_error before update on cron.job for each row execute function test_restore_error();""")
    clock.q("call dufynd_ns_v1_pilot_abort()")
    wait_for(lambda: state(clock)["restore_attempts"] == 3)
    receipt = state(clock)
    assert receipt["owner_hold"] is True
    assert clock.q("select dufynd_ns_v1_pilot_restore()")["state"] == "OWNER_HOLD"
    assert state(clock) == receipt
    before = int(
        clock.q("select value->>'calls' from dufynd_master_status where key='test.legacy_ceo'")
    )
    wait_for(
        lambda: (
            int(
                clock.q(
                    "select value->>'calls' from dufynd_master_status where key='test.legacy_ceo'"
                )
            )
            > before
        )
    )
    assert state(clock) == receipt
    assert (
        clock.q(
            "select value->'enabled' from dufynd_master_status where key='jarvis.native_nightshift_v1.config'"
        )
        is False
    )
