"""CONSENT-26 analytics retention against CI's disposable PostgreSQL only."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated PostgreSQL service required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261015180054_dufynd_analytics_retention_v1.sql"


@pytest.fixture(scope="module", autouse=True)
def schema():
    if not DSN:
        yield
        return

    import psycopg

    with psycopg.connect(DSN, autocommit=True) as connection:
        for role in ("anon", "authenticated", "service_role"):
            connection.execute(
                f"""
                do $$
                begin
                  if not exists(select 1 from pg_roles where rolname='{role}') then
                    create role {role} nologin;
                  end if;
                end
                $$;
                """
            )
        # This service database is ephemeral. Recreate only the analytics table
        # so the retention migration is exercised against its exact contract.
        connection.execute("drop table if exists public.scentai_analytics_events cascade")
        connection.execute(
            """
            create table public.scentai_analytics_events(
              id bigserial primary key,
              event_id uuid not null default gen_random_uuid(),
              occurred_at timestamptz not null,
              session_key text not null default 'qa-session',
              event text not null default 'page_view',
              traffic_class text not null
                check(traffic_class in ('visitor','internal_qa','unclassified'))
            )
            """
        )
        connection.execute(MIGRATION.read_text(encoding="utf-8"))
    yield


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as connection:
        yield connection
        connection.rollback()


def insert_event(db, traffic_class: str, occurred_at: str) -> None:
    db.execute(
        """
        insert into public.scentai_analytics_events(traffic_class, occurred_at)
        values(%s, %s::timestamptz)
        """,
        (traffic_class, occurred_at),
    )


def test_retention_boundaries_and_idempotency(db):
    now = "2026-10-15T12:00:00Z"
    rows = [
        ("visitor", "2026-07-16T11:59:59Z", False),
        ("visitor", "2026-07-17T12:00:00Z", True),
        ("visitor", "2026-10-15T11:00:00Z", True),
        ("internal_qa", "2026-09-15T11:59:59Z", False),
        ("internal_qa", "2026-09-15T12:00:00Z", True),
        ("unclassified", "2026-09-15T11:59:59Z", False),
        ("unclassified", "2026-10-01T12:00:00Z", True),
    ]
    for traffic_class, occurred_at, _keep in rows:
        insert_event(db, traffic_class, occurred_at)

    result = db.execute(
        "select public.purge_dufynd_analytics_retention(%s::timestamptz)",
        (now,),
    ).fetchone()[0]

    assert result["visitor_retention_days"] == 90
    assert result["diagnostic_retention_days"] == 30
    assert result["deleted_visitor"] == 1
    assert result["deleted_internal_qa"] == 1
    assert result["deleted_unclassified"] == 1
    assert result["deleted_total"] == 3

    remaining = db.execute(
        """
        select traffic_class, occurred_at::text
        from public.scentai_analytics_events
        order by occurred_at, traffic_class
        """
    ).fetchall()
    assert len(remaining) == 4
    assert {row[0] for row in remaining} == {"visitor", "internal_qa", "unclassified"}

    again = db.execute(
        "select public.purge_dufynd_analytics_retention(%s::timestamptz)",
        (now,),
    ).fetchone()[0]
    assert again["deleted_total"] == 0


def test_retention_function_is_not_publicly_executable(db):
    assert db.execute(
        """
        select has_function_privilege(
          'service_role',
          'public.purge_dufynd_analytics_retention(timestamp with time zone)',
          'execute'
        )
        """
    ).fetchone()[0]
    assert not db.execute(
        """
        select has_function_privilege(
          'anon',
          'public.purge_dufynd_analytics_retention(timestamp with time zone)',
          'execute'
        )
        """
    ).fetchone()[0]
    assert not db.execute(
        """
        select has_function_privilege(
          'authenticated',
          'public.purge_dufynd_analytics_retention(timestamp with time zone)',
          'execute'
        )
        """
    ).fetchone()[0]
