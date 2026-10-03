from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
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
        self.agent_runs_override = None

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
        if self.agent_runs_override is not None:
            return list(self.agent_runs_override)
        return [
            {
                "agent_name": "jarvis_safe_worker",
                "run_type": "safe_task:repo_current_commerce",
                "output_summary": "DUFYND_TASK_STATE: done",
                "decisions": [{"cost_usd": 0.08}],
                "created_at": since_iso,
            },
            {
                "agent_name": "jarvis_branch_worker",
                "run_type": "branch_task:repo_current_engineering",
                "output_summary": "branch prepared",
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


def test_orchestration_failure_persists_stop_reason_and_blocked_result(monkeypatch):
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(nightshift, "_require_budget_window", lambda bridge: ("budget", {}))

    async def failed_worker(*args, **kwargs):
        request = httpx.Request("PATCH", "https://example.test/tasks")
        response = httpx.Response(400, request=request)
        raise httpx.HTTPStatusError("status rejected", request=request, response=response)

    monkeypatch.setattr(nightshift, "_run_task_with_retry", failed_worker)
    asyncio.run(nightshift.run_nightshift(bridge, max_events=0))
    session = bridge.master[nightshift.SESSION_KEY]["value"]
    assert session["status"] == "completed"
    assert session["stop_reason"] == "no_safe_work"
    assert session["ended_at"]
    assert session["task_results"][0]["final_status"] == "blocked"
    report, markdown = nightshift.build_morning_report(
        bridge, historical_report=True, qa_status="failure"
    )
    assert report["blocked"] == 1
    assert report["ai_cost_complete"] is False
    assert "no_safe_work" in markdown


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


def test_non_repo_current_green_task_is_selected() -> None:
    candidate = task("jarvis_research_backlog_001", "research", 100)
    queue = {"safe_to_execute": [candidate]}

    selected = nightshift._select_task(
        queue,
        branch_worker_used=False,
        attempted_task_ids=set(),
    )

    assert selected is not None
    assert selected["task_id"] == "jarvis_research_backlog_001"


def test_non_repo_current_engineering_task_still_respects_tech_lease() -> None:
    candidate = task("jarvis_engineering_backlog_001", "engineering", 100)
    queue = {"safe_to_execute": [candidate]}

    selected = nightshift._select_task(
        queue,
        branch_worker_used=False,
        attempted_task_ids=set(),
        engineering_allowed=False,
    )

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


def test_select_task_blocks_engineering_while_tech_lease_is_active() -> None:
    queue = {
        "safe_to_execute": [
            task("repo_current_engineering", "engineering", 100),
        ]
    }

    selected = nightshift._select_task(
        queue,
        branch_worker_used=False,
        attempted_task_ids=set(),
        engineering_allowed=False,
    )

    assert selected is None


def test_expired_tech_lease_allows_takeover(monkeypatch) -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.TECH_LEASE_KEY] = {
        "key": nightshift.TECH_LEASE_KEY,
        "value": {
            "status": "active",
            "owner": "chatgpt_work_tech",
            "heartbeat_at": "2026-09-29T20:00:00+00:00",
            "expires_at": "2026-09-29T20:01:00+00:00",
        },
    }
    monkeypatch.setattr(
        nightshift,
        "utc_now",
        lambda: nightshift.datetime.fromisoformat("2026-09-29T21:00:00+00:00"),
    )

    lease = nightshift._tech_lease_state(bridge)

    assert lease["active"] is False
    assert lease["remaining_seconds"] == 0


def test_active_tech_lease_reports_remaining_seconds(monkeypatch) -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.TECH_LEASE_KEY] = {
        "key": nightshift.TECH_LEASE_KEY,
        "value": {
            "status": "active",
            "owner": "chatgpt_work_tech",
            "heartbeat_at": "2026-09-29T21:00:00+00:00",
            "expires_at": "2026-09-29T21:30:00+00:00",
        },
    }
    monkeypatch.setattr(
        nightshift,
        "utc_now",
        lambda: nightshift.datetime.fromisoformat("2026-09-29T21:10:00+00:00"),
    )

    lease = nightshift._tech_lease_state(bridge)

    assert lease["active"] is True
    assert lease["owner"] == "chatgpt_work_tech"
    assert lease["remaining_seconds"] == 1200


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


def test_recovery_requires_verification_of_audited_worker_completion() -> None:
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

    assert bridge.tasks["repo_current_commerce"]["status"] == "waiting_external"
    assert session["current_task"] is None
    assert session["task_results"][0]["recovered_after_interruption"] is True


