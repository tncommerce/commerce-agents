from pathlib import Path

API = Path("examples/retail/storefront-web/lib/api.ts")
OFFERS = Path("examples/retail/storefront-web/components/FragranceOffers.tsx")
VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_merchant_offer_request_has_bounded_wait_and_fail_open_recovery() -> None:
    api_source = API.read_text(encoding="utf-8")
    offers_source = OFFERS.read_text(encoding="utf-8")
    qa_source = VISUAL_QA.read_text(encoding="utf-8")

    assert "const MERCHANT_OFFERS_TIMEOUT_MS = 8_000;" in api_source
    assert "new AbortController()" in api_source
    assert "controller.abort()" in api_source
    assert "signal: controller.signal" in api_source
    assert "clearTimeout(timeoutId)" in api_source

    assert "setLoadError(true)" in offers_source
    assert "Die Händlerangebote konnten gerade nicht geladen werden." in offers_source
    assert "Angebote erneut prüfen" in offers_source
    assert "setReloadToken((value) => value + 1)" in offers_source

    assert 'label: "merchant-offer-request-timeout"' in qa_source
    assert 'label: "merchant-offer-timeout-recovery"' in qa_source
    assert "setTimeout(resolve, 8_500)" in qa_source
    assert "merchantOfferRequestCount !== 2" in qa_source
    assert "QA Timeout Merchant" in qa_source
