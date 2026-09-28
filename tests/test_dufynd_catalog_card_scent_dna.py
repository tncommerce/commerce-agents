"""Keep DUFYND catalog cards visually scannable with real scent-profile data."""

from pathlib import Path

CATALOG_BROWSER = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")


def test_catalog_cards_surface_four_axis_scent_dna() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert "const SCENT_DNA_PROFILES" in source
    assert '{ key: "freshness", label: "Frisch" }' in source
    assert '{ key: "sweetness", label: "Süß" }' in source
    assert '{ key: "woodiness", label: "Holzig" }' in source
    assert '{ key: "spiciness", label: "Würzig" }' in source
    assert 'aria-label="Duft-DNA"' in source
    assert "SCENT_DNA_PROFILES.map" in source


def test_catalog_card_scent_dna_is_clamped_to_visual_scale() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert "Math.min(10, fragrance.scores[profile] ?? 0)" in source
    assert "width: `${value * 10}%`" in source
    assert "Profil 0–10" in source
