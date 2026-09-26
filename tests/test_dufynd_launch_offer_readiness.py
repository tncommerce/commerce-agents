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


def test_merchant_partner_readiness_uses_public_https_and_clock_skew_tolerance() -> None:
    source = READINESS.read_text(encoding="utf-8")

    partners = source.split("const activeMerchantPartners =", 1)[1].split("add(", 1)[0]

    assert "validPublicHttpUrl(" in partners
    assert 'String(partner.affiliate_url || "")' in partners
    assert "ageHours >= -MAX_FUTURE_CLOCK_SKEW_HOURS" in partners
    assert "ageHours <= 720" in partners


def test_launch_offer_readiness_requires_eur_currency() -> None:
    source = READINESS.read_text(encoding="utf-8")

    offers = source.split("const eligibleOffers =", 1)[1].split("add(", 1)[0]

    assert 'String(offer.currency || "").trim().toUpperCase() === "EUR"' in offers
