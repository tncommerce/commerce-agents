from __future__ import annotations

from datetime import UTC, datetime

from scripts.promote_scentai_catalog import (
    build_catalog_product,
    eligible_purchase_offers,
    promotion_blockers,
    promotion_plan,
)

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def staged_product() -> dict:
    return {
        "candidate_id": "TEST-FRAGRANCE",
        "product_id": "SC-TEST-FRAGRANCE-100",
        "batch": 1,
        "brand": "Test Brand",
        "name": "Test Fragrance",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "classification": {
            "target_groups": ["unisex"],
            "audience_lean": None,
        },
        "fragrance_profile": {
            "scent_family": "fresh woody",
            "key_notes": ["bergamot", "cedar"],
            "community_accords": ["fresh", "citrus", "woody"],
            "recommendation_profile": {
                "scores": {
                    "freshness": 8,
                    "sweetness": 2,
                    "woodiness": 5,
                    "spiciness": 3,
                },
                "source": "deterministic_editorial_mapping_v1",
                "confidence": "medium",
                "customer_facing": False,
            },
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.0,
            "rating_count": 500,
            "longevity_10": 7.5,
            "projection_10": 7.0,
            "provisional": False,
        },
        "media": {
            "image_url": "/products/test/test-fragrance.png",
            "image_status": "approved_feed_image",
        },
        "validation": {
            "catalog_ready": False,
            "blockers": [],
        },
    }


def affiliate_offer() -> dict:
    return {
        "offer_id": "merchant-test-fragrance",
        "product_id": "SC-TEST-FRAGRANCE-100",
        "merchant_id": "merchant-de",
        "merchant_name": "Merchant",
        "merchant_product_id": "SKU-1",
        "price": 79.95,
        "currency": "EUR",
        "shipping_cost": 0.0,
        "in_stock": True,
        "product_url": "https://merchant.example/product",
        "affiliate_url": "https://network.example/click",
        "network": "Awin",
        "data_source": "approved-feed",
        "last_updated_at": "2026-09-18T11:00:00Z",
    }


def test_current_staging_requirements_are_strict() -> None:
    product = staged_product()
    product["media"] = {
        "image_url": None,
        "image_status": "pending_approved_feed_or_manufacturer_image",
    }

    blockers = promotion_blockers(
        product,
        [],
        now=NOW,
    )

    assert "missing_approved_image" in blockers
    assert "missing_current_purchase_destination" in blockers


def test_ready_product_passes_promotion_gates() -> None:
    product = staged_product()
    offer = affiliate_offer()

    blockers = promotion_blockers(
        product,
        [offer],
        now=NOW,
    )

    assert blockers == []


def test_non_affiliate_offer_unlocks_promotion_when_purchase_url_is_verified() -> None:
    product = staged_product()
    offer = affiliate_offer()
    offer["affiliate_url"] = None

    blockers = promotion_blockers(
        product,
        [offer],
        now=NOW,
    )

    assert blockers == []


def test_stale_offer_does_not_unlock_promotion() -> None:
    product = staged_product()
    offer = affiliate_offer()
    offer["last_updated_at"] = "2026-09-14T11:00:00Z"

    blockers = promotion_blockers(
        product,
        [offer],
        now=NOW,
        max_offer_age_hours=72.0,
    )

    assert "missing_current_purchase_destination" in blockers



def test_equal_price_prefers_affiliate_then_higher_commission() -> None:
    direct = affiliate_offer()
    direct["offer_id"] = "direct"
    direct["merchant_name"] = "Direct Merchant"
    direct["affiliate_url"] = None
    direct["commission_rate"] = None

    lower = affiliate_offer()
    lower["offer_id"] = "affiliate-lower"
    lower["merchant_name"] = "Affiliate Lower"
    lower["commission_rate"] = 4.0

    higher = affiliate_offer()
    higher["offer_id"] = "affiliate-higher"
    higher["merchant_name"] = "Affiliate Higher"
    higher["commission_rate"] = 8.0

    ranked = eligible_purchase_offers(
        [direct, lower, higher],
        product_id="SC-TEST-FRAGRANCE-100",
        now=NOW,
        max_age_hours=72.0,
    )

    assert [row["offer_id"] for row in ranked] == [
        "affiliate-higher",
        "affiliate-lower",
        "direct",
    ]


def test_provisional_community_data_is_blocked_by_default() -> None:
    product = staged_product()
    product["community"]["provisional"] = True

    blockers = promotion_blockers(
        product,
        [affiliate_offer()],
        now=NOW,
    )

    assert "provisional_community_data" in blockers


def test_missing_target_group_blocks_live_promotion() -> None:
    product = staged_product()
    product["classification"]["target_groups"] = []

    blockers = promotion_blockers(
        product,
        [affiliate_offer()],
        now=NOW,
    )

    assert "missing_target_group" in blockers


def test_catalog_conversion_marks_current_merchant_price() -> None:
    converted = build_catalog_product(
        staged_product(),
        best_offer=affiliate_offer(),
    )

    assert converted["product_id"] == "SC-TEST-FRAGRANCE-100"
    assert converted["price"] == 79.95
    assert converted["attributes"]["price_source"] == "current_merchant_offer"
    assert converted["attributes"]["profile_source"] == "deterministic_editorial_mapping_v1"


def test_promotion_plan_is_all_gate_aware() -> None:
    ready = staged_product()
    blocked = staged_product()
    blocked["product_id"] = "SC-BLOCKED-100"
    blocked["candidate_id"] = "BLOCKED"
    blocked["media"] = {
        "image_url": None,
        "image_status": "pending_approved_feed_or_manufacturer_image",
    }

    plan = promotion_plan(
        {"products": [ready, blocked]},
        {"store_name": "DUFYND", "products": []},
        {"offers": [affiliate_offer()]},
        product_ids=[],
        batch=1,
        limit=10,
        now=NOW,
        max_offer_age_hours=72.0,
        allow_provisional=False,
    )

    assert plan["selected_count"] == 2
    assert plan["ready_count"] == 1
    assert plan["blocked_count"] == 1
    assert plan["rows"][0]["ready"] is True
    assert plan["rows"][1]["ready"] is False
