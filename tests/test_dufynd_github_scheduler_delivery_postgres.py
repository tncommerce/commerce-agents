"""Real PostgreSQL scheduler-delivery contracts; all HTTP is a local queue stub."""

from __future__ import annotations

import copy
import json
import os
from datetime import timedelta
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261029115518_dufynd_github_scheduler_delivery_monitor.sql"
KEY = "ops.github_scheduler_delivery_v1"
WORKFLOWS = {"reader": 373752411, "watchdog": 377395476}
PATHS = {
    "reader": ".github/workflows/dufynd-private-observer.yml",
    "watchdog": ".github/workflows/dufynd-private-observer-watchdog.yml",
}
ISSUE = "github_scheduler_"


def install_monitor(db):
    """Install only the new monitor into an existing disposable PG/net fixture."""
    db.execute("delete from public.dufynd_master_status where key=%s", (KEY,))
    db.execute(MIGRATION.read_text())


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as connection:
        try:
            connection.execute("set local statement_timeout='10s'")
            connection.execute("set local timezone='UTC'")
            connection.execute("""
                DO $fixture$ BEGIN
                  IF to_regnamespace('dufynd_scheduler_fixture_net') IS NOT NULL THEN
                    RAISE EXCEPTION 'scheduler test schema already exists';
                  END IF;
                  IF to_regnamespace('net') IS NOT NULL THEN
                    ALTER SCHEMA net RENAME TO dufynd_scheduler_fixture_net;
                  END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
                  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role; END IF;
                END $fixture$;
                CREATE TABLE IF NOT EXISTS public.dufynd_master_status(
                  key text primary key,category text,value jsonb,priority integer,last_verified_at timestamptz);
                ALTER TABLE public.dufynd_master_status ENABLE ROW LEVEL SECURITY;
                REVOKE ALL ON public.dufynd_master_status FROM PUBLIC,anon,authenticated;
                CREATE SCHEMA net;
                CREATE TABLE net.http_request_queue(
                  id bigserial primary key,url text,headers jsonb,timeout_milliseconds integer);
                CREATE TABLE net._http_response(
                  id bigint,status_code integer,content_type text,content text,headers jsonb,
                  timed_out boolean,error_msg text,created timestamptz);
                CREATE TABLE net.test_request_calls(id bigint,url text,headers jsonb,requested_at timestamptz);
                CREATE FUNCTION net.http_get(url text,headers jsonb,timeout_milliseconds integer)
                RETURNS bigint LANGUAGE plpgsql AS $stub$
                DECLARE rid bigint;
                BEGIN
                  INSERT INTO net.http_request_queue(url,headers,timeout_milliseconds)
                  VALUES(url,headers,timeout_milliseconds) RETURNING id INTO rid;
                  INSERT INTO net.test_request_calls VALUES(rid,url,headers,clock_timestamp());
                  RETURN rid;
                END $stub$;
            """)
            install_monitor(connection)
            yield connection
        finally:
            connection.rollback()


def stored(db):
    return db.execute(
        "select value from public.dufynd_master_status where key=%s", (KEY,)
    ).fetchone()[0]


def save(db, value):
    db.execute(
        "update public.dufynd_master_status set value=%s::jsonb where key=%s",
        (json.dumps(value), KEY),
    )


def enable_monitor(db):
    value = stored(db)
    value["enabled"] = True
    save(db, value)


def poll(db):
    return db.execute("select public.poll_dufynd_github_scheduler_delivery_v1()").fetchone()[0]


def read(db):
    return db.execute("select public.read_dufynd_github_scheduler_delivery_v1()").fetchone()[0]


def now(db):
    return db.execute("select clock_timestamp()").fetchone()[0]


