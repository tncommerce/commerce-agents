"""Platform-specific delivery policy; fake probe data is not production evidence."""

import hashlib
import json
from types import SimpleNamespace

import pytest
from scripts import dufynd_publish_orchestrator as mod


@pytest.fixture
def media_probe(tmp_path, monkeypatch):
    path = tmp_path / "fixture.mp4"
    path.write_bytes(b"explicitly synthetic probe fixture")
    state = dict(bitrate=193, lufs=-14, peak=-5.65, decode_error=False, duration=10.08)
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if "-af" in args:
            return SimpleNamespace(
                returncode=int(state["decode_error"]),
                stderr=json.dumps({"input_i": str(state["lufs"]), "input_tp": str(state["peak"])}),
            )
        if "s16le" in args:
            return SimpleNamespace(returncode=0, stdout=b"\0" * round(state["duration"] * 16000))
        return SimpleNamespace(
            stderr=(
                "Duration: 00:00:10.08\n"
                "Stream #0:0 Video: h264, yuv420p, 1080x1920, 24 fps\n"
                f"Stream #0:1 Audio: aac, 48000 Hz, stereo, {state['bitrate']} kb/s\n"
            )
        )

    monkeypatch.setattr(mod.subprocess, "run", run)
    return path, state, calls


@pytest.mark.parametrize("platform", ["youtube", "tiktok"])
def test_recommended_bitrate_is_not_a_shared_hard_limit(media_probe, platform):
    path, _, calls = media_probe
    result = mod.audit_media(path, ffmpeg="fixture", platform=platform)
    assert result["audio_bitrate_recommendation_exceeded"] is True
    assert result["publication_authorized"] is False
    assert result["audible_preview_verified"] is False
    assert result["quality_score"] is None
    assert len(calls) == 3
    assert all(str(path) == cmd[cmd.index("-i") + 1] for cmd in calls)
    assert all(cmd[-1] == "-" for cmd in calls[1:])  # no media output file


def test_instagram_default_profile_still_blocks_high_bitrate(media_probe):
    path, _, calls = media_probe
    with pytest.raises(mod.PublishBlocked, match="audio_bitrate"):
        mod.audit_media(path, ffmpeg="fixture")
    assert len(calls) == 1


@pytest.mark.parametrize("platform", ["youtube", "tiktok"])
def test_preservation_exception_is_bound_to_exact_bytes(media_probe, monkeypatch, platform):
    path, state, _ = media_probe
    state["lufs"] = -20.89
    with pytest.raises(mod.PublishBlocked, match="internal_loudness"):
        mod.audit_media(path, ffmpeg="fixture", platform=platform)
    monkeypatch.setattr(
        mod, "PRESERVED_ELIXIR_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    result = mod.audit_media(path, ffmpeg="fixture", platform=platform)
    assert result["owner_preserved_audio_evidence_ref"] == mod.PRESERVED_ELIXIR_EVIDENCE
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(mod.PublishBlocked, match="internal_loudness"):
        mod.audit_media(path, ffmpeg="fixture", platform=platform)


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"lufs": "-inf"}, "silent_or_unsafe"),
        ({"lufs": "nan"}, "silent_or_unsafe"),
        ({"lufs": -20.89, "peak": 0.1}, "silent_or_unsafe"),
        ({"lufs": -25}, "internal_loudness"),
        ({"decode_error": True}, "full_av_decode"),
        ({"duration": 9}, "duration_mismatch"),
        ({"bitrate": 0}, "audio_bitrate"),
    ],
)
def test_exact_hash_does_not_bypass_decode_duration_or_peak_checks(
    media_probe, monkeypatch, change, reason
):
    path, state, _ = media_probe
    monkeypatch.setattr(
        mod, "PRESERVED_ELIXIR_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    state.update(change)
    with pytest.raises(mod.PublishBlocked, match=reason):
        mod.audit_media(path, ffmpeg="fixture", platform="youtube")


def test_unknown_platform_fails_closed_before_probe(media_probe):
    path, _, calls = media_probe
    with pytest.raises(mod.PublishBlocked, match="unsupported_media_platform"):
        mod.audit_media(path, ffmpeg="fixture", platform="unknown")
    assert not calls
