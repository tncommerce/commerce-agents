"""Read-only aggregation on a disposable localhost DB; no production analytics."""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.dufynd_nightshift_value_v2 import ValueHold, first_money

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated localhost PostgreSQL required")
START = datetime(2026, 10, 13, tzinfo=UTC)
END = datetime(2026, 10, 14, tzinfo=UTC)
SQL = (Path(__file__).resolve().parents[1] / "scripts/dufynd_first_money_value_v2.sql").read_text()


@pytest.fixture
def database():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.sql import SQL, Identifier

    params = conninfo_to_dict(DSN)
    assert params.get("host") in {"localhost", "127.0.0.1", "::1"}
    assert "test" in params.get("dbname", "")
    name = "dufynd_value_test_" + uuid4().hex
    with psycopg.connect(DSN, autocommit=True) as root:
        root.execute(SQL("create database {}").format(Identifier(name)))
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=name), autocommit=True) as c:
            c.execute("""create table public.scentai_analytics_events(
                event_id uuid,session_key text,occurred_at timestamptz,event text,
                traffic_class text,acquisition_source text,source text,campaign_id text)""")
            yield c
    finally:
        with psycopg.connect(DSN, autocommit=True) as root:
            root.execute(SQL("drop database {} with (force)").format(Identifier(name)))


def event(c, session, kind="page_view", traffic="visitor", when="2026-10-13T10:00Z", uid=None):
    c.execute(
        "insert into scentai_analytics_events values(%s,%s,%s,%s,%s,'instagram','instagram','synthetic-test')",
        (uid or uuid4(), session, when, kind, traffic),
    )


def read(c):
    return c.execute(
        SQL.replace("$1", "%(start)s").replace("$2", "%(end)s"), {"start": START, "end": END}
    ).fetchone()[0]


def test_historical_qa_and_bots_never_count_as_eligible_clickouts(database):
    c = database
    event(c, "qa", traffic="qa", when="2026-10-12T10:00Z")
    event(c, "qa", kind="merchant_clickout")
    event(c, "bot", traffic="bot", kind="merchant_clickout")
    event(c, "possible-human", kind="offer_section_view")
    report = read(c)
    assert report["events"] == 3 and report["sessions"] == 3
    assert report["qa_sessions"] == report["bot_sessions"] == 1
    assert report["visitor_unverified_sessions"] == report["social_tagged_sessions"] == 1
    assert report["merchant_clickouts"] == 0 and report["offer_views"] == 1
    assert first_money(report, now=END)["verified_external_visitors"] == "UNKNOWN"


def test_null_identity_or_duplicate_event_is_hold(database):
    uid = uuid4()
    event(database, "same", uid=uid)
    event(database, "same", uid=uid)
    with pytest.raises(ValueHold, match="deduplicated"):
        first_money(read(database), now=END)
    event(database, None)
    with pytest.raises(ValueHold, match="incomplete"):
        first_money(read(database), now=END)


def test_unknown_class_and_exact_window(database):
    event(database, "old", when=START)
    event(database, "future", when="2026-10-15T00:00Z")
    event(database, "unknown", traffic=None, when=END)
    report = read(database)
    assert report["events"] == report["unknown_sessions"] == 1
    assert report["visitor_unverified_sessions"] == 0


def test_no_events_is_not_proof_no_visitors(database):
    report = read(database)
    assert report["complete"] and report["sessions"] == 0
    result = first_money(report, now=END)
    assert result["next_action"] == "OBSERVE_APPROVED_ORGANIC_ENTRY"
    assert result["revenue"] == "UNKNOWN"


def test_read_does_not_create_events(database):
    event(database, "synthetic")
    first = read(database)
    assert read(database) == first
    assert database.execute("select count(*) from scentai_analytics_events").fetchone()[0] == 1
