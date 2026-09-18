from __future__ import annotations

from datetime import UTC, datetime

from scripts.report_scentai_promotion_readiness import (
    build_readiness_report,
    promotion_tier,
)


NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def staged_product(
    product_id: str,
    *,
    coverage: int = 2,
    provisional: bool = False,
    image_ready: bool = True,
) -> dict:
    return {
        "candidate_id": product_id.replace("SC-", ""),
        "product_id": product_id,
        "batch": 1,
        "brand": "Test Brand",
        "name": product_id,
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "classification": {
            "target_groups": ["unisex"],
            "audience_lean": None,
        },
        "fragrance_profile": {
            "recommendation_profile": {
                "scores": {
                    "freshness": 8,
                    "sweetness": 3,
                    "woodiness": 5,
                    "spiciness": 2,
                }
            }
        },
        "community": {
            "rating_10": 8.1,
            "provisional": provisional,
        },
        "media": {
            "image_url": (
                "/products/test.png"
                if image_ready
                else None
            ),
            "image_status": (
                "approved_feed_image"
                if image_ready
                else "pending_approved_feed_or_manufacturer_image"
            ),
        },
        "commerce": {
            "merchant_coverage_count": coverage,
        },
    }


def affiliate_offer(product_id: str) -> dict:
    return {
        "offer_id": f"merchant-{product_id}",
        "product_id": product_id,
        "merchant_id": "merchant-de",
        "merchant_name": "Merchant",
        "price": 79.95,
        "currency": "EUR",
        "shipping_cost": 0.0,
        "in_stock": True,
        "affiliate_url": "https://network.example/click",
        "last_updated_at": "2026-09-18T11:00:00Z",
    }


def test_promotion_tiers_use_coverage_and_provisional_state() -> None:
    assert promotion_tier(staged_product("SC-A", coverage=2)) == "A"
    assert promotion_tier(staged_product("SC-B", coverage=1)) == "B"
    assert promotion_tier(staged_product("SC-C", coverage=0)) == "C"
    assert (
        promotion_tier(
            staged_product(
                "SC-PROVISIONAL",
                coverage=3,
                provisional=True,
            )
        )
        == "C"
    )


def test_readiness_report_summarizes_live_blockers() -> None:
    ready = staged_product("SC-READY", coverage=3)
    blocked = staged_product(
        "SC-BLOCKED",
        coverage=1,
        image_ready=False,
    )

    report = build_readiness_report(
        {"products": [ready, blocked]},
        {"store_name": "SCENTAI", "products": []},
        {"offers": [affiliate_offer("SC-READY")]},
        now=NOW,
    )

    assert report["staged_count"] == 2
    assert report["ready_count"] == 1
    assert report["blocked_count"] == 1
    assert report["tier_counts"] == {
        "A": 1,
        "B": 1,
        "C": 0,
    }
    assert report["blocker_counts"] == {
        "missing_approved_image": 1,
        "missing_current_affiliate_offer": 1,
    }

    assert report["rows"][0]["product_id"] == "SC-READY"
    assert report["rows"][0]["ready"] is True
    assert report["rows"][1]["product_id"] == "SC-BLOCKED"
    assert report["rows"][1]["ready"] is False
