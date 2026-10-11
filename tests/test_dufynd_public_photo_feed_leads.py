"""No image registration may be derived from a missing DUFYND photo-source lead."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from scripts.report_dufynd_public_photo_feed_leads import create_review, safe_feed_image

META = {
    "source": "awin_product_feed_list",
    "advertiser_id": "31081",
    "feed_id": "91379",
    "joined": True,
    "downloaded": True,
    "checked_at": "2026-10-11T18:00:00Z",
}
RIGHTS = {
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
GAP = {
    "status": "RIGHTS_SOURCE_ACQUISITION_PENDING_NO_AUTO_APPROVAL",
    "items": [
        {
            "product_id": "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
            "brand": "Essential Parfums",
            "name": "Bois Impérial",
            "concentration": "Eau de Parfum",
            "volume_ml": 100,
        },
        {
            "product_id": "SC-XERJOFF-NAXOS-100",
            "brand": "Xerjoff",
            "name": "Naxos",
            "concentration": "Eau de Parfum",
            "volume_ml": 100,
        },
        {
            "product_id": "SC-PDM-LAYTON-125",
            "brand": "Parfums de Marly",
            "name": "Layton",
            "concentration": "Eau de Parfum",
            "volume_ml": 125,
        },
    ],
}
MAPPINGS = {
    "mappings": [
        {
            "product_id": "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
            "merchant": "top-parfuemerie",
            "merchant_product_id": "924719",
            "gtin": "3770010614630",
        },
    ]
}
PHOTO_BOIS = "https://www.topparfuemerie.de/media/catalog/product/9/2/924719_3770010614630_051.png"
PHOTO_NAXOS = "https://www.topparfuemerie.de/media/catalog/product/9/8/989001_0000000000000_051.png"


def row(sku: str, name: str, url: str, **kwargs) -> dict:
    return {
        "merchant_product_id": sku,
        "product_name": name,
        "merchant_image_url": url,
        "aw_deep_link": "https://tracking.example.test/?apikey=DO_NOT_EXPOSE",
        "search_price": "99.99",
        "in_stock": "true",
        **kwargs,
    }


def run(rows: list[dict], **kwargs) -> dict:
    return create_review(
        kwargs.get("gap", GAP),
        kwargs.get("mappings", MAPPINGS),
        rows,
        kwargs.get("metadata", META),
        kwargs.get("rights", RIGHTS),
        now=kwargs.get("now", datetime(2026, 10, 11, 19, 0, tzinfo=UTC)),
    )


def test_mapped_sku_and_name_only_leads_are_both_manual_holds() -> None:
    result = run(
        [
            row("924719", "Essential Parfums Bois Imperial EDP 100 ml", PHOTO_BOIS),
            row("989001", "Xerjoff Naxos Eau de Parfum 100 ml", PHOTO_NAXOS),
            row("989002", "Xerjoff Naxos EDP 50 ml", PHOTO_NAXOS),
        ]
    )
    assert result["status"] == "REVIEW_ONLY_NOT_LIVE"
    assert result["products_reviewed"] == 3
    assert result["products_with_leads"] == 2
    assert result["total_review_candidates"] == 2
    rows = {r["product_id"]: r for r in result["items"]}
    assert (
        rows["SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"]["candidates"][0]["match_type"]
        == "mapped_sku_needs_feed_variant_review"
    )
    assert (
        rows["SC-XERJOFF-NAXOS-100"]["candidates"][0]["match_type"]
        == "name_lead_manual_sku_mapping_required"
    )
    assert not rows["SC-PDM-LAYTON-125"]["candidates"]
    assert result["approved_new_images"] == 0
    assert result["automated_registration_allowed"] is False
    assert result["product_offer_activation_allowed"] is False
    assert "DO_NOT_EXPOSE" not in str(result)
    assert "search_price" not in str(result)


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://www.topparfuemerie.de/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de/media/catalog/product/a/1/123.png?key=abc",
        "https://other-merchant.invalid/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de.evil.invalid/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de/media/catalog/product/../private.png",
        "https://www.topparfuemerie.de/media/catalog/product/a/1/123.png#fragment",
        "https://admin@www.topparfuemerie.de/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de:8080/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de:broken/media/catalog/product/a/1/123.png",
        "",
    ],
)
def test_only_public_merchant_image_url_allowed(bad_url: str) -> None:
    assert safe_feed_image(bad_url) is None


def test_invalid_source_or_rights_fail_closed() -> None:
    meta = deepcopy(META)
    meta["joined"] = False
    with pytest.raises(ValueError, match="official_awin"):
        run([], metadata=meta)
    rights = deepcopy(RIGHTS)
    rights["entries"][0]["program_status"] = "pending"
    with pytest.raises(ValueError, match="rights"):
        run([], rights=rights)
    with pytest.raises(ValueError, match="current_awin_feed_timestamp_required"):
        run([], now=datetime(2026, 10, 19, tzinfo=UTC))
    with pytest.raises(ValueError, match="current_awin_feed_timestamp_required"):
        run([], now=datetime(2026, 10, 10, tzinfo=UTC))
    gap = deepcopy(GAP)
    gap["status"] = "approved_for_release"
    with pytest.raises(ValueError, match="unapproved"):
        run([], gap=gap)


def test_duplicate_feed_sku_and_duplicate_targets_are_not_approved() -> None:
    rows = [
        row("924719", "Essential Parfums Bois Imperial EDP 100 ml", PHOTO_BOIS),
        row("924719", "Essential Parfums Bois Imperial EDP 100 ml", PHOTO_BOIS),
    ]
    output = run(rows)
    entry = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert entry["duplicate_pinned_feed_sku_hold"] is True
    assert entry["candidates"] == []
    gap = deepcopy(GAP)
    gap["items"].append(gap["items"][0])
    with pytest.raises(ValueError, match="duplicate"):
        run([], gap=gap)


def test_secret_bearing_non_feed_urls_and_wrong_concentration_are_excluded() -> None:
    rows = [
        row(
            "989001",
            "Xerjoff Naxos EDP 100 ml",
            "https://www.topparfuemerie.de/media/catalog/product/9/8/abc.png?token=secret",
        ),
        row("989002", "Xerjoff Naxos EDT 100 ml", PHOTO_NAXOS),
        row("989003", "Xerjoff Naxos EDP 125 ml", PHOTO_NAXOS),
    ]
    result = run(rows)
    assert result["total_review_candidates"] == 0


def test_mapped_sku_different_fragrance_name_is_a_hard_hold() -> None:
    output = run([row("924719", "Essential Parfums Fig Infusion EDP 100 ml", PHOTO_BOIS)])
    record = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["pinned_feed_identity_conflict_hold"] is True
    assert record["candidates"] == []
    assert output["approved_new_images"] == 0


def test_mapped_sku_conflicting_official_gtin_is_a_hard_hold() -> None:
    output = run(
        [
            row(
                "924719",
                "Essential Parfums Bois Imperial EDP 100 ml",
                PHOTO_BOIS,
                gtin="0000000000000",
            )
        ]
    )
    record = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["pinned_feed_identity_conflict_hold"] is True
    assert record["candidates"] == []


def test_mapped_sku_matching_gtin_only_enters_manual_review() -> None:
    output = run(
        [
            row(
                "924719",
                "Essential Parfums Bois Imperial EDP 100 ml",
                PHOTO_BOIS,
                gtin="3770010614630",
            )
        ]
    )
    record = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["pinned_feed_identity_conflict_hold"] is False
    assert record["candidates"][0]["status"] == "HUMAN_SOURCE_VARIANT_IMAGE_REVIEW_REQUIRED"
    assert record["candidates"][0]["registered"] is False
    assert record["candidates"][0]["published"] is False


def test_missing_volume_in_mapped_feed_title_cannot_claim_verified_size() -> None:
    output = run([row("924719", "Essential Parfums Bois Imperial EDP", PHOTO_BOIS)])
    record = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["candidates"][0]["feed_explicit_size_match"] is False
    assert record["candidates"][0]["status"] == "HUMAN_SOURCE_VARIANT_IMAGE_REVIEW_REQUIRED"
