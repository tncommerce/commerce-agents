from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.register_scentai_model3d import APPROVABLE_SOURCE_CLASSES, VERIFIED_RIGHTS_STATUS
from scripts.scentai_model3d_guard import normalize_model_url, validated_model_sha256

DEFAULT_PRODUCTS = Path("examples/retail/data/scentai_products.json")
DEFAULT_CANDIDATES = Path("examples/retail/data/dufynd_model3d_candidates.json")
DEFAULT_PUBLIC_ROOT = Path("examples/retail/storefront-web/public")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm(value: object) -> str:
    return str(value or "").strip()


def approval_plan(
    products: dict,
    candidates_payload: dict,
    *,
    product_id: str,
    model_url: str,
    actual_model_sha256: str,
    human_visual_approval: bool,
    replace_verified_model: bool = False,
) -> dict:
    product_id = _norm(product_id)
    model_url = normalize_model_url(model_url)
    actual_model_sha256 = _norm(actual_model_sha256).casefold()

    if human_visual_approval is not True:
        raise ValueError("human_3d_geometry_approval_required")
    if _norm(candidates_payload.get("status")) != "review_only_not_live":
        raise ValueError("model_candidate_payload_not_review_only")

    candidate = next(
        (
            row
            for row in candidates_payload.get("candidates", [])
            if _norm(row.get("product_id")) == product_id
            and _norm(row.get("model_url")) == model_url
        ),
        None,
    )
    if candidate is None:
        raise ValueError("model_review_candidate_not_found")
    if _norm(candidate.get("review_status")) not in {"pending_review", "approved"}:
        raise ValueError("model_candidate_not_approvable")
    if candidate.get("exact_variant_verified") is not True:
        raise ValueError("model_exact_variant_not_verified")
    if candidate.get("geometry_review_required") is not True:
        raise ValueError("model_geometry_review_contract_missing")
    if _norm(candidate.get("proposed_fidelity_status")) != "verified":
        raise ValueError("model_candidate_fidelity_invalid")
    if _norm(candidate.get("source_class")) not in APPROVABLE_SOURCE_CLASSES:
        raise ValueError("model_source_class_not_approvable")

    expected_sha256 = _norm(candidate.get("model_sha256")).casefold()
    if not expected_sha256 or actual_model_sha256 != expected_sha256:
        raise ValueError("model_asset_hash_mismatch")

    rights = candidate.get("rights_evidence") or {}
    if _norm(rights.get("rights_status")) != VERIFIED_RIGHTS_STATUS:
        raise ValueError("model_rights_not_verified")
    for field, error in (
        ("commercial_use_allowed", "model_commercial_use_not_allowed"),
        ("public_distribution_allowed", "model_public_distribution_not_allowed"),
        ("interactive_web_display_allowed", "model_interactive_web_display_not_allowed"),
    ):
        if rights.get(field) is not True:
            raise ValueError(error)

    rights_basis_id = _norm(rights.get("rights_basis_id"))
    rights_checked_at = _norm(rights.get("rights_checked_at"))
    if not rights_basis_id or not rights_checked_at:
        raise ValueError("model_rights_evidence_incomplete")

    product = next(
        (
            row
            for row in products.get("products", [])
            if _norm(row.get("product_id")) == product_id
        ),
        None,
    )
    if product is None:
        raise ValueError("model_product_not_found")

    expected_variant = f"{int(product['volume_ml']) if float(product['volume_ml']).is_integer() else product['volume_ml']}ml"
    if _norm(candidate.get("variant")).replace(" ", "").casefold() != expected_variant.casefold():
        raise ValueError("model_candidate_variant_mismatch")

    existing = next(
        (
            visual
            for visual in product.get("visuals", [])
            if _norm(visual.get("role")) == "model_3d"
            and _norm(visual.get("fidelity_status")) == "verified"
        ),
        None,
    )
    already_same = bool(
        existing
        and _norm(existing.get("url")) == model_url
        and _norm(existing.get("model_sha256")).casefold() == actual_model_sha256
    )
    if existing and not already_same and not replace_verified_model:
        raise ValueError("verified_model_already_exists_use_replace_flag")

    return {
        "product_id": product_id,
        "model_url": model_url,
        "model_sha256": actual_model_sha256,
        "variant": expected_variant,
        "source_class": candidate["source_class"],
        "rights_basis_id": rights_basis_id,
        "rights_checked_at": rights_checked_at,
        "attribution_text": rights.get("attribution_text"),
        "already_approved": already_same,
        "will_change": not already_same,
    }


def apply_approval(
    products: dict,
    candidates_payload: dict,
    plan: dict,
    *,
    reviewed_at: str,
) -> None:
    candidate = next(
        row
        for row in candidates_payload.get("candidates", [])
        if _norm(row.get("product_id")) == plan["product_id"]
        and _norm(row.get("model_url")) == plan["model_url"]
    )
    product = next(
        row
        for row in products.get("products", [])
        if _norm(row.get("product_id")) == plan["product_id"]
    )

    if plan["will_change"]:
        visuals = [
            visual
            for visual in product.get("visuals", [])
            if _norm(visual.get("role")) != "model_3d"
        ]
        visual = {
            "role": "model_3d",
            "url": plan["model_url"],
            "provenance": plan["source_class"],
            "fidelity_status": "verified",
            "variant": plan["variant"],
            "model_sha256": plan["model_sha256"],
            "rights_basis_id": plan["rights_basis_id"],
            "rights_checked_at": plan["rights_checked_at"],
        }
        if plan.get("attribution_text"):
            visual["attribution_text"] = plan["attribution_text"]
        visuals.append(visual)
        product["visuals"] = visuals

    candidate["review_status"] = "approved"
    candidate["geometry_review_required"] = False
    candidate["reviewed_at"] = reviewed_at
    candidate["approved_model_sha256"] = plan["model_sha256"]


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Activate one rights-cleared DUFYND GLB only after explicit human geometry review."
    )
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--human-visual-approval", action="store_true")
    parser.add_argument("--replace-verified-model", action="store_true")
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
        actual_sha256 = validated_model_sha256(args.public_root, model_url)
        plan = approval_plan(
            products,
            candidates,
            product_id=args.product_id,
            model_url=model_url,
            actual_model_sha256=actual_sha256,
            human_visual_approval=args.human_visual_approval,
            replace_verified_model=args.replace_verified_model,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.write:
        reviewed_at = datetime.now(UTC).isoformat()
        apply_approval(products, candidates, plan, reviewed_at=reviewed_at)
        write_json(args.products, products)
        write_json(args.candidates, candidates)

    output = {**plan, "mode": "WRITE" if args.write else "DRY-RUN"}
    if args.machine_readable:
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(
            "DUFYND 3D model approval | "
            f"mode={output['mode']} | product={output['product_id']} | "
            f"will_change={output['will_change']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
