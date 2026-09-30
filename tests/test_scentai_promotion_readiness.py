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
            "image_url": ("/products/test.png" if image_ready else None),
            "image_status": (
                "approved_feed_image"
                if image_ready
                else "pending_approved_feed_or_manufacturer_image"
            ),
            **(
                {
                    "image_reviewed_at": "2026-09-18T10:00:00+00:00",
                    "image_rights_basis_id": "awin-test-feed-rights",
                    "image_rights_checked_at": "2026-09-18",
                }
                if image_ready
                else {}
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
        "product_url": "https://merchant.example/product",
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
        "missing_current_purchase_destination": 1,
    }

    assert report["rows"][0]["product_id"] == "SC-READY"
    assert report["rows"][0]["ready"] is True
    assert report["rows"][0]["eligible_purchase_offers"] == 1
    assert report["rows"][0]["eligible_affiliate_offers"] == 1
    assert report["rows"][1]["product_id"] == "SC-BLOCKED"
    assert report["rows"][1]["ready"] is False


def test_readiness_report_separates_already_live_from_promotion_candidates() -> None:
    live = staged_product("SC-LIVE", coverage=2)
    blocked = staged_product(
        "SC-BLOCKED",
        coverage=1,
        image_ready=False,
    )

    report = build_readiness_report(
        {"products": [live, blocked]},
        {"store_name": "SCENTAI", "products": [{"product_id": "SC-LIVE"}]},
        {"offers": []},
        now=NOW,
    )

    assert report["staged_count"] == 2
    assert report["already_live_count"] == 1
    assert report["promotion_candidate_count"] == 1
    assert report["ready_count"] == 0
    assert report["blocked_count"] == 2
    assert report["promotion_blocked_count"] == 1

    by_id = {row["product_id"]: row for row in report["rows"]}
    assert by_id["SC-LIVE"]["already_live"] is True
    assert by_id["SC-LIVE"]["promotion_candidate"] is False
    assert by_id["SC-BLOCKED"]["already_live"] is False
    assert by_id["SC-BLOCKED"]["promotion_candidate"] is True

    assert report["blocker_counts"]["already_live"] == 1
    assert "already_live" not in report["candidate_blocker_counts"]
    assert report["candidate_blocker_counts"] == {
        "missing_approved_image": 1,
        "missing_current_purchase_destination": 1,
    }


def test_readiness_closest_candidates_excludes_already_live_rows() -> None:
    live = staged_product("SC-LIVE", coverage=4)
    blocked = staged_product(
        "SC-BLOCKED",
        coverage=1,
        image_ready=False,
    )

    report = build_readiness_report(
        {"products": [live, blocked]},
        {"store_name": "SCENTAI", "products": [{"product_id": "SC-LIVE"}]},
        {"offers": []},
        now=NOW,
    )

    assert [row["product_id"] for row in report["closest_candidates"]] == ["SC-BLOCKED"]
    assert report["closest_candidates"][0]["promotion_candidate"] is True
    assert report["closest_candidates"][0]["already_live"] is False


def test_readiness_report_exposes_image_only_promotion_candidates() -> None:
    image_only = staged_product(
        "SC-IMAGE-ONLY",
        coverage=1,
        image_ready=False,
    )
    image_only["validation"] = {
        "catalog_ready": False,
        "blockers": ["approved_product_image_pending"],
    }
    image_and_offer = staged_product(
        "SC-IMAGE-AND-OFFER",
        coverage=1,
        image_ready=False,
    )
    ready = staged_product("SC-READY", coverage=2)

    report = build_readiness_report(
        {"products": [image_only, image_and_offer, ready]},
        {"store_name": "SCENTAI", "products": []},
        {"offers": [affiliate_offer("SC-IMAGE-ONLY"), affiliate_offer("SC-READY")]},
        now=NOW,
    )

    assert report["image_only_candidate_count"] == 1
    assert report["image_only_candidate_scope"] == "promotion_gate_only"
    assert report["image_only_candidates_require_image_rights_and_human_approval"] is True
    assert [row["product_id"] for row in report["image_only_candidates"]] == ["SC-IMAGE-ONLY"]
    candidate = report["image_only_candidates"][0]
    assert candidate["promotion_candidate"] is True
    assert candidate["already_live"] is False
    assert candidate["ready"] is False
    assert candidate["blockers"] == ["missing_approved_image"]
    assert candidate["eligible_purchase_offers"] == 1


