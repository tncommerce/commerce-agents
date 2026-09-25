"""Guard DUFYND product visual review queue against catalog drift."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

CATALOG = Path("examples/retail/data/scentai_products.json")
STATIC_CATALOG = Path("examples/retail/data/catalog.json")
QUEUE = Path("examples/retail/data/dufynd_product_visual_review_queue.json")
PUBLIC_ROOT = Path("examples/retail/storefront-web/public")
CANDIDATE_DIR = Path("examples/retail/review-assets/product-candidates")


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
        assert item["priority"] == "P0"
        assert item["asset"] == products[product_id]["image_url"]

        candidate = item.get("candidate_asset")
        if candidate:
            assert candidate.startswith("examples/retail/review-assets/product-candidates/")
            assert candidate != item["asset"]
            candidate_path = Path(candidate)
            assert candidate_path.is_file(), f"missing candidate asset: {candidate_path}"
            assert PUBLIC_ROOT not in candidate_path.parents

    assert len(items) == 4
    assert all(item.get("candidate_asset") for item in items)
    assert all(item["status"] == "candidate_generated_pending_reference_gate" for item in items)

    p0 = {item["product_id"] for item in items if item["priority"] == "P0"}
    assert p0 == {
        "SC-CREED-ABSOLU-AVENTUS-100",
        "SC-ARMANI-SWY-INTENSELY-100",
        "SC-PRADA-LHOMME-100",
        "SC-SOSPIRO-VIBRATO-100",
    }

    assert set(queue["cleared_for_editorial_use"]) == {
        "SC-AL-HARAMAIN-DETOUR-NOIR-100",
        "SC-CREED-AVENTUS-100",
        "SC-ARMAF-CDNIM-EDP-200",
        "SC-MAISON-ASRAR-VANGUARD-100",
        "SC-XERJOFF-NAXOS-100",
        "SC-WIDIAN-LONDON-EXTRAIT-50",
    }


def test_p0_candidates_are_reviewable_but_not_active_product_truth() -> None:
    assert not (PUBLIC_ROOT / "products/candidates").exists()

    source = json.loads(CATALOG.read_text(encoding="utf-8"))
    static_catalog = json.loads(STATIC_CATALOG.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    candidate_assets = {item["candidate_asset"] for item in queue["items"]}

    active_urls = {
        product["image_url"] for product in source["products"] if product.get("image_url")
    }
    for product in source["products"]:
        active_urls.update(
            visual["url"] for visual in product.get("visuals", []) if visual.get("url")
        )

    for product in static_catalog["products"]:
        if product.get("image_url"):
            active_urls.add(product["image_url"])
        attributes = product.get("attributes", {})
        for key in ("product_cutout_url", "product_model_3d_url"):
            if attributes.get(key):
                active_urls.add(attributes[key])

    candidate_names = {Path(candidate).name for candidate in candidate_assets}
    active_names = {Path(url).name for url in active_urls}
    assert candidate_names.isdisjoint(active_names)

    candidate_files = {path.as_posix() for path in CANDIDATE_DIR.iterdir() if path.is_file()}
    assert candidate_files == candidate_assets

    for candidate in candidate_assets:
        candidate_path = Path(candidate)
        with Image.open(candidate_path) as image:
            width, height = image.size

        assert width >= 1000
        assert height >= 1200
        assert height > width
