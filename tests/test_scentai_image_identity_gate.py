from __future__ import annotations

from scripts.build_scentai_image_approval_work_queue import (
    build_queue,
)


def test_identity_pending_candidate_does_not_advance_audit_too_far() -> None:
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
                    "image_status": ("pending_approved_feed_or_manufacturer_image"),
                },
            }
        ]
    }
    candidates = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "image_state": "identity_check_pending",
                "next_action": "verify_exact_variant",
                "candidate_source": {
                    "source_class": "manufacturer_official",
                    "exact_variant_verified": False,
                    "verified_at": "2026-09-19",
                },
            }
        ]
    }

    queue = build_queue(
        staging,
        [],
        generated_at="2026-09-19T10:00:00+00:00",
        asset_candidates=candidates,
    )

    row = queue["items"][0]

    assert row["image_state"] == "identity_check_pending"
    assert "exact_variant_identity_not_verified" in row["blockers"]
    assert len(row["audit_trail"]) == 2
    assert row["audit_trail"][-1]["to"] == "identity_check_pending"
    assert queue["summary"]["identity_check_pending"] == 1
    assert queue["summary"]["rights_or_source_check_pending"] == 0
