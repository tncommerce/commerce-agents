ture__ import annotations

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

    url_profile = next(row for row in report["profiles"] if row["column"] == "url_col")
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
            "image
…[4663 chars truncated — re-run with head/grep/tail for full output]…
   releases,
        generated_at="2026-09-19T10:00:00+00:00",
        asset_candidates=candidates,
    )

    row = queue["items"][0]

    assert row["image_state"] == "rights_or_source_check_pending"
    assert row["candidate_source"]["exact_variant_verified"] is True
    assert "asset_usage_or_feed_rights_not_verified" in row["blockers"]
    assert queue["summary"]["rights_or_source_check_pending"] == 1
    assert queue["summary"]["approved_images"] == 0


def test_approved_image_overrides_candidate_pending_state() -> None:
    staging = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "candidate_id": "TEST",
                "brand": "Brand",
                "name": "Test",
                "batch": 1,
                "media": {
                    "image_url": "/products/test.png",
                    "image_status": "approved_feed_image",
                },
            }
        ]
    }
    releases = []
    candidates = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "image_state": "rights_or_source_check_pending",
            }
        ]
    }

    queue = build_queue(
        staging,
        releases,
        generated_at="2026-09-19T10:00:00+00:00",
        asset_candidates=candidates,
    )

    row = queue["items"][0]

    assert row["image_state"] == "approved_feed_image"
    assert row["blockers"] == []
    assert row["next_action"] == "none"
    assert queue["summary"]["approved_images"] == 1
