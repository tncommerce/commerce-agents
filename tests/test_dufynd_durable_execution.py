from __future__ import annotations

from pathlib import Path

import pytest
from scripts.dufynd_durable_execution import ExecutionFenceLost, consume, run_execution


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
                "verifying" if self.execution["last_checkpoint"]["step"] == 3 else "running"
            )
            return self.execution.copy()
        if name == "finish_dufynd_execution":
            if self.finish_crash:
                raise RuntimeError("response persisted before crash")
            assert self.execution["last_checkpoint"]["step"] == 3
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
