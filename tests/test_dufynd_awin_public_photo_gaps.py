from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from scripts.export_dufynd_awin_public_photo_gaps import build_discovery

SOURCE = b"new gap discovery source fixture"
SECRET = "DONT_EMIT_TEST_SECRET"


def context():
    gap = json.loads(
        Path("artifacts/dufynd-wave2-discovery-20261026/public-photo-gaps.json").read_text()
    )
    meta = {
        "advertiser_id": "31081",
        "feed_id": "91379",
        "joined": True,
        "downloaded": True,
        "download_sha256": hashlib.sha256(SOURCE).hexdigest(),
        "downloaded_bytes": len(SOURCE),
    }
    return gap, meta


def test_new_gaps_only_and_ambiguous_variants_remain_unapproved():
    gap, meta = context()
    rows = [
        {
            "merchant_product_id": "849413",
            "product_name": "Montblanc Explorer EdP Nat. Spray",
            "search_price": "68.95",
        },
        {
            "merchant_product_id": "849448",
            "product_name": "Montblanc Explorer Platinum EdP Nat. Spray",
        },
        {
            "merchant_product_id": "924719",
            "product_name": "Essential Parfums Bois Imperial EdP Nat. Spray",
        },
    ]
    result = build_discovery(rows, meta, SOURCE, SECRET, gap)
    assert {x["merchant_product_id"] for x in result["rows"]} == {
        "849413",
        "849448",
        "780879",
        "825869",
        "856448",
        "787670",
    }
    assert all(x["expected_gtin"] is None for x in result["rows"])
    assert all("size" in x["missing_fields"] for x in result["rows"] if "fields" in x)
    assert result["image_publication_allowed"] is False
    assert result["activation_allowed"] is False
    assert result["tracking_clicks_executed"] == 0
    assert len(result["scope"]) == 27 and result["existing_original_photos_excluded"] == 10


def test_duplicate_sku_and_secret_fields_stay_held():
    gap, meta = context()
    row = {"merchant_product_id": "815680", "product_name": "Prada L'Homme EdT Nat. Spray"}
    result = build_discovery([row, row], meta, SOURCE, SECRET, gap)
    assert (
        next(x for x in result["rows"] if x["merchant_product_id"] == "815680")["status"] == "HOLD"
    )
    result = build_discovery([{**row, "description": SECRET}], meta, SOURCE, SECRET, gap)
    assert next(x for x in result["rows"] if x["merchant_product_id"] == "815680")[
        "withheld_fields"
    ] == ["description"]
    assert SECRET not in json.dumps(result)


def test_source_binding_membership_and_scope_fail_closed():
    gap, meta = context()
    rows = [{"merchant_product_id": "836129", "product_name": "Xerjoff Naxos EdP Spray Gift Box"}]
    for change in ({"joined": False}, {"download_sha256": "bad"}, {"advertiser_id": "0"}):
        with pytest.raises(ValueError):
            build_discovery(rows, {**meta, **change}, SOURCE, SECRET, gap)
    with pytest.raises(ValueError, match="manifest"):
        build_discovery(rows, meta, SOURCE, SECRET, {**gap, "items": gap["items"][:-1]})


def test_unexpected_large_match_set_fails_without_partial_export():
    gap, meta = context()
    rows = [
        {"merchant_product_id": str(800000 + i), "product_name": "Creed Aventus EdP"}
        for i in range(25)
    ]
    with pytest.raises(ValueError, match="bound_exceeded"):
        build_discovery(rows, meta, SOURCE, SECRET, gap)
