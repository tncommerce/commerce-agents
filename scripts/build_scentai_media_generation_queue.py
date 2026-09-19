from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_PROVIDERS = DATA_DIR / "scentai_media_generation_providers.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_media_generation_queue.json"

DEFAULT_BATCHES = [
    {
        "batch_id": "pilot_batch_01",
        "manifest": DATA_DIR / "scentai_pilot_batch_01.json",
        "jobs": DATA_DIR / "scentai_pilot_batch_01_production_jobs.json",
        "voiceover": DATA_DIR / "scentai_pilot_batch_01_voiceover_spec.json",
    },
    {
        "batch_id": "pilot_batch_02",
        "manifest": DATA_DIR / "scentai_pilot_batch_02.json",
        "jobs": DATA_DIR / "scentai_pilot_batch_02_production_jobs.json",
        "voiceover": DATA_DIR / "scentai_pilot_batch_02_voiceover_spec.json",
    },
    {
        "batch_id": "pilot_batch_03",
        "manifest": DATA_DIR / "scentai_pilot_batch_03.json",
        "jobs": DATA_DIR / "scentai_pilot_batch_03_production_jobs.json",
        "voiceover": DATA_DIR / "scentai_pilot_batch_03_voiceover_spec.json",
    },
]


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


def build_queue(
    providers: dict,
    batches: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    source_payloads: list[dict] = [providers]

    for batch in batches:
        batch_id = str(batch["batch_id"])
        manifest = batch["manifest"]
        jobs = batch["jobs"]
        voiceover = batch["voiceover"]
        source_payloads.extend([manifest, jobs, voiceover])

        pilot_by_id = {str(row.get("content_id") or ""): row for row in manifest.get("pilots", [])}
        voice_by_id = {str(row.get("content_id") or ""): row for row in voiceover.get("pilots", [])}

        for job in jobs.get("jobs", []):
            content_id = str(job.get("content_id") or "")
            pilot = pilot_by_id.get(content_id, {})
            voice = voice_by_id.get(content_id, {})

            rows.append(
                {
                    "batch_id": batch_id,
                    "production_order": int(job.get("production_order", 0) or 0),
                    "content_id": content_id,
                    "campaign_id": manifest.get("campaign_id"),
                    "state": job.get("state"),
                    "target_duration_seconds": job.get("expected_duration_seconds"),
                    "script": voice.get(
                        "script",
                        pilot.get("voiceover"),
                    ),
                    "product_ids": list(pilot.get("product_ids", [])),
                    "landing_path": pilot.get("landing_path"),
                    "paths": {
                        "visual_preview": job.get("visual_preview_path"),
                        "voiceover": job.get("voiceover_path"),
                        "subtitle": job.get("subtitle_path"),
                        "final_render": job.get("final_render_path"),
                    },
                    "required_capabilities": [
                        "visual_preview_render",
                        "voice_synthesis_or_recorded_voiceover",
                        "subtitle_timing_conformance",
                        "subtitle_burn_in",
                        "voiceover_mux",
                        "technical_media_qa",
                    ],
                    "approval_gates": [
                        "subtitle_timing_confirmation",
                        "mobile_content_review",
                        "explicit_user_publish_approval",
                    ],
                    "provider_may_publish": False,
                    "publish_action_class": "approval_required",
                }
            )

    rows.sort(
        key=lambda row: (
            int(row["batch_id"].rsplit("_", 1)[-1]),
            int(row["production_order"]),
        )
    )

    implemented = {
        str(row.get("provider_id") or ""): row
        for row in providers.get("providers", [])
        if row.get("status") == "implemented"
    }

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(*source_payloads),
        "machine_id": "scentai_media_generation_queue_v1",
        "active_provider": providers.get("active_provider"),
        "summary": {
            "jobs": len(rows),
            "batches": len({row["batch_id"] for row in rows}),
            "local_visual_render_available": ("local_ffmpeg" in implemented),
            "voice_synthesis_provider_connected": any(
                row.get("type") == "external_connector" and row.get("status") == "connected"
                for row in providers.get("providers", [])
            ),
        },
        "safety": {
            "automatic_publish_allowed": False,
            "provider_credentials_allowed_in_repo_state": False,
            "provider_may_change_claims": False,
        },
        "jobs": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build provider-neutral SCENTAI media generation jobs for all pre-launch pilot batches."
        )
    )
    parser.add_argument(
        "--providers",
        type=Path,
        default=DEFAULT_PROVIDERS,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    generated_at = args.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    batches = []
    for spec in DEFAULT_BATCHES:
        batches.append(
            {
                "batch_id": spec["batch_id"],
                "manifest": load_json(spec["manifest"]),
                "jobs": load_json(spec["jobs"]),
                "voiceover": load_json(spec["voiceover"]),
            }
        )

    report = build_queue(
        load_json(args.providers),
        batches,
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
        summary = report["summary"]
        print(
            "SCENTAI media generation queue | "
            f"jobs={summary['jobs']} | "
            f"batches={summary['batches']} | "
            f"local_visual={summary['local_visual_render_available']} | "
            f"voice_provider="
            f"{summary['voice_synthesis_provider_connected']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
