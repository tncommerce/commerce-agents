"""Keep shopper-facing affiliate disclosure aligned with DUFYND ordering policy."""

from pathlib import Path

OFFERS = Path("examples/retail/storefront-web/components/FragranceOffers.tsx")
TRANSPARENCY = Path("examples/retail/storefront-web/app/transparenz/page.tsx")


def test_offer_disclosure_explains_equal_price_tie_break() -> None:
    offers = OFFERS.read_text(encoding="utf-8")

    assert "Bei gleichem Gesamtpreis und vergleichbarer Aktualität" in offers
    assert "die Provision als Tie-Breaker dienen" in offers
    assert "Reihenfolge der Angebote." not in offers


def test_offer_disclosure_matches_transparency_policy() -> None:
    transparency = TRANSPARENCY.read_text(encoding="utf-8")

    assert "Bei gleichem Gesamtpreis und vergleichbarer Aktualität" in transparency
    assert "höhere Provision die Reihenfolge entscheiden" in transparency
