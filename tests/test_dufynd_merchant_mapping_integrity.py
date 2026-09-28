"""Protect canonical DUFYND merchant mappings from identity corruption."""

from __future__ import annotations

import json
from pathlib import Path

MAPPINGS = Path("examples/retail/data/merchant_product_mappings.json")
STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
SOURCE = Path("examples/retail/data/scentai_products.json")

GTIN_LENGTHS = {8, 12, 13, 14}


def _gtin_valid(value: str) -> bool:
    digits = [int(char) for char in value]
    if len(digits) not in GTIN_LENGTHS:
        return False

    check = digits.pop()
    total = 0
    for offset, digit in enumerate(reversed(digits)):
        total += digit * (3 if offset % 2 == 0 else 1)

    return (10 - total % 10) % 10 == check


def test_mapping_identifiers_are_internally_consistent() -> None:
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    for row in rows:
        ean = str(row.get("ean") or "").strip()
        gtin = str(row.get("gtin") or "").strip()

        if ean:
            assert ean.isdigit(), row
            assert _gtin_valid(ean), row
        if gtin:
            assert gtin.isdigit(), row
            assert _gtin_valid(gtin), row
        if ean and gtin:
            assert ean == gtin, row


def test_mapping_product_ids_belong_to_known_dufynd_products() -> None:
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]
    staged = json.loads(STAGING.read_text(encoding="utf-8"))["products"]
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["products"]
    known_ids = {row["product_id"] for row in staged} | {row["product_id"] for row in source}

    unknown = sorted(
        {str(row.get("product_id") or "") for row in rows if row.get("product_id") not in known_ids}
    )
    assert not unknown, f"merchant mappings reference unknown products: {unknown}"


def test_merchant_product_ids_are_not_reused_across_dufynd_products() -> None:
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]
    seen: dict[tuple[str, str], str] = {}

    for row in rows:
        merchant_product_id = str(row.get("merchant_product_id") or "").strip()
        if not merchant_product_id:
            continue

        key = (str(row.get("merchant") or "").strip(), merchant_product_id)
        product_id = str(row.get("product_id") or "")
        previous = seen.setdefault(key, product_id)
        assert previous == product_id, (
            f"{key[0]} product ID {key[1]} maps to both {previous} and {product_id}"
        )


def test_gtins_are_not_reused_across_dufynd_products() -> None:
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]
    seen: dict[str, str] = {}

    for row in rows:
        gtin = str(row.get("gtin") or row.get("ean") or "").strip()
        if not gtin:
            continue

        product_id = str(row.get("product_id") or "")
        previous = seen.setdefault(gtin, product_id)
        assert previous == product_id, f"GTIN {gtin} maps to both {previous} and {product_id}"


