"""Report all currently pending DUFYND human visual-fidelity reviews.

This is read-only. It does not approve, activate, publish, register rights, or
move any candidate into the public storefront.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DATA = Path("examples/retail/data")
STAGED_PACKET = DATA / "dufynd_staged_image_fidelity_candidates_20260930.json"
VISUAL_QUEUE = DATA / "dufynd_product_visual_review_queue.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pending_visual_reviews(
    staged_packet: dict[str, Any],
    visual_queue: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for row in staged_packet.get("items", []):
        if row.get("status") != "pending_human_fidelity":
            continue
        items.append(
            {
                "product_id": row["product_id"],
                "candidate_asset": row["candidate_asset"],
                "status": row["status"],
                "reference_url": row.get("reference_url"),
                "review_focus": row.get("review_focus", []),
                "source_manifest": str(STAGED_PACKET),
                "public_activation": bool(row.get("public_activation", False)),
                "catalog_promotion": bool(row.get("catalog_promotion", False)),
            }
        )

    for row in visual_queue.get("items", []):
        if row.get("status") not in {
            "candidate_generated_pending_human_fidelity",
            "pending_human_fidelity",
        }:
            continue
        provenance = row.get("candidate_provenance") or {}
        items.append(
            {
                "product_id": row["product_id"],
                "candidate_asset": row["candidate_asset"],
                "status": row["status"],
                "reference_url": row.get("evidence_url"),
                "review_focus": [],
                "source_manifest": str(VISUAL_QUEUE),
                "public_activation": bool(provenance.get("public_activation", False)),
                "catalog_promotion": False,
            }
        )

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        product_id = str(item["product_id"])
        if product_id in seen:
            raise ValueError(f"duplicate pending visual review: {product_id}")
        seen.add(product_id)
        if item["public_activation"] or item["catalog_promotion"]:
            raise ValueError(f"pending candidate is already active: {product_id}")
        unique.append(item)

    return sorted(unique, key=lambda item: str(item["product_id"]))


def build_report() -> dict[str, Any]:
    items = pending_visual_reviews(load_json(STAGED_PACKET), load_json(VISUAL_QUEUE))
    return {
        "status": "waiting_human_fidelity",
        "pending_count": len(items),
        "automatic_approval_allowed": False,
        "automatic_activation_allowed": False,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    report = build_report()
    if args.machine_readable:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print(f"Pending visual fidelity reviews: {report['pending_count']}")
    for item in report["items"]:
        print(f"- {item['product_id']} | {item['status']} | {item['candidate_asset']}")
    print("No pending candidate is approved or activated by this report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
