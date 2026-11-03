#!/usr/bin/env python3
"""Build the CURRENT public DUFYND photo gap from approved product truth.

This output is review input for the manually triggered Awin photo-lead scanner,
never a product image, rights approval, merchant link, price or offer activation.
The October 11 historical gap is used for priority ORDER, not stale counts.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/retail/data"
WEB = ROOT / "examples/retail/storefront-web/lib/generated"
LEGACY = ROOT / "docs/dufynd-catalog-photo-gap-20261011.json"


def load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def unique(rows: list[dict], label: str) -> dict[str, dict]:
    ids = [str(row.get("product_id") or "") for row in rows]
    if not ids or any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"invalid_or_duplicate_{label}_product_id")
    return dict(zip(ids, rows, strict=True))


def blocked(source: dict) -> list[str]:
    return [
        str(value).strip()
        for value in (source.get("validation") or {}).get("blockers") or []
        if str(value).strip()
    ]


def approved_original(product: dict, photo: dict) -> bool:
    size = product.get("volume_ml")
    if not isinstance(size, int) or size <= 0:
        return False
    if photo.get("volume_ml") != size or not str(photo.get("rights_basis_id") or "").strip():
        return False
    url = photo.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    return any(
        visual.get("role") in {"primary", "cutout"}
        and visual.get("fidelity_status") == "verified"
        and visual.get("url") == url
        and str(visual.get("variant") or "").strip().replace(" ", "").lower() == f"{size}ml"
        for visual in product.get("visuals") or []
    )


def build_gap(
    catalog: dict,
    source: dict,
    released: dict,
    approvals: dict,
    photographs: list,
    wave2: dict,
    legacy: dict,
) -> dict:
    """Fail closed if public catalog, approvals or registered visuals drift."""
    catalog_rows = catalog.get("products")
    source_rows = source.get("products")
    public_rows = released.get("profiles")
    approval_rows = approvals.get("approvals")
    wave2_rows = wave2.get("profiles")
    if not all(
        isinstance(rows, list)
        for rows in (catalog_rows, source_rows, public_rows, approval_rows, photographs, wave2_rows)
    ):
        raise ValueError("public_catalog_input_malformed")
    if legacy.get("schema") != "dufynd_catalog_photo_gap_v1":
        raise ValueError("historical_priority_contract_changed")
    by_source = unique(source_rows, "source")
    base = [
        row
        for row in catalog_rows
        if str(row.get("product_id") or "").startswith("SC-")
        and row.get("category") == "fragrance"
        and row.get("in_stock") is not False
        and not blocked(by_source.get(row["product_id"], {}))
    ]
    base_by_id = unique(base, "public_base")
    if any(row["product_id"] not in by_source for row in base):
        raise ValueError("public_base_without_verified_source")
    new_by_id = unique(public_rows, "released")
    by_approval = unique(approval_rows, "release_approval")
    held_by_id = unique(wave2_rows, "private_second_wave")
    if len(new_by_id) != len(by_approval) or set(new_by_id) != set(by_approval):
        raise ValueError("released_approval_set_mismatch")
    if set(held_by_id) & (set(base_by_id) | set(new_by_id)):
        raise ValueError("private_wave_two_entered_public_catalog")
    if set(new_by_id) & set(base_by_id):
        raise ValueError("public_base_and_release_overlap")
    for product_id, row in new_by_id.items():
        approval = by_approval[product_id]
        if (
            row.get("indexing_approved") is not True
            or approval.get("publication_approved") is not True
            or approval.get("indexing_approved") is not True
            or row.get("seo", {}).get("public_path") != f"/duft/{row.get('slug')}"
            or not str(row.get("brand") or "").strip()
            or not str(row.get("name") or "").strip()
        ):
            raise ValueError(f"unverified_public_release:{product_id}")
    if len(base_by_id) != 37 or len(new_by_id) != 20 or len(held_by_id) != 21:
        raise ValueError("public_catalog_source_inventory_changed_requires_review")

    public: dict[str, dict] = {}
    for product_id, row in base_by_id.items():
        fact = by_source[product_id]
        if row.get("category") != "fragrance":
            raise ValueError("unexpected_public_category")
        if (
            str(row.get("brand") or "") != str(fact.get("brand") or "")
            or str((row.get("attributes") or {}).get("canonical_name") or "")
            != str(fact.get("name") or "")
            or str((row.get("attributes") or {}).get("concentration") or "")
            != str(fact.get("concentration") or "")
            or str((row.get("attributes") or {}).get("volume_ml") or "")
            != str(fact.get("volume_ml") or "")
        ):
            raise ValueError(f"public_base_source_identity_drift:{product_id}")
        public[product_id] = fact
    for product_id, row in new_by_id.items():
        public[product_id] = row
    if len(public) != 57:
        raise ValueError("public_product_count_changed_requires_review")

    photos_by_id = unique(photographs, "registered_photo")
    if not set(photos_by_id).issubset(public):
        raise ValueError("registered_photo_points_to_nonpublic_product")
    verified_photo_ids: set[str] = set()
    for product_id, photo in photos_by_id.items():
        if product_id in new_by_id:
            # A newly owner-approved released photo must first appear in a
            # variant-bound, reviewed public truth source, not in this queue.
            raise ValueError("released_photo_requires_separate_public_truth_gate")
        if not approved_original(by_source[product_id], photo):
            raise ValueError(f"registered_photo_lacks_exact_source_truth:{product_id}")
        verified_photo_ids.add(product_id)

    priority = legacy.get("priority_first8_ids")
    if not isinstance(priority, list) or len(priority) != len(set(priority)):
        raise ValueError("historical_priority_order_invalid")
    if any(product_id not in base_by_id for product_id in priority):
        raise ValueError("historical_priority_target_no_longer_public")
    missing_ids = set(public) - verified_photo_ids
    ordered = [
        *[product_id for product_id in priority if product_id in missing_ids],
        *sorted((set(base_by_id) & missing_ids) - set(priority)),
        *sorted(set(new_by_id) & missing_ids),
    ]
    if len(ordered) != len(missing_ids) or len(set(ordered)) != len(ordered):
        raise ValueError("photo_gap_not_exactly_public_minus_approved")

    items = [
        {
            "priority": (
                "first_visible_photo_gap"
                if product_id in priority
                else "published_fact_only_wave"
                if product_id in new_by_id
                else "rest_of_public_catalog"
            ),
            "product_id": product_id,
            "brand": public[product_id]["brand"],
            "name": public[product_id]["name"],
            "concentration": public[product_id]["concentration"],
            "volume_ml": public[product_id]["volume_ml"],
            "source_state": "NO_EXACT_APPROVED_PHOTO",
            "visual_publish_go": False,
            "merchant_offer_activation_go": False,
        }
        for product_id in ordered
    ]
    public_blocked = [
        {"product_id": product_id, "reason": blocked(fact)}
        for product_id, fact in sorted(by_source.items())
        if product_id.startswith("SC-") and blocked(fact)
    ]
    return {
        "schema": "dufynd_catalog_photo_gap_v1",
        "status": "RIGHTS_SOURCE_ACQUISITION_PENDING_NO_AUTO_APPROVAL",
        "catalog_snapshot_source": "examples/retail/data/catalog.json",
        "source_fact_registry": "examples/retail/data/scentai_products.json",
        "released_profile_source": "examples/retail/storefront-web/lib/generated/released-profiles.json",
        "release_approval_source": "examples/retail/data/dufynd_release_authorizations.json",
        "photo_registry_source": "examples/retail/storefront-web/lib/generated/original-photos.json",
        "historical_snapshot_used_for_priority_and_policy": LEGACY.relative_to(ROOT).as_posix(),
        "public_fragrances": len(public),
        "original_catalog_fragrances": len(base_by_id),
        "owner_released_fact_profiles": len(new_by_id),
        "unpublished_private_wave_two": len(held_by_id),
        "approved_original_photo_variants": len(verified_photo_ids),
        "public_without_photo": len(items),
        "separate_hidden_variants": public_blocked,
        "display_policy": legacy["display_policy"],
        "possible_rights_route": legacy["possible_rights_route"],
        "asset_requirements": legacy["asset_requirements"],
        "priority_first8_ids": [x for x in priority if x in missing_ids],
        "new_images_approved": 0,
        "merchant_offers_activated": 0,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    gap = build_gap(
        load(DATA / "catalog.json"),
        load(DATA / "scentai_products.json"),
        load(WEB / "released-profiles.json"),
        load(DATA / "dufynd_release_authorizations.json"),
        load(WEB / "original-photos.json"),
        load(DATA / "dufynd_facts_wave_02_review.json"),
        load(LEGACY),
    )
    gap["generated_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    gap["source_commit"] = os.environ.get("GITHUB_SHA", "")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(gap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"DUFYND public photo source: {gap['public_fragrances']} pages; "
        f"{gap['approved_original_photo_variants']} verified original variants; "
        f"{gap['public_without_photo']} review-only gaps; 0 activations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
