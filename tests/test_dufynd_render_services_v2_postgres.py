"""Real per-service Render transactions, permissions and normal health cycles."""

from __future__ import annotations

import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from tests.test_dufynd_github_observer_receipt_postgres import function_sql
from tests.test_dufynd_render_observer_recovery import DEPLOY, SOURCE
from tests.test_dufynd_render_only_capture_postgres import (
    capture as capture_v1,
)
from tests.test_dufynd_render_only_capture_postgres import (
    capture_database,
)
from tests.test_dufynd_render_only_capture_postgres import (
    health as health_v1,
)

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "supabase/migrations"
MIGRATION = next(SQL.glob("*_dufynd_render_services_v2_capture.sql"))
ROLLBACK = ROOT / "release/dufynd-render-services-v2-20261029/rollback.sql"
POLL = SQL / "20261029115545_dufynd_scheduler_delivery_diagnostics.sql"
RELEASE = SQL / "20261029095417_dufynd_service_release_expectations.sql"
EVENTS = SQL / "20261002094028_dufynd_supervisor_v2_external_events.sql"
API = "srv-dakpfrnf3r2c73dr3f20"
STORE = "srv-dakpiajl550s73cp4lvg"
SERVICES = (API, STORE)
PREFIX = "ops.private_observer.render_capture_v2."
RECEIPT_KEYS = {
    "version",
    "mode",
    "scope_id",
    "source",
    "service_id",
    "observer_id",
    "observed_at",
    "captured_at",
    "evidence_sha256",
    "accepted",
    "reused",
    "render_captures",
    "gmail_captures",
    "acks",
    "activation_changed",
    "business_success",
    "full_chain_complete",
}


def install(db):
    db.execute(function_sql(POLL, "poll_dufynd_observers"))
    db.execute("""CREATE TEMP TABLE multiservice_poller_before AS
      SELECT prosrc,proowner,proacl,prosecdef,provolatile,proconfig FROM pg_proc
      WHERE oid='public.poll_dufynd_observers()'::regprocedure""")
    db.execute(MIGRATION.read_text())


@contextmanager
def database(dsn):
    with capture_database(dsn) as connection:
        install(connection)
        yield connection


@pytest.fixture
def db():
    with database(DSN) as connection:
        yield connection


def seed(db, services=SERVICES):
    """Owner-reviewed scope activation is fixture-only, never migration DML."""
    for service in services:
        db.execute(
            """INSERT INTO public.dufynd_external_observers
            (observer_id,source_type,source_id,enabled,interval_seconds,health_status,
             last_success_at,last_attempt_at,last_snapshot)
            VALUES(%s,'render',%s,true,120,'stale',clock_timestamp()-interval '2 hours',
              clock_timestamp()-interval '2 hours','{"retained":true}')
            ON CONFLICT(observer_id) DO NOTHING""",
            ("render:" + service, service),
        )
        db.execute(
            """UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=true,
            runtime_source_sha=%s,runtime_image_digest=%s,verified_at=clock_timestamp()-interval '1 hour'
            WHERE service_id=%s""",
            (SOURCE["sha"], "sha256:" + "4" * 64, service),
        )


def observation(db, service=API, *, age=30, status="live"):
    stamp = db.execute("SELECT clock_timestamp()").fetchone()[0] - timedelta(seconds=age)
    deploy = copy.deepcopy(DEPLOY)
    deploy.update(
        service_id=service,
        deployment_id="dep-api" if service == API else "dep-storefront",
        status=status,
    )
    return {
        "version": 2,
        "scope_id": "render_services_v2",
        "service_id": service,
        "observed_at": stamp.isoformat(),
        "deployments": [deploy],
    }


def capture(db, value, source=None):
    return db.execute(
        "SELECT public.capture_dufynd_render_service_read_v2(%s::jsonb,%s::jsonb)",
        (json.dumps(SOURCE if source is None else source), json.dumps(value)),
    ).fetchone()[0]


def state(db):
    return db.execute("""SELECT jsonb_build_object(
      'observers',(SELECT jsonb_agg(to_jsonb(o) ORDER BY observer_id) FROM public.dufynd_external_observers o),
      'credentials',(SELECT jsonb_agg(to_jsonb(c) ORDER BY credential_id) FROM public.dufynd_observer_credentials c),
      'scopes',(SELECT jsonb_agg(to_jsonb(s) ORDER BY service_id) FROM public.dufynd_render_observer_scopes_v2 s),
      'receipts',(SELECT jsonb_agg(to_jsonb(m) ORDER BY key) FROM public.dufynd_master_status m
        WHERE key LIKE 'ops.private_observer.render_capture_v2.%'),
      'legacy',(SELECT to_jsonb(m) FROM public.dufynd_master_status m WHERE key='ops.private_observer.render_capture_v1'),
      'pause',(SELECT to_jsonb(m) FROM public.dufynd_master_status m WHERE key='jarvis.private_observer_scheduler_v1'),
      'sessions',(SELECT jsonb_agg(to_jsonb(s)) FROM public.dufynd_broker_acceptance_sessions s),
      'events',(SELECT count(*) FROM public.dufynd_jarvis_inbox))""").fetchone()[0]


