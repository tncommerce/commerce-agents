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


def test_staging_qa_rejects_variant_and_provisional_gate_drift() -> None:
    row = load_staging()["products"][-1].copy()
    row["volume_ml"] = 75
    row["community"] = {**row["community"], "provisional": True}
    row["validation"] = {**row["validation"], "catalog_ready": True}

    assert data_quality_issues({"products": [row]}) == [
        f"{row['product_id']}:volume_product_id_mismatch",
        f"{row['product_id']}:provisional_gate_mismatch",
        f"{row['product_id']}:provisional_marked_ready",
    ]


def test_live_staging_overlap_requires_explicit_promotion_provenance() -> None:
    staged_ids = {row["product_id"] for row in load_staging()["products"]}
    live = json.loads(Path("examples/retail/data/catalog.json").read_text(encoding="utf-8"))
    live_rows = {
        row["product_id"]: row for row in live["products"] if row.get("category") == "fragrance"
    }

    overlapping_ids = staged_ids & set(live_rows)
    assert overlapping_ids

    for product_id in overlapping_ids:
        attributes = live_rows[product_id].get("attributes") or {}
        assert attributes.get("promotion_source") == "scentai_catalog_staging", product_id


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


def test_preapproved_images_clear_only_the_image_gate_not_purchase_or_release() -> None:
    staging = load_staging()
    products = {row["product_id"]: row for row in staging["products"]}
    approved = {
        "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100": "approved_licensed_image",
        "SC-PDM-DELINA-EDP-75": "approved_feed_image",
        "SC-YSL-LIBRE-EDP-90": "approved_feed_image",
        "SC-YSL-BLACK-OPIUM-EDP-90": "approved_feed_image",
    }
    for product_id, status in approved.items():
        row = products[product_id]
        assert row["media"]["image_status"] == status
        assert row["media"]["image_reviewed_at"]
        assert row["media"]["image_rights_basis_id"]
        assert row["validation"]["blockers"] == ["verified_purchase_destination_pending"]
        assert row["commerce"]["live_offer_status"] == "pending_current_purchase_destination"
        assert row["validation"]["catalog_ready"] is False
    goddess = products["SC-BURBERRY-GODDESS-EDP-100"]
    assert "approved_product_image_pending" in goddess["validation"]["blockers"]
    assert goddess["validation"]["catalog_ready"] is False


def test_missing_approval_evidence_does_not_clear_image_gate() -> None:
    from scripts.build_scentai_catalog_staging import reconcile_approved_image_gates

    row = {
        "media": {"image_url": "https://example.com/a.jpg", "image_status": "approved_feed_image"},
        "commerce": {"live_offer_status": "pending_current_purchase_destination"},
        "validation": {"catalog_ready": False, "blockers": ["approved_product_image_pending"]},
    }
    reconcile_approved_image_gates(row)
    assert row["validation"]["blockers"] == ["approved_product_image_pending"]
    assert row["validation"]["catalog_ready"] is False


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
    one_million_id = "SC-RABANNE-1-MILLION-EDT-100"
    assert one_million_id in live_ids
    assert (expected_batch4 - {one_million_id}).isdisjoint(live_ids)

    for row in staging["products"]:
        if row["product_id"] not in expected_batch4:
            continue
        if row["product_id"] == one_million_id:
            assert row["media"]["image_url"] == (
                "/products/rabanne-1-million-edt-100-user-contentmaster.webp"
            )
            assert row["media"]["image_status"] == "approved_licensed_image"
            assert row["validation"]["catalog_ready"] is True
            assert row["validation"]["blockers"] == []
            assert row["commerce"]["live_offer_status"] == "verified_current_purchase_destination"
        else:
            assert row["media"]["image_url"] is None
            assert row["validation"]["catalog_ready"] is False
            assert "approved_product_image_pending" in row["validation"]["blockers"]
            assert "verified_purchase_destination_pending" in row["validation"]["blockers"]
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
        assert "verified_purchase_destination_pending" in row["validation"]["blockers"]
        assert row["research"]["source_wave_id"] == "DUFYND-CATALOG-EXPANSION-NEXT-10"

    jpg = next(
        row for row in wave["candidates"] if row["product_id"] == "SC-JPG-LE-MALE-ELIXIR-PARFUM-125"
    )
    assert "merchant_concentration_attribute_review_pending" not in jpg["validation"]["blockers"]
    assert jpg["content_context"]["existing_content_state"] == "user_confirmed_final_viral_short"
    assert jpg["content_context"]["publish_authorized"] is False


