"""Actual scheduler source feeds existing reader/planner/audit; no live requests."""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path

import pytest
from tests.test_dufynd_planner_technical_blockers_postgres import (
    db as planner_database,  # noqa: F401
)
from tests.test_dufynd_public_health_integration_postgres import (
    db as public_database,  # noqa: F401
)
from tests.test_dufynd_service_release_expectations_postgres import (
    db as release_database,  # noqa: F401
)

from tests import test_dufynd_github_scheduler_delivery_postgres as scheduler
from tests import test_dufynd_service_release_expectations_postgres as releases

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase/migrations"
CORE = MIGRATIONS / "20261029115518_dufynd_github_scheduler_delivery_monitor.sql"
MIGRATION = MIGRATIONS / "20261029115545_dufynd_scheduler_delivery_diagnostics.sql"
STOREFRONT = MIGRATIONS / "20261029104253_dufynd_public_storefront_health.sql"
SSR_FIX = MIGRATIONS / "20261029111936_dufynd_storefront_ssr_block_boundaries.sql"
KEY = "ops.github_scheduler_delivery_v1"
pytestmark = pytest.mark.skipif(
    not os.getenv("DUFYND_TEST_DATABASE_URL"), reason="dedicated disposable PostgreSQL required"
)


@pytest.fixture
def db(request):
    connection = request.getfixturevalue("public_database")
    connection.execute("""
        DO $fixture$ BEGIN
          IF to_regnamespace('dufynd_scheduler_integration_original_net') IS NOT NULL THEN
            RAISE EXCEPTION 'scheduler integration fixture namespace already exists';
          END IF;
          IF to_regnamespace('net') IS NOT NULL THEN
            ALTER SCHEMA net RENAME TO dufynd_scheduler_integration_original_net;
          END IF;
        END $fixture$;
        CREATE SCHEMA net;
        CREATE TABLE net.http_request_queue(
          id bigserial PRIMARY KEY,url text,params jsonb,headers jsonb,timeout_milliseconds integer);
        CREATE TABLE net._http_response(
          id bigint,status_code integer,content_type text,content text,headers jsonb,
          timed_out boolean,error_msg text,created timestamptz);
        CREATE FUNCTION net.http_get(url text,params jsonb DEFAULT '{}',
          headers jsonb DEFAULT '{}',timeout_milliseconds integer DEFAULT 5000)
        RETURNS bigint LANGUAGE sql AS $fixture$
          INSERT INTO net.http_request_queue(url,params,headers,timeout_milliseconds)
          VALUES(url,params,headers,timeout_milliseconds) RETURNING id
        $fixture$;
        ALTER TABLE public.dufynd_external_observers
          ADD COLUMN IF NOT EXISTS config jsonb,
          ADD COLUMN IF NOT EXISTS last_attempt_at timestamptz,
          ADD COLUMN IF NOT EXISTS last_cursor text,
          ADD COLUMN IF NOT EXISTS last_event_at timestamptz,
          ADD COLUMN IF NOT EXISTS consecutive_failures integer DEFAULT 0,
          ADD COLUMN IF NOT EXISTS last_error text,
          ADD COLUMN IF NOT EXISTS etag text,
          ADD COLUMN IF NOT EXISTS page_token text,
          ADD COLUMN IF NOT EXISTS request_id bigint,
          ADD COLUMN IF NOT EXISTS request_started_at timestamptz,
          ADD COLUMN IF NOT EXISTS request_kind text,
          ADD COLUMN IF NOT EXISTS pending_cursor text,
          ADD COLUMN IF NOT EXISTS pending_page_token text;
        UPDATE public.dufynd_external_observers SET request_id=NULL,request_started_at=NULL;
        ALTER TABLE public.dufynd_master_status ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.dufynd_master_status FROM PUBLIC,anon,authenticated;
        GRANT SELECT,INSERT,UPDATE ON public.dufynd_master_status TO service_role;
    """)
    connection.execute(STOREFRONT.read_text())
    connection.execute(SSR_FIX.read_text())
    connection.execute(CORE.read_text())
    old_audit = connection.execute(
        "SELECT pg_get_functiondef('public.audit_dufynd_integrity_v1()'::regprocedure)"
    ).fetchone()[0]
    connection.execute(
        old_audit.replace(
            "public.audit_dufynd_integrity_v1(",
            "public.audit_dufynd_integrity_before_scheduler_source(",
            1,
        )
    )
    connection.execute("""
        CREATE TEMP TABLE scheduler_integration_before AS
        SELECT oid,proname,prosrc,proowner,proacl,prosecdef,provolatile,proconfig
        FROM pg_proc WHERE oid IN (
          'public.poll_dufynd_observers()'::regprocedure,
          'public.read_dufynd_technical_work_blockers_v1()'::regprocedure,
          'public.plan_dufynd_free_work_v1()'::regprocedure,
          'public.audit_dufynd_integrity_v1()'::regprocedure);
    """)
    connection.execute(MIGRATION.read_text())
    yield connection


