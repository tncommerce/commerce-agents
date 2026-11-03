"""Open-licensed Commons photos are only private leads until exact variant approval."""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST = Path("examples/retail/data/dufynd_commons_original_photo_leads_20261101.json")


def test_commons_photos_have_real_named_creators_and_source_license() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["status"] == "PRIVATE_ORIGINAL_PHOTO_CANDIDATES_VARIANT_UNVERIFIED"
    rows = manifest["products"]
    assert {row["product_id"] for row in rows} == {
        "SC-PRADA-PARADOXE-EDP-90",
        "SC-YSL-Y-EDP-100",
    }
    assert sum(len(row["candidates"]) for row in rows) == 3
    for row in rows:
        source = row["source_verified_only"]
        assert source["license"] == "CC BY-SA 4.0"
        assert source["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
        assert source["creator"].strip()
        assert source["exact_variant_visible"] is False
        assert row["public_path"].startswith("/duft/")
        for candidate in row["candidates"]:
            assert candidate["file_page"].startswith("https://commons.wikimedia.org/wiki/File:")
            assert len(candidate["source_file_sha1"]) == 40
            assert candidate["source_file_size_bytes"] > 1_000_000
            assert candidate["byte_sha256"] is None
            assert candidate["exact_size_evidence"] == "unverified"


def test_no_asset_promotion_or_affiliate_action_from_commons_leads() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    gates = data["gates"]
    assert gates["current_original_bytes_downloaded"] is False
    assert gates["asset_sha256_verified"] is False
    assert gates["file_visual_variant_verified"] is False
    assert gates["public_product_image_activation"] is False
    assert gates["merchant_offer_activation"] is False
    assert gates["no_auto_promotion"] is True
    for row in data["products"]:
        assert row["variant_approved"] is False
        assert row["rights_scope_final_approved"] is False
        assert row["publication_authorized"] is False
        assert all(candidate["public_activation"] is False for candidate in row["candidates"])
    # Existing approved public image records remain untouched; no image URLs,
    # downloadable binaries, editor-provided rights or affiliate fields here.
    assert "image_url" not in json.dumps(data)
    assert "affiliate_url" not in json.dumps(data)
