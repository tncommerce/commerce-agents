from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from .merchant_feed_assets import extract_feed_image_candidates
from .merchant_feed_preflight import build_feed_preflight
from .merchant_import import (
    MerchantProductMapping,
    import_feed_rows,
    resolve_product_id,
)
from .merchant_offers import rank_offers
from .merchant_partners import _valid_https_url
from .merchant_provider_contract import validate_provider_contract_rows


def build_release_feed_readiness(
    release_product_ids: list[str],
    rows: list[dict],
    mappings: list[MerchantProductMapping],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = now or datetime.now(UTC)
    release_ids = list(dict.fromkeys(release_product_ids))
    release_set = set(release_ids)

    preflight = build_feed_preflight(rows)
    contract = validate_provider_contract_rows(rows)

    import_issue_indexes = {
        int(issue["row_index"]) for issue in preflight["issues"] if issue["import_failures"]
    }
    import_issue_indexes.update(issue.row_index for issue in contract.invalid)

    release_relevant_import_issue_indexes: set[int] = set()
    for row_index in import_issue_indexes:
        row = rows[row_index]
        product_id = resolve_product_id(
            mappings,
            merchant=str(row.get("merchant") or ""),
            merchant_product_id=row.get("merchant_product_id"),
            ean=row.get("ean"),
            gtin=row.get("gtin"),
        )
        if product_id in release_set:
            release_relevant_import_issue_indexes.add(row_index)

    release_feed_rows_import_ready = (
        bool(contract.rows) and not release_relevant_import_issue_indexes
    )

    imported = import_feed_rows(contract.rows, mappings)
    images = extract_feed_image_candidates(rows, mappings)

    offers_by_product: dict[str, list] = defaultdict(list)
    for offer in imported.offers:
        if offer.product_id in release_set:
            offers_by_product[offer.product_id].append(offer)

    images_by_product: dict[str, list[dict]] = defaultdict(list)
    for candidate in images["candidates"]:
        product_id = str(candidate.get("product_id") or "")
        if product_id in release_set:
            images_by_product[product_id].append(candidate)

    product_rows = []
    for product_id in release_ids:
        offers = offers_by_product.get(product_id, [])
        trackable = [
            offer
            for offer in rank_offers(offers, now=checked_at)
            if _valid_https_url(offer.affiliate_url)
        ]
        image_candidates = images_by_product.get(product_id, [])

        product_rows.append(
            {
                "product_id": product_id,
                "mapped_offer_count": len(offers),
                "trackable_in_stock_offer_count": len(trackable),
                "ineligible_offer_count": len(offers) - len(trackable),
                "feed_image_candidate_count": len(image_candidates),
                "mapped": bool(offers),
                "trackable_offer_ready": bool(trackable),
                "feed_image_candidate_ready": bool(image_candidates),
            }
        )

    mapped_count = sum(1 for row in product_rows if row["mapped"])
    trackable_count = sum(1 for row in product_rows if row["trackable_offer_ready"])
    image_count = sum(1 for row in product_rows if row["feed_image_candidate_ready"])

    blockers = []
    if not release_feed_rows_import_ready:
        blockers.append("feed_not_import_ready")
    if mapped_count != len(release_ids):
        blockers.append("release_mapping_incomplete")
    if trackable_count != len(release_ids):
        blockers.append("release_affiliate_offer_coverage_incomplete")
    if image_count != len(release_ids):
        blockers.append("release_feed_image_coverage_incomplete")

    status = (
        "ready_for_manual_asset_review"
        if not blockers
        else ("blocked" if "feed_not_import_ready" in blockers else "review")
    )

    return {
        "status": status,
        "checked_at": checked_at.isoformat(),
        "max_offer_age_hours": 72,
        "tracking_verified": False,
        "activation_allowed": False,
        "release_size": len(release_ids),
        "feed_row_count": len(rows),
        "feed_import_ready": preflight["ready_for_offer_import"],
        "release_feed_rows_import_ready": release_feed_rows_import_ready,
        "release_relevant_import_issue_count": len(release_relevant_import_issue_indexes),
        "non_release_import_issue_count": len(
            import_issue_indexes - release_relevant_import_issue_indexes
        ),
        "feed_promotion_asset_ready": preflight["ready_for_promotion_assets"],
        "release_mapped_product_count": mapped_count,
        "release_trackable_offer_product_count": trackable_count,
        "release_feed_image_product_count": image_count,
        "provider_contract_invalid_count": len(contract.invalid),
        "feed_unmatched_count": len(imported.unmatched),
        "feed_invalid_count": len(imported.invalid),
        "blockers": blockers,
        "products": product_rows,
        "note": (
            "A ready result means the feed can cover the release with mapped "
            "current eligible affiliate URL candidates and reviewable feed images. "
            "This static check does not verify redirects, network attribution, "
            "exact landing-page variants, image rights or owner release approval."
        ),
    }
