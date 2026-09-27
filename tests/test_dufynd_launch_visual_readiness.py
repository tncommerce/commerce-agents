"""Keep strict launch readiness blocked by unresolved live P0 product visuals."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("examples/retail/data/catalog.json")
QUEUE = Path("examples/retail/data/dufynd_product_visual_review_queue.json")
READINESS = Path("examples/retail/storefront-web/scripts/check-launch-readiness.mjs")


def test_active_p0_visual_reviews_are_live_launch_blockers() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    live_ids = {
        row["product_id"]
        for row in catalog["products"]
        if str(row.get("product_id", "")).startswith("SC-")
        and row.get("category") == "fragrance"
        and row.get("in_stock") is not False
    }
    blocking = {
        item["product_id"]
        for item in queue["items"]
        if item.get("priority") == "P0" and item.get("product_id") in live_ids
    }

    assert blocking == {
        "SC-CREED-ABSOLU-AVENTUS-100",
        "SC-ARMANI-SWY-INTENSELY-100",
        "SC-PRADA-LHOMME-100",
        "SC-SOSPIRO-VIBRATO-100",
    }


def test_launch_checker_consumes_visual_review_queue_as_gate() -> None:
    source = READINESS.read_text(encoding="utf-8")

    assert 'readJson("dufynd_product_visual_review_queue.json")' in source
    assert 'item.priority === "P0"' in source
    assert 'liveProductIds.has(String(item.product_id || ""))' in source
    assert '"product_visual_fidelity"' in source
    assert 'blockingP0ProductIds.length ? "gate" : "pass"' in source
