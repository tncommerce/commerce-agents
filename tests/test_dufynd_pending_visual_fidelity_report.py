from __future__ import annotations

from scripts.report_dufynd_pending_visual_fidelity import build_report


def test_pending_visual_report_unifies_current_review_sources() -> None:
    report = build_report()

    assert report["status"] == "waiting_human_fidelity"
    assert report["review_gate"] == "fidelity_only"
    assert report["automatic_approval_allowed"] is False
    assert report["automatic_activation_allowed"] is False
    assert report["rights_clearance_implied"] is False
    assert report["fidelity_approval_is_not_production_approval"] is True
    assert report["pending_count"] == 4

    by_id = {item["product_id"]: item for item in report["items"]}
    assert set(by_id) == {
        "SC-CREED-ABSOLU-AVENTUS-100",
        "SC-GUERLAIN-MON-GUERLAIN-EDP-100",
        "SC-JPG-LE-MALE-ELIXIR-PARFUM-125",
        "SC-YSL-LIBRE-EDP-90",
    }

    for item in report["items"]:
        assert item["candidate_asset"]
        assert item["reference_url"]
        assert item["rights_clearance_implied"] is False
        assert item["production_approval_ready"] is False
        assert item["public_activation"] is False
        assert item["catalog_promotion"] is False


def test_pending_visual_report_keeps_creed_and_staged_candidates_distinct() -> None:
    report = build_report()
    by_id = {item["product_id"]: item for item in report["items"]}

    assert by_id["SC-CREED-ABSOLU-AVENTUS-100"]["source_manifest"].endswith(
        "dufynd_product_visual_review_queue.json"
    )
    assert by_id["SC-YSL-LIBRE-EDP-90"]["source_manifest"].endswith(
        "dufynd_staged_image_fidelity_candidates_20260930.json"
    )


def test_generated_candidates_do_not_gain_rights_from_fidelity_queue() -> None:
    report = build_report()
    by_id = {item["product_id"]: item for item in report["items"]}

    assert by_id["SC-YSL-LIBRE-EDP-90"]["provenance"] == (
        "dufynd_generated_internal_candidate"
    )
    assert by_id["SC-YSL-LIBRE-EDP-90"]["source_registration_status"] == "not_registered"
    assert by_id["SC-CREED-ABSOLU-AVENTUS-100"]["provenance"] == "dufynd_generated"

    for item in report["items"]:
        assert item["rights_clearance_implied"] is False
        assert item["production_approval_ready"] is False
