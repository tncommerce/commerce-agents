from __future__ import annotations

from scripts.build_scentai_release_feed_activation_queue import (
    build_feed_activation_queue,
)


def release() -> dict:
    return {
        "release_id": "SCENTAI-RELEASE-TEST",
        "product_ids": [
            "SC-A",
            "SC-B",
        ],
    }


def mappings() -> dict:
    return {
        "mappings": [
            {
                "product_id": "SC-A",
                "merchant": "merchant-one",
                "merchant_product_id": "a-1",
            },
            {
                "product_id": "SC-B",
                "merchant": "merchant-one",
                "ean": "1234567890123",
            },
            {
                "product_id": "SC-A",
                "merchant": "merchant-two",
                "merchant_product_id": "a-2",
            },
        ]
    }


def affiliates(status: str = "applied") -> dict:
    return {
        "network": "Awin",
        "applications": [
            {
                "program": "Merchant One",
                "status": status,
                "merchant_id": "merchant-one",
            },
            {
                "program": "Merchant Two",
                "status": "approved",
                "merchant_id": "merchant-two",
            },
        ],
        "other_networks": [],
    }


def test_full_mapping_does_not_bypass_program_approval() -> None:
    queue = build_feed_activation_queue(
        release(),
        mappings(),
        affiliates("applied"),
        generated_at="2026-09-19T10:00:00+00:00",
    )

    merchant = next(row for row in queue["programs"] if row["merchant_id"] == "merchant-one")

    assert merchant["full_release_mapping_coverage"] is True
    assert merchant["program_approved"] is False
    assert merchant["state"] == "program_pending_full_mapping_ready"
    assert merchant["live_routing_allowed"] is False
    assert queue["summary"]["feed_validation_path_available"] is False
    assert queue["summary"]["live_activation_ready"] is False


def test_approval_opens_feed_validation_not_live_routing() -> None:
    queue = build_feed_activation_queue(
        release(),
        mappings(),
        affiliates("approved"),
        generated_at="2026-09-19T10:00:00+00:00",
    )

    merchant = next(row for row in queue["programs"] if row["merchant_id"] == "merchant-one")

    assert merchant["state"] == ("approved_mapping_ready_feed_sample_pending")
    assert merchant["feed_state"] == ("await_real_feed_or_tracked_link_sample")
    assert merchant["live_routing_allowed"] is False
    assert queue["summary"]["feed_validation_path_available"] is True
    assert queue["summary"]["live_activation_ready"] is False


def test_partial_mapping_cannot_be_full_release_path() -> None:
    queue = build_feed_activation_queue(
        release(),
        mappings(),
        affiliates("approved"),
        generated_at="2026-09-19T10:00:00+00:00",
    )

    merchant = next(row for row in queue["programs"] if row["merchant_id"] == "merchant-two")

    assert merchant["mapped_release_product_count"] == 1
    assert merchant["full_release_mapping_coverage"] is False
    assert merchant["state"] == "approved_mapping_partial"
    assert merchant["live_routing_allowed"] is False
