from __future__ import annotations

from scripts.build_scentai_jarvis_operations_status import (
    build_operations_status,
)


def base_sources() -> tuple[dict, dict, dict, dict, dict]:
    mapping = {
        "summary": {
            "staged_products": 30,
            "products_with_resolved_mapping": 29,
            "products_without_resolved_mapping": 1,
        }
    }
    affiliate = {
        "summary": {
            "programs": 9,
            "active": 0,
        }
    }
    images = {
        "summary": {
            "staged_products": 30,
            "approved_images": 0,
            "pending_images": 30,
            "review_ready": 0,
            "rights_or_source_check_pending": 5,
        }
    }
    release = {
        "summary": {
            "release_size": 5,
            "mapping_ready": 5,
            "image_identity_source_verified": 5,
            "approved_images": 0,
            "current_tracked_affiliate_offers": 0,
            "promotion_ready": 0,
        }
    }
    feed = {
        "summary": {
            "programs_with_full_release_mapping": 2,
            "approved_programs_with_full_release_mapping": 0,
        },
        "programs": [
            {
                "merchant_id": "douglas",
                "network": "Awin",
                "program": "Douglas_DE",
                "application_status": "applied",
                "program_approved": False,
                "full_release_mapping_coverage": True,
                "next_action": "await_program_decision",
            }
        ],
    }
    return mapping, affiliate, images, release, feed


def test_control_plane_waits_for_external_affiliate_decision() -> None:
    status = build_operations_status(
        *base_sources(),
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert status["overall_state"] == ("waiting_external_affiliate_decision")
    assert status["user_approval_required_now"] is False
    assert status["next_action"] == "await_affiliate_program_decision"
    assert status["safety"]["no_automatic_live_release"] is True
    assert status["safety"]["commission_may_affect_recommendations"] is False


def test_approved_full_mapping_path_opens_integration_only() -> None:
    mapping, affiliate, images, release, feed = base_sources()
    feed["summary"]["approved_programs_with_full_release_mapping"] = 1
    feed["programs"][0]["application_status"] = "approved"
    feed["programs"][0]["program_approved"] = True

    status = build_operations_status(
        mapping,
        affiliate,
        images,
        release,
        feed,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert status["overall_state"] == "integration_path_open"
    assert status["next_action"] == "run_feed_preflight_and_dry_run"
    assert status["user_approval_required_now"] is False
    assert status["safety"]["live_routing_allowed"] is False


def test_complete_release_requires_user_approval() -> None:
    mapping, affiliate, images, release, feed = base_sources()
    feed["summary"]["approved_programs_with_full_release_mapping"] = 1
    release["summary"]["approved_images"] = 5
    release["summary"]["current_tracked_affiliate_offers"] = 5
    release["summary"]["promotion_ready"] = 5

    status = build_operations_status(
        mapping,
        affiliate,
        images,
        release,
        feed,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert status["overall_state"] == "ready_for_user_approval"
    assert status["user_approval_required_now"] is True
    assert status["next_action_class"] == "approval_required"
    assert status["safety"]["live_routing_allowed"] is False
