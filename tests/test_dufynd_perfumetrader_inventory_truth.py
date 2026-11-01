"""Fresh Perfumetrader feed-list evidence must not be mistaken for product offers."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "examples/retail/data/dufynd_awin_perfumetrader_provider_config.json"


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_perfumetrader_live_feed_list_and_unverified_product_schema_are_separate() -> None:
    data = config()
    availability = data["source_availability"]
    assert data["merchant_scope"]["awin_advertiser_id"] == "11672"
    assert data["merchant_scope"]["market"] == "DE"
    assert data["status"] == "feed_list_verified_product_csv_schema_unverified_hold"
    assert availability["feed_list_verified"] is True
    assert availability["verified_product_schema"] is False
    assert availability["product_absence_proven"] is False
    assert availability["verified_product_rows"] == 0
    assert availability["awin_product_data_available"] is False
    ids = [entry["feed_id"] for entry in availability["feeds"]]
    assert ids == ["29975", "94153", "94768"]
    de = [entry for entry in availability["feeds"] if entry["use_for_DE_review"]]
    assert len(de) == 1 and de[0]["feed_id"] == "29975"
    assert all(entry["joined"] and entry["membership_status"] == "active" for entry in availability["feeds"])


def test_no_merchant_offer_or_photo_rights_activate_from_feed_inventory() -> None:
    data = config()
    assert data["source_availability"]["first_attempt_state"] == "BLOCKED_UNVERIFIED_SCHEMA"
    assert data["source_availability"]["first_attempt_run_id"] == 41189749680
    assert data["source_availability"]["corrected_reader_merged_PR"] == 868
    assert data["safety"]["no_offer_activation_from_config_alone"] is True
    assert data["safety"]["no_image_approval_from_config_alone"] is True
    assert data["safety"]["direct_merchant_data_validation_required"] is True
    assert data["source_availability"]["product_absence_proven"] is False
    assert "Angebote" in data["note"]
    assert data["field_map"]["affiliate_url"] == "aw_deep_link"
    assert not any(
        key in data["source_availability"]
        for key in ("approved_price", "approved_stock", "approved_image", "approved_affiliate_url")
    )
