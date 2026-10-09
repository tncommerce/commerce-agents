"""Exact-asset embedded-audio publishing. No external calls from prepare or CLI.

The connector adapter uses the already connected Metricool tool. This module
does not require buying API access. External tool/UI calls remain outside it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from array import array
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge


class PublishBlocked(RuntimeError):
    pass


def audit_media(path: Path, *, ffmpeg: str) -> dict:
    """Full A/V decode and measured loudness; NOT a listening or visual score."""
    if not path.is_file() or path.stat().st_size > 300_000_000:
        raise PublishBlocked("media_missing_or_too_large")
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    ).stderr
    video = next((s for s in probe.splitlines() if "Video:" in s and "Stream #" in s), "")
    audio = next((s for s in probe.splitlines() if "Audio:" in s and "Stream #" in s), "")
    dims = re.search(r"\b(\d{3,5})x(\d{3,5})\b", video)
    fps = re.search(r"([\d.]+) fps", video)
    duration = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe)
    if not dims or not fps or not duration:
        raise PublishBlocked("video_probe_failed")
    width, height = map(int, dims.groups())
    seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3])
    rate = float(fps[1])
    if width < 1080 or height < 1920 or width * 16 != height * 9:
        raise PublishBlocked("video_requires_1080x1920_9_16")
    if not 8 <= seconds <= 15 or not 24 <= rate <= 60:
        raise PublishBlocked("duration_or_frame_rate_invalid")
    if "Video: h264" not in video or "yuv420p" not in video:
        raise PublishBlocked("h264_yuv420p_required")
    if "Audio: aac" not in audio:
        raise PublishBlocked("aac_audio_required")
    audio_rate = re.search(r"(\d+) kb/s", audio)
    sample_rate = re.search(r"(\d+) Hz", audio)
    if (
        not audio_rate
        or int(audio_rate[1]) > 128
        or not sample_rate
        or int(sample_rate[1]) not in {44100, 48000}
    ):
        raise PublishBlocked("audio_bitrate_or_sample_rate_invalid")
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-v",
            "info",
            "-xerror",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-af",
            "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        raise PublishBlocked("full_av_decode_failed")
    pcm = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-xerror",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
    audio_seconds = len(pcm.stdout) / 16000
    if pcm.returncode or abs(audio_seconds - seconds) > 0.08:
        raise PublishBlocked("audio_video_duration_mismatch")
    matches = re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    if not matches:
        raise PublishBlocked("loudness_measurement_missing")
    loudness = json.loads(matches[-1])
    integrated, peak = float(loudness["input_i"]), float(loudness["input_tp"])
    if (
        not all(math.isfinite(v) for v in (integrated, peak))
        or not -20 <= integrated <= -10
        or peak > -1
    ):
        raise PublishBlocked("silent_or_unsafe_loudness")
    return {
        "asset_sha256": digest,
        "width_px": width,
        "height_px": height,
        "fps": rate,
        "duration_seconds": seconds,
        "audio_codec": "aac",
        "audio_kbps": int(audio_rate[1]),
        "audio_sample_rate": int(sample_rate[1]),
        "decoded_audio_seconds": audio_seconds,
        "integrated_lufs": integrated,
        "true_peak_dbtp": peak,
        "full_decode_passed": True,
        "audible_preview_verified": False,
        "genuine_motion_verified": False,
        "quality_score": None,
        "publication_authorized": False,
    }


def compare_audio(source: Path, platform_output: Path, *, ffmpeg: str) -> dict:
    """Measure waveform correlation and alignment after platform transcoding.

    Mono 8 kHz removes codec/container differences. Search +/-250 ms. Reject
    muting, replaced music, changed duration and >80 ms displacement. A device
    listening check is still required for the independently reviewed output.
    """
    tracks = []
    for path in (source, platform_output):
        decoded = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-nostdin",
                "-xerror",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "8000",
                "-f",
                "s16le",
                "-",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if decoded.returncode or not decoded.stdout or len(decoded.stdout) > 500_000:
            raise PublishBlocked("platform_audio_decode_failed")
        samples = array("h")
        samples.frombytes(decoded.stdout)
        tracks.append(samples)
    a, b = tracks
    if abs(len(a) - len(b)) / 8000 > 0.08 or len(a) < 64000:
        raise PublishBlocked("platform_audio_duration_changed")
    # 5000 samples spread across the full track, excluding alignment margins.
    stride = max(1, (len(a) - 4000) // 5000)
    indices = range(2000, min(len(a), len(b)) - 2000, stride)
    av = [a[i] for i in indices]
    am = sum(av) / len(av)
    centered = [v - am for v in av]
    energy = sum(v * v for v in centered)
    if energy < len(av) * 100:
        raise PublishBlocked("source_audio_silent")
    best, lag = -1.0, 0
    for offset in range(-2000, 2001, 8):
        bv = [b[i + offset] for i in indices]
        bm = sum(bv) / len(bv)
        bv = [v - bm for v in bv]
        be = sum(v * v for v in bv)
        if be < len(bv) * 100:
            continue
        correlation = sum(x * y for x, y in zip(centered, bv, strict=True)) / math.sqrt(energy * be)
        if correlation > best:
            best, lag = correlation, offset
    if best < 0.90 or abs(lag) / 8000 > 0.08:
        raise PublishBlocked("platform_audio_changed_or_shifted")
    return {
        "audio_match_verified": True,
        "timing_verified": True,
        "waveform_correlation": round(best, 5),
        "alignment_seconds": lag / 8000,
        "audible_playback_verified": False,
    }


def connector_arguments(packet: dict) -> dict:
    """Use the live Swagger media ARRAY; no guessed mediaId-only payload."""
    platform = packet["platform"]
    if platform not in {"instagram", "tiktok"} or packet["brand_id"] != "7182186":
        raise PublishBlocked("wrong_platform_or_brand")
    parsed = urlsplit(packet["uri"])
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PublishBlocked("public_https_media_required")
    if packet["asset_sha256"] not in parsed.path:
        raise PublishBlocked("content_addressed_media_required")
    desired = datetime.fromisoformat(packet["requested_at"].replace("Z", "+00:00"))
    if desired.tzinfo is None or desired <= datetime.now(UTC):
        raise PublishBlocked("requested_time_missing_or_past")
    info = {
        "text": packet["caption"],
        "providers": [{"network": platform}],
        "media": [packet["uri"]],
        "autoPublish": True,
        "draft": False,
        "saveExternalMediaFiles": True,
        "shortener": False,
        "publicationDate": {
            "dateTime": desired.astimezone(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%dT%H:%M:%S"),
            "timezone": "Europe/Berlin",
        },
    }
    if platform == "instagram":
        info["instagramData"] = {"type": "REEL", "autoPublish": True, "showReelOnFeed": True}
    else:
        # Deliberately no music/autoAddMusic that could replace the frozen soundtrack.
        info["tiktokData"] = {"autoAddMusic": False, "commercialContentOwnBrand": True}
    return {
        "blogId": "7182186",
        "date": desired.isoformat(),
        "info": json.dumps(info, ensure_ascii=False),
        "mediaFiles": [packet["uri"]],
    }


def schedule_receipt(response: dict, packet: dict) -> dict:
    """Accept only a complete provider echo; incomplete/rewritten media is uncertain."""
    if response.get("isError"):
        raise PublishBlocked("provider_error")
    data = response.get("data", response)
    if not isinstance(data, dict) or not data.get("id"):
        raise PublishBlocked("provider_receipt_incomplete")
    networks = [p.get("network") for p in data.get("providers", [])]
    if networks != [packet["platform"]] or data.get("text") != packet["caption"]:
        raise PublishBlocked("provider_target_or_caption_changed")
    if data.get("media") != [packet["uri"]]:
        raise PublishBlocked("provider_media_requires_byte_verification")
    expected = json.loads(connector_arguments(packet)["info"])
    for key in ("publicationDate", "autoPublish", "draft"):
        if data.get(key) != expected[key]:
            raise PublishBlocked("provider_schedule_changed")
    if packet["platform"] == "instagram":
        ig = data.get("instagramData", {})
        if (
            ig.get("type") != "REEL"
            or ig.get("autoPublish") is not True
            or ig.get("audioConfiguration")
        ):
            raise PublishBlocked("provider_audio_or_reel_configuration_changed")
    elif data.get("tiktokData", {}).get("autoAddMusic") is not False or data.get(
        "tiktokData", {}
    ).get("music"):
        raise PublishBlocked("provider_audio_configuration_changed")
    return {
        "provider_post_id": str(data["id"]),
        "asset_sha256": packet["asset_sha256"],
        "exact_media_uri_echoed": True,
        "provider_ingested_bytes_verified": False,
        "publication_verified": False,
    }


class PublishOrchestrator:
    def __init__(
        self,
        bridge: DufyndJarvisBridge,
        *,
        ffmpeg: str,
        metricool_schedule: Callable[[dict], dict] | None = None,
    ):
        self.bridge, self.ffmpeg, self.metricool_schedule = bridge, ffmpeg, metricool_schedule

    def prepare(self, asset_id: str, path: Path) -> tuple[dict, dict]:
        packet = self.bridge._rpc("read_dufynd_publish_packet_v1", {"p_asset_id": asset_id})
        if packet.get("ready") is not True:
            raise PublishBlocked(packet.get("reason", "packet_not_ready"))
        report = audit_media(path, ffmpeg=self.ffmpeg)
        if report["asset_sha256"] != packet["asset_sha256"]:
            raise PublishBlocked("local_asset_bytes_changed")
        connector_arguments(packet)
        return packet, report

    def dispatch(
        self,
        asset_id: str,
        path: Path,
        decision_id: str,
        *,
        verify_hosted_media: Callable[[str, str], bool],
    ) -> dict:
        if self.metricool_schedule is None:
            raise PublishBlocked("connected_metricool_adapter_required")
        packet, report = self.prepare(asset_id, path)
        # Adapter must download and hash the hosted bytes, with safe origin/redirect
        # policy. An immutable storage policy is also required by the SQL gate.
        if verify_hosted_media(packet["uri"], report["asset_sha256"]) is not True:
            raise PublishBlocked("hosted_asset_bytes_changed")
        args = connector_arguments(packet)
        reservation = self.bridge._rpc(
            "reserve_dufynd_publish_v1",
            {
                "p_asset_id": asset_id,
                "p_revision_fingerprint": packet["revision_fingerprint"],
                "p_asset_sha256": report["asset_sha256"],
                "p_decision_id": decision_id,
            },
        )
        if reservation.get("reserved") is not True:
            raise PublishBlocked(reservation.get("reason", "reservation_denied"))
        dispatch_id = reservation["dispatch_id"]
        # Durable reservation BEFORE the irreversible call. Never auto-retry an
        # exception, missing receipt or process crash, even if the provider accepted.
        try:
            if reservation.get("packet") != packet:
                raise PublishBlocked("reserved_packet_changed")
            receipt = schedule_receipt(self.metricool_schedule(args), packet)
        except Exception:
            self.bridge._rpc(
                "record_dufynd_publish_receipt_v1",
                {
                    "p_dispatch_id": dispatch_id,
                    "p_state": "outcome_unknown",
                    "p_receipt": {"reason": "reconcile_provider_before_any_retry"},
                },
            )
            raise PublishBlocked("outcome_unknown_no_retry") from None
        saved = self.bridge._rpc(
            "record_dufynd_publish_receipt_v1",
            {
                "p_dispatch_id": dispatch_id,
                "p_state": "scheduled",
                "p_receipt": receipt,
            },
        )
        if saved is not True:
            raise PublishBlocked("receipt_not_saved_no_retry")
        return {
            "dispatch_id": dispatch_id,
            "stage": "SCHEDULED_AWAITING_PUBLIC_PLAYBACK",
            **receipt,
        }


def verify_publication(packet: dict, provider: dict, playback: dict) -> dict:
    """Require independent actual platform playback evidence, not a schedule.

    Platform transcoding changes hashes: playback must identify the platform
    output digest AND the reviewed source digest, with measured audio-match/timing
    evidence. This checks supplied evidence, it does not invent a listener.
    """
    url = urlsplit(str(provider.get("publicUrl", "")))
    hosts = {
        "instagram": {"www.instagram.com", "instagram.com"},
        "tiktok": {"www.tiktok.com", "tiktok.com"},
    }
    expected = packet["platform"]
    if (
        provider.get("status") != "PUBLISHED"
        or provider.get("network") != expected
        or not provider.get("id")
        or url.scheme != "https"
        or url.hostname not in hosts[expected]
    ):
        raise PublishBlocked("actual_platform_publication_required")
    if (
        playback.get("source_sha256") != packet["asset_sha256"]
        or playback.get("platform_post_id") != str(provider["id"])
        or playback.get("public_url") != provider["publicUrl"]
    ):
        raise PublishBlocked("public_playback_binding_invalid")
    for key in (
        "full_decode_passed",
        "audible_playback_verified",
        "timing_verified",
        "audio_match_verified",
    ):
        if playback.get(key) is not True:
            raise PublishBlocked("public_audio_playback_not_verified")
    if (
        not re.fullmatch(r"[a-f0-9]{64}", str(playback.get("platform_output_sha256", "")))
        or not playback.get("checker_id")
        or playback["checker_id"] == packet.get("maker_id")
        or not playback.get("evidence_ref")
    ):
        raise PublishBlocked("independent_public_playback_evidence_required")
    return {
        "publication_verified": True,
        "platform_post_id": str(provider["id"]),
        "source_sha256": packet["asset_sha256"],
        "evidence_ref": playback["evidence_ref"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline file audit; no approval or scheduling.")
    parser.add_argument("media", type=Path)
    parser.add_argument("--ffmpeg", required=True)
    args = parser.parse_args()
    try:
        result = audit_media(args.media, ffmpeg=args.ffmpeg)
    except (PublishBlocked, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(json.dumps({"passed": False, "reason": str(exc), "publication_authorized": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
