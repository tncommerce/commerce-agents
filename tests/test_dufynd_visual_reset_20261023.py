"""Guard visual redesign against fabricated assets and lost purchase pathways."""

from pathlib import Path

ROOT = Path("examples/retail/storefront-web")


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_editorial_home_still_has_search_and_advisor() -> None:
    hero = read("components/AtelierHero.tsx")
    home = read("components/views/HomeView.tsx")
    assert "Nicht irgendein" in hero
    assert "Parfum." in hero
    assert "Deins." in hero
    assert 'role="search"' in hero
    assert 'name="q"' in hero
    assert "appendAcquisitionAttribution" in hero
    assert 'href="/duftfinder"' in hero
    assert 'href="/vergleich"' in hero
    assert 'href="#duft-atlas"' in hero
    assert "vr-home" in home
    assert home.index("<AtelierSelection />") < home.index("<ScentAtlas />")
    assert "visual-reset.css" in read("app/layout.tsx")


def test_feature_requires_exact_original_and_credit() -> None:
    hero = read("components/AtelierHero.tsx")
    assert "SC-YSL-BLACK-OPIUM-EDP-90" in hero
    assert "originalPhotoFor(featured)" in hero
    assert "featured && featuredVisual" in hero
    assert "ImageAttribution visual={featuredVisual}" in hero
    assert "affiliate_url" not in hero.lower()
    assert "€" not in hero
    selection = read("components/AtelierSelection.tsx")
    assert "originalPhotoFor(p)" in selection


def test_existing_consented_buyer_path_is_untouched() -> None:
    home = read("app/page.tsx")
    offers = read("components/FragranceOffers.tsx")
    assert "trackPageView={false}" in home
    assert "trackAnalyticsEvent" in home
    assert "merchantClickoutUrl" in offers
    assert "measurementAllowed()" in offers
    assert "RETURN_RECHECK_INTERVAL_MS" in offers
    visual = read("components/FragranceVisual.tsx")
    assert "data-dufynd-visual-state" in visual