def test_recovery_never_marks_failed_safe_run_done() -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    bridge.tasks["repo_current_commerce"]["status"] = "in_progress"
    bridge.agent_runs_override = [
        {
            "agent_name": "jarvis",
            "run_type": "safe_task_failed:repo_current_commerce",
            "output_summary": ("Useful evidence collected.\nDUFYND_TASK_STATE: waiting_external"),
            "decisions": [{"cost_usd": 0.12}],
            "created_at": "2026-09-29T21:55:00+00:00",
        }
    ]
    session = {
        "session_id": "nightshift-recover-failed-safe",
        "started_at": "2026-09-29T21:50:00+00:00",
        "current_task": {
            "task_id": "repo_current_commerce",
            "domain": "commerce",
            "worker": "safe_worker",
            "attempt": 1,
            "started_at": "2026-09-29T21:55:00+00:00",
        },
        "task_results": [],
    }

    nightshift._recover_interrupted_work(bridge, session)

    assert bridge.tasks["repo_current_commerce"]["status"] == "waiting_external"
    assert session["task_results"][0]["final_status"] == "waiting_external"
    assert session["task_results"][0]["result_code"] == 1
    assert session["current_task"] is None


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
    assert bridge.tasks["repo_current_commerce"]["status"] == "waiting_external"
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
    assert bridge.tasks["repo_current_content"]["status"] == "waiting_external"
    assert calls == 3
    assert [row["final_status"] for row in session["task_results"]] == [
        "blocked",
        "waiting_external",
    ]


def test_nightshift_bounds_unexpected_task_local_exception(monkeypatch) -> None:
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

    async def broken_safe(_bridge, *, task_id=None):
        raise ValueError("persistence edge case")

    monkeypatch.setattr(nightshift, "process_safe_task", broken_safe)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_tasks=1,
            max_events=0,
            worker_timeout_seconds=60,
            max_retries=0,
        )
    )

    assert bridge.tasks["repo_current_commerce"]["status"] == "blocked"
    assert session["status"] == "completed"
    assert session["current_task"] is None
    assert session["task_results"][0]["final_status"] == "blocked"


def test_persistence_failure_is_recorded_without_aborting_nightshift(monkeypatch) -> None:
    class PersistenceFailureBridge(FakeBridge):
        def set_autonomy_task_status(self, *, task_id, status, evidence):
            if task_id == "repo_current_commerce" and status == "blocked":
                raise RuntimeError("simulated Supabase persistence failure")
            return super().set_autonomy_task_status(
                task_id=task_id,
                status=status,
                evidence=evidence,
            )

    bridge = PersistenceFailureBridge(
        [
            task("repo_current_commerce", "commerce", 100),
            task("repo_current_content", "content", 90),
        ]
    )

    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(
        nightshift,
        "_require_budget_window",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    async def task_worker(_bridge, *, task_id=None):
        if task_id == "repo_current_commerce":
            raise ValueError("simulated task-local failure")
        bridge.tasks["repo_current_content"]["status"] = "in_progress"
        bridge.tasks["repo_current_content"]["evidence"] = (
            "content prepared\nDUFYND_TASK_STATE: done"
        )
        return 0

    monkeypatch.setattr(nightshift, "process_safe_task", task_worker)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_tasks=8,
            max_events=0,
            worker_timeout_seconds=60,
            max_retries=0,
        )
    )

    assert [row["final_status"] for row in session["task_results"]] == [
        "blocked",
        "waiting_external",
    ]
    assert session["status"] == "completed"
    assert session["persistence_errors"][0]["task_id"] == "repo_current_commerce"
    assert bridge.tasks["repo_current_content"]["status"] == "waiting_external"


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
        historical_report=True,
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


