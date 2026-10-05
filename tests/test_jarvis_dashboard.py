from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from retail.api.jarvis_dashboard import (
    MASTER_READS,
    DashboardReader,
    DashboardUnavailable,
    build_snapshot,
    create_dashboard_router,
)

NOW = datetime(2026, 10, 3, 16, 0, tzinfo=UTC)
STAMP = NOW.isoformat()


def fixture_data():
    return {
        "tasks": [
            {
                "task_id": "publish",
                "title": "Publish launch content",
                "status": "waiting_human_input",
                "requires_human_approval": True,
                "approval_action_type": "publish_content",
                "priority": 100,
            },
            {
                "task_id": "rights",
                "title": "Review incoming images",
                "status": "waiting_external",
                "requires_human_approval": True,
            },
            {
                "task_id": "audit",
                "title": "Attribution audit",
                "status": "ready",
                "worker_state": "queued",
                "blocked_reason": "budget_exhausted",
            },
        ],
        "recent_done": [
            {
                "task_id": "old",
                "title": "Already completed",
                "status": "done",
                "requires_human_approval": True,
            }
        ],
        "active_runs": [],
        "recent_runs": [],
        "observers": [
            {
                "observer_id": "github_branch:scentai-mvp",
                "source_type": "github_branch",
                "health_status": "healthy",
                "enabled": True,
                "last_success_at": STAMP,
                "observed_sha": "a" * 40,
                "interval_seconds": 120,
            }
        ],
        "credentials": [],
        "inbox": [],
        "checkpoint": [
            {
                "observed_at": STAMP,
                "paid_enabled": False,
                "priority": "Observer acceptance",
                "next_action": "Read current health",
            }
        ],
        "supervisor": [{"checked_at": STAMP}],
        "lease": [],
        "smoke": [],
    }


def run_row(**overrides):
    return {
        "execution_id": "run-1",
        "task_id": "work",
        "worker_id": "worker-1",
        "worker_type": "github_actions",
        "status": "running",
        "heartbeat_at": STAMP,
        "last_progress_at": STAMP,
        "started_at": STAMP,
        "lease_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        **overrides,
    }


def test_decisions_only_include_actual_waiting_human_not_future_or_terminal_approval_flags():
    result = build_snapshot(fixture_data(), now=NOW)
    assert result["decision_center"] == [
        {"task_id": "publish", "title": "Publish launch content", "type": "publish_content"}
    ]
    assert result["command_center"]["active_workers"] == 0
    assert result["mission_board"]["BLOCKED"][0]["task_id"] == "audit"
    assert not result["mission_board"]["READY"]
    assert result["budget"]["paid_model_execution"] == "OFF"
    assert result["budget"]["remaining_usd"] is None


@pytest.mark.parametrize(
    "override,expected",
    [
        ({}, "ACTIVE"),
        ({"lease_expires_at": STAMP}, "STALE"),
        ({"heartbeat_at": (NOW - timedelta(minutes=4)).isoformat()}, "STALE"),
        ({"heartbeat_at": (NOW + timedelta(minutes=1)).isoformat()}, "STALE"),
        ({"last_progress_at": (NOW - timedelta(minutes=11)).isoformat()}, "WAITING"),
        ({"completed_at": STAMP}, "IDLE"),
    ],
)
def test_worker_health_never_calls_expired_missing_or_future_heartbeats_active(override, expected):
    data = fixture_data()
    data["active_runs"] = [run_row(**override)]
    data["recent_runs"] = [run_row(**override)]
    result = build_snapshot(data, now=NOW)
    assert len(result["worker_deck"]) == 1
    assert result["worker_deck"][0]["status"] == expected
    assert result["command_center"]["active_workers"] == (1 if expected == "ACTIVE" else 0)


def test_task_lease_worker_without_execution_is_visible():
    data = fixture_data()
    data["tasks"].append({**run_row(), "worker_state": "working", "worker_owner": "chat-worker"})
    result = build_snapshot(data, now=NOW)
    assert result["worker_deck"][0]["worker_type"] == "task_lease"
    assert result["command_center"]["active_workers"] == 1


