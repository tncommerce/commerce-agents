"""Atomic Render-only capture through real PostgreSQL, no provider requests."""

from __future__ import annotations

import copy
import json
import os
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_private_observer_ingest import (
    HEALTH_PATH,
    RENDER_PATH,
    ArtifactError,
    ingest_render_artifact,
    ingest_render_recovery,
)
from tests.test_dufynd_github_observer_receipt_postgres import function_sql
from tests.test_dufynd_render_observer_recovery import DEPLOY, SOURCE

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "supabase/migrations"
MIGRATION = SQL / "20261029104500_dufynd_render_only_observer_capture.sql"
CREDENTIALS = SQL / "20261002161040_dufynd_observer_credential_plane.sql"
EVENTS = SQL / "20261002094028_dufynd_supervisor_v2_external_events.sql"
NORMALIZER = SQL / "20261002134258_dufynd_ci_pr_verifier.sql"
PROJECTOR = SQL / "20261003092500_dufynd_private_observer_health_projection.sql"
KEY = "ops.private_observer.render_capture_v1"
API = "render:srv-dakpfrnf3r2c73dr3f20"
GMAIL_IDS = ("1a0f385ed98c6af8", "1a0f69c169fb928f", "1a0f6a90772a743d")


@contextmanager
def capture_database(dsn):
    import psycopg

    with psycopg.connect(dsn) as connection:
        try:
            connection.execute("SET LOCAL statement_timeout='10s'")
            connection.execute("""
                DO $fixture$ BEGIN
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role; END IF;
                END $fixture$;
                CREATE TABLE IF NOT EXISTS public.dufynd_master_status(
                  key text primary key,category text,value jsonb,priority int,last_verified_at timestamptz);
                CREATE TABLE IF NOT EXISTS public.dufynd_external_observers(
                  observer_id text primary key,source_type text,source_id text,config jsonb default '{}',
                  enabled boolean default false,interval_seconds int default 120,
                  last_attempt_at timestamptz,last_success_at timestamptz,last_cursor text,
                  last_event_at timestamptz,consecutive_failures int default 0,
                  next_retry_at timestamptz default now(),health_status text,last_error text,
                  last_snapshot jsonb default '{}',etag text,page_token text,request_id bigint,
                  request_started_at timestamptz,request_kind text,pending_cursor text,pending_page_token text);
                CREATE TABLE IF NOT EXISTS public.dufynd_task_external_waits(task_id text,observer_id text);
                CREATE TABLE IF NOT EXISTS public.dufynd_jarvis_inbox(
                  event_id uuid default gen_random_uuid(),event_type text,source_type text,source_id text,
                  payload jsonb,status text,source_cursor text,fingerprint text,related_task_ids jsonb);
                CREATE UNIQUE INDEX IF NOT EXISTS dufynd_event_fingerprint
                  ON public.dufynd_jarvis_inbox(fingerprint) WHERE fingerprint IS NOT NULL;
                CREATE TABLE IF NOT EXISTS public.dufynd_broker_acceptance_sessions(
                  run_id bigint,source_sha text,status text,captured_observers jsonb,
                  created_at timestamptz,finalized_at timestamptz,recurring_read boolean);
                DELETE FROM public.dufynd_master_status WHERE key='ops.private_observer.render_capture_v1';
                INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
                VALUES('jarvis.private_observer_scheduler_v1','jarvis',
                  '{"gmail_recovery_paused":true,"owner_action_required":false}',100,now())
                ON CONFLICT(key) DO UPDATE SET value=excluded.value,last_verified_at=excluded.last_verified_at;
            """)
            if (
                connection.execute(
                    "SELECT to_regclass('public.dufynd_observer_credentials')"
                ).fetchone()[0]
                is None
            ):
                connection.execute(
                    CREDENTIALS.read_text().split(
                        "create function public.get_dufynd_credential_health"
                    )[0]
                )
            connection.execute("""
                UPDATE public.dufynd_observer_credentials SET activation_enabled=true,
                  status=CASE WHEN provider='render' THEN 'healthy' ELSE 'revoked' END,
                  health_reason=CASE WHEN provider='render' THEN 'healthy' ELSE 'revoked' END,
                  revoked_at=CASE WHEN provider='gmail' THEN now()-interval '2 hours' ELSE null END,
                  expires_at=CASE WHEN provider='gmail' THEN now()-interval '2 hours' ELSE null END,
                  refreshed_at=null,rotation_due_at=null,last_health_check=now()-interval '2 hours';
            """)
            for kind, identity in (
                ("render", API.split(":", 1)[1]),
                *(("gmail", x) for x in GMAIL_IDS),
            ):
                connection.execute(
                    """INSERT INTO public.dufynd_external_observers
                    (observer_id,source_type,source_id,enabled,interval_seconds,health_status,
                     last_success_at,last_attempt_at,next_retry_at,last_snapshot,last_cursor)
                    VALUES(%s,%s,%s,true,120,%s,now()-interval '2 hours',now()-interval '2 hours',
                      now()-interval '119 minutes','{"retained":true}','42')
                    ON CONFLICT(observer_id) DO UPDATE SET enabled=true,source_type=excluded.source_type,
                      source_id=excluded.source_id,health_status=excluded.health_status,
                      last_success_at=excluded.last_success_at,last_attempt_at=excluded.last_attempt_at,
                      next_retry_at=excluded.next_retry_at,last_snapshot=excluded.last_snapshot,
                      last_cursor=excluded.last_cursor""",
                    (
                        f"{kind}:{identity}",
                        kind,
                        identity,
                        "stale" if kind == "render" else "blocked_configuration",
                    ),
                )
            connection.execute(
                function_sql(NORMALIZER, "normalize_dufynd_observation").replace(
                    "public.normalize_dufynd_observation(",
                    "public.normalize_dufynd_observation_base(",
                    1,
                )
            )
            for path, name in (
                (CREDENTIALS, "normalize_dufynd_observation"),
                (EVENTS, "capture_dufynd_observation"),
                (CREDENTIALS, "get_dufynd_credential_health"),
                (CREDENTIALS, "capture_dufynd_broker_observation"),
                (PROJECTOR, "project_dufynd_broker_health"),
            ):
                connection.execute(function_sql(path, name))
            connection.execute(MIGRATION.read_text())
            yield connection
        finally:
            connection.rollback()


