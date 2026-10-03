"""Privilege/session checks against CI's disposable PostgreSQL, never production."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated PostgreSQL service required")


@pytest.fixture(scope="module", autouse=True)
def schema():
    if not DSN:
        yield
        return
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("""
          do $$ begin
            if not exists(select from pg_roles where rolname='anon') then create role anon; end if;
            if not exists(select from pg_roles where rolname='authenticated') then create role authenticated; end if;
            if not exists(select from pg_roles where rolname='service_role') then create role service_role; end if;
          end $$;
          create schema auth;
          create table auth.users(id uuid primary key, email_confirmed_at timestamptz,
            deleted_at timestamptz, banned_until timestamptz, is_anonymous boolean default false);
          create table auth.sessions(id uuid primary key, user_id uuid, not_after timestamptz);
          create function auth.jwt() returns jsonb language sql stable as $$
            select nullif(current_setting('request.jwt.claims',true),'')::jsonb
          $$;
          create function auth.uid() returns uuid language sql stable as $$
            select (auth.jwt()->>'sub')::uuid
          $$;
        """)
        migration = next(
            (Path(__file__).resolve().parents[1] / "supabase/migrations").glob(
                "*dufynd_control_room_owner_session.sql"
            )
        )
        c.execute(migration.read_text())
    yield


@pytest.mark.parametrize(
    "condition,expected",
    [
        ("valid", True),
        ("other_user", False),
        ("other_session", False),
        ("expired", False),
        ("revoked", False),
        ("deleted", False),
        ("banned", False),
        ("unconfirmed", False),
        ("anonymous", False),
    ],
)
def test_live_session_conditions(condition, expected):
    import psycopg

    owner, session = str(uuid4()), str(uuid4())
    with psycopg.connect(DSN) as c:
        c.execute("insert into auth.users(id,email_confirmed_at) values(%s,now())", (owner,))
        c.execute(
            "insert into auth.sessions values(%s,%s,now()+interval '1 hour')", (session, owner)
        )
        if condition == "expired":
            c.execute(
                "update auth.sessions set not_after=now()-interval '1 second' where id=%s",
                (session,),
            )
        if condition == "revoked":
            c.execute("delete from auth.sessions where id=%s", (session,))
        updates = {
            "deleted": "deleted_at=now()",
            "banned": "banned_until=now()+interval '1 hour'",
            "unconfirmed": "email_confirmed_at=null",
            "anonymous": "is_anonymous=true",
        }
        if condition in updates:
            c.execute("update auth.users set " + updates[condition] + " where id=%s", (owner,))
        claims = {
            "sub": str(uuid4()) if condition == "other_user" else owner,
            "session_id": str(uuid4()) if condition == "other_session" else session,
        }
        c.execute("select set_config('request.jwt.claims',%s,true)", (json.dumps(claims),))
        c.execute("set local role authenticated")
        assert (
            c.execute("select public.dufynd_dashboard_owner_session(%s)", (session,)).fetchone()[0]
            is expected
        )
        c.rollback()


@pytest.mark.parametrize("role", ["anon", "service_role"])
def test_unprivileged_roles_cannot_execute(role):
    import psycopg

    with psycopg.connect(DSN) as c:
        c.execute("set local role " + role)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select public.dufynd_dashboard_owner_session(%s)", (str(uuid4()),))
        c.rollback()


def test_authenticated_has_no_raw_auth_table_access():
    import psycopg

    with psycopg.connect(DSN) as c:
        c.execute("set local role authenticated")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select * from auth.sessions")
        c.rollback()
