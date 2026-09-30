from __future__ import annotations

import json
from pathlib import Path

DATA = Path("examples/retail/data")
OBSERVED_AT = "2026-09-30T08:17:30Z"


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_refreshed_women_offers_match_exact_variants() -> None:
    offers = {row["offer_id"]: row for row in load("merchant_offers.json")["offers"]}

    good_girl = offers["mueller-good-girl-edp-80"]
    armani_si = offers["mueller-armani-si-edp-100"]

    assert good_girl["product_id"] == "SC-CAROLINA-HERRERA-GOOD-GIRL-EDP-80"
    assert good_girl["merchant_product_id"] == "2070740"
    assert good_girl["variant_label"] == "80 ml · Eau de Parfum"
    assert good_girl["price"] == 79.95
    assert good_girl["last_updated_at"] == OBSERVED_AT

    assert armani_si["product_id"] == "SC-ARMANI-SI-EDP-100"
    assert armani_si["merchant_product_id"] == "689615"
    assert armani_si["variant_label"] == "100 ml · Eau de Parfum · nachfüllbarer Flakon"
    assert armani_si["price"] == 89.95
    assert armani_si["last_updated_at"] == OBSERVED_AT


def test_refreshed_evidence_does_not_grant_image_or_affiliate_rights() -> None:
    for name in (
        "dufynd_good_girl_80_purchase_evidence.json",
        "dufynd_armani_si_edp_100_purchase_evidence.json",
    ):
        evidence = load(name)
        assert evidence["observed_at"] == OBSERVED_AT
        assert evidence["observation_method"] == (
            "current_public_merchant_page_read_only_web_retrieval"
        )
        assert evidence["rights_or_affiliate_impact"] == {
            "image_rights_granted": False,
            "affiliate_tracking_verified": False,
            "final_image_approval_granted": False,
        }


def test_refreshed_women_candidates_still_fail_closed_on_image_gate() -> None:
    staging = {row["product_id"]: row for row in load("scentai_catalog_staging.json")["products"]}

    for product_id in (
        "SC-CAROLINA-HERRERA-GOOD-GIRL-EDP-80",
        "SC-ARMANI-SI-EDP-100",
    ):
        product = staging[product_id]
        assert product["commerce"]["market_status"] == "verified_current_purchase_destination"
        assert product["commerce"]["live_offer_status"] == "current_purchase_destination_verified"
        assert product["validation"]["catalog_ready"] is False
        assert product["validation"]["blockers"] == ["approved_product_image_pending"]
