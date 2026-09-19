from __future__ import annotations

from retail.api.merchant_import import MerchantProductMapping
from retail.api.scentai_release_feed_readiness import (
    build_release_feed_readiness,
)

PRODUCT_IDS = [f"SC-RELEASE-{index}" for index in range(1, 6)]


def mappings() -> list[MerchantProductMapping]:
    return [
        MerchantProductMapping(
            product_id=product_id,
            merchant="merchant-de",
            merchant_product_id=f"SKU-{index}",
        )
        for index, product_id in enumerate(PRODUCT_IDS, start=1)
    ]


def complete_rows() -> list[dict]:
    return [
        {
            "offer_id": f"offer-{index}",
            "merchant": "merchant-de",
            "merchant_id": "merchant-de",
            "merchant_name": "Merchant DE",
            "merchant_product_id": f"SKU-{index}",
            "price": 79.95 + index,
            "currency": "EUR",
            "in_stock": True,
            "product_url": (
                f"https://merchant.example/product/{index}"
            ),
            "affiliate_url": (
                f"https://network.example/click/{index}"
            ),
            "last_updated_at": "2026-09-19T08:00:00Z",
            "data_source": "approved-affiliate-feed",
            "network": "Awin",
            "image_url": (
                f"https://cdn.example.com/product-{index}.jpg"
            ),
        }
        for index in range(1, 6)
    ]


def test_complete_release_feed_is_ready_for_manual_asset_review() -> None:
    report = build_release_feed_readiness(
        PRODUCT_IDS,
        complete_rows(),
        mappings(),
    )

    assert report["status"] == "ready_for_manual_asset_review"
    assert report["feed_import_ready"] is True
    assert report["release_mapped_product_count"] == 5
    assert report["release_trackable_offer_product_count"] == 5
    assert report["release_feed_image_product_count"] == 5
    assert report["blockers"] == []


def test_incomplete_release_mapping_requires_review() -> None:
    rows = complete_rows()
    rows[-1]["merchant_product_id"] = "UNMAPPED-SKU"

    report = build_release_feed_readiness(
        PRODUCT_IDS,
        rows,
        mappings(),
    )

    assert report["status"] == "review"
    assert report["feed_import_ready"] is True
    assert report["release_mapped_product_count"] == 4
    assert report["release_trackable_offer_product_count"] == 4
    assert report["release_feed_image_product_count"] == 4
    assert "release_mapping_incomplete" in report["blockers"]
    assert (
        "release_affiliate_offer_coverage_incomplete"
        in report["blockers"]
    )
    assert (
        "release_feed_image_coverage_incomplete"
        in report["blockers"]
    )


def test_invalid_feed_blocks_release_activation() -> None:
    rows = complete_rows()
    rows[0]["price"] = "not-a-price"

    report = build_release_feed_readiness(
        PRODUCT_IDS,
        rows,
        mappings(),
    )

    assert report["status"] == "blocked"
    assert report["feed_import_ready"] is False
    assert "feed_not_import_ready" in report["blockers"]
    assert report["provider_contract_invalid_count"] == 1
