from __future__ import annotations

from scripts.profile_scentai_merchant_feed_schema import (
    profile_feed_rows,
)
from scripts.validate_scentai_provider_config import (
    validate_provider_config,
)


def test_feed_schema_profile_excludes_raw_values() -> None:
    rows = [
        {
            "sku": "secret-sku-123",
            "price_col": "19.99",
            "url_col": "https://private.example/product?token=secret",
            "stock_col": "yes",
        },
        {
            "sku": "secret-sku-456",
            "price_col": "24.99",
            "url_col": "https://private.example/product/2",
            "stock_col": "no",
        },
    ]

    report = profile_feed_rows(rows)
    serialized = str(report)

    assert report["row_count"] == 2
    assert report["column_count"] == 4
    assert "secret-sku-123" not in serialized
    assert "token=secret" not in serialized
    assert "https://private.example" not in serialized

    url_profile = next(
        row
        for row in report["profiles"]
        if row["column"] == "url_col"
    )
    assert url_profile["http_url_like_count"] == 2


def valid_provider_config() -> dict:
    return {
        "provider_name": "awin-douglas",
        "field_map": {
            "offer_id": "id",
            "merchant_product_id": "sku",
            "price": "price",
            "in_stock": "stock",
            "product_url": "url",
            "affiliate_url": "tracked_url",
            "last_updated_at": "updated",
            "image_url": "image",
        },
        "constants": {
            "merchant": "douglas",
            "merchant_id": "douglas-de",
            "merchant_name": "Douglas",
            "currency": "EUR",
            "network": "Awin",
            "data_source": "awin_douglas_feed",
        },
    }


def test_provider_config_can_be_promotion_contract_ready() -> None:
    report = validate_provider_config(valid_provider_config())

    assert report["valid"] is True
    assert report["import_contract_ready"] is True
    assert report["promotion_asset_contract_ready"] is True
    assert report["promotion_field_gaps"] == []


def test_provider_config_requires_product_identifier() -> None:
    config = valid_provider_config()
    del config["field_map"]["merchant_product_id"]

    report = validate_provider_config(config)

    assert report["valid"] is False
    assert "missing_product_identifier_mapping" in report["issues"]


def test_provider_config_reports_missing_promotion_fields() -> None:
    config = valid_provider_config()
    del config["field_map"]["affiliate_url"]
    del config["field_map"]["image_url"]

    report = validate_provider_config(config)

    assert report["valid"] is True
    assert report["import_contract_ready"] is True
    assert report["promotion_asset_contract_ready"] is False
    assert report["promotion_field_gaps"] == [
        "affiliate_url",
        "image_url",
    ]
