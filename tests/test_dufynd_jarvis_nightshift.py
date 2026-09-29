from __future__ import annotations

import asyncio
from pathlib import Path

import scripts.dufynd_jarvis_nightshift as nightshift


class FakeBridge:
    def __init__(self, tasks: list[dict] | None = None) -> None:
        self.tasks = {task["task_id"]: dict(task) for task in (tasks or [])}
        self.master = {
            "jarvis.repo_state_snapshot": {
                "key": "jarvis.repo_state_snapshot",
                "value": {"source_fingerprint_sha256": "fingerprint-1"},
            }
        }
        self.runs = []
        self.status_writes = []
        self.inbox_pending = 0

    def load_master_status_entry(self, key: str):
        return self.master.get(key)

    def upsert_master_status(self, *, key, category, value, priority, last_verified_at):
        self.master[key] = {
            "key": key,
            "category": category,
            "value": dict(value),
            "priority": priority,
            "last_verified_at": last_verified_at,
        }

    def load_autonomy_queue(self):
        ready = [dict(task) for task in self.tasks.values() if task.get("status") == "ready"]
        ready.sort(key=lambda task: (-int(task.get("priority") or 0), task["task_id"]))
        return {
            "safe_to_execute": ready,
            "in_progress": [
                dict(task) for task in self.tasks.values() if task.get("status") == "in_progress"
            ],
            "waiting_human_input": [
                dict(task)
                for task in self.tasks.values()
                if task.get("status") == "waiting_human_input"
            ],
            "waiting_external": [
                dict(task)
                for task in self.tasks.values()
                if task.get("status") == "waiting_external"
            ],
            "approval_required": [
                dict(task)
                for task in self.tasks.values()
                if task.get("status") == "approval_required"
            ],
            "done_recent": [
                dict(task) for task in self.tasks.values() if task.get("status") == "done"
            ],
        }

    def load_autonomy_task(self, task_id: str):
        task = self.tasks.get(task_id)
        return dict(task) if task else None

    def set_autonomy_task_status(self, *, task_id, status, evidence):
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["evidence"] = evidence
        self.status_writes.append((task_id, status))

    def record_run(self, **kwargs):
        self.runs.append(kwargs)

    def load_agent_runs_since(self, since_iso: str):
        return [
            {
                "agent_name": "jarvis_safe_worker",
                "run_type": "safe_task:repo_current_commerce",
                "decisions": [{"cost_usd": 0.08}],
                "created_at": since_iso,
            },
            {
                "agent_name": "jarvis_branch_worker",
                "run_type": "branch_task:repo_current_engineering",
                "decisions": [{"cost_usd": 0.11}],
                "created_at": since_iso,
            },
        ]

    def load_health(self):
        return {
            "state": "idle",
            "inbox": {"pending": self.inbox_pending, "processing": 0, "failed": 0},
            "pending_human_decisions": 0,
        }

    def load_pending_decisions(self):
        return []

    def load_budget_status(self, _budget_id: str):
        return {
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "can_run": True,
            "spent_usd": 0.4,
            "remaining_usd": 2.1,
        }


def task(task_id: str, domain: str, priority: int) -> dict:
    return {
        "task_id": task_id,
        "domain": domain,
        "title": task_id.replace("_", " "),
        "status": "ready",
        "priority": priority,
        "requires_human_approval": False,
        "evidence": "source_fingerprint_sha256=fingerprint-1",
    }


def test_safe_worker_outcome_defaults_to_in_progress() -> None:
    assert nightshift._safe_worker_outcome("evidence without marker") == "in_progress"


def test_safe_worker_outcome_uses_last_valid_marker() -> None:
    evidence = (
        "research notes\n"
        "DUFYND_TASK_STATE: in_progress\n"
        "more evidence\n"
        "DUFYND_TASK_STATE: waiting_external"
    )

    assert nightshift._safe_worker_outcome(evidence) == "waiting_external"


def test_non_green_task_is_not_selected() -> None:
    candidate = task("repo_current_commerce", "commerce", 100)
    candidate["approval_action_type"] = "manual_state_reconciliation_required"
    queue = {"safe_to_execute": [candidate]}

    selected = nightshift._select_task(queue, branch_worker_used=False)

    assert selected is None


def test_select_task_prefers_non_engineering_before_branch_patch() -> None:
    queue = {
        "safe_to_execute": [
            task("repo_current_engineering", "engineering", 100),
            task("repo_current_commerce", "commerce", 90),
        ]
    }

    selected = nightshift._select_task(
        queue,
        branch_worker_used=False,
        attempted_task_ids=set(),
    )

    assert selected is not None
    assert selected["task_id"] == "repo_current_commerce"


