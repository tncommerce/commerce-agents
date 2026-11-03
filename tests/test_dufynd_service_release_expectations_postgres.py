"""Approved service releases, real planner/audit consumers, no provider requests."""

from __future__ import annotations

import copy
import json
import os
import re
from datetime import timedelta
from pathlib import Path

import pytest
from tests.test_dufynd_planner_technical_blockers_postgres import (
    db as planner_database,  # noqa: F401
)

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261029095417_dufynd_service_release_expectations.sql"
OLD_READER = ROOT / "supabase/migrations/20261028131239_dufynd_public_api_health_planner.sql"
OLD_AUDIT = ROOT / "supabase/migrations/20261007064000_jarvis_measurement_continuity_v1.sql"
KEY = "ops.render_release_expectations_v1"
HEAD = "a2d6bfefcc80efe34ebcb212cf887d8aa98473e8"
API_SHA = "7f63836c1e1f837e1dc72e3ab0e12090a97d8112"
STORE_SHA = "063f4f2ca0a6403137c6f5e94a71f0ec593e6a98"
API = "srv-dakpfrnf3r2c73dr3f20"
STORE = "srv-dakpiajl550s73cp4lvg"
GMAIL = "gmail:abcdef1234567890"


def function_sql(path, name):
    source = path.read_text()
    start = re.search(
        rf"create or replace function public\.{name}\(\).*?as (\$function\$)", source, re.S
    )
    assert start
    end = source.index(start[1], start.end()) + len(start[1])
    return source[start.start() : end] + ";"


def contract(db):
    approved_at = db.execute("SELECT now()-interval '1 minute'").fetchone()[0]
    return {
        "version": 1,
        "repository": "tncommerce/commerce-agents",
        "branch": "scentai-mvp",
        "repository_head_sha": HEAD,
        "approval_status": "approved",
        "approved_at": approved_at.isoformat(),
        "services": [
            {
                "component": "api",
                "service_id": API,
                "expected_deployment_sha": API_SHA,
                "decision": "hold_existing_release",
                "scope": "api_runtime",
                "evidence_ref": "fixture:approved-api-release",
                "rationale": "Approved API remains deployed while later Commerce changes are pending.",
            },
            {
                "component": "storefront",
                "service_id": STORE,
                "expected_deployment_sha": STORE_SHA,
                "decision": "hold_existing_release",
                "scope": "storefront_static",
                "evidence_ref": "fixture:approved-storefront-release",
                "rationale": "Keep the explicitly approved storefront deployment.",
            },
        ],
    }


def save_contract(db, value):
    db.execute(
        """INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
        VALUES(%s,'ops',%s::jsonb,100,now()) ON CONFLICT(key) DO UPDATE
        SET value=excluded.value,last_verified_at=excluded.last_verified_at""",
        (KEY, json.dumps(value)),
    )


def seed_render(db, service_id, sha):
    db.execute(
        """INSERT INTO public.dufynd_external_observers
        (observer_id,source_type,source_id,enabled,health_status,last_success_at,
         interval_seconds,next_retry_at,last_snapshot)
        VALUES(%s,'render',%s,true,'healthy',now(),120,now()+interval '2 minutes',%s::jsonb)
        ON CONFLICT(observer_id) DO UPDATE SET source_type='render',source_id=excluded.source_id,
        enabled=true,health_status='healthy',last_success_at=now(),interval_seconds=120,
        next_retry_at=excluded.next_retry_at,last_snapshot=excluded.last_snapshot""",
        (
            f"render:{service_id}",
            service_id,
            json.dumps(
                {
                    "sha": sha,
                    "service_id": service_id,
                    "state": "live",
                    "deployment_id": "dep-releasefixture",
                }
            ),
        ),
    )