@pytest.mark.parametrize(
    "health,last_success,expected",
    [
        ("healthy", STAMP, "HEALTHY"),
        ("healthy", (NOW - timedelta(hours=1)).isoformat(), "STALE"),
        ("blocked_configuration", STAMP, "BLOCKED"),
        ("initializing", None, "UNKNOWN"),
        ("unrecognized", STAMP, "UNKNOWN"),
    ],
)
def test_observer_health_uses_own_freshness_and_blockers(health, last_success, expected):
    data = fixture_data()
    data["observers"].append(
        {
            "observer_id": "gmail:thread",
            "source_type": "gmail",
            "enabled": True,
            "health_status": health,
            "last_success_at": last_success,
        }
    )
    result = build_snapshot(data, now=NOW)
    assert result["system_health"][2]["health"] == expected
    assert (
        result["command_center"]["status"] == "ERROR"
    )  # Missing live loop evidence is an error; observer warning is separate.


def test_stale_checkpoint_and_supervisor_are_explicit():
    data = fixture_data()
    data["checkpoint"][0]["observed_at"] = (NOW - timedelta(days=1)).isoformat()
    data["supervisor"][0]["checked_at"] = (NOW - timedelta(minutes=7)).isoformat()
    result = build_snapshot(data, now=NOW)
    assert result["command_center"]["checkpoint_stale"]
    assert result["command_center"]["next_supervisor_wake_estimate"] is None
    assert result["system_health"][3]["health"] == "STALE"


def test_allowlist_drops_nested_payloads_tokens_email_bodies_and_arbitrary_errors():
    data = fixture_data()
    marker = "highly-sensitive-marker"
    for rows in data.values():
        for row in rows:
            row.update(
                {
                    "payload": {"body": marker},
                    "secret_reference": marker,
                    "lease_token": marker,
                    "last_error": marker,
                    "last_checkpoint": {"token": marker},
                    "external_observation": {"body": marker},
                    "evidence": marker,
                }
            )
    data["credentials"] = [{"provider": "gmail", "status": "healthy", "secret_reference": marker}]
    data["tasks"][0]["title"] = "Secret " + marker
    data["tasks"][0]["owner"] = "Bearer a-token"
    data["tasks"][0]["expected_next_checkpoint"] = "Reply to person@example.org"
    encoded = json.dumps(build_snapshot(data, now=NOW, secrets=(marker,)))
    assert marker not in encoded
    assert "a-token" not in encoded
    assert "person@example.org" not in encoded
    assert "last_checkpoint" not in encoded
    assert "secret_reference" not in encoded
    assert "[restricted]" in encoded


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", {}, True, "1e999"])
def test_budget_rejects_invalid_or_unbounded_numbers(amount):
    data = fixture_data()
    data["budget"] = [{"cap_usd": amount}]
    assert build_snapshot(data, now=NOW)["budget"]["cap_usd"] is None


def test_budget_uses_authoritative_reservation_aware_values_without_recomputing():
    data = fixture_data()
    data["budget"] = [
        {
            "cap_usd": "2.50",
            "spent_usd": "0.20",
            "remaining_usd": "1.90",
            "reserved_unsettled_usd": "0.40",
            "runs": 3,
        }
    ]
    result = build_snapshot(data, now=NOW)
    assert result["budget"]["remaining_usd"] == "1.90"
    assert result["budget"]["reserved_unsettled_usd"] == "0.40"


def test_truncated_operational_reads_cannot_claim_complete_healthy_state():
    data = fixture_data()
    counts = {name: len(rows) for name, rows in data.items()}
    counts["active_runs"] = 999
    result = build_snapshot(data, now=NOW, source_counts=counts)
    assert not result["freshness"]["operational_complete"]
    assert (
        next(h for h in result["system_health"] if h["name"] == "Execution Plane")["health"]
        == "UNKNOWN"
    )
    assert result["command_center"]["status"] == "ERROR"


