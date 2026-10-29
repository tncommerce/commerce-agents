"""Real public-health readers feed the existing planner/audit, without HTTP."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from tests.test_dufynd_planner_technical_blockers_postgres import (
    db as planner_database,  # noqa: F401
)
from tests.test_dufynd_service_release_expectations_postgres import (
    API,
    STORE,
    audit,
    plan,
    technical,
)
from tests.test_dufynd_service_release_expectations_postgres import (
    db as release_database,  # noqa: F401
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261029104331_dufynd_public_storefront_health_planner.sql"
STOREFRONT = ROOT / "supabase/migrations/20261029104253_dufynd_public_storefront_health.sql"
KEY = "ops.public_storefront_health_v1"
pytestmark = pytest.mark.skipif(
    not os.getenv("DUFYND_TEST_DATABASE_URL"), reason="dedicated disposable PostgreSQL required"
)


def reader_definition():
    source = STOREFRONT.read_text()
    match = re.search(
        r"create or replace function public\.read_dufynd_public_storefront_health_v1\(\).*?\bas\s+(\$[A-Za-z_0-9]*\$)",
        source,
        re.I | re.S,
    )
    assert match
    end = source.index(match[1], match.end()) + len(match[1])
    return source[match.start() : end] + ";"


@pytest.fixture
def db(release_database):  # noqa: F811
    connection = release_database
    # The receipt transport and HTML validation have their own native PG suite.
    # Install the actual final reader here; there is no network function to call.
    connection.execute(reader_definition())
    connection.execute(
        """INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
        VALUES(%s,'operations','{"enabled":false,"status":"disabled"}',90,now())
        ON CONFLICT(key) DO UPDATE SET value=excluded.value,last_verified_at=excluded.last_verified_at""",
        (KEY,),
    )
    connection.execute(MIGRATION.read_text())
    yield connection


def patch(db, values, key=KEY):
    db.execute(
        "UPDATE public.dufynd_master_status SET value=value||%s::jsonb WHERE key=%s",
        (json.dumps(values), key),
    )


def healthy_storefront(db):
    db.execute(
        """UPDATE public.dufynd_master_status SET value=jsonb_build_object(
        'enabled',true,'status','healthy','last_status_code',200,
        'html_contract','dufynd_home_v1','last_response_bytes',32522,
        'last_success_at',now()-interval '10 seconds',
        'valid_until',now()+interval '590 seconds') WHERE key=%s""",
        (KEY,),
    )


def task_fingerprint(db):
    return db.execute(
        """SELECT md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY task_id),'[]'::jsonb)::text)
        FROM public.dufynd_autonomy_tasks t"""
    ).fetchone()[0]


@pytest.mark.parametrize(
    ("state", "issue"),
    [
        ("pending", "public_storefront_health_pending"),
        ("stale", "public_storefront_health_stale"),
        ("unhealthy", "public_storefront_unhealthy"),
        ("unavailable", "public_storefront_health_unavailable"),
    ],
)
def test_current_storefront_problem_reaches_planner_and_integrity(db, state, issue):
    patch(db, {"enabled": True, "status": state})
    if state == "pending":
        db.execute(
            "UPDATE public.dufynd_master_status SET value=value||jsonb_build_object('request_id',123,'requested_at',now()) WHERE key=%s",
            (KEY,),
        )
    before = task_fingerprint(db)
    report = technical(db)
    assert report["issues"] == [issue]
    assert report["private_technical_work_remaining"] is False
    assert report["public_storefront_health"]["scope"] == "public_storefront_liveness_only"
    planned = plan(db)
    assert planned["state"] == "technical_remediation_required"
    assert planned["action"] == "diagnose_public_storefront_health"
    result = audit(db)
    assert result["status"] == "degraded" and issue in result["issues"]
    assert result["technical_diagnosis_current"] is True
    assert result["planner_starved"] is False
    assert result["technical_work"]["public_storefront_health"]["healthy"] is False
    assert result["technical_work"]["technical_repair_executed"] is False
    assert task_fingerprint(db) == before


def test_disabled_monitor_is_visible_without_a_false_outage(db):
    result = technical(db)
    assert result["public_storefront_health"]["enabled"] is False
    assert result["public_storefront_health"]["status"] == "disabled"
    assert result["issues"] == []
    assert plan(db)["state"] == "waiting_market_signal"


def test_valid_public_receipt_preserves_existing_market_wait_without_new_tasks(db):
    healthy_storefront(db)
    before = task_fingerprint(db)
    result = technical(db)
    assert result["status"] == "healthy" and result["issues"] == []
    public = result["public_storefront_health"]
    assert public["healthy"] is True
    for flag in (
        "private_observer_evidence",
        "full_chain_complete",
        "deployment_revision_verified",
        "redirect_chain_verified",
        "final_origin_verified",
    ):
        assert public[flag] is False
    assert plan(db)["state"] == "waiting_market_signal"
    assert audit(db)["status"] == "healthy"
    assert task_fingerprint(db) == before


@pytest.mark.parametrize("service_id", [API, STORE])
def test_public_html_success_cannot_replace_private_deployment_evidence(db, service_id):
    healthy_storefront(db)
    db.execute(
        "UPDATE public.dufynd_external_observers SET last_success_at=now()-interval '1 hour',health_status='stale' WHERE observer_id=%s",
        (f"render:{service_id}",),
    )
    result = technical(db)
    assert result["public_storefront_health"]["healthy"] is True
    assert result["private_technical_work_remaining"] is True
    assert "render_release_observation_unverified" in result["issues"]
    planned = plan(db)
    assert planned["state"] == "technical_remediation_required"
    assert planned["action"] == "diagnose_private_observer_runtime"
    assert audit(db)["status"] == "degraded"


def test_public_html_success_does_not_hide_independent_api_outage(db):
    healthy_storefront(db)
    patch(db, {"enabled": True, "status": "unhealthy"}, "ops.public_api_health_v1")
    result = technical(db)
    assert result["public_storefront_health"]["healthy"] is True
    assert result["issues"] == ["public_api_unhealthy"]
    planned = plan(db)
    assert planned["state"] == "technical_remediation_required"
    assert planned["action"] == "diagnose_public_api_health"
    assert "public_api_unhealthy" in audit(db)["issues"]


def test_two_independent_public_failures_remain_separate_diagnostics(db):
    patch(db, {"enabled": True, "status": "unhealthy"})
    patch(db, {"enabled": True, "status": "unavailable"}, "ops.public_api_health_v1")
    expected = {"public_api_health_unavailable", "public_storefront_unhealthy"}
    assert set(technical(db)["issues"]) == expected
    planned = plan(db)
    assert planned["state"] == "technical_remediation_required"
    assert planned["action"] == "diagnose_public_api_health"
    assert expected <= set(audit(db)["issues"])


def test_reader_expiry_reaches_integrity_without_another_poll(db):
    healthy_storefront(db)
    db.execute(
        """UPDATE public.dufynd_master_status SET value=value||jsonb_build_object(
        'last_success_at',now()-interval '601 seconds','valid_until',now()-interval '1 second') WHERE key=%s""",
        (KEY,),
    )
    assert technical(db)["issues"] == ["public_storefront_health_stale"]
    assert plan(db)["state"] == "technical_remediation_required"
    assert "public_storefront_health_stale" in audit(db)["issues"]


def test_short_pending_request_preserves_last_valid_receipt_without_outage(db):
    healthy_storefront(db)
    db.execute(
        "UPDATE public.dufynd_master_status SET value=value||jsonb_build_object('request_id',123,'requested_at',now()-interval '40 seconds') WHERE key=%s",
        (KEY,),
    )
    before = db.execute(
        "SELECT value->'last_success_at' FROM public.dufynd_master_status WHERE key=%s", (KEY,)
    ).fetchone()[0]
    result = technical(db)
    assert result["public_storefront_health"]["healthy"] is True
    assert result["public_storefront_health"]["request_pending"] is True
    assert result["issues"] == []
    assert result["public_storefront_health"]["last_success_at"] == before
    assert plan(db)["state"] == "waiting_market_signal"
