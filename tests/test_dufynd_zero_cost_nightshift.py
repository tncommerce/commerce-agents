from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from scripts.dufynd_zero_cost_nightshift import (
    RUNNER_SHA,
    Gate,
    Queue,
    checkout_identity,
    execute_offline,
    read_input,
    run,
    validate_plan,
)

SHA = "a" * 40
NOW = datetime(2026, 10, 12, 20, tzinfo=UTC)


class Clock:
    def __init__(self):
        self.now = NOW.timestamp()
        self.elapsed = 0

    def sleep(self, seconds):
        self.now += seconds
        self.elapsed += seconds


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "docs").mkdir()
    raw = b'{"valid":true}'
    (tmp_path / "docs/input.json").write_bytes(raw)
    task = {
        "task_id": "inspect",
        "action": "json_integrity",
        "due_at": NOW.isoformat(),
        "max_attempts": 2,
        "depends_on": [],
        "inputs": [{"path": "docs/input.json", "sha256": hashlib.sha256(raw).hexdigest()}],
    }
    plan = {
        "schema_version": 1,
        "repository": "tncommerce/commerce-agents",
        "plan_id": "night1",
        "checkout_sha": SHA,
        "runner_sha256": RUNNER_SHA,
        "enabled": True,
        "production_activation": False,
        "max_external_cost_eur": 0,
        "starts_at": NOW.isoformat(),
        "ends_at": (NOW + timedelta(hours=1)).isoformat(),
        "max_attempts": 4,
        "max_tasks_per_tick": 3,
        "tasks": [task],
    }
    q = Queue(tmp_path / "state/queue.sqlite")
    yield tmp_path, plan, q
    q.db.close()


def drive(setup, **kwargs):
    root, plan, q = setup
    c = kwargs.pop("timer", Clock())
    return run(
        plan,
        q,
        root,
        clock=lambda: c.now,
        monotonic=lambda: c.elapsed,
        sleep=c.sleep,
        identity=lambda _: SHA,
        **kwargs,
    )


def test_waits_until_due_and_deduplicates_across_plan_and_checkout(setup):
    root, plan, q = setup
    plan["tasks"][0]["due_at"] = (NOW + timedelta(seconds=3)).isoformat()
    c = Clock()
    calls = []

    def handler(action, inputs):
        calls.append(c.now)
        return execute_offline(action, inputs)

    first = drive(setup, timer=c, handler=handler)
    assert first["stop_reason"] == "QUEUE_TERMINAL"
    assert calls == [NOW.timestamp() + 3]
    plan["plan_id"] = "night2"
    result = drive(setup, timer=c, handler=handler)
    assert len(calls) == 1
    assert result["attempts"] == 0
    assert result["tasks"][0]["reason"] == "deduplicated"
    assert (root / "state/queue.sqlite").stat().st_mode & 0o777 == 0o600


def test_owner_hold_and_dependent_do_not_stop_independent_work(setup):
    _, plan, _ = setup
    owner = {
        **plan["tasks"][0],
        "task_id": "a_owner",
        "action": "owner_gate",
        "hold_reason": "external_login",
        "inputs": [],
    }
    waiting = {**plan["tasks"][0], "task_id": "b_waiting", "depends_on": ["a_owner"]}
    plan["tasks"] = [owner, waiting, plan["tasks"][0]]
    result = drive(setup)
    assert [t["status"] for t in result["tasks"]] == ["hold", "hold", "done"]
    assert result["attempts"] == 1


def test_crash_resume_fences_old_worker_and_commits_result_atomically(setup):
    _, plan, q = setup
    q.register(plan)
    old, _ = q.claim(plan, NOW.timestamp())
    assert q.claim(plan, NOW.timestamp() + 1)[0] is None
    newer, _ = q.claim(plan, NOW.timestamp() + 31)
    assert newer[2] != old[2]
    with pytest.raises(Gate, match="lease_lost"):
        q.finish(plan, old, NOW.timestamp() + 32, result={"old": True})
    assert q.db.execute("SELECT count(*) FROM completed").fetchone()[0] == 0
    q.finish(plan, newer, NOW.timestamp() + 32, result={"valid": True})
    assert q.snapshot(plan)["attempts"] == 2
    assert q.db.execute("SELECT result FROM completed").fetchone()[0] == '{"valid":true}'
    with pytest.raises(Gate, match="lease_lost"):
        q.finish(plan, newer, NOW.timestamp() + 33, result={"duplicate": True})


def test_concurrent_process_connections_cannot_claim_equivalent_work(setup):
    root, plan, q = setup
    second = {**plan, "plan_id": "night2"}
    q.register(plan)
    q.register(second)

    def claim(p):
        connection = Queue(root / "state/queue.sqlite")
        try:
            return connection.claim(p, NOW.timestamp())[0]
        finally:
            connection.db.close()

    with ThreadPoolExecutor(2) as pool:
        claims = list(pool.map(claim, [plan, second]))
    assert sum(c is not None for c in claims) == 1


