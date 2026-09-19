from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_MANIFEST = DATA_DIR / "scentai_pilot_batch_01.json"
DEFAULT_JOBS = DATA_DIR / "scentai_pilot_batch_01_production_jobs.json"
DEFAULT_SUBTITLES = DATA_DIR / "scentai_pilot_batch_01_subtitles.json"
DEFAULT_LINKS = DATA_DIR / "scentai_pilot_batch_01_links.json"
DEFAULT_SOCIAL = DATA_DIR / "scentai_pilot_batch_01_social_copy.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _scene_end_seconds(scene: dict) -> float:
    raw = str(scene.get("seconds") or "")
    if "-" not in raw:
        raise ValueError(f"invalid scene timing {raw!r}")
    _, end = raw.split("-", maxsplit=1)
    return float(end)


def _subtitle_end_seconds(item: dict) -> float:
    segments = item.get("segments", [])
    if not segments:
        raise ValueError(
            f"{item.get('content_id')}: subtitle segments missing"
        )
    return float(segments[-1]["end"])


def validate_contract(
    manifest: dict,
    jobs: dict,
    subtitles: dict,
    links: dict,
    social_copy: dict,
) -> dict[str, Any]:
    issues: list[str] = []

    pilots = manifest.get("pilots", [])
    pilot_by_id = {
        str(row.get("content_id") or ""): row
        for row in pilots
    }
    pilot_ids = set(pilot_by_id)

    job_rows = jobs.get("jobs", [])
    jobs_by_id = {
        str(row.get("content_id") or ""): row
        for row in job_rows
    }
    subtitle_rows = subtitles.get("items", [])
    subtitles_by_id = {
        str(row.get("content_id") or ""): row
        for row in subtitle_rows
    }

    social_rows = social_copy.get("posts")
    if not isinstance(social_rows, list):
        social_rows = social_copy.get("items", [])
    social_by_id = {
        str(row.get("content_id") or ""): row
        for row in social_rows
    }

    if pilot_ids != set(jobs_by_id):
        issues.append("content_id_mismatch:manifest_vs_jobs")
    if pilot_ids != set(subtitles_by_id):
        issues.append("content_id_mismatch:manifest_vs_subtitles")
    if pilot_ids != set(social_by_id):
        issues.append("content_id_mismatch:manifest_vs_social_copy")

    channels = {
        str(value)
        for value in manifest.get("channels", [])
    }
    if channels != {"tiktok", "instagram", "youtube"}:
        issues.append("unexpected_channel_set")

    campaign_id = str(manifest.get("campaign_id") or "")
    link_rows = links.get("links", [])

    for content_id in sorted(pilot_ids):
        pilot = pilot_by_id[content_id]
        job = jobs_by_id.get(content_id)
        subtitle = subtitles_by_id.get(content_id)
        social = social_by_id.get(content_id)

        target = float(pilot.get("target_duration_seconds") or 0)
        scenes = pilot.get("scenes", [])
        if not scenes:
            issues.append(f"{content_id}:scenes_missing")
        else:
            try:
                scene_end = _scene_end_seconds(scenes[-1])
            except (TypeError, ValueError) as exc:
                issues.append(
                    f"{content_id}:scene_timing_invalid:{exc}"
                )
            else:
                if abs(scene_end - target) > 0.05:
                    issues.append(
                        f"{content_id}:scene_duration_mismatch"
                    )

        if subtitle is not None:
            try:
                subtitle_end = _subtitle_end_seconds(subtitle)
            except (KeyError, TypeError, ValueError) as exc:
                issues.append(
                    f"{content_id}:subtitle_timing_invalid:{exc}"
                )
            else:
                if abs(subtitle_end - target) > 0.05:
                    issues.append(
                        f"{content_id}:subtitle_duration_mismatch"
                    )

        if job is not None:
            if (
                abs(
                    float(job.get("expected_duration_seconds") or 0)
                    - target
                )
                > 0.05
            ):
                issues.append(
                    f"{content_id}:job_duration_mismatch"
                )

            expected_subtitle = (
                "examples/retail/data/"
                "scentai_pilot_batch_01_subtitles/"
                f"{content_id}.srt"
            )
            if job.get("subtitle_path") != expected_subtitle:
                issues.append(
                    f"{content_id}:job_subtitle_path_mismatch"
                )

            expected_price_recheck = bool(
                pilot.get("price_snapshot", {}).get(
                    "reverify_before_publish",
                    False,
                )
            )
            if (
                bool(job.get("price_recheck_required"))
                != expected_price_recheck
            ):
                issues.append(
                    f"{content_id}:price_recheck_flag_mismatch"
                )

        rows = [
            row
            for row in link_rows
            if row.get("content_id") == content_id
        ]
        if len(rows) != len(channels):
            issues.append(
                f"{content_id}:tracked_link_count_mismatch"
            )
        if {
            str(row.get("channel") or "")
            for row in rows
        } != channels:
            issues.append(
                f"{content_id}:tracked_link_channels_mismatch"
            )

        for row in rows:
            if row.get("campaign_id") != campaign_id:
                issues.append(
                    f"{content_id}:tracked_link_campaign_mismatch"
                )
            if row.get("landing_path") != pilot.get("landing_path"):
                issues.append(
                    f"{content_id}:tracked_link_landing_mismatch"
                )
            url = str(row.get("url") or "")
            expected_query = (
                f"src={row.get('channel')}"
                f"&cmp={campaign_id}"
                f"&content={content_id}"
            )
            if expected_query not in url:
                issues.append(
                    f"{content_id}:tracked_link_query_mismatch"
                )

        if social is not None:
            for channel in channels:
                if channel not in social:
                    issues.append(
                        f"{content_id}:social_copy_missing_{channel}"
                    )

    return {
        "valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "summary": {
            "pilots": len(pilot_ids),
            "jobs": len(job_rows),
            "subtitle_items": len(subtitle_rows),
            "social_items": len(social_rows),
            "tracked_links": len(link_rows),
            "channels": sorted(channels),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate cross-file SCENTAI Pilot Batch 01 production contract."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument(
        "--subtitles",
        type=Path,
        default=DEFAULT_SUBTITLES,
    )
    parser.add_argument("--links", type=Path, default=DEFAULT_LINKS)
    parser.add_argument("--social-copy", type=Path, default=DEFAULT_SOCIAL)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_contract(
            load_json(args.manifest),
            load_json(args.jobs),
            load_json(args.subtitles),
            load_json(args.links),
            load_json(args.social_copy),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "SCENTAI pilot contract | "
            f"valid={report['valid']} | "
            f"issues={report['issue_count']} | "
            f"pilots={report['summary']['pilots']} | "
            f"links={report['summary']['tracked_links']}"
        )
        for issue in report["issues"]:
            print(f"  - {issue}")

    return 0 if report["valid"] else 20


if __name__ == "__main__":
    raise SystemExit(main())
