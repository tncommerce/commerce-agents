from __future__ import annotations

import json
from pathlib import Path

from scripts.build_dufynd_cj_deep_link import build_cj_deep_link

DATA = Path("examples/retail/data/scentai_notino_release01_affiliate_evidence_20260930.json")

EXPECTED_PRODUCTS = {
    "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100": "LAM13175",
    "SC-PDM-DELINA-EDP-75": "PDM0227",
    "SC-DIOR-HYPNOTIC-POISON-EDT-100": "CHD0313",
    "SC-YSL-BLACK-OPIUM-EDP-90": "YSL2377",
    "SC-YSL-LIBRE-EDP-90": "VZR11010",
}


def _payload() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_release01_notino_evidence_is_staged_not_live() -> None:
    payload = _payload()

    assert payload["scope"]["candidate_count"] == 5
    assert payload["scope"]["live_routing_allowed"] is False
    assert payload["scope"]["source_of_truth_mapping_mutation"] is False
    assert payload["scope"]["control_plane_mutation"] is False
    assert payload["scope"]["website_mutation"] is False

    rows = {row["product_id"]: row for row in payload["candidates"]}
    assert set(rows) == set(EXPECTED_PRODUCTS)

    for product_id, merchant_product_id in EXPECTED_PRODUCTS.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["mapping_status"] == "verified_current_variant_candidate"
        assert row["activation_state"] == "staged_not_live"
        assert row["publish_allowed"] is False
        assert row["image_rights_status"] == "not_implied_by_affiliate_mapping"


def test_release01_notino_candidate_links_use_guarded_builder() -> None:
    payload = _payload()

    for row in payload["candidates"]:
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_release01_notino_availability_is_observation_not_activation() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    assert rows["SC-LANCOME-LA-VIE-EST-BELLE-EDP-100"]["availability_observed"] is False
    assert all(
        row["publish_allowed"] is False
        for row in payload["candidates"]
        if row["availability_observed"] is True
    )
