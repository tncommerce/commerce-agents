from __future__ import annotations

from scripts.build_scentai_jarvis_master_status import (
    build_master_status,
)


def test_master_selects_content_when_commerce_waits_external() -> None:
    commerce = {
        "overall_state": "waiting_external_affiliate_decision",
        "next_action": "await_affiliate_program_decision",
        "next_action_class": "auto_allowed",
        "user_approval_required_now": False,
        "blockers": ["affiliate_pending"],
    }
    content = {
        "overall_state": "visual_preview_generation_pending",
        "next_action": "render_and_verify_visual_preview_mp4s",
        "next_action_class": "auto_allowed",
        "user_approval_required_now": False,
        "blockers": ["visual_previews_missing"],
    }
    pipeline = {
        "release_count": 3,
        "current_release_id": "SCENTAI-RELEASE-01",
        "pipeline_state": "blocked_on_current_release",
    }

    report = build_master_status(
        commerce,
        content,
        pipeline,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert report["overall_state"] == "work_available"
    assert report["active_domain"] == "content"
    assert report["next_action"] == ("render_and_verify_visual_preview_mp4s")
    assert report["user_approval_required_now"] is False


def test_master_prioritizes_explicit_user_approval() -> None:
    commerce = {
        "overall_state": "waiting_external_affiliate_decision",
        "next_action": "await_affiliate_program_decision",
        "next_action_class": "auto_allowed",
        "user_approval_required_now": False,
        "blockers": [],
    }
    content = {
        "overall_state": "mobile_content_review_pending",
        "next_action": "perform_mobile_content_review",
        "next_action_class": "approval_required",
        "user_approval_required_now": True,
        "blockers": [],
    }

    report = build_master_status(
        commerce,
        content,
        {},
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert report["overall_state"] == "user_approval_required"
    assert report["active_domain"] == "content"
    assert report["user_approval_required_now"] is True
    assert report["safety"]["automatic_social_publish_allowed"] is False
