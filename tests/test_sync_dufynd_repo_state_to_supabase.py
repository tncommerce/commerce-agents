from __future__ import annotations

from scripts.sync_dufynd_repo_state_to_supabase import (
    SNAPSHOT_KEY,
    _task_state,
    apply_sync_plan,
    build_sync_plan,
)


class RecordingBridge:
    def __init__(self) -> None:
        self.master_rows = []
        self.tasks = []

    def upsert_master_status(self, **kwargs):
        self.master_rows.append(kwargs)

    def upsert_autonomy_task(self, **kwargs):
        self.tasks.append(kwargs)


def sample_repo_status() -> dict:
    return {
        "generated_at": "2026-09-29T17:00:00+00:00",
        "source_fingerprint_sha256": "abc123",
        "overall_state": "work_available",
        "active_domain": "commerce",
        "next_action": "obtain_licensed_image_sources",
        "next_action_class": "auto_allowed",
        "user_approval_required_now": False,
        "domains": {
            "commerce": {
                "domain": "commerce",
                "overall_state": "waiting_licensed_image_sources_and_approval",
                "execution_state": "work_available",
                "next_action": "obtain_licensed_image_sources",
                "next_action_class": "auto_allowed",
                "user_approval_required_now": False,
                "blockers": ["approved_images_incomplete"],
            },
            "content": {
                "domain": "content",
                "overall_state": "strategy_work_available",
                "execution_state": "manual_step_pending",
                "next_action": "reconcile_live_social_state",
                "next_action_class": "manual_state_reconciliation_required",
                "user_approval_required_now": False,
                "blockers": [],
            },
        },
    }


def test_task_state_maps_safe_work_to_ready() -> None:
    assert _task_state(
        {
            "execution_state": "work_available",
            "next_action_class": "auto_allowed",
        }
    ) == ("ready", False)


def test_task_state_preserves_explicit_approval_gate() -> None:
    assert _task_state(
        {
            "execution_state": "work_available",
            "next_action_class": "approval_required",
            "user_approval_required_now": True,
        }
    ) == ("approval_required", True)


def test_build_sync_plan_creates_snapshot_and_stable_domain_tasks() -> None:
    plan = build_sync_plan(sample_repo_status())

    assert plan["snapshot"]["key"] == SNAPSHOT_KEY
    assert plan["snapshot"]["value"]["source_fingerprint_sha256"] == "abc123"
    assert [task["task_id"] for task in plan["tasks"]] == [
        "repo_current_commerce",
        "repo_current_content",
    ]

    commerce, content = plan["tasks"]
    assert commerce["status"] == "ready"
    assert commerce["priority"] == 100
    assert commerce["requires_human_approval"] is False
    assert commerce["dependencies"] == ["approved_images_incomplete"]

    assert content["status"] == "waiting_human_input"
    assert content["priority"] == 90
    assert content["requires_human_approval"] is False


def test_apply_sync_plan_upserts_snapshot_and_tasks() -> None:
    bridge = RecordingBridge()
    plan = build_sync_plan(sample_repo_status())

    apply_sync_plan(bridge, plan)

    assert len(bridge.master_rows) == 1
    assert bridge.master_rows[0]["key"] == SNAPSHOT_KEY
    assert len(bridge.tasks) == 2
    assert bridge.tasks[0]["task_id"] == "repo_current_commerce"


def test_build_sync_plan_requires_fingerprint() -> None:
    payload = sample_repo_status()
    payload["source_fingerprint_sha256"] = ""

    try:
        build_sync_plan(payload)
    except ValueError as exc:
        assert "source_fingerprint_sha256" in str(exc)
    else:
        raise AssertionError("expected missing fingerprint to fail")