def make_transport(data, calls, *, failure=None):
    def respond(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.host == "bqsdxaagklpkxioaqdqa.supabase.co"
        assert request.headers["apikey"] == "test-secret"
        if failure is not None:
            return failure(request)
        table = request.url.path.rsplit("/", 1)[-1]
        if table == "dufynd_master_status":
            key = request.url.params["key"][3:]
            name = next(name for name, (master_key, _) in MASTER_READS.items() if master_key == key)
        elif table == "dufynd_autonomy_tasks":
            name = "recent_done" if request.url.params["status"] == "eq.done" else "tasks"
        elif table == "dufynd_execution_runs":
            name = "active_runs" if "status" in request.url.params else "recent_runs"
        elif table == "get_dufynd_jarvis_budget_status":
            return httpx.Response(200, json={"cap_usd": "2.50"})
        elif table == "read_dufynd_first_money_runtime":
            return httpx.Response(200, json=(data.get("first_money_runtime") or [{}])[0])
        else:
            name = {
                "dufynd_external_observers": "observers",
                "dufynd_task_external_waits": "external_waits",
                "dufynd_observer_credentials": "credentials",
                "dufynd_jarvis_inbox": "inbox",
                "dufynd_human_decisions": "decisions",
                "scentai_analytics_events": "first_money_events",
                "dufynd_budget_reservations": "open_costs"
                if "status" in request.url.params
                else "daily_costs",
            }[table]
        rows = data.get(name, [])
        return httpx.Response(200, json=rows, headers={"content-range": f"0-0/{len(rows)}"})

    return httpx.MockTransport(respond)


def test_reader_requests_fixed_allowlisted_columns_no_generic_queries_or_provider_calls():
    calls = []
    reader = DashboardReader(
        secret_key="test-secret",
        budget_id="nightshift",
        transport=make_transport(fixture_data(), calls),
    )
    result = reader.snapshot(now=NOW)
    assert result["command_center"]["observed_head_sha"] == "a" * 40
    assert len(calls) == 23
    for call in calls:
        selected = call.url.params.get("select", "")
        assert "*" not in selected
        assert not any(
            word in selected
            for word in (
                "secret_reference",
                "lease_token",
                "payload",
                "last_error",
                "config",
            )
        )
        assert not ("value" in selected and "value->" not in selected)
        assert not any(field == "last_checkpoint" for field in selected.split(","))


def test_checkpoint_is_only_a_scalar_projection_and_known_secrets_are_hidden_in_enums():
    data = fixture_data()
    data["tasks"][0]["domain"] = "testsecret"
    data["active_runs"] = [
        run_row(
            checkpoint_step="read",
            checkpoint_verified=True,
            checkpoint_verified_at=STAMP,
            last_checkpoint={"body": "must-not-leak"},
        )
    ]
    result = build_snapshot(data, now=NOW, secrets=("testsecret",))
    assert result["mission_board"]["WAITING HUMAN"][0]["domain"] is None
    assert result["worker_deck"][0]["checkpoint"] == {
        "step": "read",
        "verified": True,
        "verified_at": STAMP,
    }
    assert "must-not-leak" not in json.dumps(result)


def test_credential_expiry_is_visible_even_if_stored_status_has_not_been_reconciled():
    data = fixture_data()
    data["credentials"] = [
        {
            "provider": "gmail",
            "status": "healthy",
            "expires_at": (NOW - timedelta(minutes=1)).isoformat(),
        }
    ]
    result = build_snapshot(data, now=NOW)
    assert result["system_health"][2]["credentials"][0]["effective_status"] == "expired"


@pytest.mark.parametrize(
    "status,expected",
    [
        ("dispatch_pending", "WAITING"),
        ("waiting_external", "WAITING"),
        ("waiting_human", "WAITING"),
        ("retryable", "WAITING"),
        ("stale", "STALE"),
        ("failed_terminal", "FAILED"),
    ],
)
def test_all_nonterminal_durable_states_stay_visible_outside_recent_history(status, expected):
    data = fixture_data()
    data["active_runs"] = [run_row(status=status, checkpoint_step="0")]
    data["recent_runs"] = [run_row(execution_id="recent", status="completed", completed_at=STAMP)]
    calls = []
    result = DashboardReader(
        secret_key="test-secret", transport=make_transport(data, calls)
    ).snapshot(now=NOW)
    old_worker = next(row for row in result["worker_deck"] if row["execution_id"] == "run-1")
    assert old_worker["status"] == expected
    assert old_worker["checkpoint"]["step"] == 0
    nonterminal_query = next(
        call
        for call in calls
        if "status" in call.url.params and call.url.path.endswith("dufynd_execution_runs")
    )
    assert nonterminal_query.url.params["status"] == "not.in.(completed,failed_terminal)"


def test_only_explicit_credential_owner_gates_add_decisions_and_unknown_task_cost_is_blocked():
    data = fixture_data()
    data["credentials"] = [
        {"provider": "gmail", "status": "expired"},
        {"provider": "render", "status": "revoked"},
    ]
    data["tasks"].append({"task_id": "cost", "status": "ready", "provider_cost_unknown": True})
    result = build_snapshot(data, now=NOW)
    assert len(result["decision_center"]) == 2
    assert result["decision_center"][1]["provider"] == "render"
    assert result["budget"]["unknown_provider_cost_task_count"] == 1
    assert any(row["task_id"] == "cost" for row in result["mission_board"]["BLOCKED"])


@pytest.mark.parametrize(
    "response",
    [
        lambda _: httpx.Response(401, json={"secret": "DO NOT LEAK"}),
        lambda _: httpx.Response(302, headers={"location": "https://attacker.example"}),
        lambda _: httpx.Response(200, json={"unexpected": "DO NOT LEAK"}),
        lambda _: httpx.Response(200, text="DO NOT LEAK"),
    ],
)
def test_read_errors_fail_closed_without_partial_results_or_upstream_text(response):
    reader = DashboardReader(
        secret_key="test-secret", transport=make_transport({}, [], failure=response)
    )
    with pytest.raises(DashboardUnavailable, match="^Dashboard read unavailable$"):
        reader.snapshot(now=NOW)


def test_no_owner_auth_is_denied_before_any_reads_and_not_in_openapi():
    calls = []
    reader = DashboardReader(
        secret_key="test-secret", transport=make_transport(fixture_data(), calls)
    )
    app = FastAPI()
    app.include_router(create_dashboard_router(reader))
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer test-secret"}, {"X-Owner": "true"}):
            assert client.get("/internal/jarvis/snapshot", headers=headers).status_code == 404
        assert "/internal/jarvis/snapshot" not in client.get("/openapi.json").json()["paths"]
        assert client.post("/internal/jarvis/snapshot").status_code == 405
    assert calls == []


def test_owner_verifier_must_allow_access_and_success_response_is_private_no_store():
    calls = []
    reader = DashboardReader(
        secret_key="test-secret", transport=make_transport(fixture_data(), calls)
    )
    app = FastAPI()
    checks = []

    def verify_owner():
        checks.append(True)

    app.include_router(create_dashboard_router(reader, authorize_owner=verify_owner))
    with TestClient(app) as client:
        response = client.get("/internal/jarvis/snapshot")
    assert response.status_code == 200
    assert checks == [True]
    assert response.headers["cache-control"] == "private, no-store"
    assert "test-secret" not in response.text
    assert calls


def test_rejected_authenticated_nonowner_does_not_read_database():
    calls = []

    def reject_nonowner():
        raise HTTPException(403, "Forbidden")

    reader = DashboardReader(secret_key="test-secret", transport=make_transport({}, calls))
    app = FastAPI()
    app.include_router(create_dashboard_router(reader, authorize_owner=reject_nonowner))
    with TestClient(app) as client:
        assert client.get("/internal/jarvis/snapshot").status_code == 403
    assert calls == []


def test_adapter_returns_safe_no_store_unavailable_when_upstream_fails():
    reader = DashboardReader(
        secret_key="test-secret",
        transport=make_transport(
            {}, [], failure=lambda _: httpx.Response(503, text="upstream-secret")
        ),
    )
    app = FastAPI()
    app.include_router(create_dashboard_router(reader, authorize_owner=lambda: None))
    with TestClient(app) as client:
        response = client.get("/internal/jarvis/snapshot")
    assert response.status_code == 503
    assert response.json() == {"status": "UNAVAILABLE"}
    assert response.headers["cache-control"] == "private, no-store"


def test_production_api_does_not_mount_dashboard_before_auth_decision():
    from pathlib import Path

    main = Path("examples/retail/api/main.py").read_text()
    assert "create_dashboard_router" not in main
    assert "jarvis_dashboard" not in main


def ceo_data():
    data = fixture_data()
    data["tasks"] = []
    data.update(
        thin=[
            {
                "observed_at": STAMP,
                "stop_reason": "waiting_external",
                "active_leases": 0,
                "stale_leases": 0,
                "open_reservations": 0,
                "provider_cost_unknown": False,
                "done": 78,
                "waiting_external": 14,
            }
        ],
        thin_config=[{"enabled": True}],
        ci=[{"sha": "a" * 40, "ready": True, "checked_at": STAMP}],
        decisions=[],
        daily_costs=[],
        open_costs=[],
        first_money_events=[],
    )
    return data


def test_ceo_waits_with_nothing_for_owner_despite_degraded_observer():
    result = build_snapshot(ceo_data(), now=NOW)
    assert result["command_center"]["status"] == "WAITING"
    assert result["command_center"]["owner_action"] == "NICHTS"
    assert result["runtime_safety"]["today_new_cost_usd"] == "0"
    assert result["queue"]["done"] == 78
    assert result["first_money"]["transactions"] is None
    assert result["first_money"]["commission_eur"] is None


def test_ceo_real_decision_even_without_task_contains_exact_go_and_safe_scalars():
    data = ceo_data()
    data["decisions"] = [
        {
            "decision_id": "gate1",
            "title": "Review scope",
            "decision_token": "GO-JARVIS-THIN-ABC",
            "risk": "bearer secret",
            "cost_usd": None,
            "context": {"secret": "never-forward"},
        }
    ]
    result = build_snapshot(data, now=NOW)
    assert result["command_center"]["status"] == "OWNER GATE"
    assert result["decision_center"][0]["go_token"] == "GO-JARVIS-THIN-ABC"
    assert result["decision_center"][0]["risk"] == "[restricted]"
    assert "never-forward" not in json.dumps(result)


def test_ceo_deduplicates_analytics_and_does_not_leak_identifiers_or_invent_sales():
    data = ceo_data()
    event = {"event_id": "evt1", "session_key": "private-hash", "event": "merchant_clickout"}
    data["first_money_events"] = [
        event,
        event,
        {"event_id": "evt2", "session_key": "private-hash", "event": "fragrance_detail_view"},
    ]
    result = build_snapshot(data, now=NOW)
    assert result["first_money"]["sessions"] == 1
    assert result["first_money"]["merchant_clickouts"] == 1
    assert result["first_money"]["product_views"] == 1
    assert result["first_money"]["transactions"] is None
    assert "private-hash" not in json.dumps(result)
    assert "evt1" not in json.dumps(result)


def test_ceo_stale_loop_moved_head_and_partial_counts_never_healthy():
    data = ceo_data()
    data["thin"][0]["observed_at"] = (NOW - timedelta(hours=1)).isoformat()
    data["ci"][0]["sha"] = "b" * 40
    counts = {k: len(v) for k, v in data.items()}
    counts["first_money_events"] = 99999
    result = build_snapshot(data, now=NOW, source_counts=counts)
    assert result["command_center"]["status"] == "ERROR"
    assert result["queue"]["done"] is None
    assert not result["first_money"]["analytics_complete"]
    assert (
        next(h for h in result["system_health"] if h["name"].startswith("CI"))["health"]
        == "DEGRADED"
    )


@pytest.mark.parametrize("status", ["dispatched", "cost_unknown", "charged_max"])
def test_ceo_unsettled_cost_never_shown_as_zero(status):
    data = ceo_data()
    data["daily_costs"] = [{"status": status, "actual_usd": None}]
    data["open_costs"] = [{"status": status}]
    result = build_snapshot(data, now=NOW)
    assert result["runtime_safety"]["today_new_cost_usd"] is None
    assert result["runtime_safety"]["provider_cost_unknown"] is True


def test_ceo_workstreams_next_and_waiting_preserve_unknown_and_priority():
    data = fixture_data()
    data["tasks"] += [
        {"task_id": "later", "title": "Later", "domain": "tech", "status": "ready", "priority": 2},
        {"task_id": "first", "title": "First", "domain": "tech", "status": "ready", "priority": 99},
    ]
    result = build_snapshot(data, now=NOW)
    assert [t["task_id"] for t in result["next_tasks"]] == ["first", "later"]
    assert result["waiting"]["external"] == 1
    assert result["waiting"]["budget"] == 1
    assert result["waiting"]["technical"] == 0
    assert next(w for w in result["workstreams"] if w["name"] == "Content")["status"] == "NO DATA"
    assert result["first_money"]["runtime"]["landing_sessions"] is None
    assert result["first_money"]["transactions"] is None
    assert result["first_money"]["commission_eur"] is None


def test_first_money_runtime_projection_never_forwards_raw_rpc_payload():
    data = fixture_data()
    data["first_money_runtime"] = [
        {
            "phase": "prelaunch",
            "observed_at": STAMP,
            "funnel": {"landing_sessions": 1, "by_source": [{"private": "hidden-marker"}]},
            "purchase_evidence": {"last_verified_at": STAMP, "raw": "hidden-marker"},
            "payload": "hidden-marker",
        }
    ]
    result = build_snapshot(data, now=NOW)
    assert result["first_money"]["runtime"]["landing_sessions"] == 1
    assert "hidden-marker" not in json.dumps(result)


@pytest.mark.parametrize(
    ("post_state", "observed_at", "expected"),
    [
        ("SCHEDULED", STAMP, "SCHEDULED"),
        ("PUBLISHED", STAMP, "LIVE"),
        ("FAILED", STAMP, "BLOCKED"),
        ("SCHEDULED", (NOW - timedelta(hours=2)).isoformat(), "STALE"),
    ],
)
def test_content_workstream_uses_publication_evidence_without_inventing_worker(
    post_state, observed_at, expected
):
    data = ceo_data()
    data["publication"] = [{"status0": post_state, "observed_at": observed_at}]
    result = build_snapshot(data, now=NOW)
    content = next(w for w in result["workstreams"] if w["name"] == "Content")
    assert content["status"] == expected
    assert content["tasks"] == 0
    assert content["next_task"] is None
    assert content["evidence_note"]
    assert result["first_money"]["analytics_provenance"] == "unclassified_may_include_tests"


def test_ceo_gate_and_external_monitoring_are_truthful():
    data = fixture_data()
    data["thin"] = [{"observed_at": STAMP, "stop_reason": "waiting_external"}]
    data["thin_config"] = [{"enabled": True}]
    data["decisions"] = []
    data["tasks"] = [
        {
            "task_id": "external",
            "domain": "affiliate",
            "title": "Await reply",
            "status": "waiting_external",
            "requires_human_approval": True,
        }
    ]
    result = build_snapshot(data, now=NOW)
    assert result["command_center"]["ceo_status"] == "JARVIS ÜBERWACHT"
    assert result["command_center"]["human_approval_count"] == 0
    assert result["command_center"]["gates_complete"] is True
    data["decisions"] = [
        {"decision_id": "real", "title": "Owner decision", "action_type": "publish"}
    ]
    assert (
        build_snapshot(data, now=NOW)["command_center"]["ceo_status"] == "WARTET AUF DEINE FREIGABE"
    )
    data["decisions"] = []
    data["active_runs"] = [run_row()]
    assert build_snapshot(data, now=NOW)["command_center"]["ceo_status"] == "JARVIS AKTIV"


def test_worker_context_joins_only_sanitized_task_evidence():
    data = ceo_data()
    data["tasks"] = [
        {
            "task_id": "work",
            "title": "Check brand reply",
            "domain": "tech",
            "status": "waiting_external",
            "dependencies": [
                "brand_or_rightsholder_reply",
                "private_marker",
                "https://secret.test",
                {},
            ],
            "expected_next_checkpoint": "deterministic_verification",
            "instruction": "private_marker",
        }
    ]
    data["active_runs"] = [run_row(status="waiting_external")]
    result = build_snapshot(data, now=NOW, secrets=("private_marker",))
    worker = result["worker_deck"][0]
    assert worker["status"] == "WAITING"
    assert worker["wait_reason"] == "external_dependency"
    assert worker["task_context"]["title"] == "Check brand reply"
    assert worker["task_context"]["dependencies"] == ["brand_or_rightsholder_reply"]
    assert worker["next_checkpoint"] == "deterministic_verification"
    assert "private_marker" not in json.dumps(result)
    assert "secret.test" not in json.dumps(result)
    assert "instruction" not in worker["task_context"]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({}, None),
        ({"status": "dispatch_pending"}, "dispatch_pending"),
        ({"status": "waiting_human"}, "owner_decision"),
        ({"status": "retryable"}, "retry_pending"),
        ({"last_progress_at": (NOW - timedelta(minutes=11)).isoformat()}, "no_recent_progress"),
        ({"lease_expires_at": STAMP}, "lease_expired"),
        ({"lease_expires_at": None}, "lease_missing"),
        ({"heartbeat_at": None}, "heartbeat_missing"),
        ({"heartbeat_at": (NOW - timedelta(minutes=4)).isoformat()}, "heartbeat_not_current"),
    ],
)
def test_worker_wait_reason_distinguishes_idle_stale_and_working(overrides, reason):
    data = ceo_data()
    data["active_runs"] = [run_row(**overrides)]
    worker = build_snapshot(data, now=NOW)["worker_deck"][0]
    assert worker["wait_reason"] == reason


