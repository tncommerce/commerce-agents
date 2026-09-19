from __future__ import annotations

import json
from pathlib import Path

from scripts.build_scentai_catalog_staging import merchant_coverage_count

DATA_DIR = Path("examples/retail/data")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_default_merchant_coverage_uses_promotion_queue() -> None:
    verified = {
        "merchant_snapshot": {
            "merchant_a": "available",
        }
    }
    queue_row = {
        "merchant_coverage_count": 3,
    }

    assert merchant_coverage_count(verified, queue_row) == 3


def test_snapshot_authority_counts_only_explicit_available_status() -> None:
    verified = {
        "merchant_coverage_source": "verification_snapshot",
        "merchant_snapshot": {
            "current_store": "available",
            "legacy_store": "sale_ended_not_valid_for_2026_coverage",
            "brand_page": "manufacturer_teaser_not_retail_available",
        },
    }
    queue_row = {
        "merchant_coverage_count": 3,
    }

    assert merchant_coverage_count(verified, queue_row) == 1


def test_fleur_du_male_2026_has_no_ambiguous_legacy_coverage() -> None:
    verification = load_json(
        DATA_DIR / "scentai_catalog_batch2_verification.json"
    )
    queue = load_json(
        DATA_DIR / "scentai_catalog_promotion_queue.json"
    )

    verified = next(
        product
        for product in verification["products"]
        if product["candidate_id"] == "JPG-FLEUR-DU-MALE-2026"
    )
    queue_row = next(
        product
        for product in queue["candidates"]
        if product["candidate_id"] == "JPG-FLEUR-DU-MALE-2026"
    )

    assert verified["merchant_coverage_source"] == "verification_snapshot"
    assert merchant_coverage_count(verified, queue_row) == 0
    assert queue_row["merchant_coverage_count"] == 0
    assert "verified_current_merchant_pending" in queue_row["blockers"]
