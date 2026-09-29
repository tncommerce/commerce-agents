from pathlib import Path

FRONTEND_ANALYTICS = Path("examples/retail/storefront-web/lib/analytics.ts")
BACKEND_ANALYTICS = Path("examples/retail/api/analytics.py")
OFFER_LINK = Path("examples/retail/storefront-web/components/OfferSectionLink.tsx")
MOBILE_BAR = Path("examples/retail/storefront-web/components/MobileOfferBar.tsx")
DETAIL_PAGE = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")


def test_offer_section_event_is_supported_across_frontend_and_backend() -> None:
    assert '"offer_section_open"' in FRONTEND_ANALYTICS.read_text(encoding="utf-8")
    assert '"offer_section_open"' in BACKEND_ANALYTICS.read_text(encoding="utf-8")


def test_offer_entry_points_use_tracked_offer_section_links() -> None:
    link = OFFER_LINK.read_text(encoding="utf-8")
    mobile = MOBILE_BAR.read_text(encoding="utf-8")
    detail = DETAIL_PAGE.read_text(encoding="utf-8")

    assert 'trackAnalyticsEvent("offer_section_open"' in link
    assert 'source="mobile_offer_bar"' in mobile
    assert 'source="hero_offer_cta"' in detail
    assert 'source="detail_quick_nav"' in detail
    assert "productId={fragrance.product_id}" in detail