@pytest.fixture
def db():
    with capture_database(DSN) as connection:
        yield connection


def health(db, *, age=30, gmail_status="revoked"):
    observed = db.execute("SELECT clock_timestamp()").fetchone()[0] - timedelta(seconds=age)
    rows = db.execute(
        "SELECT provider,to_jsonb(c)-'activation_enabled' FROM public.dufynd_observer_credentials c"
    ).fetchall()
    result = dict(rows)
    for provider in ("render", "gmail"):
        result[provider]["last_health_check"] = observed.isoformat()
    result["gmail"]["status"] = gmail_status
    result["gmail"]["health_reason"] = gmail_status
    if gmail_status != "revoked":
        result["gmail"]["revoked_at"] = None
    if gmail_status == "missing_configuration":
        result["gmail"]["expires_at"] = None
    return result


def capture(db, payload=None, *, source=None, evidence=None):
    return db.execute(
        "SELECT public.capture_dufynd_render_observer_read_v1(%s::jsonb,%s::jsonb,%s::jsonb)",
        (
            json.dumps(source if source is not None else SOURCE),
            json.dumps(payload if payload is not None else health(db)),
            json.dumps(evidence if evidence is not None else [DEPLOY]),
        ),
    ).fetchone()[0]


def state(db):
    return db.execute("""SELECT jsonb_build_object(
      'observers',(SELECT jsonb_agg(to_jsonb(o) ORDER BY observer_id) FROM public.dufynd_external_observers o),
      'credentials',(SELECT jsonb_agg(to_jsonb(c) ORDER BY credential_id) FROM public.dufynd_observer_credentials c),
      'receipt',(SELECT to_jsonb(m) FROM public.dufynd_master_status m WHERE key='ops.private_observer.render_capture_v1'),
      'pause',(SELECT to_jsonb(m) FROM public.dufynd_master_status m WHERE key='jarvis.private_observer_scheduler_v1'),
      'sessions',(SELECT jsonb_agg(to_jsonb(s)) FROM public.dufynd_broker_acceptance_sessions s),
      'events',(SELECT count(*) FROM public.dufynd_jarvis_inbox),
      'waits',(SELECT count(*) FROM public.dufynd_task_external_waits))""").fetchone()[0]