def test_select_task_skips_second_engineering_patch() -> None:
    queue = {
        "safe_to_execute": [
            task("repo_current_engineering", "engineering", 100),
            task("repo_current_commerce", "commerce", 90),
        ]
    }

    selected = nightshift._select_task(queue, branch_worker_used=True)

    assert selected is not None
    assert selected["task_id"] == "repo_current_commerce"


def test_same_fingerprint_session_is_resumed() -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "nightshift-existing",
            "status": "running",
            "source_fingerprint_sha256": "fingerprint-1",
            "resume_count": 2,
            "task_results": [],
        },
    }

    session = nightshift._load_or_start_session(
        bridge,
        fingerprint="fingerprint-1",
        max_tasks=8,
        max_events=2,
    )

    assert session["session_id"] == "nightshift-existing"
    assert session["resume_count"] == 3
    assert session["status"] == "running"


def test_recovery_marks_audited_safe_worker_done() -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    bridge.tasks["repo_current_commerce"]["status"] = "in_progress"
    session = {
        "session_id": "nightshift-recover-safe",
        "started_at": "2026-09-29T20:00:00+00:00",
        "current_task": {
            "task_id": "repo_current_commerce",
            "domain": "commerce",
            "worker": "safe_worker",
            "attempt": 1,
            "started_at": "2026-09-29T20:00:00+00:00",
        },
        "task_results": [],
    }

    nightshift._recover_interrupted_work(bridge, session)

    assert bridge.tasks["repo_current_commerce"]["status"] == "done"
    assert session["current_task"] is None
    assert session["task_results"][0]["recovered_after_interruption"] is True


def test_recovery_requeues_interrupted_branch_patch() -> None:
    bridge = FakeBridge([task("repo_current_engineering", "engineering", 100)])
    bridge.tasks["repo_current_engineering"]["status"] = "in_progress"
    session = {
        "session_id": "nightshift-recover-branch",
        "started_at": "2026-09-29T20:00:00+00:00",
        "current_task": None,
        "branch_worker_used": True,
        "task_results": [
            {
                "task_id": "repo_current_engineering",
                "domain": "engineering",
                "worker": "branch_worker",
                "final_status": "in_progress",
                "finished_at": "2026-09-29T20:10:00+00:00",
            }
        ],
    }

    nightshift._recover_interrupted_work(bridge, session)

    assert bridge.tasks["repo_current_engineering"]["status"] == "ready"
    assert session["branch_worker_used"] is False
    assert session["current_task"] is None


def test_changed_fingerprint_starts_new_session() -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "nightshift-old",
            "status": "running",
            "source_fingerprint_sha256": "old-fingerprint",
        },
    }

    session = nightshift._load_or_start_session(
        bridge,
        fingerprint="fingerprint-1",
        max_tasks=8,
        max_events=2,
    )

    assert session["session_id"] != "nightshift-old"
    assert session["source_fingerprint_sha256"] == "fingerprint-1"


def test_nightshift_routes_workers_and_consumes_multiple_tasks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    bridge = FakeBridge(
        [
            task("repo_current_engineering", "engineering", 100),
            task("repo_current_commerce", "commerce", 90),
        ]
    )

    monkeypatch.setenv(
        "DUFYND_JARVIS_TASK_METADATA_PATH",
        str(tmp_path / "worker-task.json"),
    )
    monkeypatch.setattr(
        nightshift,
        "_require_autonomous_mode",
        lambda: None,
    )
    monkeypatch.setattr(
        nightshift,
        "_require_budget_window",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    async def fake_loop(_bridge, *, max_events):
        assert max_events == 2
        return 0

    async def fake_branch(_bridge, *, task_id=None):
        bridge.tasks["repo_current_engineering"]["status"] = "in_progress"
        bridge.tasks["repo_current_engineering"]["evidence"] = "branch prepared"
        return 0

    async def fake_safe(_bridge, *, task_id=None):
        bridge.tasks["repo_current_commerce"]["status"] = "in_progress"
        bridge.tasks["repo_current_commerce"]["evidence"] = (
            "research complete\nDUFYND_TASK_STATE: done"
        )
        return 0

    monkeypatch.setattr(nightshift, "process_loop", fake_loop)
    monkeypatch.setattr(nightshift, "process_branch_task", fake_branch)
    monkeypatch.setattr(nightshift, "process_safe_task", fake_safe)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_tasks=8,
            max_events=2,
            worker_timeout_seconds=60,
            max_retries=1,
        )
    )

    assert bridge.tasks["repo_current_engineering"]["status"] == "in_progress"
    assert bridge.tasks["repo_current_commerce"]["status"] == "done"
    assert session["branch_worker_used"] is True
    assert len(session["task_results"]) == 2
    assert {row["worker"] for row in session["task_results"]} == {
        "branch_worker",
        "safe_worker",
    }
    assert session["stop_reason"] == "engineering_quality_gate_pending"
    assert session["status"] == "awaiting_validation"
    assert (tmp_path / "worker-task.json").exists()


