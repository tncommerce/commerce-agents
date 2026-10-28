"""Execute planner truth against a disposable PostgreSQL database; rollback all fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261028082303_jarvis_planner_technical_blockers.sql"
SHA = "36cc84c34791284e4245ab4504ae020434dca89e"


def call(db, function):
    assert function in (
        "read_dufynd_technical_work_blockers_v1",
        "read_dufynd_safe_work_exhaustion_v1",
        "plan_dufynd_free_work_v1",
    )
    return db.execute(f"SELECT public.{function}()").fetchone()[0]


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as connection:
        try:
            connection.execute("SET LOCAL statement_timeout='10s'")
            # Minimal contracts allow this module to run alone; CI's migrated
            # tables already exist. No production connection is used by CI.
            connection.execute("""
                CREATE TABLE IF NOT EXISTS public.dufynd_external_observers(
                  observer_id text primary key,source_type text,source_id text,
                  enabled boolean,health_status text,last_success_at timestamptz,
                  interval_seconds integer,last_snapshot jsonb);
                CREATE TABLE IF NOT EXISTS public.dufynd_broker_acceptance_sessions(
                  run_id bigint primary key,source_sha text,run_attempt integer,status text,
                  captured_observers jsonb,created_at timestamptz default now(),
                  expires_at timestamptz,finalized_at timestamptz,recurring_read boolean);
                CREATE TABLE IF NOT EXISTS public.dufynd_autonomy_tasks(
                  task_id text primary key,domain text,title text,instruction text,
                  status text,blocked_reason text);
                CREATE TABLE IF NOT EXISTS public.dufynd_master_status(
                  key text primary key,category text,value jsonb,priority integer,last_verified_at timestamptz);
                CREATE TEMP TABLE planner_technical_case(key text primary key,value jsonb);
                UPDATE public.dufynd_external_observers SET enabled=false;
                UPDATE public.dufynd_broker_acceptance_sessions SET recurring_read=false;
            """)
            dependencies = {
                "read_dufynd_first_money_runtime": {"next_evidence": "merchant_clickout"},
                "read_dufynd_first_money_measurement_audit_v1": {
                    "decision": "qualified_traffic_present_no_clickout"
                },
                "get_dufynd_next_autonomous_action": {
                    "state": "planner_gap",
                    "ready_count": 0,
                    "active_count": 0,
                    "approval_count": 0,
                    "waiting_human_count": 0,
                    "waiting_external_count": 14,
                },
                "wake_dufynd_purchase_freshness": {},
                "plan_dufynd_affiliate_work_v1": {},
                "plan_dufynd_zero_budget_content_work_v1": {},
                "plan_dufynd_content_packet_work_v1": {},
                "plan_dufynd_measurement_work_v1": {},
                "plan_dufynd_autonomous_business_work_v1": {"state": "planner_gap"},
            }
            for name, value in dependencies.items():
                connection.execute(
                    "INSERT INTO pg_temp.planner_technical_case VALUES(%s,%s::jsonb)",
                    (name, json.dumps(value)),
                )
                connection.execute(f"""CREATE OR REPLACE FUNCTION public.{name}()
                    RETURNS jsonb LANGUAGE sql STABLE SET search_path TO 'public'
                    AS $fixture$ SELECT value FROM pg_temp.planner_technical_case
                    WHERE key='{name}' $fixture$""")
            for source_type, source_id in (
                ("render", "srv-planner-fixture"),
                ("gmail", "abcdef1234567890"),
                ("github_branch", "scentai-mvp"),
            ):
                connection.execute(
                    """INSERT INTO public.dufynd_external_observers
                    (observer_id,source_type,source_id,enabled,health_status,last_success_at,interval_seconds,last_snapshot)
                    VALUES(%s,%s,%s,true,'healthy',now(),120,%s::jsonb)
                    ON CONFLICT(observer_id) DO UPDATE SET enabled=true,health_status='healthy',
                    last_success_at=now(),interval_seconds=120,last_snapshot=excluded.last_snapshot""",
                    (
                        f"{source_type}:{source_id}",
                        source_type,
                        source_id,
                        json.dumps({"sha": SHA}),
                    ),
                )
            connection.execute(
                """INSERT INTO public.dufynd_broker_acceptance_sessions
                (run_id,source_sha,run_attempt,status,captured_observers,created_at,expires_at,finalized_at,recurring_read)
                VALUES(999999999999,%s,1,'activated','["render:srv-planner-fixture","gmail:abcdef1234567890"]',now(),now()+interval '10 minutes',now(),true)""",
                (SHA,),
            )
            today = connection.execute(
                "SELECT to_char(now() AT TIME ZONE 'UTC','YYYYMMDD')"
            ).fetchone()[0]
            for task in (
                f"bizplan:zero-budget-content-queue:{today}",
                f"bizplan:content-packet:fixture:{today}",
                f"bizplan:creative-recovery:{today}",
            ):
                connection.execute(
                    """INSERT INTO public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status)
                    VALUES(%s,'supervisor','isolated regression','test fixture','done')
                    ON CONFLICT(task_id) DO UPDATE SET status='done'""",
                    (task,),
                )
            connection.execute(MIGRATION.read_text())
            yield connection
        finally:
            connection.rollback()


def test_healthy_technical_evidence_preserves_honest_market_wait(db):
    report = call(db, "read_dufynd_technical_work_blockers_v1")
    assert report["status"] == "healthy" and report["issues"] == []
    exhaustion = call(db, "read_dufynd_safe_work_exhaustion_v1")
    assert exhaustion["business_work_exhausted"] is True
    assert exhaustion["safe_internal_work_exhausted"] is True
    assert call(db, "plan_dufynd_free_work_v1")["state"] == "waiting_market_signal"


@pytest.mark.parametrize(
    ("change", "issue"),
    [
        (
            "UPDATE public.dufynd_external_observers SET last_success_at=now()-interval '6 days' WHERE source_type='render'",
            "private_observer_stale",
        ),
        (
            "UPDATE public.dufynd_external_observers SET health_status='blocked_configuration' WHERE source_type='gmail'",
            "blocked_observer_configuration",
        ),
        (
            "UPDATE public.dufynd_external_observers SET last_snapshot='{\"sha\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}' WHERE source_type='render'",
            "github_render_sha_mismatch",
        ),
        (
            "UPDATE public.dufynd_broker_acceptance_sessions SET created_at=now()-interval '1 hour' WHERE recurring_read",
            "private_broker_acceptance_gap",
        ),
        (
            "UPDATE public.dufynd_external_observers SET enabled=false WHERE source_type='render'",
            "render_monitor_missing",
        ),
        (
            "UPDATE public.dufynd_external_observers SET last_success_at=now()-interval '1 hour' WHERE source_type='github_branch'",
            "production_revision_unverified",
        ),
        (
            "UPDATE public.dufynd_external_observers SET last_success_at=now()+interval '1 day' WHERE source_type='render'",
            "private_observer_stale",
        ),
    ],
)
def test_technical_blockers_prevent_global_exhaustion_without_fake_tasks(db, change, issue):
    db.execute(change)
    before = db.execute("SELECT count(*) FROM public.dufynd_autonomy_tasks").fetchone()[0]
    exhaustion = call(db, "read_dufynd_safe_work_exhaustion_v1")
    assert exhaustion["business_work_exhausted"] is True
    assert exhaustion["safe_internal_work_exhausted"] is False
    assert issue in exhaustion["technical_work"]["issues"]
    report = call(db, "plan_dufynd_free_work_v1")
    assert report["state"] == "technical_remediation_required"
    assert report["operational_state"] == "degraded"
    assert report["action"] == "diagnose_private_observer_runtime"
    assert report["technical_repair_executed"] is False
    assert report["new_spend_usd"] == 0
    assert report["queue"]["waiting_external_count"] == 14
    assert db.execute("SELECT count(*) FROM public.dufynd_autonomy_tasks").fetchone()[0] == before
    assert (
        db.execute(
            "SELECT value->>'state' FROM public.dufynd_master_status WHERE key='jarvis.planner_v1'"
        ).fetchone()[0]
        == "technical_remediation_required"
    )


@pytest.mark.parametrize("status", ["failed", "capturing", "captured"])
def test_recent_acceptance_is_not_successful_capture(db, status):
    db.execute(
        "UPDATE public.dufynd_broker_acceptance_sessions SET status=%s WHERE recurring_read",
        (status,),
    )
    report = call(db, "read_dufynd_technical_work_blockers_v1")
    assert report["private_broker_acceptance_gap"] is False
    assert report["last_broker_complete_capture_at"] is None
    assert "private_broker_capture_unverified" in report["issues"]
    assert call(db, "plan_dufynd_free_work_v1")["state"] == "technical_remediation_required"


@pytest.mark.parametrize("state", ["work_available", "work_in_progress", "owner_gate"])
def test_existing_real_work_or_owner_gate_still_takes_precedence(db, state):
    db.execute(
        "UPDATE public.dufynd_external_observers SET health_status='blocked_configuration' WHERE source_type='gmail'"
    )
    db.execute(
        "UPDATE pg_temp.planner_technical_case SET value=jsonb_set(value,'{state}',%s::jsonb) WHERE key='get_dufynd_next_autonomous_action'",
        (json.dumps(state),),
    )
    assert call(db, "plan_dufynd_free_work_v1")["state"] == state


def test_migration_reapply_acl_and_read_only_classifier(db):
    db.execute(MIGRATION.read_text())
    for name in (
        "read_dufynd_technical_work_blockers_v1",
        "read_dufynd_safe_work_exhaustion_v1",
        "plan_dufynd_free_work_v1",
    ):
        for role in ("anon", "authenticated"):
            assert not db.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, f"public.{name}()")
            ).fetchone()[0]
        assert db.execute(
            "SELECT has_function_privilege('service_role',%s,'EXECUTE')", (f"public.{name}()",)
        ).fetchone()[0]
    assert db.execute(
        "SELECT provolatile='s' AND NOT prosecdef FROM pg_proc WHERE oid='public.read_dufynd_technical_work_blockers_v1()'::regprocedure"
    ).fetchone()[0]
    source = MIGRATION.read_text().lower()
    for forbidden in (
        "cron.schedule",
        "insert into public.dufynd_autonomy_tasks",
        "update public.dufynd_external_observers",
        "http_post",
        "security definer",
    ):
        assert forbidden not in source


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE public.dufynd_broker_acceptance_sessions SET captured_observers='[\"render:srv-planner-fixture\"]' WHERE recurring_read",
        "UPDATE public.dufynd_broker_acceptance_sessions SET finalized_at=null WHERE recurring_read",
        "UPDATE public.dufynd_broker_acceptance_sessions SET source_sha='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' WHERE recurring_read",
    ],
)
def test_partial_or_unfinalized_or_wrong_revision_receipt_never_completes_chain(db, change):
    db.execute(change)
    report = call(db, "read_dufynd_technical_work_blockers_v1")
    assert report["status"] == "degraded"
    assert report["last_broker_complete_capture_at"] is None
    assert "private_broker_capture_unverified" in report["issues"]
