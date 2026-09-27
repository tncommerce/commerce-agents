"""Guard the Release 01 licensed-image acquisition plan."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
PLAN = DATA_DIR / "dufynd_release01_image_acquisition_plan.json"
RELEASE = DATA_DIR / "scentai_release_batch_01.json"
RIGHTS = DATA_DIR / "dufynd_release01_asset_rights_audit.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_image_acquisition_plan_matches_release01_manifest() -> None:
    plan = _load(PLAN)
    release = _load(RELEASE)

    plan_ids = [row["product_id"] for row in plan["products"]]

    assert plan["release_id"] == release["release_id"]
    assert plan_ids == release["product_ids"]
    assert plan["summary"]["release_products"] == len(release["product_ids"])
    assert plan["summary"]["approved_images"] == 1
    assert plan["summary"]["licensed_source_required"] == len(release["product_ids"]) - 1
    assert plan["summary"]["currently_usable_licensed_feed_assets"] == 0
    assert plan["summary"]["manual_visual_approval_ready"] == 0


def test_acquisition_plan_never_treats_reference_images_as_approved() -> None:
    plan = _load(PLAN)
    rights = _load(RIGHTS)
    rights_by_id = {row["product_id"]: row for row in rights["products"]}

    for row in plan["products"]:
        product_id = row["product_id"]
        evidence = rights_by_id[product_id]

        if product_id == "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100":
            assert row["image_state"] == "approved_licensed_image"
            assert row["currently_usable_licensed_asset"] is True
            assert evidence["rights_basis_id"] == row["approved_rights_basis_id"]
            assert evidence["image_url"] == row["approved_image_url"]
            assert row["next_action"] == "none"
            continue
        assert row["image_state"] == "licensed_source_required"
        assert row["currently_usable_licensed_asset"] is False
        assert evidence["public_distribution_allowed"] is False
        assert evidence["final_composite_allowed"] is False
        assert "dufynd_owned_original_product_photography" in row["alternative_routes"]
        assert row["next_action"] == (
            "obtain_exact_licensed_or_dufynd_owned_asset_then_manual_visual_approval"
        )


def test_top_parfuemerie_candidates_remain_conditional() -> None:
    plan = _load(PLAN)
    rows = plan["products"]
    with_candidate = [row for row in rows if row["top_parfuemerie"]["image_candidate_present"]]
    without_candidate = [
        row for row in rows if not row["top_parfuemerie"]["image_candidate_present"]
    ]

    assert len(with_candidate) == 4
    assert [row["product_id"] for row in without_candidate] == ["SC-DIOR-HYPNOTIC-POISON-EDT-100"]

    for row in with_candidate:
        top = row["top_parfuemerie"]
        assert top["program_status"] == "applied_pending"
        assert top["acquisition_state"] == (
            "blocked_until_program_approval_and_image_rights_basis_verified"
        )


def test_perfumetrader_approval_does_not_fake_product_feed_availability() -> None:
    plan = _load(PLAN)

    for row in plan["products"]:
        merchant = row["perfumetrader"]
        assert merchant["program_status"] == "approved"
        assert merchant["official_awin_product_feed_available"] is False
        assert merchant["acquisition_state"] != "licensed_feed_asset_ready"
