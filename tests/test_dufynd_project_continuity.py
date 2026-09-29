from __future__ import annotations

from scripts.dufynd_project_continuity import (
    bootstrap_instruction,
    build_bootstrap_context,
    build_checkpoint_row,
)


def sample_repo_status(fingerprint: str = "abc123") -> dict:
    return {
        "generated_at": "2026-09-29T20:00:00+00:00",
        "source_fingerprint_sha256": fingerprint,
        "overall_state": "work_available",
        "active_domain": "commerce",
        "domains": {
            "commerce": {
                "domain": "commerce",
                "execution_state": "work_available",
                "next_action": "audit_catalog",
                "next_action_class": "auto_allowed",
                "blockers": [],
            },
            "content": {
                "domain": "content",
                "execution_state": "manual_step_pending",
                "next_action": "reconcile_social",
                "next_action_class": "manual_state_reconciliation_required",
                "blockers": [],
            },
        },
    }


def sample_contract() -> dict:
    return {"version": "3.0"}


def live_context(
    snapshot_fingerprint: str = "abc123",
    checkpoint_fingerprint: str = "abc123",
) -> dict:
    return {
        "master_status": [
            {
                "key": "jarvis.repo_state_snapshot",
                "last_verified_at": "2026-09-29T20:00:00+00:00",
                "value": {
                    "generated_at": "2026-09-29T20:00:00+00:00",
                    "source_fingerprint_sha256": snapshot_fingerprint,
                },
            },
            {
                "key": "continuity.checkpoint.tech",
                "last_verified_at": "2026-09-29T20:01:00+00:00",
                "value": {
                    "summary": "Tech work continues",
                    "completed": ["A"],
                    "in_progress": ["B"],
                    "blocked": [],
                    "waiting_approval": [],
                    "next_safe_action": "B",
                    "source_fingerprint_sha256": checkpoint_fingerprint,
                    "repo_head": "deadbeef",
                },
            },
        ]
    }


def queue() -> dict:
    return {
        "safe_to_execute": [
            {
                "task_id": "tech_ready",
                "domain": "engineering",
                "status": "ready",
                "priority": 99,
                "title": "Fix tested UI issue",
                "requires_human_approval": False,
            },
            {
                "task_id": "commerce_ready",
                "domain": "commerce",
                "status": "ready",
                "priority": 100,
                "title": "Audit catalog",
                "requires_human_approval": False,
            },
            {
                "task_id": "content_ready",
                "domain": "content",
                "status": "ready",
                "priority": 90,
                "title": "Prepare content",
                "requires_human_approval": False,
            },
        ],
        "in_progress": [
            {
                "task_id": "jarvis_work",
                "domain": "jarvis",
                "status": "in_progress",
                "priority": 92,
                "title": "Harden orchestrator",
                "requires_human_approval": False,
            }
        ],
        "waiting_human_input": [
            {
                "task_id": "publish_content",
                "domain": "content",
                "status": "waiting_human_input",
                "priority": 100,
                "title": "Publish content",
                "requires_human_approval": True,
            }
        ],
        "waiting_external": [],
        "approval_required": [],
        "done_recent": [
            {
                "task_id": "tech_done",
                "domain": "engineering",
                "status": "done",
                "priority": 80,
                "title": "Prior patch",
            }
        ],
    }


def test_tech_bootstrap_is_domain_scoped_and_selects_safe_task() -> None:
    context = build_bootstrap_context(
        logical_domain="tech",
        repo_status=sample_repo_status(),
        contract=sample_contract(),
        live_context=live_context(),
        autonomy_queue=queue(),
        health={"state": "ok"},
        pending_decisions=[],
        repo_head="deadbeef",
    )

    assert context["freshness"]["stale"] is False
    assert context["work_allowed_after_live_git_check"] is True
    assert context["next_safe_action"]["task_id"] == "tech_ready"
    assert {row["task_id"] for row in context["active_tasks"]} == {"tech_ready"}
    assert context["checkpoint"]["fresh"] is True
    assert context["repository"]["live_git_verification_required"] is True


def test_content_bootstrap_does_not_leak_tech_task() -> None:
    context = build_bootstrap_context(
        logical_domain="content",
        repo_status=sample_repo_status(),
        contract=sample_contract(),
        live_context=live_context(),
        autonomy_queue=queue(),
        health={},
        pending_decisions=[],
    )

    ids = {row["task_id"] for row in context["active_tasks"] + context["blocked_or_waiting"]}
    assert "content_ready" in ids
    assert "publish_content" in ids
    assert "tech_ready" not in ids
    assert context["repo_domain_state"]["next_action"] == "reconcile_social"


def test_business_bootstrap_maps_commerce_state() -> None:
    context = build_bootstrap_context(
        logical_domain="business",
        repo_status=sample_repo_status(),
        contract=sample_contract(),
        live_context=live_context(),
        autonomy_queue=queue(),
        health={},
        pending_decisions=[],
    )

    assert context["next_safe_action"]["task_id"] == "commerce_ready"
    assert context["repo_domain_state"]["next_action"] == "audit_catalog"


def test_jarvis_bootstrap_selects_jarvis_task() -> None:
    context = build_bootstrap_context(
        logical_domain="jarvis",
        repo_status=sample_repo_status(),
        contract=sample_contract(),
        live_context=live_context(),
        autonomy_queue=queue(),
        health={},
        pending_decisions=[],
    )

    assert context["next_safe_action"]["task_id"] == "jarvis_work"
    assert {row["task_id"] for row in context["active_tasks"]} == {"jarvis_work"}
    assert context["repository"]["live_git_verification_required"] is True


