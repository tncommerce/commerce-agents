"""Offline discovery of *candidate* exact-variant fields in an Awin Enhanced feed.

No token, network call, offer activation, tracking-link construction or DB write.
A successful result still needs original publisher/feed authorization and an
independently certified per-SKU observation time before prepare_batch().
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from scripts.dufynd_commerce_gates import approved_affiliate_route

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/retail/data"
MAX_SOURCE_BYTES = 64_000_000
MAX_ROWS = 250_000
MAX_LINE_BYTES = 256_000
MAX_OFFERS = 50
MONEY = re.compile(r"^(\d{1,6}(?:\.\d{1,2})?) EUR$")


def money(value: Any, *, allow_zero: bool = False) -> Decimal | None:
    if not isinstance(value, str):
        return None
    match = MONEY.fullmatch(value)
    if match is None:
        return None
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    if (amount < 0 if allow_zero else amount <= 0) or amount > 100_000:
        return None
    return amount


def read_selected_jsonl(path: Path, sku_ids: set[str]) -> tuple[dict[str, list[dict]], str, int]:
    """Hash every source byte, keeping only bound merchant IDs in memory."""
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("enhanced_source_too_large")
    digest = hashlib.sha256()
    selected: dict[str, list[dict]] = {}
    count = 0
    with path.open("rb") as stream:
        for raw in stream:
            digest.update(raw)
            count += 1
            if count > MAX_ROWS or len(raw) > MAX_LINE_BYTES:
                raise ValueError("enhanced_source_bounds_exceeded")
            if not raw.strip():
                continue
            try:
                row = json.loads(
                    raw, parse_constant=lambda _: (_ for _ in ()).throw(
                        ValueError("non_finite_enhanced_value")
                    )
                )
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError("invalid_enhanced_source_line") from exc
            if not isinstance(row, dict):
                raise ValueError("invalid_enhanced_source_record")
            mid = row.get("id")
            if isinstance(mid, str) and mid in sku_ids:
                hits = selected.setdefault(mid, [])
                if len(hits) < 2:
                    hits.append(row)
    return selected, digest.hexdigest(), count


def _variant_reason(
    source: dict[str, Any], offer: dict[str, Any],
    mappings: list[dict[str, Any]], products: list[dict[str, Any]],
) -> str:
    source_id = offer.get("merchant_product_id")
    product_id = offer.get("product_id")
    matching = [
        row for row in mappings
        if row.get("merchant_product_id") == source_id
        and row.get("product_id") == product_id
        and row.get("merchant") == "top-parfuemerie"
        and row.get("mapping_status") == "verified_current_variant"
    ]
    products_matching = [p for p in products if p.get("product_id") == product_id]
    if len(matching) != 1 or len(products_matching) != 1:
        return "CANONICAL_VARIANT_NOT_UNAMBIGUOUS"
    actual_gtin = source.get("gtin")
    expected = matching[0].get("gtin") or matching[0].get("ean")
    if not isinstance(actual_gtin, str) or actual_gtin != expected:
        return "GTIN_MISSING_OR_DIFFERENT"
    attrs = products_matching[0].get("attributes") or {}
    volume = attrs.get("volume_ml")
    if not isinstance(volume, str) or not volume.isdigit():
        return "CANONICAL_VOLUME_UNKNOWN"
    sizes = [source[key] for key in ("size", "unit_pricing_measure") if source.get(key)]
    if not sizes or any(
        not isinstance(size, str) or
        re.fullmatch(rf"{volume}\s*ml", size.strip(), flags=re.IGNORECASE) is None
        for size in sizes
    ):
        return "SIZE_MISSING_OR_DIFFERENT"
    if "brand" in source and source["brand"] != products_matching[0].get("brand"):
        return "BRAND_NEEDS_REVIEW"
    if source.get("availability") != "in_stock":
        return "EXACT_VARIANT_NOT_CONFIRMED_IN_STOCK"
    if source.get("sale_price") or source.get("sale_price_effective_date"):
        return "PROMOTIONAL_PRICE_NEEDS_APPROVAL"
    if money(source.get("price")) is None:
        return "EUR_PRICE_MISSING_OR_INVALID"
    shippings = source.get("shipping")
    if isinstance(shippings, dict):
        shippings = [shippings]
    if not isinstance(shippings, list):
        return "DE_SHIPPING_MISSING"
    de = [s for s in shippings if isinstance(s, dict) and s.get("country") == "DE"]
    if len(de) != 1:
        return "DE_SHIPPING_MISSING_OR_AMBIGUOUS"
    shipment = de[0]
    # A regional or postal-code-specific price is not an all-Germany total.
    if any(shipment.get(k) for k in ("region", "postal_code", "location_id")):
        return "DE_SHIPPING_REGION_SPECIFIC"
    if money(shipment.get("price"), allow_zero=True) is None:
        return "DE_SHIPPING_PRICE_UNCONFIRMED"
    return "ENHANCED_FIELDS_PRESENT_SOURCE_REVIEW_ONLY"


def review_enhanced_candidates(
    canonical_offers: list[dict[str, Any]],
    partners: dict[str, Any],
    mappings: dict[str, Any],
    catalog: dict[str, Any],
    *,
    selected_rows: dict[str, list[dict]],
    publisher_source: dict[str, Any],
    original_digest: str,
    now: datetime,
) -> dict[str, Any]:
    """Never turn a publisher-provided candidate into a certified purchase."""
    if now.tzinfo is None:
        raise ValueError("timezone_required")
    if (
        publisher_source.get("publisher_id") != "3099222"
        or publisher_source.get("advertiser_id") != "31081"
        or publisher_source.get("source_type") != "awin_enhanced_retail_jsonl"
        or publisher_source.get("download_sha256") != original_digest
        or re.fullmatch(r"[0-9a-f]{64}", str(original_digest)) is None
    ):
        raise ValueError("enhanced_feed_provenance_not_attested")
    observed = publisher_source.get("downloaded_at")
    if not isinstance(observed, str):
        raise ValueError("feed_download_time_missing")
    try:
        downloaded = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        if downloaded.tzinfo is None:
            raise ValueError()
    except ValueError as exc:
        raise ValueError("invalid_feed_download_timestamp") from exc
    seconds_old = (now.astimezone(UTC) - downloaded.astimezone(UTC)).total_seconds()
    if not 0 <= seconds_old <= 72 * 3600:
        raise ValueError("feed_download_too_old_or_future")

    candidates = [
        o for o in canonical_offers if o.get("merchant_id") == "top-parfuemerie"
    ]
    ids = [o.get("offer_id") for o in candidates]
    skus = [o.get("merchant_product_id") for o in candidates]
    if not 1 <= len(candidates) <= MAX_OFFERS or any(not isinstance(x, str) for x in ids + skus):
        raise ValueError("canonical_scope_invalid")
    if len(set(ids)) != len(ids) or len(set(skus)) != len(skus):
        raise ValueError("canonical_offer_or_sku_ambiguous")

    results: list[dict[str, str]] = []
    for offer in candidates:
        sku = offer["merchant_product_id"]
        matching = selected_rows.get(sku, [])
        if not approved_affiliate_route(offer, partners):
            reason = "AFFILIATE_ROUTE_NOT_APPROVED"
        elif len(matching) == 0:
            reason = "EXACT_MERCHANT_SKU_ABSENT"
        elif len(matching) != 1:
            reason = "DUPLICATE_ENHANCED_SKU"
        else:
            reason = _variant_reason(
                matching[0], offer, mappings.get("mappings", []),
                catalog.get("products", []),
            )
        results.append({
            "offer_id": offer["offer_id"],
            "status": (
                "FIELD_COMPLETE_REVIEW_ONLY"
                if reason == "ENHANCED_FIELDS_PRESENT_SOURCE_REVIEW_ONLY"
                else "BLOCKED_SOURCE_FIELDS"
            ),
            "reason": reason,
        })
    return {
        "schema_version": 1,
        "status": "ENHANCED_FEED_FIELD_TRIAGE_ONLY_NOT_CERTIFIED",
        "offer_count": len(results),
        "source_rows_authenticated_by_this_script": False,
        "per_sku_price_timestamp_verified": False,
        "not_a_purchase_price_certificate": True,
        "public_offer_activations": 0,
        "database_writes": 0,
        "affiliate_clickouts": 0,
        "counts": {
            "FIELD_COMPLETE_REVIEW_ONLY": sum(
                r["status"] == "FIELD_COMPLETE_REVIEW_ONLY" for r in results
            ),
            "BLOCKED_SOURCE_FIELDS": sum(
                r["status"] == "BLOCKED_SOURCE_FIELDS" for r in results
            ),
        },
        "items": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, required=True, help="Local JSONL, never a URL")
    parser.add_argument("--source-receipt", type=Path, required=True)
    args = parser.parse_args()
    offers = json.loads((DATA / "merchant_offers.json").read_text(encoding="utf-8"))["offers"]
    partners = json.loads((DATA / "merchant_partners.json").read_text(encoding="utf-8"))
    mapping = json.loads((DATA / "merchant_product_mappings.json").read_text(encoding="utf-8"))
    catalog = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
    skus = {str(o["merchant_product_id"]) for o in offers if o.get("merchant_id") == "top-parfuemerie"}
    rows, digest, row_count = read_selected_jsonl(args.feed, skus)
    receipt = json.loads(args.source_receipt.read_text(encoding="utf-8"))
    report = review_enhanced_candidates(
        offers, partners, mapping, catalog,
        selected_rows=rows, publisher_source=receipt,
        original_digest=digest, now=datetime.now(UTC),
    )
    report["source_rows_scanned"] = row_count
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
