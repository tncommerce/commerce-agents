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
