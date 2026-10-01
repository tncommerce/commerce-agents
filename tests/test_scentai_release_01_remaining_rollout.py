from __future__ import annotations

import json
from pathlib import Path

ROLLOUT = Path("examples/retail/data/scentai_release_01_remaining_rollout_20261001.json")


def test_remaining_release01_rollout_reflects_current_product_scoped_notino_state() -> None:
    payload = json.loads(ROLLOUT.read_text(encoding="utf-8"))

    assert payload["historical_manifest_mutated"] is False
    assert payload["state"] == "partially_activated_pending_hypnotic_image_gate"
    assert payload["write_enabled"] is False

    readiness = payload["current_readiness"]
    assert set(readiness["affiliate_live_product_ids"]) == {
        "SC-PDM-DELINA-EDP-75",
        "SC-YSL-BLACK-OPIUM-EDP-90",
        "SC-YSL-LIBRE-EDP-90",
    }
    assert readiness["affiliate_pending_activation_product_ids"] == []
    assert readiness["affiliate_blocked_product_ids"] == {
        "SC-DIOR-HYPNOTIC-POISON-EDT-100": ["approved_product_image"]
    }

    affiliate = payload["affiliate_preparation"]
    assert affiliate["routing_scope"] == "verified_product_only"
    assert (
        affiliate["live_routing_state"]
        == "all_currently_eligible_release01_products_scoped_active_hypnotic_blocked"
    )
    assert affiliate["live_routing_allowed"] is False
    assert set(affiliate["live_routing_product_ids"]) == {
        "SC-PDM-DELINA-EDP-75",
        "SC-YSL-BLACK-OPIUM-EDP-90",
        "SC-YSL-LIBRE-EDP-90",
    }
    assert affiliate["pending_live_routing_approval_product_ids"] == []
    assert affiliate["blocked_live_routing_product_ids"] == {
        "SC-DIOR-HYPNOTIC-POISON-EDT-100": ["approved_product_image"]
    }
    assert affiliate["image_rights_implied_by_affiliate_mapping"] is False
