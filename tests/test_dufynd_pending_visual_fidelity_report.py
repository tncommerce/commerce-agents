from __future__ import annotations

import json
from pathlib import Path

from scripts.report_dufynd_pending_visual_fidelity import build_report

DATA = Path("examples/retail/data")


def test_pending_visual_report_unifies_current_review_sources() -> None:
    report = build_report()

    assert report["status"] == "waiting_human_fidelity"
    assert report["review_gate"] == "fidelity_only"
    assert report["automatic_approval_allowed"] is False
    assert report["automatic_activation_allowed"] is False
    assert report["rights_clearance_implied"] is False
    assert report["fidelity_approval_is_not_production_approval"] is True
    assert report["pending_count"] == 2

    by_id = {item["product_id"]: item for item in report["items"]}
    assert set(by_id) == {
        "SC-GUERLAIN-MON-GUERLAIN-EDP-100",
        "SC-JPG-LE-MALE-ELIXIR-PARFUM-125",
    }

    for item in report["items"]:
        assert item["candidate_asset"]
        assert item["reference_url"]
        assert item["rights_clearance_implied"] is False
        assert item["production_approval_ready"] is False
        assert item["public_activation"] is False
        assert item["catalog_promotion"] is False


def test_approved_fidelity_candidates_leave_pending_report_but_stay_non_public() -> None:
    report = build_report()
    pending_ids = {item["product_id"] for item in report["items"]}
    assert "SC-CREED-ABSOLU-AVENTUS-100" not in pending_ids
    assert "SC-YSL-LIBRE-EDP-90" not in pending_ids

    queue = json.loads((DATA / "dufynd_product_visual_review_queue.json").read_text())
    creed = next(
        item for item in queue["items"] if item["product_id"] == "SC-CREED-ABSOLU-AVENTUS-100"
    )
    assert creed["status"] == "human_fidelity_approved_pending_promotion"
    assert creed["candidate_provenance"]["public_activation"] is False

    staged = json.loads(
        (DATA / "dufynd_staged_image_fidelity_candidates_20260930.json").read_text()
    )
    libre = next(
        item for item in staged["items"] if item["product_id"] == "SC-YSL-LIBRE-EDP-90"
    )
    assert libre["status"] == "human_fidelity_approved_pending_registration"
    assert libre["source_registration_status"] == "not_registered"
    assert libre["catalog_promotion"] is False
    assert libre["public_activation"] is False


def test_pending_generated_candidates_do_not_gain_rights_from_fidelity_queue() -> None:
    report = build_report()

    for item in report["items"]:
        assert item["provenance"] == "dufynd_generated_internal_candidate"
        assert item["source_registration_status"] == "not_registered"
        assert item["rights_clearance_implied"] is False
        assert item["production_approval_ready"] is False
