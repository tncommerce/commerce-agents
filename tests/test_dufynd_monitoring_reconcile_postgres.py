"""Operational reconciliation against disposable PostgreSQL, never production."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
SQL = (
    Path(__file__).resolve().parents[1]
    / "release/dufynd-observer-operations-20261028/reconcile-monitoring.sql"
)


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as conn:
        try:
            conn.execute("set local statement_timeout='15s'")
            # Earlier budget cases leave referenced reservations/evidence. A
            # transaction-local truncate isolates this case and is rolled back
            # with the rest of the fixture, including every dependent table.
            conn.execute(
                "truncate public.dufynd_autonomy_tasks, public.dufynd_external_observers cascade"
            )
            for kind, identity, state in (
                ("github_branch", "scentai-mvp", "branch"),
                ("github_pr", "623", "merged"),
                ("github_pr", "625", "merged"),
                ("github_ci", "37016647384", "success"),
                ("github_ci", "37033948872", "success"),
                ("render", "srv-dakpfrnf3r2c73dr3f20", "live"),
            ):
                conn.execute(
                    """insert into public.dufynd_external_observers
                        (observer_id,source_type,source_id,last_snapshot,last_success_at,last_cursor,health_status)
                        values (%s,%s,%s,jsonb_build_object('state',%s::text,'sha',%s::text),now()-interval '6 days','original-cursor','healthy')""",
                    (
                        kind + ":" + identity,
                        kind,
                        identity,
                        state,
                        "36cc84c34791284e4245ab4504ae020434dca89e",
                    ),
                )
            yield conn
        finally:
            conn.rollback()


def test_reconciliation_retires_terminal_monitors_without_forging_freshness(db):
    old = db.execute(
        "select last_success_at,last_cursor,last_snapshot from public.dufynd_external_observers where source_type='render'"
    ).fetchone()
    before_tasks = db.execute("select count(*) from public.dufynd_autonomy_tasks").fetchone()[0]
    db.execute(SQL.read_text())
    assert (
        db.execute(
            "select count(*) from public.dufynd_external_observers where not enabled"
        ).fetchone()[0]
        == 4
    )
    fresh = db.execute(
        "select source_id,health_status,last_success_at,last_cursor,interval_seconds from public.dufynd_external_observers where source_id in ('802','823','837','840') order by source_id"
    ).fetchall()
    assert len(fresh) == 4
    assert all(row[1:] == ("initializing", None, None, 1200) for row in fresh)
    assert (
        db.execute(
            "select last_success_at,last_cursor,last_snapshot from public.dufynd_external_observers where source_type='render'"
        ).fetchone()
        == old
    )
    assert (
        db.execute(
            "select health_status from public.dufynd_external_observers where source_type='render'"
        ).fetchone()[0]
        == "stale"
    )
    assert (
        db.execute("select count(*) from public.dufynd_autonomy_tasks").fetchone()[0]
        == before_tasks
    )
    db.execute(SQL.read_text())
    assert db.execute("select count(*) from public.dufynd_external_observers").fetchone()[0] == 10


def test_active_waiter_prevents_retirement_atomically(db):
    db.execute(
        "insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status) values ('monitor-test','test','test','test','waiting_external')"
    )
    db.execute(
        "insert into public.dufynd_task_external_waits(task_id,observer_id,event_types,policy,satisfied) values ('monitor-test','github_pr:625','[\"github.pr.merged\"]','dependency',false)"
    )
    with pytest.raises(Exception, match="active consumer"), db.transaction():
        db.execute(SQL.read_text())
    assert (
        db.execute(
            "select count(*) from public.dufynd_external_observers where not enabled"
        ).fetchone()[0]
        == 0
    )


def test_changed_production_baseline_prevents_all_changes(db):
    db.execute(
        "update public.dufynd_external_observers set last_snapshot='{}' where source_type='github_branch'"
    )
    with pytest.raises(Exception, match="baseline changed"), db.transaction():
        db.execute(SQL.read_text())
    assert db.execute("select count(*) from public.dufynd_external_observers").fetchone()[0] == 6


def test_fresh_render_and_existing_target_are_not_rewound(db):
    db.execute(
        "update public.dufynd_external_observers set last_success_at=now() where source_type='render'"
    )
    db.execute(SQL.read_text())
    db.execute(
        "update public.dufynd_external_observers set last_success_at=now(),last_attempt_at=now(),last_cursor='actual-source-cursor',health_status='healthy' where observer_id='github_pr:840'"
    )
    before = db.execute(
        "select last_success_at,last_attempt_at,last_cursor,next_retry_at from public.dufynd_external_observers where observer_id='github_pr:840'"
    ).fetchone()
    db.execute(SQL.read_text())
    assert (
        db.execute(
            "select last_success_at,last_attempt_at,last_cursor,next_retry_at from public.dufynd_external_observers where observer_id='github_pr:840'"
        ).fetchone()
        == before
    )
    assert (
        db.execute(
            "select health_status from public.dufynd_external_observers where source_type='render'"
        ).fetchone()[0]
        == "healthy"
    )
