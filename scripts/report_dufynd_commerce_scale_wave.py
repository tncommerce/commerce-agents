"""Review 10-20 DUFYND fragrances in one offline, rights-safe batch.

Reuses public/staging catalog, licensed original photo registry, canonical
merchant offers, approved partner scope and the existing source-gated photo
wave. Produces a tri-gate REVIEW report; it never publishes or writes prices.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.dufynd_commerce_gates import approved_affiliate_route

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from retail.api.merchant_offers import (  # noqa: E402
    MerchantOffer,
    offer_age_hours,
    rank_offers,
)

DATA = ROOT / "examples/retail/data"
PUBLIC = ROOT / "examples/retail/storefront-web/lib/generated/public-fragrances.json"
PHOTOS = ROOT / "examples/retail/storefront-web/lib/generated/original-photos.json"


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except ValueError:
        return None


def _review_photo_candidates(wave: dict | None, now: datetime) -> dict[str, dict]:
    if not isinstance(wave, dict) or wave.get("status") != "REVIEW_ONLY_NOT_LIVE":
        return {}
    feed = wave.get("current_feed") or {}
    checked = _time(feed.get("checked_at"))
    if checked is None or not timedelta(0) <= now - checked <= timedelta(days=7):
        return {}
    if str(feed.get("advertiser_id")) != "31081" or str(feed.get("feed_id")) != "91379":
        return {}
    if wave.get("automatic_image_approval_allowed") is not False:
        return {}
    return {
        item["product_id"]: item
        for item in wave.get("items", [])
        if isinstance(item, dict)
        and item.get("status") == "SOURCE_IMAGE_REVIEW_REQUIRED"
        and item.get("rights_basis_id") == wave.get("rights_basis_id")
        and item.get("product_id")
    }


def build_commerce_wave(
    staging: dict,
    public: dict,
    photos: list[dict],
    offers: dict,
    partners: dict,
    *,
    now: datetime,
    batch_size: int = 20,
    product_ids: list[str] | None = None,
    photo_review: dict | None = None,
    api_status: str = "not_checked",
) -> dict[str, Any]:
    """Build one auditable read-only preflight without turning review into GO."""
    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    if api_status not in {"not_checked", "healthy", "unavailable"}:
        raise ValueError("invalid_api_status")
    if not 10 <= batch_size <= 20:
        raise ValueError("batch_size_must_be_10_to_20")
    staged = {
        row.get("product_id"): row
        for row in staging.get("products", [])
        if isinstance(row, dict) and row.get("product_id")
    }
    public_rows = {
        row.get("product_id"): row
        for row in public.get("products", [])
        if isinstance(row, dict) and row.get("product_id")
    }
    unpublished = [pid for pid in staged if pid not in public_rows]
    # Never consume a review slot on an already-public fragrance.
    ids = unpublished[:batch_size] if product_ids is None else list(product_ids)
    if not 10 <= len(ids) <= 20 or len(set(ids)) != len(ids):
        raise ValueError("batch_must_have_10_to_20_unique_products")
    if any(not isinstance(pid, str) or pid not in staged | public_rows for pid in ids):
        raise ValueError("unknown_or_unreleased_review_product")

    originals: dict[str, list[dict]] = {}
    for photo in photos:
        originals.setdefault(str(photo.get("product_id")), []).append(photo)
    by_offer: dict[str, list[dict]] = {}
    for offer in offers.get("offers", []):
        by_offer.setdefault(str(offer.get("product_id")), []).append(offer)
    candidates = _review_photo_candidates(photo_review, now.astimezone(UTC))

    items: list[dict] = []
    totals: Counter[str] = Counter()
    for pid in ids:
        product = public_rows.get(pid) or staged[pid]
        known_public = pid in public_rows
        profile_fields_valid = (
            all(
                str(product.get(field) or "").strip()
                for field in ("brand", "name", "concentration")
            )
            and type(product.get("volume_ml")) is int
            and product["volume_ml"] > 0
        )
        profile = (
            "PUBLIC_INFORMATION_PROFILE"
            if known_public and profile_fields_valid
            else "REVIEW_ONLY"
            if profile_fields_valid
            else "IDENTITY_REVIEW_REQUIRED"
        )

        matched_originals = [
            p
            for p in originals.get(pid, [])
            if type(p.get("volume_ml")) is int
            and p["volume_ml"] == product.get("volume_ml")
            and str(p.get("rights_basis_id") or "").strip()
            and str(p.get("url") or "").startswith("https://")
        ]
        candidate = candidates.get(pid)
        if len(matched_originals) == 1:
            image = "REUSE_ALREADY_APPROVED_ORIGINAL"
        elif candidate is not None:
            image = "SOURCE_IMAGE_REVIEW_REQUIRED"
        else:
            image = "NO_APPROVED_ORIGINAL"
        if len(originals.get(pid, [])) > 1:
            image = "CONFLICTING_ORIGINAL_REGISTRY"

        source_rows = by_offer.get(pid, [])
        fresh = 0
        expired = 0
        affiliate_hold = 0
        other_hold = 0
        for raw in source_rows:
            if not approved_affiliate_route(raw, partners):
                affiliate_hold += 1
                continue
            try:
                offer = MerchantOffer.model_validate(raw)
                if rank_offers([offer], now=now):
                    fresh += 1
                elif offer_age_hours(offer, now=now) > 72:
                    expired += 1
                else:
                    other_hold += 1
            except (TypeError, ValueError):
                other_hold += 1

        # This offline repository audit never infers active DB certification.
        # Even a fresh JSON row requires runtime evidence and the buyer API.
        if fresh:
            offer_state = "CURRENT_STATIC_ROW_REQUIRES_RUNTIME_CERTIFICATION"
        elif expired:
            offer_state = "EXPECTED_72H_EXPIRY"
        elif affiliate_hold:
            offer_state = "AFFILIATE_OR_PARTNER_HOLD"
        else:
            offer_state = "NO_CERTIFIED_CURRENT_OFFER"
        findings: list[str] = []
        if image != "REUSE_ALREADY_APPROVED_ORIGINAL":
            findings.append("original_image_or_rights_pending")
        if expired:
            findings.append("normal_offer_expiry")
        if affiliate_hold:
            findings.append("affiliate_unavailable")
        if profile == "IDENTITY_REVIEW_REQUIRED":
            findings.append("product_identity_pending")
        totals.update([profile, image, offer_state])
        items.append(
            {
                "product_id": pid,
                "brand": product.get("brand"),
                "name": product.get("name"),
                "concentration": product.get("concentration"),
                "volume_ml": product.get("volume_ml"),
                "profile_gate": profile,
                "original_image_gate": image,
                "offer_gate": offer_state,
                "canonical_offer_rows": len(source_rows),
                "fresh_static_candidates_not_activated": fresh,
                "normal_expired_offer_rows": expired,
                "partner_or_link_holds": affiliate_hold,
                "other_offer_holds": other_hold,
                "source_photo_candidate_needs_human_go": candidate is not None,
                "diagnostic_categories": findings,
                "public_release_authorized_by_this_report": False,
            }
        )
    return {
        "schema_version": 1,
        "status": "REVIEW_ONLY_NO_PRICE_OR_MEDIA_WRITES",
        "generated_at": now.astimezone(UTC).isoformat(),
        "batch_size": len(items),
        "staged_already_public_count": len(staged) - len(unpublished),
        "unpublished_staging_backlog": len(unpublished),
        "default_selection_excludes_public": product_ids is None,
        "api_status": api_status,
        "critical_software_api_incident": api_status == "unavailable",
        "normal_expiry_is_software_incident": False,
        "summary": dict(sorted(totals.items())),
        "items": items,
        "automatic_image_approval_allowed": False,
        "automatic_offer_activation_allowed": False,
        "automatic_profile_publication_allowed": False,
        "merchant_clickouts": 0,
        "network_requests": 0,
        "database_writes": 0,
    }


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--product-ids-file", type=Path)
    parser.add_argument("--photo-wave", type=Path)
    parser.add_argument(
        "--api-status", choices=["not_checked", "healthy", "unavailable"], default="not_checked"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    ids = load(args.product_ids_file)["product_ids"] if args.product_ids_file else None
    report = build_commerce_wave(
        load(DATA / "scentai_catalog_staging.json"),
        load(PUBLIC),
        load(PHOTOS),
        load(DATA / "merchant_offers.json"),
        load(DATA / "merchant_partners.json"),
        now=datetime.now(UTC),
        batch_size=args.batch_size,
        product_ids=ids,
        photo_review=load(args.photo_wave) if args.photo_wave else None,
        api_status=args.api_status,
    )
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 20 if report["critical_software_api_incident"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