def run_body(
    db,
    target="reader",
    *,
    age_seconds=60,
    attempt=1,
    status="completed",
    conclusion="success",
    run_id=None,
):
    stamp = now(db)
    created = stamp - timedelta(seconds=age_seconds)
    repo = {
        "id": 1367576041,
        "full_name": "tncommerce/commerce-agents",
        "name": "commerce-agents",
        "owner": {"id": 324597697, "login": "tncommerce"},
        "private": False,
    }
    run = {
        "id": run_id or (40834260621 if target == "reader" else 40837134023),
        "workflow_id": WORKFLOWS[target],
        "path": PATHS[target],
        "repository": repo,
        "head_repository": copy.deepcopy(repo),
        "head_branch": "main",
        "event": "schedule",
        "head_sha": "37727be7994ebb3fc3881f8adb06d8596774e2ad",
        "created_at": created.isoformat(),
        "run_started_at": (stamp - timedelta(seconds=1)).isoformat(),
        "updated_at": stamp.isoformat(),
        "run_attempt": attempt,
        "status": status,
        "conclusion": conclusion,
    }
    return {"total_count": 1, "workflow_runs": [run]}


def respond(
    db,
    target="reader",
    *,
    body=None,
    status=200,
    headers=None,
    content_type="application/json; charset=utf-8",
    timed_out=False,
    error=None,
    created="clock_timestamp()",
):
    rid = stored(db)["schedules"][target]["request_id"]
    if body is None:
        body = run_body(db, target)
    if not isinstance(body, str):
        body = json.dumps(body)
    db.execute("delete from net.http_request_queue where id=%s", (rid,))
    db.execute(
        "insert into net._http_response(id,status_code,content_type,content,headers,timed_out,error_msg,created) "
        f"values(%s,%s,%s,%s,%s::jsonb,%s,%s,{created})",
        (rid, status, content_type, body, json.dumps(headers or {}), timed_out, error),
    )
    return rid


def elapse_budget(db, seconds=601):
    """Move only fixture request-budget clocks; preserve all actual receipts/run times."""
    value = stored(db)
    stamp = now(db)
    value["budget"]["last_attempt_at"] = (stamp - timedelta(seconds=seconds)).isoformat()
    value["budget"]["next_poll_at"] = (stamp - timedelta(seconds=1)).isoformat()
    for target in WORKFLOWS:
        t = value["schedules"][target]
        if "last_attempt_at" in t:
            t["last_attempt_at"] = (stamp - timedelta(seconds=seconds)).isoformat()
    save(db, value)


def observe_both(db, *, reader_body=None, watchdog_body=None):
    """Exercise real poller + two real SQL receipts; reusable by integration tests."""
    enable_monitor(db)
    poll(db)
    respond(db, "reader", body=reader_body)
    poll(db)
    elapse_budget(db)
    poll(db)
    respond(db, "watchdog", body=watchdog_body)
    return poll(db)


def test_disabled_is_unknown_and_does_not_write_or_request(db):
    before = db.execute(
        "select value,last_verified_at from public.dufynd_master_status where key=%s", (KEY,)
    ).fetchone()
    result = poll(db)
    assert result["status"] == "disabled" and result["delivery_gap"] is None
    assert result["issues"] == [ISSUE + "observation_unavailable"]
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 0
    assert (
        before
        == db.execute(
            "select value,last_verified_at from public.dufynd_master_status where key=%s", (KEY,)
        ).fetchone()
    )


def test_actual_receipts_classify_current_window_without_capture_or_cadence_claim(db):
    result = observe_both(db)
    assert result["healthy"] and result["status"] == "healthy", result
    assert result["delivery_gap"] is False and result["dispatch_status"] == "success"
    assert result["issues"] == []
    for name in (
        "private_observer_evidence",
        "full_chain_complete",
        "business_success",
        "capture_verified",
        "cadence_guarantee",
        "downstream_dispatch_verified",
        "final_origin_verified",
        "redirect_chain_verified",
    ):
        assert result[name] is False
    assert result["dispatch_status_basis"] == "github_workflow_run_conclusion"
    for target in WORKFLOWS:
        value = stored(db)["schedules"][target]
        receipt = db.execute(
            "select created from net._http_response where id=%s", (value["receipt_id"],)
        ).fetchone()[0]
        assert db.execute(
            "select %s::timestamptz=%s::timestamptz", (value["observed_at"], receipt)
        ).fetchone()[0]
        assert result["schedules"][target]["transport_status"] == "fresh"
        assert value["snapshot"]["workflow_runs"][0]["event"] == "schedule"


