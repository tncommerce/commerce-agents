"""Image acquisition can become human-reviewable, never silently approvable."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from scripts.prepare_dufynd_catalog_photo_wave import prepare_photo_wave

NOW = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)
PID = "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"
SKU = "924719"
GTIN = "3770010614630"
# This address is a synthetic test fixture, NOT an observed Awin feed URL.
FIXTURE_PHOTO = "https://www.topparfuemerie.de/media/catalog/product/test-fixture.jpg"


def gaps() -> dict:
    return {
        "status": "RIGHTS_SOURCE_ACQUISITION_PENDING_NO_AUTO_APPROVAL",
        "items": [
            {
                "product_id": PID,
                "source_state": "NO_EXACT_APPROVED_PHOTO",
                "brand": "Essential Parfums",
                "name": "Bois Impérial",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
            },
            {
                "product_id": "SC-XERJOFF-NAXOS-100",
                "source_state": "NO_EXACT_APPROVED_PHOTO",
                "name": "Naxos",
            },
        ],
    }


def mappings() -> dict:
    return {
        "mappings": [
            {
                "product_id": PID,
                "merchant": "top-parfuemerie",
                "merchant_product_id": SKU,
                "gtin": GTIN,
                "mapping_status": "verified_current_variant",
                "verified_at": "2026-09-22",
            },
        ],
    }


def extracted() -> dict:
    return {
        "status": "review_only_not_live",
        "provider": "awin-top-parfuemerie-de",
        "candidates": [
            {
                "product_id": PID,
                "merchant": "top-parfuemerie",
                "merchant_id": "top-parfuemerie",
                "merchant_product_id": SKU,
                "network": "Awin",
                "data_source": "awin-product-data-feed-preflight",
                "review_status": "pending_review",
                "proposed_image_status": "approved_feed_image",
                "offer_id": "123",
                "image_url": FIXTURE_PHOTO,
            }
        ],
    }


def metadata() -> dict:
    return {
        "source": "awin_product_feed_list",
        "advertiser_id": "31081",
        "feed_id": "91379",
        "checked_at": "2026-10-11T17:15:00+00:00",
        "joined": True,
        "downloaded": True,
    }


def rights() -> dict:
    return {
        "entries": [
            {
                "rights_basis_id": "awin_top_parfuemerie_feed_materials_20260928",
                "merchant_id": "top-parfuemerie",
                "network": "Awin",
                "advertiser_id": "31081",
                "program_status": "approved",
                "rights_status": "verified_for_publisher_service",
                "checked_at": "2026-09-28",
            }
        ]
    }


def build(
    *,
    missing=None,
    product_mappings=None,
    feed=None,
    feed_meta=None,
    registry=None,
    now=NOW,
):
    return prepare_photo_wave(
        gaps() if missing is None else missing,
        mappings() if product_mappings is None else product_mappings,
        extracted() if feed is None else feed,
        metadata() if feed_meta is None else feed_meta,
        rights() if registry is None else registry,
        now=now,
    )


def test_exact_current_feed_source_only_enters_human_review() -> None:
    packet = build()
    assert packet["status"] == "REVIEW_ONLY_NOT_LIVE"
    assert packet["review_ready_count"] == 1
    assert packet["hold_count"] == 1
    assert packet["automatic_image_approval_allowed"] is False
    assert packet["automatic_offer_activation_allowed"] is False
    assert packet["automatic_publication_allowed"] is False
    row = packet["items"][0]
    assert row["status"] == "SOURCE_IMAGE_REVIEW_REQUIRED"
    assert row["source_image_url"] == FIXTURE_PHOTO
    assert row["approved_image"] is False
    assert row["publish_go"] is False
    assert row["offer_activation_go"] is False
    assert "human_exact_variant_visual_match" in row["remaining_gates"]
    assert packet["items"][1]["blockers"] == ["current_exact_merchant_sku_mapping_missing"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("advertiser_id", "11672"),
        ("feed_id", "00000"),
        ("joined", False),
        ("downloaded", False),
        ("source", "merchant_product_page"),
    ],
)
def test_wrong_feed_provenance_never_mints_review_asset(field, value) -> None:
    data = metadata()
    data[field] = value
    with pytest.raises(ValueError):
        build(feed_meta=data)


def test_stale_or_future_feed_is_rejected() -> None:
    with pytest.raises(ValueError, match="feed_too_old_or_from_future"):
        build(now=NOW + timedelta(days=8))
    with pytest.raises(ValueError, match="feed_too_old_or_from_future"):
        build(now=NOW - timedelta(hours=1))


def test_program_rights_gate_stays_independent() -> None:
    records = rights()
    records["entries"][0]["program_status"] = "pending"
    with pytest.raises(ValueError):
        build(registry=records)


def test_duplicate_or_missing_official_feed_rows_stay_on_hold() -> None:
    feed = extracted()
    feed["candidates"].append(deepcopy(feed["candidates"][0]))
    packet = build(feed=feed)
    assert packet["review_ready_count"] == 0
    assert "ambiguous_current_feed_image_rows" in packet["items"][0]["blockers"]
    feed["candidates"] = []
    packet = build(feed=feed)
    assert "current_official_feed_image_row_missing" in packet["items"][0]["blockers"]


@pytest.mark.parametrize(
    "url",
    [
        "https://merchant-example.net/bois.jpg",
        "https://www.topparfuemerie.de/image/bois.jpg",
        "https://www.topparfuemerie.de/media/catalog/product/a.jpg?api_key=secret",
        "http://www.topparfuemerie.de/media/catalog/product/a.jpg",
    ],
)
def test_off_site_or_secret_image_url_never_becomes_review_candidate(url) -> None:
    feed = extracted()
    feed["candidates"][0]["image_url"] = url
    packet = build(feed=feed)
    assert packet["review_ready_count"] == 0
    assert "feed_image_url_not_public_or_official" in packet["items"][0]["blockers"]
    assert "source_image_url" not in packet["items"][0]


def test_conflicting_gtin_stays_hold_even_when_sku_matches() -> None:
    feed = extracted()
    feed["candidates"][0]["ean"] = "0000000000000"
    packet = build(feed=feed)
    assert packet["review_ready_count"] == 0
    assert "feed_identity_conflicts_with_gtin" in packet["items"][0]["blockers"]


def test_ambiguous_or_unverified_merchant_mapping_blocks_image_review() -> None:
    records = mappings()
    records["mappings"][0]["mapping_status"] = "unverified"
    packet = build(product_mappings=records)
    assert "independent_exact_variant_evidence_required" in packet["items"][0]["blockers"]
    records["mappings"][0]["mapping_status"] = "verified_current_variant"
    records["mappings"].append(deepcopy(records["mappings"][0]))
    packet = build(product_mappings=records)
    assert "ambiguous_merchant_sku_mapping" in packet["items"][0]["blockers"]


def test_non_review_extractor_payload_fails_closed() -> None:
    feed = extracted()
    feed["status"] = "approved"
    with pytest.raises(ValueError, match="review_only"):
        build(feed=feed)


def test_already_registered_or_duplicate_public_gap_is_rejected() -> None:
    data = gaps()
    data["items"][0]["source_state"] = "APPROVED_ORIGINAL"
    with pytest.raises(ValueError):
        build(missing=data)
    data = gaps()
    data["items"].append(deepcopy(data["items"][0]))
    with pytest.raises(ValueError):
        build(missing=data)
