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

ACTIVE_P0 = {"SC-CREED-ABSOLU-AVENTUS-100"}
APPROVED_P0 = {
    "SC-ARMANI-SWY-INTENSELY-100",
    "SC-PRADA-LHOMME-100",
    "SC-SOSPIRO-VIBRATO-100",
}


def test_product_visual_review_queue_references_catalog_products() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    products = {product["product_id"]: product for product in catalog["products"]}
    items = queue["items"]
    approved = queue["approved_product_truth"]

    assert {item["product_id"] for item in items} == ACTIVE_P0
    assert all(item["priority"] == "P0" for item in items)
    assert all(item["status"] == "human_fidelity_approved_pending_promotion" for item in items)

    for item in items:
        product_id = item["product_id"]
        assert product_id in products
        assert item["asset"] == products[product_id]["image_url"]
        candidate = Path(item["candidate_asset"])
        assert candidate.is_file(), f"missing candidate asset: {candidate}"
        assert PUBLIC_ROOT not in candidate.parents
        assert item["approval_basis"] == "explicit_user_visual_approval_2026-09-30"
        assert item["candidate_provenance"]["approval_status"] == "human_fidelity_approved"
        assert item["candidate_provenance"]["public_activation"] is False

    approved_by_id = {item["product_id"]: item for item in approved}
    assert set(approved_by_id) == APPROVED_P0

    for product_id, record in approved_by_id.items():
        assert record["status"] == "human_fidelity_approved_promoted"
        assert record["approval_basis"] == "explicit_user_visual_approval_2026-09-29"
        assert record["provenance"] == "dufynd_generated"
        assert record["fidelity_status"] == "verified"
        assert record["variant"] == "100ml"

        source_candidate = Path(record["source_candidate_asset"])
        assert source_candidate.is_file()
        assert PUBLIC_ROOT not in source_candidate.parents

        public_asset = PUBLIC_ROOT / record["public_asset"].removeprefix("/")
        assert public_asset.is_file(), f"missing promoted asset: {public_asset}"

        product = products[product_id]
        assert product["image_url"] == record["public_asset"]
        assert any(
            visual.get("url") == record["public_asset"]
            and visual.get("role") in {"primary", "cutout"}
            and visual.get("fidelity_status") == "verified"
            and visual.get("variant") == "100ml"
            for visual in product.get("visuals", [])
        )

    assert set(queue["cleared_for_editorial_use"]) == {
        "SC-AL-HARAMAIN-DETOUR-NOIR-100",
        "SC-CREED-AVENTUS-100",
        "SC-ARMAF-CDNIM-EDP-200",
        "SC-MAISON-ASRAR-VANGUARD-100",
        "SC-XERJOFF-NAXOS-100",
        "SC-WIDIAN-LONDON-EXTRAIT-50",
    }


def test_pending_candidates_stay_private_and_approved_assets_are_public_product_truth() -> None:
    assert not (PUBLIC_ROOT / "products/candidates").exists()

    source = json.loads(CATALOG.read_text(encoding="utf-8"))
    static_catalog = json.loads(STATIC_CATALOG.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    active_candidate_assets = {item["candidate_asset"] for item in queue["items"]}
    historical_candidate_assets = {
        history["candidate_asset"]
        for item in queue["items"]
        for history in item.get("candidate_history", [])
    }
    approved_source_assets = {
        item["source_candidate_asset"] for item in queue["approved_product_truth"]
    }
    all_internal_assets = (
        active_candidate_assets | historical_candidate_assets | approved_source_assets
    )

    candidate_files = {path.as_posix() for path in CANDIDATE_DIR.iterdir() if path.is_file()}
    assert candidate_files == all_internal_assets

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

    internal_names = {Path(candidate).name for candidate in all_internal_assets}
    active_names = {Path(url).name for url in active_urls}
    assert internal_names.isdisjoint(active_names)

    for candidate in all_internal_assets:
        with Image.open(Path(candidate)) as image:
            width, height = image.size
        assert width >= 1000
        assert height >= 1200
        assert height > width

    for record in queue["approved_product_truth"]:
        assert record["public_asset"] in active_urls
