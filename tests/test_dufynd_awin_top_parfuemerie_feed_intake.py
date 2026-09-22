from __future__ import annotations

import json
from pathlib import Path

INTAKE = Path("examples/retail/data/dufynd_awin_top_parfuemerie_feed_intake.json")
PROVIDER = Path("examples/retail/data/dufynd_awin_top_parfuemerie_provider_config.json")
AUDIT = Path("examples/retail/data/dufynd_top_parfuemerie_release01_variant_audit.json")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_real_feed_profile_is_recorded_without_pretending_metadata_exists() -> None:
    intake = load(INTAKE)
    assert intake["source_availability"]["row_count"] == 8053
    assert intake["source_availability"]["header_count"] == 86
    assert "ean" in intake["field_evidence"]["present_but_empty"]
    assert "product_GTIN" in intake["field_evidence"]["present_but_empty"]
    assert intake["quality_profile"]["zero_price_rows"] == 60
    assert intake["quality_profile"]["rows_older_than_7_days"] == 7076


def test_provider_mapping_uses_only_real_populated_feed_fields() -> None:
    provider = load(PROVIDER)
    mapping = provider["field_map"]
    assert mapping["offer_id"] == "aw_product_id"
    assert mapping["merchant_product_id"] == "merchant_product_id"
    assert mapping["affiliate_url"] == "aw_deep_link"
    assert mapping["image_url"] == "merchant_image_url"
    assert "ean" not in mapping
    assert "gtin" not in mapping
    assert "shipping_cost" not in mapping
    assert provider["safety"]["reject_nonpositive_price"] is True


def test_release01_keeps_unverified_or_stale_offers_blocked() -> None:
    audit = load(AUDIT)
    rows = audit["release_01"]
    assert len(rows) == 5
    mapped = [row for row in rows if row["merchant_product_id"]]
    assert len(mapped) == 4
    hypnotic = next(row for row in rows if "Hypnotic Poison" in row["dufynd_product"])
    assert hypnotic["offer_activation"] == "blocked_no_feed_offer"
    assert all(row["offer_activation"].startswith("blocked") for row in rows)
