"""Keep DUFYND promotion queue semantics aligned with purchase-destination policy."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

QUEUE = Path("examples/retail/data/scentai_catalog_promotion_queue.json")

DIRECT_PURCHASE_READY = {
    "SC-YSL-LIBRE-EDP-90",
    "SC-GUERLAIN-MON-GUERLAIN-EDP-100",
    "SC-BURBERRY-GODDESS-EDP-100",
    "SC-PRADA-PARADOXE-EDP-90",
    "SC-PDM-DELINA-EDP-75",
}


def test_affiliate_is_not_a_catalog_promotion_gate() -> None:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    rows = queue["candidates"]

    assert all("affiliate_link_pending" not in row["blockers"] for row in rows)

    ready_by_id = {
        row["proposed_product_id"]: row
        for row in rows
        if row["proposed_product_id"] in DIRECT_PURCHASE_READY
    }
    assert set(ready_by_id) == DIRECT_PURCHASE_READY

    for row in ready_by_id.values():
        assert "verified_purchase_destination_pending" not in row["blockers"]
        assert row["blockers"] == ["approved_product_image_pending"]
        assert row["ready_for_live"] is False

    waiting = [
        row
        for row in rows
        if row["proposed_product_id"] not in DIRECT_PURCHASE_READY
    ]
    assert all(
        "verified_purchase_destination_pending" in row["blockers"]
        for row in waiting
    )


def test_queue_blocker_summary_matches_candidate_rows() -> None:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    actual = Counter(
        blocker
        for row in queue["candidates"]
        for blocker in row.get("blockers", [])
    )

    assert queue["blocker_counts"] == dict(actual)
    assert queue["summary"]["current_purchase_destinations_ready"] == 5
    assert queue["summary"]["affiliate_links_ready"] == 0
