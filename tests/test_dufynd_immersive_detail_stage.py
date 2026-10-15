"""Keep the verified 2D fallback immersive without pretending it is true 3D."""

from pathlib import Path

CSS = Path("examples/retail/storefront-web/app/globals.css")
DETAIL = Path("examples/retail/storefront-web/components/FragranceDetailPage.tsx")


def test_verified_detail_fallback_uses_immersive_hero_stage() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert '.dufynd-fragrance-hero .dufynd-product-stage[data-variant="hero"] {' in css
    assert "var(--dufynd-detail-glow-a)" in css
    assert "var(--dufynd-detail-glow-b)" in css
    assert "@keyframes dufynd-detail-stage-orbit" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_detail_page_keeps_true_model_and_verified_cutout_paths_separate() -> None:
    source = DETAIL.read_text(encoding="utf-8")

    assert "<FragranceModel3D" not in source
    assert "<FragranceVisual" in source
    assert 'mode="cutout"' in source
    assert "const productTruthVisual = originalPhotoFor(fragrance);" in source


def test_immersive_fallback_does_not_generate_or_transform_bottle_geometry() -> None:
    css = CSS.read_text(encoding="utf-8")
    source = DETAIL.read_text(encoding="utf-8")

    assert "depth staging, not simulated" in css
    assert "bottle geometry" in css
    assert "<FragranceModel3D" not in source
    assert "Originalfoto in Prüfung" in source
    assert "dufynd-product-image" in css
