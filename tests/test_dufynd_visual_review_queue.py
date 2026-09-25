"""Guard DUFYND visual-review items from being promoted as verified product truth."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("examples/retail/data/catalog.json")
QUEUE = Path("examples/retail/data/dufynd_product_visual_review_queue.json")


def test_p0_visuals_are_not_verified_product_layers() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    products = {
        row["product_id"]: row
        for row in catalog["products"]
        if str(row.get("product_id", "")).startswith("SC-")
    }

    for item in queue["items"]:
        if item.get("priority") != "P0":
            continue

        product_id = item["product_id"]
        assert product_id in products, product_id
        assert item.get("evidence_url"), product_id
        assert item.get("next_action"), product_id

        product = products[product_id]
        attributes = product.get("attributes") or {}
        asset = item["asset"]

        assert attributes.get("product_cutout_url") != asset, (
            f"{product_id}: P0 editorial asset must not become verified cutout"
        )
        assert attributes.get("product_model_3d_url") != asset, (
            f"{product_id}: P0 editorial asset must not become a 3D source"
        )