def test_workstream_focus_selects_actual_blocker_and_does_not_invent_idle_worker():
    data = ceo_data()
    data["tasks"] = [
        {"task_id": "external", "domain": "tech", "status": "waiting_external", "priority": 99},
        {
            "task_id": "blocked",
            "domain": "tech",
            "status": "blocked",
            "blocked_reason": "deterministic_merchant_coverage_required",
            "priority": 1,
            "dependencies": ["brand_or_rightsholder_reply"] * 30,
        },
    ]
    result = build_snapshot(data, now=NOW)
    tech = next(w for w in result["workstreams"] if w["name"] == "Tech / Workmode")
    assert tech["focus_task"]["task_id"] == "blocked"
    assert tech["status"] == "BLOCKED"
    assert tech["active_workers"] == []
    assert tech["tasks_preview"][1]["dependencies"] == ["brand_or_rightsholder_reply"]
    assert len(result["worker_deck"]) == 0


def test_workstream_active_focus_is_actual_lease_instead_of_highest_priority_waiter():
    data = ceo_data()
    data["tasks"] = [
        {"task_id": "external", "domain": "tech", "status": "waiting_external", "priority": 99},
        {"task_id": "work", "domain": "tech", "title": "Real execution", "status": "in_progress"},
    ]
    data["active_runs"] = [run_row()]
    result = build_snapshot(data, now=NOW)
    tech = next(w for w in result["workstreams"] if w["name"] == "Tech / Workmode")
    assert tech["focus_task"]["task_id"] == "work"
    assert tech["active_workers"][0]["task_title"] == "Real execution"


