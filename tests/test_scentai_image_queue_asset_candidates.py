from __future__ import annotations

from scripts.build_scentai_image_approval_work_queue import (
    build_queue,
)


def test_image_queue_preserves_verified_asset_candidate_state() -> None:
    staging = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "candidate_id": "TEST",
                "brand": "Brand",
                "name": "Test",
                "batch": 1,
                "media": {
                    "image_url": None,
                    "image_status": (
                        "pending_approved_feed_or_manufacturer_image"
                    ),
                },
            }
        ]
    }
    releases = [
        {
            "release_id": "SCENTAI-RELEASE-01",
            "write_enabled": True,
            "product_ids": ["SC-TEST-100"],
        }
    ]
    candidates = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "image_state": "rights_or_source_check_pending",
                "next_action": (
                    "prefer_approved_affiliate_feed_image_else_"
                    "verify_manufacturer_asset_usage"
                ),
                "candidate_source": {
                    "source_class": "manufacturer_official",
                    "source_page_url": "https://example.com/product",
                    "exact_variant_verified": True,
                    "verified_at": "2026-09-19",
                },
            }
        ]
    }

    queue = build_queue(
        staging,
        releases,
        generated_at="2026-09-19T10:00:00+00:00",
        asset_candidates=candidates,
    )

    row = queue["items"][0]

    assert row["image_state"] == "rights_or_source_check_pending"
    assert row["candidate_source"]["exact_variant_verified"] is True
    assert "asset_usage_or_feed_rights_not_verified" in row["blockers"]
    assert queue["summary"]["rights_or_source_check_pending"] == 1
    assert queue["summary"]["approved_images"] == 0


def test_approved_image_overrides_candidate_pending_state() -> None:
    staging = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "candidate_id": "TEST",
                "brand": "Brand",
                "name": "Test",
                "batch": 1,
                "media": {
                    "image_url": "/products/test.png",
                    "image_status": "approved_feed_image",
                },
            }
        ]
    }
    releases = []
    candidates = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "image_state": "rights_or_source_check_pending",
            }
        ]
    }

    queue = build_queue(
        staging,
        releases,
        generated_at="2026-09-19T10:00:00+00:00",
        asset_candidates=candidates,
    )

    row = queue["items"][0]

    assert row["image_state"] == "approved_feed_image"
    assert row["blockers"] == []
    assert row["next_action"] == "none"
    assert queue["summary"]["approved_images"] == 1
