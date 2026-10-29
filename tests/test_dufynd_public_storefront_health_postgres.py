"""Public storefront receipt/HTML contracts in real PostgreSQL; no live HTTP."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tests.test_dufynd_public_api_health_postgres import db as api_db  # noqa: F401

from tests import test_dufynd_public_api_health_postgres as api

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261029104253_dufynd_public_storefront_health.sql"
GITHUB_MIGRATION = (
    ROOT / "supabase/migrations/20261029090152_dufynd_github_observer_receipt_freshness.sql"
)
KEY = "ops.public_storefront_health_v1"
URL = "https://dufynd.de/"
HTML = (
    '<!DOCTYPE html><html lang="de"><head><title>DUFYND – Duftberatung &amp; Parfumvergleich</title>'
    '<link rel="canonical" href="https://dufynd.de"/></head><body><main>'
    '<section data-dufynd-home-audience-stage=""><h2>Deine Duftwelt</h2>'
    '<a href="/duft">Düfte entdecken</a></section></main></body></html>'
)


@pytest.fixture
def db(request):
    c = request.getfixturevalue("api_db")
    # Reuse the actual public API setup; preserve #847's current GitHub hook.
    c.execute(GITHUB_MIGRATION.read_text())
    assert (
        c.execute(
            "select md5(prosrc) from pg_proc where oid='public.poll_dufynd_observers()'::regprocedure"
        ).fetchone()[0]
        == "609d0c703afbccb6dd73d25a21b4e84e"
    )
    assert (
        c.execute(
            "select md5(prosrc) from pg_proc where oid='public.poll_dufynd_public_api_health_v1()'::regprocedure"
        ).fetchone()[0]
        == "9306ac4948d135ffee46d4562112c470"
    )
    before = c.execute(
        "select pg_get_functiondef('public.poll_dufynd_public_api_health_v1()'::regprocedure)"
    ).fetchone()[0]
    c.execute(
        before.replace(
            "public.poll_dufynd_public_api_health_v1(",
            "public.poll_dufynd_api_before_cardinality_fix(",
            1,
        )
    )
    c.execute("alter table net._http_response drop constraint if exists _http_response_pkey")
    c.execute("delete from public.dufynd_master_status where key=%s", (KEY,))
    # Match the verified production masterstatus privacy boundary in standalone
    # fixture runs as well; rollback restores a preceding native-suite schema.
    c.execute("alter table public.dufynd_master_status enable row level security")
    c.execute("revoke all on public.dufynd_master_status from public,anon,authenticated")
    c.execute("grant select,insert,update on public.dufynd_master_status to service_role")
    c.execute(MIGRATION.read_text())
    yield c


@pytest.mark.parametrize("conflicting_status", [200, 503])
def test_api_duplicate_receipts_are_reproduced_and_rejected_without_false_health(
    db, conflicting_status
):
    api.enable(db)
    api.poll(db)
    rid = api.respond(db)
    db.execute(
        "insert into net._http_response(id,status_code,content_type,content,created,timed_out) "
        "select id,%s,content_type,content,created,false from net._http_response where id=%s",
        (conflicting_status, rid),
    )
    pending = api.stored(db)
    assert db.execute("select public.poll_dufynd_api_before_cardinality_fix()").fetchone()[0][
        "healthy"
    ]
    db.execute(
        "update public.dufynd_master_status set value=%s::jsonb where key=%s",
        (json.dumps(pending), api.KEY),
    )
    result = api.poll(db)
    assert result["healthy"] is False and result["last_error"] == "ambiguous_api_receipt"
    assert result["last_success_at"] is None and result["last_status_code"] is None
    assert "request_id" not in api.stored(db)
    assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 0


@pytest.mark.parametrize(
    "existing_case",
    [
        api.test_only_actual_typed_health_response_sets_success_time,
        api.test_one_pending_identity_and_no_backlog_when_worker_is_unavailable,
        api.test_missing_response_after_worker_loses_request_enters_bounded_backoff,
        api.test_failed_probe_preserves_previous_success_but_cannot_stay_healthy,
    ],
    ids=lambda case: case.__name__,
)
def test_api_cardinality_fix_preserves_adjacent_existing_contracts(db, existing_case):
    existing_case(db)


def test_api_cardinality_fix_still_rejects_future_unique_receipt(db):
    api.test_transport_and_response_bounds_fail_closed(
        db, {"age_seconds": -30}, "response_not_fresh"
    )


def stored(db):
    return db.execute(
        "select value from public.dufynd_master_status where key=%s", (KEY,)
    ).fetchone()[0]


def patch(db, value):
    db.execute(
        "update public.dufynd_master_status set value=value||%s::jsonb where key=%s",
        (json.dumps(value), KEY),
    )


def enable(db):
    patch(db, {"enabled": True})


def poll(db):
    return db.execute("select public.poll_dufynd_public_storefront_health_v1()").fetchone()[0]


def read(db):
    return db.execute("select public.read_dufynd_public_storefront_health_v1()").fetchone()[0]


def respond(
    db,
    *,
    status=200,
    body=HTML,
    content_type="text/html; charset=utf-8",
    headers=None,
    timed_out=False,
    error=None,
    created="clock_timestamp()",
):
    rid = stored(db)["request_id"]
    db.execute("delete from net.http_request_queue where id=%s", (rid,))
    db.execute(
        "insert into net._http_response(id,status_code,content_type,content,headers,timed_out,error_msg,created) "
        f"values(%s,%s,%s,%s,%s::jsonb,%s,%s,{created})",
        (rid, status, content_type, body, json.dumps(headers or {}), timed_out, error),
    )
    return rid


def request_age(db, seconds):
    db.execute(
        "update public.dufynd_master_status set value=value||jsonb_build_object("
        "'requested_at',clock_timestamp()-make_interval(secs=>%s)) where key=%s",
        (seconds, KEY),
    )


def healthy(db):
    enable(db)
    poll(db)
    respond(db)
    result = poll(db)
    assert result["healthy"], result
    return stored(db)["last_success_at"]


def test_storefront_install_is_disabled_without_a_source_observation(db):
    value = read(db)
    assert value["status"] == "disabled" and value["healthy"] is False
    assert poll(db)["enabled"] is False
    assert "last_success_at" not in stored(db) and "valid_until" not in stored(db)
    assert stored(db)["config_checked_at"]
    assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 0


def test_storefront_request_and_report_scope_are_fixed_and_private_evidence_is_untouched(db):
    before = api.stored(db)
    db.execute(
        "insert into public.dufynd_external_observers(observer_id,source_type,source_id,enabled,"
        "last_cursor,last_snapshot,last_success_at,health_status) values"
        "('render:storefront-scope-fixture','render','storefront-scope-fixture',false,"
        "'private-cursor','{\"sha\":\"original-private-proof\"}',now()-interval '6 days','stale')"
    )
    private_before = db.execute(
        "select to_jsonb(o) from public.dufynd_external_observers o "
        "where observer_id='render:storefront-scope-fixture'"
    ).fetchone()[0]
    enable(db)
    patch(
        db,
        {
            "endpoint": "https://evil.test/click?token=secret",
            "headers": {"Cookie": "secret"},
            "scope": "private_provider",
            "canonical": "https://evil.test/",
        },
    )
    result = poll(db)
    assert db.execute(
        "select url,headers,timeout_milliseconds from net.http_request_queue"
    ).fetchone() == (
        URL,
        {"Accept": "text/html", "User-Agent": "DUFYND-Public-Storefront-Health/1"},
        5000,
    )
    assert result["endpoint"] == URL and result["canonical"] == "https://dufynd.de"
    assert result["scope"] == "public_storefront_liveness_only"
    for key in (
        "private_observer_evidence",
        "full_chain_complete",
        "deployment_revision_verified",
        "redirect_chain_verified",
        "final_origin_verified",
        "javascript_executed",
    ):
        assert result[key] is False
    assert result["redirect_behavior"] == "pg_net_follows_redirects"
    assert "secret" not in json.dumps(result)
    assert api.stored(db) == before
    respond(db)
    assert poll(db)["healthy"] is True
    assert (
        db.execute(
            "select to_jsonb(o) from public.dufynd_external_observers o "
            "where observer_id='render:storefront-scope-fixture'"
        ).fetchone()[0]
        == private_before
    )


def test_storefront_only_real_unique_html_receipt_sets_time_and_no_raw_body_is_saved(db):
    enable(db)
    poll(db)
    rid = respond(db)
    result = poll(db)
    assert result["healthy"] and result["status"] == "healthy", result
    assert result["html_contract"] == "dufynd_home_v1"
    assert result["last_response_bytes"] == len(HTML.encode())
    assert db.execute(
        "select (value->>'last_success_at')::timestamptz=r.created and "
        "(value->>'valid_until')::timestamptz=r.created+interval '600 seconds' "
        "from public.dufynd_master_status s cross join net._http_response r where s.key=%s and r.id=%s",
        (KEY, rid),
    ).fetchone()[0]
    before = stored(db)["last_success_at"]
    poll(db)
    assert stored(db)["last_success_at"] == before
    assert all(
        marker not in json.dumps(stored(db)) for marker in ("<!DOCTYPE", "<html", "<section")
    )


@pytest.mark.parametrize("extra_bytes", [0, 1])
def test_storefront_response_acceptance_limit_is_in_utf8_bytes(db, extra_bytes):
    padding = " " * (131072 - len(HTML.encode()) + extra_bytes)
    body = HTML.replace("</main>", padding + "</main>")
    assert len(body.encode()) == 131072 + extra_bytes
    enable(db)
    poll(db)
    respond(db, body=body)
    result = poll(db)
    assert result["healthy"] is (extra_bytes == 0)
    assert result["last_response_bytes"] == 131072 + extra_bytes
    if extra_bytes:
        assert result["last_error"] == "response_size_rejected"


@pytest.mark.parametrize(
    "body",
    [
        HTML.replace(
            '<link rel="canonical" href="https://dufynd.de"/>',
            "<link href='https://dufynd.de' rel='canonical'>",
        ),
        HTML.replace(
            "</head>", '<script>const markup="<link rel=canonical href=evil>";</script></head>'
        ),
        HTML.replace("</head>", '<!-- <link rel="canonical" href="https://evil.test"> --></head>'),
        HTML.replace("<section data-", '<section class="home" data-').replace(
            '<a href="/duft">', '<a class="link" href="/duft">'
        ),
    ],
)
def test_storefront_valid_quote_order_and_non_document_decoys_are_handled(db, body):
    enable(db)
    poll(db)
    respond(db, body=body)
    assert poll(db)["healthy"] is True


@pytest.mark.parametrize(
    "body,reason",
    [
        ("DUFYND temporarily unavailable", "html_document_rejected"),
        (
            "<!DOCTYPE html><html><head><title>Service error</title></head><body>DUFYND 500</body></html>",
            "dufynd_identity_rejected",
        ),
        (HTML.replace("DUFYND –", "OTHER –"), "dufynd_identity_rejected"),
        (
            HTML.replace('<link rel="canonical" href="https://dufynd.de"/>', ""),
            "canonical_homepage_rejected",
        ),
        (
            HTML.replace('href="https://dufynd.de"', 'href="https://dufynd.de/duft"'),
            "canonical_homepage_rejected",
        ),
        (
            HTML.replace('href="https://dufynd.de"', 'href="https://dufynd.de?error=1"'),
            "canonical_homepage_rejected",
        ),
        (
            HTML.replace('href="https://dufynd.de"', 'href="https://evil.test"'),
            "canonical_homepage_rejected",
        ),
        (
            HTML.replace("</head>", '<link rel="canonical" href="https://dufynd.de"/></head>'),
            "canonical_homepage_rejected",
        ),
        (
            HTML.replace(
                'href="https://dufynd.de"', 'href="https://dufynd.de" href="https://evil.test"'
            ),
            "canonical_homepage_rejected",
        ),
        (
            HTML.replace(
                '<link rel="canonical" href="https://dufynd.de"/>',
                '<script>"<link rel="canonical" href="https://dufynd.de"/>"</script>',
            ),
            "canonical_homepage_rejected",
        ),
        (
            HTML.replace(
                '<link rel="canonical" href="https://dufynd.de"/>',
                '<!-- <link rel="canonical" href="https://dufynd.de"/> -->',
            ),
            "canonical_homepage_rejected",
        ),
        (
            HTML.replace("data-dufynd-home-audience-stage", "data-error-page"),
            "homepage_content_rejected",
        ),
        (HTML.replace('href="/duft"', 'href="/login"'), "homepage_content_rejected"),
        (HTML.replace("</html>", ""), "html_document_rejected"),
    ],
)
def test_storefront_200_error_wrong_route_and_decoy_markup_fail_closed(db, body, reason):
    enable(db)
    poll(db)
    respond(db, body=body)
    result = poll(db)
    assert result["healthy"] is False and result["last_error"] == reason
    assert result["last_success_at"] is None


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"status": 503}, "http_status_rejected"),
        ({"status": 302}, "redirect_response_unverified"),
        ({"status": 304}, "redirect_response_unverified"),
        (
            {"headers": {"Location": "https://evil.test/?secret=canary"}},
            "redirect_response_unverified",
        ),
        ({"headers": {"lOcAtIoN": "https://dufynd.de/"}}, "redirect_response_unverified"),
        ({"timed_out": True}, "transport_timeout"),
        ({"error": "PRIVATE_BODY_PASSWORD_CANARY"}, "transport_failure"),
        ({"content_type": "application/json"}, "content_type_rejected"),
        ({"content_type": None}, "content_type_rejected"),
        ({"body": None}, "response_size_rejected"),
        ({"body": HTML + "é" * 65536}, "response_size_rejected"),
        ({"created": "clock_timestamp()+interval '1 second'"}, "response_not_fresh"),
        ({"created": "'infinity'::timestamptz"}, "response_not_fresh"),
        ({"created": "'-infinity'::timestamptz"}, "response_not_fresh"),
        ({"created": "null::timestamptz"}, "response_not_fresh"),
        ({"created": "clock_timestamp()-interval '900 seconds'"}, "response_not_fresh"),
    ],
)
def test_storefront_transport_redirect_type_size_and_source_time_are_fail_closed(
    db, kwargs, reason
):
    enable(db)
    poll(db)
    respond(db, **kwargs)
    result = poll(db)
    assert result["healthy"] is False and result["last_error"] == reason
    assert result["last_success_at"] is None
    assert all(value not in json.dumps(stored(db)) for value in ("CANARY", "evil.test", "<html"))


@pytest.mark.parametrize("conflicting_status", [200, 503])
def test_storefront_duplicate_response_cannot_pick_a_healthy_row(db, conflicting_status):
    enable(db)
    poll(db)
    rid = respond(db)
    db.execute(
        "insert into net._http_response(id,status_code,content_type,content,created,timed_out) "
        "select id,%s,content_type,content,created,false from net._http_response where id=%s",
        (conflicting_status, rid),
    )
    result = poll(db)
    assert result["healthy"] is False and result["last_error"] == "ambiguous_storefront_receipt"
    assert result["last_status_code"] is None and result["last_response_bytes"] is None
    assert result["last_success_at"] is None


def test_storefront_last_good_receipt_survives_short_pending_but_not_overdue_pending(db):
    original = healthy(db)
    patch(db, {"next_poll_at": "2000-01-01T00:00:00Z"})
    assert poll(db)["healthy"] is True
    assert stored(db)["last_success_at"] == original
    request_age(db, 120)
    assert read(db)["healthy"] is True and read(db)["request_pending"] is True
    request_age(db, 181)
    result = read(db)
    assert result["healthy"] is False and result["last_error"] == "request_overdue"
    assert stored(db)["last_success_at"] == original


@pytest.mark.parametrize("seconds", [90, 120])
def test_storefront_initial_pending_has_consumer_grace_without_invented_success(db, seconds):
    enable(db)
    poll(db)
    request_age(db, seconds)
    respond(db, created=f"clock_timestamp()-interval '{seconds - 1} seconds'")
    assert read(db)["status"] == "pending" and read(db)["healthy"] is False
    assert read(db)["last_success_at"] is None
    assert poll(db)["healthy"] is True


def test_storefront_queued_overdue_request_never_accumulates_retries(db):
    enable(db)
    poll(db)
    rid = stored(db)["request_id"]
    request_age(db, 86400)
    for _ in range(3):
        assert poll(db)["healthy"] is False
        assert stored(db)["last_error"] == "request_dispatch_overdue"
        assert stored(db)["request_id"] == rid
    assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 1


@pytest.mark.parametrize(
    "override",
    [
        {"requested_at": None},
        {"requested_at": "infinity"},
        {"requested_at": "-infinity"},
        {"requested_at": "2999-01-01T00:00:00Z"},
        {"requested_at": "not-a-time"},
        {"request_id": None},
        {"request_id": "not-an-id"},
    ],
)
def test_storefront_invalid_pending_identity_is_held_without_orphaning_queue(db, override):
    enable(db)
    poll(db)
    patch(db, override)
    before = stored(db)
    for _ in range(2):
        result = poll(db)
        assert result["healthy"] is False
        assert stored(db)["last_error"] == "invalid_pending_state"
        assert stored(db)["request_id"] == before["request_id"]
        assert stored(db)["requested_at"] == before["requested_at"]
    assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 1


def test_storefront_lost_request_backoff_retries_once_and_caps_without_duplication(db):
    enable(db)
    for delay in (120, 240, 480, 960, 1800, 1800):
        patch(db, {"next_poll_at": "2000-01-01T00:00:00Z"})
        poll(db)
        assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 1
        db.execute("delete from net.http_request_queue")
        request_age(db, 61)
        assert poll(db)["last_error"] == "response_missing"
        assert (
            db.execute(
                "select extract(epoch from((value->>'next_poll_at')::timestamptz-"
                "(value->>'last_error_at')::timestamptz)) from public.dufynd_master_status where key=%s",
                (KEY,),
            ).fetchone()[0]
            == delay
        )
        poll(db)
        assert "request_id" not in stored(db)
        assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 0


def test_storefront_failure_and_disabled_state_preserve_historical_success_without_health(db):
    original = healthy(db)
    patch(db, {"next_poll_at": "2000-01-01T00:00:00Z"})
    poll(db)
    respond(db, status=503)
    assert poll(db)["healthy"] is False
    assert stored(db)["last_success_at"] == original
    patch(db, {"next_poll_at": "2000-01-01T00:00:00Z"})
    poll(db)
    patch(db, {"enabled": False})
    respond(db)
    assert poll(db)["status"] == "disabled"
    assert stored(db)["last_success_at"] == original


@pytest.mark.parametrize(
    "override",
    [
        {"last_success_at": "infinity", "valid_until": "infinity"},
        {"html_contract": "other"},
        {"last_response_bytes": 131073},
        {"last_response_bytes": "500"},
        {"last_status_code": 503},
    ],
)
def test_storefront_reader_cannot_project_unproved_health(db, override):
    healthy(db)
    patch(db, override)
    assert read(db)["healthy"] is False


def test_storefront_reader_expires_valid_receipt_even_when_cron_stops(db):
    healthy(db)
    db.execute(
        "update public.dufynd_master_status set value=value||jsonb_build_object("
        "'last_success_at',clock_timestamp()-interval '601 seconds',"
        "'valid_until',clock_timestamp()-interval '1 second') where key=%s",
        (KEY,),
    )
    result = read(db)
    assert result["status"] == "stale" and result["last_error"] == "storefront_success_stale"


def test_storefront_actual_receipt_can_arrive_after_statement_start(db):
    enable(db)
    poll(db)
    respond(db)
    db.execute("alter table net._http_response rename to storefront_test_receipts")
    db.execute(
        "create view net._http_response as select id,status_code,content_type,content,headers,"
        "timed_out,error_msg,clock_timestamp() as created from net.storefront_test_receipts"
    )
    assert poll(db)["healthy"] is True


def test_existing_hook_keeps_github_receipt_body_exact_and_both_public_monitors_independent(db):
    old = GITHUB_MIGRATION.read_text().split("AS $function$", 1)[1].split("$function$;", 1)[0]
    new = db.execute(
        "select prosrc from pg_proc where oid='public.poll_dufynd_observers()'::regprocedure"
    ).fetchone()[0]
    addition = "\n begin\n  perform public.poll_dufynd_public_storefront_health_v1();\n exception when others then\n  raise log 'DUFYND public storefront health hook unavailable';\n end;"
    assert new.count(addition) == 1 and new.replace(addition, "", 1) == old
    enable(db)
    api.enable(db)
    assert db.execute("select public.poll_dufynd_observers()").fetchone()[0] == {"attempted": 0}
    assert db.execute("select url from net.http_request_queue order by url").fetchall() == [
        (URL,),
        (api.URL,),
    ]
    db.execute("select public.poll_dufynd_observers()")
    assert db.execute("select count(*) from net.http_request_queue").fetchone()[0] == 2


def test_storefront_exception_does_not_stop_other_existing_observers(db):
    api.enable(db)
    db.execute(
        "create or replace function public.poll_dufynd_public_storefront_health_v1() "
        "returns jsonb language plpgsql as $$ begin raise exception 'private-canary'; end $$"
    )
    assert db.execute("select public.poll_dufynd_observers()").fetchone()[0] == {"attempted": 0}
    assert db.execute("select url from net.http_request_queue").fetchall() == [(api.URL,)]


def test_storefront_private_roles_configuration_and_idempotent_install(db):
    enable(db)
    poll(db)
    before = stored(db)
    db.execute(MIGRATION.read_text())
    assert stored(db) == before
    for name in (
        "read_dufynd_public_storefront_health_v1",
        "poll_dufynd_public_storefront_health_v1",
    ):
        assert db.execute(
            "select prosecdef,proconfig,has_function_privilege('anon',oid,'execute'),"
            "has_function_privilege('authenticated',oid,'execute'),"
            "has_function_privilege('service_role',oid,'execute') from pg_proc where proname=%s",
            (name,),
        ).fetchone() == (False, ["search_path=pg_catalog, public"], False, False, True)
    assert db.execute(
        "select relrowsecurity,has_table_privilege('anon',oid,'select'),"
        "has_table_privilege('authenticated',oid,'update') from pg_class "
        "where oid='public.dufynd_master_status'::regclass"
    ).fetchone() == (True, False, False)
    assert (
        db.execute(
            "select md5(prosrc) from pg_proc where oid='public.read_dufynd_public_api_health_v1()'::regprocedure"
        ).fetchone()[0]
        == "87b2b6712206b00f583b16bddaa6dc4a"
    )
