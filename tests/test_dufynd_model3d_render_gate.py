"""Keep DUFYND fragrance detail pages from hydrating the 3D wrapper without a model."""

from pathlib import Path

DETAIL = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")
HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")
CSS = Path("examples/retail/storefront-web/app/globals.css")


def test_detail_page_only_renders_model_viewer_for_real_model_asset() -> None:
    source = DETAIL.read_text(encoding="utf-8")

    assert "{fragrance.model_3d_url ? (" in source
    assert "{fragrance.model_3d_url || heroIsProductTruth ? (" not in source
    assert "<FragranceModel3D" in source


def test_non_3d_hero_keeps_product_truth_visual_mode() -> None:
    source = DETAIL.read_text(encoding="utf-8")

    assert "cutoutUrl={heroIsProductTruth ? heroVisual?.url : undefined}" in source
    assert 'mode={heroIsProductTruth ? "cutout" : "editorial"}' in source


def test_homepage_only_renders_model_viewer_for_real_model_asset() -> None:
    source = HOME.read_text(encoding="utf-8")

    assert "{spotlightModelUrl ? (" in source
    assert "{spotlightModelUrl || spotlightIsProductTruth ? (" not in source
    assert "spotlightIsProductTruth ? (" in source
    assert 'mode="cutout"' in source


def test_homepage_spotlight_visual_layer_is_height_independent() -> None:
    source = CSS.read_text(encoding="utf-8")

    assert ".dufynd-hero-product > :is(" in source
    assert ".dufynd-product-stage," in source
    assert ".dufynd-editorial-media," in source
    assert ".dufynd-model-stage" in source
    assert "position: absolute;" in source
    assert "inset: 0;" in source
    assert "min-height: 100%;" in source
    assert ".dufynd-hero-product .dufynd-product-object" in source