@pytest.fixture
def db(planner_database):  # noqa: F811
    connection = planner_database
    connection.execute("""
        ALTER TABLE public.dufynd_external_observers ADD COLUMN IF NOT EXISTS next_retry_at timestamptz;
        ALTER TABLE public.dufynd_autonomy_tasks ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
        CREATE TABLE IF NOT EXISTS public.dufynd_handler_contracts(
          handler_id text,handler_version text,contract jsonb,enabled boolean,
          PRIMARY KEY(handler_id,handler_version));
        INSERT INTO public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
          VALUES('release_fixture_handler','1','{}',true) ON CONFLICT DO NOTHING;
        UPDATE public.dufynd_external_observers SET enabled=false WHERE source_type='render';
        UPDATE public.dufynd_external_observers SET next_retry_at=now()+interval '2 minutes';
        CREATE TEMP TABLE release_fixture_dependencies(name text PRIMARY KEY);
    """)
    # The real audit tests presence of these contracts, without executing them.
    for name in (
        "reconcile_dufynd_supervisor_v2",
        "run_dufynd_content_worker_v1",
        "run_dufynd_affiliate_worker_v1",
        "run_dufynd_content_backlog_worker_v1",
        "run_dufynd_content_packet_worker_v1",
        "run_dufynd_measurement_worker_v1",
    ):
        if (
            connection.execute("SELECT to_regprocedure(%s)", (f"public.{name}()",)).fetchone()[0]
            is None
        ):
            connection.execute(
                f"CREATE FUNCTION public.{name}() RETURNS jsonb LANGUAGE sql AS $fixture$ SELECT '{{}}'::jsonb $fixture$"
            )
    connection.execute(
        """UPDATE public.dufynd_external_observers SET last_snapshot=jsonb_build_object('sha',%s::text),
        last_success_at=now(),health_status='healthy' WHERE observer_id='github_branch:scentai-mvp'""",
        (HEAD,),
    )
    seed_render(connection, API, API_SHA)
    seed_render(connection, STORE, STORE_SHA)
    connection.execute(
        """UPDATE public.dufynd_broker_acceptance_sessions SET source_sha=%s,
        captured_observers=%s::jsonb WHERE run_id=999999999999""",
        (HEAD, json.dumps([f"render:{API}", f"render:{STORE}", GMAIL])),
    )
    connection.execute(function_sql(OLD_AUDIT, "audit_dufynd_integrity_v1"))
    # Match the verified live ACL/security contract before replacement.
    connection.execute("""
        REVOKE ALL ON FUNCTION public.audit_dufynd_integrity_v1(),public.read_dufynd_technical_work_blockers_v1()
          FROM PUBLIC,anon,authenticated;
        GRANT EXECUTE ON FUNCTION public.audit_dufynd_integrity_v1(),public.read_dufynd_technical_work_blockers_v1()
          TO service_role,postgres;
        CREATE TEMP TABLE release_fixture_acl AS SELECT oid,proacl,prosecdef,provolatile,proconfig
        FROM pg_proc WHERE oid IN ('public.audit_dufynd_integrity_v1()'::regprocedure,
          'public.read_dufynd_technical_work_blockers_v1()'::regprocedure);
    """)
    connection.execute(MIGRATION.read_text())
    save_contract(connection, contract(connection))
    yield connection


def helper(db):
    return db.execute("SELECT public.read_dufynd_render_release_expectations_v1()").fetchone()[0]


def technical(db):
    return db.execute("SELECT public.read_dufynd_technical_work_blockers_v1()").fetchone()[0]


def plan(db):
    return db.execute("SELECT public.plan_dufynd_free_work_v1()").fetchone()[0]


def audit(db):
    return db.execute("SELECT public.audit_dufynd_integrity_v1()").fetchone()[0]


def service(report, identity=API):
    return next(row for row in report["services"] if row["service_id"] == identity)


def assert_same_release_diagnosis(db):
    first = technical(db)["render_release_expectations"]
    second = audit(db)["render_release_expectations"]
    for field in (
        "status",
        "binding_status",
        "binding_reason",
        "issues",
        "services",
        "revision_mismatch_count",
        "unknown_service_count",
    ):
        assert second[field] == first[field]
    return first


