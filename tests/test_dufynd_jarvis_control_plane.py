from datetime import UTC, datetime, timedelta

import pytest
from scripts.dufynd_jarvis_control_plane import (
    human_gate_allowed,
    lease_state,
    recovery_state,
    resources_conflict,
    worker_health,
    worst_case_call_allowed,
)
from scripts.dufynd_jarvis_runtime import require_bounded_provider_execution

NOW = datetime(2026, 10, 2, 7, tzinfo=UTC)


def worker(**changes):
    return {
        "worker_state": "working",
        "heartbeat_at": NOW.isoformat(),
        "last_progress_at": NOW.isoformat(),
        "lease_expires_at": (NOW + timedelta(minutes=3)).isoformat(),
        **changes,
    }


def test_normal_worker_is_healthy():
    assert worker_health(worker(), NOW) == "healthy"


def test_expired_heartbeat_is_stale():
    assert (
        worker_health(worker(heartbeat_at=(NOW - timedelta(minutes=4)).isoformat()), NOW)
        == "heartbeat_stale"
    )


def test_fresh_heartbeat_does_not_hide_progress_stall():
    assert (
        worker_health(worker(last_progress_at=(NOW - timedelta(minutes=11)).isoformat()), NOW)
        == "progress_stalled"
    )


@pytest.mark.parametrize("expires", [(NOW - timedelta(seconds=1)).isoformat(), "bad", None])
def test_expired_or_malformed_lease_is_reclaimable(expires):
    assert lease_state({"status": "active", "expires_at": expires}, NOW)["reclaimable"]


def test_released_active_lease_is_inactive_even_before_ttl():
    result = lease_state(
        {
            "status": "active",
            "released_at": NOW.isoformat(),
            "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        },
        NOW,
    )
    assert result["inconsistent"] and not result["active"]


@pytest.mark.parametrize(
    "left,right",
    [
        (["repo:scripts"], ["repo:scripts/job.py"]),
        (["db:tasks"], ["db:tasks"]),
        (["external:render"], ["external:render"]),
        (["exclusive:queue"], ["exclusive:queue"]),
        (["repo:*"], ["repo:tests"]),
        ([], ["repo:tests"]),
    ],
)
def test_colliding_scopes_prevent_parallel_claim(left, right):
    assert resources_conflict(left, right)


def test_disjoint_scopes_allow_parallelism():
    assert not resources_conflict(
        ["repo:scripts/a.py", "db:tasks_a"], ["repo:scripts/b.py", "db:tasks_b"]
    )
    assert not resources_conflict(["repo:tests/a"], ["repo:tests/ab"])


def test_retryable_error_requeues_but_unknown_paid_outcome_is_quarantined():
    assert recovery_state("tool_timeout") == "failed_retryable"
    assert recovery_state("tool_timeout", cost_unknown=True) == "blocked"
    assert recovery_state("tool_timeout", retry_count=2) == "failed_terminal"


def test_owner_decision_is_a_human_gate():
    assert recovery_state("owner_decision") == "waiting_human_input"
    assert human_gate_allowed({}, "DUFYND_BLOCK_REASON: owner_decision")


@pytest.mark.parametrize(
    "reason",
    [
        "budget_exhausted",
        "unbounded_provider_cost",
        "session_ended",
        "tool_timeout",
        "technical_research",
    ],
)
def test_technical_stops_are_not_human_gates(reason):
    assert recovery_state(reason) != "waiting_human_input"
    assert not human_gate_allowed({}, "DUFYND_TASK_STATE: waiting_human_input")


@pytest.mark.parametrize(
    "remaining,worst_case,bounded",
    [
        ("0.10", "0.11", True),
        ("2.5", None, True),
        ("NaN", "0.1", True),
        ("Infinity", "0.1", True),
        ("2.5", "0.1", False),
        ("2.5", "-1", True),
    ],
)
def test_missing_or_insufficient_worst_case_bound_refuses_model(remaining, worst_case, bounded):
    assert not worst_case_call_allowed(remaining, worst_case, bounded=bounded)


def test_exact_budget_boundary():
    assert worst_case_call_allowed("0.11", "0.11", bounded=True)
    assert not worst_case_call_allowed("0.109999", "0.11", bounded=True)


def test_sdk_is_fail_closed_before_any_paid_execution(monkeypatch):
    monkeypatch.setenv("DUFYND_JARVIS_MAX_BUDGET_USD", "1000")
    with pytest.raises(RuntimeError, match="unbounded_provider_cost"):
        require_bounded_provider_execution()
