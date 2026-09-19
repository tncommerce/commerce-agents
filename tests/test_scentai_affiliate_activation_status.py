from __future__ import annotations

from scripts.evaluate_scentai_affiliate_activation import (
    build_state_report,
)


def test_affiliate_state_report_uses_control_plane_summary_schema() -> None:
    programs = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "douglas",
                "program": "Douglas_DE",
                "status": "applied",
            },
            {
                "merchant_id": "flaconi",
                "program": "Flaconi DE",
                "status": "approved",
            },
        ],
        "other_networks": [],
    }

    report = build_state_report(
        programs,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert report["generated_at"] == "2026-09-19T10:00:00+00:00"
    assert report["summary"] == {
        "programs": 2,
        "approved": 1,
        "active": 0,
        "pending": 2,
        "ready_for_user_approval": 0,
    }
    assert report["program_count"] == 2
    assert report["live_program_count"] == 0

    flaconi = next(
        row
        for row in report["programs"]
        if row["merchant_id"] == "flaconi"
    )
    assert flaconi["activation_state"] == (
        "approved_credentials_pending"
    )
    assert flaconi["live_routing_allowed"] is False
    assert flaconi["next_action"] == "verify_credentials"