def observer(db, service):
    return db.execute(
        "SELECT to_jsonb(o) FROM public.dufynd_external_observers o WHERE observer_id=%s",
        ("render:" + service,),
    ).fetchone()[0]


def test_install_is_disabled_private_and_preserves_existing_poller_attributes(db):
    rows = db.execute(
        "SELECT service_id,enabled,verified_at FROM public.dufynd_render_observer_scopes_v2 ORDER BY service_id"
    ).fetchall()
    assert rows == [(API, False, None), (STORE, False, None)]
    assert state(db)["receipts"] is None
    assert (
        db.execute(
            "SELECT count(*) FROM public.dufynd_external_observers WHERE source_id=%s", (STORE,)
        ).fetchone()[0]
        == 0
    )
    before, after = db.execute("""SELECT to_jsonb(b),to_jsonb(p) FROM multiservice_poller_before b,
      LATERAL (SELECT prosrc,proowner,proacl,prosecdef,provolatile,proconfig FROM pg_proc
       WHERE oid='public.poll_dufynd_observers()'::regprocedure) p""").fetchone()
    assert {k: v for k, v in before.items() if k != "prosrc"} == {
        k: v for k, v in after.items() if k != "prosrc"
    }
    assert (
        after["prosrc"].replace(
            "\n perform public.refresh_dufynd_render_service_health_v2();", "", 1
        )
        == before["prosrc"]
    )
    for role in ("anon", "authenticated", "service_role"):
        privileges = db.execute(
            """SELECT has_table_privilege(%s,'public.dufynd_render_observer_scopes_v2','SELECT'),
          has_table_privilege(%s,'public.dufynd_render_observer_scopes_v2','INSERT,UPDATE,DELETE,TRUNCATE')""",
            (role, role),
        ).fetchone()
        assert privileges == (role == "service_role", False)
    for name in (
        "dufynd_render_source_valid_v2(jsonb)",
        "capture_dufynd_render_service_read_v2(jsonb,jsonb)",
        "refresh_dufynd_render_service_health_v2()",
    ):
        assert db.execute(
            "SELECT prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure",
            ("public." + name,),
        ).fetchone() == (False, ["search_path=pg_catalog, public"])
        for role in ("anon", "authenticated", "service_role"):
            assert db.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, "public." + name)
            ).fetchone()[0] is (role == "service_role")


