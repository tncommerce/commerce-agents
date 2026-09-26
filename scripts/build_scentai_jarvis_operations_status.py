from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_MAPPING = DATA_DIR / "scentai_merchant_mapping_work_queue.json"
DEFAULT_AFFILIATE = DATA_DIR / "scentai_affiliate_activation_status.json"
DEFAULT_IMAGES = DATA_DIR / "scentai_image_approval_work_queue.json"
DEFAULT_RELEASE = DATA_DIR / "scentai_release_01_gate_status.json"
DEFAULT_FEED = DATA_DIR / "scentai_release_01_feed_activation_queue.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_jarvis_operations_status.json"


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


def build_operations_status(
    mapping: dict,
    affiliate: dict,
    images: dict,
    release: dict,
    feed: dict,
    *,
    generated_at: str,
) -> dict[str, Any]:
    mapping_summary = mapping.get("summary", {})
    affiliate_summary = affiliate.get("summary", {})
    image_summary = images.get("summary", {})
    release_summary = release.get("summary", {})
    feed_summary = feed.get("summary", {})

    approved_programs = int(affiliate_summary.get("approved", 0) or 0)
    active_programs = int(affiliate_summary.get("active", 0) or 0)

    full_feed_paths = int(feed_summary.get("programs_with_full_release_mapping", 0) or 0)
    approved_full_paths = int(
        feed_summary.get(
            "approved_programs_with_full_release_mapping",
            0,
        )
        or 0
    )

    release_size = int(release_summary.get("release_size", 0) or 0)
    mapping_ready = int(release_summary.get("mapping_ready", 0) or 0)
    approved_images = int(release_summary.get("approved_images", 0) or 0)
    tracked_offers = int(
        release_summary.get(
            "current_tracked_affiliate_offers",
            0,
        )
        or 0
    )
    purchase_destinations = int(release_summary.get("current_purchase_destinations", 0) or 0)
    promotion_ready = int(release_summary.get("promotion_ready", 0) or 0)

    blockers: list[str] = []
    if release_size and approved_images < release_size:
        blockers.append("release_approved_images_incomplete")
    if release_size and purchase_destinations < release_size:
        blockers.append("release_purchase_destinations_incomplete")
    if promotion_ready < release_size:
        blockers.append("release_promotion_gates_incomplete")

    if not blockers and release_size > 0:
        overall_state = "ready_for_user_approval"
        user_approval_required_now = True
        next_action = "request_explicit_user_approval_for_release"
        next_action_class = "approval_required"
    elif approved_full_paths >= 1:
        overall_state = "integration_path_open"
        user_approval_required_now = False
        next_action = "run_feed_preflight_and_dry_run"
        next_action_class = "auto_allowed"
    else:
        overall_state = "waiting_purchase_destinations_and_images"
        user_approval_required_now = False
        next_action = "verify_purchase_destinations_and_image_rights"
        next_action_class = "auto_allowed"

    full_mapping_merchants = [
        {
            "merchant_id": row.get("merchant_id"),
            "network": row.get("network"),
            "program": row.get("program"),
            "application_status": row.get("application_status"),
            "program_approved": bool(row.get("program_approved")),
            "next_action": row.get("next_action"),
        }
        for row in feed.get("programs", [])
        if row.get("full_release_mapping_coverage")
    ]

    pending_manual_approvals = []
    if int(image_summary.get("review_ready", 0) or 0) > 0:
        pending_manual_approvals.append("review_ready_product_images")
    if overall_state == "ready_for_user_approval":
        pending_manual_approvals.append("release_01_live_activation")

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(
            mapping,
            affiliate,
            images,
            release,
            feed,
        ),
        "system": "DUFYND",
        "control_plane": "commerce_jarvis",
        "policy_ref": "scentai_jarvis_operating_policy.json",
        "overall_state": overall_state,
        "user_approval_required_now": (user_approval_required_now),
        "next_action": next_action,
        "next_action_class": next_action_class,
        "blockers": blockers,
        "safety": {
            "live_routing_allowed": (
                overall_state == "ready_for_user_approval" and user_approval_required_now is False
            ),
            "no_automatic_spend": True,
            "no_automatic_live_release": True,
            "commission_may_affect_recommendations": False,
            "secrets_allowed_in_repo_state": False,
        },
        "catalog": {
            "staged_products": int(mapping_summary.get("staged_products", 0) or 0),
            "products_with_resolved_mapping": int(
                mapping_summary.get(
                    "products_with_resolved_mapping",
                    0,
                )
                or 0
            ),
            "products_without_resolved_mapping": int(
                mapping_summary.get(
                    "products_without_resolved_mapping",
                    0,
                )
                or 0
            ),
        },
        "affiliate": {
            "registered_programs": int(affiliate_summary.get("programs", 0) or 0),
            "active_programs": active_programs,
            "approved_programs": approved_programs,
            "full_release_mapping_paths": full_feed_paths,
            "approved_full_release_paths": approved_full_paths,
            "full_mapping_merchants": full_mapping_merchants,
        },
        "images": {
            "staged_products": int(image_summary.get("staged_products", 0) or 0),
            "approved_images": int(image_summary.get("approved_images", 0) or 0),
            "pending_images": int(image_summary.get("pending_images", 0) or 0),
            "review_ready": int(image_summary.get("review_ready", 0) or 0),
            "rights_or_source_check_pending": int(
                image_summary.get(
                    "rights_or_source_check_pending",
                    0,
                )
                or 0
            ),
        },
        "release_01": {
            "release_size": release_size,
            "mapping_ready": mapping_ready,
            "image_identity_source_verified": int(
                release_summary.get(
                    "image_identity_source_verified",
                    0,
                )
                or 0
            ),
            "approved_images": approved_images,
            "current_purchase_destinations": purchase_destinations,
            "current_tracked_affiliate_offers": tracked_offers,
            "promotion_ready": promotion_ready,
        },
        "pending_manual_approvals": pending_manual_approvals,
        "operating_note": (
            "This control-plane status summarizes operational readiness. "
            "It does not authorize live writes, spending, outbound messages "
            "or affiliate activation."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one Jarvis-readable DUFYND operations status from "
            "mapping, affiliate, image and release source states."
        )
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=DEFAULT_MAPPING,
    )
    parser.add_argument(
        "--affiliate",
        type=Path,
        default=DEFAULT_AFFILIATE,
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=DEFAULT_IMAGES,
    )
    parser.add_argument(
        "--release",
        type=Path,
        default=DEFAULT_RELEASE,
    )
    parser.add_argument(
        "--feed",
        type=Path,
        default=DEFAULT_FEED,
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

    status = build_operations_status(
        load_json(args.mapping),
        load_json(args.affiliate),
        load_json(args.images),
        load_json(args.release),
        load_json(args.feed),
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
            "DUFYND Jarvis operations | "
            f"state={status['overall_state']} | "
            f"next={status['next_action']} | "
            f"approval_now={status['user_approval_required_now']}"
        )
        print(
            "Release 01 | "
            f"mapping={status['release_01']['mapping_ready']}/"
            f"{status['release_01']['release_size']} | "
            f"images={status['release_01']['approved_images']}/"
            f"{status['release_01']['release_size']} | "
            f"affiliate={status['release_01']['current_tracked_affiliate_offers']}/"
            f"{status['release_01']['release_size']} | "
            f"ready={status['release_01']['promotion_ready']}/"
            f"{status['release_01']['release_size']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
