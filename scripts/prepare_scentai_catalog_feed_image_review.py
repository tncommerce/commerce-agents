from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .prepare_scentai_feed_image_review import (
        APPROVED_IMAGE_STATUSES,
        EXPECTED_ADVERTISER_ID,
        EXPECTED_FEED_ID,
        EXPECTED_MERCHANT_ID,
        EXPECTED_NETWORK,
        VERIFIED_RIGHTS_STATUS,
        _feed_provenance,
        _norm,
        _public_image_url,
        _rights_entry,
    )
else:
    from prepare_scentai_feed_image_review import (
        APPROVED_IMAGE_STATUSES,
        EXPECTED_ADVERTISER_ID,
        EXPECTED_FEED_ID,
        EXPECTED_MERCHANT_ID,
        EXPECTED_NETWORK,
        VERIFIED_RIGHTS_STATUS,
        _feed_provenance,
        _norm,
        _public_image_url,
        _rights_entry,
    )

DEFAULT_CANDIDATES = Path("examples/retail/data/merchant_feed_image_candidates.json")
DEFAULT_FEED_METADATA = Path("awin-feed-metadata.json")
DEFAULT_STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
DEFAULT_RIGHTS = Path("examples/retail/data/dufynd_affiliate_feed_image_rights.json")
DEFAULT_MAPPINGS = Path("examples/retail/data/merchant_product_mappings.json")

