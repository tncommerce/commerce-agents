"""Real PostgreSQL regression for Jarvis planner evidence/stall classification.

Only runs in the disposable budget-postgres CI database. All fixture changes,
including temporary function replacements and master-status writes, roll back.
No real traffic, merchant click, cron change, provider call or production write.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase/migrations/20261021130229_jarvis_planner_external_signal_truth.sql"
)
LEGACY = ROOT / "supabase/migrations/20261007064000_jarvis_measurement_continuity_v1.sql"

DEFAULT_QUEUE = {
    "state": "planner_gap",
    "ready_count": 0,
    "active_count": 0,
    "waiting_human_count": 0,
    "approval_count": 0,
    "waiting_external_count": 14,
    "external_with_unsatisfied_dependency": 3,
    "external_without_verified_dependency": 11,
    "stop_reason": "no_executable_work",
}


def set_case(db, key: str, value: dict) -> None:
    db.execute(
        """INSERT INTO pg_temp.dufynd_planner_case(key,value)
           VALUES(%s,%s::jsonb)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (key, json.dumps(value)),
    )


def configure(db, *, next_evidence="merchant_clickout",
              decision="qualified_traffic_present_no_clickout",
              queue=None) -> None:
    set_case(db, "fm", {"next_evidence": next_evidence, "publication_verified": False})
    set_case(db, "audit", {"decision": decision, "clickout_is_sale": False})
    set_case(db, "queue", queue or DEFAULT_QUEUE)


def seed_completed_daily_work(db, *, omit=(), measurement=False) -> None:
    today = db.execute(
        "SELECT to_char(now() AT TIME ZONE 'UTC','YYYYMMDD')"
    ).fetchone()[0]
    identifiers = {
        "content_queue": f"bizplan:zero-budget-content-queue:{today}",
        "content_packet": f"bizplan:content-packet:planner-fixture:{today}",
        "content_reuse": f"bizplan:creative-recovery:{today}",
        "measurement": f"bizplan:first-money-measurement:{today}",
    }
    for name in ("content_queue", "content_packet", "content_reuse", "measurement"):
        if name in omit or (name == "measurement" and not measurement):
            continue
        db.execute(
            """INSERT INTO public.dufynd_autonomy_tasks
                 (task_id,domain,title,instruction,status)
               VALUES(%s,'supervisor','isolated planner regression',
                      'not a real task','done')
               ON CONFLICT(task_id) DO UPDATE SET status='done'""",
            (identifiers[name],),
        )


def read_exhaustion(db) -> dict:
    return db.execute(
        "SELECT public.read_dufynd_safe_work_exhaustion_v1()"
    ).fetchone()[0]


def run_planner(db) -> dict:
    return db.execute(
        "SELECT public.plan_dufynd_free_work_v1()"
    ).fetchone()[0]


@pytest.fixture
def db():
    """Compile actual patched SQL and execute with test-only dependency inputs.

    The shared dedicated PostgreSQL service is initialized by the preceding
    budget fixture module. We replace only transaction-local SQL definitions;
    the pytest connection is rolled back before returning to other modules.
    """
    if not DSN:
        pytest.skip("disposable PostgreSQL not available")
    import psycopg

    with psycopg.connect(DSN) as connection:
        try:
            connection.execute("SET LOCAL statement_timeout = '20000ms'")
            connection.execute(
                """CREATE TEMP TABLE dufynd_planner_case
                   (key text PRIMARY KEY, value jsonb NOT NULL)
                   ON COMMIT DROP"""
            )
            configure(connection)
            for function, key in (
                ("read_dufynd_first_money_runtime", "fm"),
                ("read_dufynd_first_money_measurement_audit_v1", "audit"),
                ("get_dufynd_next_autonomous_action", "queue"),
                ("plan_dufynd_affiliate_work_v1", "affiliate"),
                ("plan_dufynd_zero_budget_content_work_v1", "content"),
                ("plan_dufynd_content_packet_work_v1", "packet"),
                ("plan_dufynd_measurement_work_v1", "measurement"),
                ("plan_dufynd_autonomous_business_work_v1", "business"),
            ):
                # Fixture keys and function names are a fixed local allowlist.
                connection.execute(
                    f"""CREATE OR REPLACE FUNCTION public.{function}()
                         RETURNS jsonb LANGUAGE sql STABLE
                         SET search_path TO 'public'
                         AS $fixture$ SELECT coalesce(
                           (SELECT value FROM pg_temp.dufynd_planner_case
                            WHERE key='{key}'), '{{}}'::jsonb
                         ) $fixture$"""
                )
            connection.execute(
                """CREATE OR REPLACE FUNCTION public.wake_dufynd_purchase_freshness()
                   RETURNS jsonb LANGUAGE plpgsql
                   SET search_path TO 'public'
                   AS $fixture$
                   DECLARE wake_case jsonb;
                   BEGIN
                     SELECT value INTO wake_case FROM pg_temp.dufynd_planner_case
                       WHERE key='wake';
                     IF wake_case->>'make_ready'='true' THEN
                       UPDATE pg_temp.dufynd_planner_case
                       SET value=jsonb_set(
                         jsonb_set(value,'{state}','"work_available"'::jsonb),
                         '{ready_count}','1'::jsonb
                       ) WHERE key='queue';
                     END IF;
                     RETURN coalesce(wake_case,'{}'::jsonb);
                   END $fixture$"""
            )
            connection.execute(MIGRATION.read_text(encoding="utf-8"))
            yield connection
        finally:
            # IMPORTANT: prevent any fixture rows or replaced public function
            # definitions from persisting even on an assertion failure.
            connection.rollback()