def test_nightshift_reports_budget_gate_after_no_cost_event_phase(monkeypatch) -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    bridge.inbox_pending = 1

    monkeypatch.setattr(
        nightshift,
        "_require_autonomous_mode",
        lambda: None,
    )

    async def fake_loop(_bridge, *, max_events):
        assert max_events == 2
        return 0

    monkeypatch.setattr(nightshift, "process_loop", fake_loop)

    def exhausted_budget(_bridge):
        raise RuntimeError("budget window does not permit another run")

    monkeypatch.setattr(nightshift, "_require_budget_window", exhausted_budget)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_tasks=8,
            max_events=2,
            worker_timeout_seconds=60,
            max_retries=1,
        )
    )

    assert session["stop_reason"] == "budget_gate"
    assert session["tasks_attempted"] == 0


def test_nightshift_defers_tasks_while_event_backlog_remains(monkeypatch) -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    bridge.inbox_pending = 3

    monkeypatch.setattr(
        nightshift,
        "_require_autonomous_mode",
        lambda: None,
    )
    monkeypatch.setattr(
        nightshift,
        "_require_budget_window",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    async def fake_loop(_bridge, *, max_events):
        assert max_events == 2
        return 0

    worker_called = False

    async def fake_safe(_bridge, *, task_id=None):
        nonlocal worker_called
        worker_called = True
        return 0

    monkeypatch.setattr(nightshift, "process_loop", fake_loop)
    monkeypatch.setattr(nightshift, "process_safe_task", fake_safe)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_tasks=8,
            max_events=2,
            worker_timeout_seconds=60,
            max_retries=1,
        )
    )

    assert worker_called is False
    assert session["stop_reason"] == "event_backlog_remaining"
    assert session["tasks_attempted"] == 0
    assert session["inbox_before"]["pending"] == 3
    assert session["inbox_after"]["pending"] == 3


def test_nightshift_does_not_mark_unclassified_safe_success_done(monkeypatch) -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])

    monkeypatch.setattr(
        nightshift,
        "_require_autonomous_mode",
        lambda: None,
    )
    monkeypatch.setattr(
        nightshift,
        "_require_budget_window",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    async def fake_safe(_bridge, *, task_id=None):
        bridge.tasks["repo_current_commerce"]["status"] = "in_progress"
        bridge.tasks["repo_current_commerce"]["evidence"] = "useful partial research"
        return 0

    monkeypatch.setattr(nightshift, "process_safe_task", fake_safe)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_tasks=8,
            max_events=0,
            worker_timeout_seconds=60,
            max_retries=1,
        )
    )

    assert bridge.tasks["repo_current_commerce"]["status"] == "ready"
    assert session["task_results"][0]["final_status"] == "in_progress"
    assert session["tasks_attempted"] == 1


def test_nightshift_retries_failed_task_then_continues(monkeypatch) -> None:
    bridge = FakeBridge(
        [
            task("repo_current_commerce", "commerce", 100),
            task("repo_current_content", "content", 90),
        ]
    )

    monkeypatch.setattr(
        nightshift,
        "_require_autonomous_mode",
        lambda: None,
    )
    monkeypatch.setattr(
        nightshift,
        "_require_budget_window",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    calls = 0

    async def flaky_safe(_bridge, *, task_id=None):
        nonlocal calls
        calls += 1
        if calls <= 2:
            bridge.tasks["repo_current_commerce"]["status"] = "blocked"
            bridge.tasks["repo_current_commerce"]["evidence"] = "worker failed"
            return 1
        bridge.tasks["repo_current_content"]["status"] = "in_progress"
        bridge.tasks["repo_current_content"]["evidence"] = (
            "content prepared\nDUFYND_TASK_STATE: done"
        )
        return 0

    monkeypatch.setattr(nightshift, "process_safe_task", flaky_safe)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_tasks=8,
            max_events=0,
            worker_timeout_seconds=60,
            max_retries=1,
        )
    )

    assert bridge.tasks["repo_current_commerce"]["status"] == "blocked"
    assert bridge.tasks["repo_current_content"]["status"] == "done"
    assert calls == 3
    assert [row["final_status"] for row in session["task_results"]] == [
        "blocked",
        "done",
    ]


