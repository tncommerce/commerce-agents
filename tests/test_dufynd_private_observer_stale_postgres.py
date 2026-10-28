"""A cron tick cannot preserve stale private observations as healthy."""

import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20261028081434_jarvis_private_observer_stale_truth.sql"
)


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as connection:
        try:
            # Earlier PostgreSQL modules install a simplified net stub. These
            # cases deliberately exercise the no-transport freshness path.
            # Preserve its objects/OIDs and restore its name on rollback.
            connection.execute(
                """do $fixture$
                begin
                  if to_regnamespace('dufynd_stale_fixture_net') is not null then
                    raise exception 'stale fixture isolation schema already exists';
                  end if;
                  if to_regnamespace('net') is not null then
                    alter schema net rename to dufynd_stale_fixture_net;
                  end if;
                end;
                $fixture$;"""
            )
            connection.execute(MIGRATION.read_text())
            connection.execute("update public.dufynd_external_observers set enabled=false")
            yield connection
        finally:
            connection.rollback()


@pytest.mark.parametrize(
    "kind,identity",
    [("render", "srv-testfreshness"), ("gmail", "aaaaaaaaaaaaaaaa"), ("github_pr", "909090")],
)
def test_poll_marks_old_success_stale_and_preserves_original_source_evidence(db, kind, identity):
    observer = kind + ":" + identity
    db.execute("select public.register_dufynd_observer(%s,%s)", (kind, identity))
    db.execute(
        "update public.dufynd_external_observers set last_success_at=now()-interval '6 days',last_attempt_at=now()-interval '6 days',last_cursor='original',last_snapshot='{\"sha\":\"original\"}',health_status='healthy' where observer_id=%s",
        (observer,),
    )
    before = db.execute(
        "select last_success_at,last_attempt_at,last_cursor,last_snapshot from public.dufynd_external_observers where observer_id=%s",
        (observer,),
    ).fetchone()
    assert db.execute("select public.poll_dufynd_observers()").fetchone()[0] == {"available": False}
    after = db.execute(
        "select last_success_at,last_attempt_at,last_cursor,last_snapshot from public.dufynd_external_observers where observer_id=%s",
        (observer,),
    ).fetchone()
    assert after == before
    assert db.execute(
        "select health_status,last_error from public.dufynd_external_observers where observer_id=%s",
        (observer,),
    ).fetchone() == ("stale", "observer_success_stale")


@pytest.mark.parametrize(
    "health,fresh,enabled,expected",
    [
        ("healthy", True, True, "healthy"),
        ("blocked_configuration", False, True, "blocked_configuration"),
        ("healthy", False, False, "healthy"),
    ],
)
def test_fresh_blocked_and_disabled_states_are_not_misrepresented(
    db, health, fresh, enabled, expected
):
    observer = "render:srv-testguard"
    db.execute("select public.register_dufynd_observer('render','srv-testguard')")
    db.execute(
        "update public.dufynd_external_observers set health_status=%s,enabled=%s,last_success_at=now()-make_interval(secs=>%s) where observer_id=%s",
        (health, enabled, 0 if fresh else 86400, observer),
    )
    db.execute("select public.poll_dufynd_observers()")
    assert (
        db.execute(
            "select health_status from public.dufynd_external_observers where observer_id=%s",
            (observer,),
        ).fetchone()[0]
        == expected
    )


def test_patch_preserves_restricted_execute_privileges(db):
    result = db.execute(
        "select has_function_privilege('anon','public.poll_dufynd_observers()','execute'),has_function_privilege('authenticated','public.poll_dufynd_observers()','execute'),has_function_privilege('service_role','public.poll_dufynd_observers()','execute')"
    ).fetchone()
    assert result == (False, False, True)