def test_request_scope_serial_budget_fairness_and_no_credentials(db):
    enable_monitor(db)
    poll(db)
    for _ in range(4):
        poll(db)
    calls = db.execute("select url,headers from net.test_request_calls order by id").fetchall()
    assert len(calls) == 1
    assert (
        calls[0][0]
        == "https://api.github.com/repos/tncommerce/commerce-agents/actions/workflows/373752411/runs?branch=main&event=schedule&per_page=1"
    )
    assert set(calls[0][1]) == {"Accept", "User-Agent", "X-GitHub-Api-Version"}
    respond(db)
    poll(db)
    # The per-target gate prevents a malformed preference from repolling reader.
    elapse_budget(db, 301)
    value = stored(db)
    value["budget"]["next_target"] = "reader"
    save(db, value)
    poll(db)
    assert (
        db.execute("select url from net.test_request_calls order by id desc limit 1")
        .fetchone()[0]
        .endswith("377395476/runs?branch=main&event=schedule&per_page=1")
    )
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 2


@pytest.mark.parametrize(
    "reader_age,watchdog_age,status,delivery,gap",
    [
        (1490, 1490, "healthy", "available", False),
        (1510, 1490, "degraded", "degraded", False),
        (1490, 1510, "degraded", "degraded", False),
        (1510, 1510, "gap", "gap", True),
        (14400, 14400, "gap", "gap", True),
    ],
)
def test_delivery_uses_immutable_created_time_not_fresh_transport(
    db, reader_age, watchdog_age, status, delivery, gap
):
    result = observe_both(
        db,
        reader_body=run_body(db, age_seconds=reader_age),
        watchdog_body=run_body(db, "watchdog", age_seconds=watchdog_age),
    )
    assert result["status"] == status and result["delivery_status"] == delivery
    assert result["delivery_gap"] is gap
    assert result["transport_status"] == "fresh"


def test_fresh_manual_or_rerun_cannot_clear_natural_gap(db):
    result = observe_both(
        db,
        reader_body=run_body(db, age_seconds=14400, attempt=2),
        watchdog_body=run_body(db, "watchdog", age_seconds=14400, attempt=4),
    )
    assert result["delivery_gap"] is True
    assert result["dispatch_status"] == "unknown"
    assert ISSUE + "dispatch_unverified" in result["issues"]
    # A manual run at the correct workflow/ref is still not natural evidence.
    elapse_budget(db)
    poll(db)
    body = run_body(db)
    body["workflow_runs"][0]["event"] = "workflow_dispatch"
    respond(db, body=body)
    result = poll(db)
    assert result["healthy"] is False and result["delivery_gap"] is None
    assert stored(db)["schedules"]["reader"]["last_error"] == "run_identity_rejected"


@pytest.mark.parametrize(
    "status,conclusion,attempt,expected",
    [
        ("completed", "failure", 1, "failed"),
        ("completed", "cancelled", 1, "failed"),
        ("completed", "skipped", 1, "failed"),
        ("queued", None, 1, "pending"),
        ("in_progress", None, 1, "pending"),
        ("completed", "success", 2, "unknown"),
    ],
)
def test_delivery_and_reported_workflow_outcome_are_independent(
    db, status, conclusion, attempt, expected
):
    result = observe_both(
        db, reader_body=run_body(db, status=status, conclusion=conclusion, attempt=attempt)
    )
    assert result["delivery_status"] == "available" and result["delivery_gap"] is False
    assert result["status"] == "degraded" and result["healthy"] is False
    assert result["dispatch_status"] == expected


