from pathlib import Path

CATALOG = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")


def source() -> str:
    return CATALOG.read_text(encoding="utf-8")


def test_mobile_catalog_toolbar_keeps_filters_reachable_while_scrolling() -> None:
    text = source()

    assert "const filterSectionRef = useRef<HTMLElement>(null);" in text
    assert "const openMobileFilters = () => {" in text
    assert "filterSectionRef.current?.scrollIntoView({" in text
    assert "ref={filterSectionRef}" in text
    assert 'className="sticky bottom-3 z-20 mt-4 md:hidden"' in text
    assert 'aria-label="Katalogfilter öffnen"' in text
    assert "{filtered.length} Treffer" in text


def test_mobile_catalog_toolbar_yields_to_comparison_bar() -> None:
    text = source()

    assert "compareSelection.length === 0 ? (" in text
    assert 'aria-label="Duftvergleich vorbereiten"' in text
