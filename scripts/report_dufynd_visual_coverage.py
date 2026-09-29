from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_PRODUCTS = DATA_DIR / "scentai_products.json"
DEFAULT_REVIEW_QUEUE = DATA_DIR / "dufynd_product_visual_review_queue.json"
DEFAULT_APPROVAL_QUEUE = DATA_DIR / "scentai_image_approval_work_queue.json"

PRODUCT_TRUTH_ROLES = {"primary", "cutout"}
PRODUCT_TRUTH_FIDELITY = {"verified"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def visual_state(product: dict[str, Any]) -> str:
    visuals = list(product.get("visuals", []) or [])

    if any(
        str(visual.get("role") or "") in PRODUCT_TRUTH_ROLES
        and str(visual.get("fidelity_status") or "") in PRODUCT_TRUTH_FIDELITY
        and str(visual.get("url") or "").strip()
        for visual in visuals
    ):
        return "verified_product_truth"

    if any(
        str(visual.get("role") or "") == "editorial" and str(visual.get("url") or "").strip()
        for visual in visuals
    ):
        return "editorial_only"

    if any(str(visual.get("url") or "").strip() for visual in visuals):
        return "other_visual"

    return "missing_real_asset"


def priority_rank(value: str | None) -> tuple[int, str]:
    raw = str(value or "").strip().upper()
    if raw.startswith("P") and raw[1:].isdigit():
        return (int(raw[1:]), raw)
    return (999, raw)


def build_visual_coverage_report(
    products_payload: dict[str, Any],
    review_queue: dict[str, Any],
    approval_queue: dict[str, Any],
) -> dict[str, Any]:
    products = list(products_payload.get("products", []) or [])
    live_products = [
        product for product in products if str(product.get("product_id") or "").startswith("SC-")
    ]

    coverage_rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()

    for product in live_products:
        state = visual_state(product)
        state_counts[state] += 1
        coverage_rows.append(
            {
                "product_id": product.get("product_id"),
                "brand": product.get("brand"),
                "name": product.get("name"),
                "visual_state": state,
                "visual_count": len(product.get("visuals", []) or []),
            }
        )

    coverage_rows.sort(
        key=lambda row: (
            0 if row["visual_state"] == "missing_real_asset" else 1,
            str(row.get("brand") or "").casefold(),
            str(row.get("name") or "").casefold(),
        )
    )

    fidelity_review_queue: list[dict[str, Any]] = []
    for item in review_queue.get("items", []) or []:
        candidate_asset = str(item.get("candidate_asset") or "").strip()
        if not candidate_asset:
            continue
        fidelity_review_queue.append(
            {
                "priority": item.get("priority"),
                "product_id": item.get("product_id"),
                "status": item.get("status"),
                "candidate_asset": candidate_asset,
                "evidence_url": item.get("evidence_url"),
                "next_action": item.get("next_action"),
            }
        )

    fidelity_review_queue.sort(
        key=lambda row: (
            priority_rank(row.get("priority")),
            str(row.get("product_id") or ""),
        )
    )

    release_asset_queue: list[dict[str, Any]] = []
    for item in approval_queue.get("items", []) or []:
        release = item.get("release") or {}
        if not release:
            continue

        image_state = str(item.get("image_state") or "")
        blockers = list(item.get("blockers", []) or [])
        if image_state.startswith("approved_") and not blockers:
            continue

        release_asset_queue.append(
            {
                "release_id": release.get("release_id"),
                "release_order": release.get("release_order"),
                "position": release.get("position"),
                "product_id": item.get("product_id"),
                "brand": item.get("brand"),
                "name": item.get("name"),
                "image_state": image_state,
                "blockers": blockers,
                "next_action": item.get("next_action"),
                "approval_action_class": item.get("approval_action_class"),
            }
        )

    release_asset_queue.sort(
        key=lambda row: (
            int(row.get("release_order") or 999),
            int(row.get("position") or 999),
            str(row.get("product_id") or ""),
        )
    )

    total = len(live_products)
    verified = int(state_counts.get("verified_product_truth", 0))
    editorial = int(state_counts.get("editorial_only", 0))
    missing = int(state_counts.get("missing_real_asset", 0))
    other = int(state_counts.get("other_visual", 0))

    return {
        "live_product_count": total,
        "coverage": {
            "verified_product_truth": verified,
            "editorial_only": editorial,
            "other_visual": other,
            "missing_real_asset": missing,
            "has_real_visual": total - missing,
            "verified_product_truth_rate_pct": round((verified / total * 100.0), 2)
            if total
            else 0.0,
            "real_visual_coverage_rate_pct": round(((total - missing) / total * 100.0), 2)
            if total
            else 0.0,
        },
        "fidelity_review_ready_count": len(fidelity_review_queue),
        "fidelity_review_queue": fidelity_review_queue,
        "release_asset_blocked_count": len(release_asset_queue),
        "release_asset_queue": release_asset_queue,
        "live_visual_rows": coverage_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report DUFYND live visual coverage and the next review/acquisition priorities."
    )
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE)
    parser.add_argument("--approval-queue", type=Path, default=DEFAULT_APPROVAL_QUEUE)
    parser.add_argument("--machine-readable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = build_visual_coverage_report(
        load_json(args.products),
        load_json(args.review_queue),
        load_json(args.approval_queue),
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    coverage = report["coverage"]
    print(
        "DUFYND visual coverage | "
        f"live={report['live_product_count']} | "
        f"verified_truth={coverage['verified_product_truth']} | "
        f"editorial={coverage['editorial_only']} | "
        f"missing={coverage['missing_real_asset']}"
    )
    print(
        "Coverage rates | "
        f"real_visual={coverage['real_visual_coverage_rate_pct']}% | "
        f"verified_truth={coverage['verified_product_truth_rate_pct']}%"
    )

    if report["fidelity_review_queue"]:
        print("Human fidelity review queue:")
        for index, row in enumerate(report["fidelity_review_queue"], start=1):
            print(
                f"  {index:>2}. {row['priority'] or '-'} {row['product_id']} | "
                f"{row['candidate_asset']}"
            )

    if report["release_asset_queue"]:
        print("Release image acquisition queue:")
        for index, row in enumerate(report["release_asset_queue"], start=1):
            print(
                f"  {index:>2}. {row['release_id']} #{row['position']} "
                f"{row['product_id']} | {row['image_state']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
