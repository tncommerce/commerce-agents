from __future__ import annotations

from scripts.build_scentai_media_generation_queue import build_queue


def test_media_queue_is_provider_neutral_and_publish_safe() -> None:
    providers = {
        "active_provider": None,
        "providers": [
            {
                "provider_id": "local_ffmpeg",
                "type": "local_toolchain",
                "status": "implemented",
            },
            {
                "provider_id": "external",
                "type": "external_connector",
                "status": "not_connected",
            },
        ],
    }
    batches = [
        {
            "batch_id": "pilot_batch_01",
            "manifest": {
                "campaign_id": "launch01",
                "pilots": [
                    {
                        "content_id": "pilot",
                        "voiceover": "Script",
                        "product_ids": ["SC-1"],
                        "landing_path": "/duftfinder",
                    }
                ],
            },
            "jobs": {
                "jobs": [
                    {
                        "content_id": "pilot",
                        "production_order": 1,
                        "state": "visual_preview_pending",
                        "expected_duration_seconds": 30,
                        "visual_preview_path": "preview.mp4",
                        "voiceover_path": "voice.wav",
                        "subtitle_path": "subtitle.srt",
                        "final_render_path": "final.mp4",
                    }
                ]
            },
            "voiceover": {
                "pilots": [
                    {
                        "content_id": "pilot",
                        "script": "Approved script",
                    }
                ]
            },
        }
    ]

    report = build_queue(
        providers,
        batches,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert report["summary"]["jobs"] == 1
    assert report["summary"]["batches"] == 1
    assert report["summary"]["local_visual_render_available"] is True
    assert report["summary"]["voice_synthesis_provider_connected"] is False
    assert report["safety"]["automatic_publish_allowed"] is False

    job = report["jobs"][0]
    assert job["script"] == "Approved script"
    assert job["provider_may_publish"] is False
    assert job["publish_action_class"] == "approval_required"
