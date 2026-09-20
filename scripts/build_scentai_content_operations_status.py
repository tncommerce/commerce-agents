from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_MANIFEST = DATA_DIR / "scentai_pilot_batch_01.json"
DEFAULT_READINESS = DATA_DIR / "scentai_pilot_batch_01_readiness.json"
DEFAULT_JOBS = DATA_DIR / "scentai_pilot_batch_01_production_jobs.json"
DEFAULT_SUBTITLES = DATA_DIR / "scentai_pilot_batch_01_subtitles.json"
DEFAULT_LINKS = DATA_DIR / "scentai_pilot_batch_01_links.json"
DEFAULT_SOCIAL_COPY = DATA_DIR / "scentai_pilot_batch_01_social_copy.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_content_operations_status.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_fingerprint(*payloads: object) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(canonical_bytes(payload))
    return digest.hexdigest()


def _nonempty_file_exists(path_value: object) -> bool:
    if not isinstance(path_value, str) or not path_value.strip():
        return False

    path = Path(path_value)
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def build_content_operations_status(
    manifest: dict,
    readiness: dict,
    jobs: dict,
    subtitles: dict,
    links: dict,
    social_copy: dict,
    *,
    generated_at: str,
) -> dict[str, Any]:
    pilots = manifest.get("pilots", [])
    pilot_ids = {str(row.get("content_id") or "") for row in pilots}
    job_rows = jobs.get("jobs", [])
    subtitle_ids = {str(row.get("content_id") or "") for row in subtitles.get("items", [])}
    social_rows = social_copy.get("posts")
    if not isinstance(social_rows, list):
        social_rows = social_copy.get("items", [])
    social_ids = {str(row.get("content_id") or "") for row in social_rows}
    link_rows = links.get("links", [])

    channels = {str(channel) for channel in manifest.get("channels", [])}
    expected_links = len(pilot_ids) * len(channels)
    actual_links = [
        row
        for row in link_rows
        if str(row.get("content_id") or "") in pilot_ids
        and str(row.get("channel") or "") in channels
    ]

    summary = readiness.get("summary", {})
    preview_path_rows = [
        row
        for row in job_rows
        if isinstance(row.get("visual_preview_path"), str)
        and str(row.get("visual_preview_path") or "").strip()
    ]
    preview_ready_ids = {
        str(row.get("content_id") or "")
        for row in preview_path_rows
        if _nonempty_file_exists(row.get("visual_preview_path"))
    }
    if preview_path_rows:
        visual_previews = len(preview_ready_ids)
        visual_preview_source = "rendered_files"
    else:
        visual_previews = int(summary.get("visual_preview_mp4s_ready", 0) or 0)
        visual_preview_source = "readiness_summary"

    final_renders = int(summary.get("final_video_renders_ready", 0) or 0)

    voiceover_scripts = int(summary.get("voiceover_scripts_ready", 0) or 0)
    tracked_links = int(summary.get("tracked_links_ready", 0) or 0)
    social_ready = int(summary.get("social_copy_ready", 0) or 0)
    subtitle_drafts = int(summary.get("subtitle_timing_drafts_ready", 0) or 0)

    blockers: list[str] = []
    if visual_previews < len(pilot_ids):
        blockers.append("visual_preview_mp4s_incomplete")
        if any(
            str(row.get("state") or "") == "visual_preview_pending"
            and (not preview_path_rows or str(row.get("content_id") or "") not in preview_ready_ids)
            for row in job_rows
        ):
            blockers.append("pilot_visual_preview_generation_pending")
    if any("voiceover_file_missing" in row.get("blockers", []) for row in job_rows):
        blockers.append("voiceover_audio_pending")
    if any(
        str(row.get("subtitle_timing_status") or "") != "conformed_to_voiceover" for row in job_rows
    ):
        blockers.append("subtitle_timing_conformance_pending")
    if final_renders < len(pilot_ids):
        blockers.append("final_video_renders_incomplete")
    if tracked_links < expected_links:
        blockers.append("tracked_links_incomplete")
    if social_ready < len(pilot_ids):
        blockers.append("social_copy_incomplete")

    if visual_previews < len(pilot_ids):
        overall_state = "visual_preview_generation_pending"
        next_action = "render_and_verify_visual_preview_mp4s"
        action_class = "auto_allowed"
        user_approval_required_now = False
    elif any("voiceover_file_missing" in row.get("blockers", []) for row in job_rows):
        overall_state = "voiceover_pending"
        next_action = "record_or_generate_voiceover_audio"
        action_class = "approval_required"
        user_approval_required_now = True
    elif any(
        str(row.get("subtitle_timing_status") or "") != "conformed_to_voiceover" for row in job_rows
    ):
        overall_state = "subtitle_conformance_pending"
        next_action = "conform_subtitles_to_voiceover"
        action_class = "approval_required"
        user_approval_required_now = True
    elif final_renders < len(pilot_ids):
        overall_state = "final_render_pending"
        next_action = "render_and_technical_qa_final_videos"
        action_class = "auto_allowed"
        user_approval_required_now = False
    else:
        overall_state = "mobile_content_review_pending"
        next_action = "perform_mobile_content_review"
        action_class = "approval_required"
        user_approval_required_now = True

    consistency = {
        "manifest_job_ids_match": (
            pilot_ids == {str(row.get("content_id") or "") for row in job_rows}
        ),
        "manifest_subtitle_ids_match": pilot_ids == subtitle_ids,
        "manifest_social_copy_ids_match": pilot_ids == social_ids,
        "tracked_link_count_expected": expected_links,
        "tracked_link_count_actual": len(actual_links),
    }

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(
            manifest,
            readiness,
            jobs,
            subtitles,
            links,
            social_copy,
            {
                "visual_preview_source": visual_preview_source,
                "preview_ready_ids": sorted(preview_ready_ids),
            },
        ),
        "system": "DUFYND",
        "domain": "content",
        "campaign_id": manifest.get("campaign_id"),
        "overall_state": overall_state,
        "next_action": next_action,
        "next_action_class": action_class,
        "user_approval_required_now": user_approval_required_now,
        "blockers": blockers,
        "summary": {
            "pilots": len(pilot_ids),
            "product_assets_verified": int(summary.get("product_assets_verified", 0) or 0),
            "product_assets_required": int(summary.get("product_assets_required", 0) or 0),
            "voiceover_scripts_ready": voiceover_scripts,
            "visual_preview_mp4s_ready": visual_previews,
            "visual_preview_source": visual_preview_source,
            "subtitle_drafts_ready": subtitle_drafts,
            "tracked_links_ready": tracked_links,
            "social_copy_ready": social_ready,
            "final_video_renders_ready": final_renders,
        },
        "consistency": consistency,
        "safety": {
            "automatic_publish_allowed": False,
            "publish_requires_explicit_user_approval": True,
            "social_credentials_allowed_in_repo_state": False,
            "price_claim_requires_publish_day_recheck": True,
        },
        "jobs": [
            {
                "content_id": row.get("content_id"),
                "production_order": row.get("production_order"),
                "state": (
                    "voiceover_pending"
                    if preview_path_rows
                    and str(row.get("content_id") or "") in preview_ready_ids
                    and "voiceover_file_missing" in row.get("blockers", [])
                    else row.get("state")
                ),
                "subtitle_timing_status": row.get("subtitle_timing_status"),
                "price_recheck_required": bool(row.get("price_recheck_required")),
                "publish_action_class": row.get("publish_action_class"),
            }
            for row in job_rows
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one Jarvis-readable DUFYND content operations status "
            "from pilot production source files."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--subtitles", type=Path, default=DEFAULT_SUBTITLES)
    parser.add_argument("--links", type=Path, default=DEFAULT_LINKS)
    parser.add_argument(
        "--social-copy",
        type=Path,
        default=DEFAULT_SOCIAL_COPY,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    generated_at = args.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    report = build_content_operations_status(
        load_json(args.manifest),
        load_json(args.readiness),
        load_json(args.jobs),
        load_json(args.subtitles),
        load_json(args.links),
        load_json(args.social_copy),
        generated_at=generated_at,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "DUFYND content operations | "
            f"state={report['overall_state']} | "
            f"next={report['next_action']} | "
            f"approval_now={report['user_approval_required_now']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