def observer(db):
    return db.execute(
        "SELECT to_jsonb(o) FROM public.dufynd_external_observers o WHERE observer_id=%s", (API,)
    ).fetchone()[0]


class PgBridge(DufyndJarvisBridge):
    def __init__(self, db):
        super().__init__(supabase_url="https://unused.invalid", secret_key="fixture-never-sent")
        self.db = db
        self.calls = []

    def _rpc(self, function_name, payload=None):
        self.calls.append(function_name)
        assert function_name == "capture_dufynd_render_observer_read_v1"
        return capture(
            self.db, payload["p_health"], source=payload["p_source"], evidence=payload["p_evidence"]
        )


def write_artifact(tmp_path, payload, *, source=None):
    path = tmp_path / "broker-render-observations.json"
    path.write_text(
        json.dumps({"_meta": source or SOURCE, HEALTH_PATH: payload, RENDER_PATH: [DEPLOY]})
    )
    return path


@pytest.mark.parametrize("gmail_status", ["revoked", "expired", "missing_configuration"])
def test_real_python_ingest_projects_metadata_and_captures_only_api(db, tmp_path, gmail_status):
    payload = health(db, gmail_status=gmail_status)
    before = state(db)
    bridge = PgBridge(db)
    result = ingest_render_artifact(
        bridge,
        write_artifact(tmp_path, payload),
        expected_run_id=SOURCE["run_id"],
        expected_sha=SOURCE["sha"],
        expected_run_attempt="1",
    )
    after = state(db)
    assert bridge.calls == ["capture_dufynd_render_observer_read_v1"]
    assert result["render_captures"] == 1 and not result["reused"]
    assert result["gmail_captures"] == result["acks"] == 0
    assert not any(
        result[key] for key in ("activation_changed", "full_chain_complete", "business_success")
    )
    assert after["pause"] == before["pause"] and after["sessions"] == before["sessions"]
    assert after["waits"] == before["waits"]
    assert [row for row in after["observers"] if row["source_type"] == "gmail"] == [
        row for row in before["observers"] if row["source_type"] == "gmail"
    ]
    assert all(row["activation_enabled"] for row in after["credentials"])
    assert observer(db)["last_snapshot"] == {
        "sha": DEPLOY["commit_sha"],
        "state": "live",
        "service_id": DEPLOY["service_id"],
        "deployment_id": DEPLOY["deployment_id"],
    }
    assert db.execute(
        "SELECT last_success_at=%s::timestamptz FROM public.dufynd_external_observers WHERE observer_id=%s",
        (payload["render"]["last_health_check"], API),
    ).fetchone()[0]
    assert db.execute(
        "SELECT last_success_at<now()-interval '20 seconds' FROM public.dufynd_external_observers WHERE observer_id=%s",
        (API,),
    ).fetchone()[0]
    assert not any(
        row["observer_id"] == "render:srv-dakpiajl550s73cp4lvg" for row in after["observers"]
    )


def test_gmail_failure_recovery_reuses_identical_atomic_boundary(db, tmp_path):
    bridge = PgBridge(db)
    result = ingest_render_recovery(
        bridge,
        write_artifact(tmp_path, health(db)),
        failure_source=SOURCE,
        expected_run_id=SOURCE["run_id"],
        expected_sha=SOURCE["sha"],
        expected_run_attempt="1",
    )
    assert result["render_captures"] == 1 and result["full_chain_complete"] is False
    assert bridge.calls == ["capture_dufynd_render_observer_read_v1"]


