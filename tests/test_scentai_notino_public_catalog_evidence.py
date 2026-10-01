from __future__ import annotations

import json
from pathlib import Path

from scripts.build_dufynd_cj_deep_link import build_cj_deep_link

DATA = Path("examples/retail/data/scentai_notino_public_catalog_evidence_20260930.json")

EXPECTED = {
    "SC-SOSPIRO-VIBRATO-100": "SSR00580",
    "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100": "VAL18249",
    "SC-DIOR-SAUVAGE-EDP-100": "CHD7137",
    "SC-PRADA-LHOMME-100": "PRA0719",
    "SC-PRADA-LHOMME-INTENSE-EDP-100": "PRA0937",
    "SC-JPG-LE-MALE-ELIXIR-PARFUM-125": "JPG04424",
    "SC-PDM-DELINA-EDP-75": "PDM0227",
    "SC-YSL-BLACK-OPIUM-EDP-90": "YSL2377",
    "SC-DIOR-HYPNOTIC-POISON-EDT-100": "CHD0313",
    "SC-YSL-LIBRE-EDP-90": "VZR11010",
    "SC-JPG-LE-MALE-LE-PARFUM-125": "JPG04167",
    "SC-PDM-HEROD-EDP-125": "PDM0055",
    "SC-INITIO-SIDE-EFFECT-EDP-90": "INI03376",
    "SC-VIKTOR-ROLF-SPICEBOMB-EXTREME-EDP-90": "VRO0459",
    "SC-HUGO-BOSS-BOTTLED-EDT-100": "HUG0302",
    "SC-DIOR-SAUVAGE-ELIXIR-100": "CHD16261",
    "SC-MUGLER-ALIEN-EDP-90": "THM1124",
    "SC-NARCISO-RODRIGUEZ-PURE-MUSC-EDP-100": "NAR01382",
    "SC-YSL-MYSLF-LE-PARFUM-100": "YSL12342",
    "SC-YSL-LA-NUIT-DE-LHOMME-EDT-100": "YSL0136",
}


def _payload() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_notino_catalog_evidence_is_exact_and_non_live() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    assert payload["live_routing_allowed"] is False
    assert set(rows) == set(EXPECTED)

    for product_id, merchant_product_id in EXPECTED.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["mapping_status"] == "verified_current_variant_evidence"
        assert row["activation_state"] == "staged_not_live"
        assert row["publish_allowed"] is False
        assert row["source_of_truth_mapping_mutation"] is False
        assert row["image_rights_status"] == "not_implied_by_affiliate_mapping"
        assert row["candidate_affiliate_url"] == build_cj_deep_link(
            destination_url=row["product_url"]
        )


def test_public_catalog_candidates_are_identified_without_activation() -> None:
    payload = _payload()
    public_rows = [row for row in payload["candidates"] if row["catalog_public"]]

    assert {row["product_id"] for row in public_rows} == {
        "SC-SOSPIRO-VIBRATO-100",
        "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100",
        "SC-DIOR-SAUVAGE-EDP-100",
        "SC-PRADA-LHOMME-100",
        "SC-PDM-DELINA-EDP-75",
        "SC-YSL-BLACK-OPIUM-EDP-90",
        "SC-DIOR-HYPNOTIC-POISON-EDT-100",
        "SC-YSL-LIBRE-EDP-90",
        "SC-JPG-LE-MALE-LE-PARFUM-125",
        "SC-PDM-HEROD-EDP-125",
        "SC-INITIO-SIDE-EFFECT-EDP-90",
        "SC-VIKTOR-ROLF-SPICEBOMB-EXTREME-EDP-90",
        "SC-HUGO-BOSS-BOTTLED-EDT-100",
        "SC-DIOR-SAUVAGE-ELIXIR-100",
        "SC-MUGLER-ALIEN-EDP-90",
        "SC-NARCISO-RODRIGUEZ-PURE-MUSC-EDP-100",
        "SC-YSL-MYSLF-LE-PARFUM-100",
        "SC-YSL-LA-NUIT-DE-LHOMME-EDT-100",
    }
    assert all(row["publish_allowed"] is False for row in public_rows)


def test_spicebomb_extreme_90_is_exact_but_not_activation_ready() -> None:
    payload = _payload()
    row = next(
        row
        for row in payload["candidates"]
        if row["product_id"] == "SC-VIKTOR-ROLF-SPICEBOMB-EXTREME-EDP-90"
    )

    assert row["merchant_product_id"] == "VRO0459"
    assert row["gtin"] == "3614270659706"
    assert row["availability_observed"] is False
    assert row["activation_state"] == "staged_not_live"
    assert row["publish_allowed"] is False


def test_commerce_wave3_evidence_is_exact_current_and_non_live() -> None:
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

    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["availability_observed"] is True
        assert row["activation_state"] == "staged_not_live"
        assert row["publish_allowed"] is False
        assert row["image_rights_status"] == "not_implied_by_affiliate_mapping"


def test_commerce_wave4_evidence_is_exact_current_and_non_live() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-HUGO-BOSS-BOTTLED-EDT-100": ("HUG0302", "737052351100"),
        "SC-DIOR-SAUVAGE-ELIXIR-100": ("CHD16261", "3348901640916"),
        "SC-MUGLER-ALIEN-EDP-90": ("THM1124", "3439600056969"),
    }

    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["availability_observed"] is True
        assert row["activation_state"] == "staged_not_live"
        assert row["publish_allowed"] is False
        assert row["image_rights_status"] == "not_implied_by_affiliate_mapping"


def test_commerce_wave5_evidence_is_exact_current_and_non_live() -> None:
    payload = _payload()
    rows = {row["product_id"]: row for row in payload["candidates"]}

    expected = {
        "SC-NARCISO-RODRIGUEZ-PURE-MUSC-EDP-100": ("NAR01382", "3423478515956"),
        "SC-YSL-MYSLF-LE-PARFUM-100": ("YSL12342", "3614274114645"),
        "SC-YSL-LA-NUIT-DE-LHOMME-EDT-100": ("YSL0136", "3365440375079"),
    }

    for product_id, (merchant_product_id, gtin) in expected.items():
        row = rows[product_id]
        assert row["merchant_product_id"] == merchant_product_id
        assert row["gtin"] == gtin
        assert row["availability_observed"] is True
        assert row["activation_state"] == "staged_not_live"
        assert row["publish_allowed"] is False
        assert row["image_rights_status"] == "not_implied_by_affiliate_mapping"
