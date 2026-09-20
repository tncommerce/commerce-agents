from __future__ import annotations

from scripts.build_scentai_content_pipeline_status import (
    build_content_pipeline_status,
)


def test_content_pipeline_prioritizes_first_unrendered_batch() -> None:
    batch01 = {
        "campaign_id": "launch01",
        "overall_state": "visual_preview_generation_pending",
        "next_action": "render_and_verify_visual_preview_mp4s",
        "next_action_class": "auto_allowed",
        "user_approval_required_now": False,
        "blockers": ["visual_preview_mp4s_incomplete"],
        "summary": {
            "pilots": 5,
            "tracked_links_ready": 15,
            "social_copy_ready": 5,
            "visual_preview_mp4s_ready": 0,
            "final_video_renders_ready": 0,
        },
    }
    batch02 = {
        **batch01,
        "summary": {
            **batch01["summary"],
            "tracked_links_ready": 15,
        },
    }

    report = build_content_pipeline_status(
        [batch01, batch02],
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert report["system"] == "DUFYND"
    assert report["batch_count"] == 2
    assert report["total_pilots"] == 10
    assert report["current_batch_id"] == "pilot_batch_01"
    assert report["production_parallel_allowed"] is True
    assert report["totals"]["tracked_links_ready"] == 30
    assert report["totals"]["final_video_renders_ready"] == 0
