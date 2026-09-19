from __future__ import annotations

from scripts.render_scentai_pilot_final import (
    evaluate_final_render,
    evaluate_inputs,
)


def job(
    subtitle_timing_status: str = "draft_not_conformed",
) -> dict:
    return {
        "content_id": "pilot",
        "expected_duration_seconds": 30,
        "duration_tolerance_seconds": 2,
        "subtitle_timing_status": subtitle_timing_status,
    }


def visual_summary() -> dict:
    return {
        "duration_seconds": 30.0,
        "video_codec": "h264",
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "audio_codec": None,
        "has_video": True,
        "has_audio": False,
    }


def voiceover_summary() -> dict:
    return {
        "duration_seconds": 28.0,
        "video_codec": None,
        "width": None,
        "height": None,
        "fps": None,
        "audio_codec": "pcm_s16le",
        "has_video": False,
        "has_audio": True,
    }


def test_draft_subtitle_timing_blocks_final_render() -> None:
    report = evaluate_inputs(
        job(),
        visual_exists=True,
        voiceover_exists=True,
        subtitle_exists=True,
        visual_summary=visual_summary(),
        voiceover_summary=voiceover_summary(),
    )

    assert report["ready_for_render"] is False
    assert "subtitle_timing_not_conformed" in report["blockers"]


def test_conformed_subtitles_and_valid_inputs_are_render_ready() -> None:
    report = evaluate_inputs(
        job("conformed_to_voiceover"),
        visual_exists=True,
        voiceover_exists=True,
        subtitle_exists=True,
        visual_summary=visual_summary(),
        voiceover_summary=voiceover_summary(),
    )

    assert report["ready_for_render"] is True
    assert report["blockers"] == []


def test_voiceover_longer_than_manifest_tolerance_is_blocked() -> None:
    audio = voiceover_summary()
    audio["duration_seconds"] = 33.0

    report = evaluate_inputs(
        job("conformed_to_voiceover"),
        visual_exists=True,
        voiceover_exists=True,
        subtitle_exists=True,
        visual_summary=visual_summary(),
        voiceover_summary=audio,
    )

    assert report["ready_for_render"] is False
    assert "voiceover_too_long_for_manifest" in report["blockers"]


def test_final_render_technical_qa_passes_expected_contract() -> None:
    report = evaluate_final_render(
        {
            "duration_seconds": 30.0,
            "video_codec": "h264",
            "audio_codec": "aac",
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
            "has_audio": True,
        },
        expected_duration_seconds=30,
        tolerance_seconds=2,
    )

    assert report["technical_qa_passed"] is True
    assert report["blockers"] == []


def test_final_render_technical_qa_rejects_wrong_contract() -> None:
    report = evaluate_final_render(
        {
            "duration_seconds": 30.0,
            "video_codec": "vp9",
            "audio_codec": None,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "has_audio": False,
        },
        expected_duration_seconds=30,
        tolerance_seconds=2,
    )

    assert report["technical_qa_passed"] is False
    assert "final_video_codec_not_h264" in report["blockers"]
    assert "final_audio_codec_not_aac" in report["blockers"]
    assert "final_width_not_1080" in report["blockers"]
    assert "final_height_not_1920" in report["blockers"]
    assert "final_fps_not_30" in report["blockers"]
    assert "final_audio_missing" in report["blockers"]
