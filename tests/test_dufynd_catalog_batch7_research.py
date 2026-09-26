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
        assert candidate["variant_status"] == "verified_retail_variant"
        assert candidate["evidence"]
        assert candidate["product_data"]["source_url"].startswith("https://")
        assert candidate["product_data"]["source_kind"]
        for evidence in candidate["research_merchant_evidence"]:
            assert evidence["url"].startswith("https://")
            assert evidence["variant"] == (
                f"{candidate['volume_ml']} ml {candidate['concentration']}"
            )
            assert (
                evidence["merchant_product_id"] in candidate["identifiers"]["merchant_product_ids"]
            )
            assert evidence["affiliate_state"] in {
                "application_pending",
                "cj_application_pending",
                "not_affiliate_target",
            }
        assert (
            "current_verified_purchase_destination_pending" in candidate["validation"]["blockers"]
        )
        assert "merchant_variant_mapping_pending" not in candidate["validation"]["blockers"]
        community = candidate["community"]
        assert community["source"] == "Parfumo"
        assert community["source_url"].startswith("https://www.parfumo.com/")
        assert community["rating_count"] > 0
        assert community["longevity_count"] > 0
        assert community["projection_count"] > 0
        assert community["provisional"] is False
        assert community["main_accords"]
        assert candidate["identifiers"]["status"] == "pending_primary_variant_verification"
        assert candidate["identifiers"]["canonical_gtin"] is None
        assert candidate["identifiers"]["observations"] == []
        assert candidate["media"]["image_url"] is None
        assert candidate["media"]["image_status"] == (
            "pending_approved_feed_or_manufacturer_image"
        )
        assert candidate["validation"]["catalog_ready"] is False



def test_batch7_official_store_can_be_non_affiliate_research_destination() -> None:
    wave = json.loads(
        Path(
            "examples/retail/data/dufynd_catalog_expansion_batch7_research.json"
        ).read_text(encoding="utf-8")
    )
    afnan = next(
        row
        for row in wave["candidates"]
        if row["product_id"] == "SC-AFNAN-9-PM-POUR-FEMME-EDP-100"
    )

    assert afnan["research_merchant_evidence"][0]["affiliate_state"] == (
        "not_affiliate_target"
    )
    assert afnan["research_merchant_evidence"][0]["url"].startswith(
        "https://www.de.afnan.com/"
    )