CATALOG_APPROVED_IMAGE_STATUSES = APPROVED_IMAGE_STATUSES | {
    "dufynd_generated_approved",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _mapping_rows(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("mappings") or payload.get("items") or []
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    raise ValueError("merchant_mappings_invalid")


def _top_parfuemerie_mapping_index(payload: object) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row in _mapping_rows(payload):
        merchant_id = _norm(row.get("merchant_id") or row.get("merchant"))
        if merchant_id.casefold() != EXPECTED_MERCHANT_ID.casefold():
            continue

        product_id = _norm(row.get("product_id"))
        merchant_product_id = _norm(row.get("merchant_product_id"))
        if not product_id or not merchant_product_id:
            raise ValueError("top_parfuemerie_mapping_identity_missing")

        previous = index.get(product_id)
        if previous is not None and _norm(previous.get("merchant_product_id")) != merchant_product_id:
            raise ValueError(f"top_parfuemerie_mapping_conflict:{product_id}")
        index[product_id] = row

    if not index:
        raise ValueError("top_parfuemerie_mappings_missing")
    return index


def prepare_catalog_review_candidates(
    candidates_payload: dict,
    feed_metadata: dict,
    staging: dict,
    rights_registry: dict,
    mappings_payload: object,
) -> dict:
    if _norm(candidates_payload.get("status")) != "review_only_not_live":
        raise ValueError("candidate_payload_not_review_only")

    provenance = _feed_provenance(feed_metadata)
    rights = _rights_entry(rights_registry)
    rights_basis_id = _norm(rights.get("rights_basis_id"))
    rights_checked_at = _norm(rights.get("checked_at"))
    if not rights_basis_id or not rights_checked_at:
        raise ValueError("top_parfuemerie_rights_evidence_incomplete")

    mappings = _top_parfuemerie_mapping_index(mappings_payload)
    staged_by_id = {
        _norm(row.get("product_id")): row
        for row in staging.get("products", [])
        if _norm(row.get("product_id"))
    }

    prepared: list[dict] = []
    skipped_approved: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    for candidate in candidates_payload.get("candidates", []):
        product_id = _norm(candidate.get("product_id"))
        mapping = mappings.get(product_id)
        if mapping is None:
            continue

        product = staged_by_id.get(product_id)
        if product is None:
            raise ValueError(f"staging_product_not_found:{product_id}")

        media = product.get("media") or {}
        if _norm(media.get("image_status")) in CATALOG_APPROVED_IMAGE_STATUSES:
            skipped_approved.append(product_id)
            continue

        if _norm(candidate.get("review_status")) != "pending_review":
            raise ValueError(f"candidate_not_pending_review:{product_id}")
        if _norm(candidate.get("proposed_image_status")) != "approved_feed_image":
            raise ValueError(f"candidate_not_feed_image:{product_id}")
        if _norm(candidate.get("network")).casefold() != EXPECTED_NETWORK.casefold():
            raise ValueError(f"candidate_network_mismatch:{product_id}")

        merchant_id = _norm(candidate.get("merchant_id") or candidate.get("merchant"))
        if merchant_id.casefold() != EXPECTED_MERCHANT_ID.casefold():
            raise ValueError(f"candidate_merchant_mismatch:{product_id}")

        original_data_source = _norm(candidate.get("data_source"))
        if original_data_source not in {
            "awin-product-data-feed-preflight",
            "approved-affiliate-feed",
        }:
            raise ValueError(f"candidate_source_invalid:{product_id}")

        image_url = _public_image_url(candidate.get("image_url"))
        merchant_product_id = _norm(candidate.get("merchant_product_id"))
        expected_merchant_product_id = _norm(mapping.get("merchant_product_id"))
        if not merchant_product_id or merchant_product_id != expected_merchant_product_id:
            raise ValueError(f"candidate_merchant_product_mismatch:{product_id}")

        feed_gtin = _norm(candidate.get("gtin"))
        feed_ean = _norm(candidate.get("ean"))
        mapped_gtin = _norm(mapping.get("gtin"))
        mapped_ean = _norm(mapping.get("ean"))
        expected_identifiers = {value for value in (mapped_gtin, mapped_ean) if value}
        observed_identifiers = {value for value in (feed_gtin, feed_ean) if value}
        if expected_identifiers and any(
            value not in expected_identifiers for value in observed_identifiers
        ):
            raise ValueError(f"candidate_gtin_mismatch:{product_id}")

        identity = (product_id, merchant_product_id, image_url)
        if identity in seen:
            continue
        seen.add(identity)

        prepared.append(
            {
                "product_id": product_id,
                "candidate_id": product.get("candidate_id"),
                "brand": product.get("brand"),
                "name": product.get("name"),
                "concentration": product.get("concentration"),
                "volume_ml": product.get("volume_ml"),
                "merchant": EXPECTED_MERCHANT_ID,
                "merchant_id": EXPECTED_MERCHANT_ID,
                "merchant_product_id": merchant_product_id,
                "gtin": feed_gtin or feed_ean or mapped_gtin or mapped_ean or None,
                "offer_id": candidate.get("offer_id"),
                "image_url": image_url,
                "network": EXPECTED_NETWORK,
                "data_source": "approved-affiliate-feed",
                "original_data_source": original_data_source,
                "last_updated_at": candidate.get("last_updated_at"),
                "review_status": "pending_review",
                "proposed_image_status": "approved_feed_image",
                "exact_variant_verified": True,
                "identity_basis": "canonical_merchant_product_id_mapping",
                "mapping_verified_at": mapping.get("verified_at"),
                "advertiser_id": EXPECTED_ADVERTISER_ID,
                "feed_id": EXPECTED_FEED_ID,
                "feed_checked_at": provenance["checked_at"],
                "rights_basis_id": rights_basis_id,
                "rights_status": VERIFIED_RIGHTS_STATUS,
                "rights_checked_at": rights_checked_at,
                "approval_action_class": "approval_required",
                "next_action": "human_visual_review",
            }
        )

    prepared.sort(key=lambda row: row["product_id"])

    return {
        "version": 1,
        "status": "review_only_not_live",
        "review_title": "DUFYND mapped Top Parfümerie catalog",
        "review_scope": "mapped_catalog_products",
        "feed_provenance": provenance,
        "rights_basis_id": rights_basis_id,
        "rights_status": VERIFIED_RIGHTS_STATUS,
        "mapped_product_count": len(mappings),
        "pending_review_count": len(prepared),
        "automatic_approval_allowed": False,
        "approval_action_class": "approval_required",
        "skipped_already_approved_product_ids": sorted(set(skipped_approved)),
        "candidates": prepared,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare sanitized, review-only image candidates for every currently mapped "
            "Top Parfümerie catalog product without approving or publishing anything."
        )
    )
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--feed-metadata", type=Path, default=DEFAULT_FEED_METADATA)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--rights-registry", type=Path, default=DEFAULT_RIGHTS)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        packet = prepare_catalog_review_candidates(
            load_json(args.candidates),
            load_json(args.feed_metadata),
            load_json(args.staging),
            load_json(args.rights_registry),
            load_json(args.mappings),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.machine_readable:
        print(json.dumps(packet, ensure_ascii=False))
    else:
        print(
            "DUFYND mapped catalog feed image review | "
            f"mapped={packet['mapped_product_count']} | "
            f"pending={packet['pending_review_count']} | "
            f"approval={packet['approval_action_class']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