def test_scope_requires_explicit_proof_and_cannot_be_enabled_by_workflow_role(db):
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(
            "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=true WHERE service_id=%s",
            (STORE,),
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute("SET LOCAL ROLE service_role")
        db.execute(
            "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=true WHERE service_id=%s",
            (STORE,),
        )
    assert not any(
        x[0]
        for x in db.execute(
            "SELECT enabled FROM public.dufynd_render_observer_scopes_v2"
        ).fetchall()
    )


def test_same_run_attempt_captures_both_services_without_cross_freshening(db):
    seed(db)
    initial = state(db)
    api, storefront = observation(db, API, age=80), observation(db, STORE, age=20)
    r1 = capture(db, api)
    api_after = observer(db, API)
    assert (
        observer(db, STORE)["last_success_at"]
        == next(x for x in initial["observers"] if x["source_id"] == STORE)["last_success_at"]
    )
    r2 = capture(db, storefront)
    assert observer(db, API) == api_after
    for service, expected, receipt in ((API, api, r1), (STORE, storefront, r2)):
        assert set(receipt) == RECEIPT_KEYS
        assert receipt["accepted"] and not receipt["reused"] and receipt["render_captures"] == 1
        assert receipt["gmail_captures"] == receipt["acks"] == 0
        assert not any(
            receipt[k] for k in ("activation_changed", "business_success", "full_chain_complete")
        )
        assert receipt["source"] == SOURCE and receipt["scope_id"] == "render_services_v2"
        assert receipt["observer_id"] == "render:" + service
        assert datetime.fromisoformat(receipt["observed_at"]) == datetime.fromisoformat(
            expected["observed_at"]
        )
        assert observer(db, service)["last_success_at"] == receipt["observed_at"]
    final = state(db)
    assert len(final["receipts"]) == 2
    for name in ("credentials", "pause", "sessions", "scopes", "legacy"):
        assert final[name] == initial[name]


def test_exact_retry_does_not_change_any_durable_state(db):
    seed(db)
    payload = observation(db, STORE)
    first = capture(db, payload)
    before = state(db)
    assert capture(db, payload) == {**first, "reused": True, "render_captures": 0}
    assert state(db) == before


def test_old_committed_retry_is_acknowledged_without_refresh(db):
    seed(db)
    payload = observation(db, STORE)
    first = capture(db, payload)
    old_stamp = (datetime.fromisoformat(payload["observed_at"]) - timedelta(hours=2)).isoformat()
    payload["observed_at"] = old_stamp
    first["observed_at"] = old_stamp
    first["captured_at"] = (datetime.fromisoformat(old_stamp) + timedelta(seconds=10)).isoformat()
    first["evidence_sha256"] = db.execute(
        "SELECT encode(sha256(convert_to(jsonb_build_object('source',%s::jsonb,'observation',%s::jsonb)::text,'UTF8')),'hex')",
        (json.dumps(SOURCE), json.dumps(payload)),
    ).fetchone()[0]
    db.execute(
        "UPDATE public.dufynd_master_status SET value=%s::jsonb,last_verified_at=%s WHERE key=%s",
        (json.dumps(first), first["captured_at"], PREFIX + STORE),
    )
    db.execute(
        "UPDATE public.dufynd_external_observers SET last_success_at=%s,last_attempt_at=%s,health_status='stale' WHERE observer_id=%s",
        (old_stamp, old_stamp, "render:" + STORE),
    )
    before = state(db)
    result = capture(db, payload)
    assert result == {**first, "reused": True, "render_captures": 0}
    assert state(db) == before


@pytest.mark.parametrize(
    "change",
    [
        {"version": True},
        {"repository": "foreign/repo"},
        {"repository_id": "1"},
        {"repository_owner_id": "2"},
        {"ref": "refs/heads/main"},
        {"workflow_ref": "wrong"},
        {"event_name": "pull_request"},
        {"sha": "x" * 40},
        {"sha": 17},
        {"run_id": "0"},
        {"run_id": "01"},
        {"run_id": "9" * 21},
        {"run_attempt": "0"},
        {"run_attempt": 1},
        {"credential": "excluded"},
    ],
)
def test_wrong_provenance_has_no_effect(db, change):
    seed(db)
    before = state(db)
    assert capture(db, observation(db), {**SOURCE, **change}) == {
        "accepted": False,
        "reason": "invalid_render_source",
    }
    assert state(db) == before


@pytest.mark.parametrize("value", [None, [], "scalar", True])
def test_nonobject_source_is_bounded_rejection(db, value):
    assert (
        db.execute(
            "SELECT public.dufynd_render_source_valid_v2(%s::jsonb)", (json.dumps(value),)
        ).fetchone()[0]
        is False
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "foreign_service",
        "wrong_scope",
        "bool_version",
        "v1_version",
        "empty_deployments",
        "too_many",
        "mixed_service",
        "deploy_extra",
        "deploy_missing",
        "wrong_sha",
        "unknown_status",
        "bad_timestamp",
        "bad_offset",
        "naive_time",
        "observed_infinity",
        "observed_non_string",
        "timestamp_extra",
        "duplicate_deployments",
        "oversized",
    ],
)
def test_bad_service_envelope_is_rejected_before_durable_changes(db, mutation):
    seed(db)
    p = observation(db)
    d = p["deployments"][0]
    if mutation == "extra":
        p["health"] = {}
    elif mutation == "missing":
        del p["scope_id"]
    elif mutation == "foreign_service":
        p["service_id"] = "srv-foreign"
    elif mutation == "wrong_scope":
        p["scope_id"] = "render_deploy_broker"
    elif mutation == "bool_version":
        p["version"] = True
    elif mutation == "v1_version":
        p["version"] = 1
    elif mutation == "empty_deployments":
        p["deployments"] = []
    elif mutation == "too_many":
        p["deployments"] = [d] * 21
    elif mutation == "mixed_service":
        d["service_id"] = STORE
    elif mutation == "deploy_extra":
        d["secret"] = "excluded"
    elif mutation == "deploy_missing":
        del d["commit_sha"]
    elif mutation == "wrong_sha":
        d["commit_sha"] = 4
    elif mutation == "unknown_status":
        d["status"] = "success"
    elif mutation == "bad_timestamp":
        d["timestamps"]["createdAt"] = "2026-02-31T01:00:00Z"
    elif mutation == "bad_offset":
        p["observed_at"] = "2026-10-29T01:00:00+25:00"
    elif mutation == "naive_time":
        p["observed_at"] = "2026-10-29T01:00:00"
    elif mutation == "observed_infinity":
        p["observed_at"] = "infinity"
    elif mutation == "observed_non_string":
        p["observed_at"] = 17
    elif mutation == "timestamp_extra":
        d["timestamps"]["secret"] = None
    elif mutation == "duplicate_deployments":
        p["deployments"] = [d, d]
    elif mutation == "oversized":
        d["deployment_id"] = "dep-" + "a" * 66000
    before = state(db)
    assert capture(db, p) == {"accepted": False, "reason": "invalid_render_observation"}
    assert state(db) == before


