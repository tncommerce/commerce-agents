from __future__ import annotations

from pathlib import Path

import pytest
from scripts.dufynd_durable_execution import ExecutionFenceLost, consume, run_execution
from scripts.dufynd_task_packet import FORBIDDEN, PacketTools, validate_packet


class Clock:
    value = 0

    def sleep(self, seconds):
        self.value += seconds

    def now(self):
        return self.value


class Store:
    def __init__(self, *, checkpoint=0, fence_lost=False, finish_crash=False):
        self.execution = {
            "execution_id": "eid",
            "task_id": "tid",
            "worker_id": "worker",
            "lease_token": "fence",
            "payload": {"kind": "durability_probe", "steps": 3, "interval_seconds": 12},
            "last_checkpoint": {"step": checkpoint, "sum": checkpoint * (checkpoint + 1) // 2},
            "status": "dispatched",
        }
        self.execution.update(
            {
                "scope": "supervisor-test",
                "resources": ["db:tid"],
                "handler_id": "durability_probe",
                "handler_version": "1",
                "packet_hash": "persisted-hash",
                "task_packet": {
                    "packet_version": 1,
                    "task_id": "tid",
                    "execution_id": "eid",
                    "handler_id": "durability_probe",
                    "handler_version": "1",
                    "explicit_scope": "supervisor-test",
                    "allowed_resources": ["db:tid"],
                    "payload": dict(self.execution["payload"]),
                    "required_capabilities": ["supabase.execution_state"],
                    "allowed_tools": ["checkpoint_dufynd_execution", "finish_dufynd_execution"],
                    "forbidden_actions": sorted(FORBIDDEN),
                    "verification_contract": {"kind": "arithmetic_checkpoint", "version": 1},
                },
            }
        )
        self.calls = []
        self.taken = False
        self.fence_lost = fence_lost
        self.finish_crash = finish_crash

    def _rpc(self, name, p):
        self.calls.append((name, p))
        if name == "take_dufynd_execution":
            if self.taken:
                return None
            self.taken = True
            return self.execution.copy()
        if name == "fail_dufynd_execution":
            return True
        assert (
            p["p_execution_id"] == "eid"
            and p["p_token"] == "fence"
            and p["p_worker_id"] == "worker"
        )
        if name == "checkpoint_dufynd_execution":
            if self.fence_lost:
                return None
            step = p["p_step"]
            if step is not None:
                assert step == self.execution["last_checkpoint"]["step"] + 1
                self.execution["last_checkpoint"]["step"] = step
            self.execution["status"] = (
                "verifying"
                if self.execution["last_checkpoint"]["step"] == self.execution["payload"]["steps"]
                else "running"
            )
            return self.execution.copy()
        if name == "finish_dufynd_execution":
            if self.finish_crash:
                raise RuntimeError("response persisted before crash")
            assert self.execution["last_checkpoint"]["step"] == self.execution["payload"]["steps"]
            return True
        raise AssertionError(name)


def test_resume_existing_checkpoint_and_heartbeat_without_progress():
    clock, store = Clock(), Store(checkpoint=1)
    result = run_execution(store, store.execution, sleep=clock.sleep, monotonic=clock.now)
    assert result["status"] == "completed" and result["real_provider_calls"] == 0
    progress = [
        p["p_step"]
        for name, p in store.calls
        if name == "checkpoint_dufynd_execution" and p["p_step"] is not None
    ]
    assert progress == [2, 3]
    assert clock.value == 24
    assert (
        sum(
            name == "checkpoint_dufynd_execution" and p["p_step"] is None for name, p in store.calls
        )
        >= 5
    )


def test_duplicate_dispatch_is_not_consumed_twice():
    store, clock = Store(), Clock()
    kwargs = {
        "external_run_id": "123",
        "worker_id": "worker",
        "sleep": clock.sleep,
        "monotonic": clock.now,
    }
    assert len(consume(store, **kwargs)) == 1
    assert consume(store, **kwargs) == []


def test_stale_fence_prevents_progress_and_finalization():
    store = Store(fence_lost=True)
    with pytest.raises(ExecutionFenceLost):
        run_execution(store, store.execution)
    assert len(store.calls) == 1


def test_response_before_finalization_crash_keeps_durable_result():
    store, clock = Store(finish_crash=True), Clock()
    with pytest.raises(RuntimeError):
        consume(
            store, external_run_id="123", worker_id="worker", sleep=clock.sleep, monotonic=clock.now
        )
    assert (
        store.execution["status"] == "verifying" and store.execution["last_checkpoint"]["step"] == 3
    )
    assert store.calls[-1][0] == "fail_dufynd_execution"
    assert store.calls[-1][1]["p_error"] == "RuntimeError"


@pytest.mark.parametrize(
    "field,value", [("kind", "shell"), ("steps", 100), ("interval_seconds", 0), ("steps", True)]
)
def test_no_arbitrary_or_paid_handler(field, value):
    store = Store()
    store.execution["payload"][field] = value
    with pytest.raises(ValueError, match="uncertified"):
        run_execution(store, store.execution)
    assert store.calls == []


def test_existing_workflow_has_isolated_free_durable_job():
    text = (
        Path(__file__).resolve().parents[1] / ".github/workflows/dufynd-jarvis-manual.yml"
    ).read_text()
    durable = text.split("  durable-execution:\n")[1]
    assert "scripts.dufynd_durable_execution consume" in durable
    assert "ANTHROPIC" not in durable and "approval_token" not in durable
    assert "contents: read" in durable and "scentai-mvp" in durable
    assert "branches: [scentai-mvp]" in text


@pytest.mark.parametrize(
    "ready_at,waiters,expected", [(45, True, 1), (999, True, 0), (45, False, 0)]
)
def test_event_wake_wait_window_is_bounded_and_has_no_chat_dependency(ready_at, waiters, expected):
    clock, store = Clock(), Store()
    original = store._rpc

    def rpc(name, params):
        if name == "has_dufynd_durable_event_waiters":
            return waiters
        if name == "take_dufynd_execution" and clock.value < ready_at:
            return None
        return original(name, params)

    store._rpc = rpc
    result = consume(
        store,
        external_run_id="123",
        worker_id="worker",
        wait_seconds=120,
        sleep=clock.sleep,
        monotonic=clock.now,
    )
    assert len(result) == expected
    assert clock.value <= 156
    assert waiters or clock.value == 0


@pytest.mark.parametrize(
    "name", ["gmail.send", "social.publish", "arbitrary_shell", "take_dufynd_execution"]
)
def test_packet_worker_cannot_access_ungranted_tools(name):
    store = Store()
    with pytest.raises(ValueError, match="tool_not_in_packet"):
        PacketTools(store, store.execution).call(name)
    assert store.calls == []


def test_packet_cannot_override_execution_resource_or_fence():
    store = Store()
    with pytest.raises(ValueError, match="outside_scope"):
        PacketTools(store, store.execution).call("checkpoint_dufynd_execution", p_token="other")
    store.execution["task_packet"]["allowed_resources"] = ["db:foreign"]
    with pytest.raises(ValueError, match="uncertified"):
        validate_packet(store.execution)
    assert store.calls == []


def test_uncertified_legacy_packet_has_no_worker_dispatch():
    store = Store()
    del store.execution["task_packet"]
    with pytest.raises(ValueError, match="uncertified"):
        run_execution(store, store.execution)
    assert store.calls == []


def test_certified_state_audit_worker_runs_from_packet_and_persistent_state_only():
    store, clock = Store(), Clock()
    payload = {"kind": "supervisor_state_audit", "steps": 1, "interval_seconds": 2}
    store.execution.update(
        {
            "handler_id": "supervisor_state_audit",
            "scope": "supervisor",
            "resources": ["db:jarvis.supervisor_v2.health"],
            "payload": payload,
        }
    )
    store.execution["task_packet"].update(
        {
            "handler_id": "supervisor_state_audit",
            "explicit_scope": "supervisor",
            "allowed_resources": ["db:jarvis.supervisor_v2.health"],
            "required_capabilities": ["supabase.execution_state", "supabase.task_state"],
            "payload": dict(payload),
            "verification_contract": {"kind": "supervisor_state_audit", "version": 1},
        }
    )
    assert (
        run_execution(store, store.execution, sleep=clock.sleep, monotonic=clock.now)["status"]
        == "completed"
    )
    assert clock.value == 2
    assert all(
        name in {"checkpoint_dufynd_execution", "finish_dufynd_execution"}
        for name, _ in store.calls
    )


def test_ci_pr_packet_uses_only_fenced_read_audit_tools():
    store, clock = Store(), Clock()
    payload = {
        "kind": "ci_pr_verifier",
        "steps": 1,
        "interval_seconds": 2,
        "pr_number": "623",
        "ci_run_id": "37014817569",
        "expected_merge_sha": "a" * 40,
        "expected_pr_head_sha": "b" * 40,
    }
    store.execution.update(
        handler_id="ci_pr_verifier",
        scope="supervisor",
        resources=["db:ci-pr-verification"],
        payload=payload,
    )
    store.execution["task_packet"].update(
        handler_id="ci_pr_verifier",
        explicit_scope="supervisor",
        allowed_resources=["db:ci-pr-verification"],
        required_capabilities=[
            "github.ci.observe",
            "github.read",
            "supabase.execution_state",
            "supabase.task_state",
        ],
        payload=dict(payload),
        verification_contract={"kind": "ci_pr_verifier", "version": 1},
    )
    assert (
        run_execution(store, store.execution, sleep=clock.sleep, monotonic=clock.now)["status"]
        == "completed"
    )
    assert {name for name, _ in store.calls} == {
        "checkpoint_dufynd_execution",
        "finish_dufynd_execution",
    }
    store.execution["task_packet"]["allowed_resources"] = ["db:other"]
    with pytest.raises(ValueError):
        validate_packet(store.execution)
