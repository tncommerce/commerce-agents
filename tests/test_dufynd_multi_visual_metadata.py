"""Validate DUFYND structured fragrance visual metadata."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("examples/retail/data/catalog.json")
SOURCE = Path("examples/retail/data/scentai_products.json")
ADAPTER = Path("examples/retail/storefront-web/lib/fragranceCatalog.ts")
PUBLIC_ROOT = Path("examples/retail/storefront-web/public")

ALLOWED_ROLES = {"primary", "cutout", "editorial", "macro", "model_3d"}
ALLOWED_STATUS = {"verified", "pending_review", "editorial_only", "rejected"}
ALLOWED_COMPOSITIONS = {"product_scene", "bottle_free_backdrop"}


def test_structured_visual_metadata_is_safe_and_consistent() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))

    catalog_by_id = {
        row["product_id"]: row
        for row in catalog["products"]
        if str(row.get("product_id", "")).startswith("SC-")
    }

    rows_with_visuals = [row for row in source["products"] if row.get("visuals")]
    assert rows_with_visuals, "Expected at least one multi-visual fragrance pilot"

    for row in rows_with_visuals:
        product_id = row["product_id"]
        assert product_id in catalog_by_id

        seen_urls: set[str] = set()
        for visual in row["visuals"]:
            assert visual["role"] in ALLOWED_ROLES
            assert visual["fidelity_status"] in ALLOWED_STATUS
            assert visual["url"].startswith(("/", "https://"))
            if visual["url"].startswith("/"):
                local_path = PUBLIC_ROOT / visual["url"].removeprefix("/")
                assert local_path.is_file(), (
                    f"{product_id}: structured visual file is missing: {visual['url']}"
                )
            assert str(visual.get("provenance") or "").strip(), (
                f"{product_id}: structured visual is missing provenance"
            )
            assert visual["url"] not in seen_urls, (
                f"{product_id}: duplicate visual URL {visual['url']}"
            )
            seen_urls.add(visual["url"])

            composition = visual.get("composition")
            if composition is not None:
                assert composition in ALLOWED_COMPOSITIONS

            if composition == "bottle_free_backdrop":
                assert visual["role"] == "editorial"
                assert visual["fidelity_status"] == "editorial_only"

            if visual["role"] == "editorial":
                assert visual["fidelity_status"] != "verified", (
                    f"{product_id}: editorial art must not be product truth"
                )

            if visual["role"] == "model_3d":
                assert visual["url"].lower().split("?", 1)[0].endswith(".glb"), (
                    f"{product_id}: model_3d visual must be a GLB"
                )


def test_naxos_visual_pilot_matches_legacy_product_layer() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))

    catalog_row = next(
        row for row in catalog["products"] if row["product_id"] == "SC-XERJOFF-NAXOS-100"
    )
    source_row = next(
        row for row in source["products"] if row["product_id"] == "SC-XERJOFF-NAXOS-100"
    )

    visuals = {visual["role"]: visual for visual in source_row["visuals"]}
    assert visuals["cutout"]["fidelity_status"] == "verified"
    assert visuals["cutout"]["url"] == (catalog_row["attributes"]["product_cutout_url"])
    assert catalog_row["image_url"] == "/products/naxos-cutout-production.png"
    assert source_row["image_url"] == "/products/naxos-cutout-production.png"
    assert visuals["editorial"]["fidelity_status"] == "editorial_only"
    assert visuals["editorial"]["composition"] == "bottle_free_backdrop"
    assert visuals["editorial"]["url"] == "/products/naxos-bottle-free-backdrop.webp"


def test_model_3d_activation_requires_structured_verified_asset() -> None:
    adapter = ADAPTER.read_text(encoding="utf-8")

    assert 'visual.role === "model_3d"' in adapter
    assert 'visual.fidelity_status === "verified"' in adapter
    assert "attributes.product_model_3d_url" not in adapter


def test_bottle_free_backdrop_requires_explicit_editorial_metadata() -> None:
    adapter = ADAPTER.read_text(encoding="utf-8")

    assert 'visual.composition === "bottle_free_backdrop"' in adapter
    assert 'visual.role === "editorial"' in adapter
    assert 'visual.fidelity_status === "editorial_only"' in adapter