def test_fingerprint_mismatch_fails_closed() -> None:
    context = build_bootstrap_context(
        logical_domain="tech",
        repo_status=sample_repo_status("new123"),
        contract=sample_contract(),
        live_context=live_context(
            snapshot_fingerprint="old123",
            checkpoint_fingerprint="old123",
        ),
        autonomy_queue=queue(),
        health={},
        pending_decisions=[],
    )

    assert context["freshness"]["stale"] is True
    assert context["work_allowed_after_live_git_check"] is False
    assert context["next_safe_action"] is None
    assert context["checkpoint"]["fresh"] is False
    assert "repo_state_snapshot_fingerprint_mismatch" in context["freshness"]["reasons"]


def test_checkpoint_head_mismatch_is_not_fresh() -> None:
    context = build_bootstrap_context(
        logical_domain="tech",
        repo_status=sample_repo_status(),
        contract=sample_contract(),
        live_context=live_context(),
        autonomy_queue=queue(),
        health={},
        pending_decisions=[],
        repo_head="new-head",
    )

    assert context["freshness"]["stale"] is False
    assert context["checkpoint"]["fingerprint_fresh"] is True
    assert context["checkpoint"]["head_fresh"] is False
    assert context["checkpoint"]["fresh"] is False


def test_offline_bootstrap_requires_live_control_plane() -> None:
    context = build_bootstrap_context(
        logical_domain="jarvis",
        repo_status=sample_repo_status(),
        contract=sample_contract(),
        autonomy_queue=queue(),
    )

    assert context["freshness"]["stale"] is True
    assert context["freshness"]["reasons"] == ["live_control_plane_not_loaded"]
    assert context["next_safe_action"] is None


def test_checkpoint_row_is_fingerprint_bound() -> None:
    row = build_checkpoint_row(
        logical_domain="tech",
        repo_status=sample_repo_status(),
        checkpoint={
            "summary": "Patch prepared",
            "completed": ["A"],
            "in_progress": ["B"],
            "blocked": [],
            "waiting_approval": [],
            "next_safe_action": "B",
            "evidence": ["PR #1"],
        },
        repo_head="deadbeef",
        verified_at="2026-09-29T20:05:00+00:00",
    )

    assert row["key"] == "continuity.checkpoint.tech"
    assert row["category"] == "continuity"
    assert row["value"]["source_fingerprint_sha256"] == "abc123"
    assert row["value"]["repo_head"] == "deadbeef"
    assert row["value"]["checkpointed_at"] == "2026-09-29T20:05:00+00:00"


def test_checkpoint_rejects_secret_like_fields() -> None:
    try:
        build_checkpoint_row(
            logical_domain="tech",
            repo_status=sample_repo_status(),
            checkpoint={
                "summary": "x",
                "completed": [],
                "in_progress": [],
                "blocked": [],
                "waiting_approval": [],
                "next_safe_action": None,
                "anthropic_api_key": "should-not-be-here",
            },
            repo_head="deadbeef",
        )
    except ValueError as exc:
        assert "forbidden secret-like fields" in str(exc)
    else:
        raise AssertionError("expected secret-like checkpoint field to be rejected")


def test_checkpoint_requires_all_work_state_fields() -> None:
    try:
        build_checkpoint_row(
            logical_domain="content",
            repo_status=sample_repo_status(),
            checkpoint={"summary": "x"},
            repo_head="deadbeef",
        )
    except ValueError as exc:
        assert "Checkpoint missing required fields" in str(exc)
    else:
        raise AssertionError("expected incomplete checkpoint to fail")


def test_bootstrap_instruction_is_short_and_actionable() -> None:
    text = bootstrap_instruction("tech")
    lines = text.splitlines()

    assert 3 <= len(lines) <= 6
    assert "scentai-mvp" in text
    assert "Live-HEAD/PR/CI" in text
    assert "fingerprint" in text


def test_global_context_can_see_cross_domain_tasks() -> None:
    context = build_bootstrap_context(
        logical_domain="global",
        repo_status=sample_repo_status(),
        contract=sample_contract(),
        live_context=live_context(),
        autonomy_queue=queue(),
        health={},
        pending_decisions=[{"decision_id": "d1", "status": "pending"}],
    )

    ids = {row["task_id"] for row in context["active_tasks"]}
    assert {"tech_ready", "commerce_ready", "content_ready", "jarvis_work"} <= ids
    assert context["pending_decisions"][0]["decision_id"] == "d1"


def test_fresh_checkpoint_supplies_next_action_when_queue_has_no_domain_task() -> None:
    context = build_bootstrap_context(
        logical_domain="tech",
        repo_status=sample_repo_status(),
        contract=sample_contract(),
        live_context=live_context(),
        autonomy_queue={},
        health={},
        pending_decisions=[],
        repo_head="deadbeef",
    )

    assert context["freshness"]["stale"] is False
    assert context["checkpoint"]["fresh"] is True
    assert context["active_tasks"] == []
    assert context["next_safe_action"]["source"] == "checkpoint"
    assert context["next_safe_action"]["action"] == "B"


def test_stale_checkpoint_never_supplies_fallback_action() -> None:
    context = build_bootstrap_context(
        logical_domain="tech",
        repo_status=sample_repo_status("new123"),
        contract=sample_contract(),
        live_context=live_context(
            snapshot_fingerprint="old123",
            checkpoint_fingerprint="old123",
        ),
        autonomy_queue={},
        health={},
        pending_decisions=[],
        repo_head="deadbeef",
    )

    assert context["freshness"]["stale"] is True
    assert context["next_safe_action"] is None
