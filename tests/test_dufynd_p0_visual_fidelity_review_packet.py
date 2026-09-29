from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
PACKET = DATA_DIR / "dufynd_p0_visual_fidelity_review_packet_20260929.json"
QUEUE = DATA_DIR / "dufynd_product_visual_review_queue.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p0_fidelity_packet_matches_existing_review_queue() -> None:
    packet = _load(PACKET)
    queue = _load(QUEUE)

    queue_by_product = {
        item["product_id"]: item
        for item in queue.get("items", [])
        if item.get("priority") == "P0" and item.get("candidate_asset")
    }

    packet_rows = packet.get("review_order", [])

    assert packet["status"] == "partially_fidelity_reviewed_not_live"
    assert packet["approval_scope"]["automatic_approval_allowed"] is False
    assert packet["approval_scope"]["automatic_live_activation_allowed"] is False
    assert packet["approval_scope"]["rights_clearance_implied"] is False
    assert len(packet_rows) == len(queue_by_product) == 4

    for row in packet_rows:
        product_id = row["product_id"]
        assert product_id in queue_by_product
        assert row["priority"] == "P0"
        assert row["candidate_asset"] == queue_by_product[product_id]["candidate_asset"]
        assert row["reference_url"] == queue_by_product[product_id]["evidence_url"]
        assert Path(row["candidate_asset"]).is_file()
        assert row["review_focus"]
        assert row["current_state"] == queue_by_product[product_id]["status"]
        assert row["fidelity_decision"] == queue_by_product[product_id]["fidelity_review"]["decision"]
        assert row["fidelity_reviewed_at"] == queue_by_product[product_id]["fidelity_review"]["reviewed_at"]


def test_p0_fidelity_packet_never_implies_live_approval() -> None:
    packet = _load(PACKET)

    allowed = set(packet["approval_scope"]["allowed_decisions"])

    assert allowed == {
        "approve_fidelity",
        "reject_fidelity",
        "needs_revision",
    }
    assert "approve_live" not in allowed
    assert "approve_rights" not in allowed


def test_p0_fidelity_decisions_are_recorded_without_live_activation() -> None:
    packet = _load(PACKET)

    assert set(packet["review_summary"]["approve_fidelity"]) == {
        "SC-ARMANI-SWY-INTENSELY-100",
        "SC-PRADA-LHOMME-100",
        "SC-SOSPIRO-VIBRATO-100",
    }
    assert packet["review_summary"]["needs_revision"] == ["SC-CREED-ABSOLU-AVENTUS-100"]
    assert packet["review_summary"]["live_activation_authorized"] is False
    assert packet["review_summary"]["rights_clearance_implied"] is False