def assert_unknown(db, reason=None):
    result = assert_same_release_diagnosis(db)
    assert result["status"] == "unknown" and result["technical_work_remaining"] is True
    assert result["revision_mismatch_count"] == 0
    if reason:
        assert result["binding_reason"] == reason
    assert technical(db)["status"] == "degraded"
    assert plan(db)["state"] == "technical_remediation_required"
    return result


def test_explicit_approved_service_holds_do_not_require_monorepo_head_deployment(db):
    assert technical(db)["status"] == "healthy"
    assert plan(db)["state"] == "waiting_market_signal"
    assert audit(db)["status"] == "healthy"
    result = assert_same_release_diagnosis(db)
    assert result["status"] == "verified" and result["binding_status"] == "approved"
    assert result["repository_head_sha"] == HEAD
    assert result["code_equivalence_verified"] is False
    assert result["revision_mismatch_count"] == 0 and result["unknown_service_count"] == 0
    assert result["expected_service_count"] == 2
    for identity, sha in ((API, API_SHA), (STORE, STORE_SHA)):
        row = service(result, identity)
        assert row["expected_deployment_sha"] == row["observed_deployment_sha"] == sha
        assert row["intent_match"] is True and row["observation_verified"] is True
        assert row["decision"] == "hold_existing_release" and row["comparison_status"] == "aligned"
    assert "github_render_sha_mismatch" not in technical(db)["issues"]
    assert "github_render_sha_mismatch" not in audit(db)["issues"]


def test_matching_head_sha_without_approval_remains_unknown(db):
    seed_render(db, API, HEAD)
    seed_render(db, STORE, HEAD)
    db.execute("DELETE FROM public.dufynd_master_status WHERE key=%s", (KEY,))
    assert technical(db)["status"] == "degraded"
    result = assert_unknown(db, "release_expectation_missing")
    assert all(
        row["observation_verified"] is True and row["intent_match"] is None
        for row in result["services"]
    )


def test_real_fresh_service_deviation_is_shared_mismatch(db):
    seed_render(db, API, "b" * 40)
    result = assert_same_release_diagnosis(db)
    assert result["status"] == "mismatch" and result["revision_mismatch_count"] == 1
    assert (
        service(result)["intent_match"] is False and service(result)["observation_verified"] is True
    )
    assert "render_release_mismatch" in technical(db)["issues"]
    assert "render_release_mismatch" in audit(db)["issues"]
    assert plan(db)["state"] == "technical_remediation_required"


@pytest.mark.parametrize(
    "change",
    [
        "enabled=false",
        "health_status='stale'",
        "last_success_at=now()-interval '601 seconds'",
        "last_success_at=now()+interval '1 second'",
        "last_success_at='infinity'::timestamptz",
        "last_success_at='-infinity'::timestamptz",
        "last_success_at=NULL",
        "source_type='github_pr'",
        "source_id='foreign-branch'",
        "last_snapshot='{\"sha\":123}'",
        "last_snapshot='{\"sha\":null}'",
    ],
)
def test_only_exact_fresh_github_source_can_bind_an_approval(db, change):
    db.execute(
        f"UPDATE public.dufynd_external_observers SET {change} WHERE observer_id='github_branch:scentai-mvp'"
    )
    result = assert_unknown(db, "github_head_unverified")
    assert result["repository_head_sha"] is None
    assert "production_revision_unverified" in technical(db)["issues"]


def test_new_repository_head_expires_previous_intent_without_allowlist(db):
    db.execute(
        "UPDATE public.dufynd_external_observers SET last_snapshot=jsonb_build_object('sha',%s::text) WHERE observer_id='github_branch:scentai-mvp'",
        ("c" * 40,),
    )
    result = assert_unknown(db, "repository_head_changed")
    assert all(
        row["expected_deployment_sha"] is None and row["intent_match"] is None
        for row in result["services"]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", "1"),
        ("version", None),
        ("repository", "another/repository"),
        ("branch", "main"),
        ("approval_status", "draft"),
        ("approval_status", True),
        ("repository_head_sha", 123),
        ("repository_head_sha", "a" * 39),
        ("services", {}),
        ("services", None),
        ("services", []),
    ],
)
def test_malformed_or_wrong_context_contract_fails_closed(db, field, value):
    data = contract(db)
    data[field] = value
    save_contract(db, data)
    result = assert_unknown(db)
    assert result["binding_status"] == "unknown"