def test_attempt_budget_survives_restart(setup):
    _, plan, q = setup
    plan["max_attempts"] = 1
    q.register(plan)
    q.claim(plan, NOW.timestamp())
    assert q.claim(plan, NOW.timestamp() + 40) == (None, "ATTEMPT_LIMIT")
    assert q.snapshot(plan)["attempts"] == 1


def test_plan_mutation_requires_new_identity(setup):
    _, plan, q = setup
    q.register(plan)
    plan["max_attempts"] += 1
    with pytest.raises(Gate, match="plan_changed_new_id_required"):
        q.register(plan)


def test_changed_input_is_hold_even_after_previous_completed_result(setup):
    root, plan, _ = setup
    drive(setup)
    plan["plan_id"] = "night2"
    (root / "docs/input.json").write_text('{"changed":true}')
    result = drive(setup)
    assert result["tasks"][0]["status"] == "hold"
    assert result["tasks"][0]["reason"] == "input_changed"
    assert result["attempts"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("repository", "another/project"),
        ("max_external_cost_eur", 0.01),
        ("max_external_cost_eur", False),
        ("production_activation", True),
        ("starts_at", "2026-10-12T20:00:00"),
        ("max_attempts", 41),
        ("max_tasks_per_tick", 0),
        ("ends_at", "2026-10-13T20:00:00Z"),
    ],
)
def test_unsafe_plan_rejected_before_queue(setup, field, value):
    _, plan, _ = setup
    plan[field] = value
    with pytest.raises(Gate):
        validate_plan(plan)


@pytest.mark.parametrize("action", ["shell", "publish", "anthropic", "http", "sql"])
def test_no_general_execution_adapter(setup, action):
    _, plan, _ = setup
    plan["tasks"][0]["action"] = action
    with pytest.raises(Gate, match="action_denied"):
        validate_plan(plan)


@pytest.mark.parametrize("dependency", ["inspect", "unknown"])
def test_dependency_cycles_and_unknown_ids_fail_closed(setup, dependency):
    _, plan, _ = setup
    plan["tasks"][0]["depends_on"] = [dependency]
    with pytest.raises(Gate, match="unknown_or_cyclic_dependency"):
        validate_plan(plan)


@pytest.mark.parametrize(
    "path", ["../outside.json", "/tmp/private.json", "docs/../private.json", ".git/config.json"]
)
def test_input_paths_fail_closed(setup, path):
    root, plan, _ = setup
    with pytest.raises(Gate, match="input_path_denied"):
        read_input(root, {**plan["tasks"][0]["inputs"][0], "path": path})


def test_symlink_input_denied(setup):
    root, plan, _ = setup
    (root / "docs/input.json").unlink()
    (root / "docs/input.json").symlink_to(root / "other.json")
    with pytest.raises(Gate, match="input_symlink_denied"):
        read_input(root, plan["tasks"][0]["inputs"][0])


def test_disabled_closed_window_stopfile_and_runtime(setup):
    root, plan, _ = setup
    plan["enabled"] = False
    assert drive(setup)["stop_reason"] == "DISABLED"
    plan["enabled"] = True
    c = Clock()
    c.now += 3600
    assert drive(setup, timer=c)["stop_reason"] == "WINDOW_CLOSED"
    stop = root / "STOP"
    stop.touch()
    assert drive(setup, stop_file=stop)["stop_reason"] == "STOP_FILE"
    stop.unlink()
    plan["plan_id"] = "later"
    plan["tasks"][0]["due_at"] = (NOW + timedelta(seconds=20)).isoformat()
    result = drive(setup, max_seconds=2)
    assert result["stop_reason"] == "RUNTIME_LIMIT"
    assert result["attempts"] == 0


def test_checkout_change_stops_before_handler(setup):
    root, plan, q = setup
    identities = iter([SHA, "b" * 40])
    result = run(plan, q, root, identity=lambda _: next(identities))
    assert result["stop_reason"] == "CHECKOUT_CHANGED"
    assert result["attempts"] == 0


def test_real_git_protected_branch_and_wrong_repo(tmp_path):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-b", "main")
    git("remote", "add", "origin", "https://github.com/tncommerce/commerce-agents.git")
    with pytest.raises(Gate, match="development_branch_required"):
        checkout_identity(tmp_path)
    git("remote", "set-url", "origin", "https://github.com/another/project.git")
    with pytest.raises(Gate, match="repository_out_of_scope"):
        checkout_identity(tmp_path)


