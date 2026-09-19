from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_JOBS = Path(
    "examples/retail/data/scentai_pilot_batch_01_production_jobs.json"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_job(jobs_payload: dict, content_id: str) -> dict:
    for job in jobs_payload.get("jobs", []):
        if str(job.get("content_id") or "") == content_id:
            return job
    raise ValueError(f"Unknown content_id: {content_id}")


def probe_media(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration:"
                "stream=index,codec_type,codec_name,width,height,r_frame_rate"
            ),
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def parse_fraction(value: str | None) -> float | None:
    if not value:
        return None
    if "/" not in value:
        try:
            return float(value)
        except ValueError:
            return None
    numerator, denominator = value.split("/", maxsplit=1)
    try:
        den = float(denominator)
        if den == 0:
            return None
        return float(numerator) / den
    except ValueError:
        return None


def media_summary(probe: dict[str, Any]) -> dict[str, Any]:
    streams = probe.get("streams", [])
    video = next(
        (
            row
            for row in streams
            if row.get("codec_type") == "video"
        ),
        None,
    )
    audio = next(
        (
            row
            for row in streams
            if row.get("codec_type") == "audio"
        ),
        None,
    )

    duration_raw = probe.get("format", {}).get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError):
        duration = None

    return {
        "duration_seconds": duration,
        "video_codec": video.get("codec_name") if video else None,
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "fps": (
            parse_fraction(str(video.get("r_frame_rate")))
            if video
            else None
        ),
        "audio_codec": audio.get("codec_name") if audio else None,
        "has_video": video is not None,
        "has_audio": audio is not None,
    }