def test_old_live_definition_reproduces_the_merchant_clickout_planner_gap(db):
    seed_completed_daily_work(db)
    legacy = LEGACY.read_text(encoding="utf-8")
    beginning = legacy.index(
        "create or replace function public.read_dufynd_safe_work_exhaustion_v1()"
    )
    end = legacy.index(
        "revoke execute on function public.read_dufynd_safe_work_exhaustion_v1()",
        beginning,
    )
    db.execute(legacy[beginning:end])
    old = read_exhaustion(db)
    assert old["safe_internal_work_exhausted"] is False
    assert old["measurement_done"] is False
    assert old["first_money_next_evidence"] == "merchant_clickout"
    db.execute(MIGRATION.read_text(encoding="utf-8"))
    fixed = read_exhaustion(db)
    assert fixed["safe_internal_work_exhausted"] is True
    assert fixed["next_external_evidence"] == "merchant_clickout"
    assert fixed["measurement_done"] is False
    assert fixed["measurement_gate_satisfied"] is True


def test_merchant_clickout_awaited_without_fake_measurement_or_new_tasks(db):
    seed_completed_daily_work(db)
    before = db.execute(
        "SELECT count(*) FROM public.dufynd_autonomy_tasks"
    ).fetchone()[0]
    audit = read_exhaustion(db)
    assert audit["measurement_done"] is False
    assert audit["measurement_work_due"] is False
    assert audit["measurement_gate_satisfied"] is True
    assert audit["safe_internal_work_exhausted"] is True
    assert audit["executable_count"] == audit["owner_gate_count"] == 0
    assert audit["reason"] == "merchant_clickout_signal_required"
    assert audit["new_spend_usd"] == 0

    for _ in range(2):
        outcome = run_planner(db)
        assert outcome["version"] == 6
        assert outcome["state"] == "waiting_market_signal"
        assert outcome["action"] == "wait_for_verified_merchant_clickout"
        assert outcome["next_external_evidence"] == "merchant_clickout"
        assert outcome["reason"] == "no_certified_safe_work_currently_executable"
        assert outcome["queue"]["waiting_external_count"] == 14
        assert outcome["master_action_required"] is False
        assert outcome["new_spend_usd"] == 0
    after = db.execute(
        "SELECT count(*) FROM public.dufynd_autonomy_tasks"
    ).fetchone()[0]
    assert after == before, "Planner generated artificial tasks in the wait state"
    saved = db.execute(
        "SELECT value FROM public.dufynd_master_status WHERE key='jarvis.planner_v1'"
    ).fetchone()[0]
    assert saved["state"] == "waiting_market_signal"


def test_network_transaction_stage_does_not_claim_a_sale(db):
    seed_completed_daily_work(db)
    configure(
        db, next_evidence="affiliate_transaction_evidence",
        decision="attributed_clickout_signal_present",
    )
    status = read_exhaustion(db)
    assert status["safe_internal_work_exhausted"] is True
    assert status["measurement_work_due"] is False
    assert status["next_external_evidence"] == "affiliate_transaction_evidence"
    outcome = run_planner(db)
    assert outcome["state"] == "waiting_market_signal"
    assert outcome["action"] == "wait_for_original_network_transaction"
    assert outcome["new_spend_usd"] == 0
    assert "commission" not in outcome and "sales" not in outcome


def test_qualified_distribution_wait_keeps_legacy_action_after_diagnostic(db):
    seed_completed_daily_work(db, measurement=True)
    configure(db, next_evidence="qualified_session",
              decision="waiting_for_qualified_distribution_signal")
    status = read_exhaustion(db)
    assert status["measurement_work_due"] is True
    assert status["measurement_done"] is True
    assert status["safe_internal_work_exhausted"] is True
    outcome = run_planner(db)
    assert outcome["state"] == "waiting_market_signal"
    assert outcome["action"] == "wait_for_qualified_distribution_signal"


