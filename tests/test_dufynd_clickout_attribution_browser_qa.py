"""Keep acquisition attribution covered on merchant clickout hrefs without executing them."""

from pathlib import Path

VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")
FRAGRANCE_OFFERS = Path("examples/retail/storefront-web/components/FragranceOffers.tsx")
ANALYTICS = Path("examples/retail/storefront-web/lib/analytics.ts")
API_ANALYTICS = Path("examples/retail/api/analytics.py")
ANALYTICS_SQL = Path("examples/retail/data/scentai_analytics_supabase.sql")
SESSION = Path("examples/web-shared/session.ts")


def test_merchant_clickout_attribution_is_browser_covered() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'label: "merchant-clickout-attribution-link"' in source
    assert "rabanne-1-million?src=tiktok&cmp=qa_campaign&content=qa_content" in source
    assert 'a[href*="/api/clickout/"]' in source
    assert 'clickoutUrl.searchParams.get("src") !== "tiktok"' in source
    assert 'clickoutUrl.searchParams.get("cmp") !== "qa_campaign"' in source
    assert 'clickoutUrl.searchParams.get("content") !== "qa_content"' in source
    assert 'clickout.getAttribute("target")' in source
    assert 'label: "merchant-clickout-live-consent-event"' in source
    offers_source = FRAGRANCE_OFFERS.read_text(encoding="utf-8")
    merchant_source = Path(
        "examples/retail/storefront-web/components/MerchantDiscovery.tsx"
    ).read_text(encoding="utf-8")
    assert 'trackAnalyticsEvent("merchant_clickout"' in offers_source
    assert "offer_id: offer.offer_id" in offers_source
    assert 'surface: "merchant_offer"' in offers_source
    assert 'trackAnalyticsEvent("merchant_clickout"' in merchant_source
    assert 'surface: "merchant_discovery"' in merchant_source


def test_offer_section_impression_is_distinct_and_browser_covered() -> None:
    qa_source = VISUAL_QA.read_text(encoding="utf-8")
    offers_source = FRAGRANCE_OFFERS.read_text(encoding="utf-8")
    analytics_source = ANALYTICS.read_text(encoding="utf-8")
    api_source = API_ANALYTICS.read_text(encoding="utf-8")
    sql_source = ANALYTICS_SQL.read_text(encoding="utf-8")

    assert 'label: "offer-section-impression-tracking"' in qa_source
    assert 'payload?.event === "offer_section_view"' in qa_source
    assert "offer section did not emit exactly one visible impression event" in qa_source
    assert "offer-section impression was emitted more than once" in qa_source

    assert 'trackAnalyticsEvent("offer_section_view"' in offers_source
    assert 'source: "merchant_offers"' in offers_source
    assert "IntersectionObserver" in offers_source
    assert "entry.intersectionRatio < 0.35" in offers_source
    assert "trackedOfferViewRef.current === impressionKey" in offers_source

    assert '| "offer_section_open"' in analytics_source
    assert '| "offer_section_view"' in analytics_source
    assert '"offer_section_open",' in api_source
    assert '"offer_section_view",' in api_source
    assert "'offer_section_open'," in sql_source
    assert "'offer_section_view'," in sql_source


def test_acquisition_attribution_survives_internal_navigation() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'label: "acquisition-navigation-clickout-attribution"' in source
    assert "/start?src=tiktok&cmp=qa_navigation_campaign&content=qa_navigation_content" in source
    assert 'name: "Katalog entdecken"' in source
    assert 'a[href*="/duft/rabanne-1-million"]' in source
    assert 'navClickoutUrl.searchParams.get("src") !== "tiktok"' in source
    assert 'navClickoutUrl.searchParams.get("cmp") !== "qa_navigation_campaign"' in source
    assert 'navClickoutUrl.searchParams.get("content") !== "qa_navigation_content"' in source