def test_exact_replay_is_noop_for_every_persisted_field(db, tmp_path):
    payload = health(db)
    first = capture(db, payload)
    committed = state(db)
    db.execute("SELECT pg_sleep(0.01)")
    replay = capture(db, payload)
    assert replay["accepted"] and replay["reused"] and replay["render_captures"] == 0
    assert replay["observed_at"] == first["observed_at"]
    assert state(db) == committed
    # The ingestion job can lose its response after a committed RPC and retry
    # the same artifact. Its summary must report zero additional captures.
    summary = ingest_render_artifact(
        PgBridge(db),
        write_artifact(tmp_path, payload),
        expected_run_id=SOURCE["run_id"],
        expected_sha=SOURCE["sha"],
        expected_run_attempt="1",
    )
    assert summary["reused"] is True and summary["render_captures"] == 0
    assert state(db) == committed


def test_committed_capture_response_loss_retries_from_second_connection(tmp_path):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    # A disposable database lets this one test commit for real without leaking
    # fixtures or revised functions into the native suite's shared database.
    name = "dufynd_render_receipt_" + uuid4().hex
    dsn = make_conninfo(DSN, dbname=name)
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            with capture_database(dsn) as producer:
                payload = health(producer)
                first = capture(producer, payload)
                producer.commit()
                committed = state(producer)
                producer.rollback()
                with psycopg.connect(dsn) as consumer:
                    result = ingest_render_artifact(
                        PgBridge(consumer),
                        write_artifact(tmp_path, payload),
                        expected_run_id=SOURCE["run_id"],
                        expected_sha=SOURCE["sha"],
                        expected_run_attempt="1",
                    )
                    consumer.commit()
                    assert result["reused"] is True and result["render_captures"] == 0
                    assert result["observed_at"] == first["observed_at"]
                    assert state(consumer) == committed
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_expired_committed_receipt_replay_never_refreshes_observation(db):
    payload = health(db)
    capture(db, payload)
    # Model time elapsed since the committed receipt, without a five-minute
    # sleep or altering the server clock. This fixture contains the exact old
    # immutable artifact and its corresponding receipt fingerprint.
    historical = health(db, age=360)
    stamp = historical["render"]["last_health_check"]
    db.execute(
        """UPDATE public.dufynd_master_status SET value=value||jsonb_build_object(
      'observed_at',%s::timestamptz,'captured_at',%s::timestamptz,'evidence_sha256',encode(sha256(convert_to(
      jsonb_build_object('source',%s::jsonb,'health',%s::jsonb,'evidence',%s::jsonb)::text,'UTF8')),'hex')),
      last_verified_at=%s::timestamptz WHERE key=%s""",
        (
            stamp,
            stamp,
            json.dumps(SOURCE),
            json.dumps(historical),
            json.dumps([DEPLOY]),
            stamp,
            KEY,
        ),
    )
    db.execute(
        "UPDATE public.dufynd_external_observers SET last_success_at=%s,last_attempt_at=%s,health_status='stale' WHERE observer_id=%s",
        (stamp, stamp, API),
    )
    before = state(db)
    result = capture(db, historical)
    assert result["accepted"] and result["reused"] and result["render_captures"] == 0
    assert state(db) == before
    assert observer(db)["health_status"] == "stale"


@pytest.mark.parametrize("changed", ["sha", "evidence", "observation_time", "gmail_health"])
def test_same_run_attempt_changed_artifact_conflicts_atomically(db, changed):
    payload = health(db)
    capture(db, payload)
    before = state(db)
    source, evidence = dict(SOURCE), [dict(DEPLOY)]
    if changed == "sha":
        source["sha"] = "c" * 40
    elif changed == "evidence":
        evidence[0]["commit_sha"] = "c" * 40
    elif changed == "observation_time":
        payload = health(db, age=20)
    else:
        payload["gmail"]["health_reason"] = "invalid_grant"
    assert capture(db, payload, source=source, evidence=evidence) == {
        "accepted": False,
        "reason": "render_receipt_conflict",
    }
    assert state(db) == before


