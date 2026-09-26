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
    assert sum(bool(candidate["merchant_evidence"]) for candidate in candidates) == 5
    for candidate in candidates:
        assert candidate["manufacturer_source_url"].startswith("https://")
        for evidence in candidate["merchant_evidence"]:
            assert evidence["product_url"].startswith("https://")
            assert evidence["selected_variant"] == f"{candidate['volume_ml']} ml"
            assert (
                evidence["merchant_product_id"] in candidate["identifiers"]["merchant_product_ids"]
            )
            assert evidence["observed_price_eur"] > 0
            assert evidence["status"] == "research_only_not_imported"
        assert (
            "current_verified_purchase_destination_pending" in candidate["validation"]["blockers"]
        )
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
        assert candidate["media"]["image_url"] is None
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
