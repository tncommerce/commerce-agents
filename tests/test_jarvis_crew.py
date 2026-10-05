"""Risk decisions and role/execution separation; no live writes or credentials."""

from datetime import timedelta

import pytest
from tests.test_jarvis_dashboard import NOW, STAMP, ceo_data, run_row

from retail.api.jarvis_dashboard import build_snapshot


def healthy_data():
    data = ceo_data()
    for name in ("gmail", "render"):
        data["observers"].append(
            {
                "observer_id": name + ":qa",
                "source_type": name,
                "enabled": True,
                "health_status": "healthy",
                "last_success_at": STAMP,
            }
        )
    data["smoke"] = [
        {"status": "healthy", "passed": 18, "total": 18, "sha": "a" * 40, "observed_at": STAMP}
    ]
    data["first_money_runtime"] = [
        {
            "version": 2,
            "observed_at": STAMP,
            "content_id": "one_million_still_hits_20261004_01",
            "experiment_id": "fms_1m_still_hits_20261004",
            "analytics_provenance": "launch_attributed_excludes_prelaunch",
            "phase": "prelaunch",
            "funnel": {
                k: 0
                for k in (
                    "landing_sessions",
                    "product_views",
                    "offer_views",
                    "offer_opens",
                    "merchant_clickouts",
                )
            },
        }
    ]
    return data


def result(data):
    return build_snapshot(data, now=NOW)


def role(snapshot, alias):
    return next(r for r in snapshot["crew"]["roles"] if r["alias"] == alias)


def test_all_green_requires_complete_verified_evidence_and_roles_are_not_executions():
    s = result(healthy_data())
    assert s["global_risk"]["tone"] == "green"
    assert not s["global_risk"]["owner_required"]
    assert len(s["crew"]["roles"]) == 10
    assert {r["cluster"] for r in s["crew"]["roles"]} == {"BUILD", "MONEY", "GROWTH", "OPERATIONS"}
    assert s["crew"]["active_executions"] == 0
    assert all(r["state"] != "AKTIV" and not r["executions"] for r in s["crew"]["roles"])
    assert role(s, "Jinbe")["state"] == "ÜBERWACHT"
    assert role(s, "Zoro")["state"] == "BEREIT"


def test_live_gmail_expiry_and_coverage_are_two_warnings_not_owner_gates():
    data = healthy_data()
    data["credentials"] = [{"provider": "gmail", "status": "healthy", "expires_at": STAMP}]
    data["tasks"] = [
        {
            "task_id": "jarvis_purchase_freshness_watchlist_20261001",
            "domain": "commerce",
            "status": "blocked",
            "blocked_reason": "deterministic_merchant_coverage_required",
            "updated_at": STAMP,
        }
    ]
    s = result(data)
    risk = s["global_risk"]
    assert risk["tone"] == "amber" and risk["critical_count"] == 0 and risk["warning_count"] == 2
    assert not risk["owner_required"]
    assert role(s, "Usopp")["state"] == "DEGRADED"
    assert next(h for h in s["system_health"] if h["name"] == "Gmail")["display_tone"] == "amber"
    assert {r["id"] for r in risk["risks"]} == {"sources", "affiliate"}
    assert role(s, "Brook")["state"] == "BLOCKIERT"
    assert "Read-only" in role(s, "Brook")["next_step"]


@pytest.mark.parametrize(
    "case", ["smoke", "ci", "unknown_cost", "stale_lease", "credential_owner", "owner_gate"]
)
def test_real_critical_conditions_are_red(case):
    data = healthy_data()
    if case == "smoke":
        data["smoke"][0].update(status="failed", passed=17)
    if case == "ci":
        data["ci"][0].update(ready=False, conclusion="failure")
    if case == "unknown_cost":
        data["thin"][0]["provider_cost_unknown"] = True
    if case == "stale_lease":
        data["active_runs"] = [run_row(lease_expires_at=STAMP)]
    if case == "credential_owner":
        data["credentials"] = [{"provider": "gmail", "status": "revoked"}]
    if case == "owner_gate":
        data["decisions"] = [
            {
                "decision_id": "qa",
                "title": "Creative prüfen",
                "action_type": "content_candidate_review",
            }
        ]
    s = result(data)
    assert s["global_risk"]["tone"] == "red"
    assert s["global_risk"]["critical_count"] >= 1
    assert s["global_risk"]["owner_required"] == (case in {"credential_owner", "owner_gate"})
    if case == "stale_lease":
        assert s["crew"]["active_executions"] == 0


