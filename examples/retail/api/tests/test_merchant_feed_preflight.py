from __future__ import annotations

from retail.api.merchant_feed_preflight import (
    build_feed_preflight,
    build_mapping_coverage,
)
from retail.api.merchant_import import MerchantProductMapping
from retail.api.preflight_merchant_feed import (
    preflight_status,
)


def complete_row() -> dict:
    return {
        "offer_id": "offer-1",
        "merchant": "notino",
        "merchant_id": "notino-de",
        "merchant_name": "Notino",
        "merchant_product_id": "SKU-123",
        "price": 89.95,
        "currency": "EUR",
        "in_stock": True,
        "product_url": "https://example.com/product",
        "affiliate_url": "https://network.example/click",
        "last_updated_at": "2026-09-18T12:00:00Z",
        "data_source": "cj-feed",
        "image_url": "https://cdn.example.com/product.jpg",
    }


def test_complete_feed_is_ready() -> None:
    report = build_feed_preflight([complete_row()])

    assert report["ready_for_offer_import"] is True
    assert report["ready_for_promotion_assets"] is True
    assert report["import_ready_rows"] == 1
    assert report["promotion_ready_rows"] == 1
    assert report["issue_count"] == 0
    assert preflight_status(report) == "ready"


def test_missing_affiliate_and_image_needs_review() -> None:
    row = complete_row()
    row.pop("affiliate_url")
    row.pop("image_url")

    report = build_feed_preflight([row])

    assert report["ready_for_offer_import"] is True
    assert report["ready_for_promotion_assets"] is False
    assert report["import_ready_rows"] == 1
    assert report["promotion_ready_rows"] == 0
    assert preflight_status(report) == "review"

    issue = report["issues"][0]
    assert issue["import_failures"] == []
    assert issue["promotion_failures"] == [
        "affiliate_url",
        "image_url",
    ]


def test_invalid_price_identifier_and_timestamp_block_import() -> None:
    row = complete_row()
    row["merchant_product_id"] = ""
    row["price"] = "not-a-price"
    row["last_updated_at"] = "yesterday"

    report = build_feed_preflight([row])

    assert report["ready_for_offer_import"] is False
    assert preflight_status(report) == "blocked"

    failures = report["issues"][0]["import_failures"]
    assert "product_identifier" in failures
    assert "price" in failures
    assert "last_updated_at" in failures


def test_ean_can_satisfy_product_identifier_requirement() -> None:
    row = complete_row()
    row["merchant_product_id"] = ""
    row["ean"] = "4012345678901"

    report = build_feed_preflight([row])

    assert report["coverage"]["product_identifier"]["valid"] == 1
    assert report["ready_for_offer_import"] is True


def test_invalid_urls_are_reported_separately() -> None:
    row = complete_row()
    row["product_url"] = "not-a-url"
    row["affiliate_url"] = "javascript:alert(1)"
    row["image_url"] = "/local/image.jpg"

    report = build_feed_preflight([row])

    assert report["ready_for_offer_import"] is False
    issue = report["issues"][0]
    assert issue["import_failures"] == ["product_url"]
    assert issue["promotion_failures"] == [
        "affiliate_url",
        "image_url",
    ]



def test_mapping_coverage_is_informational_for_broad_feed() -> None:
    rows = [
        complete_row(),
        {
            **complete_row(),
            "offer_id": "offer-2",
            "merchant_product_id": "UNRELATED",
        },
    ]
    mappings = [
        MerchantProductMapping(
            product_id="SC-TEST-100",
            merchant="notino",
            merchant_product_id="SKU-123",
        )
    ]

    report = build_mapping_coverage(rows, mappings)

    assert report["row_count"] == 2
    assert report["mapped_rows"] == 1
    assert report["unmapped_rows"] == 1
    assert report["mapping_coverage_pct"] == 50.0
    assert report["mapped_product_ids"] == ["SC-TEST-100"]
    assert report["unmatched_preview"][0]["offer_id"] == "offer-2"