def test_newer_attempt_requires_same_source_and_new_real_observation(db):
    old = health(db, age=40)
    capture(db, old)
    before = state(db)
    attempt2 = {**SOURCE, "run_attempt": "2"}
    assert capture(db, old, source=attempt2)["reason"] == "superseded_render_observation"
    assert (
        capture(db, health(db, age=30), source={**attempt2, "sha": "c" * 40})["reason"]
        == "render_receipt_conflict"
    )
    assert state(db) == before
    newer = capture(db, health(db, age=20), source=attempt2)
    assert newer["accepted"] and not newer["reused"]
    before = state(db)
    assert (
        capture(db, health(db, age=10), source=SOURCE)["reason"] == "superseded_render_observation"
    )
    assert state(db) == before


def test_later_run_supersedes_older_run_even_when_relabelled_with_fresh_time(db):
    old = health(db, age=40)
    capture(db, old)
    capture(db, health(db, age=30), source={**SOURCE, "run_id": "123456790"})
    before = state(db)
    assert capture(db, old)["reason"] == "superseded_render_observation"
    assert (
        capture(db, health(db, age=10), source={**SOURCE, "run_attempt": "2"})["reason"]
        == "superseded_render_observation"
    )
    assert state(db) == before


@pytest.mark.parametrize("age", [301, -1])
@pytest.mark.parametrize("provider", ["render", "gmail"])
def test_expired_or_future_health_never_projects_or_captures(db, age, provider):
    payload = health(db)
    payload[provider]["last_health_check"] = health(db, age=age)[provider]["last_health_check"]
    before = state(db)
    assert capture(db, payload)["reason"] == "stale_render_observation"
    assert state(db) == before


@pytest.mark.parametrize(
    "value",
    [
        None,
        "infinity",
        "-infinity",
        "2026-10-29T10:00:00+99:99",
        "2026-02-30T10:00:00Z",
        "2026-10-29 10:00:00",
        123,
    ],
)
def test_invalid_health_timestamp_fails_before_mutation(db, value):
    import psycopg

    payload = health(db)
    payload["render"]["last_health_check"] = value
    before = state(db)
    with (
        pytest.raises(psycopg.errors.RaiseException, match="invalid broker health timestamp"),
        db.transaction(),
    ):
        capture(db, payload)
    assert state(db) == before


@pytest.mark.parametrize(
    "mutation", ["disabled", "unactivated", "foreign_observer", "missing_observer"]
)
def test_existing_activation_and_observer_identity_are_still_required(db, mutation):
    if mutation == "disabled":
        db.execute(
            "UPDATE public.dufynd_external_observers SET enabled=false WHERE observer_id=%s", (API,)
        )
    elif mutation == "unactivated":
        db.execute(
            "UPDATE public.dufynd_observer_credentials SET activation_enabled=false WHERE provider='render'"
        )
    elif mutation == "foreign_observer":
        db.execute(
            "UPDATE public.dufynd_external_observers SET source_id='srv-foreign' WHERE observer_id=%s",
            (API,),
        )
    else:
        db.execute("DELETE FROM public.dufynd_external_observers WHERE observer_id=%s", (API,))
    before = state(db)
    assert capture(db)["reason"] == "blocked_configuration"
    assert state(db) == before


@pytest.mark.parametrize(
    "change",
    [
        {"version": True},
        {"repository": "other/repo"},
        {"repository_id": 1367576041},
        {"repository_owner_id": "999"},
        {"ref": "refs/heads/main"},
        {
            "workflow_ref": "tncommerce/commerce-agents/.github/workflows/ci.yml@refs/heads/scentai-mvp"
        },
        {"event_name": "pull_request"},
        {"sha": "invalid"},
        {"run_id": "0"},
        {"run_attempt": "0"},
        {"extra": "must-not-be-stored"},
    ],
)
def test_server_side_provenance_rejects_before_projection(db, change):
    before = state(db)
    assert capture(db, source={**SOURCE, **change}) == {
        "accepted": False,
        "reason": "invalid_render_source",
    }
    assert state(db) == before