@pytest.mark.parametrize(
    "case",
    [
        "old_smoke",
        "old_render",
        "old_loop",
        "missing_tracking",
        "open_reservation",
        "past_ci_failure",
    ],
)
def test_evidence_gaps_and_reservations_warn_without_inventing_failure(case):
    data = healthy_data()
    if case == "old_smoke":
        data["smoke"][0]["observed_at"] = (NOW - timedelta(hours=12)).isoformat()
    if case == "old_render":
        data["observers"][-1]["last_success_at"] = (NOW - timedelta(hours=2)).isoformat()
    if case == "old_loop":
        data["thin"][0]["observed_at"] = (NOW - timedelta(hours=1)).isoformat()
    if case == "missing_tracking":
        data.pop("first_money_runtime")
    if case == "open_reservation":
        data["open_costs"] = [{"status": "reserved"}]
    if case == "past_ci_failure":
        data["ci"][0].update(sha="b" * 40, conclusion="failure", ready=False)
    s = result(data)
    assert s["global_risk"]["tone"] == "amber"
    assert s["global_risk"]["critical_count"] == 0
    if case == "past_ci_failure":
        assert not next(h for h in s["system_health"] if h["name"].startswith("CI"))[
            "confirmed_failure"
        ]
    if case == "old_smoke":
        assert (
            next(p for p in s["global_risk"]["panels"] if p["id"] == "production")["title"]
            == "Letzter Test bestanden"
        )
        assert not next(h for h in s["system_health"] if h["name"] == "Production Smoke")[
            "confirmed_failure"
        ]


def test_dior_is_robin_by_purpose_not_old_tech_domain_and_normal_wait_is_info():
    data = healthy_data()
    data["tasks"] = [
        {
            "task_id": "jarvis_dior_hypnotic_image_rights_outreach_20261001",
            "domain": "commerce",
            "title": "Dior Bildrechte",
            "status": "waiting_external",
            "updated_at": STAMP,
        }
    ]
    s = result(data)
    robin = role(s, "Robin")
    assert robin["state"] == "WARTET EXTERN"
    assert "Dior" in robin["reason"] and "nicht erneut senden" in robin["reason"]
    assert robin["since"] == STAMP and "exakter Statusbeginn" in robin["since_basis"]
    assert not robin["active_count"] and not robin["executions"]
    assert s["global_risk"]["tone"] == "green"
    assert robin["connections"] == ["external"]


def test_handler_owns_execution_role_and_multiple_instances_remain_one_stable_node():
    data = healthy_data()
    data["active_runs"] = [
        run_row(execution_id="a", worker_id="supervisor_v2", handler_id="analytics_funnel_audit"),
        run_row(execution_id="b", worker_id="supervisor_v2", handler_id="analytics_funnel_audit"),
    ]
    a = result(data)
    data["active_runs"].reverse()
    b = result(data)
    assert role(a, "Nami")["active_count"] == role(b, "Nami")["active_count"] == 2
    assert role(a, "Nami")["state"] == "AKTIV"
    assert role(a, "Jinbe")["state"] == "ÜBERWACHT"
    assert [(r["role_id"], r["alias"]) for r in a["crew"]["roles"]] == [
        (r["role_id"], r["alias"]) for r in b["crew"]["roles"]
    ]


def test_unknown_execution_is_explicitly_unassigned_never_random_function_claim():
    data = healthy_data()
    data["active_runs"] = [run_row(worker_id="opaque-worker")]
    s = result(data)
    assert len(s["crew"]["unassigned_executions"]) == 1
    assert not any(r["state"] == "AKTIV" for r in s["crew"]["roles"])


def test_incomplete_bounded_read_cannot_be_green_or_show_active_crew():
    data = healthy_data()
    data["active_runs"] = [run_row(worker_id="tech-worker")]
    counts = {k: len(v) for k, v in data.items()}
    counts["tasks"] = 1
    s = build_snapshot(data, now=NOW, source_counts=counts)
    assert s["global_risk"]["tone"] == "amber"
    assert all(r["state"] == "DEGRADED" for r in s["crew"]["roles"])
    assert not s["crew"]["active_executions"]


def test_role_explanations_only_use_sanitized_payload():
    data = healthy_data()
    data["tasks"] = [
        {
            "task_id": "tech-test",
            "domain": "tech",
            "status": "waiting_external",
            "title": "Bearer secret",
            "payload": {"credential": "must-not-leak"},
        }
    ]
    s = result(data)
    assert role(s, "Zoro")["task"] == "[restricted]"
    assert "must-not-leak" not in str(s)
