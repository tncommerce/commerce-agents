from __future__ import annotations

import json
from pathlib import Path

from scripts.build_dufynd_cj_deep_link import build_cj_deep_link

CANDIDATES = Path("examples/retail/data/scentai_notino_activation_candidates_20260930.json")


def _payload() -> dict:
    return json.loads(CANDIDATES.read_text(encoding="utf-8"))


def test_notino_candidates_are_staged_not_live() -> None:
    payload = _payload()

    assert payload["state"] == "staged_not_live"
    assert payload["live_routing_allowed"] is False
    assert all(row["publish_allowed"] is False for row in payload["candidates"])


def test_euphoria_candidate_uses_guarded_cj_builder() -> None:
    payload = _payload()
    candidate = next(
        row
        for row in payload["candidates"]
        if row["product_id"] == "SC-CALVIN-KLEIN-EUPHORIA-EDP-100"
    )

    assert candidate["mapping_status"] == "verified_current_variant"
    assert candidate["readiness"] == "ready_for_user_activation_approval"
    assert candidate["candidate_affiliate_url"] == build_cj_deep_link(
        destination_url=candidate["product_url"]
    )


def test_unmapped_notino_offers_remain_blocked() -> None:
    payload = _payload()
    blocked = {
        row["product_id"]: row for row in payload["candidates"] if row["readiness"] == "blocked"
    }

    assert blocked["SC-XERJOFF-NAXOS-100"]["blocker"] == (
        "notino_exact_mapping_missing_from_merchant_product_mappings"
    )
    assert blocked["SC-HUGO-BOSS-BOTTLED-ABSOLU-100"]["blocker"] == (
        "notino_exact_mapping_missing_from_merchant_product_mappings"
    )
