"""The manufacturer-only packet must fail closed at the existing import gate."""

import json
from pathlib import Path

from scripts.validate_dufynd_catalog_expansion_wave import validate_wave

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/retail/data"
PACKET = ROOT / "docs/dufynd-growth-02-import-hold.json"


def read(path):
    return json.loads(path.read_text())


def test_unknown_affiliate_evidence_cannot_enter_existing_staging():
    packet = read(PACKET)
    assert validate_wave(
        packet, read(DATA / "catalog.json"), read(DATA / "scentai_catalog_staging.json")
    ) == [f"candidate_{i}:merchant_1:invalid_affiliate_state" for i in (1, 2, 3)]
    assert packet["enabled"] is False
    assert packet["live_publication_authorized"] is False
    assert packet["staging_ready"] is False


def test_exact_candidates_do_not_reuse_existing_catalog_or_exclusif_ids():
    packet = read(PACKET)
    candidates = {
        r["candidate_id"] for r in read(DATA / "scentai_catalog_candidates.json")["products"]
    }
    registered = {
        r["product_id"]
        for file in ("catalog.json", "scentai_products.json", "scentai_catalog_staging.json")
        for r in read(DATA / file)["products"]
    }
    proposed = {r["product_id"] for r in packet["candidates"]}
    assert len(proposed) == 3
    assert not proposed & registered
    assert "SC-PDM-VALAYA-EXCLUSIF-EDP-75" in registered
    for row in packet["candidates"]:
        assert row["candidate_id"] in candidates
        assert row["validation"]["catalog_ready"] is False
        assert row["validation"]["blockers"]
        assert row["identifiers"]["canonical_gtin"] is None
        assert row["identifiers"]["observations"] == []
        assert row["media"]["image_url"] is None
        assert not {"price", "in_stock", "affiliate_url", "community"} & row.keys()
        assert row["product_data"]["notes"]
        assert all(m["affiliate_state"] == "UNKNOWN" for m in row["research_merchant_evidence"])