@pytest.mark.parametrize("value", [None, [], True, 123, "approved"])
def test_wrong_top_level_json_type_is_diagnostic_not_exception(db, value):
    save_contract(db, value)
    assert_unknown(db, "release_expectation_invalid")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("component", "storefront"),
        ("service_id", STORE),
        ("scope", "storefront_static"),
        ("decision", "auto_deploy_latest"),
        ("decision", None),
        ("expected_deployment_sha", 123),
        ("expected_deployment_sha", None),
        ("expected_deployment_sha", "x" * 40),
        ("evidence_ref", {}),
        ("evidence_ref", "  "),
        ("rationale", []),
        ("rationale", ""),
    ],
)
def test_service_scope_sha_and_evidence_are_typed_and_bound(db, field, value):
    data = contract(db)
    data["services"][0][field] = value
    save_contract(db, data)
    assert_unknown(db, "release_service_invalid")


@pytest.mark.parametrize("value", [None, [], True, "api"])
def test_non_object_service_entry_is_diagnostic_not_exception(db, value):
    data = contract(db)
    data["services"][0] = value
    save_contract(db, data)
    assert_unknown(db, "release_service_invalid")


def test_duplicate_service_cannot_replace_missing_coverage(db):
    data = contract(db)
    data["services"][1] = copy.deepcopy(data["services"][0])
    save_contract(db, data)
    assert_unknown(db, "release_service_duplicate")


@pytest.mark.parametrize("count", [1, 3])
def test_partial_or_extra_approval_rows_fail_closed(db, count):
    data = contract(db)
    data["services"] = (data["services"] * 2)[:count]
    save_contract(db, data)
    assert_unknown(db, "release_service_coverage_invalid")


@pytest.mark.parametrize(
    "timestamp",
    [
        None,
        123,
        "infinity",
        "-infinity",
        "tomorrow",
        "2026-10-29T10:00:00",
        "2026-99-99T00:00:00Z",
        "2026-10-29T10:00:00+99:99",
    ],
)
@pytest.mark.parametrize("field", ["approved_at", "valid_until"])
def test_invalid_approval_time_is_unknown_for_both_consumers(db, timestamp, field):
    data = contract(db)
    data[field] = timestamp
    save_contract(db, data)
    assert_unknown(db, "release_approval_time_invalid")


@pytest.mark.parametrize("field", ["approved_at", "valid_until"])
def test_future_approval_or_expired_explicit_deadline_fails_closed(db, field):
    data = contract(db)
    moment = db.execute("SELECT now()").fetchone()[0]
    data[field] = (
        moment + timedelta(seconds=1) if field == "approved_at" else moment - timedelta(seconds=1)
    ).isoformat()
    save_contract(db, data)
    assert_unknown(
        db,
        "release_approval_time_invalid" if field == "approved_at" else "release_approval_expired",
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        "NULL",
        "'infinity'::timestamptz",
        "'-infinity'::timestamptz",
        "now()+interval '1 second'",
        "now()-interval '2 minutes'",
    ],
)
def test_masterstatus_review_timestamp_must_support_the_decision(db, timestamp):
    db.execute(
        f"UPDATE public.dufynd_master_status SET last_verified_at={timestamp} WHERE key=%s", (KEY,)
    )
    assert_unknown(db, "release_approval_time_invalid")


def test_old_head_bound_approval_has_no_artificial_ttl_and_honors_optional_deadline(db):
    data = contract(db)
    moment = db.execute("SELECT now()").fetchone()[0]
    data["approved_at"] = (moment - timedelta(days=30)).isoformat()
    data["valid_until"] = (moment + timedelta(days=1)).isoformat()
    save_contract(db, data)
    db.execute("SET LOCAL TIME ZONE 'Pacific/Honolulu'")
    assert helper(db)["status"] == "verified"
    assert technical(db)["status"] == "healthy"


