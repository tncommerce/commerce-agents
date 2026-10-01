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


def test_naxos_and_bottled_absolu_mapping_evidence_is_verified_but_not_live() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    for product_id in (
        "SC-XERJOFF-NAXOS-100",
        "SC-HUGO-BOSS-BOTTLED-ABSOLU-100",
    ):
        row = rows[product_id]
        assert row["mapping_status"] == "verified_current_variant_evidence"
        assert row["readiness"] == "verified_mapping_evidence_staged"
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "pending_collision_free_handoff"
        assert row["offer_in_stock_observation"] is True
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )

    assert "Bottled Absolute" in rows["SC-HUGO-BOSS-BOTTLED-ABSOLU-100"]["variant_disambiguation"]


def test_libre_90_candidate_is_exact_and_staged_not_live() -> None:
    payload = _payload()
    row = next(row for row in payload["candidates"] if row["product_id"] == "SC-YSL-LIBRE-EDP-90")

    assert row["merchant_product_id"] == "VZR11010"
    assert row["gtin"] == "3614272648425"
    assert row["mapping_status"] == "verified_current_variant"
    assert row["readiness"] == "ready_for_controlled_activation_preflight"
    assert row["publish_allowed"] is False
    assert row["source_of_truth_mapping_state"] == "not_promoted"
    assert row["offer_in_stock_observation"] is True
    assert row["candidate_affiliate_url"] == build_cj_deep_link(destination_url=row["product_url"])


def test_commerce_wave2_exact_candidates_are_preflight_only() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-JPG-LE-MALE-LE-PARFUM-125": ("JPG04167", "8435415032315"),
        "SC-PDM-HEROD-EDP-125": ("PDM0055", "3700578502353"),
        "SC-INITIO-SIDE-EFFECT-EDP-90": ("INI03376", "3701415900073"),
    }

    assert payload["live_routing_allowed"] is False
    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["offer_in_stock_observation"] is True
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )

    assert "SC-VIKTOR-ROLF-SPICEBOMB-EXTREME-EDP-90" not in rows


def test_commerce_wave3_exact_candidates_are_preflight_only() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-SOSPIRO-VIBRATO-100": ("SSR00580", "3770009763769"),
        "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100": ("VAL18249", "3614273790826"),
        "SC-DIOR-SAUVAGE-EDP-100": ("CHD7137", "3348901368247"),
        "SC-PRADA-LHOMME-100": ("PRA0719", "8435137749607"),
        "SC-PRADA-LHOMME-INTENSE-EDP-100": ("PRA0937", "8435137764730"),
        "SC-JPG-LE-MALE-ELIXIR-PARFUM-125": ("JPG04424", "8435415076944"),
    }

    assert payload["live_routing_allowed"] is False
    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["offer_in_stock_observation"] is True
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_commerce_wave4_exact_candidates_are_preflight_only() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-HUGO-BOSS-BOTTLED-EDT-100": ("HUG0302", "737052351100"),
        "SC-DIOR-SAUVAGE-ELIXIR-100": ("CHD16261", "3348901640916"),
        "SC-MUGLER-ALIEN-EDP-90": ("THM1124", "3439600056969"),
    }

    assert payload["live_routing_allowed"] is False
    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["offer_in_stock_observation"] is True
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_commerce_wave5_exact_candidates_are_preflight_only() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-NARCISO-RODRIGUEZ-PURE-MUSC-EDP-100": ("NAR01382", "3423478515956"),
        "SC-YSL-MYSLF-LE-PARFUM-100": ("YSL12342", "3614274114645"),
        "SC-YSL-LA-NUIT-DE-LHOMME-EDT-100": ("YSL0136", "3365440375079"),
    }

    assert payload["live_routing_allowed"] is False
    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["offer_in_stock_observation"] is True
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_commerce_wave6_exact_candidates_are_preflight_only() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-CHLOE-CHLOE-EDP-100": ("CHL03807", "3616302038633"),
        "SC-TOM-FORD-OMBRE-LEATHER-EDP-100": ("TOF01567", "888066075145"),
        "SC-PDM-VALAYA-EXCLUSIF-EDP-75": ("PDM00727", "3700578505767"),
    }

    assert payload["live_routing_allowed"] is False
    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["offer_in_stock_observation"] is True
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_commerce_wave7_exact_candidates_are_preflight_only() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-CAROLINA-HERRERA-GOOD-GIRL-EDP-80": ("CHR0865", "8411061818961"),
        "SC-DIOR-JADORE-EDP-100": ("CHD17856", "3348901738224"),
        "SC-VALENTINO-DONNA-BORN-IN-ROMA-EDP-100": ("VAL00621", "3614272761445"),
    }

    assert payload["live_routing_allowed"] is False
    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["offer_in_stock_observation"] is True
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_commerce_wave8_exact_candidates_are_preflight_only() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-BURBERRY-GODDESS-EDP-100": ("BUR09233", "3616302020652"),
        "SC-GUERLAIN-MON-GUERLAIN-EDP-100": ("GUR2617", "3346470131408"),
    }

    assert payload["live_routing_allowed"] is False
    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["offer_in_stock_observation"] is True
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_commerce_wave9_exact_candidates_are_preflight_only() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-ARMANI-SI-EDP-100": ("GIO0643", "3605521816658"),
        "SC-GUCCI-FLORA-GORGEOUS-GARDENIA-EDP-100": ("GUC05421", "3616302022472"),
        "SC-CHLOE-NOMADE-EDP-75": ("CHL1784", "3614223113347"),
        "SC-LATTAFA-ANGHAM-EDP-100": ("LTF00992", "6290360598338"),
    }

    assert payload["live_routing_allowed"] is False
    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["mapping_status"] == "verified_current_variant"
        assert row["readiness"] == "ready_for_controlled_activation_preflight"
        assert row["offer_in_stock_observation"] is True
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_state"] == "not_promoted"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )
