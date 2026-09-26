"""Guard the 2026-09-26 DUFYND live purchase-destination coverage wave."""

from __future__ import annotations

import json
from pathlib import Path

OFFERS = Path("examples/retail/data/merchant_offers.json")

EXPECTED = {
    "SC-MONTBLANC-EXPLORER-100": {
        "merchant_product_id": "058199",
        "price": 79.99,
        "product_url": "https://www.douglas.de/de/p/3001052849",
    },
    "SC-CHANEL-BLEU-DE-CHANEL-EDP-100": {
        "merchant_product_id": "819601",
        "price": 109,
        "product_url": "https://www.douglas.de/de/p/3001004983?variant=819601",
    },
    "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100": {
        "merchant_product_id": "1073334",
        "price": 119,
        "product_url": "https://www.douglas.de/de/p/5010863001?variant=1073334",
    },
    "SC-PRADA-LHOMME-100": {
        "merchant_product_id": "936318",
        "price": 109.99,
        "product_url": "https://www.douglas.de/de/p/3001030828",
    },
    "SC-DIOR-SAUVAGE-EDP-100": {
        "merchant_product_id": "995604",
        "price": 97,
        "product_url": "https://www.douglas.de/de/p/3001042193?variant=995604",
    },
}


def test_live_offer_wave_has_exact_verified_douglas_variants() -> None:
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    by_product = {offer["product_id"]: offer for offer in offers if offer["product_id"] in EXPECTED}

    assert set(by_product) == set(EXPECTED)

    for product_id, expected in EXPECTED.items():
        offer = by_product[product_id]
        assert offer["merchant_id"] == "douglas-de"
        assert offer["merchant_name"] == "Douglas"
        assert offer["merchant_product_id"] == expected["merchant_product_id"]
        assert offer["price"] == expected["price"]
        assert offer["currency"] == "EUR"
        assert offer["shipping_cost"] == 0
        assert offer["in_stock"] is True
        assert offer["variant_label"] == "100 ml"
        assert offer["product_url"] == expected["product_url"]
        assert offer["affiliate_url"] is None
        assert offer["data_source"] == "manual_verified_web"