def test_failed_execution_with_verified_partial_checkpoint_is_not_a_verified_completion():
    data = ceo_data()
    data["recent_runs"] = [
        run_row(
            execution_id="failed-partial",
            status="failed_terminal",
            completed_at=STAMP,
            checkpoint_verified=True,
        )
    ]
    result = build_snapshot(data, now=NOW)
    assert not any(event["id"] == "failed-partial" for event in result["live_feed"])


def test_launch_runtime_excludes_old_raw_counts_and_keeps_network_revenue_unknown():
    data = ceo_data()
    data["first_money_events"] = [
        {"event_id": "old", "session_key": "old", "event": "merchant_clickout"}
    ]
    data["first_money_runtime"] = [
        {
            "version": 2,
            "content_id": "one_million_still_hits_20261004_01",
            "experiment_id": "fms_1m_still_hits_20261004",
            "observed_at": STAMP,
            "analytics_provenance": "launch_attributed_excludes_prelaunch",
            "phase": "prelaunch",
            "decision_state": "waiting_first_signal",
            "next_evidence": "publication_evidence",
            "funnel": {
                "landing_sessions": 0,
                "product_views": 0,
                "offer_views": 0,
                "offer_opens": 0,
                "merchant_clickouts": 0,
            },
            "transactions": 999,
            "commission_eur": 999,
            "recent_signals": [
                {"event_id": "signal", "event": "offer_section_open", "occurred_at": STAMP}
            ],
        }
    ]
    result = build_snapshot(data, now=NOW)
    money = result["first_money"]
    assert money["sessions"] == money["merchant_clickouts"] == 0
    assert money["offer_opens"] == 0
    assert money["analytics_complete"]
    assert money["analytics_provenance"] == "launch_attributed_excludes_prelaunch"
    assert money["runtime"]["decision_state"] == "waiting_first_signal"
    assert money["transactions"] is None and money["commission_eur"] is None
    assert any(e["title"] == "First Money · offer_section_open" for e in result["live_feed"])
    assert not any(e["id"] == "old" for e in result["live_feed"])
    data["first_money_runtime"][0]["observed_at"] = (NOW - timedelta(minutes=6)).isoformat()
    assert (
        build_snapshot(data, now=NOW)["first_money"]["analytics_provenance"]
        == "unclassified_may_include_tests"
    )


