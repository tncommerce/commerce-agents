from __future__ import annotations

from scripts.refresh_scentai_jarvis_state import (
    summary,
)


def test_refresh_summary_exposes_control_plane_state() -> None:
    state = {
        "mapping_queue": {
            "summary": {
                "staged_products": 30,
            }
        },
        "affiliate_status": {
            "summary": {
                "programs": 9,
            }
        },
        "image_queue": {
            "summary": {
                "pending_images": 30,
            }
        },
        "feed_queue": {
            "summary": {
                "programs_with_full_release_mapping": 2,
            }
        },
        "release_status": {
            "summary": {
                "release_size": 5,
                "promotion_ready": 0,
            }
        },
        "operations": {
            "overall_state": "waiting_external_affiliate_decision",
            "next_action": "await_affiliate_program_decision",
            "user_approval_required_now": False,
        },
    }

    report = summary(state)

    assert report["overall_state"] == ("waiting_external_affiliate_decision")
    assert report["next_action"] == "await_affiliate_program_decision"
    assert report["user_approval_required_now"] is False
    assert report["mapping"]["staged_products"] == 30
    assert report["affiliate"]["programs"] == 9
    assert report["images"]["pending_images"] == 30
    assert report["release_01"]["release_size"] == 5
