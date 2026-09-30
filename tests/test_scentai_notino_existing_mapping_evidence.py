from __future__ import annotations

import json
from pathlib import Path

from scripts.build_dufynd_cj_deep_link import build_cj_deep_link

DATA = Path("examples/retail/data/scentai_notino_existing_mapping_evidence_20260930.json")


def _payload() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_existing_notino_mapping_evidence_stays_non_live() -> None:
    payload = _payload()

    assert payload["live_routing_allowed"] is False
    assert payload["policy"]["source_of_truth_mapping_mutation"] is False
    assert all(row["publish_allowed"] is False for row in payload["candidates"])
    assert all(
        row["image_rights_status"] == "not_implied_by_affiliate_mapping"
        for row in payload["candidates"]
    )


def test_existing_notino_candidates_use_guarded_cj_builder() -> None:
    payload = _payload()

    for row in payload["candidates"]:
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_bois_imperial_evidence_does_not_mutate_incomplete_mapping() -> None:
    payload = _payload()
    row = next(
        item
        for item in payload["candidates"]
        if item["product_id"] == "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"
    )

    assert row["merchant_product_id"] == "ETP00580"
    assert row["source_of_truth_mapping_row_present"] is True
    assert row["source_of_truth_merchant_product_id_present"] is False
    assert row["availability_observed"] is False
    assert row["publish_allowed"] is False
