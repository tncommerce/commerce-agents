"""Guard the curated Widian London DUFYND catalog entry."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("examples/retail/data/catalog.json")
SOURCE = Path("examples/retail/data/scentai_products.json")
OFFICIAL = Path("examples/retail/storefront-web/lib/officialProductPages.ts")
PUBLIC = Path("examples/retail/storefront-web/public")
NOTE_LABELS = Path("examples/retail/storefront-web/lib/noteLabels.ts")

PRODUCT_ID = "SC-WIDIAN-LONDON-EXTRAIT-50"


def test_widian_london_catalog_variant_and_metrics_are_consistent() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))

    catalog_row = next(row for row in catalog["products"] if row["product_id"] == PRODUCT_ID)
    source_row = next(row for row in source["products"] if row["product_id"] == PRODUCT_ID)

    assert source_row["brand"] == "Widian"
    assert source_row["name"] == "London"
    assert source_row["concentration"] == "Extrait de Parfum"
    assert source_row["volume_ml"] == 50
    assert source_row["release_year"] == 2018

    assert catalog_row["attributes"]["volume_ml"] == "50"
    assert catalog_row["attributes"]["concentration"] == "Extrait de Parfum"
    assert catalog_row["attributes"]["community_rating_10"] == "9.0"
    assert catalog_row["attributes"]["longevity"] == "8.9"
    assert catalog_row["attributes"]["projection"] == "8.6"

    assert source_row["community"]["source"] == "Parfumo"
    assert source_row["community"]["rating_10"] == 9.0
    assert source_row["community"]["rating_count"] == 4219
    assert source_row["market"]["market_price_eur"] == 270
    assert source_row["market"]["price_checked_at"] == "2026-09-18"


def test_widian_london_generated_visual_remains_editorial_only() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    row = next(row for row in source["products"] if row["product_id"] == PRODUCT_ID)

    assert len(row["visuals"]) == 1
    visual = row["visuals"][0]
    assert visual["role"] == "editorial"
    assert visual["fidelity_status"] == "editorial_only"
    assert visual["provenance"] == "user_higgsfield_video_20260925"
    assert visual.get("variant") is None
    assert visual["composition"] == "product_scene"
    assert row["image_url"] == visual["url"]

    image_path = PUBLIC / visual["url"].removeprefix("/")
    assert image_path.is_file()


def test_widian_london_has_official_fallback_and_german_note_labels() -> None:
    official = OFFICIAL.read_text(encoding="utf-8")
    labels = NOTE_LABELS.read_text(encoding="utf-8")

    assert f'"{PRODUCT_ID}"' in official
    assert 'url: "https://widian.com/en/products/london"' in official
    assert '"cypress": "Zypresse"' in labels
    assert '"raspberry": "Himbeere"' in labels