@pytest.mark.parametrize("value", [None, [], "scalar", True])
def test_nonobject_observation_is_bounded_rejection(db, value):
    assert capture(db, value) == {"accepted": False, "reason": "invalid_render_observation"}


@pytest.mark.parametrize("suffix_length,accepted", [(100, True), (101, False)])
def test_deployment_id_limit_matches_runtime_and_reader(db, suffix_length, accepted):
    seed(db)
    payload = observation(db)
    payload["deployments"][0]["deployment_id"] = "dep-" + "a" * suffix_length
    before = state(db)
    result = capture(db, payload)
    assert result["accepted"] is accepted
    if not accepted:
        assert result["reason"] == "invalid_render_observation"
        assert state(db) == before


@pytest.mark.parametrize("age", [301, -1])
def test_fresh_global_credential_never_makes_stale_or_future_service_evidence_fresh(db, age):
    seed(db)
    db.execute(
        "UPDATE public.dufynd_observer_credentials SET last_health_check=clock_timestamp() WHERE provider='render'"
    )
    before = state(db)
    assert capture(db, observation(db, STORE, age=age))["reason"] == "stale_render_observation"
    assert state(db) == before


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("scope_off", "render_scope_unverified"),
        ("scope_future", "render_scope_unverified"),
        ("observer_off", "blocked_configuration"),
        ("observer_missing", "blocked_configuration"),
        ("credential_off", "blocked_configuration"),
        ("credential_revoked", "blocked_configuration"),
        ("credential_expired", "blocked_configuration"),
        ("credential_status", "blocked_configuration"),
    ],
)
def test_explicit_scope_observer_and_shared_credential_kill_switches(db, mutation, reason):
    seed(db)
    if mutation == "scope_off":
        db.execute(
            "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=false WHERE service_id=%s",
            (STORE,),
        )
    elif mutation == "scope_future":
        db.execute(
            "UPDATE public.dufynd_render_observer_scopes_v2 SET verified_at=clock_timestamp()+interval '1 minute' WHERE service_id=%s",
            (STORE,),
        )
    elif mutation == "observer_off":
        db.execute(
            "UPDATE public.dufynd_external_observers SET enabled=false WHERE source_id=%s", (STORE,)
        )
    elif mutation == "observer_missing":
        db.execute("DELETE FROM public.dufynd_external_observers WHERE source_id=%s", (STORE,))
    elif mutation == "credential_off":
        db.execute(
            "UPDATE public.dufynd_observer_credentials SET activation_enabled=false WHERE provider='render'"
        )
    elif mutation == "credential_revoked":
        db.execute(
            "UPDATE public.dufynd_observer_credentials SET revoked_at=clock_timestamp() WHERE provider='render'"
        )
    elif mutation == "credential_expired":
        db.execute(
            "UPDATE public.dufynd_observer_credentials SET expires_at=clock_timestamp()-interval '1 minute' WHERE provider='render'"
        )
    else:
        db.execute(
            "UPDATE public.dufynd_observer_credentials SET status='refresh_failed' WHERE provider='render'"
        )
    before = state(db)
    assert capture(db, observation(db, STORE))["reason"] == reason
    assert state(db) == before


@pytest.mark.parametrize("change", ["sha", "timestamp", "deployment", "event_name"])
def test_same_attempt_conflicts_cannot_replace_a_committed_receipt(db, change):
    seed(db)
    payload = observation(db)
    assert capture(db, payload)["accepted"]
    source = dict(SOURCE)
    if change == "sha":
        source["sha"] = "b" * 40
    elif change == "event_name":
        source["event_name"] = (
            "schedule" if source["event_name"] != "schedule" else "workflow_dispatch"
        )
    elif change == "timestamp":
        payload["observed_at"] = observation(db, age=10)["observed_at"]
    else:
        payload["deployments"][0]["commit_sha"] = "c" * 40
    before = state(db)
    assert capture(db, payload, source)["reason"] == "render_receipt_conflict"
    assert state(db) == before


