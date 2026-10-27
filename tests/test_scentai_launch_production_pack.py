from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
PUBLIC_ROOT = Path("examples/retail/storefront-web/public")
# These prepared social assets retain their original channel-specific use.
# The new storefront feed-photo permission does not authorize replacing them
# with retailer photographs in existing social/launch packs.
RETAINED_PREPARED_ASSETS = {
    "SC-PDM-LAYTON-125": "/products/pilot/pdm-layton-editorial.webp",
    "SC-PDM-ALTHAIR-125": "/products/pilot/pdm-althair-editorial.webp",
    "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100": "/products/pilot/bois-imperial-editorial.webp",
    "SC-ARMANI-SWY-INTENSELY-100": "/products/armani-swy-intensely-100-cutout-production.webp",
    "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100": "/products/pilot/valentino-born-in-roma-intense-editorial.webp",
}
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
    product_by_id = {row["product_id"]: row for row in products["products"]}

    all_content_ids: list[str] = []
    retained_product_ids: set[str] = set()

    for pack_name, script_name in PACK_SCRIPT_PAIRS:
        pack = load_json(DATA_DIR / pack_name)
        scripts = load_json(DATA_DIR / script_name)
        script_by_id = {row["content_id"]: row for row in scripts["creatives"]}

        assert len(pack["creatives"]) == 5

        for creative in pack["creatives"]:
            content_id = creative["content_id"]
            all_content_ids.append(content_id)
            assert content_id in script_by_id

            script = script_by_id[content_id]
            assert len(creative["scene_assets"]) == len(script["scenes"])

            packed_product_ids = {row["product_id"] for row in creative["required_product_assets"]}
            assert packed_product_ids == set(script["product_ids"])

            for asset in creative["required_product_assets"]:
                product = product_by_id[asset["product_id"]]
                assert asset["image_url"].startswith("/products/")
                assert (PUBLIC_ROOT / asset["image_url"].removeprefix("/")).is_file()
                if asset["image_url"] != product["image_url"]:
                    assert asset["image_url"] == RETAINED_PREPARED_ASSETS[asset["product_id"]]
                    retained_product_ids.add(asset["product_id"])
                    matches = [
                        visual
                        for visual in product["visuals"]
                        if visual["url"] == asset["image_url"]
                    ]
                    assert len(matches) == 1
                    visual = matches[0]
                    assert visual["variant"] == f"{product['volume_ml']}ml"
                    if asset["product_id"] == "SC-ARMANI-SWY-INTENSELY-100":
                        assert visual["provenance"] == "dufynd_generated"
                        assert visual["role"] == "cutout"
                        assert visual["fidelity_status"] == "verified"
                    else:
                        assert visual["provenance"] == "legacy_catalog"
                        assert visual["role"] == "editorial"
                        assert visual["fidelity_status"] == "editorial_only"

            assert creative["production_status"] in {
                "asset_ready",
                "asset_ready_with_text_reference",
            }

    assert len(all_content_ids) == 15
    assert len(all_content_ids) == len(set(all_content_ids))
    assert retained_product_ids == set(RETAINED_PREPARED_ASSETS)


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
    assert any("alternative" in value for value in relationship_instructions)
