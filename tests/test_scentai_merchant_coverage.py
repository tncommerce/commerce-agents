from __future__ import annotations

from datetime import UTC, datetime

from scripts.report_scentai_merchant_coverage import (
    build_merchant_coverage_report,
)

NOW = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)


def staged_product(
    product_id: str,
    *,
    targets: list[str],
    merchant_coverage: int = 2,
    image_ready: bool = False,
    provisional: bool = False,
) -> dict:
    return {
        "candidate_id": product_id.replace("SC-", ""),
        "product_id": product_id,
        "batch": 1,
        "brand": "Brand",
        "name": product_id,
        "classification": {
            "target_groups": targets,
        },
        "community": {
            "provisional": provisional,
        },
        "media": {
            "image_url": ("/products/test.png" if image_ready else None),
            "image_status": (
                "approved_feed_image"
                if image_ready
                else "pending_approved_feed_or_manufacturer_image"
            ),
        },
        "commerce": {
            "merchant_coverage_count": merchant_coverage,
        },
    }


def test_merchant_coverage_distinguishes_research_from_integration() -> None:
    staging = {
        "products": [
            staged_product(
                "SC-WOMEN-1",
                targets=["women"],
                merchant_coverage=3,
            )
        ]
    }
    catalog = {
        "products": [
            {
                "product_id": "SC-LIVE-1",
                "category": "fragrance",
                "in_stock": True,
                "attributes": {
                    "target_group": "men, unisex",
                },
            }
        ]
    }

    report = build_merchant_coverage_report(
        staging,
        catalog,
        {"offers": []},
        {"mappings": []},
        now=NOW,
    )

    row = report["rows"][0]
    assert row["declared_merchant_coverage_count"] == 3
    assert row["integrated_offer_count"] == 0
    assert row["fresh_affiliate_offer_count"] == 0
    assert "no_integrated_merchant_offer" in row["blockers"]
    assert "no_resolved_merchant_mapping" in row["blockers"]
    assert report["live_audience_counts"] == {
        "men": 1,
        "unisex": 1,
    }


def test_merchant_coverage_counts_fresh_affiliate_offer_and_mapping() -> None:
    staging = {
        "products": [
            staged_product(
                "SC-READY-1",
                targets=["women"],
                image_ready=True,
            )
        ]
    }

    report = build_merchant_coverage_report(
        staging,
        {"products": []},
        {
            "offers": [
                {
                    "offer_id": "offer-1",
                    "product_id": "SC-READY-1",
                    "merchant_name": "Merchant",
                    "price": 50,
                    "currency": "EUR",
                    "shipping_cost": 0,
                    "in_stock": True,
                    "affiliate_url": "https://example.com/a",
                    "last_updated_at": "2026-09-18T19:00:00Z",
                }
            ]
        },
        {
            "mappings": [
                {
                    "product_id": "SC-READY-1",
                    "merchant": "merchant",
                    "merchant_product_id": "sku-1",
                    "ean": None,
                    "gtin": None,
                }
            ]
        },
        now=NOW,
    )

    row = report["rows"][0]
    assert row["integrated_offer_count"] == 1
    assert row["affiliate_offer_count"] == 1
    assert row["fresh_affiliate_offer_count"] == 1
    assert row["resolved_mapping_count"] == 1
    assert row["approved_image_ready"] is True
    assert row["blockers"] == []


def test_provisional_community_data_remains_visible_as_gap() -> None:
    report = build_merchant_coverage_report(
        {
            "products": [
                staged_product(
                    "SC-PROVISIONAL",
                    targets=["men"],
                    provisional=True,
                )
            ]
        },
        {"products": []},
        {"offers": []},
        {"mappings": []},
        now=NOW,
    )

    assert "community_data_provisional" in report["rows"][0]["blockers"]
