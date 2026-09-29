from __future__ import annotations

from pathlib import Path

ROOT = Path("examples/retail/storefront-web")


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_discovery_surfaces_use_presentation_visual() -> None:
    catalog_lib = _read("lib/fragranceCatalog.ts")
    product_tile = _read("components/ProductTile.tsx")
    catalog_browser = _read("components/FragranceCatalogBrowser.tsx")
    discovery_page = _read("app/duft/page.tsx")
    detail_page = _read("app/duft/[slug]/page.tsx")
    acquisition = _read("components/AcquisitionLanding.tsx")
    library_hub = _read("components/FragranceLibraryHub.tsx")

    assert "presentation_visual: FragranceVisualAsset | null" in catalog_lib
    assert "composition === \"product_scene\"" in catalog_lib
    assert "fragrance?.presentation_visual" in product_tile
    assert "fragrance.presentation_visual" in catalog_browser
    assert "fragrance.presentation_visual" in discovery_page
    assert "item.fragrance.presentation_visual" in detail_page
    assert "fragrance.presentation_visual" in acquisition
    assert "fragrance.presentation_visual" in library_hub


def test_truth_sensitive_detail_surface_stays_on_preferred_visual() -> None:
    detail_page = _read("app/duft/[slug]/page.tsx")

    assert "const heroVisual = fragrance.preferred_visual;" in detail_page
    assert "heroIsProductTruth && heroVisual?.url" in detail_page
    assert "verifiedProductImage" in detail_page


def test_product_tile_missing_visual_uses_neutral_fragrance_stage() -> None:
    product_tile = _read("components/ProductTile.tsx")

    assert '<FragranceVisual\n        alt={product.title}\n        variant="card"' in product_tile
    assert "h-20 w-16" not in product_tile
