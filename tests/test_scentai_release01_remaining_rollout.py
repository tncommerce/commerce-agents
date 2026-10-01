from __future__ import annotations

import json
from pathlib import Path

ROLLOUT = Path("examples/retail/data/scentai_release_01_remaining_rollout_20261001.json")
ACTIVATION = Path("examples/retail/data/scentai_notino_activation_candidates_20260930.json")


def test_remaining_rollout_preserves_release01_history() -> None:
    payload = json.loads(ROLLOUT.read_text(encoding="utf-8"))

    assert payload["source_release_id"] == "SCENTAI-RELEASE-01"
    assert payload["historical_manifest_mutated"] is False
    assert payload["write_enabled"] is False
    assert payload["excluded_historical_products"] == [
        {
            "product_id": "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100",
            "reason": "already_live",
            "retained_in_source_release": True,
        }
    ]
    assert payload["product_ids"] == [
        "SC-PDM-DELINA-EDP-75",
        "SC-DIOR-HYPNOTIC-POISON-EDT-100",
        "SC-YSL-BLACK-OPIUM-EDP-90",
        "SC-YSL-LIBRE-EDP-90",
    ]


def test_remaining_rollout_is_fail_closed_on_hypnotic_poison() -> None:
    payload = json.loads(ROLLOUT.read_text(encoding="utf-8"))

    assert payload["current_readiness"]["blocked_products"] == {
        "SC-DIOR-HYPNOTIC-POISON-EDT-100": ["approved_product_image"]
    }
    assert payload["affiliate_preparation"]["live_routing_allowed"] is False
    assert payload["affiliate_preparation"]["image_rights_implied_by_affiliate_mapping"] is False


def test_release01_notino_candidates_are_preflight_only() -> None:
    payload = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-PDM-DELINA-EDP-75": "PDM0227",
        "SC-YSL-BLACK-OPIUM-EDP-90": "YSL2377",
        "SC-DIOR-HYPNOTIC-POISON-EDT-100": "CHD0313",
    }

    assert payload["live_routing_allowed"] is False
    for product_id, merchant_product_id in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"

    assert rows["SC-DIOR-HYPNOTIC-POISON-EDT-100"]["product_publication_blockers"] == [
        "approved_product_image"
    ]
