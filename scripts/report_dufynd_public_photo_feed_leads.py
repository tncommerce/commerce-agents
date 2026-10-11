"""Bounded, rights-scoped Awin photo-source DISCOVERY for public DUFYND gaps.

This file must never approve imagery, store prices, expose affiliate links, or
enable a storefront/merchant offer. The source is the CURRENT official feed
downloaded by the existing revalidation workflow, not scraped merchant pages.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from retail.api.merchant_feed_reader import read_merchant_feed_rows  # noqa: E402

ADVERTISER = "31081"
FEED = "91379"
MERCHANT = "top-parfuemerie"
RIGHTS_BASIS = "awin_top_parfuemerie_feed_materials_20260928"
PHOTO_PATH = re.compile(
    r"/media/catalog/product/(?:[a-z0-9]/){0,3}[a-z0-9_-]+\.(?:png|jpe?g|webp)$",
    re.IGNORECASE,
)
VOLUME = re.compile(r"(?<!\d)(\d{2,3})\s*(?:ml|milliliter)(?!\w)", re.I)
STOP = {
    "de", "der", "das", "die", "und", "the", "by", "for", "pour",
    "eau", "parfum", "perfume", "parfums", "edp", "edt", "elixir",
    "intense", "extrait", "spray", "nat", "vapo", "flacon", "flasche",
    "ml", "100", "90", "75", "125", "50", "edition",
}
MAX_CANDIDATES = 3


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"\s+", " ", "".join(
        ch.lower() if ch.isalnum() else " "
        for ch in text if not unicodedata.combining(ch)
    )).strip()


def safe_feed_image(value: object) -> str | None:
    url = str(value or "").strip()
    try:
        p = urlsplit(url)
    except ValueError:
        return None
    if (p.scheme != "https" or p.hostname not in
        {"topparfuemerie.de", "www.topparfuemerie.de"}
        or p.port is not None or p.username is not None or
        p.password is not None or p.query or p.fragment or
        not PHOTO_PATH.fullmatch(p.path)):
        return None
    return url


def feed_name_matches(item: dict, row: dict) -> bool:
    label = norm(row.get("product_name"))
    tokens = set(label.split())
    names = {x for x in norm(item.get("name")).split() if x not in STOP}
    brands = {x for x in norm(item.get("brand")).split() if x not in STOP}
    if not names or not brands or not names.issubset(tokens) or not (brands & tokens):
        return False
    quantities = [int(v) for v in VOLUME.findall(str(row.get("product_name") or ""))]
    expected = int(item.get("volume_ml") or 0)
    if quantities and expected not in quantities:
        return False
    concentration = norm(item.get("concentration"))
    if concentration == "eau de parfum" and (
        "edt" in tokens or "toilette" in tokens
    ):
        return False
    if concentration == "eau de toilette" and (
        "edp" in tokens or "extrait" in tokens
    ):
        return False
    return True


def verify_context(metadata: dict, rights: dict) -> None:
    if (
        metadata.get("source") != "awin_product_feed_list"
        or str(metadata.get("advertiser_id")) != ADVERTISER
        or str(metadata.get("feed_id")) != FEED
        or metadata.get("joined") is not True
        or metadata.get("downloaded") is not True
        or not metadata.get("checked_at")
    ):
        raise ValueError("current_official_awin_feed_evidence_required")
    eligible = [
        x for x in rights.get("entries", [])
        if x.get("merchant_id") == MERCHANT
        and str(x.get("advertiser_id")) == ADVERTISER
        and x.get("rights_basis_id") == RIGHTS_BASIS
        and x.get("program_status") == "approved"
        and x.get("rights_status") == "verified_for_publisher_service"
        and x.get("asset_scope") == "unaltered_advertiser_materials_from_official_awin_product_feed"
    ]
    if len(eligible) != 1:
        raise ValueError("exact_affiliate_program_rights_unverified")


def create_review(
    gap: dict, mappings: dict, rows: list[dict],
    metadata: dict, rights: dict,
) -> dict:
    verify_context(metadata, rights)
    if gap.get("status") != "RIGHTS_SOURCE_ACQUISITION_PENDING_NO_AUTO_APPROVAL":
        raise ValueError("photo_gap_must_be_unapproved")
    pending = gap.get("items")
    if not isinstance(pending, list) or len(pending) > 250:
        raise ValueError("bounded_photo_gap_manifest_required")
    targets = {str(x.get("product_id") or ""): x for x in pending}
    if not targets or len(targets) != len(pending) or "" in targets:
        raise ValueError("invalid_or_duplicate_photo_gap_ids")
    by_sku: dict[str, list[dict]] = defaultdict(list)
    clean_rows = []
    for row in rows:
        sku = str(row.get("merchant_product_id") or "").strip()
        image = safe_feed_image(row.get("merchant_image_url"))
        if sku and sku.isdigit() and len(sku) <= 16 and image:
            clean_rows.append((sku, row, image))
            by_sku[sku].append((row, image))
    mapped: dict[str, set[str]] = defaultdict(set)
    for m in mappings.get("mappings", []):
        pid = str(m.get("product_id") or "")
        if pid not in targets or m.get("merchant") != MERCHANT:
            continue
        sku = str(m.get("merchant_product_id") or "")
        if sku.isdigit() and len(sku) <= 16:
            mapped[pid].add(sku)
    report = []
    for product_id, item in sorted(targets.items()):
        approved_skus = mapped.get(product_id, set())
        leads = []
        ambiguous = False
        for sku in sorted(approved_skus):
            matches = by_sku.get(sku, [])
            if len(matches) > 1:
                ambiguous = True
                continue
            if len(matches) == 1:
                row, img = matches[0]
                leads.append((0, sku, row, img, "mapped_sku_needs_feed_variant_review"))
        # Research leads use a strict brand+product-name intersection,
        # never infer exact 100ml variant from a similar 50ml name.
        # Name-only leads NEVER become verified mappings automatically.
        for sku, row, img in clean_rows:
            if sku in approved_skus:
                continue
            if feed_name_matches(item, row):
                leads.append((1, sku, row, img, "name_lead_manual_sku_mapping_required"))
        leads.sort(key=lambda x: (x[0], x[1], x[3]))
        distinct = {(sku, img): (rank, sku, row, img, typ) for rank, sku, row, img, typ in leads}
        hits = list(distinct.values())
        hits.sort(key=lambda x: (x[0], x[1], x[3]))
        candidates = []
        for rank, sku, row, img, match_type in hits[:MAX_CANDIDATES]:
            title = str(row.get("product_name") or "")
            title = re.sub(r"[\x00-\x1f\x7f]", " ", title)[:130].strip()
            quantities = [int(v) for v in VOLUME.findall(title)]
            candidates.append({
                "merchant_product_id": sku,
                "merchant_product_name": title,
                "feed_image_url": img,
                "match_type": match_type,
                "feed_explicit_size_match": int(item.get("volume_ml") or 0) in quantities,
                "status": "HUMAN_SOURCE_VARIANT_IMAGE_REVIEW_REQUIRED",
                "registered": False, "published": False,
            })
        report.append({
            "product_id": product_id,
            "brand": item.get("brand"),
            "name": item.get("name"),
            "concentration": item.get("concentration"),
            "volume_ml": item.get("volume_ml"),
            "pinned_merchant_skus": sorted(approved_skus),
            "total_possible_feed_rows": len(hits),
            "duplicate_pinned_feed_sku_hold": ambiguous,
            "more_matches_truncated": len(hits) > MAX_CANDIDATES,
            "candidates": candidates,
            "status": ("REVIEW_LEADS_FOUND" if candidates
                       else "NO_REGISTERABLE_FEED_IMAGE_SOURCE"),
        })
    return {
        "schema": "dufynd_licensed_feed_photo_review_v1",
        "status": "REVIEW_ONLY_NOT_LIVE",
        "feed_provenance": {
            "source": "awin_product_feed_list", "advertiser_id": ADVERTISER,
            "feed_id": FEED, "checked_at": metadata["checked_at"],
            "last_imported": metadata.get("last_imported"),
        },
        "source_rights_basis_id": RIGHTS_BASIS,
        "approved_new_images": 0,
        "automated_registration_allowed": False,
        "product_offer_activation_allowed": False,
        "merchant_links_included": False,
        "products_reviewed": len(report),
        "products_with_leads": sum(bool(x["candidates"]) for x in report),
        "total_review_candidates": sum(len(x["candidates"]) for x in report),
        "items": report,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feed", type=Path, required=True)
    p.add_argument("--feed-metadata", type=Path, required=True)
    p.add_argument("--gap", type=Path, default=Path("docs/dufynd-catalog-photo-gap-20261011.json"))
    p.add_argument("--mappings", type=Path, default=Path("examples/retail/data/merchant_product_mappings.json"))
    p.add_argument("--rights", type=Path, default=Path("examples/retail/data/dufynd_affiliate_feed_image_rights.json"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        feed = read_merchant_feed_rows(args.feed, max_bytes=64 * 1024 * 1024, max_rows=30_000)
        result = create_review(
            json.loads(args.gap.read_text(encoding="utf-8")),
            json.loads(args.mappings.read_text(encoding="utf-8")),
            feed,
            json.loads(args.feed_metadata.read_text(encoding="utf-8")),
            json.loads(args.rights.read_text(encoding="utf-8")),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("DUFYND photo gap review: products=%d leads=%d, zero approvals or merchant activation" % (
            result["products_reviewed"], result["total_review_candidates"]))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
