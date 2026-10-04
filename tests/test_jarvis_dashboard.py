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
    assert len(calls) == 22
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
