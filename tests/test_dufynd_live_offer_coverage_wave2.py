"""Guard the second DUFYND live purchase-destination coverage wave."""

from __future__ import annotations

import json
from pathlib import Path

OFFERS = Path("examples/retail/data/merchant_offers.json")

EXPECTED = {
    "SC-ARMANI-SWY-INTENSELY-100": {
        "merchant_id": "parfum-zentrum-de",
        "merchant_product_id": "18674",
        "price": 75.95,
        "shipping_cost": 4.99,
        "variant_label": "100 ml",
        "product_url": (
            "https://www.parfum-zentrum.de/giorgio-armani-emporio-armani-"
            "stronger-with-you-intensely-eau-de-parfum-100-ml-man_z750821/"
        ),
    },
    "SC-PDM-LAYTON-125": {
        "merchant_id": "parfum-zentrum-de",
        "merchant_product_id": "142576",
        "price": 220.73,
        "shipping_cost": 0,
        "variant_label": "125 ml",
        "product_url": (
            "https://www.parfum-zentrum.de/parfums-de-marly-layton-"
            "eau-de-parfum-125-ml-unisex_z889836/"
        ),
    },
    "SC-SOSPIRO-VIBRATO-100": {
        "merchant_id": "notino",
        "merchant_product_id": "SSR00580",
        "price": 224,
        "shipping_cost": 0,
        "variant_label": "100 ml",
        "product_url": "https://www.notino.de/sospiro/vibrato-eau-de-parfum-unisex/",
    },
    "SC-AL-HARAMAIN-DETOUR-NOIR-100": {
        "merchant_id": "parfum-zentrum-de",
        "merchant_product_id": "146296",
        "price": 20.43,
        "shipping_cost": 4.99,
        "variant_label": "100 ml",
        "product_url": (
            "https://www.parfum-zentrum.de/al-haramain-detour-noir-"
            "eau-de-parfum-100-ml-unisex_z907102/"
        ),
    },
    "SC-ARMAF-CDNIM-EDP-200": {
        "merchant_id": "parfum-zentrum-de",
        "merchant_product_id": "131232",
        "price": 74.97,
        "shipping_cost": 4.99,
        "variant_label": "200 ml",
        "product_url": (
            "https://www.parfum-zentrum.de/armaf-club-de-nuit-intense-man-"
            "eau-de-parfum-200-ml-man_z783835/"
        ),
    },
}


def test_second_live_offer_wave_keeps_exact_verified_variants() -> None:
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    by_product = {offer["product_id"]: offer for offer in offers if offer["product_id"] in EXPECTED}

    assert set(by_product) == set(EXPECTED)

    for product_id, expected in EXPECTED.items():
        offer = by_product[product_id]
        assert offer["merchant_id"] == expected["merchant_id"]
        assert offer["merchant_product_id"] == expected["merchant_product_id"]
        assert offer["price"] == expected["price"]
        assert offer["shipping_cost"] == expected["shipping_cost"]
        assert offer["variant_label"] == expected["variant_label"]
        assert offer["product_url"] == expected["product_url"]
        assert offer["currency"] == "EUR"
        assert offer["in_stock"] is True
        assert offer["affiliate_url"] is None
        assert offer["data_source"] == "manual_verified_web"