def test_attempt_and_run_watermarks_are_independent_for_each_service(db):
    seed(db)
    newer_source = {**SOURCE, "run_id": str(int(SOURCE["run_id"]) + 10), "run_attempt": "2"}
    assert capture(db, observation(db, API, age=60), newer_source)["accepted"]
    assert capture(db, observation(db, STORE, age=90), SOURCE)["accepted"]
    before = state(db)
    assert (
        capture(db, observation(db, API, age=10), SOURCE)["reason"]
        == "superseded_render_observation"
    )
    assert (
        capture(db, observation(db, API, age=10), {**newer_source, "run_attempt": "1"})["reason"]
        == "superseded_render_observation"
    )
    assert state(db) == before
    assert capture(db, observation(db, API, age=20), {**newer_source, "run_attempt": "3"})[
        "accepted"
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("service_id", STORE),
        ("scope_id", "foreign"),
        ("source", {}),
        ("accepted", False),
        ("reused", True),
        ("render_captures", 0),
        ("gmail_captures", 1),
        ("acks", 1),
        ("business_success", True),
        ("observed_at", "infinity"),
        ("evidence_sha256", "bad"),
        ("version", 2.0),
        ("render_captures", 1.0),
        ("gmail_captures", 0.0),
        ("acks", 0.0),
    ],
)
def test_corrupt_previous_receipt_cannot_be_used_or_overwritten(db, field, value):
    seed(db)
    assert capture(db, observation(db))["accepted"]
    db.execute(
        "UPDATE public.dufynd_master_status SET value=jsonb_set(value,ARRAY[%s],%s::jsonb) WHERE key=%s",
        (field, json.dumps(value), PREFIX + API),
    )
    before = state(db)
    assert (
        capture(db, observation(db, age=10), {**SOURCE, "run_id": str(int(SOURCE["run_id"]) + 1)})[
            "reason"
        ]
        == "render_receipt_invalid"
    )
    assert state(db) == before


def test_downstream_capture_exception_rolls_back_receipt_observation_and_events(db):
    import psycopg

    seed(db)
    db.execute("""CREATE FUNCTION pg_temp.reject_render_event() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'fixture downstream event failure'; END $$;
      CREATE TRIGGER reject_render_event BEFORE INSERT ON public.dufynd_jarvis_inbox
      FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_render_event()""")
    before = state(db)
    with (
        pytest.raises(psycopg.errors.RaiseException, match="fixture downstream event failure"),
        db.transaction(),
    ):
        capture(db, observation(db, STORE))
    assert state(db) == before


def install_readers(db):
    for path, names in (
        (RELEASE, ["read_dufynd_render_release_expectations_v1"]),
        (
            SQL / "20261028130335_dufynd_public_api_health_monitor.sql",
            ["read_dufynd_public_api_health_v1"],
        ),
        (
            SQL / "20261029104253_dufynd_public_storefront_health.sql",
            ["read_dufynd_public_storefront_health_v1"],
        ),
        (
            SQL / "20261029115518_dufynd_github_scheduler_delivery_monitor.sql",
            ["dufynd_scheduler_parse_time_v1", "read_dufynd_github_scheduler_delivery_v1"],
        ),
        (POLL, ["read_dufynd_technical_work_blockers_v1"]),
    ):
        for name in names:
            db.execute(function_sql(path, name))
    db.execute(
        """INSERT INTO public.dufynd_external_observers
      (observer_id,source_type,source_id,enabled,health_status,last_success_at,last_snapshot)
      VALUES('github_branch:scentai-mvp','github_branch','scentai-mvp',true,'healthy',clock_timestamp(),%s::jsonb)
      ON CONFLICT(observer_id) DO UPDATE SET enabled=true,health_status='healthy',
      last_success_at=clock_timestamp(),last_snapshot=excluded.last_snapshot""",
        (json.dumps({"sha": SOURCE["sha"]}),),
    )
    contract = {
        "version": 1,
        "repository": "tncommerce/commerce-agents",
        "branch": "scentai-mvp",
        "repository_head_sha": SOURCE["sha"],
        "approval_status": "approved",
        "approved_at": (
            db.execute("SELECT clock_timestamp()").fetchone()[0] - timedelta(minutes=1)
        ).isoformat(),
        "services": [
            {
                "component": "api" if service == API else "storefront",
                "service_id": service,
                "expected_deployment_sha": DEPLOY["commit_sha"],
                "decision": "hold_existing_release",
                "scope": "api_runtime" if service == API else "storefront_static",
                "evidence_ref": "fixture:verified-current-release",
                "rationale": "Explicit local test release evidence.",
            }
            for service in SERVICES
        ],
    }
    db.execute(
        "INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at) VALUES('ops.render_release_expectations_v1','ops',%s::jsonb,100,clock_timestamp()) ON CONFLICT(key) DO UPDATE SET value=excluded.value,last_verified_at=excluded.last_verified_at",
        (json.dumps(contract),),
    )


