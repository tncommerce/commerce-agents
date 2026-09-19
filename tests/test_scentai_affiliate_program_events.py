from __future__ import annotations

import pytest

from scripts.validate_scentai_affiliate_program_events import (
    build_parity_report,
    derive_current_statuses,
)


def test_latest_sequence_is_authoritative_for_program_state() -> None:
    events = {
        "events": [
            {
                "sequence": 1,
                "event_id": "one",
                "network": "Awin",
                "merchant_id": "merchant",
                "status_after": "applied",
            },
            {
                "sequence": 2,
                "event_id": "two",
                "network": "Awin",
                "merchant_id": "merchant",
                "status_after": "approved",
            },
        ]
    }

    latest = derive_current_statuses(events)

    assert latest[("awin", "merchant")]["status_after"] == "approved"


def test_event_ledger_detects_registry_drift() -> None:
    events = {
        "events": [
            {
                "sequence": 1,
                "event_id": "one",
                "network": "Awin",
                "merchant_id": "merchant",
                "status_after": "approved",
            }
        ]
    }
    registry = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "merchant",
                "status": "applied",
            }
        ],
        "other_networks": [],
    }

    report = build_parity_report(events, registry)

    assert report["in_sync"] is False
    assert report["out_of_sync_count"] == 1


def test_event_ledger_rejects_duplicate_event_ids() -> None:
    events = {
        "events": [
            {
                "sequence": 1,
                "event_id": "same",
                "network": "Awin",
                "merchant_id": "one",
                "status_after": "applied",
            },
            {
                "sequence": 2,
                "event_id": "same",
                "network": "Awin",
                "merchant_id": "two",
                "status_after": "applied",
            },
        ]
    }

    with pytest.raises(ValueError, match="duplicate affiliate event_id"):
        derive_current_statuses(events)
