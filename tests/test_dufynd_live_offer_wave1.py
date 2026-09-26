"""Guard the first DUFYND live purchase-destination expansion wave."""

from __future__ import annotations

import json
from pathlib import Path

OFFERS = Path("examples/retail/data/merchant_offers.json")
LIVE = Path("examples/retail/data/scentai_products.json")

EXPECTED = {
    "SC-ARMANI-SWY-INTENSELY-100": {
        "offer_id": "douglas-armani-swy-intensely-100",
        "merchant": "Douglas",
        "price": 79.99,
        "variant": "100 ml · Eau de Parfum",
    },
    "SC-CHANEL-BLEU-DE-CHANEL-EDP-100": {
        "offer_id": "douglas-chanel-bleu-edp-100",
        "merchant": "Douglas",
        "price": 109.0,
        "variant": "100 ml · Eau de Parfum",
    },
    "SC-PRADA-LHOMME-100": {
        "offer_id": "notino-prada-lhomme-edt-100",
        "merchant": "Notino",
        "price": 77.5,
        "variant": "100 ml · Eau de Toilette",
    },
    "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100": {
        "offer_id": "notino-valentino-born-in-roma-intense-uomo-edp-100",
        "merchant": "Notino",
        "price": 117.0,
        "variant": "100 ml · Eau de Parfum",
    },
}


def test_live_offer_wave_uses_exact_live_variants() -> None:
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    live = json.loads(LIVE.read_text(encoding="utf-8"))["products"]
    live_by_id = {row["product_id"]: row for row in live}
    offers_by_product = {row["product_id"]: row for row in offers if row["product_id"] in EXPECTED}

    assert set(offers_by_product) == set(EXPECTED)

    for product_id, expected in EXPECTED.items():
        product = live_by_id[product_id]
        offer = offers_by_product[product_id]

        assert offer["offer_id"] == expected["offer_id"]
        assert offer["merchant_name"] == expected["merchant"]
        assert offer["price"] == expected["price"]
        assert offer["variant_label"] == expected["variant"]
        assert offer["in_stock"] is True
        assert offer["shipping_cost"] == 0
        assert offer["product_url"].startswith("https://")
        assert offer["affiliate_url"] is None
        assert offer["commission_rate"] is None
        assert offer["data_source"] == "manual_verified_web"

        expected_variant = f"{product['volume_ml']} ml · {product['concentration']}"
        assert offer["variant_label"] == expected_variant


def test_live_offer_wave_uses_regular_not_code_only_prices() -> None:
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    by_id = {row["offer_id"]: row for row in offers}

    # Douglas currently advertises lower optional code prices for SWY Intensely.
    # DUFYND stores the unconditional displayed product price instead.
    assert by_id["douglas-armani-swy-intensely-100"]["price"] == 79.99

    # Notino also shows optional code prices on some pages; these rows keep the
    # directly displayed price so users are not promised a conditional discount.
    assert by_id["notino-valentino-born-in-roma-intense-uomo-edp-100"]["price"] == 117.0


def test_live_offer_coverage_grows_without_affiliate_claims() -> None:
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    live = json.loads(LIVE.read_text(encoding="utf-8"))["products"]
    live_ids = {row["product_id"] for row in live}

    covered = {
        row["product_id"]
        for row in offers
        if row["product_id"] in live_ids and row["in_stock"] is True and row["product_url"]
    }

    assert len(covered) == 6
    assert set(EXPECTED).issubset(covered)
    assert all(row["affiliate_url"] is None for row in offers if row["product_id"] in EXPECTED)