def test_morning_report_aggregates_supervisor_session_history(monkeypatch) -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "session-2",
            "status": "completed",
            "started_at": "2026-09-30T01:00:00+00:00",
            "ended_at": "2026-09-30T01:30:00+00:00",
            "stop_reason": "no_safe_work",
            "task_results": [],
            "validation": {"status": "not_run", "pr_url": None},
        },
    }
    bridge.master[nightshift.SUPERVISOR_KEY] = {
        "key": nightshift.SUPERVISOR_KEY,
        "value": {
            "supervisor_id": "supervisor-1",
            "status": "completed",
            "started_at": "2026-09-30T00:00:00+00:00",
            "ended_at": "2026-09-30T02:00:00+00:00",
            "stop_reason": "idle_limit_reached",
            "cycles_completed": 2,
            "idle_cycles": 2,
            "session_summaries": [
                {
                    "session_id": "session-1",
                    "task_results": [
                        {
                            "task_id": "repo_current_commerce",
                            "domain": "commerce",
                            "title": "Verify merchant data",
                            "worker": "safe_worker",
                            "result_code": 0,
                            "final_status": "done",
                            "attempts": 1,
                        }
                    ],
                },
                {
                    "session_id": "session-2",
                    "task_results": [
                        {
                            "task_id": "repo_current_content",
                            "domain": "content",
                            "title": "Prepare content queue",
                            "worker": "safe_worker",
                            "result_code": 1,
                            "final_status": "blocked",
                            "attempts": 1,
                        }
                    ],
                },
            ],
        },
    }
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    report, markdown = nightshift.build_morning_report(
        bridge, historical_report=True, qa_status="success"
    )

    assert report["supervisor"]["supervisor_id"] == "supervisor-1"
    assert report["session_count"] == 2
    assert report["duration"] == "2h00m"
    assert report["completed"] == 1
    assert report["blocked"] == 1
    assert report["stop_reason"] == "idle_limit_reached"
    assert "Verify merchant data" in markdown
    assert "Prepare content queue" in markdown
    assert "Sessions: 2" in markdown


def test_morning_report_ignores_stale_supervisor_for_newer_session(monkeypatch) -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.SUPERVISOR_KEY] = {
        "key": nightshift.SUPERVISOR_KEY,
        "value": {
            "supervisor_id": "old-supervisor",
            "status": "completed",
            "started_at": "2026-09-29T20:00:00+00:00",
            "ended_at": "2026-09-29T21:00:00+00:00",
            "stop_reason": "idle_limit_reached",
            "cycles_completed": 0,
            "session_summaries": [],
        },
    }
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "new-session",
            "status": "completed",
            "started_at": "2026-09-30T05:00:00+00:00",
            "ended_at": "2026-09-30T05:20:00+00:00",
            "stop_reason": "no_safe_work",
            "source_fingerprint_sha256": "fresh",
            "task_results": [
                {
                    "task_id": "repo_current_research",
                    "domain": "research",
                    "title": "Fresh research",
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
        bridge, historical_report=True, qa_status="success"
    )

    assert report["supervisor"] is None
    assert report["session_id"] == "new-session"
    assert report["start"] == "2026-09-30T05:00:00+00:00"
    assert report["completed"] == 1
    assert "Fresh research" in markdown


def test_morning_report_uses_newer_idle_supervisor_without_stale_session(
    monkeypatch,
) -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "old-session",
            "status": "completed",
            "started_at": "2026-09-29T20:00:00+00:00",
            "ended_at": "2026-09-29T20:30:00+00:00",
            "stop_reason": "no_safe_work",
            "task_results": [
                {
                    "task_id": "old-task",
                    "domain": "commerce",
                    "title": "Old task",
                    "worker": "safe_worker",
                    "final_status": "done",
                    "attempts": 1,
                }
            ],
            "validation": {"status": "not_run", "pr_url": None},
        },
    }
    bridge.master[nightshift.SUPERVISOR_KEY] = {
        "key": nightshift.SUPERVISOR_KEY,
        "value": {
            "supervisor_id": "idle-supervisor",
            "status": "completed",
            "started_at": "2026-09-30T05:00:00+00:00",
            "ended_at": "2026-09-30T06:00:00+00:00",
            "stop_reason": "idle_limit_reached",
            "cycles_completed": 0,
            "idle_cycles": 12,
            "session_summaries": [],
        },
    }
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    report, markdown = nightshift.build_morning_report(
        bridge, historical_report=True, qa_status="success"
    )

    assert report["supervisor"]["supervisor_id"] == "idle-supervisor"
    assert report["session_count"] == 0
    assert report["completed"] == 0
    assert report["start"] == "2026-09-30T05:00:00+00:00"
    assert report["stop_reason"] == "idle_limit_reached"
    assert "Old task" not in markdown


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
        historical_report=True,
        qa_status="failure",
    )

    assert report["ai_cost_source"] == "audited_agent_runs"
    assert report["ai_cost_complete"] is False
    assert "zusätzlicher Provider-Verbrauch unverbucht" in markdown


