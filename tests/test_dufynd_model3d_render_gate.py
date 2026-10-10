"""Keep DUFYND fragrance detail pages from hydrating the 3D wrapper without a model."""

from pathlib import Path

DETAIL = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")
HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")


def test_detail_page_only_renders_model_viewer_for_real_model_asset() -> None:
    source = DETAIL.read_text(encoding="utf-8")

    assert "{fragrance.model_3d_url ? (" in source
    assert "{fragrance.model_3d_url || heroIsProductTruth ? (" not in source
    assert "<FragranceModel3D" in source


def test_non_3d_hero_keeps_product_truth_visual_mode() -> None:
    source = DETAIL.read_text(encoding="utf-8")

    assert "cutoutUrl={heroIsProductTruth ? heroVisual?.url : undefined}" in source
    assert 'mode={heroIsProductTruth ? "cutout" : "editorial"}' in source


def test_homepage_photo_entry_does_not_instantiate_a_bottle_model() -> None:
    home = HOME.read_text(encoding="utf-8")
    intro = Path("examples/retail/storefront-web/components/DiscoveryIntro.tsx").read_text(
        encoding="utf-8"
    )
    assert "<DiscoveryIntro />" in home
    assert "FragranceModel3D" not in home + intro
    assert "model-viewer" not in intro
    assert "isVerifiedProductTruthVisual(visual)" in intro
    assert 'mode="cutout"' in intro
