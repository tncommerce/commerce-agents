"""Guard DUFYND launch-readiness offer eligibility against runtime drift."""

from pathlib import Path

READINESS = Path("examples/retail/storefront-web/scripts/check-launch-readiness.mjs")


def test_launch_offer_readiness_requires_public_https_clickout() -> None:
    source = READINESS.read_text(encoding="utf-8")

    assert "const hasValidClickout =" in source
    assert 'validPublicHttpUrl(String(offer.affiliate_url || ""))' in source
    assert 'validPublicHttpUrl(String(offer.product_url || ""))' in source
    assert "hasValidClickout" in source


def test_affiliate_readiness_requires_valid_public_https_url() -> None:
    source = READINESS.read_text(encoding="utf-8")

    assert "const affiliateOffers = eligibleOffers.filter((offer) =>" in source
    assert 'validPublicHttpUrl(String(offer.affiliate_url || ""))' in source
