from __future__ import annotations

from pathlib import Path

FREE_COMPARISON = Path(
    "examples/retail/storefront-web/components/FragranceComparisonPicker.tsx"
)
EXPLICIT_COMPARISON = Path(
    "examples/retail/storefront-web/app/vergleich/[pair]/page.tsx"
)
DETAIL_PAGE = Path(
    "examples/retail/storefront-web/app/duft/[slug]/page.tsx"
)
GALLERY = Path(
    "examples/retail/storefront-web/components/FragranceVisualGallery.tsx"
)
STANDARD = Path("docs/dufynd-storefront-visual-standard-20260929.md")


def test_comparison_surfaces_prefer_storefront_presentation() -> None:
    for path in (FREE_COMPARISON, EXPLICIT_COMPARISON):
        source = path.read_text(encoding="utf-8")
        assert "fragrance.presentation_visual || productTruthVisual" in source
        assert "visualWorldFor(fragrance)" in source
        assert "presentationIsProductTruth" in source
        assert "productTruthIsVerified" in source


def test_comparison_3d_fallback_keeps_product_truth_separate() -> None:
    for path in (FREE_COMPARISON, EXPLICIT_COMPARISON):
        source = path.read_text(encoding="utf-8")
        assert "productTruthVisual = fragrance.preferred_visual" in source
        assert "cutoutUrl={" in source
        assert "productTruthVisual?.url" in source


def test_detail_gallery_and_related_cards_share_fragrance_world() -> None:
    detail = DETAIL_PAGE.read_text(encoding="utf-8")
    gallery = GALLERY.read_text(encoding="utf-8")

    assert "world={visualTheme}" in detail
    assert "world={visualWorldFor(item.fragrance)}" in detail
    assert "world?: FragranceVisualWorld" in gallery
    assert "world={world}" in gallery


def test_standard_covers_comparison_and_gallery_surfaces() -> None:
    source = STANDARD.read_text(encoding="utf-8")
    assert "Free-comparison product cards" in source
    assert "Explicit-comparison product headers" in source
    assert "Product-detail visual gallery" in source
    assert "Comparison and gallery consistency" in source
