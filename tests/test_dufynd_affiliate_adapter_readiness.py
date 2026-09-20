from __future__ import annotations

from scripts.check_dufynd_affiliate_adapter_readiness import (
    evaluate_adapter_readiness,
)


def provider_config(
    *,
    merchant_id: str = "douglas",
    network: str = "Awin",
) -> dict:
    return {
        "provider_name": "awin-douglas",
        "field_map": {
            "offer_id": "offer",
            "merchant_product_id": "sku",
            "price": "price",
            "in_stock": "stock",
            "product_url": "url",
            "affiliate_url": "tracked_url",
            "last_updated_at": "updated",
            "image_url": "image",
        },
        "constants": {
            "merchant": merchant_id,
            "merchant_id": merchant_id,
            "merchant_name": "Douglas",
            "currency": "EUR",
            "network": network,
            "data_source": "approved_feed",
        },
    }


PROGRAMS = {
    "network": "Awin",
    "applications": [
        {
            "program": "Douglas_DE",
            "status": "applied",
            "merchant_id": "douglas",
        }
    ],
    "other_networks": [
        {
            "network": "CJ Affiliate",
            "program": "Notino",
            "status": "approved",
            "merchant_id": "notino",
        }
    ],
}

PARTNERS = {
    "partners": [
        {
            "merchant_id": "douglas",
            "status": "pending_affiliate_link",
        },
        {
            "merchant_id": "notino",
            "status": "pending_affiliate_link",
        },
    ]
}


def test_pending_application_waits_without_blocking_contract() -> None:
    report = evaluate_adapter_readiness(
        provider_config(),
        PROGRAMS,
        PARTNERS,
    )

    assert report["state"] == "WAITING_APPROVAL"
    assert report["next_action"] == "await_affiliate_program_approval"


def test_approved_application_is_ready_for_feed_preflight() -> None:
    config = provider_config(
        merchant_id="notino",
        network="CJ Affiliate",
    )
    config["constants"]["merchant_name"] = "Notino"

    report = evaluate_adapter_readiness(
        config,
        PROGRAMS,
        PARTNERS,
    )

    assert report["state"] == "READY_FOR_FEED_PREFLIGHT"
    assert report["next_action"] == "run_real_feed_preflight"


def test_network_mismatch_blocks_adapter() -> None:
    report = evaluate_adapter_readiness(
        provider_config(network="CJ Affiliate"),
        PROGRAMS,
        PARTNERS,
    )

    assert report["state"] == "BLOCKED"
    assert any(issue.startswith("affiliate_network_mismatch:") for issue in report["issues"])
