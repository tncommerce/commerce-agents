"""Validate historical DUFYND live/product merchant evidence without network or writes.

The snapshot documents facts seen on a specific date. Even a valid in-stock
merchant page is NOT Awin approval, current network price or a publishable offer.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

DATA = Path("examples/retail/data")
GENERATED = Path("examples/retail/storefront-web/lib/generated")
SNAPSHOT = DATA / "dufynd_live_commerce_evidence_20261102.json"
PUBLIC_ORIGIN = "https://dufynd.de"
STOCK_STATES = {"MERCHANT_PAGE_IN_STOCK", "MERCHANT_PAGE_OUT_OF_STOCK"}
PAGE_FIELDS = {
    "product_id",
    "slug",
    "url",
    "http_status",
    "canonical",
    "robots",
    "photo_state",
    "offers_section_rendered",
    "html_sha256",
    "html_bytes",
}
MERCHANT_FIELDS = {
    "product_id",
    "merchant_id",
    "merchant_article",
    "gtin",
    "volume_ml",
    "concentration",
    "source_page_url",
    "http_status",
    "page_title",
    "observed_stock",
    "observed_at_utc",
    "html_sha256",
    "html_bytes",
    "price_published",
    "tracked_link_currently_verified",
    "merchant_offer_activated",
    "image_rights_granted",
}


def _load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _check(parsed.tzinfo is not None, "naive_source_timestamp")
    return parsed.astimezone(UTC)


def _digest(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


TOP_GALLERY_FIELDS = {
    "product_id",
    "merchant_id",
    "source_page_url",
    "merchant_product_id",
    "gtin",
    "observed_at_utc",
    "page_http_status",
    "page_html_sha256",
    "page_title",
    "variant_gallery_image_url",
    "variant_gallery_url_in_live_html",
    "og_preview_product_sku",
    "og_preview_gtin",
    "og_preview_exact_variant",
    "gift_box_source",
    "source_image_bytes_downloaded",
    "source_image_sha256",
    "exact_front_photo_visually_verified",
    "merchant_image_rights_final_approved",
    "owner_visual_approved",
    "public_photo_activation",
    "merchant_offer_activation",
}


def validate_top_gallery(evidence: dict, public_ids: set, photo_ids: set, mappings: dict) -> dict:
    review = evidence["top_parfuemerie_gallery_crawl"]
    records = review["records"]
    _check(
        review["advertiser_id"] == "31081"
        and review["feed_id"] == "91379"
        and review["source_scope"]
        == "DIRECT_PUBLIC_MERCHANT_GALLERY_VARIANT_LEADS_NOT_AWIN_FEED_OR_APPROVED_ASSETS"
        and review["image_bytes_downloaded"] == 0
        and review["rights_reuse_permission_not_sufficient_for_auto_publication"] is True
        and review["owner_visual_approval_required"] is True,
        "top_source_rights_or_feed_gate",
    )
    _check(
        review["product_page_count"] == len(records) == 4
        and len({x["product_id"] for x in records}) == 4,
        "top_gallery_scope_changed",
    )
    verified_mapping = {
        m["product_id"]: m
        for m in mappings["mappings"]
        if m.get("merchant") == "top-parfuemerie"
        and m.get("mapping_status") == "verified_current_variant"
    }
    stamp = _utc(review["observed_at_utc"])
    incorrect_og = 0
    gifts = 0
    for row in records:
        _check(set(row) == TOP_GALLERY_FIELDS, "top_gallery_unexpected_fields")
        pid = row["product_id"]
        mapping = verified_mapping.get(pid)
        _check(
            mapping is not None
            and pid in public_ids
            and pid not in photo_ids
            and row["merchant_id"] == "top-parfuemerie"
            and row["source_page_url"] == mapping.get("evidence_url")
            and row["merchant_product_id"] == mapping["merchant_product_id"]
            and row["gtin"] == mapping.get("gtin")
            and row["page_http_status"] == 200
            and _digest(row["page_html_sha256"])
            and bool(row["page_title"]),
            "top_gallery_exact_identity_mismatch",
        )
        url = urlsplit(row["variant_gallery_image_url"])
        sku = re.escape(row["merchant_product_id"])
        gtin = re.escape(row["gtin"])
        path_contract = (
            rf"/media/catalog/product/cache/[a-f0-9]{{32}}/"
            rf"[0-9]/[0-9]/{sku}_{gtin}_[0-9]{{3}}[.]png"
        )
        _check(
            url.scheme == "https"
            and url.hostname == "www.topparfuemerie.de"
            and url.username is None
            and url.password is None
            and url.query == ""
            and url.fragment == ""
            and url.port is None
            and re.fullmatch(path_contract, url.path) is not None
            and row["variant_gallery_url_in_live_html"] is True,
            "top_gallery_exact_image_url_missing",
        )
        og_exact = (
            row["og_preview_product_sku"] == row["merchant_product_id"]
            and row["og_preview_gtin"] == row["gtin"]
        )
        _check(
            row["og_preview_exact_variant"] is og_exact
            and re.fullmatch(r"[0-9]+", row["og_preview_product_sku"]) is not None
            and re.fullmatch(r"[0-9]{12,14}", row["og_preview_gtin"]) is not None,
            "top_og_preview_variant_mismatch_not_reported",
        )
        incorrect_og += int(not og_exact)
        expected_giftbox = pid == "SC-XERJOFF-NAXOS-100"
        _check(row["gift_box_source"] is expected_giftbox, "top_giftbox_not_held")
        gifts += int(expected_giftbox)
        _check(
            _utc(row["observed_at_utc"]) == stamp
            and row["source_image_bytes_downloaded"] is False
            and row["source_image_sha256"] is None
            and row["exact_front_photo_visually_verified"] is False
            and row["merchant_image_rights_final_approved"] is False
            and row["owner_visual_approved"] is False
            and row["public_photo_activation"] is False
            and row["merchant_offer_activation"] is False,
            "top_gallery_wrongly_promoted",
        )
    _check(
        incorrect_og == review["generic_og_preview_other_variant_count"] == 3
        and review["exact_gallery_variant_filename_count"] == 4
        and gifts == review["gift_box_source_hold_count"] == 1,
        "top_gallery_review_summary_mismatch",
    )
    return {
        "private_gallery_leads": len(records),
        "wrong_og_variants": incorrect_og,
        "giftbox_hold": gifts,
    }


def validate_evidence(
    evidence: dict,
    legacy: dict,
    released: dict,
    held: dict,
    originals: list,
    mappings: dict,
    *,
    now: datetime | None = None,
) -> dict:
    _check(evidence.get("schema_version") == 1, "schema_version")
    _check(
        evidence.get("status") == "HISTORICAL_READ_ONLY_EVIDENCE_NO_OFFER_ACTIVATION",
        "historical_evidence_only",
    )
    safety = evidence["safety"]
    required_true = {
        "no_product_images_downloaded",
        "no_photo_rights_granted",
        "no_offers_activated",
        "no_affiliate_tracking_link_generated",
        "no_merchant_clickouts",
        "no_runtime_price_or_stock_write",
        "no_live_publish",
        "no_new_cost",
        "source_html_not_stored",
        "not_authoritative_for_current_stock_after_expiry",
        "merchant_page_not_awin_csv",
        "no_top_parfuemerie_gallery_assets_downloaded",
        "no_wrong_og_preview_promoted",
    }
    _check(all(safety.get(key) is True for key in required_true), "unsafe_source_claim")

    originals_public = {
        p["product_id"]: p
        for p in legacy["products"]
        if not p.get("validation", {}).get("blockers")
    }
    fact_public = {p["product_id"]: p for p in released["profiles"]}
    held_ids = {p["product_id"] for p in held["profiles"]}
    photo_ids = {p["product_id"] for p in originals}
    public_ids = set(originals_public) | set(fact_public)
    _check(
        len(originals_public) == 37
        and len(fact_public) == 20
        and len(held_ids) == 21
        and len(photo_ids) == 10,
        "publication_inventory_changed",
    )
    _check(
        not (set(originals_public) & set(fact_public))
        and not (held_ids & public_ids)
        and photo_ids <= public_ids,
        "public_private_scope_overlap",
    )

    public = evidence["public_crawl"]
    pages = public["records"]
    _check(
        len(pages) == public["expected_product_count"] == 57
        and len({p["product_id"] for p in pages}) == 57
        and len({p["url"] for p in pages}) == 57
        and {p["product_id"] for p in pages} == public_ids,
        "public_exact_scope_mismatch",
    )
    _check(public["sitemap_source_url"] == PUBLIC_ORIGIN + "/sitemap.xml", "sitemap_source")
    _check(
        public["sitemap_http_request_id"] > 0
        and public["private_wave2_excluded_count"] == 21
        and public["all_http_200"] is True
        and public["all_canonical_exact"] is True
        and public["all_robots_index_follow"] is True
        and public["no_product_snippet_without_qualifying_offer"] is True,
        "public_summary_gates_changed",
    )
    _utc(public["observed_at_utc"])
    counters = {"VERIFIED_ORIGINAL": 0, "ORIGINAL_PENDING": 0, "STUDIO_HOLD": 0}
    for page in pages:
        _check(set(page) == PAGE_FIELDS, "unexpected_public_evidence_fields")
        pid = page["product_id"]
        url = page["url"]
        _check(url == PUBLIC_ORIGIN + "/duft/" + page["slug"], "public_route_mismatch")
        _check(
            re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", page["slug"]) is not None,
            "unsafe_public_slug",
        )
        _check(
            page["canonical"] == url
            and page["http_status"] == 200
            and page["robots"] == "index, follow"
            and _digest(page["html_sha256"])
            and type(page["html_bytes"]) is int
            and page["html_bytes"] > 1000,
            "public_html_proof_missing",
        )
        state = (
            "STUDIO_HOLD"
            if pid in fact_public
            else "VERIFIED_ORIGINAL"
            if pid in photo_ids
            else "ORIGINAL_PENDING"
        )
        _check(page["photo_state"] == state, "original_rights_state_inaccurate")
        _check(
            page["offers_section_rendered"] is (pid in originals_public),
            "merchant_section_scope_changed",
        )
        if pid in fact_public:
            _check(
                page["slug"] == fact_public[pid]["slug"],
                "owner_release_route_mismatch",
            )
        counters[state] += 1
    _check(
        counters == {"VERIFIED_ORIGINAL": 10, "ORIGINAL_PENDING": 27, "STUDIO_HOLD": 20}
        and counters["VERIFIED_ORIGINAL"] == public["verified_original_count"]
        and counters["ORIGINAL_PENDING"] == public["pending_original_count"]
        and counters["STUDIO_HOLD"] == public["studio_hold_count"],
        "photo_inventory_or_summary_mismatch",
    )

    merchant = evidence["perfumetrader_crawl"]
    records = merchant["merchant_source_pages"]
    _check(
        merchant["advertiser_id"] == "11672"
        and merchant["feed_id"] == "29975"
        and merchant["product_csv_schema_verified"] is False,
        "unauthorized_product_feed_assertion",
    )
    _check(
        merchant["record_count"] == len(records) == 5
        and len({x["product_id"] for x in records}) == len(records)
        and merchant["stock_observations_expire_after_hours"] == 24,
        "merchant_record_count_or_ttl",
    )
    mapped = {
        x["product_id"]: x for x in mappings["mappings"] if x.get("merchant") == "perfumetrader"
    }
    stock_count = {"MERCHANT_PAGE_IN_STOCK": 0, "MERCHANT_PAGE_OUT_OF_STOCK": 0}
    observation = _utc(evidence["checked_at_utc"])
    for row in records:
        _check(set(row) == MERCHANT_FIELDS, "unexpected_merchant_evidence_fields")
        pid = row["product_id"]
        mapping = mapped.get(pid)
        product = originals_public.get(pid) or fact_public.get(pid)
        _check(
            mapping is not None and product is not None and pid not in held_ids,
            "unreleased_or_unmapped_merchant_product",
        )
        url = urlsplit(row["source_page_url"])
        _check(
            url.scheme == "https"
            and url.hostname == "www.perfumetrader.de"
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and not url.port
            and re.fullmatch(r"/(de|en)/[a-z0-9/-]+", url.path) is not None,
            "merchant_source_not_direct_https",
        )
        _check(
            row["merchant_id"] == "perfumetrader"
            and row["merchant_article"] == mapping["merchant_product_id"]
            and row["gtin"] == (mapping.get("gtin") or mapping.get("ean"))
            and row["volume_ml"] == product["volume_ml"]
            and row["concentration"] == product["concentration"]
            and row["http_status"] == 200
            and _digest(row["html_sha256"])
            and type(row["html_bytes"]) is int
            and row["html_bytes"] > 1000,
            "merchant_exact_variant_proof_missing",
        )
        _check(
            row["concentration"] in row["page_title"]
            and str(row["volume_ml"]) + " ml" in row["page_title"],
            "merchant_product_title_mismatch",
        )
        _check(
            row["observed_stock"] in STOCK_STATES
            and row["price_published"] is False
            and row["tracked_link_currently_verified"] is False
            and row["merchant_offer_activated"] is False
            and row["image_rights_granted"] is False,
            "merchant_evidence_wrongly_promoted",
        )
        _check(_utc(row["observed_at_utc"]) == observation, "merchant_source_time_mismatch")
        stock_count[row["observed_stock"]] += 1
    _check(
        stock_count["MERCHANT_PAGE_IN_STOCK"] == merchant["in_stock_page_observations"] == 1
        and stock_count["MERCHANT_PAGE_OUT_OF_STOCK"]
        == merchant["out_of_stock_page_observations"]
        == 4,
        "merchant_stock_summary_mismatch",
    )
    gallery = validate_top_gallery(evidence, public_ids, photo_ids, mappings)
    current = (now or datetime.now(UTC)).astimezone(UTC)
    age = current - observation
    fresh_for_private_review = timedelta(minutes=-5) <= age <= timedelta(hours=24)
    return {
        "status": "PASS",
        "verified_live_urls": len(pages),
        "approved_photos": counters["VERIFIED_ORIGINAL"],
        "public_missing_original": counters["ORIGINAL_PENDING"] + counters["STUDIO_HOLD"],
        "merchant_pages_examined": len(records),
        "top_gallery_leads_held": gallery["private_gallery_leads"],
        "wrong_og_preview_variants_blocked": gallery["wrong_og_variants"],
        "giftbox_photos_held": gallery["giftbox_hold"],
        "merchant_in_stock_history": stock_count["MERCHANT_PAGE_IN_STOCK"],
        "merchant_out_of_stock_history": stock_count["MERCHANT_PAGE_OUT_OF_STOCK"],
        "merchant_observations_fresh_for_private_review": fresh_for_private_review,
        "merchant_offers_activated": 0,
        "affiliate_clickouts": 0,
        "database_writes": 0,
        "source_html_downloads": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=SNAPSHOT)
    args = parser.parse_args()
    report = validate_evidence(
        _load(args.evidence),
        _load(GENERATED / "public-fragrances.json"),
        _load(GENERATED / "released-profiles.json"),
        _load(DATA / "dufynd_facts_wave_02_review.json"),
        _load(GENERATED / "original-photos.json"),
        _load(DATA / "merchant_product_mappings.json"),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
