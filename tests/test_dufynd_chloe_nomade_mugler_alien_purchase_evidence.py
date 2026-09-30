from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.promote_scentai_catalog import promotion_blockers

DATA = Path("examples/retail/data")
OBSERVED_AT = "2026-09-30T11:29:00Z"


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_chloe_nomade_offer_matches_exact_75_ml_edp_variant() -> None:
    offers = {row["offer_id"]: row for row in load("merchant_offers.json")["offers"]}
    offer = offers["douglas-chloe-nomade-edp-75-20260930"]

    assert offer["product_id"] == "SC-CHLOE-NOMADE-EDP-75"
    assert offer["merchant_id"] == "douglas-de"
    assert offer["merchant_product_id"] == "996998"
    assert offer["variant_label"] == "75 ml · Nomade Eau de Parfum"
    assert offer["price"] == 79.99
    assert offer["shipping_cost"] == 0
    assert offer["currency"] == "EUR"
    assert offer["in_stock"] is True
    assert offer["affiliate_url"] is None
    assert offer["last_updated_at"] == OBSERVED_AT


def test_mugler_alien_offer_matches_exact_90_ml_edp_variant() -> None:
    offers = {row["offer_id"]: row for row in load("merchant_offers.json")["offers"]}
    offer = offers["douglas-mugler-alien-edp-90-20260930"]

    assert offer["product_id"] == "SC-MUGLER-ALIEN-EDP-90"
    assert offer["merchant_id"] == "douglas-de"
    assert offer["merchant_product_id"] == "913048"
    assert offer["variant_label"] == "90 ml · Alien Refillable Eau de Parfum"
    assert offer["price"] == 99
    assert offer["shipping_cost"] == 0
    assert offer["currency"] == "EUR"
    assert offer["in_stock"] is True
    assert offer["affiliate_url"] is None
    assert offer["last_updated_at"] == OBSERVED_AT


def test_new_women_purchase_evidence_does_not_grant_image_or_affiliate_rights() -> None:
    for name in (
        "dufynd_chloe_nomade_edp_75_purchase_evidence.json",
        "dufynd_mugler_alien_edp_90_purchase_evidence.json",
    ):
        evidence = load(name)
        assert evidence["observed_at"] == OBSERVED_AT
        assert evidence["rights_or_affiliate_impact"] == {
            "image_rights_granted": False,
            "affiliate_tracking_verified": False,
            "final_image_approval_granted": False,
        }


def test_new_women_offers_clear_dynamic_purchase_gate_only() -> None:
    staging = {
        row["product_id"]: row
        for row in load("scentai_catalog_staging.json")["products"]
    }
    offers = load("merchant_offers.json")["offers"]

    for product_id in (
        "SC-CHLOE-NOMADE-EDP-75",
        "SC-MUGLER-ALIEN-EDP-90",
    ):
        product = staging[product_id]
        blockers = promotion_blockers(
            product,
            offers,
            now=datetime(2026, 9, 30, 11, 30, tzinfo=UTC),
            max_offer_age_hours=72.0,
        )

        assert "missing_current_purchase_destination" not in blockers
        assert "missing_approved_image" in blockers
        assert product["validation"]["catalog_ready"] is False
        assert "verified_purchase_destination_pending" in product["validation"]["blockers"]
        assert "approved_product_image_pending" in product["validation"]["blockers"]
