from __future__ import annotations

import pytest

from scripts.prepare_scentai_catalog_feed_image_review import (
    prepare_catalog_review_candidates,
)


PRODUCT_ID = "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"
IMAGE_URL = "https://www.topparfuemerie.de/media/catalog/product/9/2/924719_3770010614630_051.png"


def _feed_metadata() -> dict:
    return {
        "source": "awin_product_feed_list",
        "advertiser_id": "31081",
        "feed_id": "91379",
        "joined": True,
        "downloaded": True,
        "checked_at": "2026-10-01T12:00:00+00:00",
        "last_imported": "2026-10-01 00:03:51",
        "download_host": "productdata.awin.com",
    }


def _rights_registry() -> dict:
    return {
        "entries": [
            {
                "network": "Awin",
                "merchant_id": "top-parfuemerie",
                "advertiser_id": "31081",
                "program_status": "approved",
                "rights_status": "verified_for_publisher_service",
                "rights_basis_id": "awin_top_parfuemerie_feed_materials_20260928",
                "checked_at": "2026-09-28",
            }
        ]
    }


def _mappings() -> dict:
    return {
        "mappings": [
            {
                "product_id": PRODUCT_ID,
                "merchant": "top-parfuemerie",
                "merchant_product_id": "924719",
                "ean": "3770010614630",
                "gtin": "3770010614630",
                "verified_at": "2026-09-22",
            }
        ]
    }


def _staging(image_status: str = "pending_approved_feed_or_manufacturer_image") -> dict:
    return {
        "products": [
            {
                "product_id": PRODUCT_ID,
                "candidate_id": "ESSENTIAL-PARFUMS-BOIS-IMPERIAL",
                "brand": "Essential Parfums",
                "name": "Bois Impérial",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "media": {
                    "image_status": image_status,
                    "image_url": None,
                },
            }
        ]
    }


def _candidates(merchant_product_id: str = "924719") -> dict:
    return {
        "status": "review_only_not_live",
        "candidates": [
            {
                "product_id": PRODUCT_ID,
                "merchant": "top-parfuemerie",
                "merchant_id": "top-parfuemerie",
                "merchant_product_id": merchant_product_id,
                "offer_id": "38332629354",
                "image_url": IMAGE_URL,
                "network": "Awin",
                "data_source": "awin-product-data-feed-preflight",
                "last_updated_at": "2026-10-01 00:03:51",
                "review_status": "pending_review",
                "proposed_image_status": "approved_feed_image",
            }
        ],
    }


def test_catalog_review_prepares_exact_mapped_candidate_without_auto_approval() -> None:
    packet = prepare_catalog_review_candidates(
        _candidates(),
        _feed_metadata(),
        _staging(),
        _rights_registry(),
        _mappings(),
    )

    assert packet["status"] == "review_only_not_live"
    assert packet["automatic_approval_allowed"] is False
    assert packet["approval_action_class"] == "approval_required"
    assert packet["mapped_product_count"] == 1
    assert packet["pending_review_count"] == 1

    row = packet["candidates"][0]
    assert row["product_id"] == PRODUCT_ID
    assert row["merchant_product_id"] == "924719"
    assert row["gtin"] == "3770010614630"
    assert row["image_url"] == IMAGE_URL
    assert row["exact_variant_verified"] is True
    assert row["identity_basis"] == "canonical_merchant_product_id_mapping"
    assert row["review_status"] == "pending_review"
    assert row["proposed_image_status"] == "approved_feed_image"
    assert row["rights_status"] == "verified_for_publisher_service"
    assert row["next_action"] == "human_visual_review"


def test_catalog_review_rejects_merchant_product_identity_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match=f"candidate_merchant_product_mismatch:{PRODUCT_ID}",
    ):
        prepare_catalog_review_candidates(
            _candidates(merchant_product_id="wrong"),
            _feed_metadata(),
            _staging(),
            _rights_registry(),
            _mappings(),
        )


def test_catalog_review_skips_products_with_existing_approved_image() -> None:
    packet = prepare_catalog_review_candidates(
        _candidates(),
        _feed_metadata(),
        _staging(image_status="approved_feed_image"),
        _rights_registry(),
        _mappings(),
    )

    assert packet["pending_review_count"] == 0
    assert packet["candidates"] == []
    assert packet["skipped_already_approved_product_ids"] == [PRODUCT_ID]