def test_morning_report_excludes_agent_runs_after_supervisor_end(monkeypatch) -> None:
    bridge = FakeBridge()
    bridge.master[nightshift.SUPERVISOR_KEY] = {
        "key": nightshift.SUPERVISOR_KEY,
        "value": {
            "supervisor_id": "supervisor-cost-window",
            "status": "completed",
            "started_at": "2026-09-30T00:00:00+00:00",
            "ended_at": "2026-09-30T02:00:00+00:00",
            "stop_reason": "idle_limit_reached",
            "cycles_completed": 1,
            "idle_cycles": 1,
            "session_summaries": [],
        },
    }
    bridge.agent_runs_override = [
        {
            "agent_name": "jarvis_safe_worker",
            "run_type": "safe_task:repo_current_commerce",
            "decisions": [{"cost_usd": 0.08}],
            "created_at": "2026-09-30T01:00:00+00:00",
        },
        {
            "agent_name": "jarvis_safe_worker",
            "run_type": "safe_task:later_task",
            "decisions": [{"cost_usd": 0.99}],
            "created_at": "2026-09-30T02:05:00+00:00",
        },
    ]
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    report, _markdown = nightshift.build_morning_report(
        bridge, historical_report=True, qa_status="success"
    )

    assert report["ai_cost_usd"] == 0.08
    assert report["ai_cost_complete"] is True


def test_nightshift_does_not_start_events_without_full_timeout_window(monkeypatch) -> None:
    bridge = FakeBridge()
    bridge.inbox_pending = 1
    called = False

    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(nightshift, "_require_budget_window", lambda _bridge: ("budget", {}))

    async def fake_loop(_bridge, *, max_events):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(nightshift, "process_loop", fake_loop)
    deadline = nightshift.utc_now() + timedelta(seconds=30)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_events=2,
            worker_timeout_seconds=60,
            deadline_at=deadline,
        )
    )

    assert called is False
    assert session["stop_reason"] == "time_horizon_reached"
    assert session["events_processed_estimate"] == 0
    assert session["tasks_attempted"] == 0


def test_nightshift_does_not_start_task_without_full_timeout_window(monkeypatch) -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    called = False

    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(nightshift, "_require_budget_window", lambda _bridge: ("budget", {}))

    async def fake_safe(_bridge, *, task_id=None):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(nightshift, "process_safe_task", fake_safe)
    deadline = nightshift.utc_now() + timedelta(seconds=30)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_events=0,
            worker_timeout_seconds=60,
            deadline_at=deadline,
        )
    )

    assert called is False
    assert session["stop_reason"] == "time_horizon_reached"
    assert session["tasks_attempted"] == 0
    assert bridge.tasks["repo_current_commerce"]["status"] == "ready"


def test_nightshift_defers_retry_when_timeout_window_no_longer_fits(monkeypatch) -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    start = datetime(2026, 9, 30, 5, 0, tzinfo=UTC)
    now = {"value": start}
    calls = 0

    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(nightshift, "_require_budget_window", lambda _bridge: ("budget", {}))
    monkeypatch.setattr(nightshift, "utc_now", lambda: now["value"])

    async def flaky_safe(_bridge, *, task_id=None):
        nonlocal calls
        calls += 1
        now["value"] = start + timedelta(seconds=100)
        raise ValueError("first attempt failed")

    monkeypatch.setattr(nightshift, "process_safe_task", flaky_safe)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_events=0,
            worker_timeout_seconds=60,
            max_retries=1,
            deadline_at=start + timedelta(seconds=120),
        )
    )

    assert calls == 1
    assert session["stop_reason"] == "time_horizon_reached"
    assert session["current_task"] is None
    assert bridge.tasks["repo_current_commerce"]["status"] == "ready"


def test_nightshift_worker_cancellation_blocks_task_and_never_auto_retries(monkeypatch) -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])

    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(nightshift, "_require_budget_window", lambda _bridge: ("budget", {}))

    async def cancelled_safe(_bridge, *, task_id=None):
        raise asyncio.CancelledError

    monkeypatch.setattr(nightshift, "process_safe_task", cancelled_safe)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            nightshift.run_nightshift(
                bridge,
                max_events=0,
                worker_timeout_seconds=60,
                max_retries=1,
                deadline_at=nightshift.utc_now() + timedelta(minutes=5),
            )
        )

    assert bridge.tasks["repo_current_commerce"]["status"] == "blocked"
    assert "no automatic retry" in bridge.tasks["repo_current_commerce"]["evidence"]
    session = bridge.master[nightshift.SESSION_KEY]["value"]
    assert session["status"] == "needs_attention"
    assert session["stop_reason"] == "worker_cancelled"
    assert session["runtime_error_type"] == "CancelledError"
    assert session["current_task"]["attempt"] == 1