def test_missing_storefront_is_always_visible_without_fabricated_observer(db):
    db.execute(
        "DELETE FROM public.dufynd_task_external_waits WHERE observer_id=%s", (f"render:{STORE}",)
    )
    db.execute(
        "DELETE FROM public.dufynd_external_observers WHERE observer_id=%s", (f"render:{STORE}",)
    )
    result = assert_unknown(db)
    row = service(result, STORE)
    assert row["expectation_status"] == "approved" and row["expected_deployment_sha"] == STORE_SHA
    assert row["observer_id"] is None and row["observation_reason"] == "observer_missing"
    assert row["observation_verified"] is False and row["intent_match"] is None
    assert result["missing_monitor_count"] == 1
    assert "render_monitor_missing" in technical(db)["issues"]
    assert (
        db.execute(
            "SELECT count(*) FROM public.dufynd_external_observers WHERE source_id=%s", (STORE,)
        ).fetchone()[0]
        == 0
    )


def test_additional_enabled_service_requires_its_own_approved_context(db):
    extra = "srv-extra-releasefixture"
    seed_render(db, extra, API_SHA)
    result = assert_unknown(db)
    row = service(result, extra)
    assert result["additional_service_count"] == 1
    assert row["expectation_status"] == "unknown" and row["intent_match"] is None
    assert row["observation_verified"] is True
    assert "render_release_expectation_unknown" in result["issues"]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("enabled=false", "observer_disabled"),
        ("health_status='stale'", "observer_unhealthy"),
        ("health_status='blocked_configuration'", "observer_unhealthy"),
        ("last_success_at=now()-interval '601 seconds'", "observer_success_unverified"),
        ("last_success_at=now()+interval '1 second'", "observer_success_unverified"),
        ("last_success_at='infinity'::timestamptz", "observer_success_unverified"),
        ("last_success_at='-infinity'::timestamptz", "observer_success_unverified"),
        ("last_success_at=NULL", "observer_success_unverified"),
        (
            "last_snapshot=jsonb_set(last_snapshot,'{state}','\"failed\"')",
            "live_deployment_unverified",
        ),
        (
            "last_snapshot=jsonb_set(last_snapshot,'{state}','\"started\"')",
            "live_deployment_unverified",
        ),
        ("last_snapshot=last_snapshot-'deployment_id'", "live_deployment_unverified"),
        (
            "last_snapshot=jsonb_set(last_snapshot,'{deployment_id}','123')",
            "live_deployment_unverified",
        ),
        (
            "last_snapshot=jsonb_set(last_snapshot,'{deployment_id}','\"not-a-deployment\"')",
            "live_deployment_unverified",
        ),
        ("last_snapshot=jsonb_set(last_snapshot,'{sha}','123')", "deployment_identity_invalid"),
        (
            "last_snapshot=jsonb_set(last_snapshot,'{service_id}','\"srv-foreign\"')",
            "deployment_identity_invalid",
        ),
    ],
)
def test_release_intent_never_replaces_current_provider_evidence(db, change, reason):
    db.execute(
        f"UPDATE public.dufynd_external_observers SET {change} WHERE observer_id=%s",
        (f"render:{API}",),
    )
    result = assert_unknown(db)
    row = service(result)
    assert row["expectation_status"] == "approved"
    assert row["observation_verified"] is False and row["observation_reason"] == reason
    assert row["comparison_status"] == "unknown"
    if reason == "deployment_identity_invalid":
        assert row["intent_match"] is None


def test_service_id_cannot_borrow_another_observers_identity(db):
    db.execute(
        "UPDATE public.dufynd_external_observers SET observer_id='render:srv-foreignidentity' WHERE observer_id=%s",
        (f"render:{STORE}",),
    )
    row = service(assert_unknown(db), STORE)
    assert row["observation_reason"] == "observer_identity_invalid" and row["intent_match"] is None


