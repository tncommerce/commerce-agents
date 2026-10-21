"""Offline-only regression: no Awin credentials, network, public media or clicks."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image
from scripts.check_dufynd_awin_original_photo_bytes import (
    PRODUCT_ID,
    RIGHTS_BASIS,
    SKU,
    SOURCE_URL,
    check_original_photo_bytes,
)


NOW = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)


def fixture():
    img = Image.new("RGB", (90, 180), (255, 255, 255))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    metadata = {
        "source": "awin_product_feed_list",
        "advertiser_id": "31081",
        "feed_id": "91379",
        "membership_status": "active",
        "joined": True,
        "downloaded": True,
        "checked_at": "2026-10-21T17:58:16+00:00",
    }
    readiness = {
        "provider": "awin-top-parfuemerie-de",
        "products": [{
            "product_id": PRODUCT_ID,
            "mapped": True,
            "feed_image_candidate_count": 1,
            "mapped_offer_count": 1,
            "offer_evidence": [{
                "merchant_product_id": SKU,
                "merchant_id": "top-parfuemerie",
                "tracking_verified": False,
                "activation_allowed": False,
            }],
        }],
    }
    registry = [{
        "product_id": PRODUCT_ID,
        "url": SOURCE_URL,
        "volume_ml": 90,
        "rights_basis_id": RIGHTS_BASIS,
    }]
    return buffer.getvalue(), metadata, readiness, registry


def call(image=None, metadata=None, readiness=None, registry=None, now=NOW):
    source = fixture()
    return check_original_photo_bytes(
        image if image is not None else source[0],
        deepcopy(metadata if metadata is not None else source[1]),
        deepcopy(readiness if readiness is not None else source[2]),
        deepcopy(registry if registry is not None else source[3]),
        now=now,
    )


def test_valid_file_produces_only_private_fingerprint():
    report = call()
    assert report["status"] == "PRIVATE_BYTE_FINGERPRINT_ONLY"
    assert len(report["source_image_sha256"]) == 64
    assert (report["image_width"], report["image_height"]) == (90, 180)
    assert report["merchant_product_id"] == SKU
    assert report["registered_source_url"] == SOURCE_URL
    assert report["official_awin_feed_checked_at"].startswith("2026-10-21")
    assert report["current_feed_candidate_count"] == 1
    for gate in ("image_origin_attested", "byte_match_to_owner_approved_source",
                 "exact_current_feed_image_url_verified", "public_image_approval",
                 "public_rehosting_authorized", "offer_activation_authorized"):
        assert report[gate] is False
    assert report["new_spend_usd"] == 0


def test_unrelated_valid_png_has_different_hash_and_is_never_autoapproved():
    old = call()
    b = BytesIO()
    Image.new("RGB", (90, 180), (1, 2, 3)).save(b, format="PNG")
    new = call(image=b.getvalue())
    assert new["source_image_sha256"] != old["source_image_sha256"]
    assert new["public_image_approval"] is False
    assert new["image_origin_attested"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("advertiser_id", "11672"),
        ("feed_id", "wrong"),
        ("membership_status", "suspended"),
        ("joined", False),
        ("downloaded", False),
        ("source", "merchant_scrape"),
    ],
)
def test_unverified_awin_provenance_is_rejected(field, value):
    image, meta, ready, registry = fixture()
    meta[field] = value
    with pytest.raises(ValueError, match="official_awin_membership_not_verified"):
        call(image=image, metadata=meta, readiness=ready, registry=registry)


def test_expired_or_future_feed_is_rejected():
    _, meta, _, _ = fixture()
    meta["checked_at"] = (NOW - timedelta(days=8)).isoformat()
    with pytest.raises(ValueError, match="feed_not_current"):
        call(metadata=meta)
    meta["checked_at"] = (NOW + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="feed_not_current"):
        call(metadata=meta)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("merchant_product_id", "787670"),
        ("merchant_id", "notino"),
    ],
)
def test_exact_merchant_sku_is_required(field, value):
    _, meta, ready, reg = fixture()
    ready["products"][0]["offer_evidence"][0][field] = value
    with pytest.raises(ValueError, match="libre_merchant_sku_mismatch"):
        call(metadata=meta, readiness=ready, registry=reg)


def test_duplicate_or_missing_feed_image_candidates_are_blocked():
    _, _, ready, _ = fixture()
    ready["products"][0]["feed_image_candidate_count"] = 2
    with pytest.raises(ValueError, match="libre_feed_candidate_not_unique"):
        call(readiness=ready)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", "https://www.topparfuemerie.de/other.png"),
        ("volume_ml", 50),
        ("rights_basis_id", "unverified"),
    ],
)
def test_registry_identity_rights_and_variant_cannot_drift(field, value):
    _, _, _, registry = fixture()
    registry[0][field] = value
    with pytest.raises(ValueError, match="approved_image_identity_or_rights_mismatch"):
        call(registry=registry)


@pytest.mark.parametrize("source", [
    b"not-an-image",
    b"\x89PNG\r\n\x1a\n" + b"A" * 64,
    b"\x89PNG\r\n\x1a\n" + b"A" * (5 * 1024 * 1024 + 1),
])
def test_invalid_corrupt_oversized_image_data_cannot_pass(source):
    with pytest.raises(ValueError, match="original_format_not_png|photo_png_integrity_failed|photo_bytes_absent_or_out_of_bounds"):
        call(image=source)


def test_runner_never_activates_public_assets_or_modifies_inputs():
    original = fixture()
    image, metadata, readiness, registry = original
    call(image=image, metadata=metadata, readiness=readiness, registry=registry)
    assert (image, metadata, readiness, registry) == original
