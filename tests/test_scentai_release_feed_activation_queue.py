from __future__ import annotations

from pathlib import Path

from scripts.build_scentai_release_feed_activation_queue import (
    build_feed_activation_queue,
    load_json,
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


def test_variant_audit_prevents_wrong_variant_mapping_for_approved_partial_program() -> None:
    audit = {
        "merchant_id": "merchant-two",
        "release_id": "SCENTAI-RELEASE-TEST",
        "checked_at": "2026-09-21",
        "scope": "public merchant evidence",
        "rows": [
            {
                "product_id": "SC-B",
                "audit_state": "exact_variant_unverified_alternative_only",
                "mapping_eligible": False,
            }
        ],
    }

    queue = build_feed_activation_queue(
        release(),
        mappings(),
        affiliates("approved"),
        generated_at="2026-09-21T20:30:00+00:00",
        variant_audit=audit,
    )

    merchant = next(row for row in queue["programs"] if row["merchant_id"] == "merchant-two")

    assert merchant["mapped_release_product_count"] == 1
    assert merchant["feed_state"] == "await_exact_variant_feed_or_product_evidence"
    assert merchant["next_action"] == "await_exact_variant_feed_or_product_evidence"
    assert merchant["variant_audit"]["missing_mapping_product_ids"] == ["SC-B"]
    assert merchant["variant_audit"]["audited_missing_mapping_product_ids"] == ["SC-B"]
    assert merchant["variant_audit"]["missing_mapping_audit_complete"] is True
    assert merchant["live_routing_allowed"] is False


def test_incomplete_variant_audit_does_not_hide_mapping_work() -> None:
    audit = {
        "merchant_id": "merchant-two",
        "release_id": "SCENTAI-RELEASE-TEST",
        "checked_at": "2026-09-21",
        "rows": [],
    }

    queue = build_feed_activation_queue(
        release(),
        mappings(),
        affiliates("approved"),
        generated_at="2026-09-21T20:30:00+00:00",
        variant_audit=audit,
    )

    merchant = next(row for row in queue["programs"] if row["merchant_id"] == "merchant-two")

    assert merchant["feed_state"] == "await_remaining_mapping_resolution"
    assert merchant["next_action"] == "resolve_remaining_release_mappings_before_feed_validation"
    assert merchant["variant_audit"]["missing_mapping_audit_complete"] is False


def test_verified_but_unmapped_exact_variant_stays_mapping_work() -> None:
    audit = {
        "merchant_id": "merchant-two",
        "release_id": "SCENTAI-RELEASE-TEST",
        "checked_at": "2026-09-21",
        "rows": [
            {
                "product_id": "SC-B",
                "audit_state": "exact_variant_verified",
                "mapping_eligible": True,
            }
        ],
    }

    queue = build_feed_activation_queue(
        release(),
        mappings(),
        affiliates("approved"),
        generated_at="2026-09-21T20:35:00+00:00",
        variant_audit=audit,
    )

    merchant = next(row for row in queue["programs"] if row["merchant_id"] == "merchant-two")

    assert merchant["feed_state"] == "await_remaining_mapping_resolution"
    assert merchant["next_action"] == "resolve_remaining_release_mappings_before_feed_validation"
    assert merchant["variant_audit"]["verified_unmapped_product_ids"] == ["SC-B"]
    assert merchant["variant_audit"]["missing_mapping_audit_complete"] is False


def test_current_release01_perfumetrader_variant_audit_matches_repo_sources() -> None:
    data_dir = Path("examples/retail/data")
    queue = build_feed_activation_queue(
        load_json(data_dir / "scentai_release_batch_01.json"),
        load_json(data_dir / "merchant_product_mappings.json"),
        load_json(data_dir / "scentai_affiliate_programs.json"),
        generated_at="2026-09-21T20:40:00+00:00",
        variant_audit=load_json(data_dir / "dufynd_perfumetrader_release01_variant_audit.json"),
    )

    merchant = next(row for row in queue["programs"] if row["merchant_id"] == "perfumetrader")
    committed = load_json(data_dir / "scentai_release_01_feed_activation_queue.json")
    committed_merchant = next(
        row for row in committed["programs"] if row["merchant_id"] == "perfumetrader"
    )

    assert committed["source_fingerprint_sha256"] == queue["source_fingerprint_sha256"]
    assert committed_merchant["feed_state"] == merchant["feed_state"]
    assert committed_merchant["next_action"] == merchant["next_action"]
    assert merchant["program_approved"] is True
    assert merchant["mapped_release_product_count"] == 1
    assert merchant["full_release_mapping_coverage"] is False
    assert merchant["feed_state"] == "await_exact_variant_feed_or_product_evidence"
    assert merchant["next_action"] == "await_exact_variant_feed_or_product_evidence"
    assert merchant["variant_audit"]["audited_release_product_count"] == 5
    assert merchant["variant_audit"]["exact_variant_verified_product_count"] == 1
    assert merchant["variant_audit"]["missing_mapping_audit_complete"] is True
    assert merchant["live_routing_allowed"] is False
