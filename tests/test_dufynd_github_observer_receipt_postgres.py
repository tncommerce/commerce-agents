"""Real poll/capture/planner regressions with disposable PostgreSQL and no HTTP."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase/migrations"
MIGRATION = next(MIGRATIONS.glob("*_dufynd_github_observer_receipt_freshness.sql"))
BASELINE = MIGRATIONS / "20261028130335_dufynd_public_api_health_monitor.sql"
EVENTS = MIGRATIONS / "20261002094028_dufynd_supervisor_v2_external_events.sql"
NORMALIZER = MIGRATIONS / "20261002134258_dufynd_ci_pr_verifier.sql"
CREDENTIALS = MIGRATIONS / "20261002161040_dufynd_observer_credential_plane.sql"
PLANNER = MIGRATIONS / "20261028082303_jarvis_planner_technical_blockers.sql"
OBSERVER = "github_branch:scentai-mvp"
SHA_A = hashlib.sha1(b"receipt-fixture-old", usedforsecurity=False).hexdigest()
SHA_B = hashlib.sha1(b"receipt-fixture-new", usedforsecurity=False).hexdigest()
ETAG = '"receipt-fixture-validator"'


def function_sql(path, name):
    """Load the existing production function, without unrelated migration DDL."""
    source = path.read_text()
    start = re.search(
        rf"create(?:\s+or\s+replace)?\s+function\s+public\.{name}\s*\(.*?\bas\s+(\$[a-z_]*\$)",
        source,
        re.IGNORECASE | re.DOTALL,
    )
    assert start, name
    end = source.index(start[1], start.end()) + len(start[1])
    sql = source[start.start() : end] + ";"
    return re.sub(r"^create(?:\s+or\s+replace)?", "CREATE OR REPLACE", sql, count=1, flags=re.I)


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as connection:
        try:
            connection.execute("SET LOCAL statement_timeout='10s'")
            # Rollback restores an existing native-suite schema and all ACLs.
            # Only pg_net's transport is substituted; production normalization,
            # capture, deduplication, failure handling and planner reads run SQL.
            connection.execute("""
                DO $fixture$ BEGIN
                  IF to_regnamespace('dufynd_receipt_fixture_net') IS NOT NULL THEN
                    RAISE EXCEPTION 'receipt fixture schema already exists';
                  END IF;
                  IF to_regnamespace('net') IS NOT NULL THEN
                    ALTER SCHEMA net RENAME TO dufynd_receipt_fixture_net;
                  END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role; END IF;
                END $fixture$;
                CREATE TABLE IF NOT EXISTS public.dufynd_master_status(
                  key text primary key,category text,value jsonb,priority integer,last_verified_at timestamptz);
                CREATE TABLE IF NOT EXISTS public.dufynd_external_observers(
                  observer_id text primary key,source_type text,source_id text,config jsonb default '{}',
                  enabled boolean default false,interval_seconds int default 120,
                  last_attempt_at timestamptz,last_success_at timestamptz,last_cursor text,
                  last_event_at timestamptz,consecutive_failures int default 0,
                  next_retry_at timestamptz default now(),health_status text,last_error text,
                  last_snapshot jsonb default '{}',etag text,page_token text,request_id bigint,
                  request_started_at timestamptz,request_kind text,pending_cursor text,pending_page_token text);
                CREATE TABLE IF NOT EXISTS public.dufynd_task_external_waits(
                  task_id text,observer_id text);
                CREATE TABLE IF NOT EXISTS public.dufynd_jarvis_inbox(
                  event_id uuid default gen_random_uuid(),event_type text,source_type text,source_id text,
                  payload jsonb,status text,source_cursor text,fingerprint text,related_task_ids jsonb);
                CREATE UNIQUE INDEX IF NOT EXISTS dufynd_event_fingerprint
                  ON public.dufynd_jarvis_inbox(fingerprint) WHERE fingerprint IS NOT NULL;
                CREATE TABLE IF NOT EXISTS public.dufynd_broker_acceptance_sessions(
                  run_id bigint,source_sha text,status text,captured_observers jsonb,
                  created_at timestamptz,finalized_at timestamptz,recurring_read boolean);
                UPDATE public.dufynd_external_observers
                  SET enabled=false,request_id=null,request_started_at=null;
                DELETE FROM public.dufynd_master_status WHERE key='ops.public_api_health_v1';
                CREATE SCHEMA net;
                CREATE TABLE net.http_request_queue(
                  id bigserial primary key,url text,headers jsonb,timeout_milliseconds int);
                -- Match pg_net: response IDs are not constrained unique.
                CREATE TABLE net._http_response(
                  id bigint,status_code int,content_type text,content text,
                  created timestamptz,headers jsonb,timed_out boolean,error_msg text);
                CREATE FUNCTION net.http_get(url text,headers jsonb,timeout_milliseconds int)
                RETURNS bigint LANGUAGE sql AS $stub$
                  INSERT INTO net.http_request_queue(url,headers,timeout_milliseconds)
                  VALUES(url,headers,timeout_milliseconds) RETURNING id
                $stub$;
            """)
            for name in ("dufynd_observer_failure", "capture_dufynd_observation"):
                connection.execute(function_sql(EVENTS, name))
            connection.execute(
                function_sql(NORMALIZER, "normalize_dufynd_observation").replace(
                    "public.normalize_dufynd_observation(",
                    "public.normalize_dufynd_observation_base(",
                    1,
                )
            )
            connection.execute(function_sql(CREDENTIALS, "normalize_dufynd_observation"))
            connection.execute(function_sql(PLANNER, "read_dufynd_technical_work_blockers_v1"))
            connection.execute(BASELINE.read_text())
            connection.execute(MIGRATION.read_text())
            yield connection
        finally:
            connection.rollback()


def seed(db, *, etag=None, interval=120):
    db.execute(
        """INSERT INTO public.dufynd_external_observers
        (observer_id,source_type,source_id,enabled,interval_seconds,last_success_at,
         last_snapshot,last_cursor,etag,health_status,next_retry_at)
        VALUES(%s,'github_branch','scentai-mvp',true,%s,clock_timestamp()-interval '60 seconds',
               %s::jsonb,%s,%s,'healthy',now()-interval '1 second')
        ON CONFLICT(observer_id) DO UPDATE SET enabled=true,interval_seconds=excluded.interval_seconds,
        last_success_at=excluded.last_success_at,last_snapshot=excluded.last_snapshot,
        last_cursor=excluded.last_cursor,etag=excluded.etag,health_status='healthy',last_error=null,
        next_retry_at=excluded.next_retry_at,request_id=null,request_started_at=null,
        request_kind=null,pending_cursor=null,consecutive_failures=0""",
        (OBSERVER, interval, json.dumps({"sha": SHA_A}), SHA_A, etag),
    )


def poll(db):
    return db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0]


def stored(db):
    # JSON avoids psycopg's intentional rejection of infinite datetime values.
    return db.execute(
        "SELECT to_jsonb(o) FROM public.dufynd_external_observers o WHERE observer_id=%s",
        (OBSERVER,),
    ).fetchone()[0]


def event_count(db):
    return db.execute(
        """SELECT count(*) FROM public.dufynd_jarvis_inbox
        WHERE source_type='github_branch' AND source_id='scentai-mvp'
          AND payload->'evidence'->>'sha' IN (%s,%s)""",
        (SHA_A, SHA_B),
    ).fetchone()[0]


def delay_pending(db, seconds):
    """Represent an earlier genuine dispatch, including its unchanged binding."""
    db.execute(
        """UPDATE public.dufynd_external_observers
        SET request_started_at=clock_timestamp()-make_interval(secs=>%s),
            last_attempt_at=clock_timestamp()-make_interval(secs=>%s)
        WHERE observer_id=%s""",
        (seconds, seconds, OBSERVER),
    )
    db.execute(
        """UPDATE public.dufynd_external_observers SET pending_cursor=encode(sha256(convert_to(
        jsonb_build_array(etag,last_snapshot,extract(epoch from last_success_at),
          request_id,extract(epoch from request_started_at))::text,'UTF8')),'hex')
        WHERE observer_id=%s AND request_kind='github_conditional'""",
        (OBSERVER,),
    )


def respond(db, *, status=200, body=None, headers=None, age=0, timed_out=False, error=None):
    if body is None and status == 200:
        body = json.dumps({"name": "scentai-mvp", "commit": {"sha": SHA_B}})
    request_id = stored(db)["request_id"]
    receipt = db.execute(
        """INSERT INTO net._http_response
        (id,status_code,content,created,headers,timed_out,error_msg)
        VALUES(%s,%s,%s,clock_timestamp()-make_interval(secs=>%s),%s::jsonb,%s,%s)
        RETURNING to_jsonb(created)""",
        (request_id, status, body, age, json.dumps(headers or {}), timed_out, error),
    ).fetchone()[0]
    return receipt


def assert_rejected(db, before, reason):
    after = stored(db)
    assert after["last_success_at"] == before["last_success_at"]
    assert after["last_snapshot"] == before["last_snapshot"]
    assert after["last_cursor"] == before["last_cursor"]
    assert after["health_status"] != "healthy"
    assert after["last_error"] == reason
    assert after["request_id"] is None and after["request_started_at"] is None
    assert after["request_kind"] is None and after["pending_cursor"] is None
    assert event_count(db) == 0
    assert db.execute(
        """SELECT next_retry_at BETWEEN last_attempt_at+interval '120 seconds' AND last_attempt_at+interval '1 hour'
        FROM public.dufynd_external_observers WHERE observer_id=%s""",
        (OBSERVER,),
    ).fetchone()[0]


@pytest.mark.parametrize("status", [200, 304])
@pytest.mark.parametrize(("interval", "age"), [(120, 601), (1200, 3601)])
def test_expired_receipt_never_renews_success_or_ingests_a_branch(db, status, interval, age):
    seed(db, etag=ETAG, interval=interval)
    poll(db)
    delay_pending(db, age + 1)
    before = stored(db)
    respond(db, status=status, age=age)
    poll(db)
    assert_rejected(db, before, "stale_observer_receipt")
    report = db.execute("SELECT public.read_dufynd_technical_work_blockers_v1()").fetchone()[0]
    assert report["github_sha"] is None
    assert "production_revision_unverified" in report["issues"]


@pytest.mark.parametrize("status", [200, 304])
@pytest.mark.parametrize(
    "timestamp",
    [
        "NULL",
        "'infinity'::timestamptz",
        "'-infinity'::timestamptz",
        "clock_timestamp()+interval '1 second'",
    ],
)
def test_invalid_receipt_time_never_becomes_fresh_evidence(db, status, timestamp):
    seed(db, etag=ETAG)
    poll(db)
    before = stored(db)
    respond(db, status=status)
    db.execute(f"UPDATE net._http_response SET created={timestamp}")
    poll(db)
    assert_rejected(db, before, "invalid_observer_receipt_timestamp")


@pytest.mark.parametrize("status", [200, 304])
def test_receipt_before_its_request_is_rejected(db, status):
    seed(db, etag=ETAG)
    poll(db)
    before = stored(db)
    respond(db, status=status, age=1)
    poll(db)
    assert_rejected(db, before, "invalid_observer_receipt_timestamp")


@pytest.mark.parametrize(
    "timestamp",
    [
        "NULL",
        "'infinity'::timestamptz",
        "'-infinity'::timestamptz",
        "clock_timestamp()+interval '1 second'",
    ],
)
def test_invalid_request_time_is_not_pending_or_successful(db, timestamp):
    seed(db)
    poll(db)
    before = stored(db)
    respond(db)
    db.execute(
        f"UPDATE public.dufynd_external_observers SET request_started_at={timestamp} WHERE observer_id=%s",
        (OBSERVER,),
    )
    poll(db)
    assert_rejected(db, before, "invalid_observer_request_timestamp")


@pytest.mark.parametrize("status", [200, 304])
@pytest.mark.parametrize(("timed_out", "error"), [(True, None), (False, "connection reset")])
def test_success_status_with_transport_error_is_not_success(db, status, timed_out, error):
    seed(db, etag=ETAG)
    poll(db)
    before = stored(db)
    respond(db, status=status, timed_out=timed_out, error=error)
    poll(db)
    assert_rejected(db, before, "external_transport_failure")


def test_accepted_200_uses_receipt_time_and_cannot_be_replayed(db):
    seed(db)
    poll(db)
    delay_pending(db, 31)
    attempt = stored(db)["request_started_at"]
    created = respond(db, age=30, headers={"etag": ETAG})
    poll(db)
    after = stored(db)
    assert after["last_success_at"] == created
    assert after["last_attempt_at"] == attempt
    assert after["last_snapshot"] == {"sha": SHA_B}
    assert after["health_status"] == "healthy" and after["etag"] == ETAG
    assert after["request_kind"] is None and after["pending_cursor"] is None
    assert event_count(db) == 1
    assert poll(db) == {"attempted": 0}
    assert stored(db) == after and event_count(db) == 1
    report = db.execute("SELECT public.read_dufynd_technical_work_blockers_v1()").fetchone()[0]
    assert (
        report["github_sha"] == SHA_B and "production_revision_unverified" not in report["issues"]
    )


@pytest.mark.parametrize("response_headers", [{}, {"etag": ETAG}, {"ETag": ETAG}])
def test_bound_304_revalidates_only_retained_snapshot_at_receipt_time(db, response_headers):
    seed(db, etag=ETAG)
    poll(db)
    delay_pending(db, 31)
    before = stored(db)
    created = respond(db, status=304, age=30, headers=response_headers)
    poll(db)
    after = stored(db)
    assert after["last_success_at"] == created
    assert after["last_snapshot"] == before["last_snapshot"]
    assert after["last_cursor"] == before["last_cursor"] and after["etag"] == ETAG
    assert after["health_status"] == "healthy" and after["request_id"] is None
    assert after["request_kind"] is None and after["pending_cursor"] is None
    assert event_count(db) == 0
    assert poll(db) == {"attempted": 0}
    assert stored(db) == after


@pytest.mark.parametrize(
    "change",
    [
        'last_snapshot=last_snapshot||\'{"state":"changed"}\'::jsonb',
        "etag='\"another-validator\"'",
        "last_success_at=last_success_at-interval '1 second'",
        "last_snapshot='{}'::jsonb",
        "request_kind=NULL,pending_cursor=NULL",
        "request_started_at=request_started_at-interval '1 second'",
    ],
)
def test_304_cannot_bless_changed_or_unproven_prior_state(db, change):
    seed(db, etag=ETAG)
    poll(db)
    db.execute(
        f"UPDATE public.dufynd_external_observers SET {change} WHERE observer_id=%s", (OBSERVER,)
    )
    before = stored(db)
    respond(db, status=304)
    poll(db)
    assert_rejected(db, before, "invalid_observer_not_modified")
    assert stored(db)["etag"] is None


@pytest.mark.parametrize(
    ("body", "headers"),
    [("unexpected body", {}), (None, {"etag": '"foreign-validator"'}), (None, {"ETag": ""})],
)
def test_304_conflicting_body_or_etag_is_rejected(db, body, headers):
    seed(db, etag=ETAG)
    poll(db)
    before = stored(db)
    respond(db, status=304, body=body, headers=headers)
    poll(db)
    assert_rejected(db, before, "invalid_observer_not_modified")


def test_conditional_binding_survives_a_session_timezone_change(db):
    seed(db, etag=ETAG)
    db.execute("SET LOCAL TIME ZONE 'Pacific/Honolulu'")
    poll(db)
    respond(db, status=304)
    db.execute("SET LOCAL TIME ZONE 'Europe/Berlin'")
    poll(db)
    assert stored(db)["health_status"] == "healthy"
    assert stored(db)["last_error"] is None and event_count(db) == 0


def test_receipt_after_transaction_start_uses_wall_clock_for_validation(db):
    seed(db)
    poll(db)
    respond(db)
    assert db.execute("SELECT created>now() FROM net._http_response").fetchone()[0]
    poll(db)
    assert stored(db)["health_status"] == "healthy"
    assert event_count(db) == 1


def test_waiting_for_shared_lock_does_not_freeze_freshness_or_backoff_time(db):
    import psycopg

    seed(db)
    db.execute(
        """UPDATE public.dufynd_external_observers SET request_id=4242,
        request_kind='github_get',request_started_at=clock_timestamp()-interval '601 seconds'
        WHERE observer_id=%s""",
        (OBSERVER,),
    )
    before = stored(db)
    respond(db, age=599.2)
    with psycopg.connect(DSN) as lock_holder:
        lock_holder.execute("SELECT pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'))")
        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting_poll = executor.submit(poll, db)
            time.sleep(1.1)
            assert not waiting_poll.done()
            released_at = lock_holder.execute("SELECT clock_timestamp()").fetchone()[0]
            lock_holder.commit()
            waiting_poll.result(timeout=5)
    assert_rejected(db, before, "stale_observer_receipt")
    assert db.execute(
        """SELECT last_attempt_at>=%s AND next_retry_at>=last_attempt_at+interval '120 seconds'
        FROM public.dufynd_external_observers WHERE observer_id=%s""",
        (released_at, OBSERVER),
    ).fetchone()[0]


def test_refused_capture_cannot_be_promoted_to_source_success(db):
    seed(db)
    poll(db)
    before = stored(db)
    respond(db, headers={"etag": ETAG})
    # Explicitly exercise the existing capture contract's accepted=false result.
    db.execute("""CREATE OR REPLACE FUNCTION public.capture_dufynd_observation(p_observer_id text,p_raw jsonb)
        RETURNS jsonb LANGUAGE sql SET search_path TO 'public'
        AS $refused$ SELECT '{"accepted":false,"reason":"unknown_observer"}'::jsonb $refused$""")
    poll(db)
    assert_rejected(db, before, "observation_not_accepted")
    assert stored(db)["etag"] == before["etag"]


def test_new_body_without_etag_clears_validator_and_next_get_is_unconditional(db):
    seed(db, etag=ETAG)
    poll(db)
    respond(db, headers={})
    poll(db)
    assert stored(db)["etag"] is None and stored(db)["last_snapshot"] == {"sha": SHA_B}
    db.execute(
        "UPDATE public.dufynd_external_observers SET next_retry_at=now() WHERE observer_id=%s",
        (OBSERVER,),
    )
    poll(db)
    headers = db.execute(
        "SELECT headers FROM net.http_request_queue ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    assert "If-None-Match" not in headers
    assert stored(db)["request_kind"] == "github_get" and stored(db)["pending_cursor"] is None


@pytest.mark.parametrize("status", [200, 304])
def test_ambiguous_duplicate_receipt_id_never_ingests_or_revalidates(db, status):
    seed(db, etag=ETAG)
    poll(db)
    before = stored(db)
    respond(db, status=status)
    respond(db, status=status)
    poll(db)
    assert_rejected(db, before, "ambiguous_observer_receipt")
    after = stored(db)
    assert poll(db) == {"attempted": 0} and stored(db) == after


@pytest.mark.parametrize("body", ["", "null", "{}", "{broken", "[]"])
def test_200_without_valid_bounded_source_body_is_rejected(db, body):
    seed(db)
    poll(db)
    before = stored(db)
    respond(db, body=body)
    poll(db)
    assert_rejected(db, before, "invalid_bounded_source_response")


@pytest.mark.parametrize("status", [200, 304])
def test_disabled_observer_pending_response_cannot_change_evidence_or_health(db, status):
    seed(db, etag=ETAG)
    poll(db)
    db.execute(
        "UPDATE public.dufynd_external_observers SET enabled=false WHERE observer_id=%s",
        (OBSERVER,),
    )
    before = stored(db)
    respond(db, status=status, headers={"etag": '"replacement"'})
    poll(db)
    after = stored(db)
    for field in (
        "last_success_at",
        "last_snapshot",
        "last_cursor",
        "etag",
        "health_status",
        "last_error",
    ):
        assert after[field] == before[field]
    assert after["request_id"] is None and after["request_started_at"] is None
    assert after["request_kind"] is None and after["pending_cursor"] is None
    assert event_count(db) == 0


def test_pending_response_preserves_existing_grace_and_then_bounded_failure(db):
    seed(db)
    poll(db)
    before = stored(db)
    assert poll(db) == {"attempted": 0} and stored(db) == before
    delay_pending(db, 61)
    poll(db)
    assert_rejected(db, before, "external_transport_failure")


def test_rate_limit_keeps_existing_retry_after_bound_without_success(db):
    seed(db)
    poll(db)
    before = stored(db)
    respond(db, status=429, headers={"retry-after": "99999"})
    poll(db)
    assert_rejected(db, before, "rate_limited")
    assert db.execute(
        "SELECT next_retry_at=last_attempt_at+interval '1 hour' FROM public.dufynd_external_observers WHERE observer_id=%s",
        (OBSERVER,),
    ).fetchone()[0]


def test_upgrade_resets_only_github_validators_without_rewriting_source_history(db):
    seed(db, etag=ETAG)
    poll(db)
    before = stored(db)
    db.execute(
        """INSERT INTO public.dufynd_external_observers
        (observer_id,source_type,source_id,enabled,etag,last_snapshot,health_status)
        VALUES('render:srv-receipt-upgrade','render','srv-receipt-upgrade',false,%s,'{}','stale')""",
        (ETAG,),
    )
    acl = db.execute(
        "SELECT proacl FROM pg_proc WHERE oid='public.poll_dufynd_observers()'::regprocedure"
    ).fetchone()[0]
    db.execute(MIGRATION.read_text())
    after = stored(db)
    assert after == {**before, "etag": None}
    db.execute(MIGRATION.read_text())
    assert stored(db) == after
    assert (
        db.execute(
            "SELECT etag FROM public.dufynd_external_observers WHERE observer_id='render:srv-receipt-upgrade'"
        ).fetchone()[0]
        == ETAG
    )
    assert (
        db.execute(
            "SELECT proacl FROM pg_proc WHERE oid='public.poll_dufynd_observers()'::regprocedure"
        ).fetchone()[0]
        == acl
    )
    respond(db, status=304)
    poll(db)
    assert_rejected(db, before, "invalid_observer_not_modified")


def test_upgrade_makes_next_due_legacy_validator_get_unconditional(db):
    seed(db, etag=ETAG)
    db.execute(MIGRATION.read_text())
    poll(db)
    headers = db.execute("SELECT headers FROM net.http_request_queue").fetchone()[0]
    assert "If-None-Match" not in headers
    assert stored(db)["request_kind"] == "github_get"
    respond(db, headers={"etag": ETAG})
    poll(db)
    assert stored(db)["last_snapshot"] == {"sha": SHA_B} and stored(db)["etag"] == ETAG


@pytest.mark.parametrize(
    ("source_type", "source_id", "body", "url_suffix"),
    [
        (
            "github_branch",
            "scentai-mvp",
            {"name": "scentai-mvp", "commit": {"sha": SHA_B}},
            "branches/scentai-mvp",
        ),
        (
            "github_pr",
            "999901",
            {
                "number": 999901,
                "state": "open",
                "head": {"sha": SHA_B},
                "base": {"ref": "scentai-mvp", "sha": SHA_A},
            },
            "pulls/999901",
        ),
        (
            "github_ci",
            "999902",
            {
                "id": 999902,
                "head_branch": "scentai-mvp",
                "head_sha": SHA_B,
                "path": ".github/workflows/ci.yml",
                "status": "completed",
                "conclusion": "success",
            },
            "actions/runs/999902",
        ),
        (
            "github_workflow",
            "999903",
            {
                "id": 999903,
                "head_branch": "scentai-mvp",
                "head_sha": SHA_B,
                "status": "completed",
                "conclusion": "success",
            },
            "actions/runs/999903",
        ),
    ],
)
def test_all_existing_github_types_accept_200_then_bound_304(
    db, source_type, source_id, body, url_suffix
):
    observer_id = f"{source_type}:{source_id}"
    db.execute(
        """INSERT INTO public.dufynd_external_observers
        (observer_id,source_type,source_id,enabled,last_snapshot,health_status,next_retry_at)
        VALUES(%s,%s,%s,true,'{}','initializing',now())
        ON CONFLICT(observer_id) DO UPDATE SET enabled=true,last_snapshot='{}',
        health_status='initializing',next_retry_at=now(),last_success_at=null,etag=null""",
        (observer_id, source_type, source_id),
    )
    poll(db)
    request_id, url, headers = db.execute(
        "SELECT id,url,headers FROM net.http_request_queue"
    ).fetchone()
    assert url == "https://api.github.com/repos/tncommerce/commerce-agents/" + url_suffix
    assert "If-None-Match" not in headers
    db.execute(
        """INSERT INTO net._http_response(id,status_code,content,headers,created)
        VALUES(%s,200,%s,%s::jsonb,clock_timestamp())""",
        (request_id, json.dumps(body), json.dumps({"etag": ETAG})),
    )
    poll(db)
    first = db.execute(
        "SELECT to_jsonb(o) FROM public.dufynd_external_observers o WHERE observer_id=%s",
        (observer_id,),
    ).fetchone()[0]
    assert first["health_status"] == "healthy" and first["last_snapshot"]["sha"] == SHA_B
    db.execute(
        "UPDATE public.dufynd_external_observers SET next_retry_at=now() WHERE observer_id=%s",
        (observer_id,),
    )
    poll(db)
    request_id, headers = db.execute(
        "SELECT id,headers FROM net.http_request_queue ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert headers["If-None-Match"] == ETAG
    db.execute(
        "INSERT INTO net._http_response(id,status_code,created) VALUES(%s,304,clock_timestamp())",
        (request_id,),
    )
    poll(db)
    after = db.execute(
        "SELECT to_jsonb(o) FROM public.dufynd_external_observers o WHERE observer_id=%s",
        (observer_id,),
    ).fetchone()[0]
    assert after["health_status"] == "healthy" and after["last_snapshot"] == first["last_snapshot"]
    assert after["last_success_at"] > first["last_success_at"]
