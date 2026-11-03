"""The owner pause controls alert wording, never credentials or recovery evidence."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "supabase/migrations"
MIGRATION = SQL / "20261029100518_dufynd_gmail_recovery_pause_projection.sql"
OLD = SQL / "20261010081755_gmail_owner_gate_persistence.sql"
KEY = "jarvis.private_observer_scheduler_v1"


def function_sql(path, name):
    source = path.read_text()
    match = re.search(
        rf"create(?:\s+or\s+replace)?\s+function\s+public\.{name}\s*\(.*?\bas\s+(\$[a-z_]*\$)",
        source,
        re.I | re.S,
    )
    assert match
    end = source.index(match[1], match.end()) + len(match[1])
    return (
        source[match.start() : end].replace("create function", "create or replace function") + ";"
    )


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as connection:
        try:
            connection.execute("SET LOCAL statement_timeout='10s'")
            connection.execute("""
                DO $fixture$ BEGIN
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role; END IF;
                END $fixture$;
                CREATE TABLE IF NOT EXISTS public.dufynd_master_status(
                  key text primary key,category text,value jsonb,priority int,last_verified_at timestamptz);
                CREATE TABLE IF NOT EXISTS public.dufynd_observer_credentials(
                  credential_id text primary key,provider text,account_alias text,allowed_operations jsonb,
                  allowed_resources jsonb,oauth_scopes jsonb,secret_reference text,status text,
                  expires_at timestamptz,refreshed_at timestamptz,revoked_at timestamptz,
                  last_health_check timestamptz,rotation_due_at timestamptz,health_reason text,
                  activation_enabled boolean);
                CREATE TABLE IF NOT EXISTS public.dufynd_external_observers(
                  observer_id text primary key,source_type text,source_id text,enabled boolean,
                  interval_seconds int,health_status text,last_success_at timestamptz,last_snapshot jsonb);
                DELETE FROM public.dufynd_master_status WHERE key IN
                  ('ops.gmail_observer.alert_v1','ops.private_observer.last_failure',
                   'ops.gmail_observer_expiration_incident_20261010','jarvis.private_observer_scheduler_v1');
                INSERT INTO public.dufynd_observer_credentials
                  (credential_id,provider,account_alias,allowed_operations,allowed_resources,oauth_scopes,
                   secret_reference,status,health_reason,revoked_at,refreshed_at,expires_at,activation_enabled)
                VALUES('gmail_known_threads','gmail','dufynd_owner_mailbox','["thread.metadata","history.read"]',
                  '["1a0f385ed98c6af8","1a0f69c169fb928f","1a0f6a90772a743d"]',
                  '["https://www.googleapis.com/auth/gmail.metadata"]','dufynd_observer_gmail_read_access_token',
                  'revoked','revoked',now()-interval '2 hours',now()-interval '3 hours',
                  now()-interval '2 hours',true)
                ON CONFLICT(credential_id) DO UPDATE SET status='revoked',health_reason='revoked',
                  revoked_at=excluded.revoked_at,refreshed_at=excluded.refreshed_at,
                  expires_at=excluded.expires_at,activation_enabled=true;
                CREATE TEMP TABLE gmail_pause_case(owner_gate boolean);
                INSERT INTO pg_temp.gmail_pause_case VALUES(false);
                CREATE OR REPLACE FUNCTION public.audit_dufynd_integrity_v1()
                RETURNS jsonb LANGUAGE plpgsql SET search_path='public' AS $fixture$
                DECLARE report jsonb;
                BEGIN
                  SELECT jsonb_build_object('status','degraded','issues',jsonb_build_array('private_observer_stale'),
                    'owner_action_required',owner_gate) INTO report FROM pg_temp.gmail_pause_case;
                  INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
                  VALUES('jarvis.integrity_v1','jarvis',report,100,now())
                  ON CONFLICT(key) DO UPDATE SET value=excluded.value,last_verified_at=excluded.last_verified_at;
                  RETURN report;
                END $fixture$;
            """)
            for identity in ("1a0f385ed98c6af8", "1a0f69c169fb928f", "1a0f6a90772a743d"):
                connection.execute(
                    """INSERT INTO public.dufynd_external_observers
                    (observer_id,source_type,source_id,enabled,interval_seconds,health_status,last_success_at)
                    VALUES(%s,'gmail',%s,true,120,'blocked_configuration',now()-interval '2 hours')
                    ON CONFLICT(observer_id) DO UPDATE SET enabled=true,health_status='blocked_configuration',
                      last_success_at=excluded.last_success_at""",
                    ("gmail:" + identity, identity),
                )
            connection.execute(
                function_sql(
                    SQL / "20261002161040_dufynd_observer_credential_plane.sql",
                    "get_dufynd_credential_health",
                )
            )
            connection.execute(
                function_sql(
                    SQL / "20261002064614_dufynd_supervisor_v2_phase1.sql", "dufynd_parse_timestamp"
                )
            )
            connection.execute(MIGRATION.read_text())
            yield connection
        finally:
            connection.rollback()


def policy(db, value=None, timestamp="now()"):
    value = (
        value
        if value is not None
        else {"gmail_recovery_paused": True, "owner_action_required": False}
    )
    assert timestamp in (
        "now()",
        "now()-interval '30 days'",
        "now()+interval '1 second'",
        "'infinity'",
        "NULL",
    )
    db.execute(
        f"""INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
        VALUES(%s,'jarvis',%s::jsonb,100,{timestamp})
        ON CONFLICT(key) DO UPDATE SET value=excluded.value,last_verified_at=excluded.last_verified_at""",
        (KEY, json.dumps(value)),
    )


def alert(db):
    return db.execute("SELECT public.reconcile_dufynd_gmail_health_v1()").fetchone()[0]


def test_old_alert_reproduces_ignored_owner_pause_then_new_projection_preserves_incident(db):
    policy(db)
    db.execute(OLD.read_text())
    before = alert(db)
    assert before["owner_action_required"] is True
    db.execute(MIGRATION.read_text())
    after = alert(db)
    assert after["owner_action_required"] is False
    assert after["reauthorization_required"] is True
    assert after["recovery_paused"] is True
    assert after["state"] == before["state"] == "credential_revoked"
    assert after["credential"] == before["credential"]
    assert after["dedup_key"] == before["dedup_key"]
    assert after["first_seen_at"] == before["first_seen_at"]
    assert after["fresh_successes"] == 0
    assert after["email_sent"] is False
    assert "POST" not in after["action"]
    assert after["pause_policy_source"] == KEY


def test_no_pause_record_preserves_the_existing_owner_gate(db):
    result = alert(db)
    assert result["recovery_paused"] is False
    assert result["owner_action_required"] is True
    assert result["reauthorization_required"] is True


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"gmail_recovery_paused": "true", "owner_action_required": False},
        {"gmail_recovery_paused": 1, "owner_action_required": False},
        {"gmail_recovery_paused": True, "owner_action_required": True},
        {"gmail_recovery_paused": True},
        {"gmail_recovery_paused": False, "owner_action_required": False},
        [],
        "true",
    ],
)
def test_absent_malformed_or_conflicting_pause_does_not_hide_owner_gate(db, value):
    policy(db, value)
    result = alert(db)
    assert result["recovery_paused"] is False
    assert result["owner_action_required"] is True
    assert result["state"] == "credential_revoked"


@pytest.mark.parametrize("timestamp", ["now()+interval '1 second'", "'infinity'", "NULL"])
def test_invalid_policy_time_cannot_suppress_the_current_gate(db, timestamp):
    policy(db, timestamp=timestamp)
    assert alert(db)["owner_action_required"] is True


def test_explicit_pause_does_not_expire_into_an_automatic_login_request(db):
    policy(db, timestamp="now()-interval '30 days'")
    assert alert(db)["owner_action_required"] is False
    policy(db, {"gmail_recovery_paused": False, "owner_action_required": False})
    assert alert(db)["owner_action_required"] is True


def test_pause_changes_no_credential_or_observer_evidence(db):
    policy(db)
    query = "SELECT (SELECT jsonb_agg(to_jsonb(c)) FROM public.dufynd_observer_credentials c),(SELECT jsonb_agg(to_jsonb(o)) FROM public.dufynd_external_observers o)"
    before = db.execute(query).fetchone()
    alert(db)
    alert(db)
    assert db.execute(query).fetchone() == before


def test_expired_token_with_pause_stays_expired_without_false_reauthorization(db):
    policy(db)
    db.execute(
        "UPDATE public.dufynd_observer_credentials SET revoked_at=null,status='healthy',health_reason='healthy' WHERE provider='gmail'"
    )
    result = alert(db)
    assert result["state"] == "credential_expired"
    assert result["reauthorization_required"] is False
    assert result["owner_action_required"] is False
    assert result["recovery_paused"] is True


def test_real_recovery_still_requires_credential_health_and_three_new_reads(db):
    policy(db)
    db.execute(
        "UPDATE public.dufynd_observer_credentials SET revoked_at=null,status='healthy',health_reason='healthy',expires_at=now()+interval '1 hour',refreshed_at=now()-interval '1 minute' WHERE provider='gmail'"
    )
    assert alert(db)["state"] == "gmail_observer_stale"
    db.execute(
        "UPDATE public.dufynd_external_observers SET health_status='healthy',last_success_at=now() WHERE source_type='gmail'"
    )
    result = alert(db)
    assert result["state"] == "recovered"
    assert result["fresh_successes"] == 3
    assert result["reauthorization_required"] is False
    assert result["owner_action_required"] is False


@pytest.mark.parametrize("other_gate", [False, True])
def test_recurring_wrapper_retains_unrelated_owner_gates_and_degraded_state(db, other_gate):
    policy(db)
    db.execute("UPDATE pg_temp.gmail_pause_case SET owner_gate=%s", (other_gate,))
    result = db.execute("SELECT public.audit_dufynd_integrity_with_gmail_v1()").fetchone()[0]
    assert result["owner_action_required"] is other_gate
    assert result["gmail_recovery_paused"] is True
    assert result["gmail_reauthorization_required"] is True
    assert result["gmail_alert"]["owner_action_required"] is False
    assert result["status"] == "degraded"
    assert result["issues"] == ["private_observer_stale"]
    stored = db.execute(
        "SELECT value FROM public.dufynd_master_status WHERE key='jarvis.integrity_v1'"
    ).fetchone()[0]
    assert stored == result


def test_private_acl_and_idempotent_application(db):
    db.execute(MIGRATION.read_text())
    for name in ("reconcile_dufynd_gmail_health_v1", "audit_dufynd_integrity_with_gmail_v1"):
        for role in ("anon", "authenticated"):
            assert not db.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, "public." + name + "()")
            ).fetchone()[0]
        assert db.execute(
            "SELECT has_function_privilege('service_role',%s,'EXECUTE')", ("public." + name + "()",)
        ).fetchone()[0]
        row = db.execute(
            "SELECT prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure",
            ("public." + name + "()",),
        ).fetchone()
        assert row == (False, ["search_path=public"])
