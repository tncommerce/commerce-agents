from __future__ import annotations

import pytest
from scripts.prepare_scentai_feed_image_review import prepare_review_candidates


def staging() -> dict:
    return {
        "products": [
            {
                "product_id": "SC-PDM-DELINA-EDP-75",
                "candidate_id": "PDM-DELINA-EDP",
                "brand": "Parfums de Marly",
                "name": "Delina",
                "concentration": "Eau de Parfum",
                "volume_ml": 75,
                "media": {"image_url": None, "image_status": "licensed_source_required"},
            },
            {
                "product_id": "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100",
                "candidate_id": "LANCOME-LA-VIE-EST-BELLE-EDP",
                "brand": "Lancôme",
                "name": "La Vie est Belle",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "media": {
                    "image_url": "https://licensed.example/lancome.jpg",
                    "image_status": "approved_licensed_image",
                },
            },
        ]
    }


def release() -> dict:
    return {
        "release_id": "SCENTAI-RELEASE-01",
        "product_ids": [
            "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100",
            "SC-PDM-DELINA-EDP-75",
        ],
    }


def candidates() -> dict:
    return {
        "status": "review_only_not_live",
        "candidates": [
            {
                "product_id": "SC-PDM-DELINA-EDP-75",
                "merchant": "top-parfuemerie",
                "merchant_id": "top-parfuemerie",
                "merchant_product_id": "825869",
                "offer_id": "123",
                "image_url": "https://images.example/delina.jpg",
                "network": "Awin",
                "data_source": "awin-product-data-feed-preflight",
                "last_updated_at": "2026-09-28",
                "review_status": "pending_review",
                "proposed_image_status": "approved_feed_image",
            },
            {
                "product_id": "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100",
                "merchant": "top-parfuemerie",
                "merchant_id": "top-parfuemerie",
                "merchant_product_id": "780879",
                "offer_id": "456",
                "image_url": "https://images.example/lancome.jpg",
                "network": "Awin",
                "data_source": "awin-product-data-feed-preflight",
                "review_status": "pending_review",
                "proposed_image_status": "approved_feed_image",
            },
        ],
    }


def feed_metadata() -> dict:
    return {
        "source": "awin_product_feed_list",
        "advertiser_id": "31081",
        "feed_id": "91379",
        "joined": True,
        "downloaded": True,
        "checked_at": "2026-09-28T12:00:00+00:00",
        "last_imported": "2026-09-28 11:30:00",
        "download_host": "datafeed.api.productserve.com",
    }


def rights_registry() -> dict:
    return {
        "entries": [
            {
                "rights_basis_id": "awin_top_parfuemerie_feed_materials_20260928",
                "network": "Awin",
                "merchant_id": "top-parfuemerie",
                "advertiser_id": "31081",
                "program_status": "approved",
                "rights_status": "verified_for_publisher_service",
                "checked_at": "2026-09-28",
            }
        ]
    }


def test_current_feed_candidate_becomes_pending_review_only() -> None:
    packet = prepare_review_candidates(
        candidates(),
        feed_metadata(),
        staging(),
        release(),
        rights_registry(),
    )

    assert packet["status"] == "review_only_not_live"
    assert packet["pending_review_count"] == 1
    assert packet["automatic_approval_allowed"] is False
    assert packet["approval_action_class"] == "approval_required"
    assert packet["skipped_already_approved_product_ids"] == [
        "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100"
    ]

    row = packet["candidates"][0]
    assert row["product_id"] == "SC-PDM-DELINA-EDP-75"
    assert row["merchant_product_id"] == "825869"
    assert row["data_source"] == "approved-affiliate-feed"
    assert row["original_data_source"] == "awin-product-data-feed-preflight"
    assert row["review_status"] == "pending_review"
    assert row["exact_variant_verified"] is True
    assert row["feed_id"] == "91379"
    assert row["rights_basis_id"] == "awin_top_parfuemerie_feed_materials_20260928"


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("advertiser_id", "999", "current_feed_advertiser_mismatch"),
        ("feed_id", "999", "current_feed_id_mismatch"),
        ("joined", False, "current_feed_program_not_joined"),
        ("downloaded", False, "current_feed_not_downloaded"),
    ],
)
def test_current_feed_provenance_is_mandatory(field: str, value: object, error: str) -> None:
    metadata = feed_metadata()
    metadata[field] = value

    with pytest.raises(ValueError, match=error):
        prepare_review_candidates(
            candidates(),
            metadata,
            staging(),
            release(),
            rights_registry(),
        )


def test_unverified_rights_never_promote_candidate_to_review_ready_source() -> None:
    rights = rights_registry()
    rights["entries"][0]["rights_status"] = "pending"

    with pytest.raises(ValueError, match="top_parfuemerie_rights_not_verified"):
        prepare_review_candidates(
            candidates(),
            feed_metadata(),
            staging(),
            release(),
            rights,
        )