def read_scheduler(db):
    return db.execute("SELECT public.read_dufynd_github_scheduler_delivery_v1()").fetchone()[0]


def protected_state(db):
    return db.execute("""SELECT
      (SELECT jsonb_agg(to_jsonb(o) ORDER BY observer_id) FROM public.dufynd_external_observers o),
      (SELECT jsonb_agg(to_jsonb(a) ORDER BY run_id) FROM public.dufynd_broker_acceptance_sessions a),
      (SELECT jsonb_agg(to_jsonb(t) ORDER BY task_id) FROM public.dufynd_autonomy_tasks t),
      (SELECT to_jsonb(m) FROM public.dufynd_master_status m WHERE key='ops.render_release_expectations_v1')
    """).fetchone()


def old_audit(db):
    return db.execute("SELECT public.audit_dufynd_integrity_before_scheduler_source()").fetchone()[
        0
    ]


@pytest.mark.parametrize("missing", [False, True])
def test_disabled_or_missing_source_is_diagnostic_without_tasks_or_requests(db, missing):
    if missing:
        db.execute("DELETE FROM public.dufynd_master_status WHERE key=%s", (KEY,))
    before = protected_state(db)
    source = read_scheduler(db)
    assert source["healthy"] is False and source["delivery_gap"] is None
    technical = releases.technical(db)
    assert technical["issues"] == ["github_scheduler_observation_unavailable"]
    assert technical["private_technical_work_remaining"] is True
    planned = releases.plan(db)
    assert planned["state"] == "technical_remediation_required"
    assert planned["action"] == "diagnose_private_scheduler_delivery"
    assert planned["technical_repair_executed"] is False and planned["new_spend_usd"] == 0
    assert planned["exhaustion"]["safe_internal_work_exhausted"] is False
    audit = releases.audit(db)
    assert audit["private_broker_scheduler_gap"] is None
    assert audit["private_broker_scheduler_observation_status"] == "unknown"
    assert "github_scheduler_observation_unavailable" in audit["issues"]
    assert "private_broker_scheduler_gap" not in audit["issues"]
    assert audit["technical_diagnosis_current"] is True and audit["planner_starved"] is False
    assert protected_state(db) == before
    assert db.execute("SELECT count(*) FROM net.http_request_queue").fetchone()[0] == 0


def test_old_acceptance_is_not_a_proven_scheduler_gap_without_source(db):
    db.execute(
        "UPDATE public.dufynd_broker_acceptance_sessions SET created_at=now()-interval '1 hour',"
        "finalized_at=now()-interval '59 minutes' WHERE recurring_read"
    )
    assert old_audit(db)["private_broker_scheduler_gap"] is True
    result = releases.audit(db)
    assert result["private_broker_acceptance_gap"] is True
    assert result["private_broker_scheduler_gap"] is None
    assert "private_broker_acceptance_gap" in result["issues"]
    assert "github_scheduler_observation_unavailable" in result["issues"]
    assert "private_broker_scheduler_gap" not in result["issues"]


@pytest.mark.parametrize("status", ["failed", "capturing", "captured"])
def test_acceptance_start_is_not_reported_as_complete_capture(db, status):
    db.execute(
        "UPDATE public.dufynd_broker_acceptance_sessions SET status=%s WHERE recurring_read",
        (status,),
    )
    assert old_audit(db)["last_private_broker_capture_at"] is not None
    result = releases.audit(db)
    assert result["last_private_broker_acceptance_started_at"] is not None
    assert result["last_private_broker_capture_at"] is None
    assert result["private_broker_acceptance_gap"] is False
    assert result["private_broker_scheduler_gap"] is None
    assert "private_broker_capture_unverified" in result["issues"]


