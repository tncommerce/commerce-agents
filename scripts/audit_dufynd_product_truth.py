from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SOURCE = Path("examples/retail/data/scentai_products.json")
REVIEW_QUEUE = Path("examples/retail/data/dufynd_product_visual_review_queue.json")

TRUTH_ROLES = {"primary", "cutout"}
VARIANT_BOUND_VERIFIED_ROLES = {"primary", "cutout", "macro", "model_3d"}


def _normalized_variant(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "")


def _variant_matches(row: dict[str, Any], visual: dict[str, Any]) -> bool:
    expected = _normalized_variant(f"{row.get('volume_ml')}ml")
    actual = _normalized_variant(visual.get("variant"))
    return bool(expected and actual and expected == actual)


def evaluate_product_truth_coverage(
    source: dict[str, Any],
    review_queue: dict[str, Any],
) -> dict[str, Any]:
    queued = {
        str(item.get("product_id")): item
        for item in review_queue.get("items", [])
        if item.get("product_id")
    }
    products: list[dict[str, Any]] = []
    issues: list[str] = []

    for row in source.get("products", []):
        product_id = str(row.get("product_id") or "")
        if not product_id.startswith("SC-"):
            continue

        verified_truth_roles: list[str] = []
        verified_model_3d = False
        invalid_verified_variants: list[str] = []

        for visual in row.get("visuals", []) or []:
            role = str(visual.get("role") or "")
            fidelity = str(visual.get("fidelity_status") or "")

            if fidelity != "verified":
                continue

            if role in VARIANT_BOUND_VERIFIED_ROLES and not _variant_matches(row, visual):
                invalid_verified_variants.append(role)
                issues.append(
                    f"{product_id}: verified {role} does not match {row.get('volume_ml')}ml variant"
                )
                continue

            if role in TRUTH_ROLES:
                verified_truth_roles.append(role)
            elif role == "model_3d":
                verified_model_3d = True

        queue_item = queued.get(product_id)
        products.append(
            {
                "product_id": product_id,
                "brand": row.get("brand"),
                "name": row.get("name"),
                "volume_ml": row.get("volume_ml"),
                "verified_product_truth": bool(verified_truth_roles),
                "verified_truth_roles": sorted(set(verified_truth_roles)),
                "verified_model_3d": verified_model_3d,
                "review_status": queue_item.get("status") if queue_item else None,
                "invalid_verified_variants": sorted(set(invalid_verified_variants)),
            }
        )

    verified_truth_products = [
        product["product_id"] for product in products if product["verified_product_truth"]
    ]
    verified_model_products = [
        product["product_id"] for product in products if product["verified_model_3d"]
    ]
    queued_products = [product["product_id"] for product in products if product["review_status"]]

    return {
        "ok": not issues,
        "summary": {
            "products": len(products),
            "verified_product_truth": len(verified_truth_products),
            "verified_model_3d": len(verified_model_products),
            "review_queue": len(queued_products),
            "without_verified_product_truth": (len(products) - len(verified_truth_products)),
        },
        "verified_product_truth_product_ids": verified_truth_products,
        "verified_model_3d_product_ids": verified_model_products,
        "review_queue_product_ids": queued_products,
        "issues": issues,
        "products": products,
    }


def load_report(
    source_path: Path = SOURCE,
    review_queue_path: Path = REVIEW_QUEUE,
) -> dict[str, Any]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    review_queue = json.loads(review_queue_path.read_text(encoding="utf-8"))
    return evaluate_product_truth_coverage(source, review_queue)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit DUFYND verified product-truth and 3D coverage."
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print summary and issues only.",
    )
    args = parser.parse_args()

    report = load_report()
    payload = (
        {
            "ok": report["ok"],
            "summary": report["summary"],
            "verified_product_truth_product_ids": (report["verified_product_truth_product_ids"]),
            "verified_model_3d_product_ids": report["verified_model_3d_product_ids"],
            "review_queue_product_ids": report["review_queue_product_ids"],
            "issues": report["issues"],
        }
        if args.compact
        else report
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
