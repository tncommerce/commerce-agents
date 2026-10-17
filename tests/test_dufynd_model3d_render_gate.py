"""Keep DUFYND fragrance detail pages from hydrating the 3D wrapper without a model."""

from pathlib import Path

DETAIL = Path("examples/retail/storefront-web/components/FragranceDetailPage.tsx")
HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")


def test_detail_page_only_renders_model_viewer_for_real_model_asset() -> None:
    source = DETAIL.read_text(encoding="utf-8")

    assert "{fragrance.model_3d_url ? (" not in source
    assert "<FragranceModel3D" not in source
    assert "originalPhotoFor(fragrance)" in source


def test_non_3d_hero_keeps_product_truth_visual_mode() -> None:
    source = DETAIL.read_text(encoding="utf-8")

    assert "cutoutUrl={heroVisual?.url}" in source
    assert 'mode="cutout"' in source
    assert "Originalfoto in Prüfung" in source


def test_homepage_photo_entry_does_not_instantiate_a_bottle_model() -> None:
    home = HOME.read_text(encoding="utf-8")
    intro = Path("examples/retail/storefront-web/components/AtelierSelection.tsx").read_text(
        encoding="utf-8"
    )
    assert "<AtelierSelection />" in home
    assert "FragranceModel3D" not in home + intro
    assert "model-viewer" not in intro
    assert 'getHomeVisual(product, { kind: "merchant_showcase"' in intro
    assert "destinationUrl: entry.merchantProductUrl" in intro
    assert 'mode="cutout"' in intro
