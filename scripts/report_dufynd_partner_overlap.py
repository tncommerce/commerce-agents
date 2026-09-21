from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_CATALOG = DATA_DIR / "catalog.json"
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_MAPPINGS = DATA_DIR / "merchant_product_mappings.json"
DEFAULT_OFFERS = DATA_DIR / "merchant_offers.json"
DEFAULT_PARTNERS = DATA_DIR / "merchant_partners.json"
DEFAULT_RELEASE_GLOB = "scentai_release_batch_*.json"

APPROVED_IMAGE_STATUSES = {
    "approved",
    "approved_manual",
    "approved_feed",
    "approved_manufacturer",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_merchant(value: str | None) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized.endswith("-de"):
        return normalized[:-3]
    return normalized


def build_release_index(releases: list[dict]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for release in releases:
        release_id = str(release.get("release_id") or "").strip()
        if not release_id:
            continue
        for product_id in release.get("product_ids", []):
            normalized = str(product_id or "").strip()
            if normalized:
                index.setdefault(normalized, []).append(release_id)
    return index


def live_fragrances(catalog: dict) -> dict[str, dict]:
    return {
        str(product.get("product_id") or ""): product
        for product in catalog.get("products", [])
        if str(product.get("product_id") or "").startswith("SC-")
        and product.get("category") == "fragrance"
        and product.get("in_stock") is not False
    }


def staged_fragrances(staging: dict) -> dict[str, dict]:
    return {
        str(product.get("product_id") or ""): product
        for product in staging.get("products", [])
        if str(product.get("product_id") or "").strip()
    }


def image_ready_for_live(product: dict) -> bool:
    return bool(str(product.get("image_url") or "").strip())


def image_ready_for_staging(product: dict) -> bool:
    media = product.get("media", {})
    image_url = str(media.get("image_url") or "").strip()
    image_status = str(media.get("image_status") or "").strip()
    return bool(image_url) and image_status in APPROVED_IMAGE_STATUSES


def build_partner_overlap_report(
    *,
    catalog: dict,
    staging: dict,
    mappings_payload: dict,
    offers_payload: dict,
    partners_payload: dict,
    releases: list[dict],
    merchant: str,
) -> dict[str, Any]:
    merchant_key = canonical_merchant(merchant)
    live = live_fragrances(catalog)
    staged = staged_fragrances(staging)
    release_index = build_release_index(releases)

    partners = partners_payload.get("partners", [])
    partner = next(
        (
            row
            for row in partners
            if canonical_merchant(row.get("merchant_id")) == merchant_key
            or canonical_merchant(row.get("merchant_name")) == merchant_key
        ),
        None,
    )

    mappings = [
        row
        for row in mappings_payload.get("mappings", [])
        if canonical_merchant(row.get("merchant")) == merchant_key
    ]
    offers = [
        row
        for row in offers_payload.get("offers", [])
        if canonical_merchant(row.get("merchant_id")) == merchant_key
    ]

    offers_by_product: dict[str, list[dict]] = {}
    for offer in offers:
        product_id = str(offer.get("product_id") or "").strip()
        if product_id:
            offers_by_product.setdefault(product_id, []).append(offer)

    rows: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()

    for mapping in mappings:
        product_id = str(mapping.get("product_id") or "").strip()
        live_product = live.get(product_id)
        staged_product = staged.get(product_id)
        product_offers = offers_by_product.get(product_id, [])
        affiliate_offers = [
            offer for offer in product_offers if str(offer.get("affiliate_url") or "").strip()
        ]

        if live_product is not None:
            catalog_state = "live"
            image_ready = image_ready_for_live(live_product)
            brand = live_product.get("brand")
            name = live_product.get("name")
        elif staged_product is not None:
            catalog_state = "staged"
            image_ready = image_ready_for_staging(staged_product)
            brand = staged_product.get("brand")
            name = staged_product.get("name")
        else:
            catalog_state = "unknown"
            image_ready = False
            brand = None
            name = None

        blockers: list[str] = []
        if catalog_state == "unknown":
            blockers.append("product_not_in_live_or_staging_catalog")
        if not image_ready:
            blockers.append("approved_image_missing")
        if not affiliate_offers:
            blockers.append("product_affiliate_offer_missing")

        blocker_counts.update(blockers)

        rows.append(
            {
                "product_id": product_id,
                "brand": brand,
                "name": name,
                "catalog_state": catalog_state,
                "release_ids": release_index.get(product_id, []),
                "merchant_product_id": mapping.get("merchant_product_id"),
                "ean": mapping.get("ean"),
                "gtin": mapping.get("gtin"),
                "integrated_offer_count": len(product_offers),
                "affiliate_offer_count": len(affiliate_offers),
                "approved_image_ready": image_ready,
                "blockers": blockers,
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row["catalog_state"] == "live" else 1,
            len(row["blockers"]),
            str(row["brand"] or "").casefold(),
            str(row["name"] or "").casefold(),
        )
    )

    return {
        "merchant": merchant_key,
        "partner_status": partner.get("status") if partner else None,
        "partner_tracking_url_configured": bool(
            str((partner or {}).get("affiliate_url") or "").strip()
        ),
        "mapped_product_count": len(rows),
        "mapped_live_product_count": sum(1 for row in rows if row["catalog_state"] == "live"),
        "mapped_staged_product_count": sum(1 for row in rows if row["catalog_state"] == "staged"),
        "product_affiliate_offer_count": sum(1 for row in rows if row["affiliate_offer_count"] > 0),
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
            "Report DUFYND catalog overlap and product-level readiness for one affiliate merchant."
        )
    )
    parser.add_argument("--merchant", default="perfumetrader")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS)
    parser.add_argument("--offers", type=Path, default=DEFAULT_OFFERS)
    parser.add_argument("--partners", type=Path, default=DEFAULT_PARTNERS)
    parser.add_argument("--release-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    releases = [load_json(path) for path in sorted(args.release_dir.glob(DEFAULT_RELEASE_GLOB))]
    report = build_partner_overlap_report(
        catalog=load_json(args.catalog),
        staging=load_json(args.staging),
        mappings_payload=load_json(args.mappings),
        offers_payload=load_json(args.offers),
        partners_payload=load_json(args.partners),
        releases=releases,
        merchant=args.merchant,
    )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(
        "DUFYND partner overlap | "
        f"merchant={report['merchant']} | "
        f"partner_status={report['partner_status']} | "
        f"mapped={report['mapped_product_count']} | "
        f"live={report['mapped_live_product_count']} | "
        f"staged={report['mapped_staged_product_count']} | "
        f"product_affiliate_offers={report['product_affiliate_offer_count']}"
    )

    for row in report["rows"]:
        blockers = ", ".join(row["blockers"]) or "-"
        releases_label = ",".join(row["release_ids"]) or "-"
        print(
            f"  {row['catalog_state'].upper()} | "
            f"{row['product_id']} | releases={releases_label} | "
            f"merchant_product_id={row['merchant_product_id'] or '-'} | "
            f"affiliate_offers={row['affiliate_offer_count']} | "
            f"blockers={blockers}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
