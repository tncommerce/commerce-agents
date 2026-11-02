from __future__ import annotations

from datetime import UTC, datetime

from scripts.audit_dufynd_jarvis_control_plane import audit_control_plane

NOW = datetime(2026, 9, 30, 6, 0, tzinfo=UTC)


class FakeBridge:
    def __init__(
        self,
        *,
        queue=None,
        health=None,
        budget=None,
        session=None,
        supervisor=None,
        tech_lease=None,
    ):
        self.queue = queue or {
            "safe_to_execute": [],
            "in_progress": [],
            "waiting_human_input": [],
            "waiting_external": [],
            "approval_required": [],
        }
        self.health = health or {
            "state": "idle",
            "inbox": {"pending": 0, "processing": 0, "failed": 0},
        }
        self.budget = budget or {
            "budget_id": "jarvis_activation_pilot_001",
            "model": "claude-sonnet-5",
            "status": "active",
            "can_run": True,
            "cap_usd": 2.5,
            "max_runs": 20,
            "spent_usd": 1.8161,
            "remaining_usd": 0.6839,
            "remaining_runs": 4,
        }
        self.rows = {}
        if session is not None:
            self.rows["jarvis.nightshift_session"] = {"value": session}
        if supervisor is not None:
            self.rows["jarvis.nightshift_supervisor"] = {"value": supervisor}
        if tech_lease is not None:
            self.rows["continuity.tech_lease"] = {"value": tech_lease}

    def load_autonomy_queue(self):
        return self.queue

    def load_health(self):
        return self.health

    def load_budget_status(self, _budget_id):
        return self.budget

    def load_master_status_entry(self, key):
        return self.rows.get(key)


def test_audit_flags_current_known_stale_snapshots_without_mutation() -> None:
    bridge = FakeBridge(
        queue={
            "safe_to_execute": [],
            "in_progress": [],
            "waiting_human_input": [{"task_id": "repo_current_content"}],
            "waiting_external": [{"task_id": "repo_current_commerce"}],
            "approval_required": [],
        },
        health={
            "state": "idle",
            "inbox": {"pending": 0, "processing": 0, "failed": 0},
            "runtime_state": {
                "pilot": {
                    "budget_id": "jarvis_activation_pilot_001",
                    "model": "claude-sonnet-5",
                    "cap_usd": 2.5,
                    "max_runs": 10,
                    "spent_usd": 0.2337,
                    "remaining_usd": 2.2663,
                    "remaining_runs": 8,
                }
            },
        },
        session={
            "session_id": "nightshift-1",
            "status": "failed",
            "started_at": "2026-09-29T21:50:07+00:00",
            "ended_at": "2026-09-29T21:55:55+00:00",
            "last_heartbeat_at": "2026-09-29T21:55:05+00:00",
            "stop_reason": "task_persistence_error",
            "current_task": None,
        },
        tech_lease={
            "owner": "chatgpt_work_tech",
            "status": "active",
            "heartbeat_at": "2026-09-29T21:46:58+00:00",
            "expires_at": "2026-09-29T22:16:58+00:00",
        },
    )

    report = audit_control_plane(bridge, now=NOW)

    assert report["status"] == "attention"
    assert report["autonomy_boundary"]["state"] == "owner_review"
    assert report["nightshift_session"]["stale"] is False
    assert report["tech_lease"]["expired"] is True
    codes = {item["code"] for item in report["issues"]}
    assert codes == {
        "expired_active_tech_lease",
        "stale_health_budget_snapshot",
    }
    assert {
        "max_runs",
        "spent_usd",
        "remaining_usd",
        "remaining_runs",
    } <= set(report["budget_snapshot"]["mismatches"])
    assert report["budget"]["remaining_runs"] == 4


def test_audit_flags_stale_active_nightshift_session() -> None:
    bridge = FakeBridge(
        session={
            "session_id": "nightshift-running",
            "status": "running",
            "started_at": "2026-09-30T04:00:00+00:00",
            "last_heartbeat_at": "2026-09-30T04:30:00+00:00",
            "current_task": {"task_id": "repo_current_commerce"},
        },
        tech_lease={
            "owner": "chatgpt_work_tech",
            "status": "released",
            "expires_at": "2026-09-30T04:45:00+00:00",
        },
    )

    report = audit_control_plane(
        bridge,
        now=NOW,
        stale_after_minutes=45,
    )

    assert report["nightshift_session"]["stale"] is True
    assert report["nightshift_session"]["heartbeat_age_minutes"] == 90.0
    assert "stale_active_nightshift_session" in {item["code"] for item in report["issues"]}


def test_audit_flags_stale_active_overnight_supervisor() -> None:
    bridge = FakeBridge(
        supervisor={
            "supervisor_id": "supervisor-running",
            "status": "running",
            "started_at": "2026-09-30T04:00:00+00:00",
            "last_heartbeat_at": "2026-09-30T04:30:00+00:00",
            "deadline_at": "2026-09-30T09:00:00+00:00",
            "cycles_completed": 3,
            "idle_cycles": 1,
            "lease_wait_cycles": 7,
        }
    )

    report = audit_control_plane(
        bridge,
        now=NOW,
        stale_after_minutes=45,
    )

    assert report["nightshift_supervisor"]["stale"] is True
    assert report["nightshift_supervisor"]["heartbeat_age_minutes"] == 90.0
    assert report["nightshift_supervisor"]["lease_wait_cycles"] == 7
    assert "stale_active_nightshift_supervisor" in {item["code"] for item in report["issues"]}


