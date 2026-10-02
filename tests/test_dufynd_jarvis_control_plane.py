import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from scripts import dufynd_jarvis_runtime as runtime
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
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


def test_bridge_uses_claim_token_and_does_not_invent_human_reason():
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if request.url.path.endswith("claim_dufynd_worker_v2"):
            return httpx.Response(200, json={"task_id": "task", "lease_token": body["p_token"]})
        return httpx.Response(200, json=True)

    bridge = DufyndJarvisBridge(
        supabase_url="https://example.test",
        secret_key="test",
        transport=httpx.MockTransport(handler),
    )
    bridge.claim_worker("task", "worker")
    bridge.update_worker("task", "heartbeat")
    bridge.set_autonomy_task_status(
        task_id="task", status="waiting_human_input", evidence="budget ran out"
    )
    assert requests[0]["p_token"] == requests[1]["p_token"] == requests[2]["p_token"]
    assert requests[2]["p_reason"] is None


def test_bridge_rejects_stale_rpc_write():
    bridge = DufyndJarvisBridge(
        supabase_url="https://example.test",
        secret_key="test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=False)),
    )
    bridge.worker_tokens["task"] = "expired-token"
    with pytest.raises(RuntimeError, match="lease lost"):
        bridge.update_worker("task", "working", evidence="late result")


class WorkerBridge:
    def __init__(self):
        self.task = {"task_id": "task", "domain": "research", "status": "ready", "evidence": ""}
        self.worker_tokens = {}
        self.states = []

    def load_autonomy_queue(self):
        return {"safe_to_execute": [dict(self.task)] if self.task["status"] == "ready" else []}

    def claim_worker(self, task_id, owner):
        self.worker_tokens[task_id] = "test-token"
        self.task["status"] = "in_progress"
        return dict(self.task)

    def load_autonomy_task(self, task_id):
        return dict(self.task)

    def update_autonomy_task_progress(self, *, task_id, status, evidence):
        self.task.update(status=status, evidence=evidence)

    def update_worker(self, task_id, state, *, evidence=None, reason=None):
        self.states.append(state)
        self.task.update(evidence=evidence or self.task["evidence"])

    def record_run(self, **kwargs):
        pass


def test_claimed_task_remains_visible_to_its_fenced_worker(monkeypatch):
    bridge = WorkerBridge()
    queries = []

    class FakeClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, prompt):
            queries.append(prompt)

    async def collect(client):
        return SimpleNamespace(
            text="partial evidence\nDUFYND_TASK_STATE: in_progress", cost_usd=0, is_error=False
        )

    # This harness never invokes a real provider. The production gate is tested
    # separately and has no env-based override.
    monkeypatch.setattr(runtime, "require_bounded_provider_execution", lambda: None)
    monkeypatch.setattr(runtime, "_require_budget_window", lambda b: ("test-budget", {}))
    monkeypatch.setattr(runtime, "make_safe_worker_options", lambda b: object())
    monkeypatch.setattr(runtime, "ClaudeSDKClient", FakeClient)
    monkeypatch.setattr(runtime, "collect_turn", collect)
    assert asyncio.run(runtime.process_safe_task(bridge, task_id="task")) == 0
    assert len(queries) == 1
    assert bridge.states[-1] == "queued"
    assert bridge.worker_tokens == {}


def test_worker_exception_still_releases_lease_and_records_retry(monkeypatch):
    bridge = WorkerBridge()
    monkeypatch.setattr(runtime, "require_bounded_provider_execution", lambda: None)

    async def process_safe_task(bridge, *, task_id):
        raise ValueError("deterministic harness failure")

    with pytest.raises(ValueError, match="harness failure"):
        asyncio.run(runtime.leased_worker(process_safe_task)(bridge, task_id="task"))
    assert bridge.states[-1] == "failed_retryable"
    assert bridge.worker_tokens == {}
