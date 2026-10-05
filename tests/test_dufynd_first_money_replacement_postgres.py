"""Replacement launch measurement in CI's disposable database only."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated PostgreSQL service required")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def schema():
    if not DSN:
        yield
        return
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("""create table scentai_analytics_events(
          id bigserial primary key,event_id uuid default gen_random_uuid(),occurred_at timestamptz default now(),
          session_key text,event text,product_id text,source text,acquisition_source text,campaign_id text,content_id text);
        """)
        c.execute(
            next(
                (ROOT / "supabase/migrations").glob("*first_money_replacement_measurement.sql")
            ).read_text()
        )
        c.execute(
            "create trigger qa_signal after insert on scentai_analytics_events for each row execute function queue_dufynd_first_money_signal_audit()"
        )
    yield


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as c:
        yield c
        c.rollback()


def replacement(c, **changes):
    value = dict(
        status="replacement_scheduled",
        publishing_authorized=True,
        instagram_auto_publish=True,
        instagram_draft=False,
        owner_publish_approval_source="qa_owner_evidence",
        replacement_content_id="replacement_fixture",
        replacement_experiment_id="replacement_experiment",
        instagram_scheduled_at="2026-01-01T00:00:00Z",
        instagram_state="owner_confirmed_removed",
        tiktok_state="stopped_before_publish",
    )
    value.update(changes)
    c.execute(
        "insert into dufynd_master_status(key,value) values('first_money.social_quality_incident.20261005',%s::jsonb) on conflict(key) do update set value=excluded.value",
        (json.dumps(value),),
    )


def event(
    c,
    *,
    content="replacement_fixture",
    campaign="replacement_experiment",
    channel="instagram",
    source="fragrance_detail_page",
    session="real-session",
    product="SC-RABANNE-1-MILLION-EDT-100",
    kind="page_view",
    occurred="2026-01-02T00:00:00Z",
):
    c.execute(
        "insert into scentai_analytics_events(content_id,campaign_id,acquisition_source,source,session_key,product_id,event,occurred_at) values(%s,%s,%s,%s,%s,%s,%s,%s)",
        (content, campaign, channel, source, session, product, kind, occurred),
    )


def runtime(c):
    return c.execute("select read_dufynd_first_money_runtime()").fetchone()[0]


def test_replacement_only_counts_exact_live_launch_not_history_or_test_traffic(db):
    replacement(db)
    baseline = db.execute(
        "select count(*) from dufynd_autonomy_tasks where task_id like 'first-money-signal:%'"
    ).fetchone()[0]
    event(db, content="removed_original")
    event(db, campaign="wrong_campaign")
    event(db, channel="tiktok")
    event(db, source="production_smoke")
    event(db, session="qa-preview-session")
    event(db, product="SC-OTHER")
    event(db, occurred="2025-12-31T00:00:00Z")
    event(db, occurred="2099-01-01T00:00:00Z")
    assert runtime(db)["funnel"]["landing_sessions"] == 0
    assert (
        db.execute(
            "select count(*) from dufynd_autonomy_tasks where task_id like 'first-money-signal:%'"
        ).fetchone()[0]
        == baseline
    )
    for kind in (
        "page_view",
        "fragrance_detail_view",
        "offer_section_view",
        "offer_section_open",
        "merchant_clickout",
    ):
        event(db, kind=kind)
    r = runtime(db)
    assert r["version"] == 3 and r["content_id"] == "replacement_fixture"
    assert (
        r["funnel"]["landing_sessions"]
        == r["funnel"]["product_views"]
        == r["funnel"]["merchant_clickouts"]
        == 1
    )
    assert r["phase"] != "schedule_unknown"  # One active platform is enough.
    assert r["sales_truth"]["clickout_is_sale"] is False
    assert r["sales_truth"]["transactions"] == "external_network_evidence_required"
    assert (
        db.execute(
            "select count(*) from dufynd_autonomy_tasks where task_id like 'first-money-signal:%'"
        ).fetchone()[0]
        == baseline + 1
    )


def test_prelaunch_zero_is_measured_and_unapproved_replacement_has_no_old_fallback(db):
    replacement(db, instagram_scheduled_at="2099-01-01T00:00:00Z")
    event(db)
    assert runtime(db)["phase"] == "prelaunch"
    assert runtime(db)["funnel"]["landing_sessions"] == 0
    replacement(db, publishing_authorized=False)
    assert db.execute("select dufynd_first_money_measurement_target()").fetchone()[0] == {}
    assert runtime(db)["content_id"] is None
    assert runtime(db)["phase"] == "schedule_unknown"