def poll_without_transport(db):
    # Exercise the actual latest function through its private credential loop.
    # No request may be queued; public hook failures are the real guarded branch.
    db.execute("""DO $fixture$ BEGIN
      IF to_regnamespace('net') IS NULL THEN CREATE SCHEMA net; END IF;
      END $fixture$;
      UPDATE public.dufynd_external_observers SET next_retry_at=clock_timestamp()+interval '1 hour'
      WHERE source_type LIKE 'github_%';""")
    return db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0]


def test_real_next_poller_and_release_reader_preserve_independent_service_times(db):
    seed(db)
    install_readers(db)
    for service, age in ((API, 90), (STORE, 20)):
        assert capture(db, observation(db, service, age=age))["accepted"]
    before_api, before_store = observer(db, API), observer(db, STORE)
    assert poll_without_transport(db) == {"attempted": 0}
    for service, before in ((API, before_api), (STORE, before_store)):
        after = observer(db, service)
        assert after["health_status"] == "healthy"
        assert after["last_success_at"] == before["last_success_at"]
        assert after["last_snapshot"] == before["last_snapshot"]
    projection = db.execute(
        "SELECT public.read_dufynd_render_release_expectations_v1()"
    ).fetchone()[0]
    assert projection["status"] == "verified"
    assert all(
        s["observation_verified"] and s["comparison_status"] == "aligned"
        for s in projection["services"]
    )
    technical = db.execute("SELECT public.read_dufynd_technical_work_blockers_v1()").fetchone()[0]
    assert "render_monitor_missing" not in technical["issues"]
    assert "render_release_observation_unverified" not in technical["issues"]


@pytest.mark.parametrize("operation", ["disable", "delete", "new_proof"])
def test_scope_revocation_immediately_degrades_only_marked_service_without_freshening(
    db, operation
):
    seed(db)
    for service in SERVICES:
        capture(db, observation(db, service))
    before_api, before_store = observer(db, API), observer(db, STORE)
    if operation == "disable":
        db.execute(
            "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=false WHERE service_id=%s",
            (STORE,),
        )
    elif operation == "delete":
        db.execute(
            "DELETE FROM public.dufynd_render_observer_scopes_v2 WHERE service_id=%s", (STORE,)
        )
    else:
        db.execute(
            "UPDATE public.dufynd_render_observer_scopes_v2 SET verified_at=clock_timestamp() WHERE service_id=%s",
            (STORE,),
        )
    after = observer(db, STORE)
    assert after["health_status"] == "blocked_configuration"
    assert after["last_success_at"] == before_store["last_success_at"]
    assert after["last_snapshot"] == before_store["last_snapshot"]
    assert observer(db, API) == before_api
    if operation == "disable":
        db.execute(
            "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=true WHERE service_id=%s",
            (STORE,),
        )
        assert observer(db, STORE)["health_status"] == "blocked_configuration"
        assert poll_without_transport(db) == {"attempted": 0}
        assert observer(db, STORE)["health_status"] == "blocked_configuration"
        assert capture(
            db, observation(db, STORE, age=5), {**SOURCE, "run_id": str(int(SOURCE["run_id"]) + 1)}
        )["accepted"]
        assert observer(db, STORE)["health_status"] == "healthy"


def test_scope_truncate_is_rejected_without_lock_order_inversion_or_state_change(db):
    import psycopg

    seed(db)
    for service in SERVICES:
        assert capture(db, observation(db, service))["accepted"]
    before = state(db)
    with (
        pytest.raises(psycopg.errors.RaiseException, match="cannot be truncated"),
        db.transaction(),
    ):
        db.execute("TRUNCATE public.dufynd_render_observer_scopes_v2")
    assert state(db) == before


def test_actual_poll_marks_old_peer_stale_and_revoked_credential_blocked(db):
    seed(db)
    for service in SERVICES:
        capture(db, observation(db, service))
    db.execute(
        "UPDATE public.dufynd_external_observers SET last_success_at=clock_timestamp()-interval '11 minutes' WHERE source_id=%s",
        (STORE,),
    )
    api_before = observer(db, API)
    poll_without_transport(db)
    assert observer(db, STORE)["health_status"] == "stale"
    assert observer(db, API)["last_success_at"] == api_before["last_success_at"]
    assert observer(db, API)["health_status"] == "healthy"
    db.execute(
        "UPDATE public.dufynd_observer_credentials SET revoked_at=clock_timestamp() WHERE provider='render'"
    )
    poll_without_transport(db)
    assert all(observer(db, s)["health_status"] == "blocked_configuration" for s in SERVICES)
    assert observer(db, API)["last_success_at"] == api_before["last_success_at"]