def test_verified_clickout_is_not_blocked_by_optional_analytics_session() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'label: "merchant-clickout-session-correlation"' in source
    assert '"**/api/session"' in source
    assert "qa-clickout_session-1234567890" in source
    assert "await sessionGate;" in source
    assert 'clickoutUrl.searchParams.get("sid") === expectedSessionId' in source
    assert 'clickoutUrl.searchParams.get("measurement") !== "granted-v1"' in source
    assert '!/^[0-9a-f-]{36}$/i.test(clickoutUrl.searchParams.get("sid") || "")' in source
    assert "merchant clickout did not correlate acquisition and analytics session context" in source
    assert (
        "verified merchant clickout unavailable while optional analytics session pending" in source
    )
    assert "merchant clickout blocked on optional analytics session" in source

    offers_source = FRAGRANCE_OFFERS.read_text(encoding="utf-8")
    analytics_source = ANALYTICS.read_text(encoding="utf-8")
    assert "ensureAnalyticsSession" not in offers_source
    assert "data-clickout-preparing" not in offers_source
    assert "clickoutSessionReady" not in offers_source
    assert (
        "href={appendAcquisitionAttribution(merchantClickoutUrl(offer.clickout_path))}"
        in offers_source
    )
    assert 'trackAnalyticsEvent("merchant_clickout"' in offers_source
    assert "export async function ensureAnalyticsSession" in analytics_source


def test_merchant_discovery_does_not_wait_for_storefront_session() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    merchant_source = Path(
        "examples/retail/storefront-web/components/MerchantDiscovery.tsx"
    ).read_text(encoding="utf-8")
    home_source = Path("examples/retail/storefront-web/components/views/HomeView.tsx").read_text(
        encoding="utf-8"
    )
    page_source = Path("examples/retail/storefront-web/app/page.tsx").read_text(encoding="utf-8")

    assert 'label: "merchant-discovery-session-correlation"' in source
    assert "qa-partner-session-1234567890" in source
    assert "await partnerSessionRequested;" in source
    assert "await partnerSessionGate;" in source
    assert "merchant CTA still waits for unrelated advisor session" in source
    assert 'clickoutUrl.searchParams.get("sid") === expectedPartnerSessionId' in source
    assert 'clickoutUrl.searchParams.get("measurement") !== "granted-v1"' in source
    assert "data-partner-clickout-preparing" not in merchant_source
    assert "sessionSettled" not in merchant_source
    assert "<MerchantDiscovery />" in home_source
    assert "sessionSettled=" not in page_source


def test_merchant_discovery_remains_actionable_after_session_failure() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    session_source = SESSION.read_text(encoding="utf-8")

    assert 'label: "merchant-discovery-session-failure-fallback"' in source
    assert '"QA session unavailable"' in source
    assert "merchant CTA blocked despite valid partner payload during advisor error" in source
    assert '!/^[0-9a-f-]{36}$/i.test(clickoutUrl.searchParams.get("sid") || "")' in source
    assert 'clickoutUrl.searchParams.get("measurement") !== "granted-v1"' in source
    assert "settled?: boolean" in session_source
    assert "settled: false" in session_source
    assert "settled: true" in session_source


def test_merchant_discovery_recovers_after_partner_api_failure() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    merchant_source = Path(
        "examples/retail/storefront-web/components/MerchantDiscovery.tsx"
    ).read_text(encoding="utf-8")

    assert 'label: "merchant-discovery-load-recovery"' in source
    assert '"QA partner discovery unavailable"' in source
    assert '"Partnerhändler erneut laden"' in source
    assert "partnerRequestCount !== 2" in source
    assert "data-merchant-discovery-error" in merchant_source
    assert "setReloadToken((value) => value + 1)" in merchant_source
    assert "Partnerhändler gerade nicht verfügbar" in merchant_source


def test_merchant_discovery_reserves_loading_state_before_partner_data() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    merchant_source = Path(
        "examples/retail/storefront-web/components/MerchantDiscovery.tsx"
    ).read_text(encoding="utf-8")

    assert 'label: "merchant-discovery-loading-stability"' in source
    assert "merchant discovery loading state exposed an actionable partner link" in source
    assert "merchant discovery loading placeholder did not clear after load failure" in source
    assert "data-merchant-discovery-loading" in merchant_source
    assert 'aria-busy="true"' in merchant_source
    assert "min-h-[132px]" in merchant_source
    assert "Partnerhändler werden geladen" in merchant_source


