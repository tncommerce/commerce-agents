from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.promote_scentai_catalog import (
    load_release_manifest,
    promotion_plan,
)

DATA_DIR = Path("examples/retail/data")
MANIFEST = DATA_DIR / "scentai_release_batch_01.json"
NOW = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_release_batch_01_is_a_guarded_five_product_manifest() -> None:
    product_ids = load_release_manifest(MANIFEST)
    staging = load_json(DATA_DIR / "scentai_catalog_staging.json")
    staged_by_id = {
        product["product_id"]: product
        for product in staging["products"]
    }

    assert len(product_ids) == 5
    assert len(set(product_ids)) == 5

    for product_id in product_ids:
        assert product_id in staged_by_id
        product = staged_by_id[product_id]
        assert product["community"]["provisional"] is False
        assert product["commerce"]["merchant_coverage_count"] >= 2


def test_release_batch_01_dry_run_stays_blocked_until_real_assets_exist() -> None:
    product_ids = load_release_manifest(MANIFEST)

    plan = promotion_plan(
        load_json(DATA_DIR / "scentai_catalog_staging.json"),
        load_json(DATA_DIR / "catalog.json"),
        load_json(DATA_DIR / "merchant_offers.json"),
        product_ids=product_ids,
        batch=None,
        limit=len(product_ids),
        now=NOW,
        max_offer_age_hours=72.0,
        allow_provisional=False,
    )

    assert plan["selected_count"] == 5
    assert plan["ready_count"] == 0
    assert plan["blocked_count"] == 5

    for row in plan["rows"]:
        assert "missing_approved_image" in row["blockers"]
        assert "missing_current_affiliate_offer" in row["blockers"]
        assert "provisional_community_data" not in row["blockers"]


@pytest.mark.parametrize(
    "product_ids",
    [
        ["SC-ONE"] * 5,
        ["SC-ONE", "SC-TWO", "SC-THREE", "SC-FOUR"],
        [f"SC-{index}" for index in range(11)],
    ],
)
def test_release_manifest_rejects_unsafe_shapes(tmp_path, product_ids: list[str]) -> None:
    path = tmp_path / "release.json"
    path.write_text(
        json.dumps({"product_ids": product_ids}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_release_manifest(path)
