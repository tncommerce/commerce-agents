from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
DEFAULT_CANDIDATES = Path("examples/retail/data/dufynd_rights_cleared_image_candidates.json")

VERIFIED_RIGHTS_STATUS = "verified_for_publisher_service"
REVIEW_STATUS = "pending_review"
APPROVAL_ACTION_CLASS = "approval_required"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm(value: object) -> str:
    return str(value or "").strip()


def review_packet(
    staging: dict,
    candidates_payload: dict,
) -> dict:
    payload_status = _norm(candidates_payload.get("status"))
    if payload_status and payload_status != "review_only_not_live":
        raise ValueError("candidate_payload_not_review_only")

    staged_by_id = {
        _norm(row.get("product_id")): row
        for row in staging.get("products", [])
        if _norm(row.get("product_id"))
    }

    items = []
    for candidate in candidates_payload.get("candidates", []):
        if _norm(candidate.get("review_status")) != REVIEW_STATUS:
            continue

        product_id = _norm(candidate.get("product_id"))
        if not product_id:
            raise ValueError("candidate_product_id_missing")

        product = staged_by_id.get(product_id)
        if product is None:
            raise ValueError(f"candidate_staging_product_not_found:{product_id}")

        if candidate.get("exact_variant_verified") is not True:
            raise ValueError(f"candidate_exact_variant_not_verified:{product_id}")

        for field in ("brand", "name", "concentration"):
            candidate_value = _norm(candidate.get(field))
            staged_value = _norm(product.get(field))
            if candidate_value != staged_value:
                raise ValueError(f"candidate_identity_mismatch:{product_id}:{field}")

        if int(candidate.get("volume_ml") or 0) != int(product.get("volume_ml") or 0):
            raise ValueError(f"candidate_identity_mismatch:{product_id}:volume_ml")

        rights = candidate.get("rights_evidence") or {}
        if _norm(rights.get("rights_status")) != VERIFIED_RIGHTS_STATUS:
            raise ValueError(f"candidate_rights_not_verified:{product_id}")
        if rights.get("commercial_use_allowed") is not True:
            raise ValueError(f"candidate_commercial_use_not_allowed:{product_id}")
        if rights.get("public_distribution_allowed") is not True:
            raise ValueError(f"candidate_public_distribution_not_allowed:{product_id}")

        rights_basis_id = _norm(rights.get("rights_basis_id"))
        rights_checked_at = _norm(rights.get("rights_checked_at"))
        if not rights_basis_id or not rights_checked_at:
            raise ValueError(f"candidate_rights_evidence_incomplete:{product_id}")

        license_name = _norm(rights.get("license_name")) or None
        license_url = _norm(rights.get("license_url")) or None
        attribution_text = _norm(rights.get("attribution_text")) or None
        share_alike_required = rights.get("share_alike_required")

        if source_class == "licensed_asset_provider":
            if not license_name or not license_url or not attribution_text:
                raise ValueError(f"candidate_license_metadata_incomplete:{product_id}")
            if not isinstance(share_alike_required, bool):
                raise ValueError(f"candidate_share_alike_requirement_missing:{product_id}")

        source_class = _norm(candidate.get("source_class"))
        proposed_image_status = _norm(candidate.get("proposed_image_status"))
        image_url = _norm(candidate.get("image_url"))
        if not source_class or not proposed_image_status or not image_url:
            raise ValueError(f"candidate_review_metadata_incomplete:{product_id}")

        items.append(
            {
                "product_id": product_id,
                "candidate_id": product.get("candidate_id"),
                "brand": product.get("brand"),
                "name": product.get("name"),
                "concentration": product.get("concentration"),
                "volume_ml": product.get("volume_ml"),
                "image_url": image_url,
                "source_class": source_class,
                "proposed_image_status": proposed_image_status,
                "review_status": REVIEW_STATUS,
                "registered_at": candidate.get("registered_at"),
                "evidence_note": candidate.get("evidence_note"),
                "rights_basis_id": rights_basis_id,
                "rights_status": VERIFIED_RIGHTS_STATUS,
                "rights_checked_at": rights_checked_at,
                "commercial_use_allowed": True,
                "public_distribution_allowed": True,
                "license_name": license_name,
                "license_url": license_url,
                "attribution_text": attribution_text,
                "share_alike_required": share_alike_required,
                "approval_action_class": APPROVAL_ACTION_CLASS,
                "next_action": "human_visual_review",
            }
        )

    items.sort(key=lambda row: row["product_id"])

    return {
        "version": 1,
        "status": "pending_visual_review" if items else "no_pending_review_candidates",
        "pending_review_count": len(items),
        "approval_action_class": APPROVAL_ACTION_CLASS,
        "automatic_approval_allowed": False,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only DUFYND visual-review packet for rights-cleared image candidates."
        )
    )
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        packet = review_packet(
            load_json(args.staging),
            load_json(args.candidates),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(packet, ensure_ascii=False))
    else:
        print(
            "DUFYND rights-cleared visual review | "
            f"status={packet['status']} | "
            f"pending={packet['pending_review_count']} | "
            f"approval={packet['approval_action_class']}"
        )
        for item in packet["items"]:
            print(
                " - "
                f"{item['product_id']} | "
                f"{item['brand']} {item['name']} "
                f"{item['concentration']} {item['volume_ml']} ml | "
                f"source={item['source_class']} | "
                f"rights={item['rights_basis_id']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