def test_next_action_approval_count_only_includes_active_human_gates() -> None:
    migration = Path("supabase/migrations/20260930124955_dufynd_next_action_approval_hygiene.sql")
    sql = migration.read_text(encoding="utf-8")

    assert "status='approval_required'" in sql
    assert "requires_human_approval" in sql
    assert "'planned'::text, 'ready'::text, 'in_progress'::text" in sql
    assert "status='approval_required' or requires_human_approval" not in sql


def test_next_action_approval_hygiene_preserves_ready_work_precedence() -> None:
    migration = Path("supabase/migrations/20260930124955_dufynd_next_action_approval_hygiene.sql")
    sql = migration.read_text(encoding="utf-8")

    assert "when ready_count > 0 then 'work_available'" in sql
    assert "when ready_count > 0 then null" in sql
    assert "when waiting_human_count > 0 then 'waiting_for_human_input'" in sql
    assert "when approval_count > 0 then 'human_approval_required'" in sql


def test_recovery_blocks_interrupted_task_without_audited_run() -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    bridge.tasks["repo_current_commerce"]["status"] = "in_progress"
    bridge.agent_runs_override = []
    session = {
        "session_id": "nightshift-recover-unknown-cost",
        "started_at": "2026-09-30T10:00:00+00:00",
        "status": "running",
        "current_task": {
            "task_id": "repo_current_commerce",
            "domain": "commerce",
            "worker": "safe_worker",
            "attempt": 1,
            "started_at": "2026-09-30T10:05:00+00:00",
        },
        "task_results": [],
    }

    nightshift._recover_interrupted_work(bridge, session)

    assert bridge.tasks["repo_current_commerce"]["status"] == "blocked"
    assert session["status"] == "needs_attention"
    assert session["stop_reason"] == "interrupted_task_unknown_cost"
    assert session["current_task"] is None
    assert session["task_results"][0]["provider_cost_unknown"] is True


def test_nightshift_event_failure_stops_before_tasks(monkeypatch) -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    bridge.inbox_pending = 1

    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(
        nightshift,
        "_require_budget_window",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    async def failed_loop(_bridge, *, max_events):
        assert max_events == 2
        return 1

    worker_called = False

    async def should_not_run(*_args, **_kwargs):
        nonlocal worker_called
        worker_called = True
        return 0

    monkeypatch.setattr(nightshift, "process_loop", failed_loop)
    monkeypatch.setattr(nightshift, "process_safe_task", should_not_run)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_events=2,
            worker_timeout_seconds=60,
        )
    )

    assert worker_called is False
    assert session["event_result"] == 1
    assert session["stop_reason"] == "event_failure"
    assert session["status"] == "needs_attention"
    assert session["tasks_attempted"] == 0


def test_nightshift_unknown_worker_cost_blocks_without_retry(monkeypatch) -> None:
    bridge = FakeBridge([task("repo_current_commerce", "commerce", 100)])
    bridge.agent_runs_override = []

    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(
        nightshift,
        "_require_budget_window",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    calls = 0

    async def failed_safe(_bridge, *, task_id=None):
        nonlocal calls
        calls += 1
        return 1

    monkeypatch.setattr(nightshift, "process_safe_task", failed_safe)

    session = asyncio.run(
        nightshift.run_nightshift(
            bridge,
            max_events=0,
            worker_timeout_seconds=60,
            max_retries=2,
        )
    )

    assert calls == 1
    assert bridge.tasks["repo_current_commerce"]["status"] == "blocked"
    assert session["stop_reason"] == "unknown_provider_cost"
    assert session["status"] == "needs_attention"
    assert session["task_results"][0]["provider_cost_unknown"] is True


def test_morning_report_marks_supervisor_cancellation_cost_incomplete() -> None:
    bridge = FakeBridge()
    bridge.agent_runs_override = []
    bridge.master[nightshift.SUPERVISOR_KEY] = {
        "key": nightshift.SUPERVISOR_KEY,
        "value": {
            "supervisor_id": "supervisor-cancelled",
            "status": "needs_attention",
            "started_at": "2026-09-30T12:00:00+00:00",
            "ended_at": "2026-09-30T12:10:00+00:00",
            "deadline_at": "2026-09-30T17:00:00+00:00",
            "stop_reason": "supervisor_cancelled",
            "runtime_error_type": "CancelledError",
            "cycles_completed": 0,
            "idle_cycles": 0,
            "session_summaries": [],
        },
    }

    report, _markdown = nightshift.build_morning_report(
        bridge,
        historical_report=True,
        qa_status="cancelled",
    )

    assert report["stop_reason"] == "supervisor_cancelled"
    assert report["ai_cost_complete"] is False
