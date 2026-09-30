"""Keep DUFYND storefront audience categories mutually exclusive."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG_LIB = Path("examples/retail/storefront-web/lib/fragranceCatalog.ts")
CATALOG_BROWSER = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")
HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")
PRODUCTS = Path("examples/retail/data/scentai_products.json")


def test_unisex_has_priority_at_storefront_taxonomy_boundary() -> None:
    source = CATALOG_LIB.read_text(encoding="utf-8")

    assert 'if (normalized.has("unisex")) return "unisex";' in source
    assert 'if (hasMen && hasWomen) return "unisex";' in source
    assert "return catalogAudienceFor(fragrance.target_groups) === audience;" in source


def test_catalog_filter_uses_exclusive_audience_matcher() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert "fragranceMatchesAudience(fragrance, audience)" in source
    assert "fragrance.target_groups.includes(audience)" not in source


def test_homepage_uses_same_exclusive_audience_taxonomy() -> None:
    source = HOME.read_text(encoding="utf-8")

    assert "catalogAudienceFor(fragrance.target_groups)" in source
    assert "fragranceMatchesAudience(fragrance, audience)" in source
    assert "fragranceMatchesAudience(fragrance, audience.key)" in source
    assert ".target_groups.includes(audience" not in source


def test_live_data_contains_overlap_case_that_regression_covers() -> None:
    products = json.loads(PRODUCTS.read_text(encoding="utf-8"))["products"]

    overlapping = [
        product
        for product in products
        if "unisex" in (product.get("classification") or {}).get("scentai_target_groups", [])
        and (
            "men" in (product.get("classification") or {}).get("scentai_target_groups", [])
            or "women" in (product.get("classification") or {}).get("scentai_target_groups", [])
        )
    ]

    assert overlapping, "Regression fixture requires at least one overlapping source tag"


def test_mobile_catalog_filter_interaction_is_browser_covered() -> None:
    visual_qa = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs").read_text(
        encoding="utf-8"
    )

    assert 'label: "catalog-mobile-filter-interaction"' in visual_qa
    assert "viewport: { width: 390, height: 844 }" in visual_qa
    assert 'name: "Katalogfilter öffnen"' in visual_qa
    assert 'name: "Unisex"' in visual_qa
    assert 'url.searchParams.get("zielgruppe") === "unisex"' in visual_qa
    assert 'url.searchParams.get("utm_source") === "qa"' in visual_qa
    assert 'name: "Filter zurücksetzen"' in visual_qa
