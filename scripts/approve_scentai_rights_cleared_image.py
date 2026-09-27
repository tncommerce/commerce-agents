from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
DEFAULT_CANDIDATES = Path("examples/retail/data/dufynd_rights_cleared_image_candidates.json")

APPROVED_IMAGE_STATUSES = {
    "approved_feed_image",
    "approved_manufacturer_image",
    "approved_licensed_image",
}
APPROVABLE_IMAGE_STATUSES = {
    "approved_manufacturer_image",
    "approved_licensed_image",
}
APPROVABLE_SOURCE_CLASSES = {
    "dufynd_owned_original_photography",
    "licensed_asset_provider",
    "written_asset_permission",
    "written_manufacturer_permission",
}
VERIFIED_RIGHTS_STATUS = "verified_for_publisher_service"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def valid_image_target(value: str) -> bool:
    candidate = value.strip()
    if candidate.startswith("/"):
        return (
            not candidate.startswith("//")
            and "\\" not in candidate
            and ".." not in Path(candidate).parts
        )

    parsed = urlparse(candidate)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
    )


def valid_https_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
    )


def approval_plan(
    staging: dict,
    candidates_payload: dict,
    *,
    product_id: str,
    image_url: str,
    replace_approved_image: bool = False,
) -> dict:
    product_id = product_id.strip()
    image_url = image_url.strip()

    if not product_id:
        raise ValueError("product_id_required")
    if not image_url:
        raise ValueError("image_url_required")
    if not valid_image_target(image_url):
        raise ValueError("image_target_must_be_https_or_safe_root_relative_path")

    payload_status = str(candidates_payload.get("status") or "").strip()
    if payload_status and payload_status != "review_only_not_live":
        raise ValueError("candidate_payload_not_review_only")

    candidate = next(
        (
            row
            for row in candidates_payload.get("candidates", [])
            if str(row.get("product_id") or "").strip() == product_id
            and str(row.get("image_url") or "").strip() == image_url
        ),
        None,
    )
    if candidate is None:
        raise ValueError("review_candidate_not_found")

    review_status = str(candidate.get("review_status") or "").strip()
    if review_status not in {"pending_review", "approved"}:
        raise ValueError(f"candidate_not_approvable:{review_status or 'missing_status'}")

    if candidate.get("exact_variant_verified") is not True:
        raise ValueError("candidate_exact_variant_not_verified")

    source_class = str(candidate.get("source_class") or "").strip()
    if source_class not in APPROVABLE_SOURCE_CLASSES:
        raise ValueError("candidate_source_class_not_approvable")

    proposed_status = str(candidate.get("proposed_image_status") or "").strip()
    if proposed_status not in APPROVABLE_IMAGE_STATUSES:
        raise ValueError("candidate_missing_approvable_image_status")

    if (
        source_class == "written_manufacturer_permission"
        and proposed_status != "approved_manufacturer_image"
    ):
        raise ValueError("manufacturer_permission_requires_manufacturer_image_status")
    if (
        source_class != "written_manufacturer_permission"
        and proposed_status != "approved_licensed_image"
    ):
        raise ValueError("non_manufacturer_source_requires_licensed_image_status")

    rights = candidate.get("rights_evidence") or {}
    if str(rights.get("rights_status") or "").strip() != VERIFIED_RIGHTS_STATUS:
        raise ValueError("candidate_rights_not_verified")
    if rights.get("commercial_use_allowed") is not True:
        raise ValueError("candidate_commercial_use_not_allowed")
    if rights.get("public_distribution_allowed") is not True:
        raise ValueError("candidate_public_distribution_not_allowed")

    rights_basis_id = str(rights.get("rights_basis_id") or "").strip()
    rights_checked_at = str(rights.get("rights_checked_at") or "").strip()
    if not rights_basis_id or not rights_checked_at:
        raise ValueError("candidate_rights_evidence_incomplete")

    license_name = str(rights.get("license_name") or "").strip() or None
    license_url = str(rights.get("license_url") or "").strip() or None
    attribution_text = str(rights.get("attribution_text") or "").strip() or None
    share_alike_required = rights.get("share_alike_required")

    if source_class == "licensed_asset_provider":
        if not license_name or not license_url or not attribution_text:
            raise ValueError("candidate_license_metadata_incomplete")
        if not valid_https_url(license_url):
            raise ValueError("candidate_license_url_must_be_https")
        if not isinstance(share_alike_required, bool):
            raise ValueError("candidate_share_alike_requirement_missing")

    product = next(
        (
            row
            for row in staging.get("products", [])
            if str(row.get("product_id") or "").strip() == product_id
        ),
        None,
    )
    if product is None:
        raise ValueError("staging_product_not_found")

    media = product.get("media", {})
    current_url = str(media.get("image_url") or "").strip()
    current_status = str(media.get("image_status") or "").strip()
    already_same = current_url == image_url and current_status == proposed_status

    if (
        current_url
        and current_url != image_url
        and current_status in APPROVED_IMAGE_STATUSES
        and not replace_approved_image
    ):
        raise ValueError("approved_image_already_exists_use_replace_flag")

    return {
        "product_id": product_id,
        "image_url": image_url,
        "source_class": source_class,
        "proposed_image_status": proposed_status,
        "candidate_status": review_status,
        "current_image_url": current_url or None,
        "current_image_status": current_status or None,
        "already_approved": already_same,
        "will_change": not already_same,
        "rights_basis_id": rights_basis_id,
        "rights_status": VERIFIED_RIGHTS_STATUS,
        "rights_checked_at": rights_checked_at,
        "license_name": license_name,
        "license_url": license_url,
        "attribution_text": attribution_text,
        "share_alike_required": share_alike_required,
    }


