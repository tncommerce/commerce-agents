from __future__ import annotations

import json
from pathlib import Path


DATA_DIR = Path("examples/retail/data")
OUTPUT = DATA_DIR / "scentai_catalog_staging.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def target_groups(value: str | None) -> list[str]:
    return [
        part.strip()
        for part in str(value or "").split(",")
        if part.strip()
    ]


def main() -> int:
    queue = load_json(
        DATA_DIR / "scentai_catalog_promotion_queue.json"
    )
    queue_by_id = {
        row["candidate_id"]: row
        for row in queue["candidates"]
    }

    products: list[dict] = []
    seen_product_ids: set[str] = set()

    for batch in (1, 2, 3):
        verification = load_json(
            DATA_DIR
            / f"scentai_catalog_batch{batch}_verification.json"
        )
        scent = load_json(
            DATA_DIR
            / f"scentai_catalog_batch{batch}_scent_qa.json"
        )
        scent_by_id = {
            row["candidate_id"]: row
            for row in scent["products"]
        }

        for verified in verification["products"]:
            candidate_id = verified["candidate_id"]
            community_row = scent_by_id.get(candidate_id, {})
            community = community_row.get(
                "parfumo",
                community_row,
            )
            queue_row = queue_by_id[candidate_id]
            product_id = verified["proposed_product_id"]

            if product_id in seen_product_ids:
                raise ValueError(
                    f"Duplicate staged product_id: {product_id}"
                )
            seen_product_ids.add(product_id)

            trend = community.get("trend_snapshot") or {}

            products.append(
                {
                    "candidate_id": candidate_id,
                    "product_id": product_id,
                    "batch": batch,
                    "brand": verified["brand"],
                    "name": verified["canonical_name"],
                    "concentration": verified["concentration"],
                    "volume_ml": verified["canonical_volume_ml"],
                    "classification": {
                        "target_groups": target_groups(
                            verified.get("target_group")
                        ),
                        "audience_lean": verified.get(
                            "audience_lean"
                        ),
                    },
                    "fragrance_profile": {
                        "scent_family": verified.get(
                            "scent_family"
                        ),
                        "key_notes": verified.get(
                            "key_notes",
                            [],
                        ),
                        "community_accords": community.get(
                            "main_accords",
                            [],
                        ),
                    },
                    "community": {
                        "source": "Parfumo",
                        "rating_10": community.get(
                            "scent_rating_10",
                            trend.get("parfumo_weekly_rating_10"),
                        ),
                        "rating_count": community.get(
                            "scent_ratings_count",
                            trend.get("weekly_ratings_count"),
                        ),
                        "longevity_10": community.get(
                            "longevity_10"
                        ),
                        "projection_10": community.get(
                            "sillage_10"
                        ),
                        "provisional": bool(
                            community.get("fast_track")
                            or (
                                community.get("longevity_10")
                                is None
                                and community.get("sillage_10")
                                is None
                            )
                        ),
                    },
                    "media": {
                        "image_url": None,
                        "image_status": (
                            "pending_approved_feed_or_"
                            "manufacturer_image"
                        ),
                    },
                    "commerce": {
                        "merchant_coverage_count": (
                            queue_row.get(
                                "merchant_coverage_count",
                                0,
                            )
                        ),
                        "live_offer_status": (
                            "pending_affiliate_approval_or_feed"
                        ),
                    },
                    "validation": {
                        "catalog_ready": False,
                        "blockers": queue_row.get(
                            "blockers",
                            [],
                        ),
                    },
                }
            )

    products.sort(
        key=lambda row: (
            row["batch"],
            row["product_id"],
        )
    )

    payload = {
        "schema_version": "1.0",
        "status": "staging_only_not_loaded_by_live_storefront",
        "product_count": len(products),
        "note": (
            "Canonical pre-live records for verified expansion "
            "candidates. No guessed prices, identifiers, affiliate "
            "URLs or product images."
        ),
        "products": products,
    }

    OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Staged {len(products)} verified SCENTAI products -> "
        f"{OUTPUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
