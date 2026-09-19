from __future__ import annotations

from scripts.build_scentai_jarvis_operations_status import (
    build_operations_status,
)
from scripts.validate_scentai_jarvis_operations_status import (
    validate_operations_status,
)


def sources() -> tuple[dict, dict, dict, dict, dict]:
    return (
        {
            "summary": {
                "staged_products": 30,
                "products_with_resolved_mapping": 29,
                "products_without_resolved_mapping": 1,
            }
        },
        {"summary": {"programs": 9, "active": 0}},
        {
            "summary": {
                "staged_products": 30,
                "approved_images": 0,
                "pending_images": 30,
                "review_ready": 0,
                "rights_or_source_check_pending": 5,
            }
        },
        {
            "summary": {
                "release_size": 5,
                "mapping_ready": 5,
                "image_identity_source_verified": 5,
                "approved_images": 0,
                "current_tracked_affiliate_offers": 0,
                "promotion_ready": 0,
            }
        },
        {
            "summary": {
                "programs_with_full_release_mapping": 2,
                "approved_programs_with_full_release_mapping": 0,
            },
            "programs": [],
        },
    )


def test_current_status_matches_sources() -> None:
    mapping, affiliate, images, release, feed = sources()
    current = build_operations_status(
        mapping,
        affiliate,
        images,
        release,
        feed,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    report = validate_operations_status(
        current,
        mapping,
        affiliate,
        images,
        release,
        feed,
    )

    assert report["valid"] is True
    assert report["issues"] == []


def test_source_change_marks_status_stale() -> None:
    mapping, affiliate, images, release, feed = sources()
    current = build_operations_status(
        mapping,
        affiliate,
        images,
        release,
        feed,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    release["summary"]["approved_images"] = 1

    report = validate_operations_status(
        current,
        mapping,
        affiliate,
        images,
        release,
        feed,
    )

    assert report["valid"] is False
    assert "operations_status_source_fingerprint_stale" in report["issues"]
    assert any(issue.startswith("operations_status_field_drift:") for issue in report["issues"])


def test_manual_status_edit_is_detected() -> None:
    mapping, affiliate, images, release, feed = sources()
    current = build_operations_status(
        mapping,
        affiliate,
        images,
        release,
        feed,
        generated_at="2026-09-19T10:00:00+00:00",
    )
    current["overall_state"] = "active"

    report = validate_operations_status(
        current,
        mapping,
        affiliate,
        images,
        release,
        feed,
    )

    assert report["valid"] is False
    assert "overall_state" in report["drift_fields"]
