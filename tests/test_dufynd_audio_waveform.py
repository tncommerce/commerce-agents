"""Real decoded PCM, including AAC transcoding; no social publication."""

import math
import os
import shutil
import struct
import subprocess
import wave

import pytest
from scripts.dufynd_publish_orchestrator import PublishBlocked, compare_audio


@pytest.fixture
def tracks(tmp_path):
    ffmpeg = os.environ.get("DUFYND_TEST_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is required for real codec regression")
    values = [
        int(9000 * math.sin(2 * math.pi * (220 * i / 8000 + 15 * (i / 8000) ** 2)))
        for i in range(96000)
    ]

    def write(name, samples):
        path = tmp_path / name
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(struct.pack("<" + "h" * len(samples), *samples))
        return path

    return ffmpeg, write, values


def test_real_aac_transcode_retains_waveform(tracks, tmp_path):
    ffmpeg, write, values = tracks
    source = write("source.wav", values)
    encoded = tmp_path / "reencoded.m4a"
    subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(source), "-c:a", "aac", "-b:a", "96k", str(encoded)],
        check=True,
        timeout=30,
    )
    result = compare_audio(source, encoded, ffmpeg=ffmpeg)
    assert result["audio_match_verified"] is True
    assert result["audible_playback_verified"] is False
    assert abs(result["alignment_seconds"]) <= 0.08


@pytest.mark.parametrize("damage", ["muted", "shifted", "replaced", "truncated"])
def test_real_muting_replacement_shift_and_truncation_block(tracks, damage):
    ffmpeg, write, values = tracks
    source = write("source.wav", values)
    damaged = {
        "muted": [0] * len(values),
        "shifted": [0] * 1280 + values[:-1280],
        "replaced": [int(9000 * math.sin(2 * math.pi * 123 * i / 8000)) for i in range(96000)],
        "truncated": values[:-8000],
    }[damage]
    with pytest.raises(PublishBlocked):
        compare_audio(source, write("damaged.wav", damaged), ffmpeg=ffmpeg)
