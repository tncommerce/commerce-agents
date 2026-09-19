from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_image_approval_work_queue.json"
DEFAULT_RELEASES = [
    DATA_DIR / "scentai_release_batch_01.json",
    DATA_DIR / "scentai_release_batch_02.json",
    DATA_DIR / "scentai_release_batch_03.json",
]
APPROVED_IMAGE_STATES = {
    "approved_feed_image",
    "approved_manufacturer_image",
    "approved_licensed_image",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_fingerprint(
    staging: dict,
    releases: list[dict],
) -> str:
    digest = hashlib.sha256()
    digest.update(canonical_bytes(staging))
    for release in releases:
        digest.update(canonical_bytes(release))
    return digest.hexdigest()


def build_release_index(
    releases: list[dict],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    for release_order, release in enumerate(releases, start=1):
        release_id = str(release.get("release_id") or "").strip()
        for position, product_id in enumerate(
            release.get("product_ids", []),
            start=1,
        ):
            index[str(product_id)] = {
                "release_id": release_id,
                "release_order": release_order,
                "position": position,
                "write_enabled": bool(release.get("write_enabled")),
            }

    return index


def build_queue(
    staging: dict,
    releases: list[dict],
    *,
    generated_at: str,
) -> dict[str, Any]:
    release_index = build_release_index(releases)
    items: list[dict[str, Any]] = []

    for product in staging.get("products", []):
        product_id = str(product.get("product_id") or "").strip()
        media = product.get("media", {})
        image_status = str(media.get("image_status") or "").strip()
        image_url = str(media.get("image_url") or "").strip() or None
        approved = (
            image_status in APPROVED_IMAGE_STATES
            and image_url is not None
        )

        items.append(
            {
                "product_id": product_id,
                "candidate_id": product.get("candidate_id"),
                "brand": product.get("brand"),
                "name": product.get("name"),
                "batch": product.get("batch"),
                "release": release_index.get(product_id),
                "current_image_url": image_url,
                "current_image_status": image_status or "missing",
                "image_state": image_status if approved else "missing",
                "blockers": (
                    [] if approved else ["approved_product_image_missing"]
                ),
                "next_action": (
                    "none"
                    if approved
                    else "await_real_feed_or_official_asset_candidate"
                ),
                "action_class": "auto_allowed",
                "approval_action_class": "approval_required",
            }
        )

    items.sort(
        key=lambda item: (
            (
                item["release"]["release_order"]
                if item["release"]
                else 99
            ),
            (
                item["release"]["position"]
                if item["release"]
                else 999
            ),
            str(item.get("brand") or "").casefold(),
            str(item.get("name") or "").casefold(),
        )
    )

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(
            staging,
            releases,
        ),
        "machine_id": "scentai_image_approval_v1",
        "policy_ref": "scentai_jarvis_operating_policy.json",
        "source_files": [
            DEFAULT_STAGING.name,
            *[path.name for path in DEFAULT_RELEASES],
        ],
        "summary": {
            "staged_products": len(items),
            "release_01_products": sum(
                1
                for item in items
                if item.get("release", {}).get("release_id")
                == "SCENTAI-RELEASE-01"
                if item.get("release")
            ),
            "release_02_products": sum(
                1
                for item in items
                if item.get("release", {}).get("release_id")
                == "SCENTAI-RELEASE-02"
                if item.get("release")
            ),
            "release_03_products": sum(
                1
                for item in items
                if item.get("release", {}).get("release_id")
                == "SCENTAI-RELEASE-03"
                if item.get("release")
            ),
            "approved_images": sum(
                1
                for item in items
                if str(item["image_state"]).startswith("approved_")
            ),
            "pending_images": sum(
                1
                for item in items
                if not str(item["image_state"]).startswith("approved_")
            ),
            "review_ready": sum(
                1
                for item in items
                if item["image_state"] == "review_ready"
            ),
        },
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Jarvis-ready SCENTAI image approval work queue "
            "from staging and guarded release manifests."
        )
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--release",
        action="append",
        type=Path,
        default=None,
        help="Optional release manifest. Repeatable.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--generated-at",
        default=None,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    release_paths = args.release or DEFAULT_RELEASES
    staging = load_json(args.staging)
    releases = [load_json(path) for path in release_paths]
    generated_at = (
        args.generated_at
        or datetime.now(UTC).replace(microsecond=0).isoformat()
    )

    queue = build_queue(
        staging,
        releases,
        generated_at=generated_at,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.machine_readable:
        print(json.dumps(queue, ensure_ascii=False))
    else:
        summary = queue["summary"]
        print(
            "SCENTAI image queue | "
            f"staged={summary['staged_products']} | "
            f"approved={summary['approved_images']} | "
            f"pending={summary['pending_images']} | "
            f"review_ready={summary['review_ready']}"
        )
        print(
            "source_fingerprint_sha256="
            f"{queue['source_fingerprint_sha256']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