def test_v1_real_capture_replaces_marker_and_scope_revocation_cannot_block_v1_api(db):
    seed(db)
    capture(db, observation(db, API, age=90))
    capture_v1(db, health_v1(db, age=20))
    old = observer(db, API)
    assert "scope_id" not in old["last_snapshot"]
    db.execute(
        "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=false WHERE service_id=%s",
        (API,),
    )
    poll_without_transport(db)
    assert observer(db, API)["health_status"] == "healthy"
    assert observer(db, API)["last_success_at"] == old["last_success_at"]


def test_v1_and_v2_cannot_overwrite_newer_peer_contract_observation(db):
    seed(db)
    assert capture_v1(db, health_v1(db, age=40))["accepted"]
    before = state(db)
    assert capture(db, observation(db, API, age=60))["reason"] == "superseded_render_observation"
    assert state(db) == before
    assert capture(db, observation(db, API, age=15))["accepted"]
    before = state(db)
    assert (
        capture_v1(
            db, health_v1(db, age=30), source={**SOURCE, "run_id": str(int(SOURCE["run_id"]) + 1)}
        )["reason"]
        == "superseded_render_observation"
    )
    assert state(db) == before


def test_deactivated_read_never_reuses_old_live_snapshot(db):
    seed(db)
    capture(db, observation(db, STORE, age=60))
    assert capture(
        db,
        observation(db, STORE, age=10, status="deactivated"),
        {**SOURCE, "run_id": str(int(SOURCE["run_id"]) + 1)},
    )["accepted"]
    assert observer(db, STORE)["last_snapshot"]["state"] == "deactivated"


def test_successful_service_role_capture_cannot_enable_or_rewrite_scopes(db):
    seed(db)
    db.execute("ALTER ROLE service_role BYPASSRLS")  # mirror Supabase's actual role; rolled back
    db.execute(
        "GRANT SELECT,INSERT,UPDATE ON public.dufynd_external_observers,public.dufynd_jarvis_inbox,public.dufynd_master_status TO service_role"
    )
    db.execute("GRANT SELECT ON public.dufynd_task_external_waits TO service_role")
    before = state(db)
    payload = observation(db, STORE)
    db.execute("SET LOCAL ROLE service_role")
    assert capture(db, payload)["accepted"]
    db.execute("RESET ROLE")
    assert state(db)["scopes"] == before["scopes"]


@contextmanager
def committed_database():
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    name = "dufynd_multiservice_" + uuid4().hex
    params = conninfo_to_dict(DSN)
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            target = make_conninfo(**{**params, "dbname": name})
            with database(target) as producer:
                seed(producer)
                producer.commit()
            yield target
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def test_concurrent_same_attempt_commits_once_and_two_services_do_not_collide():
    import psycopg

    with committed_database() as dsn:
        with psycopg.connect(dsn) as connection:
            payloads = {s: observation(connection, s) for s in SERVICES}

        def execute(service):
            with psycopg.connect(dsn) as connection:
                result = capture(connection, payloads[service])
                connection.commit()
                return result

        with ThreadPoolExecutor(max_workers=3) as workers:
            results = list(workers.map(execute, (API, STORE, API)))
        assert sum(r["render_captures"] for r in results) == 2
        assert sum(r["reused"] for r in results) == 1
        with psycopg.connect(dsn) as connection:
            assert len(state(connection)["receipts"]) == 2


def test_scope_revocation_waits_for_inflight_capture_then_immediately_blocks_it():
    import psycopg

    ready = Event()
    with committed_database() as dsn, psycopg.connect(dsn) as producer:
        assert capture(producer, observation(producer, STORE))["accepted"]

        def revoke():
            with psycopg.connect(dsn) as connection:
                connection.execute("SET statement_timeout='5s'")
                ready.set()
                connection.execute(
                    "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=false WHERE service_id=%s",
                    (STORE,),
                )
                connection.commit()

        with ThreadPoolExecutor(max_workers=1) as worker:
            task = worker.submit(revoke)
            assert ready.wait(timeout=2)
            producer.commit()
            task.result(timeout=5)
        with psycopg.connect(dsn) as connection:
            assert observer(connection, STORE)["health_status"] == "blocked_configuration"
            before = state(connection)
            assert (
                capture(connection, observation(connection, STORE))["reason"]
                == "render_scope_unverified"
            )
            assert state(connection) == before


