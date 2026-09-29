from __future__ import annotations

from scripts.report_dufynd_visual_coverage import (
    build_visual_coverage_report,
    storefront_presentation_state,
    visual_state,
)


def test_visual_state_distinguishes_truth_editorial_and_missing() -> None:
    assert (
        visual_state(
            {
                "visuals": [
                    {
                        "role": "cutout",
                        "fidelity_status": "verified",
                        "url": "/products/truth.webp",
                    }
                ]
            }
        )
        == "verified_product_truth"
    )
    assert (
        visual_state(
            {
                "visuals": [
                    {
                        "role": "editorial",
                        "fidelity_status": "editorial_only",
                        "url": "/products/editorial.webp",
                    }
                ]
            }
        )
        == "editorial_only"
    )
    assert (
        visual_state(
            {
                "image_url": "/products/pilot/legacy-editorial.webp",
                "visuals": [],
            }
        )
        == "legacy_visual"
    )
    assert visual_state({"visuals": []}) == "missing_real_asset"




def test_storefront_presentation_distinguishes_layered_editorial_and_bare_truth() -> None:
    assert (
        storefront_presentation_state(
            {
                "visuals": [
                    {
                        "role": "cutout",
                        "fidelity_status": "verified",
                        "url": "/products/truth.webp",
                    },
                    {
                        "role": "editorial",
                        "fidelity_status": "editorial_only",
                        "composition": "bottle_free_backdrop",
                        "url": "/products/world.webp",
                    },
                ]
            }
        )
        == "layered_product_truth"
    )
    assert (
        storefront_presentation_state(
            {
                "visuals": [
                    {
                        "role": "cutout",
                        "fidelity_status": "verified",
                        "url": "/products/truth.webp",
                    },
                    {
                        "role": "editorial",
                        "fidelity_status": "editorial_only",
                        "composition": "product_scene",
                        "url": "/products/editorial.webp",
                    },
                ]
            }
        )
        == "editorial_product_scene"
    )
    assert (
        storefront_presentation_state(
            {
                "visuals": [
                    {
                        "role": "cutout",
                        "fidelity_status": "verified",
                        "url": "/products/truth.webp",
                    }
                ]
            }
        )
        == "product_truth_stage_only"
    )
    assert (
        storefront_presentation_state(
            {
                "image_url": "/products/pilot/legacy-editorial.webp",
                "visuals": [],
            }
        )
        == "legacy_image_presentation"
    )


def test_report_prioritizes_human_review_and_release_asset_work() -> None:
    products = {
        "products": [
            {
                "product_id": "SC-A-100",
                "brand": "A",
                "name": "Truth",
                "visuals": [
                    {
                        "role": "primary",
                        "fidelity_status": "verified",
                        "url": "/truth.webp",
                    }
                ],
            },
            {
                "product_id": "SC-B-100",
                "brand": "B",
                "name": "Editorial",
                "visuals": [
                    {
                        "role": "editorial",
                        "fidelity_status": "editorial_only",
                        "composition": "product_scene",
                        "url": "/editorial.webp",
                    }
                ],
            },
            {
                "product_id": "SC-C-100",
                "brand": "C",
                "name": "Missing",
                "visuals": [],
            },
        ]
    }
    review_queue = {
        "items": [
            {
                "product_id": "SC-B-100",
                "priority": "P1",
                "status": "candidate_generated_pending_reference_gate",
                "candidate_asset": "review-assets/b.webp",
                "next_action": "review",
            },
            {
                "product_id": "SC-C-100",
                "priority": "P0",
                "status": "candidate_generated_pending_reference_gate",
                "candidate_asset": "review-assets/c.webp",
                "next_action": "review",
            },
        ]
    }
    approval_queue = {
        "items": [
            {
                "product_id": "SC-D-100",
                "brand": "D",
                "name": "Blocked",
                "image_state": "licensed_source_required",
                "blockers": ["approved_product_image_missing"],
                "next_action": "obtain_asset",
                "approval_action_class": "approval_required",
                "release": {
                    "release_id": "SCENTAI-RELEASE-01",
                    "release_order": 1,
                    "position": 2,
                },
            },
            {
                "product_id": "SC-A-100",
                "brand": "A",
                "name": "Approved",
                "image_state": "approved_licensed_image",
                "blockers": [],
                "next_action": "none",
                "approval_action_class": "approval_required",
                "release": {
                    "release_id": "SCENTAI-RELEASE-01",
                    "release_order": 1,
                    "position": 1,
                },
            },
        ]
    }

    report = build_visual_coverage_report(
        products,
        review_queue,
        approval_queue,
    )

    assert report["live_product_count"] == 3
    assert report["coverage"]["verified_product_truth"] == 1
    assert report["coverage"]["editorial_only"] == 1
    assert report["coverage"]["missing_real_asset"] == 1
    assert report["coverage"]["real_visual_coverage_rate_pct"] == 66.67
    assert report["storefront_presentation"]["editorial_product_scene"] == 1
    assert report["storefront_presentation"]["product_truth_stage_only"] == 1
    assert report["storefront_presentation"]["missing_presentation"] == 1
    assert report["storefront_presentation"]["background_presented_rate_pct"] == 33.33
    assert set(report["storefront_presentation_upgrade_product_ids"]) == {
        "SC-A-100",
        "SC-C-100",
    }
    assert report["fidelity_review_ready_count"] == 2
    assert report["fidelity_review_queue"][0]["product_id"] == "SC-C-100"
    assert report["release_asset_blocked_count"] == 1
    assert report["release_asset_queue"][0]["product_id"] == "SC-D-100"


def test_report_ignores_non_scentai_products() -> None:
    report = build_visual_coverage_report(
        {
            "products": [
                {
                    "product_id": "OTHER-1",
                    "brand": "Other",
                    "name": "Ignore",
                    "visuals": [],
                }
            ]
        },
        {"items": []},
        {"items": []},
    )

    assert report["live_product_count"] == 0
    assert report["coverage"]["real_visual_coverage_rate_pct"] == 0.0
    assert report["storefront_presentation"]["background_presented_rate_pct"] == 0.0