@pytest.mark.parametrize("state", ["work_available", "work_in_progress", "owner_gate"])
def test_existing_real_work_and_owner_gate_still_precede_scheduler_diagnosis(db, state):
    db.execute(
        "UPDATE pg_temp.planner_technical_case SET value=jsonb_set(value,'{state}',%s::jsonb) "
        "WHERE key='get_dufynd_next_autonomous_action'",
        (json.dumps(state),),
    )
    assert releases.plan(db)["state"] == state


@pytest.mark.parametrize(
    "key,action",
    [
        ("ops.public_api_health_v1", "diagnose_public_api_health"),
        ("ops.public_storefront_health_v1", "diagnose_public_storefront_health"),
    ],
)
def test_public_endpoint_failures_keep_priority_over_unknown_scheduler(db, key, action):
    db.execute(
        'UPDATE public.dufynd_master_status SET value=value||\'{"enabled":true,"status":"unhealthy"}\'::jsonb '
        "WHERE key=%s",
        (key,),
    )
    report = releases.plan(db)
    assert report["action"] == action
    assert "github_scheduler_observation_unavailable" in report["technical_work"]["issues"]


def test_stale_scheduler_diagnosis_cannot_hide_actual_starvation(db):
    releases.plan(db)
    db.execute(
        "UPDATE public.dufynd_master_status SET last_verified_at=now()-interval '601 seconds' "
        "WHERE key='jarvis.planner_v1'"
    )
    result = releases.audit(db)
    assert result["technical_diagnosis_current"] is False
    assert result["planner_starved"] is True and "planner_starvation" in result["issues"]


def test_resolved_schedule_issue_cannot_hide_unplanned_business_work(db):
    assert releases.plan(db)["action"] == "diagnose_private_scheduler_delivery"
    assert scheduler.observe_both(db)["healthy"] is True
    db.execute(
        "UPDATE public.dufynd_autonomy_tasks SET status='blocked' "
        "WHERE task_id LIKE 'bizplan:creative-recovery:%'"
    )
    assert releases.technical(db)["technical_work_remaining"] is False
    result = releases.audit(db)
    assert result["technical_diagnosis_current"] is False
    assert result["planner_starved"] is True and "planner_starvation" in result["issues"]


def test_gmail_pause_wrapper_keeps_existing_truth_with_scheduler_diagnosis(db):
    scheduler.observe_both(db)
    releases.test_real_release_audit_and_paused_gmail_wrapper_preserve_unresolved_truth(db)
    assert releases.plan(db)["action"] == "diagnose_private_observer_runtime"
    assert releases.audit(db)["github_scheduler_delivery"]["healthy"] is True


def test_current_observer_body_is_unchanged_except_isolated_scheduler_hook(db):
    previous = db.execute(
        "SELECT prosrc FROM pg_temp.scheduler_integration_before WHERE proname='poll_dufynd_observers'"
    ).fetchone()[0]
    current = db.execute(
        "SELECT prosrc FROM pg_proc WHERE oid='public.poll_dufynd_observers()'::regprocedure"
    ).fetchone()[0]
    addition = "\n begin\n  perform public.poll_dufynd_github_scheduler_delivery_v1();\n exception when others then\n  raise log 'DUFYND GitHub scheduler delivery hook unavailable';\n end;"
    assert current.count(addition) == 1 and current.replace(addition, "", 1) == previous
    db.execute("UPDATE public.dufynd_external_observers SET enabled=false")
    before = protected_state(db)
    assert db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0] == {"attempted": 0}
    assert protected_state(db) == before
    assert db.execute("SELECT count(*) FROM net.http_request_queue").fetchone()[0] == 0


def test_scheduler_exception_is_isolated_from_existing_observer_poll(db):
    db.execute("UPDATE public.dufynd_external_observers SET enabled=false")
    db.execute(
        "CREATE OR REPLACE FUNCTION public.poll_dufynd_github_scheduler_delivery_v1() "
        "RETURNS jsonb LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'private-canary'; END $$"
    )
    assert db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0] == {"attempted": 0}
    assert db.execute("SELECT count(*) FROM net.http_request_queue").fetchone()[0] == 0


