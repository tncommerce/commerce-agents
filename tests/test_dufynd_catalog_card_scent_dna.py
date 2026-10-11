"""Cards describe scents without unsupported numerical quality claims."""

from pathlib import Path

ROOT = Path("examples/retail/storefront-web")


def test_cards_preserve_qualitative_discovery_without_numeric_dna():
    source = (ROOT / "components/FragranceCatalogBrowser.tsx").read_text()
    assert "accordLabel(accord)" in source
    assert "Profil 0–10" not in source
    assert 'className="dufynd-catalog-card-signature"' not in source


def test_illustrations_are_explicitly_separate_from_original_photography():
    source = (ROOT / "components/ScentStudy.tsx").read_text()
    assert "Duftillustration · kein Produktfoto" in source
    assert "<img" not in source
    model = (ROOT / "lib/fragranceCatalog.ts").read_text()
    assert "a.url === v.url" in model
    assert "a.volume_ml === fragrance.volume_ml" in model
