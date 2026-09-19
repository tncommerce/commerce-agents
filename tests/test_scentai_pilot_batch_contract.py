from __future__ import annotations

from scripts.validate_scentai_pilot_batch_contract import (
    validate_contract,
)


def valid_sources() -> tuple[dict, dict, dict, dict, dict]:
    manifest = {
        "campaign_id": "launch01",
        "channels": ["tiktok", "instagram", "youtube"],
        "pilots": [
            {
                "content_id": "pilot",
                "landing_path": "/duftfinder",
                "target_duration_seconds": 30,
                "scenes": [
                    {
                        "seconds": "0-30",
                    }
                ],
                "price_snapshot": {
                    "reverify_before_publish": True,
                },
            }
        ],
    }
    jobs = {
        "jobs": [
            {
                "content_id": "pilot",
                "expected_duration_seconds": 30,
                "subtitle_path": (
                    "examples/retail/data/"
                    "scentai_pilot_batch_01_subtitles/pilot.srt"
                ),
                "price_recheck_required": True,
            }
        ]
    }
    subtitles = {
        "items": [
            {
                "content_id": "pilot",
                "segments": [
                    {
                        "start": 0,
                        "end": 30,
                        "text": "Test",
                    }
                ],
            }
        ]
    }
    links = {
        "links": [
            {
                "campaign_id": "launch01",
                "content_id": "pilot",
                "channel": channel,
                "landing_path": "/duftfinder",
                "url": (
                    "https://example.com/duftfinder?"
                    f"src={channel}&cmp=launch01&content=pilot"
                ),
            }
            for channel in ("tiktok", "instagram", "youtube")
        ]
    }
    social = {
        "posts": [
            {
                "content_id": "pilot",
                "tiktok": {},
                "instagram": {},
                "youtube": {},
            }
        ]
    }
    return manifest, jobs, subtitles, links, social


def test_valid_pilot_contract_passes() -> None:
    report = validate_contract(*valid_sources())

    assert report["valid"] is True
    assert report["issues"] == []
    assert report["summary"]["tracked_links"] == 3


def test_duration_drift_is_detected() -> None:
    manifest, jobs, subtitles, links, social = valid_sources()
    subtitles["items"][0]["segments"][0]["end"] = 29

    report = validate_contract(
        manifest,
        jobs,
        subtitles,
        links,
        social,
    )

    assert report["valid"] is False
    assert "pilot:subtitle_duration_mismatch" in report["issues"]


def test_price_recheck_drift_is_detected() -> None:
    manifest, jobs, subtitles, links, social = valid_sources()
    jobs["jobs"][0]["price_recheck_required"] = False

    report = validate_contract(
        manifest,
        jobs,
        subtitles,
        links,
        social,
    )

    assert report["valid"] is False
    assert "pilot:price_recheck_flag_mismatch" in report["issues"]


def test_tracking_channel_gap_is_detected() -> None:
    manifest, jobs, subtitles, links, social = valid_sources()
    links["links"] = [
        row
        for row in links["links"]
        if row["channel"] != "youtube"
    ]

    report = validate_contract(
        manifest,
        jobs,
        subtitles,
        links,
        social,
    )

    assert report["valid"] is False
    assert "pilot:tracked_link_count_mismatch" in report["issues"]
    assert "pilot:tracked_link_channels_mismatch" in report["issues"]