def test_finalize_branch_task_moves_yellow_work_to_owner_review() -> None:
    bridge = FakeBridge([task("repo_current_engineering", "engineering", 100)])
    bridge.tasks["repo_current_engineering"]["status"] = "in_progress"
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "nightshift-test",
            "status": "awaiting_validation",
            "task_results": [
                {
                    "task_id": "repo_current_engineering",
                    "final_status": "in_progress",
                }
            ],
            "validation": {"status": "not_run", "pr_url": None},
        },
    }

    metadata = Path("test-nightshift-worker-metadata.json")
    metadata.write_text(
        '{"session_id":"nightshift-test","task_id":"repo_current_engineering"}',
        encoding="utf-8",
    )
    try:
        changed = nightshift.finalize_branch_task(
            bridge,
            metadata_path=metadata,
            status="waiting_human_input",
            evidence="QA passed. READY FOR TUAN APPROVAL.",
            pr_url="https://github.com/tncommerce/commerce-agents/pull/999",
        )
    finally:
        metadata.unlink(missing_ok=True)

    assert changed is True
    assert bridge.tasks["repo_current_engineering"]["status"] == "waiting_human_input"
    session = bridge.master[nightshift.SESSION_KEY]["value"]
    assert session["validation"]["status"] == "passed"
    assert session["status"] == "completed"
    assert session["task_results"][0]["pr_url"].endswith("/999")


def test_finalize_branch_task_blocks_missing_pr_url() -> None:
    bridge = FakeBridge([task("repo_current_engineering", "engineering", 100)])
    bridge.tasks["repo_current_engineering"]["status"] = "in_progress"
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "nightshift-no-pr",
            "status": "awaiting_validation",
            "task_results": [
                {
                    "task_id": "repo_current_engineering",
                    "final_status": "in_progress",
                }
            ],
            "validation": {"status": "not_run", "pr_url": None},
        },
    }

    metadata = Path("test-nightshift-no-pr.json")
    metadata.write_text(
        '{"session_id":"nightshift-no-pr","task_id":"repo_current_engineering"}',
        encoding="utf-8",
    )
    try:
        changed = nightshift.finalize_branch_task(
            bridge,
            metadata_path=metadata,
            status="waiting_human_input",
            evidence="QA passed.",
            pr_url=None,
        )
    finally:
        metadata.unlink(missing_ok=True)

    assert changed is True
    assert bridge.tasks["repo_current_engineering"]["status"] == "blocked"
    session = bridge.master[nightshift.SESSION_KEY]["value"]
    assert session["validation"]["status"] == "failed"
    assert session["status"] == "needs_attention"


def test_morning_report_uses_audited_system_data(monkeypatch) -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "nightshift-report",
            "status": "completed",
            "started_at": "2026-09-29T20:00:00+00:00",
            "ended_at": "2026-09-29T21:30:00+00:00",
            "stop_reason": "no_safe_work",
            "source_fingerprint_sha256": "fingerprint-1",
            "task_results": [
                {
                    "task_id": "repo_current_commerce",
                    "domain": "commerce",
                    "title": "Verify merchant data",
                    "worker": "safe_worker",
                    "final_status": "done",
                    "attempts": 1,
                }
            ],
            "validation": {"status": "not_run", "pr_url": None},
        },
    }
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    report, markdown = nightshift.build_morning_report(
        bridge,
        qa_status="success",
    )

    assert report["duration"] == "1h30m"
    assert report["completed"] == 1
    assert report["ai_cost_usd"] == 0.19
    assert report["ai_cost_source"] == "audited_agent_runs"
    assert report["ai_cost_complete"] is True
    assert report["budget"]["remaining_usd"] == 2.1
    assert "Verify merchant data" in markdown
    assert "$0.1900" in markdown


def test_morning_report_marks_timeout_cost_as_incomplete(monkeypatch) -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "nightshift-timeout-report",
            "status": "completed",
            "started_at": "2026-09-29T20:00:00+00:00",
            "ended_at": "2026-09-29T20:10:00+00:00",
            "stop_reason": "event_timeout",
            "event_result": 124,
            "source_fingerprint_sha256": "fingerprint-1",
            "task_results": [],
            "validation": {"status": "not_run", "pr_url": None},
        },
    }
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    report, markdown = nightshift.build_morning_report(
        bridge,
        qa_status="failure",
    )

    assert report["ai_cost_source"] == "audited_agent_runs"
    assert report["ai_cost_complete"] is False
    assert "zusätzlicher Provider-Verbrauch unverbucht" in markdown