def test_integration_preserves_existing_owner_acl_security_and_reapplication(db):
    before = protected_state(db)
    db.execute(MIGRATION.read_text())
    assert protected_state(db) == before
    assert db.execute("""SELECT bool_and(
      p.proowner=b.proowner AND p.proacl IS NOT DISTINCT FROM b.proacl
      AND p.prosecdef=b.prosecdef AND p.provolatile=b.provolatile AND p.proconfig=b.proconfig)
      FROM pg_proc p JOIN pg_temp.scheduler_integration_before b USING(oid)
    """).fetchone()[0]
    for name in (
        "poll_dufynd_observers",
        "read_dufynd_technical_work_blockers_v1",
        "plan_dufynd_free_work_v1",
        "audit_dufynd_integrity_v1",
    ):
        assert db.execute(
            "SELECT has_function_privilege('anon',%s,'execute'),"
            "has_function_privilege('authenticated',%s,'execute'),"
            "has_function_privilege('service_role',%s,'execute')",
            ("public." + name + "()",) * 3,
        ).fetchone() == (False, False, True)


def test_real_schedule_receipts_preserve_healthy_market_wait_without_business_claims(db):
    before = protected_state(db)
    source = scheduler.observe_both(db)
    assert source["healthy"] is True and source["transport_status"] == "fresh"
    assert source["delivery_gap"] is False and source["dispatch_status"] == "success"
    report = releases.technical(db)
    assert report["status"] == "healthy" and report["issues"] == []
    assert report["private_technical_work_remaining"] is False
    assert releases.plan(db)["state"] == "waiting_market_signal"
    result = releases.audit(db)
    assert result["status"] == "healthy" and result["private_broker_scheduler_gap"] is False
    for flag in (
        "business_success",
        "full_chain_complete",
        "capture_verified",
        "cadence_guarantee",
    ):
        assert result["github_scheduler_delivery"][flag] is False
    assert protected_state(db) == before


def test_recent_acceptance_cannot_hide_a_proven_natural_delivery_gap(db):
    source = scheduler.observe_both(
        db,
        reader_body=scheduler.run_body(db, age_seconds=7200),
        watchdog_body=scheduler.run_body(db, "watchdog", age_seconds=7200),
    )
    assert source["transport_status"] == "fresh" and source["delivery_gap"] is True
    assert old_audit(db)["private_broker_scheduler_gap"] is False
    report = releases.plan(db)
    assert report["action"] == "diagnose_private_scheduler_delivery"
    result = releases.audit(db)
    assert result["private_broker_acceptance_gap"] is False
    assert result["private_broker_scheduler_gap"] is True
    assert result["last_private_broker_capture_at"] is not None
    assert "github_scheduler_delivery_gap" in result["issues"]
    assert result["technical_diagnosis_current"] is True and result["planner_starved"] is False


def test_old_acceptance_cannot_turn_fresh_schedule_delivery_into_a_scheduler_gap(db):
    scheduler.observe_both(db)
    db.execute(
        "UPDATE public.dufynd_broker_acceptance_sessions SET created_at=now()-interval '1 hour',"
        "finalized_at=now()-interval '59 minutes' WHERE recurring_read"
    )
    assert old_audit(db)["private_broker_scheduler_gap"] is True
    result = releases.audit(db)
    assert result["private_broker_acceptance_gap"] is True
    assert result["private_broker_scheduler_gap"] is False
    assert "private_broker_acceptance_gap" in result["issues"]
    assert "github_scheduler_delivery_gap" not in result["issues"]
    assert releases.plan(db)["action"] == "diagnose_private_observer_runtime"


def test_one_missing_schedule_stays_degraded_without_claiming_both_schedules_failed(db):
    source = scheduler.observe_both(db, reader_body=scheduler.run_body(db, age_seconds=7200))
    assert source["delivery_status"] == "degraded" and source["delivery_gap"] is False
    assert releases.plan(db)["action"] == "diagnose_private_scheduler_delivery"
    result = releases.audit(db)
    assert result["private_broker_scheduler_gap"] is False
    assert "github_scheduler_delivery_degraded" in result["issues"]
    assert result["github_scheduler_delivery"]["schedules"]["reader"]["delivery_status"] == "gap"