def evaluate_inputs(
    job: dict,
    *,
    visual_exists: bool,
    voiceover_exists: bool,
    subtitle_exists: bool,
    visual_summary: dict[str, Any] | None = None,
    voiceover_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected = float(job["expected_duration_seconds"])
    tolerance = float(job.get("duration_tolerance_seconds", 2.0))
    blockers: list[str] = []

    if not visual_exists:
        blockers.append("visual_preview_missing")
    if not voiceover_exists:
        blockers.append("voiceover_file_missing")
    if not subtitle_exists:
        blockers.append("subtitle_file_missing")

    subtitle_timing_status = str(
        job.get("subtitle_timing_status") or ""
    ).strip()
    if subtitle_timing_status != "conformed_to_voiceover":
        blockers.append("subtitle_timing_not_conformed")

    if visual_summary is not None:
        if visual_summary.get("width") != 1080:
            blockers.append("visual_width_not_1080")
        if visual_summary.get("height") != 1920:
            blockers.append("visual_height_not_1920")
        fps = visual_summary.get("fps")
        if fps is None or abs(float(fps) - 30.0) > 0.05:
            blockers.append("visual_fps_not_30")
        duration = visual_summary.get("duration_seconds")
        if (
            duration is None
            or abs(float(duration) - expected) > tolerance
        ):
            blockers.append("visual_duration_outside_tolerance")

    if voiceover_summary is not None:
        if not voiceover_summary.get("has_audio"):
            blockers.append("voiceover_has_no_audio_stream")
        duration = voiceover_summary.get("duration_seconds")
        if duration is None:
            blockers.append("voiceover_duration_unknown")
        elif float(duration) > expected + tolerance:
            blockers.append("voiceover_too_long_for_manifest")

    return {
        "content_id": job["content_id"],
        "ready_for_render": not blockers,
        "blockers": blockers,
        "expected_duration_seconds": expected,
        "duration_tolerance_seconds": tolerance,
        "visual_summary": visual_summary,
        "voiceover_summary": voiceover_summary,
        "write_action_class": "auto_allowed",
        "publish_action_class": "approval_required",
    }


def escape_subtitle_filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", "\\:")
    value = value.replace("'", "\\'")
    return value


def render_final(
    *,
    visual: Path,
    voiceover: Path,
    subtitles: Path,
    output: Path,
    duration_seconds: float,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subtitle_path = escape_subtitle_filter_path(subtitles)

    subtitle_filter = (
        f"subtitles='{subtitle_path}':"
        "force_style='"
        "FontName=DejaVu Sans,"
        "FontSize=18,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H801E2C4F,"
        "BackColour=&H801E2C4F,"
        "BorderStyle=3,"
        "Outline=1,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginV=120"
        "'"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(visual),
        "-i",
        str(voiceover),
        "-vf",
        subtitle_filter,
        "-af",
        "apad",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-t",
        f"{duration_seconds:.3f}",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output),
    ]

    subprocess.run(command, check=True)


def evaluate_final_render(
    summary: dict[str, Any],
    *,
    expected_duration_seconds: float,
    tolerance_seconds: float,
) -> dict[str, Any]:
    blockers: list[str] = []

    if summary.get("video_codec") != "h264":
        blockers.append("final_video_codec_not_h264")
    if summary.get("audio_codec") != "aac":
        blockers.append("final_audio_codec_not_aac")
    if summary.get("width") != 1080:
        blockers.append("final_width_not_1080")
    if summary.get("height") != 1920:
        blockers.append("final_height_not_1920")

    fps = summary.get("fps")
    if fps is None or abs(float(fps) - 30.0) > 0.05:
        blockers.append("final_fps_not_30")

    duration = summary.get("duration_seconds")
    if (
        duration is None
        or abs(
            float(duration) - float(expected_duration_seconds)
        )
        > float(tolerance_seconds)
    ):
        blockers.append("final_duration_outside_tolerance")

    if not summary.get("has_audio"):
        blockers.append("final_audio_missing")

    return {
        "technical_qa_passed": not blockers,
        "blockers": blockers,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate or render one SCENTAI pilot final video. "
            "Dry-run/diagnostic is the default; --write creates the MP4."
        )
    )
    parser.add_argument("--content-id", required=True)
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        job = load_job(load_json(args.jobs), args.content_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    visual = Path(job["visual_preview_path"])
    voiceover = Path(job["voiceover_path"])
    subtitles = Path(job["subtitle_path"])
    output = Path(job["final_render_path"])

    visual_summary = (
        media_summary(probe_media(visual))
        if visual.exists()
        else None
    )
    voiceover_summary = (
        media_summary(probe_media(voiceover))
        if voiceover.exists()
        else None
    )

    report = evaluate_inputs(
        job,
        visual_exists=visual.exists(),
        voiceover_exists=voiceover.exists(),
        subtitle_exists=subtitles.exists(),
        visual_summary=visual_summary,
        voiceover_summary=voiceover_summary,
    )

    report["dry_run"] = not args.write
    report["rendered"] = False
    report["final_render_path"] = str(output)
    report["technical_qa"] = None

    if args.write:
        if not report["ready_for_render"]:
            if args.machine_readable:
                print(json.dumps(report, ensure_ascii=False))
            else:
                print(
                    "SCENTAI final render blocked | "
                    + ", ".join(report["blockers"])
                )
            return 20

        render_final(
            visual=visual,
            voiceover=voiceover,
            subtitles=subtitles,
            output=output,
            duration_seconds=float(
                job["expected_duration_seconds"]
            ),
        )
        report["rendered"] = True

        final_summary = media_summary(probe_media(output))
        report["technical_qa"] = evaluate_final_render(
            final_summary,
            expected_duration_seconds=float(
                job["expected_duration_seconds"]
            ),
            tolerance_seconds=float(
                job.get("duration_tolerance_seconds", 2.0)
            ),
        )

        if not report["technical_qa"]["technical_qa_passed"]:
            if args.machine_readable:
                print(json.dumps(report, ensure_ascii=False))
            else:
                print(
                    "SCENTAI final render QA failed | "
                    + ", ".join(
                        report["technical_qa"]["blockers"]
                    )
                )
            return 30

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        mode = "WRITE" if args.write else "DRY-RUN"
        print(
            "SCENTAI final render | "
            f"mode={mode} | "
            f"content={args.content_id} | "
            f"ready={report['ready_for_render']} | "
            f"rendered={report['rendered']}"
        )
        for blocker in report["blockers"]:
            print(f"  - {blocker}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
