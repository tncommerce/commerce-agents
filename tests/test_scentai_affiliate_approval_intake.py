from __future__ import annotations

from scripts.validate_scentai_affiliate_approval_intake import (
    validate_intake,
)


def registry(status: str = "applied") -> dict:
    return {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "douglas",
                "program": "Douglas_DE",
                "status": status,
            }
        ],
        "other_networks": [],
    }


def intake() -> dict:
    return {
        "version": 1,
        "intake_type": "affiliate_program_decision",
        "merchant_id": "douglas",
        "network": "Awin",
        "program": "Douglas_DE",
        "observed_status": "approved",
        "observed_at": "2026-09-19T10:00:00Z",
        "evidence": {
            "source_type": "network_dashboard",
            "external_program_id": "123",
            "reference_note": "Approval visible in dashboard.",
        },
        "capabilities": {
            "deeplink_available": True,
            "product_feed_available": True,
            "tracked_product_url_available": True,
            "product_image_in_feed": True,
            "feed_format": "csv",
        },
        "integration_metadata": {
            "credential_storage": "external_secret_store_only",
            "provider_config_ready": False,
            "real_feed_sample_available": False,
        },
    }


def test_valid_approval_intake_never_enables_live_routing() -> None:
    report = validate_intake(intake(), registry("applied"))

    assert report["valid"] is True
    assert report["current_registry_status"] == "applied"
    assert report["observed_status"] == "approved"
    assert report["activation_state_after_event"] == ("approved_credentials_pending")
    assert report["live_routing_allowed_after_event"] is False
    assert report["live_activation_action_class"] == "approval_required"


def test_intake_rejects_secret_bearing_fields() -> None:
    payload = intake()
    payload["evidence"]["token"] = "must-not-be-here"

    report = validate_intake(payload, registry())

    assert report["valid"] is False
    assert any("secret-bearing field is forbidden" in issue for issue in report["issues"])


def test_intake_requires_exact_registered_program_name() -> None:
    payload = intake()
    payload["program"] = "Douglas"

    report = validate_intake(payload, registry())

    assert report["valid"] is False
    assert any("program name does not exactly match" in issue for issue in report["issues"])


def test_rejected_program_cannot_be_reapproved_by_intake() -> None:
    report = validate_intake(intake(), registry("rejected"))

    assert report["valid"] is False
    assert report["live_routing_allowed_after_event"] is False
    assert any("observed status is not valid" in issue for issue in report["issues"])