def test_empty_natural_lists_are_observed_gap_not_unknown(db):
    empty = {"total_count": 0, "workflow_runs": []}
    result = observe_both(db, reader_body=empty, watchdog_body=empty)
    assert result["delivery_gap"] is True and result["transport_status"] == "fresh"
    assert result["latest_natural_created_at"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "40834260621"),
        ("id", -1),
        ("id", 1.5),
        ("id", 10**19),
        ("workflow_id", 377395476),
        ("workflow_id", "373752411"),
        ("path", PATHS["watchdog"]),
        ("head_branch", "scentai-mvp"),
        ("event", "workflow_dispatch"),
        ("event", "push"),
        ("head_sha", "a" * 39),
        ("head_sha", 123),
        ("run_attempt", 0),
        ("run_attempt", "1"),
        ("run_attempt", True),
        ("repository", {"full_name": "attacker/commerce-agents"}),
        ("head_repository", {"full_name": "attacker/commerce-agents"}),
    ],
)
def test_provider_identity_is_checked_after_endpoint_filtering(db, field, value):
    enable_monitor(db)
    poll(db)
    body = run_body(db)
    body["workflow_runs"][0][field] = value
    respond(db, body=body)
    assert poll(db)["healthy"] is False
    assert stored(db)["schedules"]["reader"]["last_error"] == "run_identity_rejected"


@pytest.mark.parametrize(
    "repo,field,value",
    [
        ("repository", "id", 1367576042),
        ("repository", "id", "1367576041"),
        ("head_repository", "id", 1367576042),
        ("head_repository", "owner_id", "324597697"),
        ("repository", "owner_id", 324597698),
        ("repository", "owner_login", "foreign-owner"),
        ("head_repository", "private", True),
        ("repository", "private", "false"),
    ],
)
def test_repository_and_owner_numeric_identity_survive_name_reuse(db, repo, field, value):
    enable_monitor(db)
    poll(db)
    body = run_body(db)
    repository = body["workflow_runs"][0][repo]
    if field.startswith("owner_"):
        repository["owner"][field.removeprefix("owner_")] = value
    else:
        repository[field] = value
    respond(db, body=body)
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "run_identity_rejected"


@pytest.mark.parametrize(
    "field,value",
    [
        ("created_at", "infinity"),
        ("created_at", "2026-10-29T10:00:00+99:99"),
        ("created_at", "2026-02-30T10:00:00Z"),
        ("created_at", "2026-10-29 10:00:00"),
        ("created_at", 123),
        ("created_at", None),
        ("run_started_at", "+infinity"),
        ("run_started_at", None),
        ("updated_at", "infinity"),
        ("updated_at", []),
    ],
)
def test_bad_run_times_are_diagnostic_not_function_abort(db, field, value):
    enable_monitor(db)
    poll(db)
    body = run_body(db)
    body["workflow_runs"][0][field] = value
    respond(db, body=body)
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "run_time_rejected"


@pytest.mark.parametrize(
    "field,seconds",
    [
        ("created_at", 30),
        ("run_started_at", 30),
        ("updated_at", 30),
        ("updated_at", -3600),
        ("run_started_at", -3600),
    ],
)
def test_run_times_cannot_be_future_or_precreation(db, field, seconds):
    enable_monitor(db)
    poll(db)
    body = run_body(db)
    body["workflow_runs"][0][field] = (now(db) + timedelta(seconds=seconds)).isoformat()
    respond(db, body=body)
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "run_time_rejected"


