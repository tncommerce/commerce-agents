"""Guard canonical DUFYND live offer coverage consolidated on 2026-09-27."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

OFFERS = Path("examples/retail/data/merchant_offers.json")
LIVE = Path("examples/retail/data/scentai_products.json")

EXPECTED = {
    "douglas-bois-imperial-100": {
        "product_id": "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
        "merchant_id": "douglas-de",
        "merchant_product_id": "1068008",
        "price": 94,
        "product_url": "https://www.douglas.de/de/p/5011160013",
        "last_updated_at": "2026-09-26T16:03:00Z",
    },
    "parfum-zentrum-naxos-100": {
        "product_id": "SC-XERJOFF-NAXOS-100",
        "merchant_id": "parfum-zentrum-de",
        "merchant_product_id": "136149",
        "price": 170.71,
        "product_url": "https://www.parfum-zentrum.de/xerjoff-xj-1861-naxos-eau-de-parfum-100-ml-unisex_z775656/",
        "last_updated_at": "2026-09-26T16:03:00Z",
    },
    "notino-naxos-100": {
        "product_id": "SC-XERJOFF-NAXOS-100",
        "merchant_id": "notino",
        "merchant_product_id": "XEF3191",
        "price": 192,
        "product_url": "https://www.notino.de/xerjoff/xj-1861-naxos-eau-de-parfum-unisex/",
        "last_updated_at": "2026-09-26T16:03:00Z",
    },
    "douglas-montblanc-explorer-100": {
        "product_id": "SC-MONTBLANC-EXPLORER-100",
        "merchant_id": "douglas-de",
        "merchant_product_id": "058199",
        "price": 79.99,
        "product_url": "https://www.douglas.de/de/p/3001052849",
        "last_updated_at": "2026-09-26T16:03:00Z",
    },
    "douglas-bleu-de-chanel-edp-100": {
        "product_id": "SC-CHANEL-BLEU-DE-CHANEL-EDP-100",
        "merchant_id": "douglas-de",
        "merchant_product_id": "819601",
        "price": 109,
        "product_url": "https://www.douglas.de/de/p/3001004983?variant=819601",
        "last_updated_at": "2026-09-26T16:03:00Z",
    },
    "douglas-valentino-uomo-born-in-roma-intense-100": {
        "product_id": "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100",
        "merchant_id": "douglas-de",
        "merchant_product_id": "1073334",
        "price": 119,
        "product_url": "https://www.douglas.de/de/p/5010863001?variant=1073334",
        "last_updated_at": "2026-09-26T16:03:00Z",
    },
    "douglas-prada-lhomme-100": {
        "product_id": "SC-PRADA-LHOMME-100",
        "merchant_id": "douglas-de",
        "merchant_product_id": "936318",
        "price": 109.99,
        "product_url": "https://www.douglas.de/de/p/3001030828",
        "last_updated_at": "2026-09-26T16:03:00Z",
    },
    "douglas-dior-sauvage-edp-100": {
        "product_id": "SC-DIOR-SAUVAGE-EDP-100",
        "merchant_id": "douglas-de",
        "merchant_product_id": "995604",
        "price": 97,
        "product_url": "https://www.douglas.de/de/p/3001042193?variant=995604",
        "last_updated_at": "2026-09-26T16:03:00Z",
    },
    "douglas-armani-swy-intensely-100": {
        "product_id": "SC-ARMANI-SWY-INTENSELY-100",
        "merchant_id": "douglas-de",
        "merchant_product_id": "063552",
        "price": 79.99,
        "product_url": "https://www.douglas.de/de/p/3001052351?variant=063552",
        "last_updated_at": "2026-09-26T14:33:00Z",
    },
}


def test_canonical_offer_wave_matches_verified_sources() -> None:
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    live = json.loads(LIVE.read_text(encoding="utf-8"))["products"]
    live_ids = {row["product_id"] for row in live}
    by_id = {row["offer_id"]: row for row in offers}

    assert len(offers) == 15
    assert set(EXPECTED).issubset(by_id)

    for offer_id, expected in EXPECTED.items():
        offer = by_id[offer_id]
        assert offer["product_id"] == expected["product_id"]
        assert offer["product_id"] in live_ids
        assert offer["merchant_id"] == expected["merchant_id"]
        assert offer["merchant_product_id"] == expected["merchant_product_id"]
        assert offer["price"] == expected["price"]
        assert offer["currency"] == "EUR"
        assert offer["shipping_cost"] == 0
        assert offer["in_stock"] is True
        assert offer["product_url"] == expected["product_url"]
        assert urlparse(offer["product_url"]).scheme == "https"
        assert offer["affiliate_url"] is None
        assert offer["commission_rate"] is None
        assert offer["data_source"] == "manual_verified_web"
        assert offer["last_updated_at"] == expected["last_updated_at"]


def test_canonical_offer_ids_are_unique() -> None:
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    offer_ids = [row["offer_id"] for row in offers]
    assert len(offer_ids) == len(set(offer_ids))
