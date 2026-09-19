from __future__ import annotations

from scripts.report_scentai_conversion import (
    build_conversion_report,
)


def catalog() -> dict:
    return {
        "products": [
            {
                "product_id": "SC-ONE",
                "brand": "Brand",
                "title": "Brand One",
                "attributes": {
                    "canonical_name": "One",
                },
            },
            {
                "product_id": "SC-TWO",
                "brand": "Brand",
                "title": "Brand Two",
                "attributes": {
                    "canonical_name": "Two",
                },
            },
        ]
    }


def test_conversion_report_aggregates_funnel_counts_and_rates() -> None:
    report = build_conversion_report(
        [
            {
                "cohort_date": "2026-09-18",
                "consultation_sessions": 20,
                "recommendation_sessions": 16,
                "advisor_open_sessions": 8,
                "detail_view_sessions": 6,
                "comparison_sessions": 4,
                "clickout_sessions": 2,
            },
            {
                "cohort_date": "2026-09-19",
                "consultation_sessions": 10,
                "recommendation_sessions": 9,
                "advisor_open_sessions": 5,
                "detail_view_sessions": 3,
                "comparison_sessions": 2,
                "clickout_sessions": 1,
            },
        ],
        [],
        [],
        [],
        catalog(),
    )

    summary = report["summary"]
    assert summary["consultation_sessions"] == 30
    assert summary["recommendation_sessions"] == 25
    assert summary["advisor_open_sessions"] == 13
    assert summary["detail_view_sessions"] == 9
    assert summary["comparison_sessions"] == 6
    assert summary["clickout_sessions"] == 3
    assert summary["consultation_to_recommendation_pct"] == 83.33
    assert summary["recommendation_to_clickout_pct"] == 12.0


def test_product_funnel_is_enriched_and_sample_status_is_explicit() -> None:
    report = build_conversion_report(
        [],
        [
            {
                "product_id": "SC-ONE",
                "recommendation_views": 20,
                "recommendation_sessions": 12,
                "advisor_open_sessions": 7,
                "detail_view_sessions": 5,
                "comparison_sessions": 3,
                "clickout_sessions": 4,
                "advisor_open_rate_pct": 58.33,
                "recommendation_to_clickout_pct": 33.33,
            },
            {
                "product_id": "SC-TWO",
                "recommendation_views": 4,
                "recommendation_sessions": 3,
                "advisor_open_sessions": 1,
                "detail_view_sessions": 1,
                "comparison_sessions": 0,
                "clickout_sessions": 1,
                "advisor_open_rate_pct": 33.33,
                "recommendation_to_clickout_pct": 33.33,
            },
        ],
        [],
        [],
        catalog(),
        minimum_sample_sessions=10,
    )

    first = report["top_clickout_products"][0]
    assert first["product"] == "Brand One"
    assert first["sample_status"] == "sufficient_signal"

    second = report["top_clickout_products"][1]
    assert second["product"] == "Brand Two"
    assert second["sample_status"] == "early_signal"

    assert len(report["best_clickout_rates"]) == 1
    assert report["best_clickout_rates"][0]["product_id"] == "SC-ONE"


def test_position_and_surface_reporting_preserves_counts() -> None:
    report = build_conversion_report(
        [],
        [],
        [
            {
                "item_position": 2,
                "recommendation_views": 20,
                "recommendation_sessions": 15,
                "advisor_open_sessions": 6,
                "open_rate_pct": 40,
            },
            {
                "item_position": 1,
                "recommendation_views": 25,
                "recommendation_sessions": 20,
                "advisor_open_sessions": 10,
                "open_rate_pct": 50,
            },
        ],
        [
            {
                "surface": "fragrance_detail",
                "clickouts": 7,
                "clickout_sessions": 5,
                "products_clicked": 3,
                "merchants_clicked": 2,
            },
            {
                "surface": "free_comparison",
                "clickouts": 2,
                "clickout_sessions": 2,
                "products_clicked": 2,
                "merchants_clicked": 1,
            },
        ],
        catalog(),
    )

    assert [row["item_position"] for row in report["advisor_positions"]] == [1, 2]
    assert report["clickout_surfaces"][0]["surface"] == "fragrance_detail"


