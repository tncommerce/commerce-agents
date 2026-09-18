from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.promote_scentai_catalog import (
    APPROVED_IMAGE_STATUSES,
    eligible_affiliate_offers,
)


DATA_DIR = Path("examples/retail/data")
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_CATALOG = DATA_DIR / "catalog.json"
DEFAULT_OFFERS = DATA_DIR / "merchant_offers.json"
DEFAULT_MAPPINGS = DATA_DIR / "merchant_product_mappings.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def target_groups_from_live_product(product: dict) -> list[str]:
    raw = str(
        product.get("attributes", {}).get("target_group") or ""
    )
    return [
        group.strip()
        for group in raw.split(",")
        if group.strip()
    ]


def build_merchant_coverage_report(
    staging: dict,
    catalog: dict,
    offers_payload: dict,
    mappings_payload: dict,
    *,
    now: datetime,
    max_offer_age_hours: float = 72.0,
) -> dict[str, Any]:
    staged_products = staging.get("products", [])
    offers = offers_payload.get(
        "offers",
        offers_payload if isinstance(offers_payload, list) else [],
    )
    mappings = mappings_payload.get("mappings", [])

    live_products = [
        product
        for product in catalog.get("products", [])
        if str(product.get("product_id") or "").startswith("SC-")
        and product.get("category") == "fragrance"
        and product.get("in_stock") is not False
    ]

    live_audience = Counter()
    for product in live_products:
        live_audience.update(
            target_groups_from_live_product(product)
        )

    staged_audience = Counter()
    rows: list[dict[str, Any]] = []

    for product in staged_products:
        product_id = str(product.get("product_id") or "").strip()
        target_groups = (
            product.get("classification", {}).get(
                "target_groups",
                [],
            )
            or []
        )
        staged_audience.update(target_groups)

        product_offers = [
            offer
            for offer in offers
            if offer.get("product_id") == product_id
        ]
        affiliate_offers = [
            offer
            for offer in product_offers
            if str(offer.get("affiliate_url") or "").strip()
        ]
        fresh_affiliate_offers = eligible_affiliate_offers(
            offers,
            product_id=product_id,
            now=now,
            max_age_hours=max_offer_age_hours,
        )

        product_mappings = [
            mapping
            for mapping in mappings
            if mapping.get("product_id") == product_id
        ]
        resolved_mappings = [
            mapping
            for mapping in product_mappings
            if any(
                str(mapping.get(key) or "").strip()
                for key in (
                    "merchant_product_id",
                    "ean",
                    "gtin",
                )
            )
        ]

        media = product.get("media", {})
        image_url = str(media.get("image_url") or "").strip()
        image_status = str(
            media.get("image_status") or ""
        ).strip()
        image_ready = bool(image_url) and (
            image_status in APPROVED_IMAGE_STATUSES
        )

        blockers = []
        if not image_ready:
            blockers.append("approved_image_missing")
        if not fresh_affiliate_offers:
            blockers.append("fresh_affiliate_offer_missing")
        if product.get("community", {}).get("provisional"):
            blockers.append("community_data_provisional")
        if not product_offers:
            blockers.append("no_integrated_merchant_offer")
        if not resolved_mappings:
            blockers.append("no_resolved_merchant_mapping")

        rows.append(
            {
                "product_id": product_id,
                "candidate_id": product.get("candidate_id"),
                "batch": product.get("batch"),
                "brand": product.get("brand"),
                "name": product.get("name"),
                "target_groups": target_groups,
                "declared_merchant_coverage_count": int(
                    product.get("commerce", {}).get(
                        "merchant_coverage_count",
                        0,
                    )
                    or 0
                ),
                "integrated_offer_count": len(product_offers),
                "affiliate_offer_count": len(affiliate_offers),
                "fresh_affiliate_offer_count": len(
                    fresh_affiliate_offers
                ),
                "mapping_count": len(product_mappings),
                "resolved_mapping_count": len(
                    resolved_mappings
                ),
                "approved_image_ready": image_ready,
                "provisional_community_data": bool(
                    product.get("community", {}).get(
                        "provisional"
                    )
                ),
                "blockers": blockers,
            }
        )

    blocker_counts = Counter(
        blocker
        for row in rows
        for blocker in row["blockers"]
    )

    rows.sort(
        key=lambda row: (
            len(row["blockers"]),
            -row["fresh_affiliate_offer_count"],
            -row["integrated_offer_count"],
            -row["resolved_mapping_count"],
            -row["declared_merchant_coverage_count"],
            str(row["brand"] or "").casefold(),
            str(row["name"] or "").casefold(),
        )
    )

    return {
        "generated_at": now.astimezone(UTC).isoformat(),
        "live_fragrance_count": len(live_products),
        "staged_fragrance_count": len(staged_products),
        "live_audience_counts": dict(
            sorted(live_audience.items())
        ),
        "staged_audience_counts": dict(
            sorted(staged_audience.items())
        ),
        "integrated_offer_count": len(offers),
        "integrated_affiliate_offer_count": sum(
            1
            for offer in offers
            if str(offer.get("affiliate_url") or "").strip()
        ),
        "resolved_mapping_count": sum(
            1
            for mapping in mappings
            if any(
                str(mapping.get(key) or "").strip()
                for key in (
                    "merchant_product_id",
                    "ean",
                    "gtin",
                )
            )
        ),
        "staged_with_integrated_offer": sum(
            1 for row in rows if row["integrated_offer_count"]
        ),
        "staged_with_fresh_affiliate_offer": sum(
            1
            for row in rows
            if row["fresh_affiliate_offer_count"]
        ),
        "staged_with_approved_image": sum(
            1 for row in rows if row["approved_image_ready"]
        ),
        "blocker_counts": dict(
            sorted(
                blocker_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report the difference between researched merchant coverage "
            "and merchant data actually integrated into SCENTAI."
        )
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
    )
    parser.add_argument(
        "--offers",
        type=Path,
        default=DEFAULT_OFFERS,
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=DEFAULT_MAPPINGS,
    )
    parser.add_argument(
        "--max-offer-age-hours",
        type=float,
        default=72.0,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 100:
        parser.error("--limit must be between 1 and 100")

    report = build_merchant_coverage_report(
        load_json(args.staging),
        load_json(args.catalog),
        load_json(args.offers),
        load_json(args.mappings),
        now=datetime.now(UTC),
        max_offer_age_hours=args.max_offer_age_hours,
    )

    if args.output is not None:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.output.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(
        "SCENTAI merchant coverage | "
        f"live={report['live_fragrance_count']} | "
        f"staged={report['staged_fragrance_count']} | "
        f"staged_integrated={report['staged_with_integrated_offer']} | "
        f"staged_affiliate_ready="
        f"{report['staged_with_fresh_affiliate_offer']} | "
        f"staged_images="
        f"{report['staged_with_approved_image']}"
    )
    print(
        "Live audience | "
        + " | ".join(
            f"{key}={value}"
            for key, value in report[
                "live_audience_counts"
            ].items()
        )
    )
    print(
        "Staged audience | "
        + " | ".join(
            f"{key}={value}"
            for key, value in report[
                "staged_audience_counts"
            ].items()
        )
    )

    print("Top integration gaps:")
    for row in report["rows"][: args.limit]:
        blockers = ", ".join(row["blockers"]) or "-"
        print(
            f"  {row['product_id']} | "
            f"researched_merchants="
            f"{row['declared_merchant_coverage_count']} | "
            f"integrated={row['integrated_offer_count']} | "
            f"affiliate={row['fresh_affiliate_offer_count']} | "
            f"mappings={row['resolved_mapping_count']} | "
            f"{blockers}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
