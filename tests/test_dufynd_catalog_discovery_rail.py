"""Keep the DUFYND catalog discovery rail visible, functional and tied to real profile filters."""

from pathlib import Path

CATALOG_BROWSER = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")


def test_catalog_has_immersive_profile_discovery_rail() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert 'aria-label="Duftgefühl entdecken"' in source
    assert "Nach Duftgefühl entdecken" in source
    assert 'value: "freshness"' in source
    assert 'value: "sweetness"' in source
    assert 'value: "woodiness"' in source
    assert 'value: "spiciness"' in source
    assert "profileCounts[card.value]" in source


def test_discovery_cards_toggle_the_existing_profile_filter() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert 'selectProfile(active ? "all" : card.value, !active)' in source
    assert "setProfile(nextProfile)" in source
    assert 'setSort("profile")' in source
    assert "aria-pressed={active}" in source
    assert 'className="mt-4 rounded-2xl' in source