def test_due_but_unfinished_measurement_never_becomes_market_wait(db):
    seed_completed_daily_work(db, measurement=False)
    configure(db, next_evidence="qualified_session",
              decision="waiting_for_qualified_distribution_signal")
    status = read_exhaustion(db)
    assert status["measurement_work_due"] is True
    assert status["measurement_done"] is False
    assert status["measurement_gate_satisfied"] is False
    assert status["safe_internal_work_exhausted"] is False
    outcome = run_planner(db)
    assert outcome["state"] == "planner_gap"
    assert outcome["exhaustion"]["safe_internal_work_exhausted"] is False


@pytest.mark.parametrize(
    ("next_evidence", "decision"),
    [
        ("merchant_clickout", "waiting_for_qualified_distribution_signal"),
        ("qualified_session", "qualified_traffic_present_no_clickout"),
        ("affiliate_transaction_evidence", "qualified_traffic_present_no_clickout"),
        ("unrecognized", "unrecognized"),
        (None, None),
    ],
)
def test_unverified_or_conflicting_evidence_fails_closed(
    db, next_evidence, decision,
):
    seed_completed_daily_work(db)
    configure(db, next_evidence=next_evidence, decision=decision)
    status = read_exhaustion(db)
    assert status["next_external_evidence"] is None
    assert status["safe_internal_work_exhausted"] is False
    assert status["reason"] == "first_money_evidence_unverified_or_missing"
    result = run_planner(db)
    assert result["state"] != "waiting_market_signal"
    assert result["new_spend_usd"] == 0


@pytest.mark.parametrize(
    ("queue", "expected"),
    [
        ({"state": "work_available", "ready_count": 1}, "work_available"),
        ({"state": "work_in_progress", "active_count": 1}, "work_in_progress"),
        ({"state": "owner_gate", "approval_count": 1}, "owner_gate"),
        ({"state": "owner_gate", "waiting_human_count": 1}, "owner_gate"),
    ],
)
def test_ready_leased_or_owner_gated_work_takes_precedence(db, queue, expected):
    seed_completed_daily_work(db)
    configure(db, queue={**DEFAULT_QUEUE, **queue})
    status = read_exhaustion(db)
    assert status["safe_internal_work_exhausted"] is False
    assert status["reason"] in (
        "certified_work_available", "certified_work_in_progress",
        "owner_approval_required",
    )
    result = run_planner(db)
    assert result["state"] == expected
    assert result["action"] == "none"
    assert result["new_spend_usd"] == 0


def test_missing_content_work_cannot_be_declared_exhausted(db):
    seed_completed_daily_work(db, omit=("content_packet",))
    status = read_exhaustion(db)
    assert status["content_packet_done"] is False
    assert status["safe_internal_work_exhausted"] is False
    assert run_planner(db)["state"] == "planner_gap"


def test_purchase_wake_wins_when_it_discovers_real_queue_work(db):
    seed_completed_daily_work(db)
    set_case(db, "wake", {"make_ready": True})
    before = db.execute(
        "SELECT count(*) FROM public.dufynd_autonomy_tasks"
    ).fetchone()[0]
    outcome = run_planner(db)
    assert outcome["state"] == "work_replenished"
    assert outcome["action"] == "purchase_freshness_wake"
    assert outcome["queue"]["state"] == "work_available"
    after = db.execute(
        "SELECT count(*) FROM public.dufynd_autonomy_tasks"
    ).fetchone()[0]
    assert before == after  # Synthetic queue state in disposable fixture only.


def test_permissions_and_idempotent_migration_preserve_isolated_acl(db):
    db.execute(MIGRATION.read_text(encoding="utf-8"))
    for function in (
        "read_dufynd_safe_work_exhaustion_v1", "plan_dufynd_free_work_v1"
    ):
        signature = f"public.{function}()"
        for blocked in ("anon", "authenticated"):
            assert not db.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE')",
                (blocked, signature),
            ).fetchone()[0]
        assert db.execute(
            "SELECT has_function_privilege('service_role',%s,'EXECUTE')",
            (signature,),
        ).fetchone()[0]
        source = db.execute(
            "SELECT pg_get_functiondef(%s::regprocedure)", (signature,)
        ).fetchone()[0]
        assert "SET search_path TO 'public'" in source
        assert "SECURITY DEFINER" not in source


def test_migration_declares_no_scheduler_queue_or_provider_side_effects():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert sql.count("create or replace function public.") == 2
    assert "create trigger" not in sql
    assert "cron.schedule" not in sql
    assert "create extension" not in sql
    assert "insert into public.dufynd_autonomy_tasks" not in sql
    assert "update public.dufynd_autonomy_tasks" not in sql
    assert "external.http" not in sql
    assert "http_post" not in sql
    assert "security definer" not in sql