def test_content_candidate_gate_projects_complete_review_without_publish_controls():
    data = ceo_data()
    caption = (
        "Review this candidate. " * 25
        + "https://dufynd.de/duft/parfums-de-marly-delina?src=instagram&cmp=qa_gate&content=qa_gate"
    )
    data["decisions"] = [
        {
            "decision_id": "candidate",
            "action_type": "content_candidate_review",
            "title": "Delina fixture",
            "candidate_product": "Delina EDP 75 ml",
            "candidate_product_id": "SC-PDM-DELINA-EDP-75",
            "candidate_asset_reference": "qa_delina_asset",
            "candidate_revision_fingerprint": "a" * 64,
            "candidate_hook": "Delina: passt sie zu dir?",
            "candidate_caption": caption,
            "candidate_platform": "instagram",
            "candidate_requested_at": STAMP,
            "candidate_content_id": "qa_delina",
            "candidate_experiment_id": "qa_gate",
            "candidate_internal_rating": 9.6,
            "candidate_reason": "Complete fixture",
            "decision_token": "GO-CONTENT-REVIEW-FIXTURE",
            "raw_payload": "must-not-leak",
        }
    ]
    result = build_snapshot(data, now=NOW)
    gate = result["decision_center"][0]["content_candidate"]
    assert gate["caption"] == caption
    assert gate["internal_rating"] == "9.6"
    assert gate["asset_reference"] == "qa_delina_asset"
    assert not gate["publishing_authorized"] and not gate["scheduling_authorized"]
    assert "must-not-leak" not in json.dumps(result)
    for unsafe in [
        "https://example.com/signed?token=abc",
        "https://dufynd.de/?sid=private-session",
        "Bearer secret",
        "https://dufynd.de/?content=ghp_secret",
    ]:
        data["decisions"][0]["candidate_caption"] = unsafe
        assert (
            build_snapshot(data, now=NOW)["decision_center"][0]["content_candidate"]["caption"]
            == "[restricted]"
        )