def test_zero_denominators_do_not_create_fake_conversion_rates() -> None:
    report = build_conversion_report(
        [
            {
                "cohort_date": "2026-09-18",
                "consultation_sessions": 0,
                "recommendation_sessions": 0,
                "advisor_open_sessions": 0,
                "detail_view_sessions": 0,
                "comparison_sessions": 0,
                "clickout_sessions": 0,
            }
        ],
        [],
        [],
        [],
        catalog(),
    )

    assert report["summary"]["consultation_to_recommendation_pct"] is None
    assert report["summary"]["recommendation_to_clickout_pct"] is None


def test_acquisition_sources_are_reported_with_sample_status() -> None:
    report = build_conversion_report(
        [],
        [],
        [],
        [],
        catalog(),
        acquisition_rows=[
            {
                "acquisition_source": "duftfinder",
                "landing_sessions": 12,
                "consultation_sessions": 8,
                "recommendation_sessions": 7,
                "detail_sessions": 5,
                "comparison_sessions": 3,
                "clickout_sessions": 2,
                "landing_to_consultation_pct": 66.67,
                "consultation_to_recommendation_pct": 87.5,
                "landing_to_clickout_pct": 16.67,
            },
            {
                "acquisition_source": "parfum_geschenkberater",
                "landing_sessions": 3,
                "consultation_sessions": 2,
                "recommendation_sessions": 2,
                "detail_sessions": 1,
                "comparison_sessions": 0,
                "clickout_sessions": 0,
                "landing_to_consultation_pct": 66.67,
                "consultation_to_recommendation_pct": 100,
                "landing_to_clickout_pct": 0,
            },
        ],
        minimum_sample_sessions=10,
    )

    assert report["acquisition_sources"][0] == {
        "acquisition_source": "duftfinder",
        "landing_sessions": 12,
        "consultation_sessions": 8,
        "recommendation_sessions": 7,
        "detail_sessions": 5,
        "comparison_sessions": 3,
        "clickout_sessions": 2,
        "landing_to_consultation_pct": 66.67,
        "consultation_to_recommendation_pct": 87.5,
        "landing_to_clickout_pct": 16.67,
        "sample_status": "sufficient_signal",
    }
    assert report["acquisition_sources"][1]["sample_status"] == "early_signal"


def test_personal_library_engagement_is_labeled_and_sampled() -> None:
    report = build_conversion_report(
        [],
        [],
        [],
        [],
        catalog(),
        library_rows=[
            {
                "product_id": "SC-ONE",
                "wishlist_adds": 14,
                "wishlist_removes": 2,
                "collection_adds": 8,
                "collection_removes": 1,
                "wishlist_add_sessions": 12,
                "collection_add_sessions": 7,
            },
            {
                "product_id": "SC-TWO",
                "wishlist_adds": 2,
                "wishlist_removes": 0,
                "collection_adds": 1,
                "collection_removes": 0,
                "wishlist_add_sessions": 2,
                "collection_add_sessions": 1,
            },
        ],
        minimum_sample_sessions=10,
    )

    first = report["personal_library_engagement"][0]
    assert first["product"] == "Brand One"
    assert first["wishlist_add_sessions"] == 12
    assert first["collection_add_sessions"] == 7
    assert first["sample_status"] == "sufficient_signal"

    second = report["personal_library_engagement"][1]
    assert second["product"] == "Brand Two"
    assert second["sample_status"] == "early_signal"


def test_retention_summary_preserves_page_and_advisor_sessions() -> None:
    report = build_conversion_report(
        [],
        [],
        [],
        [],
        catalog(),
        retention_rows=[
            {
                "wishlist_page_views": 14,
                "wishlist_page_sessions": 10,
                "collection_page_views": 9,
                "collection_page_sessions": 7,
                "wishlist_add_sessions": 8,
                "collection_add_sessions": 5,
                "collection_advisor_sessions": 3,
                "last_retention_event_at": "2026-09-19T07:00:00Z",
            }
        ],
    )

    assert report["retention_summary"] == {
        "wishlist_page_views": 14,
        "wishlist_page_sessions": 10,
        "collection_page_views": 9,
        "collection_page_sessions": 7,
        "wishlist_add_sessions": 8,
        "collection_add_sessions": 5,
        "collection_advisor_sessions": 3,
        "last_retention_event_at": "2026-09-19T07:00:00Z",
    }
