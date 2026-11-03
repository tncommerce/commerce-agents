"""Compile the reversible Thin V1 SQL change in disposable CI PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated PostgreSQL service required")
ROOT = Path(__file__).resolve().parents[1]


def test_thin_noop_migration_compiles_and_preserves_acl():
    """Reuse the budget-postgres CI fixture schema; rollback every DDL statement."""
    import psycopg

    migration = (
        ROOT / "supabase/migrations/20261017214500_dufynd_thin_noop_suppression.sql"
    ).read_text(encoding="utf-8")
    with psycopg.connect(DSN) as db:
        db.execute(migration)
        definition = db.execute(
            "select pg_get_functiondef('public.run_dufynd_thin_v1()'::regprocedure)"
        ).fetchone()[0]
        assert "periodic_health_tasks" in definition
        assert "prepare_dufynd_execution(" in definition
        assert "purchase_destination_freshness_audit" in definition
        assert not db.execute(
            "select has_function_privilege('anon','public.run_dufynd_thin_v1()','execute')"
        ).fetchone()[0]
        assert not db.execute(
            "select has_function_privilege('authenticated','public.run_dufynd_thin_v1()','execute')"
        ).fetchone()[0]
        db.rollback()


def test_thin_noop_guard_controls_actual_task_creation():
    """Call the real patched Thin Worker against disposable PostgreSQL.

    The isolated budget-postgres fixture supplies genuine queue tables and
    supervisor handler contracts. Temporary test-only stand-ins replace
    unrelated live GitHub polling and dashboard JSON readers. Every change,
    including the synthetic control task in rollback mode, is rolled back.
    """
    import psycopg

    migration = (
        ROOT / "supabase/migrations/20261017214500_dufynd_thin_noop_suppression.sql"
    ).read_text(encoding="utf-8")
    with psycopg.connect(DSN) as db:
        # Green CI is simulated only inside the disposable transaction. This
        # tests the new insertion gate, not the separately tested CI verifier.
        db.execute(
            """
            create or replace function public.poll_dufynd_thin_ci()
            returns jsonb language sql as $$
            select '{"ready":true,"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","run_id":"ci-fixture"}'::jsonb
            $$
            """
        )
        db.execute(
            """
            create or replace function public.dufynd_thin_gate(jsonb)
            returns text language sql as $$ select null::text $$
            """
        )
        db.execute(
            """
            create or replace function public.read_dufynd_thin_state()
            returns jsonb language sql as $$ select '{}'::jsonb $$
            """
        )
        db.execute(
            """
            create or replace function public.read_dufynd_planner_state()
            returns jsonb language sql as $$ select '{}'::jsonb $$
            """
        )
        db.execute(
            """
            insert into public.dufynd_master_status(key,category,value,priority)
            values ('jarvis.thin_v1.config','jarvis',
                    '{"enabled":true,"periodic_health_tasks":false}'::jsonb,100)
            on conflict(key) do update set value=excluded.value
            """
        )
        # The generic budget fixture predates created_at; production has it.
        # Add it only to this transaction, where rollback removes it again.
        db.execute(
            "alter table public.dufynd_autonomy_tasks "
            "add column if not exists created_at timestamptz default now()"
        )
        db.execute(migration)

        task_filter = (
            "select count(*) from public.dufynd_autonomy_tasks where task_id like 'thin-health:%'"
        )
        before = db.execute(task_filter).fetchone()[0]
        off = db.execute("select public.run_dufynd_thin_v1()").fetchone()[0]
        after_off = db.execute(task_filter).fetchone()[0]
        assert after_off == before, "default-off created synthetic health work"
        assert off["paid_calls"] == 0
        assert off["loop_ci"]["ready"] is True

        # The documented recovery switch must restore the precise old
        # behavior, without changing Cron or disabling the other workers.
        db.execute(
            """
            update public.dufynd_master_status
            set value=jsonb_set(value,'{periodic_health_tasks}','true'::jsonb,true)
            where key='jarvis.thin_v1.config'
            """
        )
        on = db.execute("select public.run_dufynd_thin_v1()").fetchone()[0]
        after_on = db.execute(task_filter).fetchone()[0]
        assert after_on == before + 1, "rollback switch did not restore task generation"
        assert on["paid_calls"] == 0

        # No synthetic duplicates on repeated same-slot invocation.
        db.execute("select public.run_dufynd_thin_v1()")
        assert db.execute(task_filter).fetchone()[0] == after_on

        db.rollback()
