"""Reuse Awin's strict source reviewer; never treat a feed hit as an image GO."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from scripts.report_dufynd_unpublished_photo_sources import (
    build_unpublished_source_queue,
)

NOW = datetime(2026, 10, 24, 10, tzinfo=UTC)
URL = "https://www.topparfuemerie.de/media/catalog/product/a/b/000100.png"
PRODUCT_ID = "SC-EXAMPLE-SCENT-EDP-100"


def inputs(count: int = 25):
    staged = {
        "products": [
            {
                "product_id": PRODUCT_ID if i == 5 else f"SC-NEW-{i:02}",
                "brand": "Example",
                "name": "Scent" if i == 5 else f"Fragrance {i}",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
            }
            for i in range(count)
        ]
    }
    public = {"products": staged["products"][:5]}
    mapped = {
        "mappings": [
            {
                "product_id": PRODUCT_ID,
                "merchant": "top-parfuemerie",
                "merchant_product_id": "100100",
                "gtin": "4000000000009",
                "mapping_status": "verified_current_variant",
            },
            {
                "product_id": PRODUCT_ID,
                "merchant": "notino",
                "merchant_product_id": "NOTINO-100",
                "gtin": "4000000000009",
            },
        ]
    }
    offers = {
        "offers": [
            {
                "product_id": PRODUCT_ID,
                "affiliate_url": "https://cj.example.invalid/historical-only",
            }
        ]
    }
    return staged, public, [], mapped, offers, {"partners": []}


def run(*args, **kwargs):
    return build_unpublished_source_queue(
        *args, now=NOW, batch_size=20, **kwargs
    )


def official_metadata():
    return {
        "source": "awin_product_feed_list",
        "advertiser_id": "31081",
        "feed_id": "91379",
        "joined": True,
        "downloaded": True,
        "checked_at": NOW.isoformat(),
        "last_imported": NOW.isoformat(),
    }


def rights():
    return {
        "entries": [
            {
                "merchant_id": "top-parfuemerie",
                "advertiser_id": "31081",
                "rights_basis_id": "awin_top_parfuemerie_feed_materials_20260928",
                "program_status": "approved",
                "rights_status": "verified_for_publisher_service",
                "asset_scope": "unaltered_advertiser_materials_from_official_awin_product_feed",
            }
        ]
    }


def feed():
    return [
        {
            "merchant_product_id": "100100",
            "product_name": "Example Scent EDP 100 ml",
            "merchant_image_url": URL,
            "gtin": "4000000000009",
        }
    ]


def test_exact_20_unpublished_items_no_double_work_no_net_calls():
    report = run(*inputs())
    assert report["review_size"] == 20
    assert report["already_public_staging_excluded"] == 5
    assert report["unpublished_staging_backlog"] == 20
    assert report["source_file_checked"] is False
    assert report["official_awin_photo_review"] is None
    assert report["publications"] == report["network_requests"] == report["database_writes"] == 0
    assert report["original_image_approvals_granted"] == 0
    public = {row["product_id"] for row in inputs()[1]["products"]}
    assert all(row["product_id"] not in public for row in report["items"])
    assert sum(row["priority"] == "EXISTING_TRACKED_ROUTE_IMAGE_HOLD" for row in report["items"]) == 1


def test_source_review_uses_existing_strict_licensed_feed_validator():
    report = run(
        *inputs(), feed_rows=feed(), feed_metadata=official_metadata(), rights=rights()
    )
    review = report["official_awin_photo_review"]
    assert review["status"] == "REVIEW_ONLY_NOT_LIVE"
    assert review["products_reviewed"] == 20
    assert review["products_with_leads"] == 1
    assert review["approved_new_images"] == 0
    record = next(x for x in review["items"] if x["product_id"] == PRODUCT_ID)
    assert record["status"] == "REVIEW_LEADS_FOUND"
    assert record["candidates"][0]["merchant_product_id"] == "100100"
    assert record["candidates"][0]["feed_explicit_size_match"] is True
    assert record["candidates"][0]["registered"] is False
    assert record["candidates"][0]["published"] is False
    assert report["original_image_approvals_granted"] == 0
    assert report["approved_merchant_offers_created"] == 0
    assert report["affiliate_links_generated"] == 0
    assert report["publications"] == 0


@pytest.mark.parametrize("invalid_source", ["wrong_advertiser", "not_joined", "stale", "wrong_rights"])
def test_wrong_source_or_rights_cannot_create_even_a_candidate(invalid_source: str):
    meta = official_metadata()
    license_data = rights()
    if invalid_source == "wrong_advertiser":
        meta["advertiser_id"] = "999"
    elif invalid_source == "not_joined":
        meta["joined"] = False
    elif invalid_source == "stale":
        meta["checked_at"] = (NOW - timedelta(days=8)).isoformat()
    else:
        license_data["entries"][0]["program_status"] = "pending"
    with pytest.raises(ValueError):
        run(*inputs(), feed_rows=feed(), feed_metadata=meta, rights=license_data)


def test_same_sku_with_conflicting_current_feed_rows_is_not_released():
    report = run(
        *inputs(),
        feed_rows=feed() + feed(),
        feed_metadata=official_metadata(),
        rights=rights(),
    )
    review = report["official_awin_photo_review"]
    match = next(x for x in review["items"] if x["product_id"] == PRODUCT_ID)
    assert match["duplicate_feed_sku_hold"] is True
    assert match["candidates"] == []
    assert report["original_image_approvals_granted"] == 0


def test_invalid_or_partial_feed_input_is_never_silently_accepted():
    with pytest.raises(ValueError, match="together"):
        run(*inputs(), feed_rows=feed())
    with pytest.raises(ValueError, match="together"):
        run(*inputs(), feed_metadata=official_metadata())
    with pytest.raises(ValueError, match="rights_registry"):
        run(*inputs(), feed_rows=feed(), feed_metadata=official_metadata())


def test_unpublished_with_approved_image_is_not_reacquired():
    staging, public, photos, mappings, offers, partners = inputs()
    photos.append(
        {
            "product_id": PRODUCT_ID,
            "volume_ml": 100,
            "rights_basis_id": "previous_verified_grant",
            "url": "https://www.example.invalid/preapproved.png",
        }
    )
    report = run(staging, public, photos, mappings, offers, partners)
    match = next(x for x in report["items"] if x["product_id"] == PRODUCT_ID)
    assert match["original_photo_gate"] == "REUSE_ALREADY_APPROVED_ORIGINAL"
    assert match["owner_visual_review_required"] is False
    assert match["image_license_granted_by_this_queue"] is False


def test_current_repo_contains_no_auto_approvable_20_item_photo_batch():
    import json

    from scripts.report_dufynd_unpublished_photo_sources import (
        MAPPINGS,
        OFFERS,
        PARTNERS,
        PHOTOS,
        PUBLIC,
        STAGING,
    )

    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    report = build_unpublished_source_queue(
        read(STAGING),
        read(PUBLIC),
        read(PHOTOS),
        read(MAPPINGS),
        read(OFFERS),
        read(PARTNERS),
        now=NOW,
        batch_size=20,
    )
    assert report["review_size"] == 20
    assert report["original_image_approvals_granted"] == 0
    assert report["approved_merchant_offers_created"] == 0
    assert all(row["public_catalog_release_authorized"] is False for row in report["items"])
