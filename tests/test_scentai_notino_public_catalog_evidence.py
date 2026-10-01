from __future__ import annotations

import json
from pathlib import Path

from scripts.build_dufynd_cj_deep_link import build_cj_deep_link

DATA = Path("examples/retail/data/scentai_notino_public_catalog_evidence_20260930.json")

EXPECTED = {
    "SC-SOSPIRO-VIBRATO-100": "SSR00580",
    "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100": "VAL18249",
    "SC-DIOR-SAUVAGE-EDP-100": "CHD7137",
    "SC-PRADA-LHOMME-100": "PRA0719",
    "SC-PRADA-LHOMME-INTENSE-EDP-100": "PRA0937",
    "SC-JPG-LE-MALE-ELIXIR-PARFUM-125": "JPG04424",
    "SC-PDM-DELINA-EDP-75": "PDM0227",
    "SC-YSL-BLACK-OPIUM-EDP-90": "YSL2377",
    "SC-DIOR-HYPNOTIC-POISON-EDT-100": "CHD0313",
}


def _payload() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_notino_catalog_evidence_is_exact_and_non_live() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    assert payload["live_routing_allowed"] is False
    assert set(rows) == set(EXPECTED)

    for product_id, merchant_product_id in EXPECTED.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["mapping_status"] == "verified_current_variant_evidence"
        assert row["activation_state"] == "staged_not_live"
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_mutation"] is False
        assert row["image_rights_status"] == "not_implied_by_affiliate_mapping"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_public_catalog_candidates_are_identified_without_activation() -> None:
    payload = _payload()
    public_rows = [row for row in payload["candidates"] if row["catalog_public"]]

    assert {row["product_id"] for row in public_rows} == {
        "SC-SOSPIRO-VIBRATO-100",
        "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100",
        "SC-DIOR-SAUVAGE-EDP-100",
        "SC-PRADA-LHOMME-100",
        "SC-PDM-DELINA-EDP-75",
        "SC-YSL-BLACK-OPIUM-EDP-90",
        "SC-DIOR-HYPNOTIC-POISON-EDT-100",
    }
    assert all(row["publish_allowed"] is False for row in public_rows)