@pytest.mark.parametrize(
    ("mutation", "issue"),
    [
        (
            "UPDATE public.dufynd_external_observers SET health_status='blocked_configuration' WHERE source_type='gmail'",
            "blocked_observer_configuration",
        ),
        (
            "UPDATE public.dufynd_broker_acceptance_sessions SET status='captured' WHERE recurring_read",
            "private_broker_capture_unverified",
        ),
        (
            "UPDATE public.dufynd_broker_acceptance_sessions SET source_sha='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' WHERE recurring_read",
            "private_broker_capture_unverified",
        ),
        (
            "UPDATE public.dufynd_broker_acceptance_sessions SET created_at=now()-interval '1 hour' WHERE recurring_read",
            "private_broker_acceptance_gap",
        ),
        (
            "UPDATE public.dufynd_master_status SET value=value||'{\"enabled\":true}'::jsonb WHERE key='ops.public_api_health_v1'",
            "public_api_health_unavailable",
        ),
    ],
)
def test_aligned_services_do_not_clear_independent_operational_blockers(db, mutation, issue):
    db.execute(mutation)
    assert helper(db)["status"] == "verified"
    assert issue in technical(db)["issues"]
    assert plan(db)["state"] == "technical_remediation_required"
    result = audit(db)
    assert result["status"] == "degraded" and issue in result["issues"]
    assert result["technical_diagnosis_current"] is True and result["planner_starved"] is False
    assert issue in result["technical_work"]["issues"]


@pytest.mark.parametrize("state", ["work_available", "work_in_progress", "owner_gate"])
def test_unknown_release_expectation_never_blocks_real_existing_work(db, state):
    db.execute("DELETE FROM public.dufynd_master_status WHERE key=%s", (KEY,))
    db.execute(
        "UPDATE pg_temp.planner_technical_case SET value=jsonb_build_object('state',%s::text) WHERE key='get_dufynd_next_autonomous_action'",
        (state,),
    )
    result = plan(db)
    assert result["state"] == state
    assert result["reason"] == "existing_work_or_gate_already_explains_next_step"


def test_current_technical_remediation_is_not_unexplained_planner_starvation(db):
    db.execute("DELETE FROM public.dufynd_master_status WHERE key=%s", (KEY,))
    assert plan(db)["state"] == "technical_remediation_required"
    result = audit(db)
    assert result["planner_starved"] is False
    assert result["technical_diagnosis_current"] is True
    assert result["status"] == "degraded"
    assert "planner_starvation" not in result["issues"]
    assert "render_release_expectation_unknown" in result["issues"]


@pytest.mark.parametrize(
    "change",
    [
        "last_verified_at=NULL",
        "last_verified_at='infinity'::timestamptz",
        "last_verified_at=now()+interval '1 second'",
        "last_verified_at=now()-interval '601 seconds'",
        "value=value-'technical_work'",
        "value=jsonb_set(value,'{technical_work,technical_work_remaining}','false')",
        "value=jsonb_set(value,'{technical_work,technical_work_remaining}','\"true\"')",
        "value=jsonb_set(value,'{state}','\"planner_gap\"')",
        "value='null'::jsonb",
    ],
)
def test_unverified_planner_diagnosis_cannot_suppress_starvation(db, change):
    db.execute("DELETE FROM public.dufynd_master_status WHERE key=%s", (KEY,))
    plan(db)
    db.execute(f"UPDATE public.dufynd_master_status SET {change} WHERE key='jarvis.planner_v1'")
    result = audit(db)
    assert result["technical_diagnosis_current"] is False
    assert result["planner_starved"] is True and "planner_starvation" in result["issues"]


def test_resolved_technical_blockers_do_not_hide_unplanned_business_work(db):
    db.execute("DELETE FROM public.dufynd_master_status WHERE key=%s", (KEY,))
    plan(db)
    save_contract(db, contract(db))
    db.execute(
        "UPDATE public.dufynd_autonomy_tasks SET status='blocked' WHERE task_id LIKE 'bizplan:creative-recovery:%'"
    )
    assert technical(db)["technical_work_remaining"] is False
    result = audit(db)
    assert result["technical_diagnosis_current"] is False
    assert result["planner_starved"] is True


