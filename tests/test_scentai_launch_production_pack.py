from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_launch_production_pack_one_matches_scripts_and_product_assets() -> None:
    pack = load_json(
        DATA_DIR / "scentai_launch_production_pack_01.json"
    )
    scripts = load_json(
        DATA_DIR / "scentai_launch_scripts_batch_01.json"
    )
    products = load_json(DATA_DIR / "scentai_products.json")

    script_by_id = {
        row["content_id"]: row
        for row in scripts["creatives"]
    }
    product_by_id = {
        row["product_id"]: row
        for row in products["products"]
    }

    assert len(pack["creatives"]) == 5

    for creative in pack["creatives"]:
        content_id = creative["content_id"]
        assert content_id in script_by_id

        script = script_by_id[content_id]
        assert len(creative["scene_assets"]) == len(script["scenes"])

        packed_product_ids = {
            row["product_id"]
            for row in creative["required_product_assets"]
        }
        assert packed_product_ids == set(script["product_ids"])

        for asset in creative["required_product_assets"]:
            product = product_by_id[asset["product_id"]]
            assert asset["image_url"] == product["image_url"]
            assert asset["image_url"].startswith("/products/")

        assert creative["production_status"] in {
            "asset_ready",
            "asset_ready_with_text_reference",
        }


def test_production_pack_keeps_relationship_labels_explicit() -> None:
    pack = load_json(
        DATA_DIR / "scentai_launch_production_pack_01.json"
    )

    relationship_instructions = [
        scene["instruction"].casefold()
        for creative in pack["creatives"]
        for scene in creative["scene_assets"]
        if scene["component"] == "relationship_badge"
    ]

    assert relationship_instructions
    assert any("clone" in value for value in relationship_instructions)
    assert any("inspired" in value for value in relationship_instructions)
