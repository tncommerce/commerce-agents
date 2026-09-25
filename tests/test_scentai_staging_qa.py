# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.build_scentai_catalog_staging import build_staging_payload
from scripts.qa_scentai_staging import (
    TYPO_CASES,
    data_quality_issues,
    exact_name_query,
    load_staging,
    run_qa,
)


def test_staging_data_quality_has_no_structural_issues() -> None:
    staging = load_staging()

    assert staging["product_count"] == len(staging["products"])
    assert staging["product_count"] >= 30
    assert data_quality_issues(staging) == []


@pytest.mark.asyncio
async def test_all_staged_products_pass_pre_live_recommendation_qa() -> None:
    result = await run_qa()

    staging = load_staging()

    assert result["product_count"] == len(staging["products"])
    assert result["checks"]["exact_name_search"]["tested"] == len(staging["products"])
    assert result["checks"]["typo_search"]["tested"] == len(TYPO_CASES)
    assert result["checks"]["budget_and_offer_qa"]["passed"] is None
    assert result["issues"] == []
    assert result["passed"] is True


def test_short_fragrance_names_use_brand_context() -> None:
    assert exact_name_query({"brand": "Yves Saint Laurent", "name": "Y"}) == (
        "Yves Saint Laurent Y"
    )
    assert exact_name_query({"brand": "Prada", "name": "Paradoxe"}) == "Paradoxe"


def test_first_controlled_expansion_wave_is_staging_only() -> None:
    staging = load_staging()
    live = json.loads(Path("examples/retail/data/catalog.json").read_text(encoding="utf-8"))

    expected_batch4 = {
        "SC-CAROLINA-HERRERA-GOOD-GIRL-EDP-80",
        "SC-CHANEL-COCO-MADEMOISELLE-EDP-100",
        "SC-CALVIN-KLEIN-EUPHORIA-EDP-100",
        "SC-RABANNE-1-MILLION-EDT-100",
        "SC-YSL-Y-EDP-100",
    }
    staged_batch4 = {row["product_id"] for row in staging["products"] if row.get("batch") == 4}
    live_ids = {
        row["product_id"]
        for row in live["products"]
        if row.get("category") == "fragrance"
        and row.get("in_stock") is not False
        and str(row.get("product_id") or "").startswith("SC-")
    }

    intake = json.loads(
        Path("examples/retail/data/dufynd_catalog_staging_intake.json").read_text(encoding="utf-8")
    )
    manifest_ids = set(intake["waves"][0]["selected_product_ids"])

    assert staged_batch4 == expected_batch4
    assert manifest_ids == expected_batch4
    assert intake["waves"][0]["live_publication_authorized"] is False
    assert staged_batch4.isdisjoint(live_ids)

    for row in staging["products"]:
        if row["product_id"] not in expected_batch4:
            continue
        assert row["media"]["image_url"] is None
        assert row["validation"]["catalog_ready"] is False
        assert "approved_product_image_pending" in row["validation"]["blockers"]
        assert "verified_affiliate_offer_pending" in row["validation"]["blockers"]
        assert row["research"]["source_wave_id"] == "DUFYND-CATALOG-EXPANSION-NEXT-10"



def test_second_controlled_expansion_wave_is_staging_only() -> None:
    staging = load_staging()
    live = json.loads(Path("examples/retail/data/catalog.json").read_text(encoding="utf-8"))
    intake = json.loads(
        Path("examples/retail/data/dufynd_catalog_staging_intake.json").read_text(encoding="utf-8")
    )
    wave = json.loads(
        Path("examples/retail/data/dufynd_catalog_expansion_next10.json").read_text(
            encoding="utf-8"
        )
    )

    expected_batch5 = {
        "SC-VALENTINO-DONNA-BORN-IN-ROMA-EDP-100",
        "SC-CHLOE-NOMADE-EDP-75",
        "SC-VERSACE-EROS-EDP-100",
        "SC-ARMANI-ACQUA-DI-GIO-PROFONDO-PARFUM-100",
        "SC-JPG-LE-MALE-ELIXIR-PARFUM-125",
    }
    staged_batch5 = {row["product_id"] for row in staging["products"] if row.get("batch") == 5}
    live_ids = {
        row["product_id"]
        for row in live["products"]
        if row.get("category") == "fragrance"
        and row.get("in_stock") is not False
        and str(row.get("product_id") or "").startswith("SC-")
    }
    manifest_batch5 = next(row for row in intake["waves"] if row["staging_batch"] == 5)
    manifest_ids = set(manifest_batch5["selected_product_ids"])

    assert staged_batch5 == expected_batch5
    assert manifest_ids == expected_batch5
    assert manifest_batch5["live_publication_authorized"] is False
    assert staged_batch5.isdisjoint(live_ids)

    for row in staging["products"]:
        if row["product_id"] not in expected_batch5:
            continue
        assert row["media"]["image_url"] is None
        assert row["validation"]["catalog_ready"] is False
        assert "approved_product_image_pending" in row["validation"]["blockers"]
        assert "verified_affiliate_offer_pending" in row["validation"]["blockers"]
        assert row["research"]["source_wave_id"] == "DUFYND-CATALOG-EXPANSION-NEXT-10"

    jpg = next(
        row
        for row in wave["candidates"]
        if row["product_id"] == "SC-JPG-LE-MALE-ELIXIR-PARFUM-125"
    )
    assert "merchant_concentration_attribute_review_pending" not in jpg["validation"]["blockers"]
    assert jpg["content_context"]["existing_content_state"] == "user_confirmed_final_viral_short"
    assert jpg["content_context"]["publish_authorized"] is False



def test_checked_in_staging_matches_reproducible_builder() -> None:
    assert load_staging() == build_staging_payload()
