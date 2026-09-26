from __future__ import annotations

import json
from pathlib import Path


def test_batch7_stays_research_only_until_sources_are_verified() -> None:
    data = Path("examples/retail/data")
    wave = json.loads((data / "dufynd_catalog_expansion_batch7_research.json").read_text())
    intake = json.loads((data / "dufynd_catalog_staging_intake.json").read_text())
    staging = json.loads((data / "scentai_catalog_staging.json").read_text())
    live = json.loads((data / "catalog.json").read_text())

    candidates = wave["candidates"]
    ids = [row["product_id"] for row in candidates]
    existing_ids = {row["product_id"] for row in [*staging["products"], *live["products"]]}

    assert len(candidates) == wave["max_products"] == 5
    assert len(set(ids)) == 5
    assert set(ids).isdisjoint(existing_ids)
    assert wave["live_publication_authorized"] is False
    assert wave["status"] == "research_only_not_enabled_for_staging"
    assert all(entry["wave_id"] != wave["wave_id"] for entry in intake["waves"])
    for candidate in candidates:
        assert candidate["manufacturer_source_url"].startswith("https://")
        assert candidate["merchant_evidence"] == []
        assert candidate["community"] is None
        assert candidate["identifiers"]["canonical_gtin"] is None
        assert candidate["media"]["image_url"] is None
        assert candidate["validation"]["catalog_ready"] is False