def test_audit_reports_clean_idle_control_plane() -> None:
    bridge = FakeBridge(
        session={
            "session_id": "nightshift-complete",
            "status": "completed",
            "started_at": "2026-09-30T05:00:00+00:00",
            "ended_at": "2026-09-30T05:05:00+00:00",
            "last_heartbeat_at": "2026-09-30T05:05:00+00:00",
            "stop_reason": "no_safe_work",
            "current_task": None,
        },
        tech_lease={
            "owner": "chatgpt_work_tech",
            "status": "released",
            "expires_at": "2026-09-30T05:30:00+00:00",
        },
        health={
            "state": "idle",
            "inbox": {"pending": 0, "processing": 0, "failed": 0},
            "runtime_state": {
                "pilot": {
                    "budget_id": "jarvis_activation_pilot_001",
                    "model": "claude-sonnet-5",
                    "cap_usd": 2.5,
                    "max_runs": 20,
                    "spent_usd": 1.8161,
                    "remaining_usd": 0.6839,
                    "remaining_runs": 4,
                }
            },
        },
    )

    report = audit_control_plane(bridge, now=NOW)

    assert report["status"] == "ok"
    assert report["issues"] == []
    assert report["autonomy_boundary"]["state"] == "idle"
    assert report["budget_snapshot"]["consistent"] is True


def test_audit_surfaces_failed_inbox_events() -> None:
    bridge = FakeBridge(
        health={
            "state": "events_waiting",
            "inbox": {"pending": 1, "processing": 0, "failed": 2},
        }
    )

    report = audit_control_plane(bridge, now=NOW)

    issue = next(item for item in report["issues"] if item["code"] == "failed_jarvis_inbox_events")
    assert issue["severity"] == "warning"
    assert "2 failed event(s)" in issue["message"]


def test_overdue_external_waits_are_visible_but_not_unblocked() -> None:
    rows = [
        {
            "task_id": "perfumetrader_product_coverage",
            "domain": "affiliate",
            "status": "waiting_external",
            "updated_at": "2026-10-01T09:00:00+00:00",
            "requires_human_approval": False,
            "instruction": "Do not leak private source details.",
        },
        {
            "task_id": "image-rights-pending",
            "domain": "commerce",
            "status": "waiting_external",
            "updated_at": "2026-10-03T09:00:00+00:00",
            "requires_human_approval": True,
            "evidence": "Private source address not for public output",
        },
        {
            "task_id": "recent-external",
            "domain": "commerce",
            "status": "waiting_external",
            "updated_at": "2026-10-30T09:00:00+00:00",
        },
    ]
    original = [dict(row) for row in rows]
    bridge = FakeBridge(
        queue={
            "safe_to_execute": [],
            "in_progress": [],
            "waiting_human_input": [],
            "waiting_external": rows,
            "approval_required": [],
            "blocked": [{"task_id": "unverified-transport"}],
        }
    )
    report = audit_control_plane(bridge, now=datetime(2026, 11, 2, tzinfo=UTC))
    waiting = report["waiting_external_review"]
    assert report["status"] == "attention"
    assert waiting["review_overdue"] == 2
    assert waiting["waiting_total"] == 3
    assert waiting["mutations_performed"] == 0
    assert waiting["automatically_unblocked"] == 0
    assert {row["task_id"] for row in waiting["overdue_tasks"]} == {
        "perfumetrader_product_coverage",
        "image-rights-pending",
    }
    assert waiting["overdue_tasks"][0]["age_days"] >= 30
    assert waiting["overdue_tasks"][1]["requires_human_approval"] is True
    assert bridge.queue["waiting_external"] == original
    assert report["autonomy_boundary"]["blocked"] == 1
    assert report["autonomy_boundary"]["state"] == "waiting_external"
    assert any(
        issue["code"] == "external_waiting_tasks_require_freshness_review"
        for issue in report["issues"]
    )
    assert "Private source address" not in str(waiting)


def test_only_blocked_tasks_are_not_reported_as_idle() -> None:
    bridge = FakeBridge(
        queue={
            "safe_to_execute": [],
            "in_progress": [],
            "waiting_human_input": [],
            "waiting_external": [],
            "approval_required": [],
            "blocked": [{"task_id": "unsafe-transport"}],
        }
    )
    report = audit_control_plane(bridge, now=NOW)
    assert report["autonomy_boundary"]["state"] == "blocked"
    assert report["autonomy_boundary"]["blocked"] == 1
    assert report["waiting_external_review"]["review_overdue"] == 0
    assert report["issues"] == []


def test_undated_or_future_waits_cannot_be_dated_by_inference() -> None:
    rows = [
        {"task_id": "missing-date", "updated_at": None},
        {"task_id": "future-date", "updated_at": "2099-01-01T00:00:00+00:00"},
        {"task_id": "invalid-date", "updated_at": "not-a-date"},
    ]
    bridge = FakeBridge(
        queue={
            "safe_to_execute": [],
            "in_progress": [],
            "waiting_human_input": [],
            "waiting_external": rows,
            "approval_required": [],
        }
    )
    report = audit_control_plane(bridge, now=NOW)
    review = report["waiting_external_review"]
    assert review["review_overdue"] == 0
    assert review["unverifiable_timestamp"] == 3
    assert review["overdue_tasks"] == []
    assert report["status"] == "ok"
