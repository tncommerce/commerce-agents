"""Keep acquisition attribution covered on merchant clickout hrefs without executing them."""

from pathlib import Path

VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")
FRAGRANCE_OFFERS = Path("examples/retail/storefront-web/components/FragranceOffers.tsx")
ANALYTICS = Path("examples/retail/storefront-web/lib/analytics.ts")


def test_merchant_clickout_attribution_is_browser_covered() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'label: "merchant-clickout-attribution-link"' in source
    assert "rabanne-1-million?src=tiktok&cmp=qa_campaign&content=qa_content" in source
    assert 'a[href*="/api/clickout/"]' in source
    assert 'clickoutUrl.searchParams.get("src") !== "tiktok"' in source
    assert 'clickoutUrl.searchParams.get("cmp") !== "qa_campaign"' in source
    assert 'clickoutUrl.searchParams.get("content") !== "qa_content"' in source
    assert 'clickout.getAttribute("target")' in source


def test_acquisition_attribution_survives_internal_navigation() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'label: "acquisition-navigation-clickout-attribution"' in source
    assert "/start?src=tiktok&cmp=qa_navigation_campaign&content=qa_navigation_content" in source
    assert 'name: "Katalog entdecken"' in source
    assert 'a[href="/duft/rabanne-1-million"]' in source
    assert 'navClickoutUrl.searchParams.get("src") !== "tiktok"' in source
    assert 'navClickoutUrl.searchParams.get("cmp") !== "qa_navigation_campaign"' in source
    assert 'navClickoutUrl.searchParams.get("content") !== "qa_navigation_content"' in source


def test_clickout_waits_for_first_party_analytics_session() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'label: "merchant-clickout-session-correlation"' in source
    assert '"**/api/session"' in source
    assert "qa-clickout-session-1234567890" in source
    assert "setTimeout(resolve, 1200)" in source
    assert 'clickoutUrl.searchParams.get("sid") !== expectedSessionId' in source
    assert "merchant clickout did not correlate acquisition and analytics session context" in source
    assert (
        "merchant clickout became actionable before analytics session correlation completed"
        in source
    )

    offers_source = FRAGRANCE_OFFERS.read_text(encoding="utf-8")
    analytics_source = ANALYTICS.read_text(encoding="utf-8")
    assert "ensureAnalyticsSession" in offers_source
    assert "data-clickout-preparing" in offers_source
    assert "clickoutSessionReady ? (" in offers_source
    assert "export async function ensureAnalyticsSession" in analytics_source


def test_merchant_discovery_waits_for_storefront_session() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    merchant_source = Path(
        "examples/retail/storefront-web/components/MerchantDiscovery.tsx"
    ).read_text(encoding="utf-8")
    home_source = Path(
        "examples/retail/storefront-web/components/views/HomeView.tsx"
    ).read_text(encoding="utf-8")
    page_source = Path(
        "examples/retail/storefront-web/app/page.tsx"
    ).read_text(encoding="utf-8")

    assert 'label: "merchant-discovery-session-correlation"' in source
    assert "qa-partner-session-1234567890" in source
    assert "setTimeout(resolve, 1200)" in source
    assert (
        "merchant discovery clickout became actionable before storefront session correlation completed"
        in source
    )
    assert 'clickoutUrl.searchParams.get("sid") !== expectedPartnerSessionId' in source
    assert "data-partner-clickout-preparing" in merchant_source
    assert "sessionReady ? (" in merchant_source
    assert "<MerchantDiscovery sessionReady={sessionReady} />" in home_source
    assert "sessionReady={Boolean(session.sessionId)}" in page_source
