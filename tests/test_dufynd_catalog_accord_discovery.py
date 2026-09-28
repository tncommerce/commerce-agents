"""Keep accord-driven DUFYND catalog discovery tied to real catalog data."""

from pathlib import Path

CATALOG_BROWSER = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")


def test_catalog_surfaces_dynamic_accord_discovery() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert "const accordDiscovery = useMemo" in source
    assert "new Set(fragrance.accords)" in source
    assert ".slice(0, 8)" in source
    assert "Beliebte Akkorde im aktuellen Katalog" in source
    assert "accordDiscovery.map" in source


def test_accord_chips_reuse_catalog_search_and_are_toggleable() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert 'setSearch(active ? "" : label)' in source
    assert "normalize(search) === normalize(label)" in source
    assert "aria-pressed={active}" in source
    assert "aria-label={`${label}: ${count} Düfte`}" in source
