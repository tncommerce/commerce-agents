"""Review up to 20 *unpublished* DUFYND fragrances against one official Awin feed.

Staging identity/name matches are DISCOVERY only. Never infer GTIN, size,
stock, price freshness, coupon eligibility, image rights outside the existing
advertiser programme, or actual affiliate-link performance from them.
Reuses the existing byte-bound, secret-filtered Awin source exporter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from retail.api.merchant_feed_reader import read_merchant_feed_rows  # noqa: E402
from scripts.export_dufynd_awin_photo_offer_review import build_review  # noqa: E402
from scripts.export_dufynd_awin_public_photo_gaps import norm  # noqa: E402

MAX_PROFILES = 20
MAX_SKUS_PER_PROFILE = 10
MAX_TOTAL_SKUS = 80
SKU = re.compile(r"[0-9]{1,16}")


def build_staging_review(
    rows: list[dict],
    metadata: dict,
    feed_bytes: bytes,
    secret: str,
    staging: dict,
    published: dict,
) -> dict:
    if not (
        metadata.get("source") == "awin_product_feed_list"
        and metadata.get("advertiser_id") == "31081"
        and metadata.get("feed_id") == "91379"
        and metadata.get("joined") is True
        and metadata.get("membership_status") == "active"
        and metadata.get("downloaded") is True
        and metadata.get("download_sha256") == hashlib.sha256(feed_bytes).hexdigest()
        and metadata.get("downloaded_bytes") == len(feed_bytes)
        and secret
    ):
        raise ValueError("current_official_feed_identity_or_bytes_required")
    if staging.get("status") != "staging_only_not_loaded_by_live_storefront":
        raise ValueError("staging_source_not_private")

    published_ids = {x.get("product_id") for x in published.get("products", [])}
    unpublished = [
        p for p in staging.get("products", [])
        if isinstance(p, dict) and p.get("product_id") not in published_ids
    ]
    if len(unpublished) < MAX_PROFILES:
        raise ValueError("not_enough_unpublished_profiles_for_bounded_review")
    batch = unpublished[:MAX_PROFILES]
    if len({p.get("product_id") for p in batch}) != MAX_PROFILES:
        raise ValueError("duplicate_or_missing_staging_product_id")

    by_sku: dict[str, set[str]] = {}
    scope = []
    for product in batch:
        identity = norm(str(product.get("brand") or "")) | norm(str(product.get("name") or ""))
        if not identity or not isinstance(product.get("volume_ml"), int):
            raise ValueError("staging_identity_incomplete")
        found = sorted({
            str(row.get("merchant_product_id"))
            for row in rows
            if isinstance(row, dict)
            and SKU.fullmatch(str(row.get("merchant_product_id") or ""))
            and identity <= norm(str(row.get("product_name") or ""))
        })
        ambiguous = len(found) > MAX_SKUS_PER_PROFILE
        allowed = [] if ambiguous else found
        for sku in allowed:
            by_sku.setdefault(sku, set()).add(product["product_id"])
        scope.append({
            "product_id": product["product_id"],
            "brand": product["brand"],
            "name": product["name"],
            "concentration": product.get("concentration"),
            "volume_ml": product["volume_ml"],
            "matched_row_sku_count": len(found),
            "ambiguous_name_hold": ambiguous,
            "status": "NAME_LEADS_ONLY" if allowed else
                      "AMBIGUOUS_NAME_HOLD" if ambiguous else "NO_SOURCE_MATCH",
            "exact_variant_verified": False,
            "owner_photo_go": False,
        })

    if len(by_sku) > MAX_TOTAL_SKUS:
        raise ValueError("source_candidate_limit_exceeded")
    if by_sku:
        review = build_review(
            rows, metadata, feed_bytes, secret,
            targets={sku: None for sku in sorted(by_sku)},
        )
        selected = []
        for item in review["rows"]:
            item["candidate_staging_product_ids"] = sorted(
                by_sku[item["merchant_product_id"]]
            )
            # A feed search price or old 'last_updated' is not an audited
            # 72-hour checked customer total. No price is exported here.
            safe = item.get("fields", {})
            item["fields"] = {
                k: safe[k] for k in (
                    "aw_product_id", "merchant_product_id", "product_name",
                    "merchant_deep_link", "aw_deep_link", "merchant_image_url",
                    "gtin", "ean", "size", "volume",
                ) if k in safe
            }
            item["exact_concentration_and_size_verified"] = False
            item["offer_activated"] = False
            item["image_publication_allowed"] = False
            selected.append(item)
        feed = review["feed"]
    else:
        selected = []
        feed = {
            k: metadata[k] for k in (
                "checked_at", "source", "advertiser_id", "feed_id",
                "membership_status", "joined", "downloaded",
                "downloaded_bytes", "download_sha256",
            ) if k in metadata
        }

    return {
        "schema_version": 1,
        "status": "UNPUBLISHED_STAGING_DISCOVERY_ONLY_NOT_APPROVED",
        "feed": feed,
        "public_product_count_excluded": len(published_ids),
        "staging_profiles_reviewed": len(batch),
        "name_matched_sku_count": len(by_sku),
        "scope": scope,
        "rows": selected,
        "source_images_downloaded": 0,
        "verified_photo_variants": 0,
        "approved_new_images": 0,
        "approved_new_offers": 0,
        "affiliate_clickouts": 0,
        "production_mutations": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    try:
        source = args.feed.read_bytes()
        report = build_staging_review(
            read_merchant_feed_rows(args.feed),
            json.loads(args.metadata.read_text(encoding="utf-8")),
            source,
            os.environ.get("AWIN_DATA_FEED_API_KEY", ""),
            json.loads((ROOT / "examples/retail/data/scentai_catalog_staging.json").read_text()),
            json.loads((ROOT / "examples/retail/storefront-web/lib/generated/public-fragrances.json").read_text()),
        )
    except Exception:
        print("staging_source_review_failed_closed", file=sys.stderr)
        return 2
    print("DUFYND_AWIN_STAGING_REVIEW=" + json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