def test_mugler_alien_mapping_selects_edp_90ml_bottle() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_mugler_alien_edp_90_mapping_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    assert evidence["product_id"] == "SC-MUGLER-ALIEN-EDP-90"
    assert evidence["merchant_product_id"] == "388723"
    assert evidence["identity"]["concentration"] == "Eau de Parfum"
    assert evidence["identity"]["volume_ml"] == 90
    assert evidence["identity"]["gtin"] == "3439600056969"
    assert evidence["freshness_policy"]["current_purchase_destination_registered"] is False
    assert evidence["freshness_policy"]["price_or_stock_freshness_asserted"] is False
    assert any(
        row["product_id"] == evidence["product_id"]
        and row["merchant"] == "mueller"
        and row["merchant_product_id"] == evidence["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in rows
    )


def test_chloe_nomade_mapping_selects_original_edp_75ml() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_chloe_nomade_edp_75_mapping_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    assert evidence["product_id"] == "SC-CHLOE-NOMADE-EDP-75"
    assert evidence["merchant_product_id"] == "CHCA64994090"
    assert evidence["identity"]["concentration"] == "Eau de Parfum"
    assert evidence["identity"]["volume_ml"] == 75
    assert evidence["identity"]["gtin"] == "3614223113347"
    assert evidence["freshness_policy"]["current_purchase_destination_registered"] is False
    assert evidence["freshness_policy"]["price_or_stock_freshness_asserted"] is False
    assert any(
        row["product_id"] == evidence["product_id"]
        and row["merchant"] == "chloe"
        and row["merchant_product_id"] == evidence["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in rows
    )


def test_prada_paradigme_mapping_selects_edp_100ml_not_le_parfum() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_prada_paradigme_edp_100_mapping_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    assert evidence["product_id"] == "SC-PRADA-PARADIGME-EDP-100"
    assert evidence["merchant_product_id"] == "3614274172997"
    assert evidence["identity"]["concentration"] == "Eau de Parfum"
    assert evidence["identity"]["volume_ml"] == 100
    assert evidence["identity"]["gtin"] == "3614274172997"
    assert evidence["freshness_policy"]["current_purchase_destination_registered"] is False
    assert evidence["freshness_policy"]["price_or_stock_freshness_asserted"] is False
    assert any(
        row["product_id"] == evidence["product_id"]
        and row["merchant"] == "prada"
        and row["merchant_product_id"] == evidence["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in rows
    )


def test_gucci_flora_gardenia_mapping_selects_regular_edp_100ml_not_intense() -> None:
    evidence = json.loads(
        Path(
            "examples/retail/data/dufynd_gucci_flora_gorgeous_gardenia_edp_100_mapping_evidence.json"
        ).read_text(encoding="utf-8")
    )
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    assert evidence["product_id"] == "SC-GUCCI-FLORA-GORGEOUS-GARDENIA-EDP-100"
    assert evidence["merchant_product_id"] == "667343999990099"
    assert evidence["identity"]["concentration"] == "Eau de Parfum"
    assert evidence["identity"]["volume_ml"] == 100
    assert evidence["identity"]["gtin"] == "3616302022472"
    assert evidence["freshness_policy"]["current_purchase_destination_registered"] is False
    assert evidence["freshness_policy"]["price_or_stock_freshness_asserted"] is False
    assert any(
        row["product_id"] == evidence["product_id"]
        and row["merchant"] == "gucci"
        and row["merchant_product_id"] == evidence["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in rows
    )


def test_valentino_born_in_roma_mapping_selects_original_edp_100ml() -> None:
    evidence = json.loads(
        Path(
            "examples/retail/data/dufynd_valentino_born_in_roma_donna_edp_100_mapping_evidence.json"
        ).read_text(encoding="utf-8")
    )
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    assert evidence["product_id"] == "SC-VALENTINO-DONNA-BORN-IN-ROMA-EDP-100"
    assert evidence["merchant_product_id"] == "MPL00468"
    assert evidence["identity"]["concentration"] == "Eau de Parfum"
    assert evidence["identity"]["volume_ml"] == 100
    assert evidence["identity"]["gtin"] == "3614272761445"
    assert evidence["freshness_policy"]["current_purchase_destination_registered"] is False
    assert evidence["freshness_policy"]["price_or_stock_freshness_asserted"] is False
    assert any(
        row["product_id"] == evidence["product_id"]
        and row["merchant"] == "valentino"
        and row["merchant_product_id"] == evidence["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in rows
    )


def test_armani_profondo_mapping_selects_parfum_100ml_not_edt_or_edp() -> None:
    evidence = json.loads(
        Path(
            "examples/retail/data/dufynd_armani_profondo_parfum_100_mapping_evidence.json"
        ).read_text(encoding="utf-8")
    )
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    assert evidence["product_id"] == "SC-ARMANI-ACQUA-DI-GIO-PROFONDO-PARFUM-100"
    assert evidence["merchant_product_id"] == "LE309800-NLP-100ML"
    assert evidence["identity"]["concentration"] == "Parfum"
    assert evidence["identity"]["volume_ml"] == 100
    assert evidence["identity"]["gtin"] == "3614273953696"
    assert evidence["freshness_policy"]["current_purchase_destination_registered"] is False
    assert evidence["freshness_policy"]["price_or_stock_freshness_asserted"] is False
    assert any(
        row["product_id"] == evidence["product_id"]
        and row["merchant"] == "armani"
        and row["merchant_product_id"] == evidence["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in rows
    )


def test_afnan_9pm_femme_mapping_uses_rendered_identity_not_url_slug() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_afnan_9pm_femme_100_mapping_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    assert evidence["product_id"] == "SC-AFNAN-9-PM-POUR-FEMME-EDP-100"
    assert evidence["merchant_product_id"] == "AFN00282"
    assert evidence["identity"]["name"] == "9 PM Pour Femme"
    assert evidence["identity"]["concentration"] == "Eau de Parfum"
    assert evidence["identity"]["volume_ml"] == 100
    assert evidence["identity"]["gtin"] == "6290171072607"
    assert evidence["source_anomaly"]["rendered_product_name"] == "9 PM Pour Femme"
    assert "9-am" in evidence["source_anomaly"]["url_slug"]
    assert evidence["freshness_policy"]["current_purchase_destination_registered"] is False
    assert evidence["freshness_policy"]["price_or_stock_freshness_asserted"] is False
    assert any(
        row["product_id"] == evidence["product_id"]
        and row["merchant"] == "notino"
        and row["merchant_product_id"] == evidence["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in rows
    )
