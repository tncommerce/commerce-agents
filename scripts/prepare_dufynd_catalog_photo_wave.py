"""Build a source-gated, review-only image shortlist for DUFYND's public catalog.

Reuses the existing official Awin feed extractor and its sanitized output.
Never scrapes merchant page images, infers product bottles, approves photos,
changes prices/offers, or promotes anything to the public storefront.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

if __package__:
    from .prepare_scentai_feed_image_review import (
        _feed_provenance, _public_image_url, _rights_entry,
    )
else:
    from prepare_scentai_feed_image_review import (
        _feed_provenance, _public_image_url, _rights_entry,
    )

DEFAULT_GAPS = Path("docs/dufynd-catalog-photo-gap-20261011.json")
DEFAULT_MAPPINGS = Path("examples/retail/data/merchant_product_mappings.json")
DEFAULT_RIGHTS = Path("examples/retail/data/dufynd_affiliate_feed_image_rights.json")
PROVIDER = "awin-top-parfuemerie-de"
MERCHANT = "top-parfuemerie"
SOURCE = "awin-product-data-feed-preflight"
MAX_FEED_AGE = timedelta(days=7)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _current_feed(metadata: dict, now: datetime) -> dict:
    source = _feed_provenance(metadata)
    value = str(source["checked_at"]).replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("feed_checked_at_invalid") from exc
    if stamp.tzinfo is None:
        raise ValueError("feed_checked_at_timezone_missing")
    age = now.astimezone(UTC) - stamp.astimezone(UTC)
    if age < timedelta(0) or age > MAX_FEED_AGE:
        raise ValueError("feed_too_old_or_from_future")
    return source


def _public_feed_photo(url: object) -> str:
    checked = _public_image_url(url)
    parsed = urlsplit(checked)
    if parsed.hostname not in {"topparfuemerie.de", "www.topparfuemerie.de"}:
        raise ValueError("not_official_merchant_image_host")
    if parsed.query or not re.fullmatch(
        r"/media/catalog/product/[a-z0-9/_-]+\.(?:png|webp|jpg|jpeg)",
        parsed.path,
    ):
        raise ValueError("not_official_merchant_image_path")
    return checked


def prepare_photo_wave(
    gaps: dict,
    mappings: dict,
    extracted: dict,
    feed_metadata: dict,
    rights_registry: dict,
    *,
    now: datetime,
) -> dict:
    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    provenance = _current_feed(feed_metadata, now)
    rights = _rights_entry(rights_registry)
    if extracted.get("status") != "review_only_not_live":
        raise ValueError("extracted_candidates_must_be_review_only")
    if extracted.get("provider") != PROVIDER:
        raise ValueError("wrong_feed_provider")
    if gaps.get("status") != "RIGHTS_SOURCE_ACQUISITION_PENDING_NO_AUTO_APPROVAL":
        raise ValueError("photo_gap_input_not_review_ready")

    missing = gaps.get("items")
    if not isinstance(missing, list) or not missing:
        raise ValueError("empty_photo_gap_queue")
    by_sku: dict[str, list[dict]] = {}
    for row in extracted.get("candidates", []):
        if (
            row.get("merchant") == MERCHANT
            and row.get("merchant_id") == MERCHANT
        ):
            by_sku.setdefault(str(row.get("merchant_product_id")), []).append(row)

    mapped: dict[str, list[dict]] = {}
    for row in mappings.get("mappings", []):
        if row.get("merchant") == MERCHANT:
            mapped.setdefault(str(row.get("product_id")), []).append(row)

    items: list[dict] = []
    seen_ids: set[str] = set()
    for entry in missing:
        product_id = str(entry.get("product_id") or "").strip()
        if not product_id or product_id in seen_ids:
            raise ValueError("missing_or_duplicate_public_product_id")
        seen_ids.add(product_id)
        if entry.get("source_state") != "NO_EXACT_APPROVED_PHOTO":
            raise ValueError("already_approved_or_wrong_gap_state")

        item = {
            "product_id": product_id,
            "brand": entry.get("brand"),
            "name": entry.get("name"),
            "concentration": entry.get("concentration"),
            "volume_ml": entry.get("volume_ml"),
            "status": "HOLD",
            "blockers": [],
            "approved_image": False,
            "publish_go": False,
            "offer_activation_go": False,
        }
        matches = mapped.get(product_id, [])
        if len(matches) != 1:
            item["blockers"].append(
                "current_exact_merchant_sku_mapping_missing"
                if not matches else "ambiguous_merchant_sku_mapping"
            )
        else:
            mapping = matches[0]
            sku = str(mapping.get("merchant_product_id") or "").strip()
            gtin = str(mapping.get("gtin") or mapping.get("ean") or "").strip()
            if (
                not re.fullmatch(r"[0-9]{5,20}", sku)
                or not re.fullmatch(r"[0-9]{8,14}", gtin)
                or mapping.get("mapping_status") != "verified_current_variant"
            ):
                item["blockers"].append("independent_exact_variant_evidence_required")
            else:
                item["merchant_product_id"] = sku
                item["known_gtin"] = gtin
                candidates = by_sku.get(sku, [])
                if len(candidates) != 1:
                    item["blockers"].append(
                        "current_official_feed_image_row_missing"
                        if not candidates else "ambiguous_current_feed_image_rows"
                    )
                else:
                    candidate = candidates[0]
                    candidate_gtins = [
                        str(candidate[field]).strip()
                        for field in ("gtin", "ean")
                        if candidate.get(field)
                    ]
                    if any(value != gtin for value in candidate_gtins):
                        item["blockers"].append("feed_identity_conflicts_with_gtin")
                    elif (
                        candidate.get("network") != "Awin"
                        or candidate.get("data_source") != SOURCE
                        or candidate.get("review_status") != "pending_review"
                        or candidate.get("proposed_image_status") != "approved_feed_image"
                    ):
                        item["blockers"].append("feed_provenance_or_review_state_invalid")
                    else:
                        try:
                            photo_url = _public_feed_photo(candidate.get("image_url"))
                        except ValueError:
                            item["blockers"].append("feed_image_url_not_public_or_official")
                        else:
                            item.update(
                                {
                                    "status": "SOURCE_IMAGE_REVIEW_REQUIRED",
                                    "source_image_url": photo_url,
                                    "awin_offer_id": str(candidate.get("offer_id") or ""),
                                    "rights_basis_id": rights["rights_basis_id"],
                                    "rights_scope": "unaltered_material_from_official_awin_feed",
                                    "mapping_checked_at": mapping.get("verified_at"),
                                    "feed_checked_at": provenance["checked_at"],
                                    "remaining_gates": [
                                        "human_exact_variant_visual_match",
                                        "source_image_byte_fingerprint",
                                        "owner_photo_go",
                                        "separate_catalog_change_review",
                                    ],
                                }
                            )
        items.append(item)

    return {
        "schema_version": 1,
        "status": "REVIEW_ONLY_NOT_LIVE",
        "current_feed": {
            "advertiser_id": provenance["advertiser_id"],
            "feed_id": provenance["feed_id"],
            "checked_at": provenance["checked_at"],
        },
        "rights_basis_id": rights["rights_basis_id"],
        "review_ready_count": sum(
            item["status"] == "SOURCE_IMAGE_REVIEW_REQUIRED" for item in items
        ),
        "hold_count": sum(item["status"] == "HOLD" for item in items),
        "items": items,
        "automatic_image_approval_allowed": False,
        "automatic_offer_activation_allowed": False,
        "automatic_publication_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gaps", type=Path, default=DEFAULT_GAPS)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS)
    parser.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS)
    parser.add_argument("--extracted-candidates", type=Path, required=True)
    parser.add_argument("--feed-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare_photo_wave(
            load_json(args.gaps),
            load_json(args.mappings),
            load_json(args.extracted_candidates),
            load_json(args.feed_metadata),
            load_json(args.rights),
            now=datetime.now(UTC),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError):
        # Never echo untrusted feed data or secret-bearing URLs into CI logs.
        parser.exit(2, "photo_wave_preflight_failed_closed\n")
    print(
        f"DUFYND image review only: {report['review_ready_count']} source "
        f"candidates; {report['hold_count']} holds; no public writes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