@pytest.mark.parametrize(
    "status,conclusion,attempt,dispatch,issue",
    [
        ("completed", "failure", 1, "failed", "github_scheduler_dispatch_failed"),
        ("queued", None, 1, "pending", "github_scheduler_dispatch_unverified"),
        ("completed", "success", 2, "unknown", "github_scheduler_dispatch_unverified"),
    ],
)
def test_schedule_creation_and_dispatch_outcome_remain_separate_in_all_consumers(
    db, status, conclusion, attempt, dispatch, issue
):
    scheduler.observe_both(
        db,
        reader_body=scheduler.run_body(db, status=status, conclusion=conclusion, attempt=attempt),
    )
    report = releases.technical(db)
    source = report["github_scheduler_delivery"]
    assert source["delivery_status"] == "available" and source["delivery_gap"] is False
    assert source["dispatch_status"] == dispatch and issue in report["issues"]
    assert releases.plan(db)["action"] == "diagnose_private_scheduler_delivery"
    result = releases.audit(db)
    assert result["private_broker_scheduler_gap"] is False and issue in result["issues"]


def test_recent_rerun_start_and_manual_provider_freshness_cannot_renew_natural_delivery(db):
    scheduler.observe_both(
        db,
        reader_body=scheduler.run_body(db, age_seconds=14400, attempt=2),
        watchdog_body=scheduler.run_body(db, "watchdog", age_seconds=14400, attempt=3),
    )
    db.execute(
        "UPDATE public.dufynd_external_observers SET last_success_at=now(),health_status='healthy' "
        "WHERE source_type='render'"
    )
    before = protected_state(db)
    result = releases.audit(db)
    assert result["private_broker_scheduler_gap"] is True
    assert result["github_scheduler_delivery"]["dispatch_status"] == "unknown"
    assert "github_scheduler_delivery_gap" in result["issues"]
    assert "github_scheduler_dispatch_unverified" in result["issues"]
    assert db.execute(
        "SELECT %s::timestamptz<now()-interval '25 minutes'",
        (result["github_scheduler_delivery"]["latest_natural_created_at"],),
    ).fetchone()[0]
    assert protected_state(db) == before


def test_expired_actual_observations_become_unknown_delivery_without_another_poll(db):
    scheduler.observe_both(db)
    value = scheduler.stored(db)
    stamp = scheduler.now(db)
    for target in value["schedules"].values():
        # Simulate elapsed time on the already validated local receipt and its
        # source timestamps, without creating a success or refreshing a request.
        target["observed_at"] = (stamp - timedelta(seconds=1201)).isoformat()
        target["receipt_requested_at"] = (stamp - timedelta(seconds=1202)).isoformat()
        for run in target["snapshot"]["workflow_runs"]:
            for field in ("created_at", "run_started_at", "updated_at"):
                run[field] = (stamp - timedelta(seconds=1300)).isoformat()
    scheduler.save(db, value)
    before = scheduler.stored(db)
    result = releases.audit(db)
    assert result["private_broker_scheduler_gap"] is None
    assert result["private_broker_scheduler_observation_status"] == "stale"
    assert "github_scheduler_observation_stale" in result["issues"]
    assert "github_scheduler_delivery_gap" not in result["issues"]
    assert releases.plan(db)["action"] == "diagnose_private_scheduler_delivery"
    assert scheduler.stored(db) == before


def test_partial_api_observation_is_unknown_delivery_not_a_proven_gap(db):
    scheduler.enable_monitor(db)
    scheduler.poll(db)
    scheduler.respond(db)
    scheduler.poll(db)
    result = releases.audit(db)
    assert result["private_broker_scheduler_gap"] is None
    assert result["private_broker_scheduler_observation_status"] == "partial"
    assert "github_scheduler_observation_unavailable" in result["issues"]
    assert releases.plan(db)["action"] == "diagnose_private_scheduler_delivery"


def test_existing_observer_hook_enqueues_real_scheduler_request_once(db):
    db.execute("UPDATE public.dufynd_external_observers SET enabled=false")
    before = protected_state(db)
    scheduler.enable_monitor(db)
    assert db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0] == {"attempted": 0}
    assert db.execute("SELECT public.poll_dufynd_observers()").fetchone()[0] == {"attempted": 0}
    assert db.execute("SELECT url FROM net.http_request_queue").fetchall() == [
        (
            "https://api.github.com/repos/tncommerce/commerce-agents/actions/workflows/373752411/runs?branch=main&event=schedule&per_page=1",
        )
    ]
    assert protected_state(db) == before
