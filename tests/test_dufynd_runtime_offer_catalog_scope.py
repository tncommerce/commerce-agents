"""Keep staged DUFYND offers private until their product enters the live catalog."""

from __future__ import annotations

from pathlib import Path

API_MAIN = Path("examples/retail/api/main.py")


def test_offer_listing_requires_live_dufynd_catalog_product() -> None:
    source = API_MAIN.read_text(encoding="utf-8")

    guard = 'if not _live_dufynd_offer_product(product_id):'
    lookup = "offers = offer_store.offers_for(product_id)"

    assert "def _live_dufynd_offer_product(product_id: str) -> bool:" in source
    assert 'product.product_id.startswith("SC-")' in source
    assert 'product.category == "fragrance"' in source
    assert "and product.in_stock" in source
    assert guard in source
    assert 'raise HTTPException(status_code=404, detail="Product not available")' in source
    assert source.index(guard) < source.index(lookup)


def test_offer_clickout_rechecks_live_catalog_scope() -> None:
    source = API_MAIN.read_text(encoding="utf-8")

    guard = (
        "if offer is None or not "
        "_live_dufynd_offer_product(offer.product_id):"
    )
    target = "target = offer_clickout_target(offer)"

    assert guard in source
    assert 'raise HTTPException(status_code=404, detail="Offer not available")' in source
    assert source.index(guard) < source.index(target)
