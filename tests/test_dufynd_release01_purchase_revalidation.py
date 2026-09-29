from __future__ import annotations

import json
from pathlib import Path

DATA = Path("examples/retail/data")
REVALIDATION = DATA / "dufynd_release01_purchase_revalidation_20260929.json"
OFFERS = DATA / "merchant_offers.json"

EXPECTED = {
    "SC-PDM-DELINA-EDP-75": {
        "offer_id": "douglas-pdm-delina-edp-75",
        "volume_ml": 75,
        "merchant_product_id": "968233",
        "price": 285,
    },
    "SC-YSL-LIBRE-EDP-90": {
        "offer_id": "douglas-ysl-libre-edp-90",
        "volume_ml": 90,
        "merchant_product_id": "289703",
        "price": 119,
    },
}


def test_release01_purchase_revalidation_is_exact_and_read_only() -> None:
    payload = json.loads(REVALIDATION.read_text(encoding="utf-8"))
    rows = {row["product_id"]: row for row in payload["products"]}

    assert payload["status"] == "applied_to_existing_non_affiliate_purchase_destinations"
    assert set(rows) == set(EXPECTED)
    assert payload["policy"]["affiliate_tracking_added"] is False
    assert payload["policy"]["recommendation_priority_changed"] is False
    assert payload["policy"]["image_reuse_rights_inferred"] is False

    for product_id, expected in EXPECTED.items():
        row = rows[product_id]
        assert row["volume_ml"] == expected["volume_ml"]
        assert row["merchant_product_id"] == expected["merchant_product_id"]
        assert row["observed_price_eur"] == expected["price"]
        assert row["shipping_cost_eur"] == 0
        assert row["in_stock"] is True
        assert row["product_url"].startswith("https://www.douglas.de/")
        assert row["intended_offer_id"] == expected["offer_id"]


def test_revalidation_matches_existing_live_offer_identity_without_mutating_it() -> None:
    payload = json.loads(REVALIDATION.read_text(encoding="utf-8"))
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    offers_by_id = {row["offer_id"]: row for row in offers}

    for row in payload["products"]:
        offer = offers_by_id[row["intended_offer_id"]]
        assert offer["product_id"] == row["product_id"]
        assert offer["merchant_id"] == row["merchant_id"]
        assert offer["merchant_product_id"] == row["merchant_product_id"]
        assert offer["product_url"] == row["product_url"]
        assert offer["last_updated_at"] == row["live_offer_refreshed_at"]
        assert row["current_live_offer_action"] == "refreshed_after_exact_variant_revalidation"
        assert offer["affiliate_url"] is None