def test_readiness_report_exposes_only_true_image_only_candidates() -> None:
    image_only = staged_product(
        "SC-IMAGE-ONLY",
        coverage=2,
        image_ready=False,
    )
    image_only["validation"] = {
        "catalog_ready": False,
        "blockers": ["approved_product_image_pending"],
    }

    identity_blocked = staged_product(
        "SC-IDENTITY-BLOCKED",
        coverage=2,
        image_ready=False,
    )
    identity_blocked["validation"] = {
        "catalog_ready": False,
        "blockers": [
            "approved_product_image_pending",
            "identity_review_required",
        ],
    }

    report = build_readiness_report(
        {"products": [image_only, identity_blocked]},
        {"store_name": "SCENTAI", "products": []},
        {
            "offers": [
                affiliate_offer("SC-IMAGE-ONLY"),
                affiliate_offer("SC-IDENTITY-BLOCKED"),
            ]
        },
        now=NOW,
    )

    assert report["image_only_candidate_count"] == 1
    assert [row["product_id"] for row in report["image_only_candidates"]] == ["SC-IMAGE-ONLY"]

    by_id = {row["product_id"]: row for row in report["rows"]}
    assert by_id["SC-IMAGE-ONLY"]["image_only_candidate"] is True
    assert by_id["SC-IMAGE-ONLY"]["source_validation_blockers"] == [
        "approved_product_image_pending"
    ]
    assert by_id["SC-IDENTITY-BLOCKED"]["image_only_candidate"] is False


def test_image_only_candidate_requires_current_purchase_destination() -> None:
    product = staged_product(
        "SC-IMAGE-NO-OFFER",
        coverage=2,
        image_ready=False,
    )
    product["validation"] = {
        "catalog_ready": False,
        "blockers": ["approved_product_image_pending"],
    }

    report = build_readiness_report(
        {"products": [product]},
        {"store_name": "SCENTAI", "products": []},
        {"offers": []},
        now=NOW,
    )

    assert report["image_only_candidate_count"] == 0
    assert report["rows"][0]["image_only_candidate"] is False
    assert "missing_current_purchase_destination" in report["rows"][0]["blockers"]


def test_current_purchase_offer_reconciles_stale_source_purchase_blocker() -> None:
    product = staged_product(
        "SC-STALE-PURCHASE",
        coverage=2,
        image_ready=False,
    )
    product["validation"]["blockers"] = [
        "verified_purchase_destination_pending",
        "approved_product_image_pending",
    ]

    report = build_readiness_report(
        {"products": [product]},
        {"store_name": "SCENTAI", "products": []},
        {
            "offers": [
                affiliate_offer("SC-STALE-PURCHASE")
            ]
        },
        now=NOW,
    )

    row = report["rows"][0]
    assert row["blockers"] == ["missing_approved_image"]
    assert row["resolved_source_validation_blockers"] == [
        "verified_purchase_destination_pending"
    ]
    assert row["effective_source_validation_blockers"] == [
        "approved_product_image_pending"
    ]
    assert row["image_only_candidate"] is True
    assert report["source_blocker_drift_count"] == 1
    assert report["source_blocker_drift"][0]["product_id"] == "SC-STALE-PURCHASE"


def test_current_purchase_offer_does_not_clear_non_purchase_source_blockers() -> None:
    product = staged_product(
        "SC-IDENTITY-PENDING",
        coverage=2,
        image_ready=False,
    )
    product["validation"]["blockers"] = [
        "canonical_gtin_feed_match_pending",
        "verified_purchase_destination_pending",
        "approved_product_image_pending",
    ]

    report = build_readiness_report(
        {"products": [product]},
        {"store_name": "SCENTAI", "products": []},
        {
            "offers": [
                affiliate_offer("SC-IDENTITY-PENDING")
            ]
        },
        now=NOW,
    )

    row = report["rows"][0]
    assert row["resolved_source_validation_blockers"] == [
        "verified_purchase_destination_pending"
    ]
    assert row["effective_source_validation_blockers"] == [
        "canonical_gtin_feed_match_pending",
        "approved_product_image_pending",
    ]
    assert row["image_only_candidate"] is False