def test_diagnosed_monitoring_work_does_not_hide_unclaimed_ready_work(db):
    db.execute("DELETE FROM public.dufynd_master_status WHERE key=%s", (KEY,))
    plan(db)
    db.execute("""INSERT INTO public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,created_at)
        VALUES('release-ready-fixture','supervisor','fixture','fixture','ready',now()-interval '16 minutes')""")
    result = audit(db)
    assert result["technical_diagnosis_current"] is True
    assert result["planner_starved"] is False
    assert result["stalled_ready"] >= 1 and "ready_work_not_claimed" in result["issues"]


def test_real_release_audit_and_paused_gmail_wrapper_preserve_unresolved_truth(db):
    from tests.test_dufynd_gmail_pause_projection_postgres import function_sql as gmail_function_sql

    migrations = ROOT / "supabase/migrations"
    db.execute("""
        CREATE TABLE IF NOT EXISTS public.dufynd_observer_credentials(
          credential_id text primary key,provider text,account_alias text,
          allowed_operations jsonb,allowed_resources jsonb,oauth_scopes jsonb,
          secret_reference text,status text,expires_at timestamptz,refreshed_at timestamptz,
          revoked_at timestamptz,last_health_check timestamptz,rotation_due_at timestamptz,
          health_reason text,activation_enabled boolean);
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
        UPDATE public.dufynd_external_observers SET enabled=false WHERE source_type='gmail';
        DELETE FROM public.dufynd_master_status WHERE key IN
          ('ops.gmail_observer.alert_v1','ops.private_observer.last_failure',
           'ops.gmail_observer_expiration_incident_20261010');
        INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
        VALUES('jarvis.private_observer_scheduler_v1','jarvis',
          '{"gmail_recovery_paused":true,"owner_action_required":false}',100,now())
        ON CONFLICT(key) DO UPDATE SET value=excluded.value,last_verified_at=excluded.last_verified_at;
    """)
    for identity in ("1a0f385ed98c6af8", "1a0f69c169fb928f", "1a0f6a90772a743d"):
        db.execute(
            """INSERT INTO public.dufynd_external_observers
            (observer_id,source_type,source_id,enabled,interval_seconds,health_status,last_success_at,next_retry_at)
            VALUES(%s,'gmail',%s,true,120,'blocked_configuration',now()-interval '2 hours',now()+interval '2 minutes')
            ON CONFLICT(observer_id) DO UPDATE SET enabled=true,health_status='blocked_configuration',
              last_success_at=excluded.last_success_at,next_retry_at=excluded.next_retry_at""",
            ("gmail:" + identity, identity),
        )
    db.execute(
        gmail_function_sql(
            migrations / "20261002161040_dufynd_observer_credential_plane.sql",
            "get_dufynd_credential_health",
        )
    )
    db.execute(
        gmail_function_sql(
            migrations / "20261002064614_dufynd_supervisor_v2_phase1.sql", "dufynd_parse_timestamp"
        )
    )
    base_audit = db.execute(
        "SELECT pg_get_functiondef('public.audit_dufynd_integrity_v1()'::regprocedure)"
    ).fetchone()[0]
    db.execute(
        (migrations / "20261029100518_dufynd_gmail_recovery_pause_projection.sql").read_text()
    )
    assert (
        db.execute(
            "SELECT pg_get_functiondef('public.audit_dufynd_integrity_v1()'::regprocedure)"
        ).fetchone()[0]
        == base_audit
    )

    evidence_query = """SELECT
        (SELECT jsonb_agg(to_jsonb(o) ORDER BY observer_id) FROM public.dufynd_external_observers o),
        (SELECT jsonb_agg(to_jsonb(c) ORDER BY credential_id) FROM public.dufynd_observer_credentials c),
        (SELECT jsonb_agg(to_jsonb(t) ORDER BY task_id) FROM public.dufynd_autonomy_tasks t),
        (SELECT to_jsonb(m) FROM public.dufynd_master_status m WHERE key='jarvis.private_observer_scheduler_v1')"""
    before = db.execute(evidence_query).fetchone()
    assert plan(db)["state"] == "technical_remediation_required"
    result = db.execute("SELECT public.audit_dufynd_integrity_with_gmail_v1()").fetchone()[0]
    assert result["status"] == "degraded"
    assert result["technical_diagnosis_current"] is True and result["planner_starved"] is False
    for issue in (
        "blocked_observer_configuration",
        "private_observer_stale",
        "private_observer_unhealthy",
        "private_broker_capture_unverified",
    ):
        assert issue in result["issues"] and issue in result["technical_work"]["issues"]
    assert "planner_starvation" not in result["issues"]
    assert result["render_release_expectations"]["status"] == "verified"
    assert result["technical_work"]["blocked_observers"] == 3
    assert (
        result["gmail_recovery_paused"] is True and result["gmail_reauthorization_required"] is True
    )
    assert result["owner_action_required"] is False
    alert = result["gmail_alert"]
    assert alert["state"] == "credential_revoked" and alert["credential"]["status"] == "revoked"
    assert alert["reauthorization_required"] is True and alert["owner_action_required"] is False
    assert alert["recovery_paused"] is True and alert["fresh_successes"] == 0
    assert alert["pause_policy_source"] == "jarvis.private_observer_scheduler_v1"
    assert alert["action"].startswith("No current owner action:") and "POST" not in alert["action"]
    assert alert["email_sent"] is False and alert["new_spend_usd"] == 0
    assert db.execute(evidence_query).fetchone() == before
    assert (
        db.execute(
            "SELECT value FROM public.dufynd_master_status WHERE key='jarvis.integrity_v1'"
        ).fetchone()[0]
        == result
    )


