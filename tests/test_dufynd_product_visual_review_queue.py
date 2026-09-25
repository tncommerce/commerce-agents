"""Guard DUFYND product visual review queue against catalog drift."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("examples/retail/data/scentai_products.json")
QUEUE = Path("examples/retail/data/dufynd_product_visual_review_queue.json")


def test_product_visual_review_queue_references_catalog_products() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    products = {product["product_id"]: product for product in catalog["products"]}
    items = queue["items"]

    assert items
    assert len({item["product_id"] for item in items}) == len(items)

    for item in items:
        product_id = item["product_id"]
        assert product_id in products
        assert item["priority"] in {"P0", "P1"}
        assert item["asset"] == products[product_id]["image_url"]

    assert len(items) == 5

    p0 = {
        item["product_id"]
        for item in items
        if item["priority"] == "P0"
    }
    assert p0 == {
        "SC-CREED-ABSOLU-AVENTUS-100",
        "SC-XERJOFF-NAXOS-100",
        "SC-ARMANI-SWY-INTENSELY-100",
        "SC-PRADA-LHOMME-100",
    }

    p1 = {
        item["product_id"]
        for item in items
        if item["priority"] == "P1"
    }
    assert p1 == {"SC-SOSPIRO-VIBRATO-100"}

    assert set(queue["cleared_for_editorial_use"]) == {
        "SC-AL-HARAMAIN-DETOUR-NOIR-100",
        "SC-CREED-AVENTUS-100",
        "SC-ARMAF-CDNIM-EDP-200",
        "SC-MAISON-ASRAR-VANGUARD-100",
    }
