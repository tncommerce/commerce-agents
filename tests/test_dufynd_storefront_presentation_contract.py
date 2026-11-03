from __future__ import annotations

from pathlib import Path

ROOT = Path("examples/retail/storefront-web")


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_discovery_surfaces_use_approved_original_photos() -> None:
    catalog_lib = _read("lib/fragranceCatalog.ts")
    product_tile = _read("components/ProductTile.tsx")
    catalog_browser = _read("components/FragranceCatalogBrowser.tsx")
    discovery_page = _read("app/duft/page.tsx")
    detail_page = _read("components/FragranceDetailPage.tsx")
    acquisition = _read("components/AcquisitionLanding.tsx")
    library_hub = _read("components/FragranceLibraryHub.tsx")
    home_view = _read("components/views/HomeView.tsx")

    assert "presentation_visual: FragranceVisualAsset | null" in catalog_lib
    assert 'composition === "product_scene"' in catalog_lib
    assert "originalPhotoFor(fragrance)" in product_tile
    assert "originalPhotoFor(fragrance)" in catalog_browser
    assert "dufynd-catalog-photo-pending" in catalog_browser
    assert "<ScentArtwork" not in catalog_browser
    assert "Originalfoto in Prüfung" in catalog_browser
    assert "<DiscoveryIntro catalog />" in discovery_page
    intro = _read("components/DiscoveryIntro.tsx")
    # These entry surfaces now require an approved original. A generic
    # presentation/fidelity flag must not restore the former editorial fallback.
    for surface in (intro, acquisition):
        assert "originalPhotoFor(fragrance)" in surface
        assert "presentation_visual" not in surface
        assert "preferred_visual" not in surface
        assert "isVerifiedProductTruthVisual" not in surface
        assert "cutoutUrl={visual.url}" in surface
        assert 'mode="cutout"' in surface
        assert "fragrance.concentration" in surface
        assert "fragrance.volume_ml" in surface
    assert "originalPhotoFor(item.fragrance)" in detail_page
    assert "originalPhotoFor(fragrance)" in library_hub
    assert "fragrance.presentation_visual" not in library_hub
    assert "<AtelierSelection />" in home_view
    assert "originalPhotoFor(p)" in _read("components/AtelierSelection.tsx")


def test_detail_hero_uses_presentation_but_truth_features_stay_verified() -> None:
    detail_page = _read("components/FragranceDetailPage.tsx")

    assert "fragrance.presentation_visual || productTruthVisual" not in detail_page
    assert "const productTruthVisual = originalPhotoFor(fragrance);" in detail_page
    assert "productTruthIsVerified && productTruthVisual?.url" in detail_page
    assert "cutoutUrl={heroVisual?.url}" in detail_page
    notes = _read("components/FragranceExplodedNotes.tsx")
    assert "FragranceVisual" not in notes
    assert "data-dufynd-exploded-note" in notes
    assert "<FragranceNotesOverview notes={fragrance.notes} />" in detail_page


def test_product_tile_missing_visual_uses_neutral_fragrance_stage() -> None:
    product_tile = _read("components/ProductTile.tsx")

    assert '<FragranceVisual\n        alt={product.title}\n        variant="card"' in product_tile
    assert "h-20 w-16" not in product_tile
