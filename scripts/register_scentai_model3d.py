from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.scentai_model3d_guard import normalize_model_url, validated_model_sha256

DEFAULT_PRODUCTS = Path("examples/retail/data/scentai_products.json")
DEFAULT_CANDIDATES = Path("examples/retail/data/dufynd_model3d_candidates.json")
DEFAULT_PUBLIC_ROOT = Path("examples/retail/storefront-web/public")

VERIFIED_RIGHTS_STATUS = "verified_for_publisher_service"
APPROVABLE_SOURCE_CLASSES = {
    "dufynd_owned_3d_capture",
    "licensed_3d_asset",
    "written_asset_permission_3d",
    "written_manufacturer_3d_permission",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm(value: object) -> str:
    return str(value or "").strip()


def registration_plan(
    products: dict,
    candidates_payload: dict,
    *,
    product_id: str,
    model_url: str,
    model_sha256: str,
    source_class: str,
    rights_basis_id: str,
    rights_checked_at: str,
    exact_variant_verified: bool,
    commercial_use_allowed: bool,
    public_distribution_allowed: bool,
    interactive_web_display_allowed: bool,
    evidence_note: str | None = None,
    license_name: str | None = None,
    license_url: str | None = None,
    attribution_text: str | None = None,
) -> dict:
    product_id = _norm(product_id)
    model_url = normalize_model_url(model_url)
    model_sha256 = _norm(model_sha256).casefold()
    source_class = _norm(source_class)
    rights_basis_id = _norm(rights_basis_id)
    rights_checked_at = _norm(rights_checked_at)
    license_name = _norm(license_name) or None
    license_url = _norm(license_url) or None
    attribution_text = _norm(attribution_text) or None

    if not product_id:
        raise ValueError("product_id_required")
    if len(model_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in model_sha256
    ):
        raise ValueError("model_sha256_invalid")
    if source_class not in APPROVABLE_SOURCE_CLASSES:
        raise ValueError("model_source_class_not_approvable")
    if exact_variant_verified is not True:
        raise ValueError("model_exact_variant_not_verified")
    if commercial_use_allowed is not True:
        raise ValueError("model_commercial_use_not_allowed")
    if public_distribution_allowed is not True:
        raise ValueError("model_public_distribution_not_allowed")
    if interactive_web_display_allowed is not True:
        raise ValueError("model_interactive_web_display_not_allowed")
    if not rights_basis_id or not rights_checked_at:
        raise ValueError("model_rights_evidence_incomplete")

    if source_class == "licensed_3d_asset":
        if not license_name or not license_url:
            raise ValueError("model_license_metadata_incomplete")
        if not license_url.startswith("https://"):
            raise ValueError("model_license_url_must_be_https")

    payload_status = _norm(candidates_payload.get("status"))
    if payload_status and payload_status != "review_only_not_live":
        raise ValueError("model_candidate_payload_not_review_only")

    product = next(
        (row for row in products.get("products", []) if _norm(row.get("product_id")) == product_id),
        None,
    )
    if product is None:
        raise ValueError("model_product_not_found")

    volume_ml = product.get("volume_ml")
    if not isinstance(volume_ml, (int, float)) or volume_ml <= 0:
        raise ValueError("model_product_volume_missing")
    variant = f"{int(volume_ml) if float(volume_ml).is_integer() else volume_ml}ml"

    candidate = {
        "product_id": product_id,
        "brand": product.get("brand"),
        "name": product.get("name"),
        "concentration": product.get("concentration"),
        "volume_ml": volume_ml,
        "variant": variant,
        "role": "model_3d",
        "model_url": model_url,
        "model_sha256": model_sha256,
        "review_status": "pending_review",
        "geometry_review_required": True,
        "proposed_fidelity_status": "verified",
        "source_class": source_class,
        "exact_variant_verified": True,
        "rights_evidence": {
            "rights_basis_id": rights_basis_id,
            "rights_status": VERIFIED_RIGHTS_STATUS,
            "rights_checked_at": rights_checked_at,
            "commercial_use_allowed": True,
            "public_distribution_allowed": True,
            "interactive_web_display_allowed": True,
        },
    }
    if evidence_note:
        candidate["evidence_note"] = _norm(evidence_note)
    if license_name:
        candidate["rights_evidence"]["license_name"] = license_name
    if license_url:
        candidate["rights_evidence"]["license_url"] = license_url
    if attribution_text:
        candidate["rights_evidence"]["attribution_text"] = attribution_text

    existing = next(
        (
            row
            for row in candidates_payload.get("candidates", [])
            if _norm(row.get("product_id")) == product_id
            and _norm(row.get("model_url")) == model_url
        ),
        None,
    )
    if existing is not None:
        comparable = dict(existing)
        comparable.pop("registered_at", None)
        if comparable != candidate:
            raise ValueError("existing_model_candidate_conflicts_with_registration")
        return {"candidate": existing, "already_registered": True, "will_change": False}

    return {"candidate": candidate, "already_registered": False, "will_change": True}


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
        description="Register a local rights-cleared GLB as a DUFYND pending human-review candidate."
    )
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--source-class", required=True, choices=sorted(APPROVABLE_SOURCE_CLASSES))
    parser.add_argument("--rights-basis-id", required=True)
    parser.add_argument("--rights-checked-at", required=True)
    parser.add_argument("--evidence-note")
    parser.add_argument("--license-name")
    parser.add_argument("--license-url")
    parser.add_argument("--attribution-text")
    parser.add_argument("--exact-variant-verified", action="store_true")
    parser.add_argument("--commercial-use-allowed", action="store_true")
    parser.add_argument("--public-distribution-allowed", action="store_true")
    parser.add_argument("--interactive-web-display-allowed", action="store_true")
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--public-root", type=Path, default=DEFAULT_PUBLIC_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        products = load_json(args.products)
        candidates = load_json(args.candidates)
        model_url = normalize_model_url(args.model_url)
        model_sha256 = validated_model_sha256(args.public_root, model_url)
        plan = registration_plan(
            products,
            candidates,
            product_id=args.product_id,
            model_url=model_url,
            model_sha256=model_sha256,
            source_class=args.source_class,
            rights_basis_id=args.rights_basis_id,
            rights_checked_at=args.rights_checked_at,
            exact_variant_verified=args.exact_variant_verified,
            commercial_use_allowed=args.commercial_use_allowed,
            public_distribution_allowed=args.public_distribution_allowed,
            interactive_web_display_allowed=args.interactive_web_display_allowed,
            evidence_note=args.evidence_note,
            license_name=args.license_name,
            license_url=args.license_url,
            attribution_text=args.attribution_text,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.write and plan["will_change"]:
        apply_registration(candidates, plan, registered_at=datetime.now(UTC).isoformat())
        write_json(args.candidates, candidates)

    output = {**plan, "mode": "WRITE" if args.write else "DRY-RUN"}
    if args.machine_readable:
        print(json.dumps(output, ensure_ascii=False))
    else:
        candidate = output["candidate"]
        print(
            "DUFYND 3D model intake | "
            f"mode={output['mode']} | product={candidate['product_id']} | "
            f"status={candidate['review_status']} | will_change={output['will_change']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