@pytest.mark.parametrize(
    "body,error",
    [
        ({"total_count": 0, "workflow_runs": [{}]}, "run_list_rejected"),
        ({"total_count": 1, "workflow_runs": []}, "run_list_rejected"),
        ({"total_count": 2, "workflow_runs": [{}, {}]}, "run_list_rejected"),
        ({"total_count": "1", "workflow_runs": []}, "run_list_rejected"),
        ({"total_count": 1, "workflow_runs": {}}, "run_list_rejected"),
        ([], "run_list_rejected"),
        ("not JSON", "run_list_rejected"),
        ("{" + " " * 65536 + "}", "response_size_rejected"),
    ],
)
def test_response_shape_and_size_are_bounded(db, body, error):
    enable_monitor(db)
    poll(db)
    respond(db, body=body)
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == error


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"status": 304}, "redirect_response_unverified"),
        ({"status": 302}, "redirect_response_unverified"),
        ({"status": 500}, "http_status_rejected"),
        ({"headers": {"Location": "https://attacker.invalid"}}, "redirect_response_unverified"),
        ({"content_type": "text/html"}, "content_type_rejected"),
        ({"timed_out": True}, "transport_timeout"),
        ({"error": "private unsanitized provider diagnostic"}, "transport_failure"),
        ({"created": "'infinity'::timestamptz"}, "response_not_fresh"),
        ({"created": "clock_timestamp()+interval '1 second'"}, "response_not_fresh"),
        ({"created": "clock_timestamp()-interval '30 minutes'"}, "response_not_fresh"),
    ],
)
def test_transport_evidence_fails_closed_and_preserves_budget(db, kwargs, error):
    enable_monitor(db)
    poll(db)
    respond(db, **kwargs)
    result = poll(db)
    assert result["healthy"] is False and result["delivery_gap"] is None
    assert stored(db)["schedules"]["reader"]["last_error"] == error
    assert "unsanitized" not in json.dumps(stored(db))
    for _ in range(3):
        poll(db)
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 1


@pytest.mark.parametrize("second_status", [200, 429])
def test_duplicate_receipts_never_choose_success_or_hide_rate_limit(db, second_status):
    enable_monitor(db)
    poll(db)
    rid = respond(db)
    db.execute(
        "insert into net._http_response select id,%s,content_type,content,headers,timed_out,error_msg,created from net._http_response where id=%s",
        (second_status, rid),
    )
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "ambiguous_scheduler_receipt"
    assert stored(db)["budget"]["blocked"] is True
    elapse_budget(db)
    poll(db)
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 1


def test_pre_request_receipt_never_becomes_delivery_evidence(db):
    enable_monitor(db)
    poll(db)
    respond(db, created="clock_timestamp()-interval '1 second'")
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "response_not_fresh"


@pytest.mark.parametrize(
    "headers",
    [
        {"retry-after": "not-a-delay"},
        {"retry-after": "-1"},
        {"retry-after": "31536001"},
        {"retry-after": 600},
        {"x-ratelimit-reset": "infinity"},
        {"x-ratelimit-reset": "999999999999"},
        {"Retry-After": "600", "retry-after": "700"},
    ],
)
def test_malformed_rate_headers_halt_instead_of_ignoring_wait(db, headers):
    enable_monitor(db)
    poll(db)
    respond(db, status=429, headers=headers)
    poll(db)
    value = stored(db)
    assert value["budget"]["blocked"] is True
    assert value["schedules"]["reader"]["last_error"] == "rate_limit_metadata_invalid"
    elapse_budget(db, 7200)
    poll(db)
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"created": "clock_timestamp()-interval '30 minutes'", "headers": {"Retry-After": "7200"}},
        {"headers": {"Retry-After": "7200", "extra": "x" * 8200}},
        {"headers": ["unknown rate headers"]},
        {"headers": {"Retry-After": "7200", "Location": "https://untrusted.invalid"}},
        {"timed_out": True, "headers": {"Retry-After": "7200"}},
    ],
)
def test_rejected_rate_limit_receipt_cannot_fall_back_to_shorter_wait(db, kwargs):
    enable_monitor(db)
    poll(db)
    respond(db, status=429, **kwargs)
    poll(db)
    assert stored(db)["budget"]["blocked"] is True
    elapse_budget(db, 3600)
    poll(db)
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 1


@pytest.mark.parametrize("status", [200, 403, 429])
def test_provider_reset_and_retry_after_are_honored_globally_without_truncation(db, status):
    enable_monitor(db)
    poll(db)
    reset = int(now(db).timestamp()) + 7200
    respond(
        db,
        status=status,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(reset),
            "Retry-After": "3600",
        },
    )
    poll(db)
    next_poll = stored(db)["budget"]["next_poll_at"]
    assert db.execute(
        "select extract(epoch from %s::timestamptz)>=%s", (next_poll, reset)
    ).fetchone()[0]
    poll(db)
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 1


