from __future__ import annotations

from scripts import dufynd_jarvis_nightshift as nightshift


class ReportBridge:
    def __init__(self) -> None:
        self.master: dict[str, dict] = {}

    def load_master_status_entry(self, key: str):
        return self.master.get(key)

    def load_agent_runs_since(self, since_iso: str):
        return [
            {
                "agent_name": "jarvis_safe_worker",
                "run_type": "safe_task:repo_current_commerce",
                "decisions": [{"cost_usd": 0.08}],
                "created_at": since_iso,
            },
            {
                "agent_name": "jarvis_safe_worker",
                "run_type": "safe_task:repo_current_content",
                "decisions": [{"cost_usd": 0.11}],
                "created_at": since_iso,
            },
        ]

    def load_autonomy_queue(self):
        return {
            "safe_to_execute": [],
            "in_progress": [],
            "waiting_human_input": [],
            "waiting_external": [],
            "blocked": [],
            "approval_required": [],
            "done_recent": [],
        }

    def load_health(self):
        return {
            "state": "idle",
            "inbox": {"pending": 0, "processing": 0, "failed": 0},
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


def test_morning_report_aggregates_supervisor_sessions(monkeypatch) -> None:
    bridge = ReportBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "nightshift-cycle-2",
            "status": "completed",
            "started_at": "2026-09-29T21:00:00+00:00",
            "ended_at": "2026-09-29T22:00:00+00:00",
            "stop_reason": "no_safe_work",
            "source_fingerprint_sha256": "fingerprint-2",
            "task_results": [],
            "validation": {"status": "not_run", "pr_url": None},
        },
    }
    bridge.master[nightshift.SUPERVISOR_KEY] = {
        "key": nightshift.SUPERVISOR_KEY,
        "value": {
            "supervisor_id": "supervisor-report",
            "status": "completed",
            "started_at": "2026-09-29T20:00:00+00:00",
            "ended_at": "2026-09-29T22:00:00+00:00",
            "deadline_at": "2026-09-30T01:00:00+00:00",
            "stop_reason": "idle_limit_reached",
            "cycles_completed": 2,
            "idle_cycles": 2,
            "session_summaries": [
                {
                    "session_id": "nightshift-cycle-1",
                    "stop_reason": "task_limit_reached",
                    "task_results": [
                        {
                            "task_id": "repo_current_commerce",
                            "domain": "commerce",
                            "title": "Verify merchant data",
                            "worker": "safe_worker",
                            "result_code": 0,
                            "final_status": "done",
                            "attempts": 1,
                            "pr_url": None,
                        }
                    ],
                },
                {
                    "session_id": "nightshift-cycle-2",
                    "stop_reason": "no_safe_work",
                    "task_results": [
                        {
                            "task_id": "repo_current_content",
                            "domain": "content",
                            "title": "Prepare content brief",
                            "worker": "safe_worker",
                            "result_code": 1,
                            "final_status": "blocked",
                            "attempts": 1,
                            "pr_url": None,
                        }
                    ],
                },
            ],
        },
    }
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    report, markdown = nightshift.build_morning_report(
        bridge,
        qa_status="success",
    )

    assert report["duration"] == "2h00m"
    assert report["session_count"] == 2
    assert report["supervisor"]["supervisor_id"] == "supervisor-report"
    assert report["supervisor"]["cycles_completed"] == 2
    assert report["stop_reason"] == "idle_limit_reached"
    assert report["completed"] == 1
    assert report["blocked"] == 1
    assert report["session_id"] == "nightshift-cycle-2"
    assert report["source_fingerprint_sha256"] == "fingerprint-2"
    assert "Verify merchant data" in markdown
    assert "Prepare content brief" in markdown
    assert "Sessions: 2" in markdown


def test_morning_report_ignores_stale_session_for_idle_supervisor(
    monkeypatch,
) -> None:
    bridge = ReportBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "key": nightshift.SESSION_KEY,
        "value": {
            "session_id": "nightshift-yesterday",
            "status": "completed",
            "started_at": "2026-09-28T20:00:00+00:00",
            "ended_at": "2026-09-28T21:00:00+00:00",
            "stop_reason": "no_safe_work",
            "source_fingerprint_sha256": "old-fingerprint",
            "task_results": [
                {
                    "task_id": "repo_current_old",
                    "domain": "commerce",
                    "title": "Old task must not appear",
                    "worker": "safe_worker",
                    "result_code": 0,
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
            "supervisor_id": "supervisor-idle",
            "status": "completed",
            "started_at": "2026-09-29T20:00:00+00:00",
            "ended_at": "2026-09-29T20:10:00+00:00",
            "deadline_at": "2026-09-30T01:00:00+00:00",
            "stop_reason": "idle_limit_reached",
            "cycles_completed": 0,
            "idle_cycles": 2,
            "session_summaries": [],
        },
    }
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    report, markdown = nightshift.build_morning_report(
        bridge,
        qa_status="success",
    )

    assert report["duration"] == "10m00s"
    assert report["session_count"] == 0
    assert report["session_id"] is None
    assert report["completed"] == 0
    assert report["source_fingerprint_sha256"] is None
    assert report["stop_reason"] == "idle_limit_reached"
    assert "Old task must not appear" not in markdown
