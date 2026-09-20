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

    assert report["system"] == "DUFYND"
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


def test_master_uses_high_end_rnd_strategy_over_legacy_voiceover() -> None:
    commerce = {
        "overall_state": "waiting_external_affiliate_decision",
        "next_action": "await_affiliate_program_decision",
        "next_action_class": "auto_allowed",
        "user_approval_required_now": False,
        "blockers": ["affiliate_pending"],
    }
    content = {
        "overall_state": "voiceover_pending",
        "next_action": "record_or_generate_voiceover_audio",
        "next_action_class": "approval_required",
        "user_approval_required_now": True,
        "blockers": ["voiceover_audio_pending"],
    }
    content_pipeline = {
        "batch_count": 3,
        "total_pilots": 15,
        "current_batch_id": None,
        "pipeline_state": "legacy_batches_on_hold_for_high_end_rnd",
        "active_track": "high_end_rnd",
        "legacy_pilot_batches": "hold",
        "next_action": "continue_high_end_rnd_preparation",
        "next_action_class": "auto_allowed",
        "user_approval_required_now": False,
        "production_parallel_allowed": False,
    }

    report = build_master_status(
        commerce,
        content,
        {},
        generated_at="2026-09-20T17:30:00+00:00",
        content_pipeline=content_pipeline,
    )

    assert report["overall_state"] == "work_available"
    assert report["active_domain"] == "content"
    assert report["next_action"] == "continue_high_end_rnd_preparation"
    assert report["user_approval_required_now"] is False
    assert report["content_pipeline"]["active_track"] == "high_end_rnd"
    assert report["content_pipeline"]["legacy_pilot_batches"] == "hold"
