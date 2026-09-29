from __future__ import annotations

import json
from pathlib import Path

SOURCE = Path("examples/retail/data/scentai_products.json")


def _products() -> list[dict]:
    return json.loads(SOURCE.read_text(encoding="utf-8"))["products"]


def test_legacy_pilot_art_is_explicit_storefront_presentation() -> None:
    pilot_rows = [
        product
        for product in _products()
        if str(product.get("image_url") or "").startswith("/products/pilot/")
    ]

    assert len(pilot_rows) == 28

    for product in pilot_rows:
        matches = [
            visual
            for visual in product.get("visuals", [])
            if visual.get("url") == product["image_url"]
        ]
        assert len(matches) == 1, product["product_id"]

        visual = matches[0]
        assert visual["role"] == "editorial"
        assert visual["composition"] == "product_scene"
        assert visual["fidelity_status"] == "editorial_only"
        assert visual["provenance"] == "legacy_catalog"


def test_pilot_presentation_metadata_never_claims_product_truth() -> None:
    for product in _products():
        for visual in product.get("visuals", []):
            if str(visual.get("url") or "").startswith("/products/pilot/"):
                assert visual["role"] == "editorial"
                assert visual["fidelity_status"] != "verified"
