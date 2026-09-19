from __future__ import annotations

from scripts.apply_scentai_affiliate_approval_intake import (
    apply_intake,
)
from scripts.build_scentai_release_feed_activation_queue import (
    build_feed_activation_queue,
)
from scripts.validate_scentai_affiliate_program_events import (
    build_parity_report,
)


def test_douglas_approval_flow_unlocks_feed_validation_not_live() -> None:
    registry = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "douglas",
                "program": "Douglas_DE",
                "status": "applied",
            }
        ],
        "other_networks": [],
    }
    events = {
        "version": 1,
        "events": [],
    }
    intake = {
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
            "reference_note": "Synthetic approval test.",
        },
        "capabilities": {
            "product_feed_available": True,
        },
        "integration_metadata": {
            "credential_storage": "external_secret_store_only",
            "provider_config_ready": False,
            "real_feed_sample_available": False,
        },
    }

    applied = apply_intake(
        intake,
        registry,
        events,
    )

    assert applied["valid"] is True
    assert applied["registry"]["applications"][0]["status"] == "approved"
    assert applied["live_routing_allowed"] is False
    assert applied["validation"]["activation_state_after_event"] == (
        "approved_credentials_pending"
    )

    parity = build_parity_report(
        applied["events"],
        applied["registry"],
    )

    assert parity["in_sync"] is True
    assert parity["out_of_sync_count"] == 0

    release = {
        "release_id": "SCENTAI-RELEASE-TEST",
        "product_ids": [
            "SC-A",
            "SC-B",
        ],
    }
    mappings = {
        "mappings": [
            {
                "product_id": "SC-A",
                "merchant": "douglas",
                "merchant_product_id": "sku-a",
            },
            {
                "product_id": "SC-B",
                "merchant": "douglas",
                "ean": "1234567890123",
            },
        ]
    }

    queue = build_feed_activation_queue(
        release,
        mappings,
        applied["registry"],
        generated_at="2026-09-19T10:01:00+00:00",
    )

    douglas = queue["programs"][0]

    assert douglas["merchant_id"] == "douglas"
    assert douglas["program_approved"] is True
    assert douglas["full_release_mapping_coverage"] is True
    assert douglas["state"] == (
        "approved_mapping_ready_feed_sample_pending"
    )
    assert douglas["next_action"] == (
        "obtain_real_feed_sample_and_create_provider_config"
    )
    assert douglas["live_routing_allowed"] is False

    assert queue["summary"]["feed_validation_path_available"] is True
    assert queue["summary"]["live_activation_ready"] is False
