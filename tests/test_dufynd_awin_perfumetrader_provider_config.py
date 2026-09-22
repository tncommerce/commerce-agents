from __future__ import annotations

import json
from pathlib import Path

from examples.retail.api.merchant_providers import load_mapped_provider_adapter
from scripts.validate_scentai_provider_config import validate_provider_config

CONFIG_PATH = Path("examples/retail/data/dufynd_awin_perfumetrader_provider_config.json")


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def test_perfumetrader_awin_schema_template_is_structurally_ready() -> None:
    config = load_config()
    report = validate_provider_config(config)

    assert report["valid"] is True
    assert report["import_contract_ready"] is True
    assert report["promotion_asset_contract_ready"] is True
    assert report["promotion_field_gaps"] == []


def test_perfumetrader_awin_config_maps_documented_columns() -> None:
    adapter = load_mapped_provider_adapter(CONFIG_PATH)

    row = adapter.adapt_row(
        {
            "aw_product_id": "AW-123",
            "merchant_product_id": "33204791",
            "ean": "3348900425309",
            "product_GTIN": "3348900425309",
            "search_price": "89.95",
            "delivery_cost": "0.00",
            "in_stock": "1",
            "product_name": "Dior Hypnotic Poison Eau de Toilette 100 ml",
            "merchant_deep_link": "https://www.perfumetrader.de/product/33204791",
            "aw_deep_link": "https://www.awin1.com/cread.php?example=1",
            "last_updated": "2026-09-22T07:00:00",
            "merchant_image_url": "https://cdn.example.com/hypnotic-poison.jpg",
        }
    )

    assert row == {
        "offer_id": "AW-123",
        "merchant_product_id": "33204791",
        "ean": "3348900425309",
        "gtin": "3348900425309",
        "price": "89.95",
        "shipping_cost": "0.00",
        "in_stock": "1",
        "variant_label": "Dior Hypnotic Poison Eau de Toilette 100 ml",
        "product_url": "https://www.perfumetrader.de/product/33204791",
        "affiliate_url": "https://www.awin1.com/cread.php?example=1",
        "last_updated_at": "2026-09-22T07:00:00",
        "image_url": "https://cdn.example.com/hypnotic-poison.jpg",
        "merchant": "perfumetrader",
        "merchant_id": "perfumetrader",
        "merchant_name": "Perfumetrader",
        "currency": "EUR",
        "network": "Awin",
        "data_source": "approved-affiliate-feed",
    }


def test_perfumetrader_awin_config_keeps_no_feed_safeguards_enabled() -> None:
    config = load_config()

    assert config["status"] == ("awin_product_feed_unavailable_direct_merchant_data_required")
    assert config["safety"] == {
        "real_feed_preflight_required": True,
        "release_checker_required": True,
        "no_write_from_config_alone": True,
        "no_offer_activation_from_config_alone": True,
        "no_image_approval_from_config_alone": True,
        "no_awin_create_a_feed_retry_without_status_change": True,
        "direct_merchant_data_validation_required": True,
    }
    assert config["merchant_scope"]["awin_advertiser_id"] == "11672"


def test_perfumetrader_awin_feed_is_marked_unavailable() -> None:
    config = load_config()
    availability = config["source_availability"]

    assert availability["awin_product_data_available"] is False
    assert availability["create_a_feed_expected"] is False
    assert availability["next_source_paths"] == [
        "direct_perfumetrader_feed_or_api",
        "exact_product_page_evidence_plus_awin_deeplink",
    ]
