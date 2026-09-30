from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.promote_scentai_catalog import promotion_blockers

DATA = Path("examples/retail/data")
PRODUCT_ID = "SC-CALVIN-KLEIN-EUPHORIA-EDP-100"
OBSERVED_AT = "2026-09-30T10:54:00Z"


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_euphoria_offer_matches_exact_100_ml_edp_variant() -> None:
    offers = {row["offer_id"]: row for row in load("merchant_offers.json")["offers"]}
    offer = offers["notino-calvin-klein-euphoria-edp-100"]

    assert offer["product_id"] == PRODUCT_ID
    assert offer["merchant_id"] == "notino"
    assert offer["merchant_product_id"] == "CAK10204"
    assert offer["variant_label"] == "100 ml · Euphoria Eau de Parfum für Damen"
    assert offer["price"] == 46.9
    assert offer["shipping_cost"] == 3.9
    assert offer["currency"] == "EUR"
    assert offer["in_stock"] is True
    assert offer["affiliate_url"] is None
    assert offer["last_updated_at"] == OBSERVED_AT


def test_euphoria_evidence_does_not_grant_image_or_affiliate_rights() -> None:
    evidence = load("dufynd_calvin_klein_euphoria_edp_100_purchase_evidence.json")

    assert evidence["observed_at"] == OBSERVED_AT
    assert evidence["product_id"] == PRODUCT_ID
    assert evidence["identity"]["volume_ml"] == 100
    assert evidence["identity"]["concentration"] == "Eau de Parfum"
    assert evidence["rights_or_affiliate_impact"] == {
        "image_rights_granted": False,
        "affiliate_tracking_verified": False,
        "final_image_approval_granted": False,
    }


def test_euphoria_current_offer_clears_purchase_gate_only() -> None:
    staging = {row["product_id"]: row for row in load("scentai_catalog_staging.json")["products"]}
    offers = load("merchant_offers.json")["offers"]
    product = staging[PRODUCT_ID]

    blockers = promotion_blockers(
        product,
        offers,
        now=datetime(2026, 9, 30, 10, 55, tzinfo=UTC),
        max_offer_age_hours=72.0,
    )

    assert "missing_current_purchase_destination" not in blockers
    assert "missing_approved_image" in blockers
    assert product["validation"]["catalog_ready"] is False
    assert "verified_purchase_destination_pending" in product["validation"]["blockers"]
    assert "approved_product_image_pending" in product["validation"]["blockers"]
