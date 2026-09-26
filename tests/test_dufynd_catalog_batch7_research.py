from __future__ import annotations

import json
from pathlib import Path


def test_batch7_stays_research_only_until_sources_are_verified() -> None:
    data = Path("examples/retail/data")
    wave = json.loads((data / "dufynd_catalog_expansion_batch7_research.json").read_text())
    intake = json.loads((data / "dufynd_catalog_staging_intake.json").read_text())
    staging = json.loads((data / "scentai_catalog_staging.json").read_text())
    live = json.loads((data / "catalog.json").read_text())
    offers = json.loads((data / "merchant_offers.json").read_text())

    candidates = wave["candidates"]
    ids = [row["product_id"] for row in candidates]
    existing_ids = {row["product_id"] for row in [*staging["products"], *live["products"]]}

    assert len(candidates) == wave["max_products"] == 5
    assert len(set(ids)) == 5
    assert set(ids).isdisjoint(existing_ids)
    assert wave["live_publication_authorized"] is False
    assert wave["status"] == "research_only_not_enabled_for_staging"
    assert all(entry["wave_id"] != wave["wave_id"] for entry in intake["waves"])
    assert set(ids).isdisjoint({offer["product_id"] for offer in offers["offers"]})
    assert sum(bool(candidate["research_merchant_evidence"]) for candidate in candidates) == 5
    for candidate in candidates:
        assert candidate["manufacturer_source_url"].startswith("https://")

        product_data = candidate["product_data"]
        assert product_data["scent_family"]
        assert product_data["source_kind"] == "official_brand"
        assert product_data["source_confidence"] == "high"
        assert product_data["source_url"] == candidate["manufacturer_source_url"]
        assert product_data.get("key_notes") or product_data.get("notes")

        merchant_evidence = candidate["research_merchant_evidence"]
        assert merchant_evidence
        for evidence in merchant_evidence:
            assert evidence["url"].startswith("https://")
            assert evidence["variant"] == (
                f"{candidate['volume_ml']} ml {candidate['concentration']}"
            )
            assert evidence["merchant_product_id"]
            assert evidence["research_state"] == "research_only_not_imported"

        evidence_urls = {evidence["url"] for evidence in candidate["evidence"]}
        assert candidate["manufacturer_source_url"] in evidence_urls
        assert candidate["community"]["source_url"] in evidence_urls
        assert all(evidence["url"] in evidence_urls for evidence in merchant_evidence)

        assert "verified_purchase_destination_pending" in candidate["validation"]["blockers"]
        assert "approved_product_image_pending" in candidate["validation"]["blockers"]
        assert "canonical_gtin_feed_match_pending" in candidate["validation"]["blockers"]
        assert "current_verified_purchase_destination_pending" not in candidate["validation"]["blockers"]
        assert "merchant_variant_mapping_pending" not in candidate["validation"]["blockers"]
        assert "community_data_pending" not in candidate["validation"]["blockers"]

        community = candidate["community"]
        assert community["source"] == "Parfumo"
        assert community["source_url"].startswith("https://www.parfumo.com/")
        assert community["rating_10"] > 0
        assert community["rating_count"] > 0
        assert community["longevity_10"] > 0
        assert community["projection_10"] > 0
        assert len(community["main_accords"]) >= 5

        assert candidate["identifiers"]["canonical_gtin"] is None
        assert candidate["identifiers"]["status"] == "pending_canonical_gtin_verification"
        assert candidate["identifiers"]["observations"]

        assert candidate["media"]["image_url"] is None
        assert candidate["media"]["image_status"] == "pending_approved_feed_or_manufacturer_image"
        assert candidate["media"]["required_variant"] == {
            "concentration": candidate["concentration"],
            "volume_ml": candidate["volume_ml"],
        }
        assert candidate["validation"]["catalog_ready"] is False


def test_batch7_small_community_sample_stays_provisional() -> None:
    wave = json.loads(
        Path("examples/retail/data/dufynd_catalog_expansion_batch7_research.json").read_text()
    )
    provisional = {
        row["product_id"] for row in wave["candidates"] if row["community"]["provisional"]
    }

    assert provisional == {"SC-AFNAN-9-PM-POUR-FEMME-EDP-100"}
    afnan = next(
        row for row in wave["candidates"] if row["product_id"] == "SC-AFNAN-9-PM-POUR-FEMME-EDP-100"
    )
    assert afnan["community"]["rating_count"] == 26


def test_batch7_normalized_schema_matches_staging_builder_contract() -> None:
    wave = json.loads(
        Path("examples/retail/data/dufynd_catalog_expansion_batch7_research.json").read_text()
    )

    for candidate in wave["candidates"]:
        assert candidate["evidence"]
        assert candidate["product_data"]
        assert candidate["research_merchant_evidence"]
        assert candidate["research_state"] == (
            "official_profile_community_and_merchant_evidence_verified"
        )
