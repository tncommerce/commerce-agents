"""Reuse the existing strict Awin source-photo reviewer for unpublished DUFYND scents.

Offline only, no official feed is presumed accessible. The default operation
prepares exactly one non-public 10–20 item acquisition queue. If an already
authorized, current Awin 91379 file and metadata are supplied, delegate all
image candidate/rights checks to the existing public-photo reviewer.
Nothing here approves, downloads, alters, generates or publishes any picture.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.report_dufynd_commerce_scale_wave import (
    DATA,
    PHOTOS,
    PUBLIC,
    build_commerce_wave,
)
from scripts.report_dufynd_public_photo_feed_leads import (
    create_review,
    read_merchant_feed_rows,
    verify_context,
)

MAPPINGS = DATA / "merchant_product_mappings.json"
RIGHTS = DATA / "dufynd_affiliate_feed_image_rights.json"
STAGING = DATA / "scentai_catalog_staging.json"
OFFERS = DATA / "merchant_offers.json"
PARTNERS = DATA / "merchant_partners.json"

SOURCE_NOTINO = "CJ_NOTINO_CURRENT_FEED_AND_IMAGE_RIGHTS_UNVERIFIED"
SOURCE_TOP = "AWIN_TOP_PARFUEMERIE_FRESH_OFFICIAL_FEED_REVIEW_ONLY"
SOURCE_PERFUMETRADER = "PERFUMETRADER_AWIN_PRODUCT_FEED_NOT_AVAILABLE"


def build_unpublished_source_queue(
    staging: dict,
    public: dict,
    original_photos: list[dict],
    mappings: dict,
    offers: dict,
    partners: dict,
    *,
    now: datetime,
    batch_size: int = 20,
    feed_rows: list[dict] | None = None,
    feed_metadata: dict | None = None,
    rights: dict | None = None,
) -> dict[str, Any]:
    """Single existing 20-product queue, no automatically approved media."""
    commerce = build_commerce_wave(
        staging,
        public,
        original_photos,
        offers,
        partners,
        now=now,
        batch_size=batch_size,
    )
    if (feed_rows is None) != (feed_metadata is None):
        raise ValueError("official_feed_and_metadata_required_together")
    if feed_rows is not None and rights is None:
        raise ValueError("official_source_rights_registry_required")

    mapping_by_product: dict[str, list[dict]] = {}
    for mapping in mappings.get("mappings", []):
        if isinstance(mapping, dict) and isinstance(mapping.get("product_id"), str):
            mapping_by_product.setdefault(mapping["product_id"], []).append(mapping)

    queue = []
    photo_gap = []
    totals: Counter[str] = Counter()
    for row in commerce["items"]:
        if row["profile_gate"] == "PUBLIC_INFORMATION_PROFILE":
            raise ValueError("default_source_queue_contains_public_product")
        pid = row["product_id"]
        known = mapping_by_product.get(pid, [])
        merchants = sorted({str(m.get("merchant") or "") for m in known if m.get("merchant")})
        verified = [
            m
            for m in known
            if m.get("mapping_status") == "verified_current_variant"
            and m.get("merchant_product_id")
            and (m.get("gtin") or m.get("ean"))
        ]
        gtins = {str(m.get("gtin") or m.get("ean")) for m in known if m.get("gtin") or m.get("ean")}
        source_paths = []
        if "notino" in merchants:
            source_paths.append(SOURCE_NOTINO)
        if "top-parfuemerie" in merchants:
            source_paths.append(SOURCE_TOP)
        if "perfumetrader" in merchants:
            source_paths.append(SOURCE_PERFUMETRADER)
        if not source_paths:
            # Source discovery via a current, joined, rights-scoped feed is
            # possible, but old merchant mappings do NOT grant image rights.
            source_paths.append("CURRENT_RIGHTS_SCOPED_SOURCE_DISCOVERY_REQUIRED")

        is_missing_image = row["original_image_gate"] == "NO_APPROVED_ORIGINAL"
        if is_missing_image:
            photo_gap.append(
                {
                    "product_id": pid,
                    "brand": row["brand"],
                    "name": row["name"],
                    "concentration": row["concentration"],
                    "volume_ml": row["volume_ml"],
                    "source_state": "NO_EXACT_APPROVED_PHOTO",
                }
            )

        # A pre-existing tracked link can prioritize review. It does not make
        # a historical price, merchant permission or image license current.
        already_tracked = any(
            offer.get("product_id") == pid and offer.get("affiliate_url")
            for offer in offers.get("offers", [])
        )
        priority = (
            "EXISTING_TRACKED_ROUTE_IMAGE_HOLD" if already_tracked else "SOURCE_ACQUISITION_HOLD"
        )
        if len(gtins) > 1:
            priority = "CROSS_MERCHANT_GTIN_CONFLICT_HOLD"
        item = {
            "product_id": pid,
            "brand": row["brand"],
            "name": row["name"],
            "concentration": row["concentration"],
            "volume_ml": row["volume_ml"],
            "priority": priority,
            "mapped_merchants": merchants,
            "recorded_merchant_mapping_count": len(known),
            "already_verified_sku_gtin_pair_count": len(verified),
            "cross_merchant_gtin_conflict": len(gtins) > 1,
            "previously_stored_affiliate_route_exists": already_tracked,
            "source_paths": source_paths,
            "original_photo_gate": row["original_image_gate"],
            "exact_original_photo_source_checked_now": False,
            "owner_visual_review_required": is_missing_image,
            "image_license_granted_by_this_queue": False,
            "commerce_offer_authorized": False,
            "public_catalog_release_authorized": False,
        }
        queue.append(item)
        totals[priority] += 1

    photo_review: dict[str, Any] | None = None
    if feed_rows is not None:
        if photo_gap:
            photo_review = create_review(
                {
                    "status": "RIGHTS_SOURCE_ACQUISITION_PENDING_NO_AUTO_APPROVAL",
                    "items": photo_gap,
                },
                mappings,
                feed_rows,
                feed_metadata,
                rights,
                now=now,
            )
        else:
            # A supplied source is never called current without verification.
            verify_context(feed_metadata, rights, now=now)
            photo_review = {
                "status": "NO_UNAPPROVED_IMAGE_GAPS",
                "products_reviewed": 0,
                "products_with_leads": 0,
                "total_review_candidates": 0,
                "items": [],
                "approved_new_images": 0,
            }
        seen = {candidate["product_id"]: candidate for candidate in photo_review["items"]}
        for item in queue:
            match = seen.get(item["product_id"])
            item["exact_original_photo_source_checked_now"] = match is not None
            item["official_feed_photo_review_lead_count"] = (
                len(match["candidates"]) if match is not None else 0
            )
            if match and match["candidates"]:
                item["owner_visual_review_required"] = True

    return {
        "schema_version": 1,
        "status": "UNPUBLISHED_SOURCE_REVIEW_ONLY_NOT_LIVE",
        "generated_at": now.astimezone(UTC).isoformat(),
        "review_size": len(queue),
        "already_public_staging_excluded": commerce["staged_already_public_count"],
        "unpublished_staging_backlog": commerce["unpublished_staging_backlog"],
        "source_file_checked": feed_rows is not None,
        "source_file_validated_as_current": photo_review is not None,
        "review_priority_counts": dict(sorted(totals.items())),
        "items": queue,
        "official_awin_photo_review": photo_review,
        "original_image_approvals_granted": 0,
        "approved_merchant_offers_created": 0,
        "source_observation_timestamps_renewed": 0,
        "affiliate_links_generated": 0,
        "merchant_clickouts": 0,
        "network_requests": 0,
        "database_writes": 0,
        "publications": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, choices=range(10, 21), default=20)
    parser.add_argument("--feed", type=Path)
    parser.add_argument("--feed-metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.feed is None) != (args.feed_metadata is None):
        parser.error("feed_and_metadata_required_together")

    def read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    try:
        feed_rows = (
            read_merchant_feed_rows(args.feed, max_bytes=64 * 1024 * 1024, max_rows=30_000)
            if args.feed is not None
            else None
        )
        report = build_unpublished_source_queue(
            read_json(STAGING),
            read_json(PUBLIC),
            read_json(PHOTOS),
            read_json(MAPPINGS),
            read_json(OFFERS),
            read_json(PARTNERS),
            now=datetime.now(UTC),
            batch_size=args.batch_size,
            feed_rows=feed_rows,
            feed_metadata=read_json(args.feed_metadata) if args.feed_metadata else None,
            rights=read_json(RIGHTS) if feed_rows is not None else None,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        parser.exit(20, "unpublished_photo_source_review_failed_closed\n")
    print(
        "DUFYND unpublished source batch: "
        f"scents={report['review_size']} | "
        f"official_feed_checked={report['source_file_checked']} | "
        f"approved_images={report['original_image_approvals_granted']} | "
        f"published={report['publications']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
