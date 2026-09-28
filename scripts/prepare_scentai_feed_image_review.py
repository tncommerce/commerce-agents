from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_CANDIDATES = Path("examples/retail/data/merchant_feed_image_candidates.json")
DEFAULT_FEED_METADATA = Path("awin-feed-metadata.json")
DEFAULT_STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
DEFAULT_RELEASE = Path("examples/retail/data/scentai_release_batch_01.json")
DEFAULT_RIGHTS = Path("examples/retail/data/dufynd_affiliate_feed_image_rights.json")

APPROVED_IMAGE_STATUSES = {
    "approved_feed_image",
    "approved_manufacturer_image",
    "approved_licensed_image",
}
VERIFIED_RIGHTS_STATUS = "verified_for_publisher_service"
EXPECTED_SOURCE = "awin_product_feed_list"
EXPECTED_NETWORK = "Awin"
EXPECTED_MERCHANT_ID = "top-parfuemerie"
EXPECTED_ADVERTISER_ID = "31081"
EXPECTED_FEED_ID = "91379"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm(value: object) -> str:
    return str(value or "").strip()


def _rights_entry(rights_registry: dict) -> dict:
    entry = next(
        (
            row
            for row in rights_registry.get("entries", [])
            if _norm(row.get("network")).casefold() == EXPECTED_NETWORK.casefold()
            and _norm(row.get("merchant_id")).casefold() == EXPECTED_MERCHANT_ID.casefold()
        ),
        None,
    )
    if entry is None:
        raise ValueError("top_parfuemerie_rights_entry_missing")
    if _norm(entry.get("rights_status")) != VERIFIED_RIGHTS_STATUS:
        raise ValueError("top_parfuemerie_rights_not_verified")
    if _norm(entry.get("program_status")).casefold() != "approved":
        raise ValueError("top_parfuemerie_program_not_approved")
    if _norm(entry.get("advertiser_id")) != EXPECTED_ADVERTISER_ID:
        raise ValueError("top_parfuemerie_advertiser_mismatch")
    return entry


def _feed_provenance(feed_metadata: dict) -> dict:
    if _norm(feed_metadata.get("source")) != EXPECTED_SOURCE:
        raise ValueError("current_feed_source_invalid")
    if _norm(feed_metadata.get("advertiser_id")) != EXPECTED_ADVERTISER_ID:
        raise ValueError("current_feed_advertiser_mismatch")
    if _norm(feed_metadata.get("feed_id")) != EXPECTED_FEED_ID:
        raise ValueError("current_feed_id_mismatch")
    if feed_metadata.get("joined") is not True:
        raise ValueError("current_feed_program_not_joined")
    if feed_metadata.get("downloaded") is not True:
        raise ValueError("current_feed_not_downloaded")

    checked_at = _norm(feed_metadata.get("checked_at"))
    if not checked_at:
        raise ValueError("current_feed_checked_at_missing")

    return {
        "source": EXPECTED_SOURCE,
        "advertiser_id": EXPECTED_ADVERTISER_ID,
        "feed_id": EXPECTED_FEED_ID,
        "joined": True,
        "downloaded": True,
        "checked_at": checked_at,
        "last_imported": _norm(feed_metadata.get("last_imported")) or None,
        "download_host": _norm(feed_metadata.get("download_host")) or None,
    }


def prepare_review_candidates(
    candidates_payload: dict,
    feed_metadata: dict,
    staging: dict,
    release: dict,
    rights_registry: dict,
) -> dict:
    if _norm(candidates_payload.get("status")) != "review_only_not_live":
        raise ValueError("candidate_payload_not_review_only")

    provenance = _feed_provenance(feed_metadata)
    rights = _rights_entry(rights_registry)
    rights_basis_id = _norm(rights.get("rights_basis_id"))
    rights_checked_at = _norm(rights.get("checked_at"))
    if not rights_basis_id or not rights_checked_at:
        raise ValueError("top_parfuemerie_rights_evidence_incomplete")

    release_ids = {_norm(value) for value in release.get("product_ids", []) if _norm(value)}
    if not release_ids:
        raise ValueError("release_product_ids_missing")

    staged_by_id = {
        _norm(row.get("product_id")): row
        for row in staging.get("products", [])
        if _norm(row.get("product_id"))
    }

    prepared: list[dict] = []
    skipped_approved: list[str] = []

    for candidate in candidates_payload.get("candidates", []):
        product_id = _norm(candidate.get("product_id"))
        if product_id not in release_ids:
            continue

        product = staged_by_id.get(product_id)
        if product is None:
            raise ValueError(f"staging_product_not_found:{product_id}")

        media = product.get("media") or {}
        if _norm(media.get("image_status")) in APPROVED_IMAGE_STATUSES:
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

        image_url = _norm(candidate.get("image_url"))
        merchant_product_id = _norm(candidate.get("merchant_product_id"))
        if not image_url or not merchant_product_id:
            raise ValueError(f"candidate_identity_evidence_incomplete:{product_id}")

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
                "offer_id": candidate.get("offer_id"),
                "image_url": image_url,
                "network": EXPECTED_NETWORK,
                "data_source": "approved-affiliate-feed",
                "original_data_source": original_data_source,
                "last_updated_at": candidate.get("last_updated_at"),
                "review_status": "pending_review",
                "proposed_image_status": "approved_feed_image",
                "exact_variant_verified": True,
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
        "release_id": release.get("release_id"),
        "feed_provenance": provenance,
        "rights_basis_id": rights_basis_id,
        "rights_status": VERIFIED_RIGHTS_STATUS,
        "pending_review_count": len(prepared),
        "automatic_approval_allowed": False,
        "approval_action_class": "approval_required",
        "skipped_already_approved_product_ids": sorted(set(skipped_approved)),
        "candidates": prepared,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert current Awin top Parfümerie feed candidates into Release 01 "
            "pending-review candidates after current-feed and rights validation."
        )
    )
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--feed-metadata", type=Path, default=DEFAULT_FEED_METADATA)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--rights-registry", type=Path, default=DEFAULT_RIGHTS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        packet = prepare_review_candidates(
            load_json(args.candidates),
            load_json(args.feed_metadata),
            load_json(args.staging),
            load_json(args.release),
            load_json(args.rights_registry),
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
            "DUFYND current feed image review | "
            f"release={packet['release_id']} | "
            f"pending={packet['pending_review_count']} | "
            f"approval={packet['approval_action_class']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
