from __future__ import annotations

from datetime import UTC, datetime

from scripts.plan_scentai_promotion_batch import (
    audience_gap_score,
    build_batch_plan,
    live_target_counts,
)

NOW = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)


def staged_product(
    product_id: str,
    *,
    targets: list[str],
    merchant_coverage: int = 2,
    rating_count: int = 1000,
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
        "fragrance_profile": {
            "recommendation_profile": {
                "scores": {
                    "freshness": 5,
                    "sweetness": 5,
                    "woodiness": 5,
                    "spiciness": 5,
                }
            }
        },
        "community": {
            "rating_10": 8.0,
            "rating_count": rating_count,
            "provisional": provisional,
        },
        "media": {
            "image_url": None,
            "image_status": "pending_approved_feed_or_manufacturer_image",
        },
        "commerce": {
            "merchant_coverage_count": merchant_coverage,
        },
    }


def catalog() -> dict:
    return {
        "products": [
            {
                "product_id": "SC-LIVE-MEN-1",
                "category": "fragrance",
                "in_stock": True,
                "attributes": {
                    "target_group": "men",
                },
            },
            {
                "product_id": "SC-LIVE-MEN-2",
                "category": "fragrance",
                "in_stock": True,
                "attributes": {
                    "target_group": "men",
                },
            },
            {
                "product_id": "SC-LIVE-WOMEN-1",
                "category": "fragrance",
                "in_stock": True,
                "attributes": {
                    "target_group": "women",
                },
            },
        ]
    }


def test_live_target_counts_reads_catalog_targets() -> None:
    counts = live_target_counts(catalog())

    assert counts["men"] == 2
    assert counts["women"] == 1


def test_audience_gap_score_prioritizes_underrepresented_target() -> None:
    counts = live_target_counts(catalog())

    assert audience_gap_score(["women"], counts) == 5.0
    assert audience_gap_score(["men"], counts) == 0.0


def test_batch_plan_prefers_underrepresented_non_provisional_product() -> None:
    staging = {
        "products": [
            staged_product(
                "SC-MEN-CANDIDATE",
                targets=["men"],
                merchant_coverage=3,
                rating_count=5000,
            ),
            staged_product(
                "SC-WOMEN-CANDIDATE",
                targets=["women"],
                merchant_coverage=2,
                rating_count=1000,
            ),
            staged_product(
                "SC-WOMEN-PROVISIONAL",
                targets=["women"],
                merchant_coverage=3,
                rating_count=6000,
                provisional=True,
            ),
        ]
    }

    report = build_batch_plan(
        staging,
        catalog(),
        {"offers": []},
        now=NOW,
        limit=3,
    )

    assert report["selected"][0]["product_id"] == "SC-WOMEN-CANDIDATE"
    assert report["selected"][1]["product_id"] == "SC-MEN-CANDIDATE"
    assert report["selected"][2]["product_id"] == "SC-WOMEN-PROVISIONAL"


def test_batch_plan_never_marks_blocked_product_ready() -> None:
    report = build_batch_plan(
        {
            "products": [
                staged_product(
                    "SC-WOMEN-CANDIDATE",
                    targets=["women"],
                )
            ]
        },
        catalog(),
        {"offers": []},
        now=NOW,
        limit=1,
    )

    row = report["selected"][0]
    assert row["promotion_ready"] is False
    assert "missing_approved_image" in row["blockers"]
    assert "missing_current_purchase_destination" in row["blockers"]


def test_batch_plan_limit_is_hard_capped() -> None:
    try:
        build_batch_plan(
            {"products": []},
            catalog(),
            {"offers": []},
            now=NOW,
            limit=11,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("limit above 10 must be rejected")
