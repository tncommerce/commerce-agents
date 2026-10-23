"""Review franchise fragrance identity without weakening existing conversion gates.

This is a source contract only. Actual iPhone/tablet/desktop layout and
licensed image decode require independent browser capture and owner review.
"""

from pathlib import Path

ROOT = Path("examples/retail/storefront-web")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_homepage_has_bespoke_fragrance_arrival_and_usable_search() -> None:
    hero = read("components/AtelierHero.tsx")
    home = read("components/views/HomeView.tsx")
    css = read("app/visual-reset.css")
    assert "Nicht irgendein" in hero and "Parfum." in hero and "Deins." in hero
    assert 'role="search"' in hero
    assert 'name="q"' in hero
    assert "appendAcquisitionAttribution" in hero
    assert 'href="/duftfinder"' in hero
    assert 'href="/duft"' in hero
    assert 'href="/vergleich"' in hero
    assert 'href="#duft-atlas"' in hero
    assert 'className="wow-home wow-polish vr-home mx-auto w-full"' in home
    assert home.index("<AtelierSelection />") < home.index("<ScentAtlas />")
    assert "visual-reset.css" in read("app/layout.tsx")
    assert "@media(max-width:760px)" in css
    assert "@media(max-width:390px)" in css


def test_featured_product_uses_an_exact_rights_checked_original() -> None:
    hero = read("components/AtelierHero.tsx")
    selection = read("components/AtelierSelection.tsx")
    assert 'item.product_id === "SC-YSL-BLACK-OPIUM-EDP-90"' in hero
    assert "originalPhotoFor(featured)" in hero
    assert "featured && featuredVisual" in hero
    assert 'mode="cutout"' in hero
    assert "ImageAttribution visual={featuredVisual}" in hero
    assert "https://www.topparfuemerie.de/" not in hero
    assert "affiliate_url" not in hero.lower()
    assert "€" not in hero
    assert 'data-dufynd-original-card' in selection
    assert "originalPhotoFor(p)" in selection
    assert "<AtelierSelection />" in read("components/views/HomeView.tsx")


def test_existing_buyer_and_privacy_code_is_not_modified_by_visual_branch() -> None:
    home = read("app/page.tsx")
    assert 'trackPageView={false}' in home
    assert 'trackAnalyticsEvent("page_view", { source: "storefront" })' in home
    offers = read("components/FragranceOffers.tsx")
    assert "merchantClickoutUrl" in offers
    assert "measurementAllowed()" in offers
    assert "RETURN_RECHECK_INTERVAL_MS" in offers
    assert "data-dufynd-visual-state={imageUnavailable" in read(
        "components/FragranceVisual.tsx"
    )
