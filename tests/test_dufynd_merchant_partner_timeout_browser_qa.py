from pathlib import Path

API = Path("examples/retail/storefront-web/lib/api.ts")
DISCOVERY = Path("examples/retail/storefront-web/components/MerchantDiscovery.tsx")
VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_partner_timeout_preserves_session_and_mobile_retry_coverage() -> None:
    api_source = API.read_text(encoding="utf-8")
    partner_request = api_source.split("export async function fetchMerchantPartners()", 1)[1]
    partner_request = partner_request.split("export function merchantPartnerClickoutUrl", 1)[0]
    discovery_source = DISCOVERY.read_text(encoding="utf-8")
    qa_source = VISUAL_QA.read_text(encoding="utf-8")

    assert "const MERCHANT_PARTNERS_TIMEOUT_MS = 8_000;" in api_source
    assert "new AbortController()" in partner_request
    assert "controller.abort()" in partner_request
    assert "signal: controller.signal" in partner_request
    assert "headers: api.headers()" in partner_request
    assert "clearTimeout(timeoutId)" in partner_request
    assert "if (!response.ok) return null" in partner_request
    assert "setLoadError(true)" in discovery_source
    assert "Partnerhändler erneut laden" in discovery_source

    assert 'label: "merchant-partner-request-timeout"' in qa_source
    assert 'label: "merchant-partner-timeout-recovery"' in qa_source
    timeout_qa = qa_source.split("const partnerTimeoutRecoveryContext", 1)[1]
    timeout_qa = timeout_qa.split("const productDetailAttributionContext", 1)[0]
    assert "setTimeout(resolve, 8_500)" in timeout_qa
    assert "partnerTimeoutRequestCount !== 2" in timeout_qa
    assert "QA Partner Timeout Recovery" in timeout_qa
    assert 'state: "visible", timeout: 12_000' in timeout_qa


def test_partner_navigation_does_not_wait_for_advisor_session() -> None:
    """Public merchant entry needs an eligible offer, not an advisor session."""
    discovery_source = DISCOVERY.read_text(encoding="utf-8")
    home_source = Path("examples/retail/storefront-web/components/views/HomeView.tsx").read_text(
        encoding="utf-8"
    )
    page_source = Path("examples/retail/storefront-web/app/page.tsx").read_text(encoding="utf-8")
    api_source = Path("examples/retail/api/main.py").read_text(encoding="utf-8")

    assert "sessionSettled" not in discovery_source
    assert "data-partner-clickout-preparing" not in discovery_source
    assert "payload.partners.map((partner) => (" in discovery_source
    assert "merchantPartnerClickoutUrl(partner.merchant_id)" in discovery_source
    assert "appendAcquisitionAttribution(" in discovery_source
    assert 'trackAnalyticsEvent("merchant_clickout"' in discovery_source
    assert 'rel="sponsored noopener noreferrer"' in discovery_source
    assert "<MerchantDiscovery />" in home_source
    assert "sessionSettled" not in home_source
    assert "sessionSettled=" not in page_source
    assert "partner = partner_store.eligible(partner_key)" in api_source
    assert "partner is None or partner.affiliate_url is None" in api_source
    assert "Cache-Control" in api_source and "no-store" in api_source
