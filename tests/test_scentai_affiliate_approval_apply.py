from __future__ import annotations

from scripts.apply_scentai_affiliate_approval_intake import (
    apply_intake,
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


def events() -> dict:
    return {
        "version": 1,
        "events": [],
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
            "reference_note": "Approval observed.",
        },
        "capabilities": {},
        "integration_metadata": {
            "credential_storage": "external_secret_store_only",
            "provider_config_ready": False,
            "real_feed_sample_available": False,
        },
    }


def test_apply_intake_updates_registry_and_appends_event() -> None:
    result = apply_intake(
        intake(),
        registry(),
        events(),
    )

    assert result["valid"] is True
    assert result["changed"] is True
    assert result["live_routing_allowed"] is False
    assert result["registry"]["applications"][0]["status"] == "approved"
    assert len(result["events"]["events"]) == 1
    assert result["events"]["events"][0]["status_after"] == "approved"
    assert result["validation"]["activation_state_after_event"] == (
        "approved_credentials_pending"
    )


def test_apply_intake_is_idempotent_on_same_event() -> None:
    first = apply_intake(
        intake(),
        registry(),
        events(),
    )

    second = apply_intake(
        intake(),
        first["registry"],
        first["events"],
    )

    assert second["valid"] is True
    assert second["changed"] is False
    assert second["idempotent_noop"] is True
    assert len(second["events"]["events"]) == 1
    assert second["live_routing_allowed"] is False


def test_invalid_intake_does_not_mutate_state() -> None:
    payload = intake()
    payload["evidence"]["api_key"] = "forbidden"

    original_registry = registry()
    original_events = events()

    result = apply_intake(
        payload,
        original_registry,
        original_events,
    )

    assert result["valid"] is False
    assert result["changed"] is False
    assert result["registry"] == original_registry
    assert result["events"] == original_events
    assert result["live_routing_allowed"] is False