def test_third_controlled_expansion_wave_is_staging_only() -> None:
    staging = load_staging()
    live = json.loads(Path("examples/retail/data/catalog.json").read_text(encoding="utf-8"))
    intake = json.loads(
        Path("examples/retail/data/dufynd_catalog_staging_intake.json").read_text(encoding="utf-8")
    )
    wave = json.loads(
        Path("examples/retail/data/dufynd_catalog_expansion_wave2_batch6.json").read_text(
            encoding="utf-8"
        )
    )

    expected_batch6 = {
        "SC-TOM-FORD-OUD-WOOD-EDP-100",
        "SC-PRADA-PARADIGME-EDP-100",
        "SC-ARMANI-SI-EDP-100",
        "SC-LATTAFA-KHAMRAH-EDP-100",
        "SC-GUCCI-FLORA-GORGEOUS-GARDENIA-EDP-100",
    }
    staged_batch6 = {row["product_id"] for row in staging["products"] if row.get("batch") == 6}
    live_ids = {
        row["product_id"]
        for row in live["products"]
        if row.get("category") == "fragrance"
        and row.get("in_stock") is not False
        and str(row.get("product_id") or "").startswith("SC-")
    }
    manifest_batch6 = next(row for row in intake["waves"] if row["staging_batch"] == 6)
    manifest_ids = set(manifest_batch6["selected_product_ids"])

    assert wave["wave_id"] == "DUFYND-CATALOG-EXPANSION-WAVE2-BATCH6"
    assert staged_batch6 == expected_batch6
    assert manifest_ids == expected_batch6
    assert manifest_batch6["live_publication_authorized"] is False
    assert staged_batch6.isdisjoint(live_ids)

    for row in staging["products"]:
        if row["product_id"] not in expected_batch6:
            continue
        assert row["media"]["image_url"] is None
        assert row["validation"]["catalog_ready"] is False
        assert "approved_product_image_pending" in row["validation"]["blockers"]
        assert "verified_purchase_destination_pending" in row["validation"]["blockers"]
        assert row["research"]["source_wave_id"] == "DUFYND-CATALOG-EXPANSION-WAVE2-BATCH6"


def test_fourth_controlled_expansion_wave_is_staging_only() -> None:
    staging = load_staging()
    live = json.loads(Path("examples/retail/data/catalog.json").read_text(encoding="utf-8"))
    intake = json.loads(
        Path("examples/retail/data/dufynd_catalog_staging_intake.json").read_text(encoding="utf-8")
    )
    wave = json.loads(
        Path("examples/retail/data/dufynd_catalog_expansion_batch7_research.json").read_text(
            encoding="utf-8"
        )
    )

    expected_batch7 = {
        "SC-MUGLER-ALIEN-EDP-90",
        "SC-MFK-BACCARAT-ROUGE-540-EDP-70",
        "SC-AFNAN-9-PM-POUR-FEMME-EDP-100",
        "SC-MAISON-MARGIELA-BY-THE-FIREPLACE-EDT-100",
        "SC-DIOR-JADORE-EDP-100",
    }
    staged_batch7 = {row["product_id"] for row in staging["products"] if row.get("batch") == 7}
    live_ids = {
        row["product_id"]
        for row in live["products"]
        if row.get("category") == "fragrance"
        and row.get("in_stock") is not False
        and str(row.get("product_id") or "").startswith("SC-")
    }
    manifest_batch7 = next(row for row in intake["waves"] if row["staging_batch"] == 7)
    manifest_ids = set(manifest_batch7["selected_product_ids"])

    assert wave["wave_id"] == "DUFYND-CATALOG-EXPANSION-BATCH7-RESEARCH"
    assert wave["status"] == "enabled_for_isolated_staging"
    assert staged_batch7 == expected_batch7
    assert manifest_ids == expected_batch7
    assert manifest_batch7["live_publication_authorized"] is False
    assert staged_batch7.isdisjoint(live_ids)

    for row in staging["products"]:
        if row["product_id"] not in expected_batch7:
            continue
        assert row["media"]["image_url"] is None
        assert row["validation"]["catalog_ready"] is False
        assert "approved_product_image_pending" in row["validation"]["blockers"]
        assert "verified_purchase_destination_pending" in row["validation"]["blockers"]
        assert row["research"]["source_wave_id"] == "DUFYND-CATALOG-EXPANSION-BATCH7-RESEARCH"

    afnan = next(
        row
        for row in staging["products"]
        if row["product_id"] == "SC-AFNAN-9-PM-POUR-FEMME-EDP-100"
    )
    assert afnan["community"]["provisional"] is True
    assert "provisional_community_data" in afnan["validation"]["blockers"]


def test_checked_in_staging_matches_reproducible_builder() -> None:
    assert load_staging() == build_staging_payload()
