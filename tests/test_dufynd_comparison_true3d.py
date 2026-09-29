"""Keep DUFYND comparison surfaces ready for reviewed true-3D assets."""

from pathlib import Path

DOCUMENTED = Path("examples/retail/storefront-web/app/vergleich/[pair]/page.tsx")
FREE = Path("examples/retail/storefront-web/components/FragranceComparisonPicker.tsx")


def test_documented_comparison_renders_verified_model_when_available() -> None:
    source = DOCUMENTED.read_text(encoding="utf-8")

    assert 'import FragranceModel3D from "@/components/FragranceModel3D";' in source
    assert "{fragrance.model_3d_url ? (" in source
    assert "modelUrl={fragrance.model_3d_url}" in source
    assert "<FragranceVisual" in source


def test_free_comparison_renders_verified_model_when_available() -> None:
    source = FREE.read_text(encoding="utf-8")

    assert 'import FragranceModel3D from "@/components/FragranceModel3D";' in source
    assert "{fragrance.model_3d_url ? (" in source
    assert "modelUrl={fragrance.model_3d_url}" in source
    assert "<FragranceVisual" in source


def test_comparison_fallbacks_keep_verified_backdrops_without_faking_3d() -> None:
    documented = DOCUMENTED.read_text(encoding="utf-8")
    free = FREE.read_text(encoding="utf-8")

    for source in (documented, free):
        assert "fragrance.backdrop_visual?.url" in source
        assert "presentationIsProductTruth" in source
        assert "productTruthIsVerified" in source
        assert "model_3d_url" in source