def test_current_sources_and_old_passed_smoke_have_separate_owner_semantics():
    data = ceo_data()
    data["observers"][0]["last_success_at"] = (NOW - timedelta(minutes=8)).isoformat()
    data["smoke"] = [
        {
            "status": "healthy",
            "passed": 18,
            "total": 18,
            "sha": "b" * 40,
            "observed_at": (NOW - timedelta(hours=12)).isoformat(),
        }
    ]
    result = build_snapshot(data, now=NOW)
    github = next(h for h in result["system_health"] if h["name"] == "GitHub")
    smoke = next(h for h in result["system_health"] if h["name"] == "Production Smoke")
    assert github["display_status"] == "AKTUELL"
    assert smoke["display_status"] == "NACHWEIS ÄLTER"
    assert smoke["test_passed"] and smoke["passed"] == 18
    assert smoke["confirmed_failure"] is False
    assert "kein Ausfall" in smoke["evidence_note"]
    data["smoke"][0].update(status="failed", passed=17)
    smoke = next(
        h for h in build_snapshot(data, now=NOW)["system_health"] if h["name"] == "Production Smoke"
    )
    assert smoke["display_tone"] == "red" and smoke["confirmed_failure"]


def test_live_wait_profiles_follow_business_purpose_and_require_actual_observer_binding():
    data = ceo_data()
    tid = "jarvis_dior_hypnotic_image_rights_outreach_20261001"
    data["tasks"] = [
        {
            "task_id": tid,
            "title": "Dior image rights",
            "domain": "platform",
            "status": "waiting_external",
            "updated_at": STAMP,
        },
        {
            "task_id": "jarvis_purchase_freshness_watchlist_20261001",
            "domain": "commerce",
            "status": "blocked",
            "blocked_reason": "deterministic_merchant_coverage_required",
        },
    ]
    data["external_waits"] = [{"task_id": tid, "observer_id": "gmail:thread", "satisfied": False}]
    data["observers"].append(
        {
            "observer_id": "gmail:thread",
            "source_type": "gmail",
            "enabled": True,
            "health_status": "healthy",
            "last_success_at": STAMP,
        }
    )
    result = build_snapshot(data, now=NOW)
    content = next(w for w in result["workstreams"] if w["name"] == "Content")
    affiliate = next(w for w in result["workstreams"] if w["name"] == "Affiliate")
    assert content["focus_task"]["task_id"] == tid
    explanation = content["focus_task"]["explanation"]
    assert "Dior" in explanation["reason"] and "nicht erneut senden" in explanation["reason"]
    assert explanation["automatic_monitoring_confirmed"]
    assert explanation["since"] == STAMP and "Statusbeginn" in explanation["since_basis"]
    assert "Keine Aktion" in explanation["owner_action"]
    assert "Read-only" in affiliate["focus_task"]["explanation"]["next_step"]
    assert not affiliate["focus_task"]["explanation"]["jarvis_can_resolve_alone"]
    assert result["worker_deck"] == []
    data["external_waits"] = []
    assert not build_snapshot(data, now=NOW)["mission_board"]["WAITING EXTERNAL"][0]["explanation"][
        "automatic_monitoring_confirmed"
    ]


def test_worker_aliases_stay_stable_distinct_and_keep_technical_identity():
    data = ceo_data()
    data["active_runs"] = [
        run_row(execution_id="a", worker_id="tech-worker"),
        run_row(execution_id="b", worker_id="analytics-worker"),
        run_row(execution_id="c", worker_id="tech-worker-2"),
    ]
    first = build_snapshot(data, now=NOW)["worker_deck"]
    assert [w["display_name"] for w in first] == ["Zoro", "Nami", "Zoro"]
    assert len({(w["display_name"], w["identity_tag"]) for w in first}) == 3
    data["active_runs"].reverse()
    later = build_snapshot(data, now=NOW + timedelta(seconds=30))["worker_deck"]
    assert {w["execution_id"]: (w["display_name"], w["identity_tag"]) for w in first} == {
        w["execution_id"]: (w["display_name"], w["identity_tag"]) for w in later
    }
    assert first[0]["worker_id"] == "tech-worker"
