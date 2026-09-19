from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.build_scentai_release_gate_status import (
    build_release_gate_status,
)

DATA_DIR = Path("examples/retail/data")
DEFAULT_RELEASES = [
    DATA_DIR / "scentai_release_batch_01.json",
    DATA_DIR / "scentai_release_batch_02.json",
    DATA_DIR / "scentai_release_batch_03.json",
]
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_MAPPINGS = DATA_DIR / "merchant_product_mappings.json"
DEFAULT_OFFERS = DATA_DIR / "merchant_offers.json"
DEFAULT_IMAGES = DATA_DIR / "scentai_image_approval_work_queue.json"
DEFAULT_AFFILIATE = DATA_DIR / "scentai_affiliate_activation_status.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_release_pipeline_status.json"


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


def build_release_pipeline_status(
    releases: list[dict],
    staging: dict,
    mappings: dict,
    offers: dict,
    images: dict,
    affiliate: dict,
    *,
    generated_at: str,
) -> dict[str, Any]:
    release_rows: list[dict[str, Any]] = []

    for release_order, manifest in enumerate(releases, start=1):
        gate = build_release_gate_status(
            manifest,
            staging,
            mappings,
            offers,
            images,
            affiliate,
            generated_at=generated_at,
        )
        summary = gate["summary"]
        release_size = int(summary.get("release_size", 0) or 0)
        promotion_ready = int(
            summary.get("promotion_ready", 0) or 0
        )
        dependencies = list(
            manifest.get("depends_on_release_ids", [])
        )

        if dependencies:
            dependency_state = "pending_prior_release_validation"
        else:
            dependency_state = "not_required"

        if promotion_ready == release_size and release_size > 0:
            gate_state = "product_gates_ready"
        elif int(summary.get("approved_images", 0) or 0) == 0:
            gate_state = "blocked_pending_images_and_affiliate_offers"
        else:
            gate_state = "blocked_pending_remaining_product_gates"

        release_rows.append(
            {
                "release_id": manifest.get("release_id"),
                "release_order": release_order,
                "manifest_status": manifest.get("status"),
                "write_enabled": bool(
                    manifest.get("write_enabled")
                ),
                "depends_on_release_ids": dependencies,
                "dependency_state": dependency_state,
                "gate_state": gate_state,
                "summary": summary,
                "write_guard_reason": manifest.get(
                    "write_guard_reason"
                ),
            }
        )

    current = next(
        (
            row
            for row in release_rows
            if row["gate_state"] != "product_gates_ready"
        ),
        release_rows[-1] if release_rows else None,
    )

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(
            releases,
            staging,
            mappings,
            offers,
            images,
            affiliate,
        ),
        "policy_ref": "scentai_jarvis_operating_policy.json",
        "release_count": len(release_rows),
        "current_release_id": (
            current.get("release_id") if current else None
        ),
        "pipeline_state": (
            "blocked_on_current_release"
            if current
            and current["gate_state"] != "product_gates_ready"
            else "all_prepared_release_product_gates_ready"
        ),
        "releases": release_rows,
        "note": (
            "Release ordering is operational, not a fragrance ranking. "
            "Dependency locks remain separate from product-level readiness."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Jarvis-readable SCENTAI Release 01-03 pipeline "
            "status from current source state."
        )
    )
    parser.add_argument(
        "--release",
        action="append",
        type=Path,
        default=None,
    )
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS)
    parser.add_argument("--offers", type=Path, default=DEFAULT_OFFERS)
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--affiliate", type=Path, default=DEFAULT_AFFILIATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    release_paths = args.release or DEFAULT_RELEASES
    generated_at = (
        args.generated_at
        or datetime.now(UTC).replace(microsecond=0).isoformat()
    )

    status = build_release_pipeline_status(
        [load_json(path) for path in release_paths],
        load_json(args.staging),
        load_json(args.mappings),
        load_json(args.offers),
        load_json(args.images),
        load_json(args.affiliate),
        generated_at=generated_at,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.machine_readable:
        print(json.dumps(status, ensure_ascii=False))
    else:
        print(
            "SCENTAI release pipeline | "
            f"releases={status['release_count']} | "
            f"current={status['current_release_id']} | "
            f"state={status['pipeline_state']}"
        )
        for row in status["releases"]:
            summary = row["summary"]
            print(
                f"  {row['release_id']} | "
                f"mapping={summary['mapping_ready']}/"
                f"{summary['release_size']} | "
                f"images={summary['approved_images']}/"
                f"{summary['release_size']} | "
                f"affiliate="
                f"{summary['current_tracked_affiliate_offers']}/"
                f"{summary['release_size']} | "
                f"ready={summary['promotion_ready']}/"
                f"{summary['release_size']} | "
                f"dependency={row['dependency_state']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