@pytest.mark.parametrize(
    "budget",
    [
        None,
        [],
        {},
        {"blocked": False},
        {
            "blocked": False,
            "next_target": "reader",
            "last_attempt_at": None,
            "next_poll_at": "infinity",
        },
        {
            "blocked": False,
            "next_target": "reader",
            "last_attempt_at": "invalid",
            "next_poll_at": "2026-10-29T00:00:00Z",
        },
        {
            "blocked": False,
            "next_target": "foreign",
            "last_attempt_at": None,
            "next_poll_at": "2026-10-29T00:00:00Z",
        },
    ],
)
def test_malformed_budget_never_becomes_immediately_due(db, budget):
    enable_monitor(db)
    value = stored(db)
    value["budget"] = budget
    save(db, value)
    for _ in range(3):
        assert poll(db)["healthy"] is False
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 0


def test_reader_is_read_only_rechecks_source_freshness_and_cannot_hide_pending_timeout(db):
    observe_both(db)
    before = db.execute(
        "select value,last_verified_at from public.dufynd_master_status where key=%s", (KEY,)
    ).fetchone()
    assert read(db)["healthy"] is True
    assert (
        before
        == db.execute(
            "select value,last_verified_at from public.dufynd_master_status where key=%s", (KEY,)
        ).fetchone()
    )
    value = stored(db)
    stamp = now(db)
    for t in value["schedules"].values():
        # Keep source/run identity consistent while aging this real receipt.
        t["observed_at"] = (stamp - timedelta(seconds=1201)).isoformat()
        t["receipt_requested_at"] = (stamp - timedelta(seconds=1202)).isoformat()
        for run in t["snapshot"]["workflow_runs"]:
            for field in ("created_at", "run_started_at", "updated_at"):
                run[field] = (stamp - timedelta(seconds=1300)).isoformat()
    save(db, value)
    result = read(db)
    assert result["status"] == "stale" and result["delivery_gap"] is None
    assert ISSUE + "observation_stale" in result["issues"]


def test_reader_uses_actual_wall_clock_after_longer_calling_statement(db):
    observe_both(db)
    value = stored(db)
    stamp = now(db)
    for t in value["schedules"].values():
        t["observed_at"] = (stamp - timedelta(seconds=1199.9)).isoformat()
        t["receipt_requested_at"] = (stamp - timedelta(seconds=1201)).isoformat()
        for run in t["snapshot"]["workflow_runs"]:
            for field in ("created_at", "run_started_at", "updated_at"):
                run[field] = (stamp - timedelta(seconds=1300)).isoformat()
    save(db, value)
    # The caller can wait on its own lock before invoking this pure reader.
    result = db.execute(
        "with waited as materialized (select pg_sleep(0.25)) "
        "select public.read_dufynd_github_scheduler_delivery_v1() from waited"
    ).fetchone()[0]
    assert result["status"] == "stale" and result["delivery_gap"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", "1"),
        ("request_workflow_id", 377395476),
        ("requested_at", "infinity"),
        ("requested_at", "2999-01-01T00:00:00Z"),
    ],
)
def test_pending_identity_cannot_be_reassigned_or_forgotten(db, field, value):
    enable_monitor(db)
    poll(db)
    state = stored(db)
    state["schedules"]["reader"][field] = value
    save(db, state)
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "invalid_pending_state"
    assert "request_id" in stored(db)["schedules"]["reader"]
    assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 1
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 1