@pytest.mark.parametrize(
    "mutation", ["foreign_service", "empty", "extra_field", "wrong_sha_type", "bad_timestamp"]
)
def test_server_rejects_unbounded_or_foreign_evidence(db, mutation):
    import psycopg

    evidence = copy.deepcopy([DEPLOY])
    if mutation == "foreign_service":
        evidence[0]["service_id"] = "srv-dakpiajl550s73cp4lvg"
    elif mutation == "empty":
        evidence = []
    elif mutation == "extra_field":
        evidence[0]["credential"] = "must-not-pass"
    elif mutation == "wrong_sha_type":
        evidence[0]["commit_sha"] = 123
    else:
        evidence[0]["timestamps"]["createdAt"] = "infinity"
    before = state(db)
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        capture(db, evidence=evidence)
    assert state(db) == before


def test_health_projection_rolls_back_when_existing_capture_rejects(db):
    import psycopg

    payload = health(db)
    payload["render"]["status"] = "revoked"
    payload["render"]["health_reason"] = "revoked"
    payload["render"]["revoked_at"] = payload["render"]["last_health_check"]
    before = state(db)
    with (
        pytest.raises(psycopg.errors.RaiseException, match="render capture rejected"),
        db.transaction(),
    ):
        capture(db, payload)
    assert state(db) == before


def test_render_projection_rolls_back_when_gmail_metadata_contract_rejects(db):
    import psycopg

    payload = health(db)
    payload["gmail"]["allowed_resources"] = []
    before = state(db)
    with pytest.raises(psycopg.errors.RaiseException, match="contract mismatch"), db.transaction():
        capture(db, payload)
    assert state(db) == before


def test_earlier_actual_observation_cannot_overwrite_later_existing_capture(db):
    payload = health(db, age=40)
    db.execute(
        "UPDATE public.dufynd_external_observers SET last_success_at=clock_timestamp()-interval '20 seconds' WHERE observer_id=%s",
        (API,),
    )
    before = state(db)
    assert capture(db, payload)["reason"] == "superseded_render_observation"
    assert state(db) == before


def test_old_rpc_reproduces_ingest_time_freshness_while_new_one_retains_provider_time(db):
    payload = health(db, age=120)
    db.execute("SELECT public.project_dufynd_broker_health(%s::jsonb)", (json.dumps(payload),))
    db.execute(
        "SELECT public.capture_dufynd_broker_observation('render_deploy_broker',%s,%s::jsonb)",
        (API, json.dumps([DEPLOY])),
    )
    assert db.execute(
        "SELECT last_success_at=now() AND last_success_at>%s::timestamptz FROM public.dufynd_external_observers WHERE observer_id=%s",
        (payload["render"]["last_health_check"], API),
    ).fetchone()[0]
    db.execute(
        "UPDATE public.dufynd_external_observers SET last_success_at=now()-interval '2 hours' WHERE observer_id=%s",
        (API,),
    )
    result = capture(db, payload)
    assert result["accepted"]
    assert db.execute(
        "SELECT last_success_at=%s::timestamptz FROM public.dufynd_external_observers WHERE observer_id=%s",
        (payload["render"]["last_health_check"], API),
    ).fetchone()[0]


def test_python_wrong_attempt_is_rejected_without_any_sql_call(db, tmp_path):
    bridge = PgBridge(db)
    before = state(db)
    with pytest.raises(ArtifactError, match="provenance"):
        ingest_render_artifact(
            bridge,
            write_artifact(tmp_path, health(db)),
            expected_run_id=SOURCE["run_id"],
            expected_sha=SOURCE["sha"],
            expected_run_attempt="2",
        )
    assert bridge.calls == [] and state(db) == before


def test_function_acl_and_migration_install_do_not_activate_or_seed_receipts(db):
    before = state(db)
    db.execute(MIGRATION.read_text())
    assert state(db) == before and before["receipt"] is None
    oid = "public.capture_dufynd_render_observer_read_v1(jsonb,jsonb,jsonb)"
    row = db.execute(
        "SELECT prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure", (oid,)
    ).fetchone()
    assert row == (False, ["search_path=public"])
    assert db.execute(
        "SELECT has_function_privilege('service_role',%s,'EXECUTE')", (oid,)
    ).fetchone()[0]
    for role in ("anon", "authenticated"):
        assert not db.execute(
            "SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, oid)
        ).fetchone()[0]
