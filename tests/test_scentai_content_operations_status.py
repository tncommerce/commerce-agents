from __future__ import annotations

from scripts.build_scentai_content_operations_status import (
    build_content_operations_status,
)


def sources() -> tuple[dict, dict, dict, dict, dict, dict]:
    manifest = {
        "campaign_id": "launch01",
        "channels": ["tiktok", "instagram", "youtube"],
        "pilots": [
            {"content_id": "a"},
            {"content_id": "b"},
        ],
    }
    readiness = {
        "summary": {
            "product_assets_verified": 2,
            "product_assets_required": 2,
            "voiceover_scripts_ready": 2,
            "visual_preview_mp4s_ready": 0,
            "subtitle_timing_drafts_ready": 2,
            "tracked_links_ready": 6,
            "social_copy_ready": 2,
            "final_video_renders_ready": 0,
        }
    }
    jobs = {
        "jobs": [
            {
                "content_id": "a",
                "production_order": 1,
                "state": "visual_preview_pending",
                "subtitle_timing_status": "draft_not_conformed",
                "blockers": [
                    "visual_preview_mp4_missing",
                    "voiceover_file_missing",
                ],
                "price_recheck_required": False,
                "publish_action_class": "approval_required",
            },
            {
                "content_id": "b",
                "production_order": 2,
                "state": "visual_preview_pending",
                "subtitle_timing_status": "draft_not_conformed",
                "blockers": [
                    "visual_preview_mp4_missing",
                    "voiceover_file_missing",
                ],
                "price_recheck_required": True,
                "publish_action_class": "approval_required",
            },
        ]
    }
    subtitles = {
        "items": [
            {"content_id": "a"},
            {"content_id": "b"},
        ]
    }
    links = {
        "links": [
            {"content_id": cid, "channel": channel}
            for cid in ("a", "b")
            for channel in ("tiktok", "instagram", "youtube")
        ]
    }
    social_copy = {
        "items": [
            {"content_id": "a"},
            {"content_id": "b"},
        ]
    }
    return manifest, readiness, jobs, subtitles, links, social_copy


def test_content_control_plane_prioritizes_visual_previews() -> None:
    report = build_content_operations_status(
        *sources(),
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert report["overall_state"] == "visual_preview_generation_pending"
    assert report["next_action"] == ("render_and_verify_visual_preview_mp4s")
    assert report["user_approval_required_now"] is False
    assert report["summary"]["tracked_links_ready"] == 6
    assert report["consistency"]["manifest_job_ids_match"] is True


def test_content_control_plane_requires_human_for_voiceover_step() -> None:
    manifest, readiness, jobs, subtitles, links, social_copy = sources()
    readiness["summary"]["visual_preview_mp4s_ready"] = 2
    for row in jobs["jobs"]:
        row["state"] = "voiceover_pending"
        row["blockers"] = ["voiceover_file_missing"]

    report = build_content_operations_status(
        manifest,
        readiness,
        jobs,
        subtitles,
        links,
        social_copy,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert report["overall_state"] == "voiceover_pending"
    assert report["next_action_class"] == "approval_required"
    assert report["user_approval_required_now"] is True
    assert report["safety"]["automatic_publish_allowed"] is False


def test_rendered_preview_files_override_stale_readiness(tmp_path) -> None:
    manifest, readiness, jobs, subtitles, links, social_copy = sources()
    for row in jobs["jobs"]:
        preview = tmp_path / f"{row['content_id']}-preview.mp4"
        preview.write_bytes(b"preview")
        row["visual_preview_path"] = str(preview)

    report = build_content_operations_status(
        manifest,
        readiness,
        jobs,
        subtitles,
        links,
        social_copy,
        generated_at="2026-09-20T16:00:00+00:00",
    )

    assert report["system"] == "DUFYND"
    assert report["summary"]["visual_preview_mp4s_ready"] == 2
    assert report["summary"]["visual_preview_source"] == "rendered_files"
    assert "visual_preview_mp4s_incomplete" not in report["blockers"]
    assert "pilot_visual_preview_generation_pending" not in report["blockers"]
    assert report["overall_state"] == "voiceover_pending"
    assert all(row["state"] == "voiceover_pending" for row in report["jobs"])