def test_unchanged_run_reread_and_rerun_keep_original_created_at(db):
    body = run_body(db, age_seconds=3600)
    observe_both(db, reader_body=body)
    before = stored(db)["schedules"]["reader"]["snapshot"]["workflow_runs"][0]["created_at"]
    elapse_budget(db)
    poll(db)
    body["workflow_runs"][0]["run_attempt"] = 2
    body["workflow_runs"][0]["run_started_at"] = (now(db) - timedelta(seconds=1)).isoformat()
    body["workflow_runs"][0]["updated_at"] = now(db).isoformat()
    respond(db, body=body)
    result = poll(db)
    assert stored(db)["schedules"]["reader"]["snapshot"]["workflow_runs"][0]["created_at"] == before
    assert result["schedules"]["reader"]["delivery_status"] == "gap"
    assert result["schedules"]["reader"]["dispatch_status"] == "unknown"


def test_same_run_cannot_be_retimed_or_replayed_as_a_new_request(db):
    body = run_body(db, age_seconds=3600)
    observe_both(db, reader_body=body)
    before = stored(db)["schedules"]["reader"]
    elapse_budget(db)
    poll(db)
    body["workflow_runs"][0]["created_at"] = (now(db) - timedelta(seconds=120)).isoformat()
    respond(db, body=body)
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "natural_run_history_conflict"
    value = stored(db)
    value["schedules"]["reader"].update(
        {
            "request_id": before["receipt_id"],
            "requested_at": before["receipt_requested_at"],
            "request_workflow_id": WORKFLOWS["reader"],
        }
    )
    save(db, value)
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "replayed_receipt_identity"


def test_timezone_changes_do_not_change_natural_identity(db):
    body = run_body(db)
    observe_both(db, reader_body=body)
    elapse_budget(db)
    db.execute("set local timezone='Asia/Kolkata'")
    poll(db)
    respond(db, body=body)
    result = poll(db)
    assert result["healthy"] is True, result


def test_pending_worker_queue_does_not_create_backlog_and_other_schedule_can_progress(db):
    enable_monitor(db)
    poll(db)
    value = stored(db)
    value["schedules"]["reader"]["requested_at"] = (now(db) - timedelta(seconds=181)).isoformat()
    save(db, value)
    elapse_budget(db)
    poll(db)
    assert stored(db)["schedules"]["reader"]["last_error"] == "request_dispatch_overdue"
    assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 2
    respond(db, "watchdog")
    result = poll(db)
    assert result["status"] == "degraded" and result["delivery_gap"] is None
    assert result["transport_status"] == "partial"
    for _ in range(3):
        poll(db)
    assert db.execute("select count(*) from net.test_request_calls").fetchone()[0] == 2


def test_private_invoker_acl_and_idempotent_disabled_seed(db):
    enable_monitor(db)
    before = stored(db)
    db.execute(MIGRATION.read_text())
    assert stored(db) == before
    definitions = db.execute("""select p.oid::regprocedure::text,p.prosecdef,p.provolatile,p.proconfig,
        has_function_privilege('anon',p.oid,'execute'),has_function_privilege('authenticated',p.oid,'execute'),
        has_function_privilege('service_role',p.oid,'execute') from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname='public' and p.proname in ('dufynd_scheduler_parse_time_v1',
        'normalize_dufynd_github_scheduler_run_v1','read_dufynd_github_scheduler_delivery_v1',
        'poll_dufynd_github_scheduler_delivery_v1')""").fetchall()
    assert len(definitions) == 4
    for name, definer, volatility, config, anon, authenticated, service in definitions:
        assert definer is False and anon is False and authenticated is False and service is True
        assert "search_path=pg_catalog, public" in config
        if "read_dufynd" in name:
            assert volatility == "v"  # Wall clock can change within the caller's statement.
    assert db.execute(
        "select relrowsecurity from pg_class where oid='public.dufynd_master_status'::regclass"
    ).fetchone()[0]


def test_wall_clock_reader_executes_in_read_only_transaction(db):
    observe_both(db)
    db.execute("set local transaction_read_only=on")
    assert db.execute("select current_setting('transaction_read_only')").fetchone()[0] == "on"
    result = read(db)
    assert result["healthy"] is True
    assert result["issues"] == []
