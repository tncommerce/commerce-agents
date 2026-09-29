"""Keep the DUFYND catalog comparison path fast and explicit."""

from pathlib import Path

CATALOG_BROWSER = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")


def test_catalog_supports_two_item_comparison_shortlist() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert 'const [compareSelection, setCompareSelection] = useState<string[]>([])' in source
    assert "if (current.length >= 2) return current" in source
    assert 'aria-label="Duftvergleich vorbereiten"' in source
    assert "Noch einen Duft auswählen" in source
    assert "Jetzt vergleichen →" in source
    assert "Ausgewählt ✓" in source


def test_catalog_shortlist_reuses_existing_comparison_contract() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert "/vergleich?left=" in source
    assert ")&right=" in source
    assert "selectedComparisonFragrances[0].product_id" in source
    assert "selectedComparisonFragrances[1].product_id" in source
