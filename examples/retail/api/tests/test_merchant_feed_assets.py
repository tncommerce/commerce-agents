from __future__ import annotations

from retail.api.merchant_feed_assets import (
    extract_feed_image_candidates,
)
from retail.api.merchant_import import (
    MerchantProductMapping,
)


def mappings() -> list[MerchantProductMapping]:
    return [
        MerchantProductMapping(
            product_id="SC-TEST-100",
            merchant="notino",
            merchant_product_id="SKU-123",
        )
    ]


def test_extracts_mapped_feed_image_candidate() -> None:
    result = extract_feed_image_candidates(
        [
            {
                "offer_id": "offer-1",
                "merchant": "notino",
                "merchant_id": "notino-de",
                "merchant_name": "Notino",
                "merchant_product_id": "SKU-123",
                "image_url": "https://cdn.example.com/product.jpg",
                "network": "CJ",
                "data_source": "cj-feed",
                "last_updated_at": "2026-09-18T12:00:00Z",
            }
        ],
        mappings(),
    )

    assert result["candidate_count"] == 1
    assert result["unmatched_count"] == 0
    assert result["invalid_count"] == 0

    candidate = result["candidates"][0]
    assert candidate["product_id"] == "SC-TEST-100"
    assert candidate["review_status"] == "pending_review"
    assert candidate["proposed_image_status"] == "approved_feed_image"


def test_unmatched_feed_image_is_kept_for_mapping_review() -> None:
    result = extract_feed_image_candidates(
        [
            {
                "offer_id": "offer-2",
                "merchant": "notino",
                "merchant_product_id": "UNKNOWN",
                "image_url": "https://cdn.example.com/unknown.jpg",
            }
        ],
        mappings(),
    )

    assert result["candidate_count"] == 0
    assert result["unmatched_count"] == 1
    assert result["unmatched"][0]["reason"] == "product_mapping_not_found"


def test_invalid_image_url_is_rejected_and_redacted() -> None:
    result = extract_feed_image_candidates(
        [
            {
                "offer_id": "offer-3",
                "merchant": "notino",
                "merchant_product_id": "SKU-123",
                "image_url": "javascript:alert(1)",
            }
        ],
        mappings(),
    )

    assert result["candidate_count"] == 0
    assert result["invalid_count"] == 1
    assert result["invalid"][0]["reason"] == "invalid_image_url"
    assert result["invalid"][0]["image_url"] is None
    assert result["invalid"][0]["image_url_redacted"] is True


def test_secret_bearing_or_non_public_image_urls_are_rejected_without_leaking_value() -> None:
    bad_urls = [
        "http://cdn.example.com/product.jpg",
        "https://user:SECRET@cdn.example.com/product.jpg",
        "https://cdn.example.com/product.jpg?api_key=SECRET",
        "https://cdn.example.com/apikey/SECRET/product.jpg",
        "https://cdn.example.com/product.jpg#token=SECRET",
        "https://127.0.0.1/product.jpg",
        "https://localhost/product.jpg",
    ]

    rows = [
        {
            "offer_id": f"offer-{index}",
            "merchant": "notino",
            "merchant_product_id": "SKU-123",
            "image_url": url,
        }
        for index, url in enumerate(bad_urls, start=10)
    ]

    result = extract_feed_image_candidates(rows, mappings())

    assert result["candidate_count"] == 0
    assert result["invalid_count"] == len(bad_urls)
    assert all(row["image_url"] is None for row in result["invalid"])
    assert all(row["image_url_redacted"] is True for row in result["invalid"])
    assert "SECRET" not in str(result)


def test_duplicate_product_image_is_deduplicated() -> None:
    row = {
        "merchant": "notino",
        "merchant_product_id": "SKU-123",
        "image_url": "https://cdn.example.com/product.jpg",
    }

    result = extract_feed_image_candidates(
        [
            {"offer_id": "offer-1", **row},
            {"offer_id": "offer-2", **row},
        ],
        mappings(),
    )

    assert result["candidate_count"] == 1
