from __future__ import annotations

from datetime import UTC, datetime

import pytest

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
            "product_url": (f"https://merchant.example/product/{index}"),
            "affiliate_url": (f"https://network.example/click/{index}"),
            "last_updated_at": datetime.now(UTC).isoformat(),
            "data_source": "approved-affiliate-feed",
            "network": "Awin",
            "image_url": (f"https://cdn.example.com/product-{index}.jpg"),
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
    assert "release_affiliate_offer_coverage_incomplete" in report["blockers"]
    assert "release_feed_image_coverage_incomplete" in report["blockers"]


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
    assert report["release_feed_rows_import_ready"] is False
    assert report["release_relevant_import_issue_count"] == 1
    assert "feed_not_import_ready" in report["blockers"]
    assert report["provider_contract_invalid_count"] == 1


def test_unrelated_bad_rows_do_not_block_release_scoped_review() -> None:
    rows = complete_rows()
    rows.extend(
        [
            {
                "offer_id": "unrelated-invalid-timestamp",
                "merchant": "merchant-de",
                "merchant_id": "merchant-de",
                "merchant_name": "Merchant DE",
                "merchant_product_id": "UNRELATED-1",
                "price": 40.0,
                "currency": "EUR",
                "in_stock": False,
                "product_url": "https://merchant.example/unrelated/1",
                "affiliate_url": "https://network.example/unrelated/1",
                "last_updated_at": "not-a-timestamp",
                "data_source": "approved-affiliate-feed",
                "network": "Awin",
                "image_url": "https://cdn.example.com/unrelated-1.jpg",
            },
            {
                "offer_id": "unrelated-zero-price",
                "merchant": "merchant-de",
                "merchant_id": "merchant-de",
                "merchant_name": "Merchant DE",
                "merchant_product_id": "UNRELATED-2",
                "price": 0,
                "currency": "EUR",
                "in_stock": False,
                "product_url": "https://merchant.example/unrelated/2",
                "affiliate_url": "https://network.example/unrelated/2",
                "last_updated_at": "2026-09-30T08:00:00Z",
                "data_source": "approved-affiliate-feed",
                "network": "Awin",
                "image_url": "https://cdn.example.com/unrelated-2.jpg",
            },
        ]
    )

    report = build_release_feed_readiness(
        PRODUCT_IDS,
        rows,
        mappings(),
    )

    assert report["status"] == "ready_for_manual_asset_review"
    assert report["feed_import_ready"] is False
    assert report["release_feed_rows_import_ready"] is True
    assert report["release_relevant_import_issue_count"] == 0
    assert report["non_release_import_issue_count"] == 2
    assert report["provider_contract_invalid_count"] == 1
    assert report["release_mapped_product_count"] == 5
    assert report["release_trackable_offer_product_count"] == 5
    assert report["release_feed_image_product_count"] == 5
    assert report["blockers"] == []


@pytest.mark.parametrize(
    "change",
    [
        {"last_updated_at": "2026-09-22T08:00:00Z"},
        {"last_updated_at": "2026-10-09T08:00:00Z"},
        {"in_stock": False},
        {"currency": "USD"},
        {"affiliate_url": "http://network.example/click/1"},
        {"affiliate_url": "https://user:password@network.example/click/1"},
        {"affiliate_url": "https://network.example/click?api_key=secret"},
        {"affiliate_url": "https://127.0.0.1/click/1"},
    ],
)
def test_ineligible_offer_cannot_count_as_release_ready(change) -> None:
    now = datetime(2026, 10, 8, 12, tzinfo=UTC)
    rows = complete_rows()
    for row in rows:
        row["last_updated_at"] = now.isoformat()
    rows[0].update(change)
    report = build_release_feed_readiness(PRODUCT_IDS, rows, mappings(), now=now)
    assert report["status"] == "review"
    assert report["release_mapped_product_count"] == 5
    assert report["release_trackable_offer_product_count"] == 4
    assert report["products"][0]["ineligible_offer_count"] == 1
    assert report["tracking_verified"] is False
    assert report["activation_allowed"] is False


def test_conflicting_gtin_is_not_an_offer_or_image_candidate() -> None:
    rows = complete_rows()
    known = mappings()
    known[0].gtin = "GTIN-90"
    rows[0]["gtin"] = "GTIN-30"
    report = build_release_feed_readiness(PRODUCT_IDS, rows, known)
    assert report["release_mapped_product_count"] == 4
    assert report["release_feed_image_product_count"] == 4
    assert report["status"] == "review"


def test_fresh_feed_check_never_grants_tracking_or_release_approval() -> None:
    report = build_release_feed_readiness(PRODUCT_IDS, complete_rows(), mappings())
    assert report["status"] == "ready_for_manual_asset_review"
    assert report["tracking_verified"] is False
    assert report["activation_allowed"] is False
