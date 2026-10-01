from __future__ import annotations

import json
from pathlib import Path

MAPPINGS = Path("examples/retail/data/merchant_product_mappings.json")
CANDIDATES = Path("examples/retail/data/scentai_notino_activation_candidates_20260930.json")
OFFERS = Path("examples/retail/data/merchant_offers.json")
PROGRAMS = Path("examples/retail/data/scentai_affiliate_programs.json")
EVIDENCE = Path(
    "examples/retail/data/dufynd_notino_mapping_promotion_naxos_boss_absolu_20261001.json"
)

EXPECTED = {
    "SC-XERJOFF-NAXOS-100": ("XEF3191", "8033488155070"),
    "SC-HUGO-BOSS-BOTTLED-ABSOLU-100": ("HUG13734", "3616305480620"),
}


def test_naxos_and_boss_absolu_notino_mappings_are_exact_and_non_live() -> None:
    mappings = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    programs = json.loads(PROGRAMS.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    notino = next(row for row in programs["other_networks"] if row["merchant_id"] == "notino")
    candidate_rows = {row["product_id"]: row for row in candidates["candidates"]}

    assert evidence["source_candidate_file_mutated"] is False
    assert evidence["safeguards"]["merchant_offers_mutated"] is False
    assert evidence["safeguards"]["affiliate_live_routing_allowed"] is False
    assert evidence["safeguards"]["catalog_publication_authorized"] is False
    assert evidence["safeguards"]["image_rights_granted"] is False

    for product_id, (merchant_product_id, gtin) in EXPECTED.items():
        exact = [
            row for row in mappings
            if row["product_id"] == product_id and row["merchant"] == "notino"
        ]
        assert len(exact) == 1
        assert exact[0]["merchant_product_id"] == merchant_product_id
        assert exact[0]["gtin"] == gtin
        assert exact[0]["mapping_status"] == "verified_current_variant"

        historical = candidate_rows[product_id]
        assert historical["publish_allowed"] is False
        assert historical["source_of_truth_mapping_state"] == "pending_collision_free_handoff"

        notino_offer = next(
            row for row in offers
            if row["product_id"] == product_id and row["merchant_id"] == "notino"
        )
        assert notino_offer["affiliate_url"] is None
        assert product_id not in set(notino["live_activation_products"])

    assert "Bottled Absolute" in candidate_rows[
        "SC-HUGO-BOSS-BOTTLED-ABSOLU-100"
    ]["variant_disambiguation"]
