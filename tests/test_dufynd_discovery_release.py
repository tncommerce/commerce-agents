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


def test_curated_wave_is_reviewable_but_not_released():
    rows = report()["profiles"]
    assert len(rows) >= 10
    assert all(r["ready_for_owner_review"] for r in rows)
    assert all(r["blockers"] == ["owner_release_approval"] for r in rows)
    assert all(not r["affiliate_offer_included"] for r in rows)
    assert {r["identity_kind"] for r in rows} == {"manufacturer_reference", "gtin"}


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


def test_legacy_boolean_cannot_replace_bound_release_authorization():
    fact, pilot = inputs()
    pilot["owner_release_approved"] = True
    result = evaluate(fact, pilot)
    assert not result["public_release_eligible"]
    assert result["blockers"] == ["use_bound_release_authorization_pipeline"]
    assert not result["affiliate_offer_included"]
