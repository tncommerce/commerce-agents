from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.qa_scentai_staging import run_qa


DATA_DIR = Path("examples/retail/data")
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_CATALOG = DATA_DIR / "catalog.json"
DEFAULT_OFFERS = DATA_DIR / "merchant_offers.json"

APPROVED_IMAGE_STATUSES = {
    "approved_feed_image",
    "approved_manufacturer_image",
    "approved_licensed_image",
}
PROFILE_AXES = (
    "freshness",
    "sweetness",
    "woodiness",
    "spiciness",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def offer_age_hours(offer: dict, *, now: datetime) -> float:
    updated = parse_timestamp(str(offer["last_updated_at"]))
    return max((now - updated).total_seconds() / 3600.0, 0.0)


def eligible_affiliate_offers(
    offers: list[dict],
    *,
    product_id: str,
    now: datetime,
    max_age_hours: float,
) -> list[dict]:
    eligible = []

    for offer in offers:
        if offer.get("product_id") != product_id:
            continue
        if not offer.get("in_stock"):
            continue
        if not str(offer.get("affiliate_url") or "").strip():
            continue

        try:
            age = offer_age_hours(offer, now=now)
        except (KeyError, TypeError, ValueError):
            continue

        if age > max_age_hours:
            continue

        eligible.append(offer)

    def sort_key(offer: dict) -> tuple[Any, ...]:
        shipping = offer.get("shipping_cost")
        known_total = shipping is not None

        try:
            price = float(offer["price"])
        except (KeyError, TypeError, ValueError):
            price = float("inf")

        total = (
            price + float(shipping)
            if known_total
            else price
        )

        return (
            0 if known_total else 1,
            total,
            offer_age_hours(offer, now=now),
            str(offer.get("merchant_name") or "").casefold(),
        )

    return sorted(eligible, key=sort_key)


def recommendation_scores(product: dict) -> dict[str, int]:
    profile = (
        product.get("fragrance_profile", {})
        .get("recommendation_profile", {})
    )
    raw_scores = profile.get("scores", {})

    scores: dict[str, int] = {}
    for axis in PROFILE_AXES:
        value = raw_scores.get(axis)
        if isinstance(value, bool):
            continue
        if not isinstance(value, (int, float)):
            continue

        numeric = int(round(value))
        if 1 <= numeric <= 10:
            scores[axis] = numeric

    return scores


def promotion_blockers(
    product: dict,
    offers: list[dict],
    *,
    now: datetime,
    max_offer_age_hours: float = 72.0,
    allow_provisional: bool = False,
) -> list[str]:
    blockers = []

    product_id = str(product.get("product_id") or "").strip()
    if not product_id:
        blockers.append("missing_product_id")

    community = product.get("community", {})
    if community.get("rating_10") is None:
        blockers.append("missing_community_rating")

    if community.get("provisional") and not allow_provisional:
        blockers.append("provisional_community_data")

    media = product.get("media", {})
    image_url = str(media.get("image_url") or "").strip()
    image_status = str(media.get("image_status") or "").strip()

    if not image_url:
        blockers.append("missing_approved_image")
    elif image_status not in APPROVED_IMAGE_STATUSES:
        blockers.append("image_not_approved")

    scores = recommendation_scores(product)
    if set(scores) != set(PROFILE_AXES):
        blockers.append("missing_recommendation_profile")

    target_groups = (
        product.get("classification", {})
        .get("target_groups", [])
    )
    if not isinstance(target_groups, list) or not target_groups:
        blockers.append("missing_target_group")
    elif not all(
        isinstance(group, str) and group.strip()
        for group in target_groups
    ):
        blockers.append("invalid_target_group")

    if product_id:
        affiliate_offers = eligible_affiliate_offers(
            offers,
            product_id=product_id,
            now=now,
            max_age_hours=max_offer_age_hours,
        )
        if not affiliate_offers:
            blockers.append("missing_current_affiliate_offer")

    return blockers


def full_product_name(product: dict) -> str:
    brand = str(product["brand"]).strip()
    name = str(product["name"]).strip()

    if name.casefold().startswith(brand.casefold() + " "):
        return name
    return f"{brand} {name}"


def build_title(product: dict) -> str:
    display = full_product_name(product)
    concentration = str(product["concentration"]).strip()
    volume = int(product["volume_ml"])

    if product["name"].casefold().endswith(
        " " + concentration.casefold().split()[0]
    ):
        return f"{display} {volume} ml"

    return f"{display} {concentration} {volume} ml"


def build_catalog_product(
    staged: dict,
    *,
    best_offer: dict,
) -> dict:
    community = staged["community"]
    profile = staged["fragrance_profile"]
    scores = recommendation_scores(staged)
    target_groups = staged.get(
        "classification",
        {},
    ).get("target_groups", [])
    accords = profile.get("community_accords", [])
    key_notes = profile.get("key_notes", [])

    rating_10 = float(community["rating_10"])

    attributes = {
        "canonical_name": str(staged["name"]),
        "community_rating_10": str(community["rating_10"]),
        "rating_source": str(community.get("source") or ""),
        "volume_ml": str(staged["volume_ml"]),
        "concentration": str(staged["concentration"]),
        "target_group": ", ".join(target_groups),
        "audience_lean": str(
            staged.get("classification", {}).get(
                "audience_lean"
            )
            or ""
        ),
        "main_accords": ", ".join(accords),
        "key_notes": ", ".join(key_notes),
        "freshness": str(scores["freshness"]),
        "sweetness": str(scores["sweetness"]),
        "woodiness": str(scores["woodiness"]),
        "spiciness": str(scores["spiciness"]),
        "profile_source": str(
            profile.get(
                "recommendation_profile",
                {},
            ).get("source")
            or ""
        ),
        "longevity": (
            ""
            if community.get("longevity_10") is None
            else str(community["longevity_10"])
        ),
        "projection": (
            ""
            if community.get("projection_10") is None
            else str(community["projection_10"])
        ),
        "price_source": "current_merchant_offer",
        "market_price_eur": str(best_offer["price"]),
        "price_checked_at": str(best_offer["last_updated_at"]),
        "promotion_source": "scentai_catalog_staging",
    }

    labels = []
    for accord in accords[:5]:
        if accord not in labels:
            labels.append(accord)

    description_accords = ", ".join(accords[:3])
    if description_accords:
        short_description = (
            f"{full_product_name(staged)} ist ein "
            f"{description_accords} geprägter Duft."
        )
    else:
        short_description = (
            f"{full_product_name(staged)} ist ein "
            f"{staged['concentration']} Duft."
        )

    return {
        "product_id": staged["product_id"],
        "title": build_title(staged),
        "image_url": staged["media"]["image_url"],
        "brand": staged["brand"],
        "price": float(best_offer["price"]),
        "currency": str(best_offer.get("currency") or "EUR"),
        "rating": round(rating_10 / 2, 1),
        "review_count": int(community.get("rating_count") or 0),
        "category": "fragrance",
        "labels": labels,
        "attributes": attributes,
        "in_stock": True,
        "short_description": short_description,
    }


def choose_products(
    staging_products: list[dict],
    *,
    product_ids: list[str],
    batch: int | None,
    limit: int,
) -> list[dict]:
    selected_ids = {
        product_id.strip()
        for product_id in product_ids
        if product_id.strip()
    }

    if not selected_ids and batch is None:
        raise ValueError(
            "Select at least one --product-id or provide --batch"
        )

    selected = []
    for product in staging_products:
        if selected_ids and product.get("product_id") in selected_ids:
            selected.append(product)
            continue
        if (
            batch is not None
            and int(product.get("batch") or 0) == batch
        ):
            selected.append(product)

    if selected_ids:
        found = {
            product["product_id"]
            for product in selected
        }
        missing = sorted(selected_ids - found)
        if missing:
            raise ValueError(
                "Unknown staged product_id values: "
                + ", ".join(missing)
            )

    return selected[:limit]


def promotion_plan(
    staging: dict,
    catalog: dict,
    offers_payload: dict,
    *,
    product_ids: list[str],
    batch: int | None,
    limit: int,
    now: datetime,
    max_offer_age_hours: float,
    allow_provisional: bool,
) -> dict:
    staged_products = staging.get("products", [])
    offers = offers_payload.get(
        "offers",
        offers_payload if isinstance(offers_payload, list) else [],
    )
    live_ids = {
        product.get("product_id")
        for product in catalog.get("products", [])
    }

    selected = choose_products(
        staged_products,
        product_ids=product_ids,
        batch=batch,
        limit=limit,
    )

    rows = []
    ready_products = []

    for product in selected:
        product_id = product["product_id"]
        blockers = promotion_blockers(
            product,
            offers,
            now=now,
            max_offer_age_hours=max_offer_age_hours,
            allow_provisional=allow_provisional,
        )

        if product_id in live_ids:
            blockers.append("already_live")

        eligible = eligible_affiliate_offers(
            offers,
            product_id=product_id,
            now=now,
            max_age_hours=max_offer_age_hours,
        )

        if not blockers:
            ready_products.append(
                build_catalog_product(
                    product,
                    best_offer=eligible[0],
                )
            )

        rows.append(
            {
                "product_id": product_id,
                "candidate_id": product.get("candidate_id"),
                "ready": not blockers,
                "blockers": blockers,
                "eligible_affiliate_offers": len(eligible),
            }
        )

    return {
        "selected_count": len(selected),
        "ready_count": len(ready_products),
        "blocked_count": len(selected) - len(ready_products),
        "rows": rows,
        "ready_products": ready_products,
    }


def write_promotions(
    catalog_path: Path,
    catalog: dict,
    ready_products: list[dict],
) -> None:
    if not ready_products:
        return

    products = list(catalog.get("products", []))
    products.extend(ready_products)

    output = {
        **catalog,
        "store_name": "SCENTAI",
        "products": products,
    }

    catalog_path.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and promote verified SCENTAI staging "
            "products into the live catalog."
        )
    )
    parser.add_argument(
        "--product-id",
        action="append",
        default=[],
        help="Specific staged product_id to validate/promote. Repeatable.",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=None,
        help="Select products from one staging batch.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of selected products per run.",
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
        "--max-offer-age-hours",
        type=float,
        default=72.0,
    )
    parser.add_argument(
        "--allow-provisional",
        action="store_true",
        help=(
            "Allow products whose community-performance data "
            "is still provisional. Off by default."
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Write ready products to catalog.json. Without "
            "this flag the command is a dry-run."
        ),
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )

    args = parser.parse_args()

    if args.limit < 1 or args.limit > 10:
        parser.error("--limit must be between 1 and 10")

    staging = load_json(args.staging)
    catalog = load_json(args.catalog)
    offers = load_json(args.offers)

    try:
        plan = promotion_plan(
            staging,
            catalog,
            offers,
            product_ids=args.product_id,
            batch=args.batch,
            limit=args.limit,
            now=datetime.now(UTC),
            max_offer_age_hours=args.max_offer_age_hours,
            allow_provisional=args.allow_provisional,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.write:
        if plan["blocked_count"]:
            parser.error(
                "Refusing partial promotion: one or more "
                "selected products are blocked. Run dry-run "
                "and resolve every blocker first."
            )

        staging_qa = asyncio.run(
            run_qa(args.staging)
        )
        if not staging_qa["passed"]:
            preview = ", ".join(
                staging_qa["issues"][:5]
            )
            parser.error(
                "Refusing live promotion because staging "
                "recommendation QA failed"
                + (f": {preview}" if preview else "")
            )

        write_promotions(
            args.catalog,
            catalog,
            plan["ready_products"],
        )

    output = {
        key: value
        for key, value in plan.items()
        if key != "ready_products"
    }
    output["mode"] = "WRITE" if args.write else "DRY-RUN"

    if args.machine_readable:
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(
            f"Mode: {output['mode']} | "
            f"Selected: {plan['selected_count']} | "
            f"Ready: {plan['ready_count']} | "
            f"Blocked: {plan['blocked_count']}"
        )
        for row in plan["rows"]:
            status = "READY" if row["ready"] else "BLOCKED"
            blockers = ", ".join(row["blockers"]) or "-"
            print(
                f"{status}: {row['product_id']} | "
                f"affiliate offers: "
                f"{row['eligible_affiliate_offers']} | "
                f"blockers: {blockers}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