def test_readers_do_not_mutate_observations_approvals_or_tasks_and_acl_is_preserved(db):
    before = db.execute(
        "SELECT jsonb_agg(to_jsonb(o) ORDER BY observer_id) FROM public.dufynd_external_observers o"
    ).fetchone()[0]
    approval = db.execute(
        "SELECT to_jsonb(m) FROM public.dufynd_master_status m WHERE key=%s", (KEY,)
    ).fetchone()[0]
    tasks = db.execute(
        "SELECT jsonb_agg(to_jsonb(t) ORDER BY task_id) FROM public.dufynd_autonomy_tasks t"
    ).fetchone()[0]
    helper(db)
    technical(db)
    audit(db)
    db.execute(MIGRATION.read_text())
    assert (
        db.execute(
            "SELECT jsonb_agg(to_jsonb(o) ORDER BY observer_id) FROM public.dufynd_external_observers o"
        ).fetchone()[0]
        == before
    )
    assert (
        db.execute(
            "SELECT to_jsonb(m) FROM public.dufynd_master_status m WHERE key=%s", (KEY,)
        ).fetchone()[0]
        == approval
    )
    assert (
        db.execute(
            "SELECT jsonb_agg(to_jsonb(t) ORDER BY task_id) FROM public.dufynd_autonomy_tasks t"
        ).fetchone()[0]
        == tasks
    )
    assert db.execute(
        "SELECT bool_and(p.proacl IS NOT DISTINCT FROM b.proacl AND p.prosecdef=b.prosecdef AND p.provolatile=b.provolatile AND p.proconfig=b.proconfig) FROM pg_proc p JOIN pg_temp.release_fixture_acl b USING(oid)"
    ).fetchone()[0]
    assert db.execute(
        "SELECT provolatile='s' AND NOT prosecdef AND proconfig=ARRAY['search_path=public'] FROM pg_proc WHERE oid='public.read_dufynd_render_release_expectations_v1()'::regprocedure"
    ).fetchone()[0]
    assert db.execute(
        "SELECT has_function_privilege('anon','public.read_dufynd_render_release_expectations_v1()','execute'),has_function_privilege('authenticated','public.read_dufynd_render_release_expectations_v1()','execute'),has_function_privilege('service_role','public.read_dufynd_render_release_expectations_v1()','execute')"
    ).fetchone() == (False, False, True)
