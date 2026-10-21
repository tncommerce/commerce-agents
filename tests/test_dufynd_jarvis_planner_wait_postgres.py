"""Real PostgreSQL regression for the DEV-only Jarvis planner state correction.

Runs exclusively against DUFYND_TEST_DATABASE_URL (CI's disposable Postgres).
A private fixture schema isolates all data/functions; no production writes,
no cron mutation and no external service calls are made.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase/migrations/20261021133000_dufynd_jarvis_planner_external_buyer_signal.sql"
)
SCHEMA = "jarvis_planner_fixture"


@pytest.fixture(scope="module")
def database():
    import psycopg

    raw = MIGRATION.read_text(encoding="utf-8")
    assert raw.count("CREATE OR REPLACE FUNCTION") == 2
    assert "cron.schedule" not in raw
    assert "insert into public.dufynd_autonomy_tasks" not in raw.lower()
    # Isolate exactly the LIVE function bodies inside the disposable fixture
    # schema, keeping helper names/types and planner execution flow unchanged.
    isolated = raw.replace("public.", f"{SCHEMA}.").replace(
        "SET search_path TO 'public'", f"SET search_path TO '{SCHEMA}'"
    )
    with psycopg.connect(DSN, autocommit=True) as setup:
        setup.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        setup.execute(f"CREATE SCHEMA {SCHEMA}")
        setup.execute(f"""
            CREATE TABLE {SCHEMA}.dufynd_autonomy_tasks(
              task_id text PRIMARY KEY, status text NOT NULL);
            CREATE TABLE {SCHEMA}.dufynd_master_status(
              key text PRIMARY KEY, category text, value jsonb, priority integer,
              last_verified_at timestamptz);
            CREATE TABLE {SCHEMA}.signals(
              singleton boolean PRIMARY KEY DEFAULT true,
              fm jsonb NOT NULL, audit jsonb NOT NULL, queue jsonb NOT NULL);
            INSERT INTO {SCHEMA}.signals VALUES(
              true,
              '{{"next_evidence":"merchant_clickout"}}'::jsonb,
              '{{"decision":"qualified_traffic_present_no_clickout"}}'::jsonb,
              '{{"state":"planner_gap"}}'::jsonb);
            CREATE FUNCTION {SCHEMA}.read_dufynd_first_money_runtime()
              RETURNS jsonb LANGUAGE sql STABLE AS
              'SELECT fm FROM {SCHEMA}.signals WHERE singleton';
            CREATE FUNCTION {SCHEMA}.read_dufynd_first_money_measurement_audit_v1()
              RETURNS jsonb LANGUAGE sql STABLE AS
              'SELECT audit FROM {SCHEMA}.signals WHERE singleton';
            CREATE FUNCTION {SCHEMA}.get_dufynd_next_autonomous_action()
              RETURNS jsonb LANGUAGE sql STABLE AS
              'SELECT queue FROM {SCHEMA}.signals WHERE singleton';
        """)
        for name, signature in [
            ("wake_dufynd_purchase_freshness", "jsonb"),
            ("plan_dufynd_affiliate_work_v1", "jsonb"),
            ("plan_dufynd_zero_budget_content_work_v1", "jsonb"),
            ("plan_dufynd_content_packet_work_v1", "jsonb"),
            ("plan_dufynd_measurement_work_v1", "jsonb"),
            ("plan_dufynd_autonomous_business_work_v1", "jsonb"),
        ]:
            setup.execute(
                f"CREATE FUNCTION {SCHEMA}.{name}() RETURNS {signature} "
                "LANGUAGE sql STABLE AS "
                '\'SELECT \'\'{"state":"planner_gap","created":false,"business_next_move":"social_publication_readiness"}\'\'::jsonb\''
            )
        setup.execute(isolated)
    try:
        yield DSN
    finally:
        with psycopg.connect(DSN, autocommit=True) as teardown:
            teardown.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture
def db(database):
    import psycopg

    with psycopg.connect(database) as connection:
        yield connection
        connection.rollback()


def setup_case(
    db,
    *,
    signal="merchant_clickout",
    decision="qualified_traffic_present_no_clickout",
    content_done=True,
    measurement_done=False,
    queue_state="planner_gap",
    executable=False,
    owner_gate=False,
):
    db.execute(f"DELETE FROM {SCHEMA}.dufynd_autonomy_tasks")
    db.execute(
        f"""UPDATE {SCHEMA}.signals SET
            fm=jsonb_build_object('next_evidence',%s),
            audit=jsonb_build_object('decision',%s),
            queue=jsonb_build_object('state',%s) WHERE singleton""",
        (signal, decision, queue_state),
    )
    day = db.execute("SELECT to_char(now() at time zone 'UTC','YYYYMMDD')").fetchone()[0]
    if content_done:
        tasks = [
            (f"bizplan:zero-budget-content-queue:{day}", "done"),
            (f"bizplan:content-packet:fixture:{day}", "done"),
            (f"bizplan:creative-recovery:{day}", "done"),
        ]
    else:
        tasks = []
    if measurement_done:
        tasks.append((f"bizplan:first-money-measurement:{day}", "done"))
    if executable:
        tasks.append(("fixture:real-ready-work", "ready"))
    if owner_gate:
        tasks.append(("fixture:approval", "approval_required"))
    for task_id, status in tasks:
        db.execute(
            f"INSERT INTO {SCHEMA}.dufynd_autonomy_tasks(task_id,status) VALUES(%s,%s)",
            (task_id, status),
        )


def exhaustion(db):
    return db.execute(f"SELECT {SCHEMA}.read_dufynd_safe_work_exhaustion_v1()").fetchone()[0]


def plan(db):
    return db.execute(f"SELECT {SCHEMA}.plan_dufynd_free_work_v1()").fetchone()[0]


def test_current_production_gap_becomes_truthful_external_buyer_wait(db):
    setup_case(db)
    exhausted = exhaustion(db)
    assert exhausted["safe_internal_work_exhausted"] is True
    assert exhausted["waiting_signal"] == "merchant_clickout"
    assert exhausted["reason"] == "genuine_merchant_clickout_required"
    assert exhausted["measurement_done"] is False
    result = plan(db)
    assert result["state"] == "waiting_buyer_signal"
    assert result["action"] == "wait_for_genuine_merchant_clickout"
    assert result["reason"] == "genuine_merchant_clickout_required"
    assert result["new_spend_usd"] == 0
    assert result["master_action_required"] is False
    assert (
        db.execute(
            f"SELECT count(*) FROM {SCHEMA}.dufynd_autonomy_tasks WHERE status='ready'"
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("missing", ["content", "ready", "owner"])
def test_real_internal_work_or_gate_prevents_false_exhaustion(db, missing):
    setup_case(
        db,
        content_done=missing != "content",
        executable=missing == "ready",
        owner_gate=missing == "owner",
    )
    report = exhaustion(db)
    assert report["safe_internal_work_exhausted"] is False
    assert report["waiting_signal"] is None
    assert report["reason"] == "internal_work_or_gate_remains"


def test_qualified_distribution_wait_preserves_original_requirement(db):
    setup_case(
        db,
        signal="qualified_session",
        decision="waiting_for_qualified_distribution_signal",
        measurement_done=True,
    )
    x = exhaustion(db)
    assert x["waiting_signal"] == "qualified_session"
    assert x["safe_internal_work_exhausted"] is True
    y = plan(db)
    assert y["state"] == "waiting_market_signal"
    assert y["action"] == "wait_for_qualified_distribution_signal"


def test_distribution_wait_needs_completed_measurement(db):
    setup_case(
        db,
        signal="qualified_session",
        decision="waiting_for_qualified_distribution_signal",
        measurement_done=False,
    )
    assert exhaustion(db)["safe_internal_work_exhausted"] is False


def test_unmatched_business_signal_does_not_claim_exhaustion(db):
    setup_case(db, signal="external_transaction", decision="unknown")
    assert exhaustion(db)["safe_internal_work_exhausted"] is False
    assert plan(db)["state"] == "planner_gap"


def test_preexisting_work_gate_remains_authoritative(db):
    setup_case(db, queue_state="owner_gate")
    report = plan(db)
    assert report["state"] == "owner_gate"
    assert report["action"] == "none"
    assert report["new_spend_usd"] == 0


def test_deterministic_replay_preserves_outcome_without_extra_tasks(db):
    setup_case(db)
    first = plan(db)
    second = plan(db)
    assert first["state"] == second["state"] == "waiting_buyer_signal"
    assert first["reason"] == second["reason"]
    assert db.execute(f"SELECT count(*) FROM {SCHEMA}.dufynd_autonomy_tasks").fetchone()[0] == 3
    saved = db.execute(
        f"SELECT value->>'state' FROM {SCHEMA}.dufynd_master_status WHERE key='jarvis.planner_v1'"
    ).fetchone()[0]
    assert saved == "waiting_buyer_signal"
