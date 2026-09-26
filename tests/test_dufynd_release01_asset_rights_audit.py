from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
AUDIT_PATH = DATA_DIR / "dufynd_release01_asset_rights_audit.json"
RELEASE_PATH = DATA_DIR / "scentai_release_batch_01.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_release01_asset_rights_audit_matches_release_manifest() -> None:
    audit = load_json(AUDIT_PATH)
    release = load_json(RELEASE_PATH)

    audit_ids = [row["product_id"] for row in audit["products"]]
    assert audit["release_id"] == release["release_id"]
    assert audit_ids == release["product_ids"]


def test_release01_official_references_never_count_as_public_approval() -> None:
    audit = load_json(AUDIT_PATH)

    assert audit["policy"]["official_brand_product_pages_are_identity_reference_only"] is True
    assert audit["policy"]["public_catalog_use_requires_documented_commercial_rights"] is True
    assert audit["policy"]["affiliate_feed_assets_require_program_or_feed_rights"] is True
    assert audit["policy"]["manual_visual_approval_still_required"] is True

    for row in audit["products"]:
        assert row["exact_variant_verified"] is True
        assert row["current_source_type"] == "official_brand_reference_unlicensed"
        assert row["catalog_image_status"] == "reference_only"
        assert row["public_distribution_allowed"] is False
        assert row["final_composite_allowed"] is False
        assert not row["catalog_image_status"].startswith("approved_")
        assert (
            row["next_action"]
            == "await_licensed_partner_feed_image_or_written_rights_permission_or_owned_photography"
        )
        assert (
            row["feed_dependency"]
            == "licensed_partner_feed_or_written_permission_or_owned_photography"
        )
