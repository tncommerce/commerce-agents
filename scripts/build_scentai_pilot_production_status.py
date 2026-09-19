from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.render_scentai_pilot_final import (
    evaluate_final_render,
    evaluate_inputs,
    media_summary,
    probe_media,
)

DEFAULT_JOBS = Path("examples/retail/data/scentai_pilot_batch_01_production_jobs.json")
DEFAULT_OUTPUT = Path("examples/retail/data/scentai_pilot_batch_01_production_status.json")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_job_status(job: dict) -> dict[str, Any]:
    visual = Path(job["visual_preview_path"])
    voiceover = Path(job["voiceover_path"])
    subtitles = Path(job["subtitle_path"])
    final_render = Path(job["final_render_path"])

    visual_summary = media_summary(probe_media(visual)) if visual.exists() else None
    voiceover_summary = media_summary(probe_media(voiceover)) if voiceover.exists() else None

    inputs = evaluate_inputs(
        job,
        visual_exists=visual.exists(),
        voiceover_exists=voiceover.exists(),
        subtitle_exists=subtitles.exists(),
        visual_summary=visual_summary,
        voiceover_summary=voiceover_summary,
    )

    final_qa = None
    if final_render.exists():
        final_qa = evaluate_final_render(
            media_summary(probe_media(final_render)),
            expected_duration_seconds=float(job["expected_duration_seconds"]),
            tolerance_seconds=float(job.get("duration_tolerance_seconds", 2.0)),
        )

    if final_qa and final_qa["technical_qa_passed"]:
        state = "content_qa_pending"
        blockers = [
            "mobile_content_review_pending",
        ]
        if job.get("price_recheck_required"):
            blockers.append("publish_day_price_recheck_required")
    elif final_render.exists():
        state = "blocked"
        blockers = list(final_qa["blockers"])
    elif inputs["ready_for_render"]:
        state = "render_ready"
        blockers = ["final_render_missing"]
    elif not visual.exists():
        state = "visual_preview_pending"
        blockers = list(inputs["blockers"])
    elif not voiceover.exists():
        state = "voiceover_pending"
        blockers = list(inputs["blockers"])
    else:
        state = "subtitle_conform_pending"
        blockers = list(inputs["blockers"])
        if subtitles.exists():
            blockers.append("subtitle_timing_manual_confirmation_required")

    return {
        "content_id": job["content_id"],
        "state": state,
        "blockers": list(dict.fromkeys(blockers)),
        "ready_for_render": inputs["ready_for_render"],
        "final_render_exists": final_render.exists(),
        "technical_qa": final_qa,
        "price_recheck_required": bool(job.get("price_recheck_required")),
        "publish_action_class": "approval_required",
    }


def build_status(payload: dict) -> dict[str, Any]:
    rows = [build_job_status(job) for job in payload.get("jobs", [])]

    return {
        "version": 1,
        "campaign_id": payload.get("campaign_id"),
        "machine_id": payload.get("machine_id"),
        "summary": {
            "pilots": len(rows),
            "voiceover_pending": sum(1 for row in rows if row["state"] == "voiceover_pending"),
            "render_ready": sum(1 for row in rows if row["state"] == "render_ready"),
            "final_render_exists": sum(1 for row in rows if row["final_render_exists"]),
            "technical_qa_passed": sum(
                1
                for row in rows
                if row["technical_qa"] and row["technical_qa"]["technical_qa_passed"]
            ),
            "ready_for_publish_approval": sum(
                1 for row in rows if row["state"] == "ready_for_publish_approval"
            ),
        },
        "jobs": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build local-machine SCENTAI pilot production readiness "
            "from actual voiceover, subtitle and render files."
        )
    )
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        report = build_status(load_json(args.jobs))
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.error(str(exc))

    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        summary = report["summary"]
        print(
            "SCENTAI pilot production | "
            f"pilots={summary['pilots']} | "
            f"voiceover_pending={summary['voiceover_pending']} | "
            f"render_ready={summary['render_ready']} | "
            f"renders={summary['final_render_exists']} | "
            f"qa_passed={summary['technical_qa_passed']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
