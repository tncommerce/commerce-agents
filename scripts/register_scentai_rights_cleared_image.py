from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.approve_scentai_rights_cleared_image import (
    APPROVABLE_SOURCE_CLASSES,
    valid_https_url,
    valid_image_target,
)

DEFAULT_STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
DEFAULT_CANDIDATES = Path("examples/retail/data/dufynd_rights_cleared_image_candidates.json")
VERIFIED_RIGHTS_STATUS = "verified_for_publisher_service"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def proposed_status_for_source(source_class: str) -> str:
    if source_class == "written_manufacturer_permission":
        return "approved_manufacturer_image"
    return "approved_licensed_image"


def registration_plan(
    staging: dict,
    candidates_payload: dict,
    *,
    product_id: str,
    image_url: str,
    source_class: str,
    rights_basis_id: str,
    rights_checked_at: str,
    exact_variant_verified: bool,
    commercial_use_allowed: bool,
    public_distribution_allowed: bool,
    evidence_note: str | None = None,
    license_name: str | None = None,
    license_url: str | None = None,
    attribution_text: str | None = None,
    share_alike_required: bool | None = None,
) -> dict:
    product_id = product_id.strip()
    image_url = image_url.strip()
    source_class = source_class.strip()
    rights_basis_id = rights_basis_id.strip()
    rights_checked_at = rights_checked_at.strip()
    license_name = str(license_name or "").strip() or None
    license_url = str(license_url or "").strip() or None
    attribution_text = str(attribution_text or "").strip() or None

    if not product_id:
        raise ValueError("product_id_required")
    if not valid_image_target(image_url):
        raise ValueError("image_target_must_be_https_or_safe_root_relative_path")
    if source_class not in APPROVABLE_SOURCE_CLASSES:
        raise ValueError("candidate_source_class_not_approvable")
    if exact_variant_verified is not True:
        raise ValueError("candidate_exact_variant_not_verified")
    if commercial_use_allowed is not True:
        raise ValueError("candidate_commercial_use_not_allowed")
    if public_distribution_allowed is not True:
        raise ValueError("candidate_public_distribution_not_allowed")
    if not rights_basis_id or not rights_checked_at:
        raise ValueError("candidate_rights_evidence_incomplete")

    if source_class == "licensed_asset_provider":
        if not license_name or not license_url or not attribution_text:
            raise ValueError("candidate_license_metadata_incomplete")
        if not valid_https_url(license_url):
            raise ValueError("candidate_license_url_must_be_https")
        if not isinstance(share_alike_required, bool):
            raise ValueError("candidate_share_alike_requirement_missing")

    payload_status = str(candidates_payload.get("status") or "").strip()
    if payload_status and payload_status != "review_only_not_live":
        raise ValueError("candidate_payload_not_review_only")

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

    proposed_status = proposed_status_for_source(source_class)
    candidate = {
        "product_id": product_id,
        "candidate_id": product.get("candidate_id"),
        "brand": product.get("brand"),
        "name": product.get("name"),
        "concentration": product.get("concentration"),
        "volume_ml": product.get("volume_ml"),
        "image_url": image_url,
        "review_status": "pending_review",
        "source_class": source_class,
        "proposed_image_status": proposed_status,
        "exact_variant_verified": True,
        "rights_evidence": {
            "rights_basis_id": rights_basis_id,
            "rights_status": VERIFIED_RIGHTS_STATUS,
            "rights_checked_at": rights_checked_at,
            "commercial_use_allowed": True,
            "public_distribution_allowed": True,
        },
    }
    if license_name:
        candidate["rights_evidence"]["license_name"] = license_name
    if license_url:
        candidate["rights_evidence"]["license_url"] = license_url
    if attribution_text:
        candidate["rights_evidence"]["attribution_text"] = attribution_text
    if share_alike_required is not None:
        candidate["rights_evidence"]["share_alike_required"] = share_alike_required
    if evidence_note:
        candidate["evidence_note"] = evidence_note.strip()

    existing = next(
        (
            row
            for row in candidates_payload.get("candidates", [])
            if str(row.get("product_id") or "").strip() == product_id
            and str(row.get("image_url") or "").strip() == image_url
        ),
        None,
    )

    if existing is not None:
        comparable_existing = dict(existing)
        comparable_existing.pop("registered_at", None)
        if comparable_existing != candidate:
            raise ValueError("existing_candidate_conflicts_with_registration")
        return {
            "candidate": existing,
            "already_registered": True,
            "will_change": False,
        }

    return {
        "candidate": candidate,
        "already_registered": False,
        "will_change": True,
    }


def apply_registration(
    candidates_payload: dict,
    plan: dict,
    *,
    registered_at: str,
) -> None:
    if not plan["will_change"]:
        return

    candidate = dict(plan["candidate"])
    candidate["registered_at"] = registered_at
    candidates_payload.setdefault("version", 1)
    candidates_payload["status"] = "review_only_not_live"
    candidates_payload.setdefault("candidates", []).append(candidate)
    candidates_payload["updated_at"] = registered_at


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Register one rights-cleared DUFYND image as a pending human-review candidate."
        )
    )
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--source-class", required=True, choices=sorted(APPROVABLE_SOURCE_CLASSES))
    parser.add_argument("--rights-basis-id", required=True)
    parser.add_argument("--rights-checked-at", required=True)
    parser.add_argument("--evidence-note")
    parser.add_argument("--license-name")
    parser.add_argument("--license-url")
    parser.add_argument("--attribution-text")
    parser.add_argument(
        "--share-alike-required",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--exact-variant-verified", action="store_true")
    parser.add_argument("--commercial-use-allowed", action="store_true")
    parser.add_argument("--public-distribution-allowed", action="store_true")
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        staging = load_json(args.staging)
        candidates = load_json(args.candidates)
        plan = registration_plan(
            staging,
            candidates,
            product_id=args.product_id,
            image_url=args.image_url,
            source_class=args.source_class,
            rights_basis_id=args.rights_basis_id,
            rights_checked_at=args.rights_checked_at,
            exact_variant_verified=args.exact_variant_verified,
            commercial_use_allowed=args.commercial_use_allowed,
            public_distribution_allowed=args.public_distribution_allowed,
            evidence_note=args.evidence_note,
            license_name=args.license_name,
            license_url=args.license_url,
            attribution_text=args.attribution_text,
            share_alike_required=args.share_alike_required,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.write and plan["will_change"]:
        registered_at = datetime.now(UTC).isoformat()
        apply_registration(
            candidates,
            plan,
            registered_at=registered_at,
        )
        write_json(args.candidates, candidates)

    output = {
        **plan,
        "mode": "WRITE" if args.write else "DRY-RUN",
    }
    if args.machine_readable:
        print(json.dumps(output, ensure_ascii=False))
    else:
        candidate = output["candidate"]
        print(
            "DUFYND rights-cleared image intake | "
            f"mode={output['mode']} | "
            f"product={candidate['product_id']} | "
            f"source={candidate['source_class']} | "
            f"will_change={output['will_change']} | "
            f"already_registered={output['already_registered']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