def test_comparison_product_links_preserve_acquisition_attribution() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    picker_source = Path(
        "examples/retail/storefront-web/components/FragranceComparisonPicker.tsx"
    ).read_text(encoding="utf-8")
    comparison_page_source = Path(
        "examples/retail/storefront-web/app/vergleich/page.tsx"
    ).read_text(encoding="utf-8")

    assert 'label: "comparison-product-navigation-attribution"' in source
    assert "qa_comparison_campaign" in source
    assert "qa_comparison_content" in source
    assert "free comparison product navigation lost acquisition attribution" in source
    assert (
        "appendAcquisitionAttribution(withCatalogContext(`/duft/${fragrance.slug}`, context))"
        in picker_source
    )
    assert 'source="comparison" trackPageView={false}' in comparison_page_source


def test_comparison_internal_links_preserve_acquisition_attribution() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    link_source = Path(
        "examples/retail/storefront-web/components/AcquisitionInternalLink.tsx"
    ).read_text(encoding="utf-8")
    comparison_page_source = Path(
        "examples/retail/storefront-web/app/vergleich/page.tsx"
    ).read_text(encoding="utf-8")

    assert 'label: "comparison-internal-navigation-attribution"' in source
    assert '["comparison catalog", comparisonCatalogHref]' in source
    assert '["documented comparison pair", comparisonPairHref]' in source
    assert "navigation lost acquisition attribution" in source
    assert "appendAcquisitionAttribution(href)" in link_source
    analytics_source = Path("examples/retail/storefront-web/lib/analytics.ts").read_text(
        encoding="utf-8"
    )
    assert "const attribution = captureAcquisitionEntry();" in analytics_source
    assert "rememberAcquisitionAttribution({" in analytics_source
    assert "AcquisitionInternalLink" in comparison_page_source


def test_comparison_footer_links_preserve_acquisition_attribution() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    comparison_page_source = Path(
        "examples/retail/storefront-web/app/vergleich/page.tsx"
    ).read_text(encoding="utf-8")

    assert 'label: "comparison-footer-navigation-attribution"' in source
    assert "comparison footer ${name} navigation lost acquisition attribution" in source
    assert (
        '<AcquisitionInternalLink href="/duft" className="hover:underline">'
        in comparison_page_source
    )
    assert (
        '<AcquisitionInternalLink href="/transparenz" className="hover:underline">'
        in comparison_page_source
    )
    assert (
        '<AcquisitionInternalLink href="/impressum" className="hover:underline">'
        in comparison_page_source
    )
    assert (
        '<AcquisitionInternalLink href="/datenschutz" className="hover:underline">'
        in comparison_page_source
    )


def test_documented_comparison_links_preserve_acquisition_attribution() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    detail_source = Path("examples/retail/storefront-web/app/vergleich/[pair]/page.tsx").read_text(
        encoding="utf-8"
    )

    assert 'label: "comparison-detail-navigation-attribution"' in source
    assert "documented comparison product" in source
    assert "documented comparison header" in source
    assert "documented comparison breadcrumb" in source
    assert "documented comparison footer" in source
    assert "navigation lost acquisition attribution" in source
    assert "AcquisitionInternalLink" in detail_source
    assert '<AcquisitionInternalLink href="/vergleich"' in detail_source
    assert '<AcquisitionInternalLink href="/duft"' in detail_source
    assert '<AcquisitionInternalLink href="/transparenz"' in detail_source


def test_product_detail_internal_links_preserve_acquisition_attribution() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    detail_source = Path(
        "examples/retail/storefront-web/components/FragranceDetailPage.tsx"
    ).read_text(encoding="utf-8")

    assert 'label: "product-detail-navigation-attribution"' in source
    assert "qa_product_detail_content" in source
    assert "product detail navigation lost acquisition attribution" in source
    assert "AcquisitionInternalLink" in detail_source
    assert '<CatalogReturnLink href="/duft"' in detail_source
    return_link = Path("examples/retail/storefront-web/components/CatalogReturnLink.tsx").read_text(
        encoding="utf-8"
    )
    # Functional return state still delegates every click/consent change to the
    # same acquisition-aware link, including its ordinary no-context fallback.
    assert 'import AcquisitionInternalLink from "./AcquisitionInternalLink"' in return_link
    assert (
        "<AcquisitionInternalLink {...props} href={context ? catalogReturnHref(context) : props.href}>"
        in return_link
    )
    assert (
        '<AcquisitionInternalLink href="/transparenz" className="hover:underline">' in detail_source
    )
