from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.promote_scentai_catalog import promotion_blockers

DATA = Path("examples/retail/data")
PRODUCT_ID = "SC-YSL-BLACK-OPIUM-EDP-90"
OBSERVED_AT = "2026-09-30T11:15:00Z"


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_black_opium_offer_matches_exact_90_ml_edp_variant() -> None:
    offers = {row["offer_id"]: row for row in load("merchant_offers.json")["offers"]}
    offer = offers["douglas-ysl-black-opium-edp-90-20260930"]

    assert offer["product_id"] == PRODUCT_ID
    assert offer["merchant_id"] == "douglas-de"
    assert offer["merchant_product_id"] == "818764"
    assert offer["variant_label"] == "90 ml · Black Opium Eau de Parfum"
    assert offer["price"] == 94.99
    assert offer["shipping_cost"] == 0
    assert offer["currency"] == "EUR"
    assert offer["in_stock"] is True
    assert offer["affiliate_url"] is None
    assert offer["last_updated_at"] == OBSERVED_AT

    historical = offers["douglas-ysl-black-opium-edp-90"]
    assert historical["price"] == 115.59
    assert historical["last_updated_at"] == "2026-09-27T09:34:00Z"


def test_black_opium_evidence_does_not_grant_image_or_affiliate_rights() -> None:
    evidence = load("dufynd_ysl_black_opium_edp_90_purchase_evidence.json")

    assert evidence["observed_at"] == OBSERVED_AT
    assert evidence["product_id"] == PRODUCT_ID
    assert evidence["identity"]["volume_ml"] == 90
    assert evidence["identity"]["concentration"] == "Eau de Parfum"
    assert evidence["rights_or_affiliate_impact"] == {
        "image_rights_granted": False,
        "affiliate_tracking_verified": False,
        "final_image_approval_granted": False,
    }


def test_black_opium_current_offer_clears_purchase_gate_only() -> None:
    staging = {row["product_id"]: row for row in load("scentai_catalog_staging.json")["products"]}
    offers = load("merchant_offers.json")["offers"]
    product = staging[PRODUCT_ID]

    blockers = promotion_blockers(
        product,
        offers,
        now=datetime(2026, 9, 30, 11, 16, tzinfo=UTC),
        max_offer_age_hours=72.0,
    )

    assert "missing_current_purchase_destination" not in blockers
    assert "missing_approved_image" not in blockers
    assert product["media"]["image_status"] == "approved_feed_image"
    assert product["validation"]["catalog_ready"] is False
    assert "verified_purchase_destination_pending" in product["validation"]["blockers"]
    # Approved Awin image predates this offer audit; only the purchase gate stays.
    assert "approved_product_image_pending" not in product["validation"]["blockers"]
