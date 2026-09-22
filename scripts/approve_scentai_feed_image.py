from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
DEFAULT_CANDIDATES = Path("examples/retail/data/merchant_feed_image_candidates.json")
DEFAULT_RIGHTS_REGISTRY = Path(
    "examples/retail/data/dufynd_affiliate_feed_image_rights.json"
)

APPROVED_IMAGE_STATUSES = {
    "approved_feed_image",
    "approved_manufacturer_image",
    "approved_licensed_image",
}
VERIFIED_RIGHTS_STATUS = "verified_for_publisher_service"
REQUIRED_FEED_DATA_SOURCE = "approved-affiliate-feed"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _norm(value: object) -> str:
    return str(value or "").strip().casefold()


def candidate_rights_evidence(
    candidate: dict,
    rights_registry: dict | None,
) -> dict:
    if rights_registry is None:
        raise ValueError("candidate_rights_not_verified")

    required_source = str(
        rights_registry.get("required_candidate_data_source")
        or REQUIRED_FEED_DATA_SOURCE
    ).strip()
    if str(candidate.get("data_source") or "").strip() != required_source:
        raise ValueError("candidate_not_from_approved_affiliate_feed")

    network = _norm(candidate.get("network"))
    merchant_id = _norm(candidate.get("merchant_id") or candidate.get("merchant"))

    entry = next(
        (
            row
            for row in rights_registry.get("entries", [])
            if _norm(row.get("network")) == network
            and _norm(row.get("merchant_id")) == merchant_id
        ),
        None,
    )
    if entry is None:
        raise ValueError("candidate_rights_not_verified")

    verified_status = str(
        rights_registry.get("verified_status") or VERIFIED_RIGHTS_STATUS
    ).strip()
    if str(entry.get("rights_status") or "").strip() != verified_status:
        raise ValueError("candidate_rights_not_verified")
    if _norm(entry.get("program_status")) != "approved":
        raise ValueError("candidate_affiliate_program_not_approved")

    rights_basis_id = str(entry.get("rights_basis_id") or "").strip()
    checked_at = str(entry.get("checked_at") or "").strip()
    if not rights_basis_id or not checked_at:
        raise ValueError("candidate_rights_evidence_incomplete")

    return {
        "rights_basis_id": rights_basis_id,
        "rights_status": verified_status,
        "rights_checked_at": checked_at,
        "publisher_scope": entry.get("publisher_scope"),
        "asset_scope": entry.get("asset_scope"),
    }


def approval_plan(
    staging: dict,
    candidates_payload: dict,
    *,
    product_id: str,
    image_url: str,
    rights_registry: dict | None = None,
    replace_approved_image: bool = False,
) -> dict:
    product_id = product_id.strip()
    image_url = image_url.strip()

    if not product_id:
        raise ValueError("product_id_required")
    if not image_url:
        raise ValueError("image_url_required")
    if not valid_http_url(image_url):
        raise ValueError("image_url_must_be_http_or_https")

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

    status = str(candidate.get("review_status") or "").strip()
    if status not in {
        "pending_review",
        "approved",
    }:
        raise ValueError(f"candidate_not_approvable:{status or 'missing_status'}")

    proposed_status = str(candidate.get("proposed_image_status") or "").strip()
    if proposed_status != "approved_feed_image":
        raise ValueError("candidate_missing_approved_feed_image_proposal")

    rights = candidate_rights_evidence(candidate, rights_registry)

    products = staging.get("products", [])
    product = next(
        (row for row in products if str(row.get("product_id") or "").strip() == product_id),
        None,
    )

    if product is None:
        raise ValueError("staging_product_not_found")

    media = product.get("media", {})
    current_url = str(media.get("image_url") or "").strip()
    current_status = str(media.get("image_status") or "").strip()

    already_same = current_url == image_url and current_status == "approved_feed_image"

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
        "candidate_status": status,
        "current_image_url": current_url or None,
        "current_image_status": current_status or None,
        "already_approved": already_same,
        "will_change": not already_same,
        **rights,
    }


def apply_approval(
    staging: dict,
    candidates_payload: dict,
    *,
    product_id: str,
    image_url: str,
    reviewed_at: str,
    rights_basis_id: str,
    rights_checked_at: str,
) -> None:
    product = next(
        row
        for row in staging.get("products", [])
        if str(row.get("product_id") or "").strip() == product_id
    )
    media = dict(product.get("media", {}))
    media.update(
        {
            "image_url": image_url,
            "image_status": "approved_feed_image",
            "image_reviewed_at": reviewed_at,
            "image_rights_basis_id": rights_basis_id,
            "image_rights_checked_at": rights_checked_at,
        }
    )
    product["media"] = media

    candidate = next(
        row
        for row in candidates_payload.get("candidates", [])
        if str(row.get("product_id") or "").strip() == product_id
        and str(row.get("image_url") or "").strip() == image_url
    )
    candidate["review_status"] = "approved"
    candidate["reviewed_at"] = reviewed_at
    candidate["rights_basis_id"] = rights_basis_id
    candidate["rights_status"] = VERIFIED_RIGHTS_STATUS
    candidate["rights_checked_at"] = rights_checked_at


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Approve one reviewed affiliate-feed product image for a staged SCENTAI fragrance."
        )
    )
    parser.add_argument(
        "--product-id",
        required=True,
    )
    parser.add_argument(
        "--image-url",
        required=True,
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=DEFAULT_CANDIDATES,
    )
    parser.add_argument(
        "--rights-registry",
        type=Path,
        default=DEFAULT_RIGHTS_REGISTRY,
    )
    parser.add_argument(
        "--replace-approved-image",
        action="store_true",
        help=("Allow replacement of an already approved image. Never enabled by default."),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=("Apply the approval. Without this flag the command is a dry-run."),
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    try:
        staging = load_json(args.staging)
        candidates = load_json(args.candidates)
        rights_registry = load_json(args.rights_registry)
        plan = approval_plan(
            staging,
            candidates,
            product_id=args.product_id,
            image_url=args.image_url,
            rights_registry=rights_registry,
            replace_approved_image=(args.replace_approved_image),
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        parser.error(str(exc))

    if args.write and plan["will_change"]:
        reviewed_at = datetime.now(UTC).isoformat()
        apply_approval(
            staging,
            candidates,
            product_id=plan["product_id"],
            image_url=plan["image_url"],
            reviewed_at=reviewed_at,
            rights_basis_id=plan["rights_basis_id"],
            rights_checked_at=plan["rights_checked_at"],
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
            "SCENTAI feed image approval | "
            f"mode={output['mode']} | "
            f"product={output['product_id']} | "
            f"rights={output['rights_status']} | "
            f"will_change={output['will_change']} | "
            f"already_approved={output['already_approved']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
