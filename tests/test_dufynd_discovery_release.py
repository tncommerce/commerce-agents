import json
from copy import deepcopy

import pytest
from scripts.report_dufynd_discovery_release import DATA, evaluate, report


def inputs():
    pilot = json.loads((DATA / "dufynd_release_pilots.json").read_text())["pilots"][0]
    fact = next(
        f
        for f in json.loads((DATA / "dufynd_discovery_qualification.json").read_text())["products"]
        if f["product_id"] == pilot["product_id"]
    )
    return fact, pilot


def test_three_fact_only_pages_are_reviewable_but_not_released():
    rows = report()["profiles"]
    assert len(rows) == 3
    assert all(r["ready_for_owner_review"] for r in rows)
    assert all(r["blockers"] == ["owner_release_approval"] for r in rows)
    assert all(not r["affiliate_offer_included"] for r in rows)
    assert all(r["identity_kind"] == "manufacturer_reference" for r in rows)


@pytest.mark.parametrize(
    "field,value",
    [("volume_ml", 50), ("concentration", "Parfum"), ("community_data_included", True)],
)
def test_changed_source_cannot_reuse_previous_review(field, value):
    fact, pilot = inputs()
    fact = deepcopy(fact)
    fact[field] = value
    pilot["owner_release_approved"] = True
    result = evaluate(fact, pilot)
    assert not result["public_release_eligible"]
    assert "evidence_changed_requires_review" in result["blockers"]


@pytest.mark.parametrize(
    "field,value",
    [("third_party_asset_used", True), ("contains_product_replica", True), ("label", "")],
)
def test_illustration_gate_fails_closed(field, value):
    fact, pilot = inputs()
    pilot["owner_release_approved"] = True
    pilot["visual"][field] = value
    assert "visual_rights_or_label" in evaluate(fact, pilot)["blockers"]


def test_affiliate_absence_does_not_block_an_explicitly_approved_fact_page():
    fact, pilot = inputs()
    pilot["owner_release_approved"] = True
    result = evaluate(fact, pilot)
    assert result["public_release_eligible"]
    assert not result["affiliate_offer_included"]