def test_migration_rejects_poller_drift_without_partial_installation():
    import psycopg

    with capture_database(DSN) as connection:
        original = function_sql(POLL, "poll_dufynd_observers")
        connection.execute(
            original.replace(
                "perform pg_advisory_xact_lock",
                "-- fixture unexpected change\n perform pg_advisory_xact_lock",
                1,
            )
        )
        before = connection.execute(
            "SELECT pg_get_functiondef('public.poll_dufynd_observers()'::regprocedure)"
        ).fetchone()[0]
        with (
            pytest.raises(psycopg.errors.RaiseException, match="baseline mismatch"),
            connection.transaction(),
        ):
            connection.execute(MIGRATION.read_text())
        assert (
            connection.execute(
                "SELECT to_regclass('public.dufynd_render_observer_scopes_v2')"
            ).fetchone()[0]
            is None
        )
        assert (
            connection.execute(
                "SELECT pg_get_functiondef('public.poll_dufynd_observers()'::regprocedure)"
            ).fetchone()[0]
            == before
        )


def test_guarded_operational_rollback_preserves_audit_and_v1_continuity():
    import psycopg

    with committed_database() as dsn, psycopg.connect(dsn) as connection:
        for service in SERVICES:
            assert capture(connection, observation(connection, service, age=60))["accepted"]
        assert capture_v1(connection, health_v1(connection, age=20))["accepted"]
        connection.execute(
            "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=false WHERE enabled"
        )
        before = state(connection)
        attributes = connection.execute(
            "SELECT proowner,proacl,prosecdef,provolatile,proconfig FROM pg_proc WHERE oid='public.poll_dufynd_observers()'::regprocedure"
        ).fetchone()
        connection.commit()
        connection.execute(ROLLBACK.read_text())
        assert state(connection) == before
        assert (
            connection.execute(
                "SELECT md5(prosrc) FROM pg_proc WHERE oid='public.poll_dufynd_observers()'::regprocedure"
            ).fetchone()[0]
            == "c07e9e3bd5233031014209b8526f1348"
        )
        assert (
            connection.execute(
                "SELECT proowner,proacl,prosecdef,provolatile,proconfig FROM pg_proc WHERE oid='public.poll_dufynd_observers()'::regprocedure"
            ).fetchone()
            == attributes
        )
        assert (
            connection.execute(
                "SELECT has_function_privilege('service_role','public.capture_dufynd_render_service_read_v2(jsonb,jsonb)','EXECUTE')"
            ).fetchone()[0]
            is False
        )
        assert observer(connection, STORE)["health_status"] == "blocked_configuration"
        assert observer(connection, API)["health_status"] == "healthy"
        assert capture_v1(
            connection,
            health_v1(connection, age=5),
            source={**SOURCE, "run_id": str(int(SOURCE["run_id"]) + 1)},
        )["accepted"]


@pytest.mark.parametrize("conflict", ["active_scope", "poller_drift", "unreconciled_observer"])
def test_rollback_guard_failure_leaves_existing_code_permissions_and_history_intact(conflict):
    import psycopg

    with committed_database() as dsn, psycopg.connect(dsn) as connection:
        assert capture(connection, observation(connection, STORE))["accepted"]
        if conflict != "active_scope":
            connection.execute(
                "UPDATE public.dufynd_render_observer_scopes_v2 SET enabled=false WHERE enabled"
            )
        if conflict == "poller_drift":
            definition = connection.execute(
                "SELECT pg_get_functiondef('public.poll_dufynd_observers()'::regprocedure)"
            ).fetchone()[0]
            connection.execute(
                definition.replace(
                    "perform public.refresh_dufynd_render_service_health_v2();",
                    "perform public.refresh_dufynd_render_service_health_v2();\n -- fixture drift",
                    1,
                )
            )
        if conflict == "unreconciled_observer":
            connection.execute(
                "UPDATE public.dufynd_external_observers SET health_status='healthy' WHERE source_id=%s",
                (STORE,),
            )
        before = state(connection)
        definition = connection.execute(
            "SELECT pg_get_functiondef('public.poll_dufynd_observers()'::regprocedure)"
        ).fetchone()[0]
        connection.commit()
        with pytest.raises(psycopg.errors.RaiseException, match="rollback"):
            connection.execute(ROLLBACK.read_text())
        connection.rollback()
        assert state(connection) == before
        assert (
            connection.execute(
                "SELECT pg_get_functiondef('public.poll_dufynd_observers()'::regprocedure)"
            ).fetchone()[0]
            == definition
        )
        assert (
            connection.execute(
                "SELECT has_function_privilege('service_role','public.capture_dufynd_render_service_read_v2(jsonb,jsonb)','EXECUTE')"
            ).fetchone()[0]
            is True
        )
