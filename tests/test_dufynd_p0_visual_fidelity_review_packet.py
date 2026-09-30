from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
PUBLIC_ROOT = Path("examples/retail/storefront-web/public")
PACKET = DATA_DIR / "dufynd_p0_visual_fidelity_review_packet_20260929.json"
QUEUE = DATA_DIR / "dufynd_product_visual_review_queue.json"

PROMOTED_IDS = {
    "SC-ARMANI-SWY-INTENSELY-100",
    "SC-PRADA-LHOMME-100",
    "SC-SOSPIRO-VIBRATO-100",
}
CREED_ID = "SC-CREED-ABSOLU-AVENTUS-100"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p0_fidelity_packet_records_human_decisions_without_auto_approval() -> None:
    packet = _load(PACKET)
    queue = _load(QUEUE)

    assert packet["status"] == "partially_approved_through_2026-09-30"
    assert packet["approval_scope"]["automatic_approval_allowed"] is False
    assert packet["approval_scope"]["automatic_live_activation_allowed"] is False
    assert packet["approval_scope"]["rights_clearance_implied"] is False

    rows = {row["product_id"]: row for row in packet["review_order"]}
    assert set(rows) == PROMOTED_IDS | {CREED_ID}

    active = {item["product_id"]: item for item in queue["items"]}
    promoted = {item["product_id"]: item for item in queue["approved_product_truth"]}
    assert set(active) == {CREED_ID}
    assert set(promoted) == PROMOTED_IDS

    for product_id in PROMOTED_IDS:
        row = rows[product_id]
        record = promoted[product_id]
        assert row["review_decision"] == "approve_fidelity"
        assert row["current_state"] == "fidelity_approved_promoted_product_truth"
        assert row["rights_source_state"] == "dufynd_generated_internal_asset"
        assert row["candidate_asset"] == record["source_candidate_asset"]
        assert row["public_asset"] == record["public_asset"]
        assert Path(row["candidate_asset"]).is_file()
        assert (PUBLIC_ROOT / row["public_asset"].removeprefix("/")).is_file()

    creed = rows[CREED_ID]
    assert creed["review_decision"] == "approve_fidelity"
    assert creed["current_state"] == "human_fidelity_approved_pending_promotion"
    assert creed["rights_source_state"] == "dufynd_generated_internal_asset"
    assert creed["candidate_asset"] == active[CREED_ID]["candidate_asset"]
    assert active[CREED_ID]["status"] == "human_fidelity_approved_pending_promotion"
    assert active[CREED_ID]["candidate_provenance"]["approval_status"] == "human_fidelity_approved"
    assert active[CREED_ID]["candidate_provenance"]["public_activation"] is False


def test_p0_fidelity_packet_never_implies_external_image_rights() -> None:
    packet = _load(PACKET)
    allowed = set(packet["approval_scope"]["allowed_decisions"])

    assert allowed == {
        "approve_fidelity",
        "reject_fidelity",
        "needs_revision",
    }
    assert "approve_live" not in allowed
    assert "approve_rights" not in allowed
    assert packet["approval_scope"]["rights_clearance_implied"] is False
