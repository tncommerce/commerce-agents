"""Keep DUFYND best-offer badges aligned with known customer totals."""

from pathlib import Path

OFFERS = Path("examples/retail/storefront-web/components/FragranceOffers.tsx")


def test_best_offer_badge_only_claims_total_price_when_total_is_known() -> None:
    source = OFFERS.read_text(encoding="utf-8")

    assert "offer.total_price != null" in source
    assert '"Bester Gesamtpreis"' in source
    assert '"Beste verfügbare Option"' in source