def apply_approval(
    staging: dict,
    candidates_payload: dict,
    *,
    product_id: str,
    image_url: str,
    reviewed_at: str,
    proposed_image_status: str,
    source_class: str,
    rights_basis_id: str,
    rights_checked_at: str,
    license_name: str | None = None,
    license_url: str | None = None,
    attribution_text: str | None = None,
    share_alike_required: bool | None = None,
) -> None:
    candidate = next(
        row
        for row in candidates_payload.get("candidates", [])
        if str(row.get("product_id") or "").strip() == product_id
        and str(row.get("image_url") or "").strip() == image_url
    )
    if str(candidate.get("review_status") or "").strip() != "approved":
        raise ValueError("final_visual_approval_required")

    product = next(
        row
        for row in staging.get("products", [])
        if str(row.get("product_id") or "").strip() == product_id
    )
    media = dict(product.get("media", {}))
    media.update(
        {
            "image_url": image_url,
            "image_status": proposed_image_status,
            "image_reviewed_at": reviewed_at,
            "image_source_class": source_class,
            "image_rights_basis_id": rights_basis_id,
            "image_rights_checked_at": rights_checked_at,
        }
    )
    if license_name:
        media["image_license_name"] = license_name
    if license_url:
        media["image_license_url"] = license_url
    if attribution_text:
        media["image_attribution_text"] = attribution_text
    if share_alike_required is not None:
        media["image_share_alike_required"] = share_alike_required
    product["media"] = media

    candidate["review_status"] = "approved"
    candidate["reviewed_at"] = reviewed_at
    candidate["rights_status"] = VERIFIED_RIGHTS_STATUS
    candidate["rights_basis_id"] = rights_basis_id
    candidate["rights_checked_at"] = rights_checked_at


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Approve one rights-cleared non-feed product image for a staged DUFYND fragrance."
        )
    )
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument(
        "--replace-approved-image",
        action="store_true",
        help="Allow replacement of an already approved image. Never enabled by default.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply the approval. Without this flag the command is a dry-run.",
    )
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        staging = load_json(args.staging)
        candidates = load_json(args.candidates)
        plan = approval_plan(
            staging,
            candidates,
            product_id=args.product_id,
            image_url=args.image_url,
            replace_approved_image=args.replace_approved_image,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.write and plan["will_change"]:
        if plan["candidate_status"] != "approved":
            parser.error("final_visual_approval_required")

        reviewed_at = datetime.now(UTC).isoformat()
        apply_approval(
            staging,
            candidates,
            product_id=plan["product_id"],
            image_url=plan["image_url"],
            reviewed_at=reviewed_at,
            proposed_image_status=plan["proposed_image_status"],
            source_class=plan["source_class"],
            rights_basis_id=plan["rights_basis_id"],
            rights_checked_at=plan["rights_checked_at"],
            license_name=plan["license_name"],
            license_url=plan["license_url"],
            attribution_text=plan["attribution_text"],
            share_alike_required=plan["share_alike_required"],
        )
        write_json(args.staging, staging)
        write_json(args.candidates, candidates)

    output = {
        **plan,
        "mode": "WRITE" if args.write else "DRY-RUN",
    }
    if args.machine_readable:
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(
            "DUFYND rights-cleared image approval | "
            f"mode={output['mode']} | "
            f"product={output['product_id']} | "
            f"source={output['source_class']} | "
            f"rights={output['rights_status']} | "
            f"will_change={output['will_change']} | "
            f"already_approved={output['already_approved']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
