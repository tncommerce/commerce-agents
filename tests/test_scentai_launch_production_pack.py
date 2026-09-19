from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
PACK_SCRIPT_PAIRS = (
    (
        "scentai_launch_production_pack_01.json",
        "scentai_launch_scripts_batch_01.json",
    ),
    (
        "scentai_launch_production_pack_02.json",
        "scentai_launch_scripts_batch_02.json",
    ),
    (
        "scentai_launch_production_pack_03.json",
        "scentai_launch_scripts_batch_03.json",
    ),
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def production_creatives() -> list[dict]:
    rows: list[dict] = []
    for pack_name, _ in PACK_SCRIPT_PAIRS:
        pack = load_json(DATA_DIR / pack_name)
        rows.extend(pack["creatives"])
    return rows


def test_launch_production_packs_match_scripts_and_product_assets() -> None:
    products = load_json(DATA_DIR / "scentai_products.json")
    product_by_id = {
        row["product_id"]: row
        for row in products["products"]
    }

    all_content_ids: list[str] = []

    for pack_name, script_name in PACK_SCRIPT_PAIRS:
        pack = load_json(DATA_DIR / pack_name)
        scripts = load_json(DATA_DIR / script_name)
        script_by_id = {
            row["content_id"]: row
            for row in scripts["creatives"]
        }

        assert len(pack["creatives"]) == 5

        for creative in pack["creatives"]:
            content_id = creative["content_id"]
            all_content_ids.append(content_id)
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

    assert len(all_content_ids) == 15
    assert len(all_content_ids) == len(set(all_content_ids))


def test_production_packs_keep_relationship_labels_explicit() -> None:
    relationship_instructions = [
        scene["instruction"].casefold()
        for creative in production_creatives()
        for scene in creative["scene_assets"]
        if scene["component"] == "relationship_badge"
    ]

    assert relationship_instructions
    assert any("clone" in value for value in relationship_instructions)
    assert any("inspired" in value for value in relationship_instructions)
    assert any(
        "alternative" in value
        for value in relationship_instructions
    )
