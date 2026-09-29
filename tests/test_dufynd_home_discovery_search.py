"""Keep the DUFYND homepage connected to catalog discovery."""

from pathlib import Path

HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")


def test_homepage_exposes_direct_catalog_search() -> None:
    source = HOME.read_text(encoding="utf-8")

    assert 'aria-labelledby="dufynd-home-search-heading"' in source
    assert 'action="/duft"' in source
    assert 'method="get"' in source
    assert 'name="q"' in source
    assert 'type="search"' in source
    assert "maxLength={80}" in source
    assert "Schon einen Duft oder eine Marke im Kopf?" in source


def test_homepage_search_preserves_existing_comparison_path() -> None:
    source = HOME.read_text(encoding="utf-8")

    assert 'href="/vergleich"' in source
    assert "Düfte vergleichen" in source
