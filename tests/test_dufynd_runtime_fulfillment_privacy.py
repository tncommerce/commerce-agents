"""Keep internal demo fulfillment fields out of DUFYND fragrance payloads."""

from pathlib import Path

MOCK_RETAIL = Path("examples/retail/api/mock_retail.py")


def test_customer_facing_fragrance_payload_hides_demo_fulfillment_attributes() -> None:
    source = MOCK_RETAIL.read_text(encoding="utf-8")
    block = source.split("internal_attributes = {", 1)[1].split("        }", 1)[0]

    assert "DELIVERY_ATTRIBUTE" in block
    assert "LOW_STOCK_ATTRIBUTE" in block


def test_fragrance_cards_keep_delivery_promises_hidden() -> None:
    tile = Path("examples/retail/storefront-web/components/ProductTile.tsx").read_text(
        encoding="utf-8"
    )

    assert 'if (product.category === "fragrance" || !promise || product.in_stock === false)' in tile
