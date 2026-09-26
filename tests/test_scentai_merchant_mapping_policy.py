"""Keep merchant mapping readiness independent from affiliate approval."""

from __future__ import annotations

from scripts.build_scentai_merchant_mapping_work_queue import build_queue


def _staging_product(product_id: str, *, provisional: bool = False) -> dict:
    return {
        "product_id": product_id,
        "candidate_id": product_id.replace("SC-", ""),
        "brand": "Brand",
        "name": "Product",
        "batch": 1,
        "commerce": {"merchant_coverage_count": 1},
        "community": {"provisional": provisional},
    }


def test_resolved_mapping_is_ready_even_when_affiliate_is_pending() -> None:
    staging = {"products": [_staging_product("SC-TEST-EDP-100")]}
    mappings = {
        "mappings": [
            {
                "product_id": "SC-TEST-EDP-100",
                "merchant": "douglas",
                "merchant_product_id": "12345",
                "ean": "1234567890123",
                "gtin": "1234567890123",
            }
        ]
    }
    affiliates = {
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

    queue = build_queue(
        staging,
        mappings,
        affiliates,
        generated_at="2026-09-26T12:00:00+00:00",
    )
    item = queue["items"][0]

    assert item["state"] == "mapping_data_ready"
    assert item["next_action"] == "maintain_mapping_and_verify_purchase_destination"
    assert "affiliate_program_not_approved" not in item["blockers"]
    assert item["merchants"][0]["affiliate_activation_state"] == "pending_program_approval"

    assert queue["summary"]["mapping_ready_products"] == 1
    assert queue["summary"]["products_with_approved_affiliate_program"] == 0


def test_affiliate_approval_remains_separate_metadata() -> None:
    staging = {"products": [_staging_product("SC-TEST-EDP-100")]}
    mappings = {
        "mappings": [
            {
                "product_id": "SC-TEST-EDP-100",
                "merchant": "perfumetrader",
                "merchant_product_id": "98765",
                "ean": "1234567890123",
            }
        ]
    }
    affiliates = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "perfumetrader",
                "program": "Perfumetrader DE",
                "status": "approved",
            }
        ],
        "other_networks": [],
    }

    queue = build_queue(
        staging,
        mappings,
        affiliates,
        generated_at="2026-09-26T12:00:00+00:00",
    )
    item = queue["items"][0]

    assert item["state"] == "mapping_data_ready"
    assert item["blockers"] == []
    assert item["merchants"][0]["affiliate_activation_state"] == "approved"
    assert queue["summary"]["mapping_ready_products"] == 1
    assert queue["summary"]["products_with_approved_affiliate_program"] == 1


def test_unresolved_mapping_still_requires_identity_work() -> None:
    staging = {
        "products": [
            _staging_product(
                "SC-TEST-EDP-100",
                provisional=True,
            )
        ]
    }
    mappings = {"mappings": []}
    affiliates = {
        "network": "Awin",
        "applications": [],
        "other_networks": [],
    }

    queue = build_queue(
        staging,
        mappings,
        affiliates,
        generated_at="2026-09-26T12:00:00+00:00",
    )
    item = queue["items"][0]

    assert item["state"] == "mapping_required"
    assert item["next_action"] == "verify_exact_merchant_product_identity"
    assert "no_resolved_merchant_mapping" in item["blockers"]
    assert "community_performance_still_provisional" in item["blockers"]
