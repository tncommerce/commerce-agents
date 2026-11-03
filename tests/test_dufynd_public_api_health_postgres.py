"""Execute public liveness bounds against disposable PostgreSQL, never live HTTP."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261028130335_dufynd_public_api_health_monitor.sql"
PENDING_GRACE_MIGRATION = (
    ROOT / "supabase/migrations/20261028134501_dufynd_public_api_pending_grace.sql"
)
KEY = "ops.public_api_health_v1"
URL = "https://scentai-api-kxhe.onrender.com/api/health"


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as connection:
        try:
            connection.execute("SET LOCAL statement_timeout='10s'")
            # Run alone or after the existing native suite. Restore its net
            # namespace, tables, functions, permissions and OIDs on rollback.
            connection.execute("""
                DO $fixture$ BEGIN
                  IF to_regnamespace('dufynd_api_health_fixture_net') IS NOT NULL THEN
                    RAISE EXCEPTION 'public API health fixture schema already exists';
                  END IF;
                  IF to_regnamespace('net') IS NOT NULL THEN
                    ALTER SCHEMA net RENAME TO dufynd_api_health_fixture_net;
                  END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role; END IF;
                END $fixture$;
                CREATE TABLE IF NOT EXISTS public.dufynd_master_status(
                  key text primary key,category text,value jsonb,priority integer,
                  last_verified_at timestamptz);
                CREATE TABLE IF NOT EXISTS public.dufynd_external_observers(
                  observer_id text primary key,source_type text,source_id text,config jsonb,
                  enabled boolean default false,interval_seconds int default 120,
                  last_attempt_at timestamptz,last_success_at timestamptz,last_cursor text,
                  last_event_at timestamptz,consecutive_failures int default 0,
                  next_retry_at timestamptz default now(),health_status text,last_error text,
                  last_snapshot jsonb,etag text,page_token text,request_id bigint,
                  request_started_at timestamptz,request_kind text,pending_cursor text,
                  pending_page_token text);
                -- Disabled legacy observers can still have pending responses;
                -- isolate those identities from this fixture's net namespace.
                UPDATE public.dufynd_external_observers
                  SET enabled=false,request_id=null,request_started_at=null;
                DELETE FROM public.dufynd_master_status WHERE key='ops.public_api_health_v1';
                CREATE SCHEMA net;
                CREATE TABLE net.http_request_queue(
                  id bigserial primary key,url text,headers jsonb,timeout_milliseconds int);
                CREATE TABLE net._http_response(
                  id bigint primary key,status_code int,content_type text,content text,
                  created timestamptz,headers jsonb,timed_out boolean,error_msg text);
                CREATE FUNCTION net.http_get(url text,headers jsonb,timeout_milliseconds int)
                RETURNS bigint LANGUAGE sql AS $stub$
                  INSERT INTO net.http_request_queue(url,headers,timeout_milliseconds)
                  VALUES(url,headers,timeout_milliseconds) RETURNING id
                $stub$;
            """)
            connection.execute(MIGRATION.read_text())
            connection.execute(PENDING_GRACE_MIGRATION.read_text())
            yield connection
        finally:
            connection.rollback()


def read(db):
    return db.execute("SELECT public.read_dufynd_public_api_health_v1()").fetchone()[0]


def poll(db):
    return db.execute("SELECT public.poll_dufynd_public_api_health_v1()").fetchone()[0]


def stored(db):
    return db.execute(
        "SELECT value FROM public.dufynd_master_status WHERE key=%s", (KEY,)
    ).fetchone()[0]


def patch(db, values):
    db.execute(
        "UPDATE public.dufynd_master_status SET value=value||%s::jsonb WHERE key=%s",
        (json.dumps(values), KEY),
    )


def enable(db):
    patch(db, {"enabled": True})


def respond(
    db,
    *,
    status=200,
    body='{"ok":true,"store":"DUFYND"}',
    content_type="application/json",
    timed_out=False,
    error=None,
    age_seconds=0,
):
    request_id = stored(db)["request_id"]
    db.execute("DELETE FROM net.http_request_queue WHERE id=%s", (request_id,))
    db.execute(
        """INSERT INTO net._http_response
        (id,status_code,content_type,content,created,timed_out,error_msg)
        VALUES(%s,%s,%s,%s,clock_timestamp()-make_interval(secs=>%s),%s,%s)""",
        (request_id, status, content_type, body, age_seconds, timed_out, error),
    )
    return request_id


def set_old_request(db, seconds=120):
    db.execute(
        """UPDATE public.dufynd_master_status SET value=value||jsonb_build_object(
        'requested_at',clock_timestamp()-make_interval(secs=>%s)) WHERE key=%s""",
        (seconds, KEY),
    )


def test_install_is_disabled_and_does_not_fabricate_source_success(db):
    assert read(db)["status"] == "disabled"
    assert poll(db)["healthy"] is False
    value = stored(db)
    assert "last_success_at" not in value and "valid_until" not in value
    assert "config_checked_at" in value
    assert db.execute("SELECT count(*) FROM net.http_request_queue").fetchone()[0] == 0


def test_caller_cannot_override_endpoint_headers_or_scope(db):
    enable(db)
    patch(db, {"endpoint": "http://169.254.169.254/", "headers": {"Authorization": "do-not-send"}})
    result = poll(db)
    request = db.execute(
        "SELECT url,headers,timeout_milliseconds FROM net.http_request_queue"
    ).fetchone()
    assert request == (
        URL,
        {"Accept": "application/json", "User-Agent": "DUFYND-Public-API-Health/1"},
        5000,
    )
    assert result["status"] == "pending" and result["healthy"] is False
    assert read(db)["status"] == "pending" and read(db)["healthy"] is False
    assert result["private_observer_evidence"] is False and result["full_chain_complete"] is False
    assert result["last_success_at"] is None


def test_one_pending_identity_and_no_backlog_when_worker_is_unavailable(db):
    enable(db)
    poll(db)
    request_id = stored(db)["request_id"]
    poll(db)
    set_old_request(db, 86400)
    for _ in range(3):
        result = poll(db)
        assert result["status"] == "unavailable"
        assert result["last_error"] == "request_dispatch_overdue"
        assert stored(db)["request_id"] == request_id
    assert db.execute("SELECT count(*) FROM net.http_request_queue").fetchone()[0] == 1
    assert read(db)["last_success_at"] is None


@pytest.mark.parametrize("age_seconds", [90, 120])
def test_pending_reader_allows_consumer_cadence_without_claiming_http_success(db, age_seconds):
    enable(db)
    poll(db)
    set_old_request(db, age_seconds)
    request_id = respond(db, age_seconds=age_seconds - 1)
    # Reproduce the real rollout: a valid response is already in pg_net, but
    # the scheduled consumer has not yet projected it into monitor state.
    db.execute(MIGRATION.read_text())
    previous = read(db)
    assert previous["status"] == "unavailable"
    assert previous["last_error"] == "request_overdue"
    before = stored(db)
    before_acl = db.execute(
        "SELECT proacl FROM pg_proc WHERE oid='public.read_dufynd_public_api_health_v1()'::regprocedure"
    ).fetchone()[0]
    db.execute(PENDING_GRACE_MIGRATION.read_text())
    result = read(db)
    assert result["status"] == "pending" and result["healthy"] is False
    assert result["last_success_at"] is None
    assert stored(db) == before
    assert (
        db.execute(
            "SELECT proacl FROM pg_proc WHERE oid='public.read_dufynd_public_api_health_v1()'::regprocedure"
        ).fetchone()[0]
        == before_acl
    )
    accepted = poll(db)
    assert accepted["healthy"] is True
    assert (
        db.execute(
            """SELECT (value->>'last_success_at')::timestamptz=r.created
        FROM public.dufynd_master_status s CROSS JOIN net._http_response r
        WHERE s.key=%s AND r.id=%s""",
            (KEY, request_id),
        ).fetchone()[0]
        is True
    )


def test_pending_reader_still_reports_overdue_after_grace_without_consumer(db):
    enable(db)
    poll(db)
    set_old_request(db, 181)
    result = read(db)
    assert result["status"] == "unavailable" and result["healthy"] is False
    assert result["last_error"] == "request_overdue"
    assert result["last_success_at"] is None


def test_only_actual_typed_health_response_sets_success_time(db):
    enable(db)
    poll(db)
    request_id = respond(db, content_type="application/json; charset=utf-8")
    result = poll(db)
    response_time = db.execute(
        "SELECT created FROM net._http_response WHERE id=%s", (request_id,)
    ).fetchone()[0]
    success_time = db.execute(
        "SELECT (value->>'last_success_at')::timestamptz FROM public.dufynd_master_status WHERE key=%s",
        (KEY,),
    ).fetchone()[0]
    assert result["healthy"] is True and result["status"] == "healthy"
    assert read(db)["healthy"] is True and read(db)["status"] == "healthy"
    assert success_time == response_time
    assert result["private_observer_evidence"] is False and result["full_chain_complete"] is False
    before = stored(db)["last_success_at"]
    poll(db)
    assert stored(db)["last_success_at"] == before
    assert db.execute("SELECT count(*) FROM net.http_request_queue").fetchone()[0] == 0


@pytest.mark.parametrize(
    "body",
    [
        "{",
        "[]",
        "null",
        '{"ok":"true","store":"DUFYND"}',
        '{"ok":false,"store":"DUFYND"}',
        '{"ok":true,"store":"OTHER"}',
        '{"ok":true}',
        '{"store":"DUFYND"}',
    ],
)
def test_malformed_false_or_wrong_store_payload_never_becomes_healthy(db, body):
    enable(db)
    poll(db)
    respond(db, body=body)
    result = poll(db)
    assert result["healthy"] is False and result["last_error"] == "health_payload_rejected"
    assert result["last_success_at"] is None


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"status": 503}, "http_status_rejected"),
        ({"status": 302}, "http_status_rejected"),
        ({"status": 304}, "http_status_rejected"),
        ({"timed_out": True}, "transport_failure"),
        ({"error": "sensitive provider error must not be persisted"}, "transport_failure"),
        ({"content_type": "text/html"}, "content_type_rejected"),
        ({"content_type": None}, "content_type_rejected"),
        ({"body": " " * 16385}, "response_size_rejected"),
        ({"age_seconds": -30}, "response_not_fresh"),
        ({"age_seconds": 900}, "response_not_fresh"),
    ],
)
def test_transport_and_response_bounds_fail_closed(db, kwargs, reason):
    enable(db)
    poll(db)
    respond(db, **kwargs)
    result = poll(db)
    assert result["healthy"] is False and result["last_error"] == reason
    assert result["last_success_at"] is None
    assert "sensitive provider error" not in json.dumps(stored(db))
    before = stored(db)
    poll(db)
    assert stored(db).get("request_id") is None
    assert stored(db)["next_poll_at"] == before["next_poll_at"]


def test_missing_response_after_worker_loses_request_enters_bounded_backoff(db):
    enable(db)
    poll(db)
    db.execute("DELETE FROM net.http_request_queue")
    set_old_request(db)
    result = poll(db)
    assert result["last_error"] == "response_missing" and result["healthy"] is False
    assert "request_id" not in stored(db)
    assert (
        db.execute(
            """SELECT extract(epoch FROM (
      (value->>'next_poll_at')::timestamptz-(value->>'last_error_at')::timestamptz))
      FROM public.dufynd_master_status WHERE key=%s""",
            (KEY,),
        ).fetchone()[0]
        == 120
    )


def test_failed_probe_preserves_previous_success_but_cannot_stay_healthy(db):
    enable(db)
    poll(db)
    respond(db)
    poll(db)
    old_success = stored(db)["last_success_at"]
    patch(db, {"next_poll_at": "2000-01-01T00:00:00Z"})
    poll(db)
    respond(db, status=503)
    result = poll(db)
    assert result["status"] == "unhealthy" and result["healthy"] is False
    assert stored(db)["last_success_at"] == old_success


def test_repeated_failure_backoff_caps_at_thirty_minutes(db):
    enable(db)
    for expected in (120, 240, 480, 960, 1800, 1800):
        patch(db, {"next_poll_at": "2000-01-01T00:00:00Z"})
        poll(db)
        respond(db, status=503)
        poll(db)
        delay = db.execute(
            """SELECT extract(epoch FROM (
            (value->>'next_poll_at')::timestamptz-(value->>'last_error_at')::timestamptz))
            FROM public.dufynd_master_status WHERE key=%s""",
            (KEY,),
        ).fetchone()[0]
        assert delay == expected
        assert read(db)["healthy"] is False
    assert stored(db)["consecutive_failures"] == 6
    assert "last_success_at" not in stored(db)


def test_disabling_pending_monitor_does_not_accept_later_response(db):
    enable(db)
    poll(db)
    patch(db, {"enabled": False})
    respond(db)
    result = poll(db)
    assert result["status"] == "disabled" and result["healthy"] is False
    assert "last_success_at" not in stored(db)
    assert db.execute("SELECT count(*) FROM net.http_request_queue").fetchone()[0] == 0


def test_reader_expires_success_when_no_cron_tick_runs(db):
    enable(db)
    poll(db)
    respond(db)
    poll(db)
    db.execute(
        """UPDATE public.dufynd_master_status SET value=value||jsonb_build_object(
      'last_success_at',now()-interval '601 seconds',
      'valid_until',now()-interval '1 second') WHERE key=%s""",
        (KEY,),
    )
    assert stored(db)["status"] == "healthy"
    result = read(db)
    assert result["status"] == "stale" and result["healthy"] is False
    assert result["last_error"] == "api_success_stale"


def test_reader_rejects_forged_expiry_and_future_success(db):
    enable(db)
    patch(
        db,
        {
            "status": "healthy",
            "last_status_code": 200,
            "last_success_at": "infinity",
            "valid_until": "infinity",
        },
    )
    assert read(db)["healthy"] is False
    db.execute(
        """UPDATE public.dufynd_master_status SET value=value||jsonb_build_object(
      'last_success_at',clock_timestamp(),'valid_until',clock_timestamp()+interval '1 day') WHERE key=%s""",
        (KEY,),
    )
    assert read(db)["healthy"] is False


def test_public_monitor_does_not_mutate_private_provider_evidence(db):
    db.execute("""INSERT INTO public.dufynd_external_observers
      (observer_id,source_type,source_id,enabled,last_cursor,last_snapshot,last_success_at,health_status)
      VALUES('render:srv-health-independent','render','srv-health-independent',false,
      'private-cursor','{"sha":"original-private-proof"}',now()-interval '6 days','stale')""")
    before = db.execute(
        "SELECT to_jsonb(o) FROM public.dufynd_external_observers o WHERE observer_id='render:srv-health-independent'"
    ).fetchone()[0]
    enable(db)
    poll(db)
    respond(db)
    poll(db)
    after = db.execute(
        "SELECT to_jsonb(o) FROM public.dufynd_external_observers o WHERE observer_id='render:srv-health-independent'"
    ).fetchone()[0]
    assert before == after


def test_no_transport_is_diagnostic_and_hook_preserves_existing_poll_contract(db):
    enable(db)
    db.execute("DROP SCHEMA net CASCADE")
    result = poll(db)
    assert result["status"] == "unavailable" and result["last_error"] == "pg_net_unavailable"
    assert result["last_success_at"] is None
    assert db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0] == {"available": False}


def test_existing_poll_hook_can_enqueue_without_private_work_or_new_cron(db):
    enable(db)
    result = db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0]
    assert result == {"attempted": 0}
    assert db.execute("SELECT count(*) FROM net.http_request_queue").fetchone()[0] == 1
    assert read(db)["healthy"] is False


def test_unexpected_monitor_exception_is_bounded_and_does_not_break_other_observers(db):
    enable(db)
    poll(db)
    db.execute("ALTER TABLE net._http_response DROP COLUMN content_type")
    result = poll(db)
    assert result["last_error"] == "monitor_internal_error"
    assert stored(db)["status"] == "unavailable"
    assert "column" not in json.dumps(stored(db))
    assert db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0] == {"attempted": 0}


def test_functions_keep_invoker_and_restricted_execute_privileges(db):
    for function in ("read_dufynd_public_api_health_v1", "poll_dufynd_public_api_health_v1"):
        row = db.execute(
            """SELECT p.prosecdef,p.proconfig,
          has_function_privilege('anon',p.oid,'execute'),
          has_function_privilege('authenticated',p.oid,'execute'),
          has_function_privilege('service_role',p.oid,'execute')
          FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='public' AND p.proname=%s""",
            (function,),
        ).fetchone()
        assert row[0] is False and row[1] == ["search_path=pg_catalog, public"]
        assert row[2:] == (False, False, True)


def test_reapplying_migration_preserves_monitor_state(db):
    enable(db)
    poll(db)
    before = stored(db)
    db.execute(MIGRATION.read_text())
    db.execute(PENDING_GRACE_MIGRATION.read_text())
    assert stored(db) == before