def test_actual_process_death_leaves_recoverable_claim(setup):
    root, plan, q = setup
    q.register(plan)
    plan_file = root / "plan.json"
    plan_file.write_text(json.dumps(plan))
    program = """
import json,os,sys
from scripts.dufynd_zero_cost_nightshift import Queue
q=Queue(sys.argv[1]); p=json.load(open(sys.argv[2]))
assert q.claim(p,float(sys.argv[3]))[0]
os._exit(17)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            str(root / "state/queue.sqlite"),
            str(plan_file),
            str(NOW.timestamp()),
        ],
        check=False,
    )
    assert result.returncode == 17
    assert q.snapshot(plan)["tasks"][0]["status"] == "running"
    c = Clock()
    c.now += 31
    result = drive(setup, timer=c)
    assert result["tasks"][0]["status"] == "done"
    assert result["attempts"] == 2


def test_source_intake_is_structural_not_authorization():
    row = {
        "candidate_id": "candidate",
        "brand": "Example",
        "name": "Example",
        "concentration": "EDP",
        "volume_ml": 100,
        "manufacturer_reference": "reference",
        "variant_evidence": "source evidence",
        "source_url": "https://example.invalid/product",
        "notes": {"top": ["rose"]},
    }
    packet = {
        "facts_only": True,
        "community_data_included": False,
        "publication_authorized": False,
        "products": [row],
    }
    result = execute_offline("source_intake", [packet])
    assert result == {
        "structurally_valid_candidates": 1,
        "source_truth_verified_by_runner": False,
        "publication_authorized": False,
    }
    packet["products"].append(copy.deepcopy(row))
    with pytest.raises(Gate, match="duplicate_source_candidate"):
        execute_offline("source_intake", [packet])


def test_real_wall_clock_due_time(setup):
    root, plan, q = setup
    start = datetime.now(UTC)
    plan["starts_at"] = start.isoformat()
    plan["ends_at"] = (start + timedelta(seconds=10)).isoformat()
    due = (start + timedelta(seconds=0.15)).timestamp()
    plan["tasks"][0]["due_at"] = datetime.fromtimestamp(due, UTC).isoformat()
    calls = []

    def handler(action, inputs):
        calls.append(time.time())
        return execute_offline(action, inputs)

    result = run(plan, q, root, identity=lambda _: SHA, handler=handler, max_seconds=3)
    assert result["tasks"][0]["status"] == "done"
    assert calls[0] >= due


def test_no_network_used_by_offline_handlers(setup, monkeypatch):
    import socket

    def denied(*args, **kwargs):
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "socket", denied)
    assert drive(setup)["tasks"][0]["status"] == "done"


def test_shared_dependency_graph_is_bounded(setup):
    _, plan, _ = setup
    template = plan["tasks"][0]
    plan["tasks"] = [
        {**template, "task_id": f"task{i}", "depends_on": [f"task{j}" for j in range(i)]}
        for i in range(80)
    ]
    validate_plan(plan)


def test_changed_runner_is_not_reused(setup):
    root, plan, q = setup
    plan["runner_sha256"] = "b" * 64
    with pytest.raises(Gate, match="runner_changed"):
        run(plan, q, root, identity=lambda _: SHA)


def test_tick_limit_then_resume_preserves_remaining_queue(setup):
    root, plan, _ = setup
    (root / "docs/second.json").write_text("{}")
    plan["tasks"].append(
        {
            **plan["tasks"][0],
            "task_id": "second",
            "inputs": [{"path": "docs/second.json", "sha256": hashlib.sha256(b"{}").hexdigest()}],
        }
    )
    plan["max_tasks_per_tick"] = 1
    first = drive(setup)
    assert first["stop_reason"] == "TICK_LIMIT"
    assert first["attempts"] == 1
    second = drive(setup)
    assert second["attempts"] == 2
    assert all(t["status"] == "done" for t in second["tasks"])


def test_wall_clock_rollback_does_not_extend_process_runtime(setup):
    _, plan, _ = setup
    c = Clock()
    c.now -= 100
    result = drive(setup, timer=c, max_seconds=2)
    assert result["stop_reason"] == "RUNTIME_LIMIT"
    assert c.elapsed == 2
    assert result["attempts"] == 0


def test_stop_checkpoint_survives_reopened_state(setup):
    root, plan, _ = setup
    report = drive(setup)
    reopened = Queue(root / "state/queue.sqlite")
    try:
        saved = json.loads(
            reopened.db.execute(
                "SELECT report FROM checkpoints WHERE plan=?", (plan["plan_id"],)
            ).fetchone()[0]
        )
        assert saved == report
        assert saved["stop_reason"] == "QUEUE_TERMINAL"
    finally:
        reopened.db.close()
