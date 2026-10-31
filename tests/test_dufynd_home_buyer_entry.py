"""Regression: homepage buyer route points at first-money fragrance, never a clickout."""

from pathlib import Path


HERO = Path("examples/retail/storefront-web/components/AtelierHero.tsx")
DETAIL = Path("examples/retail/storefront-web/components/FragranceDetailPage.tsx")


def test_home_page_links_to_existing_first_money_offer_section() -> None:
    source = HERO.read_text(encoding="utf-8")
    assert 'SC-RABANNE-1-MILLION-EDT-100' in source
    assert 'href={`/duft/${buyerFragrance.slug}#angebote`}' in source
    assert "data-dufynd-home-buyer-entry" in source
    assert "homepage_buyer_entry" in source
    assert "Rabanne 1 Million EDT 100 ml · Kaufoptionen prüfen" in source
    assert 'id="angebote"' in DETAIL.read_text(encoding="utf-8")


def test_buyer_shortcut_never_claims_price_or_opens_network_clickout() -> None:
    source = HERO.read_text(encoding="utf-8")
    area = source.split("data-dufynd-home-buyer-entry", 1)[1].split(") : null}", 1)[0]
    for forbidden in ("/api/clickout/", "www.awin1.com", "jdoqocy.com", "€", "in_stock"):
        assert forbidden not in area


def test_buyer_shortcut_records_only_existing_consent_bound_product_open() -> None:
    source = HERO.read_text(encoding="utf-8")
    assert 'trackAnalyticsEvent("product_open", {' in source
    assert 'source: "homepage_buyer_entry"' in source
    assert 'import { appendAcquisitionAttribution, trackAnalyticsEvent }' in source
    assert 'AcquisitionInternalLink' in source
